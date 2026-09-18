"""Paged member quality annotations; no raw evidence mutation or inline projection."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from spireagent.hub.collections import CollectionAccess
from spireagent.hub.console_auth import ConsolePrincipal
from spireagent.hub.curation import CurationLedger
from spireagent.hub.curation_access import guarded_runs
from spireagent.json_boundary import BoundaryError, digest, object_fields

if TYPE_CHECKING:
    from spireagent.hub.uploads import UploadService


class QualityAnnotations:
    def __init__(self, service: UploadService) -> None:
        self.service = service
        self.collections = CollectionAccess(service)
        self.ledger = CurationLedger(service.operations)

    def read(
        self, principal: ConsolePrincipal, upload: str, limit: int, offset: int
    ) -> dict[str, Any]:
        self.collections.require_member(principal)
        source = self.collections.collection(upload)
        guarded_runs(self.service.operations, self.service.store, source)
        if not self.ledger.exact_source_ready(source.artifact_id):
            return {"items": [], "total": 0, "availability": "index_pending", "next_offset": None}
        with self.service.operations.transaction() as db:
            joined = (
                " FROM curation_occurrences o JOIN curation_source_decisions s "
                "ON s.occurrence=o.id "
                "JOIN curation_occurrence_details d ON d.id=o.id WHERE s.source=?"
            )
            total = db.execute("SELECT count(*)" + joined, (source.artifact_id,)).fetchone()[0]
            rows = db.execute(
                "SELECT o.*,d.sequence,d.family,d.surface,d.action"
                + joined
                + " ORDER BY o.run,d.sequence,o.id LIMIT ? OFFSET ?",
                (source.artifact_id, limit, offset),
            ).fetchall()
        items = [
            {
                **dict(row),
                "action": json.loads(row["action"]),
                "annotations": self.ledger.history(row["id"]),
            }
            for row in rows
        ]
        return {
            "items": items,
            "total": total,
            "availability": "available",
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if offset + limit < total else None,
        }

    def write(self, principal: ConsolePrincipal, body: object) -> dict[str, Any]:
        self.collections.require_member(principal)
        obj = object_fields(body, {"upload_id", "occurrence", "action", "reason"}, "quality")
        key = digest(obj["occurrence"], "quality.occurrence")
        source = self.collections.collection(obj["upload_id"])
        guarded_runs(self.service.operations, self.service.store, source)
        if not self.ledger.exact_source_ready(source.artifact_id):
            raise BoundaryError("quality", "source_index_pending")
        with self.service.operations.transaction() as db:
            found = db.execute(
                "SELECT 1 FROM curation_occurrences o "
                "JOIN curation_source_decisions s ON s.occurrence=o.id "
                "WHERE o.id=? AND s.source=?",
                (key, source.artifact_id),
            ).fetchone()
        if found is None:
            raise BoundaryError("quality", "occurrence_not_found")
        sequence = self.ledger.annotate(key, principal.subject, obj["action"], obj["reason"])
        return {
            "sequence": sequence,
            "occurrence": key,
            "action": obj["action"],
            "effect": "new_selections_only",
            "raw_evidence": "unchanged",
        }
