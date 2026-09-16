"""Bounded immutable download inventories, not ZIP jobs or scientific admission.

Every HTTP request authenticates again. Inventories contain exact selected own files,
never storage keys, presigned URLs, credentials, local paths or recursive parent bytes.
Accepted project collections need no second grant; explicit withdrawal still applies.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterator
from contextlib import closing
from typing import Any

from spireagent.artifact_contracts import Manifest
from spireagent.hub.access import POLICY_VERSION
from spireagent.hub.collections import CollectionAccess
from spireagent.hub.console_auth import ConsolePrincipal
from spireagent.hub.console_index import timestamp
from spireagent.hub.uploads import UploadService
from spireagent.json_boundary import BoundaryError, digest, json_bytes, object_fields

SCHEMA = "stpd/project-export-v1"
REQUEST_SCHEMA = "stpd/project-export-request-v1"
MAX_SELECTIONS = 100
MAX_FILES = 1000
MAX_BYTES = 20 * 1024**3
MAX_INVENTORY_BYTES = 2 * 1024**2


class ExportService:
    def __init__(self, service: UploadService) -> None:
        self.service = service
        self.collections = CollectionAccess(service)
        with service.operations.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS project_exports("
                "id TEXT PRIMARY KEY,inventory TEXT NOT NULL,created_at REAL NOT NULL)"
            )

    @staticmethod
    def _file(manifest: Manifest, role: str | None, upload_id: str | None = None) -> dict[str, Any]:
        kind = "manifest" if role is None else "payload"
        identity = hashlib.sha256(json_bytes([manifest.artifact_id, kind, role])).hexdigest()
        if role is None:
            raw = manifest.to_bytes()
            size, sha, media = len(raw), hashlib.sha256(raw).hexdigest(), "application/json"
        else:
            item = manifest.payload(role)
            size, sha, media = item.size, item.sha256, item.media_type
        return {
            "file_id": identity,
            "artifact_id": manifest.artifact_id,
            "type": kind,
            "role": role,
            "sha256": sha,
            "size": size,
            "media_type": media,
            "filename": identity + (".json" if role is None else ".bin"),
            "upload_id": upload_id,
        }

    def create(self, principal: ConsolePrincipal, request: object) -> dict[str, Any]:
        self.collections.require_member(principal)
        value = object_fields(request, {"schema", "collections", "artifacts"}, "export")
        collections, artifacts = value["collections"], value["artifacts"]
        if (
            value["schema"] != REQUEST_SCHEMA
            or not isinstance(collections, list)
            or not isinstance(artifacts, list)
            or not 1 <= len(collections) + len(artifacts) <= MAX_SELECTIONS
        ):
            raise BoundaryError("export", "invalid_selection")
        collections = sorted(self.collections.upload_id(item) for item in collections)
        if len(set(collections)) != len(collections):
            raise BoundaryError("export", "duplicate_selection")
        selected: list[dict[str, Any]] = []
        files: list[dict[str, Any]] = []
        seen: set[str] = set()
        for upload_id in collections:
            manifest = self.collections.collection(upload_id)
            # The original archive contains its own bundle manifest. Transport intent,
            # receiver receipt and arbitrary received-artifact metadata are not exported.
            files.append(self._file(manifest, "archive", upload_id))
        for raw in artifacts:
            item = object_fields(raw, {"artifact_id", "roles"}, "export.artifact")
            manifest = self.collections.artifact(item["artifact_id"])
            roles = item["roles"]
            if (
                not isinstance(roles, list)
                or len(roles) > MAX_FILES
                or any(not isinstance(role, str) for role in roles)
                or len(set(roles)) != len(roles)
                or manifest.artifact_id in seen
            ):
                raise BoundaryError("export", "invalid_payload_roles")
            seen.add(manifest.artifact_id)
            selected.append({"artifact_id": manifest.artifact_id, "roles": sorted(roles)})
            files.append(self._file(manifest, None))
            files.extend(self._file(manifest, role) for role in sorted(roles))
        files.sort(key=lambda item: item["file_id"])
        if len({item["file_id"] for item in files}) != len(files):
            raise BoundaryError("export", "duplicate_file_selection")
        size = sum(item["size"] for item in files)
        if len(files) > MAX_FILES or size > MAX_BYTES:
            raise BoundaryError("export", "export_size_limit")
        inventory = {
            "schema": SCHEMA,
            "policy": POLICY_VERSION,
            "selection": {
                "collections": collections,
                "artifacts": sorted(selected, key=lambda item: item["artifact_id"]),
            },
            "files": files,
            "total_bytes": size,
            "files_count": len(files),
            "scope": "selected_own_payloads",
            "non_claims": ["complete lineage cache", "research admission", "training permission"],
        }
        raw_bytes = json_bytes(inventory)
        if len(raw_bytes) > MAX_INVENTORY_BYTES:
            raise BoundaryError("export", "inventory_size_limit")
        identity = hashlib.sha256(raw_bytes).hexdigest()
        with self.service.operations.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO project_exports VALUES(?,?,?)",
                (identity, raw_bytes.decode(), time.time()),
            )
            self.service.operations._event(
                db,
                principal.subject,
                "project_export_selected",
                identity,
                {"files": len(files), "bytes": size},
            )
        return self.read(principal, identity)

    def _inventory(self, principal: ConsolePrincipal, export_id: str) -> dict[str, Any]:
        self.collections.require_member(principal)
        identity = digest(export_id, "export.id")
        with closing(self.service.console_index.read()) as db:
            row = db.execute(
                "SELECT inventory,created_at FROM project_exports WHERE id=?",
                (identity,),
            ).fetchone()
        if row is None:
            raise BoundaryError("export", "export_not_found")
        raw = row[0].encode()
        if len(raw) > MAX_INVENTORY_BYTES or hashlib.sha256(raw).hexdigest() != identity:
            raise BoundaryError("export", "inventory_integrity_failure")
        value = json.loads(raw)
        if value["schema"] != SCHEMA or value["policy"] not in {
            "stpd/project-sharing-v1", POLICY_VERSION,
        }:
            raise BoundaryError("export", "export_policy_changed")
        return {**value, "export_id": identity, "created_at": timestamp(row[1])}

    def read(self, principal: ConsolePrincipal, export_id: str) -> dict[str, Any]:
        value = self._inventory(principal, export_id)
        # Old inventories retain their hash and policy; current access is still rechecked.
        for upload_id in value["selection"]["collections"]:
            self.collections.collection(upload_id)
        for item in value["selection"]["artifacts"]:
            self.collections.artifact(item["artifact_id"])
        return value

    def payload(
        self,
        principal: ConsolePrincipal,
        export_id: str,
        file_id: str,
    ) -> tuple[dict[str, Any], Iterator[bytes]]:
        value = self._inventory(principal, export_id)
        identity = digest(file_id, "export.file_id")
        item = next((item for item in value["files"] if item["file_id"] == identity), None)
        if item is None:
            raise BoundaryError("export", "file_not_selected")
        # Recheck the requested file, not every other source in a bulk selection on
        # every streamed download. Inventory retrieval separately checks the full set.
        manifest = (
            self.collections.collection(item["upload_id"])
            if item["upload_id"]
            else self.collections.artifact(item["artifact_id"])
        )
        observed = self._file(manifest, item["role"], item["upload_id"])
        if item != observed:
            raise BoundaryError("export", "file_identity_mismatch")
        if item["type"] == "manifest":
            return item, iter((manifest.to_bytes(),))
        # The ArtifactStore verifies every bounded chunk and the final size/hash. The
        # client also verifies the inventory hash and whole file before publishing it.
        return item, self.service.store.read_payload(manifest.payload(item["role"]))
