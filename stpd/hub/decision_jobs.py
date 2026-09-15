"""Durable bounded CPU dataset work; HTTP enqueues and reads, never projects archives."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from ..fullrun.decision_dataset import SelectionRules
from ..fullrun.decision_store import preview, publish
from ..json_boundary import BoundaryError, digest, object_fields
from .console_auth import ConsolePrincipal
from .exports import ExportService
from .uploads import UploadService


class DecisionJobs:
    def __init__(self, service: UploadService) -> None:
        self.service = service
        self.exports = ExportService(service)
        with service.operations.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS decision_jobs("
                "id TEXT PRIMARY KEY,owner TEXT NOT NULL,request TEXT NOT NULL,"
                "state TEXT NOT NULL,result TEXT,error TEXT,created REAL NOT NULL,"
                "updated REAL NOT NULL)"
            )

    def _sources(self, selections: object) -> tuple[Any, ...]:
        if not isinstance(selections, list) or not 1 <= len(selections) <= 100:
            raise BoundaryError("decision_job", "selection_limit")
        if any(not isinstance(value, str) for value in selections):
            raise BoundaryError("decision_job", "invalid_selection")
        if len(set(selections)) != len(selections):
            raise BoundaryError("decision_job", "duplicate_selection")
        sources = tuple(self.exports._collection(value) for value in selections)
        if any(s.parameters.value()["disposition"] != "verified" for s in sources):
            raise BoundaryError("decision_job", "source_not_verified")
        return sources

    def create(self, principal: ConsolePrincipal, body: object) -> dict[str, Any]:
        self.exports._member(principal)
        obj = object_fields(body, {"uploads", "rules", "preview_id", "name"}, "decision_job")
        self._sources(obj["uploads"])
        rules = SelectionRules.decode(obj["rules"])
        if not isinstance(obj["name"], str) or not 1 <= len(obj["name"]) <= 100:
            raise BoundaryError("decision_job", "invalid_name")
        expected = None
        if obj["preview_id"] is not None:
            previous = self.read(principal, obj["preview_id"])
            if (
                previous["state"] != "completed"
                or previous["request"]["preview_id"] is not None
                or previous["request"]["uploads"] != obj["uploads"]
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
        self.exports._member(principal)
        digest(identity, "decision_job.id", length=32)
        with self.service.operations.transaction() as db:
            row = db.execute("SELECT * FROM decision_jobs WHERE id=?", (identity,)).fetchone()
        if row is None or (
            row["owner"] not in {principal.subject, "receiver"} and principal.role != "admin"
        ):
            raise BoundaryError("decision_job", "not_found")
        request = json.loads(row["request"])
        self._sources(request["uploads"])
        return {
            "id": identity,
            "state": row["state"],
            "request": request,
            "result": json.loads(row["result"]) if row["result"] else None,
            "error": row["error"],
        }

    def list(self, principal: ConsolePrincipal) -> dict[str, Any]:
        self.exports._member(principal)
        with self.service.operations.transaction() as db:
            rows = db.execute(
                "SELECT id FROM decision_jobs WHERE owner=? ORDER BY created DESC LIMIT 50",
                (principal.subject,),
            ).fetchall()
        items = []
        for row in rows:
            try:
                items.append(self.read(principal, row[0]))
            except BoundaryError as error:
                if error.code not in {"collection_not_shared", "source_sharing_not_established"}:
                    raise
        return {"items": items, "limit": 50}

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
        self.exports._member(principal)
        with self.service.operations.transaction() as db:
            rows = db.execute(
                "SELECT j.request,j.result FROM decision_jobs j JOIN collection_sharing s "
                "ON s.upload_id=json_extract(j.request,'$.uploads[0]') "
                "WHERE j.owner='receiver' AND j.state='completed' AND s.approved=1 "
                "ORDER BY j.created DESC LIMIT 100"
            ).fetchall()
            waiting = db.execute(
                "SELECT count(*) FROM decision_jobs WHERE owner='receiver' "
                "AND state IN ('pending','running')"
            ).fetchone()[0]
            failures = db.execute(
                "SELECT j.id,j.error FROM decision_jobs j JOIN collection_sharing s "
                "ON s.upload_id=json_extract(j.request,'$.uploads[0]') "
                "WHERE j.owner='receiver' AND j.state='failed' AND s.approved=1 "
                "AND NOT EXISTS (SELECT 1 FROM decision_jobs newer WHERE newer.owner='receiver' "
                "AND newer.state='completed' AND newer.updated>j.updated AND "
                "json_extract(newer.request,'$.uploads[0]')=json_extract(j.request,'$.uploads[0]')) "
                "ORDER BY j.created DESC LIMIT 100"
            ).fetchall()
        games: dict[str, Any] = {}
        for row in rows:
            upload = json.loads(row["request"])["uploads"][0]
            for run in json.loads(row["result"])["runs"]:
                previous = games.setdefault(run["run_id"], {**run, "uploads": []})
                previous["uploads"].append(upload)
                if any(previous[key] != run[key] for key in ("complete", "outcome", "canonical")):
                    previous["coverage_status"] = "overlapping_exports_differ"
        return {
            "items": list(games.values()),
            "profile_limit": 100,
            "pending_profiles": waiting,
            "failed_profiles": len(failures),
            "failures": [dict(row) for row in failures],
            "scope": "latest_100_shared_recording_profiles",
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
                "json_extract(j.request,'$.uploads[0]')=u.id) ORDER BY u.id LIMIT 1"
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
        try:
            with self.service.operations.transaction() as db:
                member = db.execute(
                    "SELECT 1 FROM identity_members WHERE subject=? AND status='active'",
                    (row["owner"],),
                ).fetchone()
            if not member and row["owner"] != "receiver":
                raise BoundaryError("decision_job", "membership_not_authorized")
            request = json.loads(row["request"])
            sources = self._sources(request["uploads"])
            rules = SelectionRules.decode(request["rules"])
            if request["expected"] is None:
                dataset = preview(self.service.store, sources, rules)
                report = dataset.report.value()
                result = {
                    "logical_id": dataset.logical_id,
                    "selected": len(dataset.records),
                    "runs": report["runs"],
                    "exclusion_counts": report["exclusion_counts"],
                    "exact_duplicate_decisions": report["exact_duplicate_decisions"],
                    "split_status": report["split_status"],
                    "non_claims": report["non_claims"],
                }
            else:
                manifest = publish(
                    self.service.store, sources, rules, self.service.producer, request["expected"]
                )
                self.service.console_index.artifact_closure(
                    self.service.store, (manifest.artifact_id,)
                )
                result = {"artifact_id": manifest.artifact_id, **manifest.parameters.value()}
            self._sources(request["uploads"])
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
