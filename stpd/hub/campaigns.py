"""Immutable collection activities and explicit member declarations, never native evidence."""

from __future__ import annotations

import builtins
import hashlib
import secrets
import sqlite3
import time
from typing import Any, Protocol

from ..collection_activity import (
    COLLECTION_SETTINGS_SCHEMA,
    ENROLLMENT_SCHEMA,
    validate_consent,
    validate_template,
)
from ..json_boundary import BoundaryError, decode_json, digest, json_bytes, object_fields, text
from .console_auth import ConsolePrincipal
from .database import Operations


class MemberAuthority(Protocol):
    def authorize(
        self, db: sqlite3.Connection, principal: ConsolePrincipal
    ) -> ConsolePrincipal: ...
    def admin(self, db: sqlite3.Connection, principal: ConsolePrincipal) -> ConsolePrincipal: ...


def create_campaign_tables(db: sqlite3.Connection) -> None:
    """Called inside the owning operations-schema migration transaction."""
    db.execute(
        "CREATE TABLE IF NOT EXISTS collection_activities("
        "id TEXT PRIMARY KEY, activity_id TEXT NOT NULL, version INTEGER NOT NULL, "
        "template TEXT NOT NULL, created_at REAL NOT NULL, created_by TEXT NOT NULL, "
        "UNIQUE(activity_id,version))"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS collection_enrollments("
        "id TEXT PRIMARY KEY, template_id TEXT NOT NULL, device_id TEXT NOT NULL, "
        "subject TEXT NOT NULL, consent TEXT NOT NULL, created_at REAL NOT NULL, "
        "UNIQUE(template_id,device_id,subject))"
    )


class Campaigns:
    def __init__(self, ops: Operations, members: MemberAuthority) -> None:
        self.ops, self.members = ops, members

    @staticmethod
    def _template(row: sqlite3.Row) -> dict[str, Any]:
        return {"template_id": row["id"], "template": decode_json(row["template"])}

    def create(self, principal: ConsolePrincipal, value: object) -> dict[str, Any]:
        template = validate_template(value)
        encoded = json_bytes(template)
        identity = hashlib.sha256(encoded).hexdigest()
        with self.ops.transaction() as db:
            current = self.members.admin(db, principal)
            old = db.execute(
                "SELECT * FROM collection_activities WHERE activity_id=? AND version=?",
                (template["activity_id"], template["version"]),
            ).fetchone()
            if old is not None:
                if old["id"] != identity:
                    raise BoundaryError("campaign", "immutable_template_conflict")
                return self._template(old)
            if db.execute("SELECT COUNT(*) FROM collection_activities").fetchone()[0] >= 256:
                raise BoundaryError("campaign", "activity_capacity_reached")
            latest = db.execute(
                "SELECT COALESCE(MAX(version),0) FROM collection_activities WHERE activity_id=?",
                (template["activity_id"],),
            ).fetchone()[0]
            if template["version"] != latest + 1:
                raise BoundaryError("campaign", "next_template_version_required")
            db.execute(
                "INSERT INTO collection_activities VALUES(?,?,?,?,?,?)",
                (
                    identity,
                    template["activity_id"],
                    template["version"],
                    encoded.decode(),
                    time.time(),
                    current.subject,
                ),
            )
            self.ops._event(db, current.subject, "collection_activity_created", identity, {})
        return {"template_id": identity, "template": template}

    def list(
        self, principal: ConsolePrincipal, *, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise BoundaryError("campaign", "invalid_pagination")
        with self.ops.transaction() as db:
            self.members.authorize(db, principal)
            total = db.execute("SELECT COUNT(*) FROM collection_activities").fetchone()[0]
            rows = db.execute(
                "SELECT * FROM collection_activities ORDER BY created_at DESC,id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return {
            "templates": [self._template(row) for row in rows],
            "total": total,
            "next_offset": offset + limit if offset + limit < total else None,
        }

    def default(self, principal: ConsolePrincipal) -> dict[str, Any] | None:
        with self.ops.transaction() as db:
            self.members.authorize(db, principal)
            row = db.execute(
                "SELECT a.* FROM settings s JOIN collection_activities a ON a.id=s.value "
                "WHERE s.key='default_collection_template'"
            ).fetchone()
            return None if row is None else self._template(row)

    def set_default(self, principal: ConsolePrincipal, template_id: str) -> dict[str, Any]:
        digest(template_id, "collection.default_template")
        with self.ops.transaction() as db:
            current = self.members.admin(db, principal)
            row = db.execute(
                "SELECT * FROM collection_activities WHERE id=?", (template_id,)
            ).fetchone()
            if row is None:
                raise BoundaryError("campaign", "activity_not_found")
            previous = db.execute(
                "SELECT value FROM settings WHERE key='default_collection_template'"
            ).fetchone()
            if previous is None or previous[0] != template_id:
                db.execute(
                    "INSERT INTO settings VALUES('default_collection_template',?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (template_id,),
                )
                self.ops._event(db, current.subject, "default_collection_changed", template_id, {})
            return self._template(row)

    def publish_default(
        self, principal: ConsolePrincipal, value: object, upload_hosts: builtins.list[str]
    ) -> dict[str, Any]:
        """A small admin form chooses consent settings, not another software release ledger.

        The existing immutable template owner still publishes every version. A failed
        recommendation leaves a harmless published template; retry is idempotent.
        """
        fields = object_fields(value, {"name", "description", "consent_text"}, "collection.default")
        with self.ops.transaction() as db:
            self.members.admin(db, principal)
            row = db.execute(
                "SELECT * FROM collection_activities WHERE activity_id='project-default' "
                "ORDER BY version DESC LIMIT 1"
            ).fetchone()
        latest = None if row is None else decode_json(row["template"])
        version = 1 if latest is None else latest["version"]
        template = validate_template(
            {
                "schema": COLLECTION_SETTINGS_SCHEMA,
                "activity_id": "project-default",
                "version": version,
                **fields,
                "allowed_upload_hosts": upload_hosts,
                "sharing_scope": "project_members",
            }
        )
        if latest is not None and template != latest:
            template["version"] += 1
        published = self.create(principal, template)
        return self.set_default(principal, published["template_id"])

    def enroll(
        self, principal: ConsolePrincipal, template_id: str, device_id: str, consent: object
    ) -> dict[str, Any]:
        digest(template_id, "campaign.template_id")
        text(device_id, "campaign.device_id", maximum=128)
        declaration = validate_consent(consent)
        with self.ops.transaction() as db:
            current = self.members.authorize(db, principal)
            device = db.execute(
                "SELECT owner_subject,active FROM devices WHERE id=?", (device_id,)
            ).fetchone()
            if device is None or not device["active"] or device["owner_subject"] != current.subject:
                raise BoundaryError("campaign", "owned_active_device_required")
            row = db.execute(
                "SELECT * FROM collection_activities WHERE id=?", (template_id,)
            ).fetchone()
            if row is None:
                raise BoundaryError("campaign", "activity_not_found")
            enrollment = db.execute(
                "SELECT * FROM collection_enrollments WHERE template_id=? "
                "AND device_id=? AND subject=?",
                (template_id, device_id, current.subject),
            ).fetchone()
            if enrollment is None:
                enrollment_id = secrets.token_hex(16)
                db.execute(
                    "INSERT INTO collection_enrollments VALUES(?,?,?,?,?,?)",
                    (
                        enrollment_id,
                        template_id,
                        device_id,
                        current.subject,
                        json_bytes(declaration).decode(),
                        time.time(),
                    ),
                )
                self.ops._event(
                    db,
                    current.subject,
                    "collection_consent_declared",
                    enrollment_id,
                    {
                        "template_id": template_id,
                        "device_id": device_id,
                        "declaration": declaration,
                        "human_origin_verified": False,
                    },
                )
                enrollment = db.execute(
                    "SELECT * FROM collection_enrollments WHERE id=?", (enrollment_id,)
                ).fetchone()
            assert enrollment is not None
            return {
                "schema": ENROLLMENT_SCHEMA,
                "enrollment_id": enrollment["id"],
                "device_id": device_id,
                **self._template(row),
                "consent": decode_json(enrollment["consent"]),
                "declared_at": enrollment["created_at"],
                "campaign_id": "campaign-" + enrollment["id"],
                "human_origin_verified": False,
            }
