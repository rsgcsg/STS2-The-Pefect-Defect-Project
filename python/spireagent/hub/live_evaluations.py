"""Member-authorized Agent reports in the existing immutable ArtifactStore.

This route is separate from Human ingest. Operations records an audit event;
there is no second upload ledger and no client-provided performance verdict.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Any

from spireagent.artifact_contracts import Manifest
from spireagent.hub.console_auth import ConsolePrincipal
from spireagent.hub.membership import MembershipService
from spireagent.hub.uploads import UploadService
from spireagent.json_boundary import BoundaryError, FrozenObject, json_bytes, object_fields, text
from spireagent.live_evaluation import (
    FILES,
    SHARE_SCHEMA,
    decode_evidence,
    expected_identity,
    verified_report,
)


class LiveEvaluations:
    def __init__(self, service: UploadService, membership: MembershipService) -> None:
        self.service, self.membership = service, membership
        if service.operations.path.resolve() != membership.ops.path.resolve():
            raise BoundaryError("evaluation", "identity_store_mismatch")

    def _authorize(self, db: Any, principal: ConsolePrincipal, device_id: str) -> ConsolePrincipal:
        current = self.membership.authorize(db, principal)
        device = db.execute(
            "SELECT owner_subject,active FROM devices WHERE id=?", (device_id,)
        ).fetchone()
        if device is None or not device["active"] or device["owner_subject"] != current.subject:
            raise BoundaryError("evaluation", "owned_active_device_required")
        return current

    def publish(self, principal: ConsolePrincipal, body: object) -> dict[str, Any]:
        value = object_fields(
            body,
            {"schema", "device_id", "share_authorized", "expected", "files"},
            "evaluation.share",
        )
        if value["schema"] != SHARE_SCHEMA or value["share_authorized"] is not True:
            raise BoundaryError("evaluation", "explicit_evaluation_sharing_required")
        device_id = text(value["device_id"], "evaluation.device_id", maximum=128)
        expected = expected_identity(value["expected"])
        with self.service.operations.transaction() as db:
            self._authorize(db, principal, device_id)
        with tempfile.TemporaryDirectory(prefix="spireagent-evaluation-") as temporary:
            directory = Path(temporary)
            decode_evidence(value["files"], directory)
            report = verified_report(directory, expected)
            report.update(device_id=device_id, submitted_by=principal.subject)
            payloads = []
            for name in FILES:
                with (directory / name).open("rb") as source:
                    payloads.append(self.service.store.put_payload("agent/" + name, source))
            payloads.append(
                self.service.store.put_payload(
                    "report", io.BytesIO(json_bytes(report)), "application/json"
                )
            )
            artifact = Manifest(
                "live_evaluation",
                self.service.producer,
                payloads=tuple(payloads),
                parameters=FrozenObject.of(report),
            )
            with self.service.operations.transaction() as db:
                current = self._authorize(db, principal, device_id)
                identity = self.service.store.publish(artifact)
                previous = db.execute(
                    "SELECT 1 FROM events WHERE operation='live_evaluation_shared' AND subject=?",
                    (identity,),
                ).fetchone()
                if previous is None:
                    self.service.operations._event(
                        db,
                        current.subject,
                        "live_evaluation_shared",
                        identity,
                        {
                            "device_id": device_id,
                            "evidence_content_id": report["evidence_content_id"],
                        },
                    )
            self.service.console_index.artifact(artifact)
        return {
            "schema": "stpd/shared-evaluation-receipt-v1",
            "artifact_id": identity,
            "evidence_content_id": report["evidence_content_id"],
            "status": "verified",
            "report": report,
        }
