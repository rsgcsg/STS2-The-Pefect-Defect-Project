"""Durable bounded CPU dataset work; HTTP enqueues and reads, never projects archives."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from spireagent.hub.collections import CollectionAccess
from spireagent.hub.console_auth import ConsolePrincipal
from spireagent.hub.uploads import UploadService
from spireagent.json_boundary import BoundaryError, digest, object_fields
from stpd.canonical import semantic_hash
from stpd.fullrun.decision_cache import VerifiedSourceCache
from stpd.fullrun.decision_dataset import SelectionRules
from stpd.fullrun.decision_store import preview, preview_union, publish, publish_union
from stpd.fullrun.decision_union import UNION_SCHEMA
from stpd.fullrun.run_coverage import summarize_run_coverage


class DecisionJobs:
    def __init__(self, service: UploadService) -> None:
        self.service = service
        self.collections = CollectionAccess(service)
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
                if row["state"] not in {"completed", "failed"}:
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

    def _inputs(self, request: dict[str, Any]) -> tuple[Any, ...]:
        if "datasets" not in request:
            return self._sources(request["uploads"])
        selections = request["datasets"]
        if (not isinstance(selections, list) or not 1 <= len(selections) <= 100
                or any(not isinstance(value, str) for value in selections)
                or len(set(selections)) != len(selections)):
            raise BoundaryError("decision_job", "invalid_dataset_selection")
        parents = tuple(self.collections.artifact(identity) for identity in selections)
        if any(parent.kind != "dataset" or parent.parameters.value().get("schema")
               not in {"stpd/decision-dataset-v1", UNION_SCHEMA} for parent in parents):
            raise BoundaryError("decision_job", "unsupported_dataset_schema")
        return parents

    def create(self, principal: ConsolePrincipal, body: object) -> dict[str, Any]:
        self.collections.require_member(principal)
        source_key = "datasets" if isinstance(body, dict) and "datasets" in body else "uploads"
        obj = object_fields(body, {source_key, "rules", "preview_id", "name"}, "decision_job")
        self._inputs(obj)
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
        self._inputs(request)
        result = json.loads(row["result"]) if row["result"] else None
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
        if prior["state"] != "failed":
            raise BoundaryError("decision_job", "retry_requires_failed_job")
        with self.service.operations.transaction() as db:
            if (
                db.execute(
                    "SELECT count(*) FROM decision_jobs WHERE state IN ('pending','running')"
                ).fetchone()[0]
                >= 10
            ):
                raise BoundaryError("decision_job", "queue_full")
            old = db.execute(
                "SELECT owner,request FROM decision_jobs WHERE id=?", (identity,)
            ).fetchone()
            new_id, now = uuid.uuid4().hex, time.time()
            db.execute(
                "INSERT INTO decision_jobs VALUES(?,?,?,'pending',NULL,NULL,?,?)",
                (new_id, old["owner"], old["request"], now, now),
            )
            self.service.operations._event(
                db, principal.subject, "decision_job_retry", new_id, {"previous_job": identity}
            )
        return {"id": new_id, "state": "pending"}

    def games(self, principal: ConsolePrincipal) -> dict[str, Any]:
        self.collections.require_member(principal)
        with self.service.operations.transaction() as db:
            rows = db.execute(
                "SELECT j.request,j.result FROM decision_jobs j JOIN collection_sharing s "
                "ON s.upload_id=json_extract(j.request,'$.uploads[0]') "
                "WHERE j.owner='receiver' AND j.state='completed' AND s.approved=1 "
                "ORDER BY j.created DESC"
            ).fetchall()
            waiting = db.execute(
                "SELECT count(*) FROM decision_jobs j JOIN collection_sharing s "
                "ON s.upload_id=json_extract(j.request,'$.uploads[0]') "
                "WHERE j.owner='receiver' AND j.state IN ('pending','running') AND s.approved=1"
            ).fetchone()[0]
            failures = db.execute(
                "SELECT j.id,j.error,json_extract(j.request,'$.uploads[0]') AS upload_id "
                "FROM decision_jobs j JOIN collection_sharing s "
                "ON s.upload_id=json_extract(j.request,'$.uploads[0]') "
                "WHERE j.owner='receiver' AND j.state='failed' AND s.approved=1 "
                "AND NOT EXISTS (SELECT 1 FROM decision_jobs newer WHERE newer.owner='receiver' "
                "AND newer.state='completed' AND newer.updated>j.updated AND "
                "json_extract(newer.request,'$.uploads[0]')="
                "json_extract(j.request,'$.uploads[0]')) "
                "ORDER BY j.created DESC"
            ).fetchall()
            shared = db.execute(
                "SELECT count(*) FROM uploads u JOIN collection_sharing s ON s.upload_id=u.id "
                "WHERE u.status='verified' AND s.approved=1"
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
                displayed = {**run, "coverage": coverage.get(run["run_id"])}
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
                "SELECT u.id FROM uploads u JOIN collection_sharing s ON s.upload_id=u.id "
                "WHERE u.status='verified' AND s.approved=1 AND NOT EXISTS "
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

    def fail(self, identity: str, reason: str) -> None:
        with self.service.operations.transaction() as db:
            db.execute(
                "UPDATE decision_jobs SET state='failed',error=?,updated=? "
                "WHERE id=? AND state IN ('pending','running')",
                (reason, time.time(), identity),
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
                db.execute(
                    "UPDATE decision_jobs SET result=?,updated=? WHERE id=? AND state='running'",
                    (json.dumps(value), time.time(), identity),
                )

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
            sources = self._inputs(request)
            rules = SelectionRules.decode(request["rules"])
            merging = "datasets" in request
            if request["expected"] is None:
                dataset = (preview_union if merging else preview)(
                    self.service.store, sources, rules, cache=cache, progress=progress
                )
                report = dataset.report.value()
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
                    "runs": report["runs"],
                    "selected_facets": report["selected_facets"],
                    "exclusion_counts": report["exclusion_counts"],
                    "exact_duplicate_decisions": report["exact_duplicate_decisions"],
                    "split_status": report["split_status"],
                    "non_claims": report["non_claims"],
                }
            else:
                manifest = (publish_union if merging else publish)(
                    self.service.store, sources, rules, self.service.producer, request["expected"],
                    cache=cache, progress=progress,
                )
                self.service.console_index.artifact_closure(
                    self.service.store, (manifest.artifact_id,)
                )
                result = {"artifact_id": manifest.artifact_id, **manifest.parameters.value()}
            if request["expected"] is None and not merging:
                coverage = {}
                for source in sources:
                    payload = source.payload("archive")
                    raw = b"".join(self.service.store.read_payload(payload))
                    projection, _ = cache.resolve(raw)
                    for run in summarize_run_coverage(projection)["runs"]:
                        prior = coverage.setdefault(run["run_id"], run)
                        if prior != run:
                            # Overlapping exports do not synthesize continuity.
                            coverage[run["run_id"]] = {**prior,
                                "native_boundary_complete": False,
                                "boundary_status": "overlapping_exports_differ",
                                "recording_continuity": "unknown"}
                result["run_coverage"] = list(coverage.values())
            self._inputs(request)
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
                    "WHERE id=? AND state='running'",
                    (json.dumps(result), time.time(), identity),
                )
        except (ValueError, OSError) as error:
            self.fail(
                identity, error.code if isinstance(error, BoundaryError) else "processing_failed"
            )
