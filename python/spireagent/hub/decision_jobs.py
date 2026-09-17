"""Durable bounded CPU dataset work; HTTP enqueues and reads, never projects archives."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from typing import Any

from spireagent.hub.collections import CollectionAccess
from spireagent.hub.console_auth import ConsolePrincipal
from spireagent.hub.curation import CurationLedger
from spireagent.hub.dataset_curation import DatasetCuration, specification
from spireagent.hub.uploads import UploadService
from spireagent.json_boundary import BoundaryError, digest, object_fields
from stpd.canonical import semantic_hash
from stpd.fullrun.contracts import SourceProjection
from stpd.fullrun.curated_dataset import SCHEMA as CURATED_SCHEMA
from stpd.fullrun.decision_cache import VerifiedSourceCache
from stpd.fullrun.decision_dataset import SelectionRules
from stpd.fullrun.decision_store import preview, preview_union, publish, publish_union
from stpd.fullrun.decision_union import UNION_SCHEMA
from stpd.fullrun.run_coverage import summarize_run_coverage


def _run_summary(run: dict[str, Any]) -> dict[str, Any]:
    """Keep full evidence inventories in stored profiles, not member overview responses."""
    return {
        **{key: value for key, value in run.items() if key != "journal_refs"},
        "journal_ref_count": (
            len(run["journal_refs"]) if "journal_refs" in run else run.get("journal_ref_count")
        ),
    }


class DecisionJobs:
    def __init__(self, service: UploadService) -> None:
        self.service = service
        self.collections = CollectionAccess(service)
        self.curation = CurationLedger(service.operations)
        with service.operations.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS decision_jobs("
                "id TEXT PRIMARY KEY,owner TEXT NOT NULL,request TEXT NOT NULL,"
                "state TEXT NOT NULL,result TEXT,error TEXT,created REAL NOT NULL,"
                "updated REAL NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS decision_job_visibility("
                "id TEXT NOT NULL,owner TEXT NOT NULL,archived INTEGER NOT NULL,"
                "PRIMARY KEY(id,owner))"
            )
            db.execute("CREATE INDEX IF NOT EXISTS decision_jobs_artifact ON decision_jobs("
                       "json_extract(result,'$.artifact_id'))")
            db.execute("CREATE TABLE IF NOT EXISTS decision_job_execution("
                       "id TEXT PRIMARY KEY,attempt INTEGER NOT NULL)")

    def set_archived(self, principal: ConsolePrincipal, body: object) -> dict[str, Any]:
        """Personal list cleanup; immutable sources, results and job state remain intact."""
        self.collections.require_member(principal)
        obj = object_fields(body, {"ids", "archived"}, "decision_job.visibility")
        ids = obj["ids"]
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 100
                or type(obj["archived"]) is not bool):
            raise BoundaryError("decision_job", "invalid_visibility_request")
        for identity in ids:
            digest(identity, "decision_job.id", length=32)
        with self.service.operations.transaction() as db:
            # Validate the whole batch before writing. Only your own terminal tasks may move.
            for identity in ids:
                row = db.execute("SELECT owner,state FROM decision_jobs WHERE id=?",
                                 (identity,)).fetchone()
                if row is None or row["owner"] != principal.subject:
                    raise BoundaryError("decision_job", "not_found")
                if row["state"] not in {"completed", "failed", "cancelled"}:
                    raise BoundaryError("decision_job", "active_job_cannot_be_archived")
            for identity in ids:
                db.execute("INSERT OR REPLACE INTO decision_job_visibility VALUES(?,?,?)",
                           (identity, principal.subject, int(obj["archived"])))
                self.service.operations._event(
                    db, principal.subject, "decision_job_visibility", identity,
                    {"archived": obj["archived"]})
        return {"ids": ids, "archived": obj["archived"]}

    def _sources(self, selections: object) -> tuple[Any, ...]:
        if not isinstance(selections, list) or not 1 <= len(selections) <= 100:
            raise BoundaryError("decision_job", "selection_limit")
        if any(not isinstance(value, str) for value in selections):
            raise BoundaryError("decision_job", "invalid_selection")
        if len(set(selections)) != len(selections):
            raise BoundaryError("decision_job", "duplicate_selection")
        sources = tuple(self.collections.collection(value) for value in selections)
        if any(s.parameters.value()["disposition"] != "verified" for s in sources):
            raise BoundaryError("decision_job", "source_not_verified")
        return sources

    def _inputs(
        self, request: dict[str, Any], *, receiver_profile: bool = False
    ) -> tuple[Any, ...]:
        if "datasets" not in request:
            sources = self._sources(request["uploads"])
            if "curation" not in request and not receiver_profile:
                from spireagent.hub.curation_access import guarded_runs

                for source in sources:
                    guarded_runs(self.service.operations, self.service.store, source)
            return sources
        selections = request["datasets"]
        if (not isinstance(selections, list) or not 1 <= len(selections) <= 100
                or any(not isinstance(value, str) for value in selections)
                or len(set(selections)) != len(selections)):
            raise BoundaryError("decision_job", "invalid_dataset_selection")
        if request.get("curation", {}).get("purpose") == "gold":
            # Trusted worker operation: Gold may compose only with other Gold. No
            # raw rows are returned by this path to a browser or local worker.
            parents = tuple(self.service.store.get_manifest(identity) for identity in selections)
            if any(p.parameters.value().get("purpose") != "gold" for p in parents):
                raise BoundaryError("curation", "gold_merge_requires_only_gold")
        else:
            parents = tuple(self.collections.artifact(identity) for identity in selections)
        if any(parent.kind != "dataset" or parent.parameters.value().get("schema")
               not in {"stpd/decision-dataset-v1", UNION_SCHEMA, CURATED_SCHEMA}
               for parent in parents):
            raise BoundaryError("decision_job", "unsupported_dataset_schema")
        return parents

    def _check_inputs(self, request: dict[str, Any]) -> None:
        """Check current indexed access on HTTP; the worker verifies actual artifacts.

        Reading a task must not fetch every selected archive manifest over the network.
        The immutable source checks still run before and after background processing.
        """
        merging = "datasets" in request
        selections = request["datasets" if merging else "uploads"]
        if not isinstance(selections, list) or not 1 <= len(selections) <= 100:
            raise BoundaryError("decision_job", "selection_limit")
        for value in selections:
            digest(value, "decision_job.selection", length=64 if merging else 32)
        if len(set(selections)) != len(selections):
            raise BoundaryError("decision_job", "duplicate_selection")
        with self.service.operations.transaction() as db:
            for value in selections:
                if not merging:
                    row = db.execute(
                        "SELECT u.status,u.receipt,s.approved FROM uploads u "
                        "LEFT JOIN collection_sharing s ON s.upload_id=u.id WHERE u.id=?",
                        (value,),
                    ).fetchone()
                    if row is None or row["approved"] == 0:
                        raise BoundaryError("sharing", "collection_not_shared")
                    if row["status"] != "verified" or not row["receipt"]:
                        raise BoundaryError("decision_job", "source_not_verified")
                else:
                    row = db.execute(
                        "SELECT kind,summary FROM console_artifacts WHERE artifact_id=?", (value,)
                    ).fetchone()
                    if row is None or row["kind"] != "dataset":
                        raise BoundaryError("decision_job", "dataset_not_available")
                    if json.loads(row["summary"])["metadata"].get("schema") not in {
                        "stpd/decision-dataset-v1", UNION_SCHEMA, CURATED_SCHEMA,
                    }:
                        raise BoundaryError("decision_job", "unsupported_dataset_schema")
                    withdrawn = db.execute(
                        "WITH RECURSIVE ancestors(id) AS (SELECT ? UNION SELECT parent "
                        "FROM console_lineage JOIN ancestors ON child=id) "
                        "SELECT 1 FROM uploads u JOIN collection_sharing s "
                        "ON s.upload_id=u.id "
                        "WHERE s.approved=0 "
                        "AND json_extract(u.receipt,'$.evidence_id') IN ancestors "
                        "LIMIT 1", (value,),
                    ).fetchone()
                    if withdrawn:
                        raise BoundaryError("sharing", "source_sharing_not_established")

    def create(self, principal: ConsolePrincipal, body: object) -> dict[str, Any]:
        self.collections.require_member(principal)
        source_key = "datasets" if isinstance(body, dict) and "datasets" in body else "uploads"
        fields = {source_key, "rules", "preview_id", "name"}
        if isinstance(body, dict) and "curation" in body:
            fields.add("curation")
        obj = object_fields(body, fields, "decision_job")
        obj = {**obj, "curation": specification(obj.get("curation", {
            "purpose": "training", "paired_training": None,
        }))}
        self._check_inputs(obj)
        rules = SelectionRules.decode(obj["rules"])
        if not isinstance(obj["name"], str) or not 1 <= len(obj["name"]) <= 100:
            raise BoundaryError("decision_job", "invalid_name")
        expected = None
        if obj["preview_id"] is not None:
            previous = self.read(principal, obj["preview_id"])
            if (
                previous["state"] != "completed"
                or previous["request"]["preview_id"] is not None
                or previous["request"].get(source_key) != obj[source_key]
                or previous["request"]["rules"] != rules.to_dict()
                or previous["request"].get("curation") != obj["curation"]
            ):
                raise BoundaryError("decision_job", "preview_mismatch")
            expected = previous["result"]["logical_id"]
        request = {**obj, "rules": rules.to_dict(), "expected": expected}
        identity = uuid.uuid4().hex
        now = time.time()
        with self.service.operations.transaction() as db:
            pending = db.execute(
                "SELECT count(*) FROM decision_jobs WHERE state IN ('pending','running')"
            ).fetchone()[0]
            if pending >= 10:
                raise BoundaryError("decision_job", "queue_full")
            db.execute(
                "INSERT INTO decision_jobs VALUES(?,?,?,'pending',NULL,NULL,?,?)",
                (identity, principal.subject, json.dumps(request), now, now),
            )
        return {"id": identity, "state": "pending"}

    def read(self, principal: ConsolePrincipal, identity: str) -> dict[str, Any]:
        self.collections.require_member(principal)
        digest(identity, "decision_job.id", length=32)
        with self.service.operations.transaction() as db:
            row = db.execute("SELECT * FROM decision_jobs WHERE id=?", (identity,)).fetchone()
        if row is None or (
            row["owner"] not in {principal.subject, "receiver"} and principal.role != "admin"
        ):
            raise BoundaryError("decision_job", "not_found")
        request = json.loads(row["request"])
        self._check_inputs(request)
        result = json.loads(row["result"]) if row["result"] else None
        if result and isinstance(result.get("runs"), list):
            result = {**result, "runs": [_run_summary(run) for run in result["runs"]]}
        return {
            "id": identity,
            "state": row["state"],
            "request": request,
            "result": result if row["state"] == "completed" else None,
            "progress": result.get("progress") if result else {"phase": row["state"]},
            "created_at": row["created"], "updated_at": row["updated"],
            "recovery": "explicit_retry" if row["state"] == "failed" else "observe_existing_job",
            "error": row["error"],
        }

    def materialize(self, principal: ConsolePrincipal, body: object) -> dict[str, Any]:
        self.collections.require_member(principal)
        obj = object_fields(body, {"dataset_id"}, "dataset.materialize")
        source = self.collections.artifact(digest(obj["dataset_id"], "dataset.id"))
        info = source.parameters.value()
        if info.get("schema") != CURATED_SCHEMA:
            raise BoundaryError("dataset", "materialization_not_required")
        now = time.time()
        with self.service.operations.transaction() as db:
            previous = db.execute(
                "SELECT id,state FROM decision_jobs WHERE owner=? AND "
                "json_extract(request,'$.materialize')=? ORDER BY created DESC LIMIT 1",
                (principal.subject, source.artifact_id),
            ).fetchone()
            if previous:
                return {"id": previous["id"], "state": previous["state"]}
            if db.execute("SELECT count(*) FROM decision_jobs WHERE state IN "
                          "('pending','running')").fetchone()[0] >= 10:
                raise BoundaryError("decision_job", "queue_full")
            identity = uuid.uuid4().hex
            request = {"datasets": [source.artifact_id], "rules": info["rules"],
                       "preview_id": None, "name": "准备数据集下载", "expected": None,
                       "materialize": source.artifact_id}
            db.execute("INSERT INTO decision_jobs VALUES(?,?,?,'pending',NULL,NULL,?,?)",
                       (identity, principal.subject, json.dumps(request), now, now))
        return {"id": identity, "state": "pending"}

    def list(self, principal: ConsolePrincipal, *, archived: bool = False,
             limit: int = 50, offset: int = 0) -> dict[str, Any]:
        self.collections.require_member(principal)
        with self.service.operations.transaction() as db:
            where = (" FROM decision_jobs j LEFT JOIN decision_job_visibility v "
                     "ON v.id=j.id AND v.owner=j.owner WHERE j.owner=? "
                     "AND COALESCE(v.archived,0)=?")
            total = db.execute("SELECT count(*)" + where,
                               (principal.subject, int(archived))).fetchone()[0]
            rows = db.execute("SELECT j.id" + where + " ORDER BY j.created DESC,j.id "
                              "LIMIT ? OFFSET ?",
                              (principal.subject, int(archived), limit, offset)).fetchall()
        items = []
        for row in rows:
            try:
                items.append(self.read(principal, row[0]))
            except BoundaryError as error:
                if error.code not in {"collection_not_shared", "source_sharing_not_established"}:
                    raise
        return {"items": items, "limit": limit, "offset": offset, "total": total,
                "next_offset": offset + limit if offset + limit < total else None,
                "archived": archived}

    def retry(self, principal: ConsolePrincipal, identity: str, body: object) -> dict[str, Any]:
        if body != {}:
            raise BoundaryError("decision_job", "unexpected_retry_fields")
        prior = self.read(principal, identity)
        if prior["state"] not in {"failed", "cancelled"}:
            raise BoundaryError("decision_job", "retry_requires_failed_job")
        with self.service.operations.transaction() as db:
            if (
                db.execute(
                    "SELECT count(*) FROM decision_jobs WHERE state IN ('pending','running')"
                ).fetchone()[0]
                >= 10
            ):
                raise BoundaryError("decision_job", "queue_full")
            changed = db.execute(
                "UPDATE decision_jobs SET state='pending',error=NULL,updated=? "
                "WHERE id=? AND state IN ('failed','cancelled')", (time.time(), identity),
            ).rowcount
            if changed != 1:
                raise BoundaryError("decision_job", "retry_requires_failed_job")
            self.service.operations._event(
                db, principal.subject, "decision_job_retry", identity,
                {"previous_state": prior["state"], "previous_error": prior["error"],
                 "previous_updated_at": prior["updated_at"], "progress": prior["progress"]},
            )
        return {"id": identity, "state": "pending"}

    def cancel(self, principal: ConsolePrincipal, identity: str, body: object) -> dict[str, Any]:
        if body != {}:
            raise BoundaryError("decision_job", "unexpected_cancel_fields")
        self.read(principal, identity)
        with self.service.operations.transaction() as db:
            row = db.execute("SELECT state,result FROM decision_jobs WHERE id=?",
                             (identity,)).fetchone()
            if row["state"] not in {"pending", "running"}:
                raise BoundaryError("decision_job", "cancel_requires_active_job")
            progress = json.loads(row["result"] or "{}").get("progress", {})
            if row["state"] == "running" and progress.get("phase") == "publishing_dataset":
                raise BoundaryError("decision_job", "publication_already_started")
            db.execute("UPDATE decision_jobs SET state='cancelled',updated=? WHERE id=?",
                       (time.time(), identity))
            db.execute("UPDATE decision_job_execution SET attempt=attempt+1 WHERE id=?",
                       (identity,))
            self.service.operations._event(
                db, principal.subject, "decision_job_cancel", identity, {})
        return {"id": identity, "state": "cancelled"}

    def next_attempt(self, identity: str) -> int:
        with closing(self.service.console_index.read()) as db:
            row = db.execute("SELECT attempt FROM decision_job_execution WHERE id=?",
                             (identity,)).fetchone()
        return int(row[0]) + 1 if row else 1

    def should_stop(self, identity: str, attempt: int) -> bool:
        with closing(self.service.console_index.read()) as db:
            row = db.execute("SELECT j.state,e.attempt FROM decision_jobs j "
                             "LEFT JOIN decision_job_execution e ON e.id=j.id WHERE j.id=?",
                             (identity,)).fetchone()
        return row is None or row["state"] == "cancelled" or (
            row["attempt"] is not None and row["attempt"] > attempt
        )

    def games(self, principal: ConsolePrincipal) -> dict[str, Any]:
        self.collections.require_member(principal)
        with self.service.operations.transaction() as db:
            rows = db.execute(
                "SELECT j.request,j.result FROM decision_jobs j LEFT JOIN collection_sharing s "
                "ON s.upload_id=json_extract(j.request,'$.uploads[0]') "
                "WHERE j.owner='receiver' AND j.state='completed' AND COALESCE(s.approved,1)=1 "
                "ORDER BY j.created DESC"
            ).fetchall()
            waiting = db.execute(
                "SELECT count(*) FROM decision_jobs j LEFT JOIN collection_sharing s "
                "ON s.upload_id=json_extract(j.request,'$.uploads[0]') "
                "WHERE j.owner='receiver' AND j.state IN ('pending','running') "
                "AND COALESCE(s.approved,1)=1"
            ).fetchone()[0]
            failures = db.execute(
                "SELECT j.id,j.error,json_extract(j.request,'$.uploads[0]') AS upload_id "
                "FROM decision_jobs j LEFT JOIN collection_sharing s "
                "ON s.upload_id=json_extract(j.request,'$.uploads[0]') "
                "WHERE j.owner='receiver' AND j.state='failed' AND COALESCE(s.approved,1)=1 "
                "AND NOT EXISTS (SELECT 1 FROM decision_jobs newer WHERE newer.owner='receiver' "
                "AND newer.state='completed' AND newer.updated>j.updated AND "
                "json_extract(newer.request,'$.uploads[0]')="
                "json_extract(j.request,'$.uploads[0]')) "
                "ORDER BY j.created DESC"
            ).fetchall()
            shared = db.execute(
                "SELECT count(*) FROM uploads u LEFT JOIN collection_sharing s ON s.upload_id=u.id "
                "WHERE u.status='verified' AND COALESCE(s.approved,1)=1"
            ).fetchone()[0]
        games: dict[str, Any] = {}
        profiled = set()
        failed: dict[str, Any] = {}
        for row in failures:
            failed.setdefault(row["upload_id"], dict(row))
        for row in rows:
            upload = json.loads(row["request"])["uploads"][0]
            if upload in profiled:
                continue
            profiled.add(upload)
            result = json.loads(row["result"])
            coverage = {r["run_id"]: r for r in result.get("run_coverage", [])}
            for run in result["runs"]:
                displayed = {
                    **_run_summary(run),
                    "coverage": coverage.get(run["run_id"]),
                }
                previous = games.setdefault(run["run_id"], {**displayed, "uploads": []})
                previous["uploads"].append(upload)
                if any(previous[key] != run[key] for key in ("complete", "outcome", "canonical")):
                    previous["coverage_status"] = "overlapping_exports_differ"
        return {
            "items": list(games.values()),
            "profile_limit": None,
            "shared_recordings": shared,
            "profiled_recordings": len(profiled),
            "missing_profiles": max(0, shared - len(profiled)),
            "partial": shared != len(profiled),
            "pending_profiles": waiting,
            "failed_profiles": len(failed),
            "failures": list(failed.values())[:100],
            "failure_detail_limit": 100,
            "scope": "all_available_shared_recording_profiles",
            "non_claims": ["global unique game count", "independent training examples"],
        }

    def pending(self) -> str | None:
        with self.service.operations.transaction() as db:
            # A crashed bounded worker never becomes a silent successful job or automatic retry.
            db.execute(
                "UPDATE decision_jobs SET state='failed',error='worker_interrupted' "
                "WHERE state='running' AND updated<?",
                (time.time() - 180,),
            )
            # One bounded automatic profile per tick; never done by an HTTP reader.
            source = db.execute(
                "SELECT u.id FROM uploads u LEFT JOIN collection_sharing s ON s.upload_id=u.id "
                "WHERE u.status='verified' AND COALESCE(s.approved,1)=1 AND NOT EXISTS "
                "(SELECT 1 FROM decision_jobs j WHERE j.owner='receiver' AND "
                "json_extract(j.request,'$.uploads[0]')=u.id AND "
                "(json_extract(j.request,'$.profile_schema')='stpd/run-coverage-v1' OR "
                "json_type(j.result,'$.run_coverage')='array')) ORDER BY u.id LIMIT 1"
            ).fetchone()
            queue_size = db.execute(
                "SELECT count(*) FROM decision_jobs WHERE state IN ('pending','running')"
            ).fetchone()[0]
            if source and queue_size < 10:
                now = time.time()
                request = {
                    "uploads": [source[0]],
                    "rules": SelectionRules().to_dict(),
                    "preview_id": None,
                    "name": "自动对局整理",
                    "profile_schema": "stpd/run-coverage-v1",
                    "expected": None,
                }
                db.execute(
                    "INSERT INTO decision_jobs VALUES(?,?,?,'pending',NULL,NULL,?,?)",
                    (uuid.uuid4().hex, "receiver", json.dumps(request), now, now),
                )
            row = db.execute(
                "SELECT id FROM decision_jobs WHERE state='pending' "
                "ORDER BY (owner='receiver'),created,id LIMIT 1"
            ).fetchone()
        return row[0] if row else None

    def fail(self, identity: str, reason: str, *, attempt: int | None = None) -> None:
        with self.service.operations.transaction() as db:
            db.execute(
                "UPDATE decision_jobs SET state='failed',error=?,updated=? "
                "WHERE id=? AND state IN ('pending','running') AND (? IS NULL OR EXISTS "
                "(SELECT 1 FROM decision_job_execution e "
                "WHERE e.id=decision_jobs.id AND e.attempt=?) OR (state='pending' AND "
                "COALESCE((SELECT attempt FROM decision_job_execution e "
                "WHERE e.id=decision_jobs.id),0)=?-1))",
                (reason, time.time(), identity, attempt, attempt, attempt),
            )

    def run(self, identity: str) -> None:
        digest(identity, "decision_job.id", length=32)
        with self.service.operations.transaction() as db:
            changed = db.execute(
                "UPDATE decision_jobs SET state='running',updated=? WHERE id=? AND state='pending'",
                (time.time(), identity),
            ).rowcount
            if changed != 1:
                return
            row = db.execute("SELECT * FROM decision_jobs WHERE id=?", (identity,)).fetchone()
            db.execute("INSERT INTO decision_job_execution VALUES(?,1) ON CONFLICT(id) "
                       "DO UPDATE SET attempt=attempt+1", (identity,))
            attempt = db.execute("SELECT attempt FROM decision_job_execution WHERE id=?",
                                 (identity,)).fetchone()[0]
        started = time.monotonic()
        cache = VerifiedSourceCache(
            self.service.operations.path, semantic_hash(self.service.producer.to_dict())
        )

        def progress(phase: str, completed: int, total: int) -> None:
            value = {"progress": {
                "phase": phase, "completed": completed, "total": total,
                "observed_at": time.time(), "elapsed_seconds": time.monotonic() - started,
                **cache.metrics(),
            }}
            with self.service.operations.transaction() as db:
                changed = db.execute(
                    "UPDATE decision_jobs SET result=?,updated=? WHERE id=? AND state='running' "
                    "AND EXISTS (SELECT 1 FROM decision_job_execution e "
                    "WHERE e.id=decision_jobs.id AND e.attempt=?)",
                    (json.dumps(value), time.time(), identity, attempt),
                ).rowcount
                if changed != 1:
                    raise BoundaryError("decision_job", "job_cancelled_or_superseded")

        stopped = threading.Event()

        def heartbeat() -> None:
            while not stopped.wait(15):
                try:
                    with self.service.operations.transaction() as db:
                        changed = db.execute(
                            "UPDATE decision_jobs SET updated=? WHERE id=? AND state='running' "
                            "AND EXISTS (SELECT 1 FROM decision_job_execution e "
                            "WHERE e.id=decision_jobs.id AND e.attempt=?)",
                            (time.time(), identity, attempt),
                        ).rowcount
                    if changed != 1:
                        return
                except sqlite3.OperationalError:
                    # Writer contention does not fabricate a fresh lease.
                    continue

        pulse = threading.Thread(target=heartbeat, name="dataset-heartbeat", daemon=True)
        pulse.start()

        try:
            progress("checking_access", 0, 1)
            with self.service.operations.transaction() as db:
                member = db.execute(
                    "SELECT 1 FROM identity_members WHERE subject=? AND status='active'",
                    (row["owner"],),
                ).fetchone()
            if not member and row["owner"] != "receiver":
                raise BoundaryError("decision_job", "membership_not_authorized")
            request = json.loads(row["request"])
            receiver_profile = (row["owner"] == "receiver"
                                and request.get("profile_schema") == "stpd/run-coverage-v1"
                                and request["expected"] is None
                                and "datasets" not in request)
            sources = self._inputs(request, receiver_profile=receiver_profile)
            rules = SelectionRules.decode(request["rules"])
            merging = "datasets" in request
            coverage: dict[str, Any] = {}

            def collect_coverage(projection: SourceProjection) -> None:
                if "curation" not in request:
                    source = next(s for s in sources
                                  if s.payload("archive").sha256 == projection.source_sha256)
                    self.curation.index_source(source.artifact_id, projection)
                for run in summarize_run_coverage(projection)["runs"]:
                    prior = coverage.setdefault(run["run_id"], run)
                    if prior != run:
                        # Overlapping exports cannot synthesize continuity.
                        coverage[run["run_id"]] = {**prior,
                            "native_boundary_complete": False,
                            "boundary_status": "overlapping_exports_differ",
                            "recording_continuity": "unknown"}

            if request.get("materialize"):
                manifest = DatasetCuration(self.service, cache).materialize(sources[0], progress)
                self.service.console_index.artifact_closure(self.service.store,
                                                           (manifest.artifact_id,))
                result = {"artifact_id": manifest.artifact_id, **manifest.parameters.value()}
            elif request["expected"] is None:
                if "curation" in request:
                    dataset = DatasetCuration(self.service, cache).select(
                        sources, request, progress, on_projection=collect_coverage)
                elif merging:
                    dataset = preview_union(self.service.store, sources, rules,
                                            cache=cache, progress=progress)
                else:
                    dataset = preview(self.service.store, sources, rules,
                                      cache=cache, progress=progress,
                                      on_projection=collect_coverage)
                report = dataset.report.value()
                selected_runs = {r.run_id for r in dataset.records}
                if row["owner"] == "receiver":
                    from spireagent.hub.statistics import DIMENSIONS, _persist, decision_profile

                    profile = decision_profile(dataset.records)
                    for name in DIMENSIONS:
                        profile["facets"][name] = report["selected_facets"][
                            "family" if name == "action_family" else name
                        ]
                    profile.update(
                        availability="available",
                        scope="source_projection",
                        admission="not_evaluated",
                    )
                    _persist(
                        self.service,
                        request["uploads"][0],
                        "collection",
                        sources[0].artifact_id,
                        profile,
                    )
                result = {
                    "logical_id": dataset.logical_id,
                    "selected": len(dataset.records),
                    "runs": [r for r in report["runs"] if r["run_id"] in selected_runs],
                    "selected_facets": report["selected_facets"],
                    "exclusion_counts": report["exclusion_counts"],
                    "exact_duplicate_decisions": report["exact_duplicate_decisions"],
                    "split_status": report["split_status"],
                    "non_claims": report["non_claims"],
                    **({"purpose": request["curation"]["purpose"],
                        "paired_training": request["curation"]["paired_training"]}
                       if "curation" in request else {}),
                }
            else:
                if "curation" in request:
                    manifest = DatasetCuration(self.service, cache).publish(
                        identity, sources, request, progress)
                else:
                    manifest = (publish_union if merging else publish)(
                        self.service.store, sources, rules, self.service.producer,
                        request["expected"], cache=cache, progress=progress)
                self.service.console_index.artifact_closure(
                    self.service.store, (manifest.artifact_id,)
                )
                result = {"artifact_id": manifest.artifact_id, **manifest.parameters.value()}
            if request["expected"] is None and not merging:
                result["run_coverage"] = list(coverage.values())
            self._inputs(request, receiver_profile=receiver_profile)
            result["progress"] = {
                "phase": "completed", "completed": 1, "total": 1,
                "observed_at": time.time(), "elapsed_seconds": time.monotonic() - started,
                **cache.metrics(),
            }
            with self.service.operations.transaction() as db:
                if (
                    row["owner"] != "receiver"
                    and not db.execute(
                        "SELECT 1 FROM identity_members WHERE subject=? AND status='active'",
                        (row["owner"],),
                    ).fetchone()
                ):
                    raise BoundaryError("decision_job", "membership_not_authorized")
                db.execute(
                    "UPDATE decision_jobs SET state='completed',result=?,updated=? "
                    "WHERE id=? AND state='running' AND EXISTS "
                    "(SELECT 1 FROM decision_job_execution e "
                    "WHERE e.id=decision_jobs.id AND e.attempt=?)",
                    (json.dumps(result), time.time(), identity, attempt),
                )
        except (ValueError, OSError) as error:
            self.fail(
                identity, error.code if isinstance(error, BoundaryError) else "processing_failed",
                attempt=attempt,
            )
        except MemoryError:
            self.fail(identity, "worker_memory_limit", attempt=attempt)
        finally:
            stopped.set()
            pulse.join(timeout=1)
