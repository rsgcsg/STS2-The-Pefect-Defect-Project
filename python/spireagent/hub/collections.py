"""One owner for collection sharing and verified source access across Hub features."""

from __future__ import annotations

import hashlib
import json
import re
import time
from contextlib import closing
from typing import TYPE_CHECKING, Any

from spireagent.artifact_contracts import Manifest
from spireagent.hub.access import lineage, project_member, require_artifact_access
from spireagent.hub.console_auth import ConsolePrincipal
from spireagent.json_boundary import BoundaryError, digest, json_bytes
from stpd.collection_activity import ENROLLMENT_SCHEMA, validate_enrollment

if TYPE_CHECKING:
    from spireagent.hub.uploads import UploadService

MAX_SELECTIONS = 100


class CollectionAccess:
    def __init__(self, service: UploadService) -> None:
        self.service = service
        with service.operations.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS collection_sharing("
                "upload_id TEXT PRIMARY KEY,approved INTEGER NOT NULL,"
                "evidence_ref TEXT NOT NULL,changed_at REAL NOT NULL)"
            )

    @staticmethod
    def require_member(principal: ConsolePrincipal) -> None:
        if not project_member(principal):
            raise BoundaryError("hub", "unauthorized")

    @staticmethod
    def upload_id(value: object) -> str:
        if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
            raise BoundaryError("sharing", "invalid_upload_id")
        return value

    def set_collection_access(
        self,
        upload_id: str,
        *,
        approved: bool,
        evidence_ref: str,
        actor: str,
    ) -> None:
        """Owner operation after explicit scoped approval, not a member HTTP mutation.

        The reference identifies the immutable approval/enrollment evidence. Revocation
        affects future requests without rewriting an export, receipt or archive.
        """
        identity = self.upload_id(upload_id)
        digest(evidence_ref, "sharing.evidence_ref")
        if type(approved) is not bool or not actor or len(actor) > 256:
            raise BoundaryError("sharing", "invalid_approval")
        with self.service.operations.transaction() as db:
            if db.execute("SELECT 1 FROM uploads WHERE id=?", (identity,)).fetchone() is None:
                raise BoundaryError("sharing", "collection_not_found")
            previous = db.execute(
                "SELECT approved,evidence_ref FROM collection_sharing WHERE upload_id=?",
                (identity,),
            ).fetchone()
            if previous and tuple(previous) == (int(approved), evidence_ref):
                return
            db.execute(
                "INSERT INTO collection_sharing VALUES(?,?,?,?) "
                "ON CONFLICT(upload_id) DO UPDATE SET approved=excluded.approved,"
                "evidence_ref=excluded.evidence_ref,changed_at=excluded.changed_at",
                (identity, int(approved), evidence_ref, time.time()),
            )
            self.service.operations._event(
                db,
                actor,
                "collection_sharing_changed",
                identity,
                {"approved": approved, "evidence_ref": evidence_ref},
            )

    def associate_verified_collection(self, upload_id: str, bundle: object) -> dict[str, Any]:
        """Receiver-only seam using the fresh successful verifier value, never a UI summary.

        Existing explicit denials/revocations win over automatic enrollment association.
        A declaration is authorization, not proof that actions were Human or scientific.
        """
        from sts2_platform_evidence import HumanSessionBundleV3

        self.upload_id(upload_id)
        if not isinstance(bundle, HumanSessionBundleV3):
            return {"availability": "not_granted", "reason": "current_verified_bundle_required"}
        campaign = re.fullmatch(r"campaign-([a-f0-9]{32})", bundle.campaign_id)
        if campaign is None:
            return {"availability": "not_granted", "reason": "no_enrollment_identity"}
        with self.service.operations.transaction() as db:
            row = db.execute("SELECT * FROM uploads WHERE id=?", (upload_id,)).fetchone()
            if row is None or row["status"] != "verified" or not row["receipt"]:
                raise BoundaryError("sharing", "collection_not_verified")
            receipt = json.loads(row["receipt"])
            if (
                row["content_id"] != bundle.bundle_content_id
                or receipt.get("content_id") != bundle.bundle_content_id
                or receipt.get("status") != "verified"
                or row["device"] != bundle.worker_id
            ):
                raise BoundaryError("sharing", "verified_bundle_identity_mismatch")
            old = db.execute(
                "SELECT approved FROM collection_sharing WHERE upload_id=?", (upload_id,)
            ).fetchone()
            if old is not None:
                return {
                    "availability": "available" if old[0] == 1 else "not_granted",
                    "reason": "existing_owner_decision_preserved",
                }
            enrollment = db.execute(
                "SELECT e.*,a.template,d.owner_subject,d.active,m.status AS membership_status "
                "FROM collection_enrollments e JOIN collection_activities a ON a.id=e.template_id "
                "JOIN devices d ON d.id=e.device_id "
                "LEFT JOIN identity_members m ON m.subject=e.subject "
                "WHERE e.id=?",
                (campaign[1],),
            ).fetchone()
            if enrollment is None:
                return {"availability": "not_granted", "reason": "enrollment_not_found"}
            if (
                enrollment["device_id"] != row["device"]
                or enrollment["owner_subject"] != enrollment["subject"]
                or enrollment["active"] != 1
                or enrollment["membership_status"] != "active"
            ):
                raise BoundaryError("sharing", "active_enrolled_device_owner_required")
            declaration = validate_enrollment(
                {
                    "schema": ENROLLMENT_SCHEMA,
                    "enrollment_id": enrollment["id"],
                    "template_id": enrollment["template_id"],
                    "template": json.loads(enrollment["template"]),
                    "device_id": enrollment["device_id"],
                    "campaign_id": bundle.campaign_id,
                    "consent": json.loads(enrollment["consent"]),
                    "declared_at": enrollment["created_at"],
                    "human_origin_verified": False,
                }
            )
            binding = {
                "schema": "stpd/enrolled-bundle-sharing-v1",
                "enrollment_sha256": hashlib.sha256(json_bytes(declaration)).hexdigest(),
                "enrollment_id": enrollment["id"],
                "template_id": enrollment["template_id"],
                "upload_id": upload_id,
                "device_id": row["device"],
                "bundle_content_id": bundle.bundle_content_id,
                "bundle_checksums_sha256": bundle.bundle_sha256,
                "received_artifact_id": digest(receipt.get("evidence_id"), "sharing.received_id"),
            }
            evidence_ref = hashlib.sha256(json_bytes(binding)).hexdigest()
            db.execute(
                "INSERT INTO collection_sharing VALUES(?,?,?,?)",
                (upload_id, 1, evidence_ref, time.time()),
            )
            self.service.operations._event(
                db,
                enrollment["subject"],
                "collection_sharing_associated",
                upload_id,
                {"evidence_ref": evidence_ref, "binding": binding, "human_origin_verified": False},
            )
        return {"availability": "available", "scope": "project_members"}

    def collection_access(self, upload_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Safe page-sized availability only. Download rechecks actual immutable bytes."""
        if len(upload_ids) > MAX_SELECTIONS:
            raise BoundaryError("sharing", "selection_limit")
        result = {}
        with closing(self.service.console_index.read()) as db:
            for identity in upload_ids:
                self.upload_id(identity)
                row = db.execute(
                    "SELECT u.status,s.approved FROM uploads u LEFT JOIN collection_sharing s "
                    "ON s.upload_id=u.id WHERE u.id=?",
                    (identity,),
                ).fetchone()
                reason = "not_granted"
                if row and row[1] == 1:
                    reason = (
                        "available" if row[0] in {"verified", "quarantined"} else "not_received"
                    )
                result[identity] = {"availability": reason, "scope": "project_members"}
        return result

    def collection(self, upload_id: str) -> Manifest:
        identity = self.upload_id(upload_id)
        with closing(self.service.console_index.read()) as db:
            row = db.execute(
                "SELECT u.*,s.approved FROM uploads u LEFT JOIN collection_sharing s "
                "ON s.upload_id=u.id WHERE u.id=?",
                (identity,),
            ).fetchone()
        if row is None or row["approved"] != 1:
            raise BoundaryError("sharing", "collection_not_shared")
        if row["status"] not in {"verified", "quarantined"} or not row["receipt"]:
            raise BoundaryError("sharing", "collection_not_received")
        receipt = json.loads(row["receipt"])
        manifest = self.service.store.get_manifest(receipt["evidence_id"])
        info = manifest.parameters.value()
        intent = json.loads(row["intent"])
        archive = manifest.payload("archive")
        if (
            manifest.kind != "evidence"
            or info.get("schema") != "stpd/received-bundle-v1"
            or info.get("content_id") != row["content_id"]
            or receipt.get("content_id") != row["content_id"]
            or info.get("disposition") != row["status"]
            or receipt.get("status") != row["status"]
            or archive.sha256 != intent.get("archive_sha256")
            or archive.size != intent.get("archive_bytes")
        ):
            raise BoundaryError("sharing", "collection_identity_mismatch")
        return manifest

    def artifact(self, artifact_id: str) -> Manifest:
        manifest = self.service.store.get_manifest(digest(artifact_id, "export.artifact_id"))
        require_artifact_access(manifest, project_member=True, store=self.service.store)
        # A derived Dataset exposes Human decision bytes. Its received-source ancestors
        # require the same sharing grants as their archives; model weights do not grant
        # permission to pull source data implicitly.
        if manifest.kind == "dataset":
            for ancestor in lineage(self.service.store, manifest):
                info = ancestor.parameters.value()
                if (
                    info.get("schema") == "stpd/source-projection-v1"
                    and info.get("scope") != "engineering"
                    and not any(
                        node.parameters.value().get("schema") == "stpd/received-bundle-v1"
                        for node in lineage(self.service.store, ancestor)
                    )
                ):
                    raise BoundaryError("sharing", "source_sharing_not_established")
                if info.get("schema") != "stpd/received-bundle-v1":
                    continue
                with closing(self.service.console_index.read()) as db:
                    rows = db.execute(
                        "SELECT id FROM uploads WHERE json_extract(receipt,'$.evidence_id')=?",
                        (ancestor.artifact_id,),
                    ).fetchall()
                if not rows:
                    raise BoundaryError("sharing", "source_sharing_not_established")
                # Identical data received by another device is not a grant for this
                # immutable received-source artifact; the exact parent must be shared.
                shared = False
                for row in rows:
                    try:
                        shared = self.collection(row[0]).artifact_id == ancestor.artifact_id
                    except BoundaryError as error:
                        if error.code != "collection_not_shared":
                            raise
                    if shared:
                        break
                if not shared:
                    raise BoundaryError("sharing", "source_sharing_not_established")
        return manifest
