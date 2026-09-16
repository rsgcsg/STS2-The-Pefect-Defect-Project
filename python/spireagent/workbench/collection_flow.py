"""Small collection application flow over existing consent, native and delivery owners.

Only the upload preference is new durable state. Preparation, native readiness,
consent and upload outcomes are always read from their existing authorities.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from spireagent.json_boundary import BoundaryError, digest, object_fields
from spireagent.workbench.collection_setup import CollectionSetup
from spireagent.workbench.developer import ProjectConfig, atomic_json
from spireagent.workbench.identity import LocalIdentity, private_read
from stpd.collection_activity import CONSENT_FIELDS

PREFERENCE_FILE = "collection-upload-preference.json"
PREFERENCE_SCHEMA = "stpd/collection-upload-preference-v1"
FLOW_SCHEMA = "stpd/local-collection-flow-v1"


def upload_preference(config: ProjectConfig) -> dict[str, Any]:
    """An absent preference preserves an already configured legacy uploader.

    A changed device/Hub or malformed preference fails closed; restarting the
    workbench must never turn a persistent pause into an implicit resume.
    """
    path = config.state_dir / PREFERENCE_FILE
    value = private_read(path)
    if not value and not path.exists():
        return {"enabled": config.delivery_config is not None, "explicit": False}
    object_fields(value, {"schema", "hub_url", "device_id", "enabled"}, "collection.upload")
    if (
        value["schema"] != PREFERENCE_SCHEMA
        or type(value["enabled"]) is not bool
        or value["hub_url"] != config.hub_url
        or value["device_id"] != LocalIdentity(config).device().get("device_id")
    ):
        raise BoundaryError("collection", "upload_preference_mismatch")
    return {"enabled": value["enabled"], "explicit": True}


def save_upload_preference(config: ProjectConfig, enabled: bool) -> dict[str, Any]:
    if type(enabled) is not bool:
        raise BoundaryError("collection", "upload_boolean_required")
    # Never replace an incompatible preference or silently transfer its ownership.
    upload_preference(config)
    device = LocalIdentity(config).device().get("device_id")
    if not device:
        raise BoundaryError("collection", "connected_device_required")
    atomic_json(
        config.state_dir / PREFERENCE_FILE,
        {
            "schema": PREFERENCE_SCHEMA,
            "hub_url": config.hub_url,
            "device_id": device,
            "enabled": enabled,
        },
    )
    return upload_preference(config)


class CollectionFlow:
    def __init__(
        self,
        setup: CollectionSetup,
        *,
        delivery_process: Callable[[], str],
        activate: Callable[[str], dict[str, Any]],
        stop_delivery: Callable[[], None],
    ) -> None:
        self.setup = setup
        self.members = setup.members
        self.delivery_process = delivery_process
        self.activate = activate
        self.stop_delivery = stop_delivery
        self.lock = threading.RLock()

    @property
    def config(self) -> ProjectConfig:
        return self.setup.config

    def _selected(self, status: dict[str, Any]) -> dict[str, Any] | None:
        items = status["items"]
        active = self.config.delivery_config
        if active is not None:
            # Keep an attached collection selected even when its owner check fails.
            # Otherwise a blocked old queue could appear to be a fresh setup.
            attached = []
            for item in items:
                root = self.config.state_dir / "campaigns" / item["enrollment_id"]
                if active == root / "delivery.json" or (
                    active.name == "delivery.json"
                    and active.parent.parent == root / "generations"
                ):
                    attached.append(item)
            if len(attached) != 1:
                raise BoundaryError("collection", "attached_collection_unavailable")
            return dict(attached[0])
        attached = [item for item in items if item["preparation"].get("delivery_selected")]
        if len(attached) > 1:
            raise BoundaryError("collection", "ambiguous_attached_collection")
        if attached:
            return dict(attached[0])
        default = status["settings"].get("default") or {}
        return next(
            (dict(item) for item in items if item["template_id"] == default.get("template_id")),
            None,
        )

    def status(self) -> dict[str, Any]:
        preference = upload_preference(self.config)
        result: dict[str, Any] = {
            "schema": FLOW_SCHEMA,
            "upload": {**preference, "process": self.delivery_process()},
            "stage": "unavailable",
            "next_action": "reconnect",
            "consent_required": None,
            "enrollment": None,
            "default": None,
        }
        try:
            current = self.setup.status(self.delivery_process())
            selected = self._selected(current)
            result.update(
                default=current["settings"].get("default"),
                enrollment=selected,
                consent_required=selected is None,
            )
            if selected is None:
                configured = result["default"] is not None
                result.update(
                    stage="consent_required" if configured else "project_setup_required",
                    next_action="consent" if configured else "contact_admin",
                )
            else:
                prepared = selected["preparation"]
                result.update(stage=prepared["status"], next_action=prepared["next_action"])
                if (
                    prepared.get("native_binding", {}).get("bound") is True
                    and not preference["enabled"]
                ):
                    result.update(stage="upload_paused", next_action="resume_upload")
                if prepared.get("error"):
                    result["error"] = prepared["error"]
        except (BoundaryError, OSError, ValueError) as error:
            result["error"] = (
                error.code if isinstance(error, BoundaryError) else "collection_status_unavailable"
            )
        if not preference["enabled"] and result["upload"]["process"] == "running":
            result.update(
                stage="upload_stop_failed",
                next_action="stop_workbench",
                error="delivery_still_running",
            )
        return result

    def consent(self, value: object) -> dict[str, Any]:
        """One explicit button accepts all displayed declarations, not Human proof."""
        body = object_fields(value, {"template_id", "accepted"}, "collection.consent")
        template_id = digest(body["template_id"], "collection.template_id")
        if body["accepted"] is not True:
            raise BoundaryError("collection", "explicit_collection_consent_required")
        with self.lock:
            settings = self.members.request("collection-settings")
            if (settings.get("default") or {}).get("template_id") != template_id:
                raise BoundaryError("collection", "collection_notice_changed")
            device = self.members.account.device().get("device_id")
            if not device:
                raise BoundaryError("collection", "connected_device_required")
            selected = self.members.request(
                f"campaigns/{template_id}/enroll",
                {"device_id": device, "consent": {field: True for field in CONSENT_FIELDS}},
            )
            # An idempotent consent replay must not undo a later deliberate pause.
            if not upload_preference(self.config)["explicit"]:
                save_upload_preference(self.config, True)
            return {"schema": FLOW_SCHEMA, "enrollment": selected, "human_origin_verified": False}

    def prepare(self, value: object) -> dict[str, Any]:
        """Advance only safe existing steps; native owner determines Human stop gates.

        Repeating this operation reads persisted preparation and does not replace
        tools/queues. It never launches a game or resumes an auth-blocked upload.
        """
        if not isinstance(value, dict) or set(value) - {"game_directory"}:
            raise BoundaryError("collection", "invalid_prepare_request")
        directory = value.get("game_directory")
        if directory is not None and (
            not isinstance(directory, str) or not Path(directory).is_absolute()
        ):
            raise BoundaryError("collection", "absolute_game_directory_required")
        with self.lock:
            current = self.setup.status(self.delivery_process())
            selected = self._selected(current)
            if selected is None:
                raise BoundaryError("collection", "collection_consent_required")
            identity = selected["enrollment_id"]
            if not upload_preference(self.config)["explicit"]:
                # Existing explicit enrollment from the old interface is sufficient;
                # the requested prepare operation must not ask the same consent again.
                save_upload_preference(self.config, True)
            self.members.prepare_campaign(identity)
            # Re-fetch from Hub rather than passing browser or stale enrollment facts.
            selected = self.setup.enrollment(identity)
            prepared = self.setup.preparation(selected, self.delivery_process())
            native = prepared.get("native_binding") or {}
            if directory is not None:
                native = self.setup.bind(identity, directory)
            elif (
                native.get("next_action") == "bind_recording_root"
                and native.get("game_running") is False
                and isinstance(native.get("game_directory"), str)
            ):
                native = self.setup.bind(identity, native["game_directory"])
            if (
                native.get("status") == "bound"
                and native.get("bound") is True
                and upload_preference(self.config)["enabled"]
            ):
                self.activate(identity)
            return self.status()

    def set_upload(self, value: object) -> dict[str, Any]:
        body = object_fields(value, {"enabled"}, "collection.upload")
        if type(body["enabled"]) is not bool:
            raise BoundaryError("collection", "upload_boolean_required")
        with self.lock:
            if not body["enabled"]:
                # Persist first. Even a process-stop failure cannot re-enable on restart.
                save_upload_preference(self.config, False)
                self.stop_delivery()
                process = self.delivery_process()
                return {
                    "schema": FLOW_SCHEMA,
                    "upload": {
                        **upload_preference(self.config),
                        "process": process,
                    },
                    "stage": "upload_stop_failed" if process == "running" else "upload_paused",
                    "next_action": "stop_workbench" if process == "running" else "resume_upload",
                    **({"error": "delivery_still_running"} if process == "running" else {}),
                }
            current = self.setup.status(self.delivery_process())
            selected = self._selected(current)
            if selected is None:
                raise BoundaryError("collection", "collection_consent_required")
            # This restores only a still-authorized collection, never a revoked grant.
            self.setup.enrollment(selected["enrollment_id"])
            account = self.members.account
            device = account.request("/v1/identity/device", token=account.device_token())
            if device.get("device_id") != account.device().get("device_id"):
                raise BoundaryError("collection", "matching_local_device_required")
            save_upload_preference(self.config, True)
            return self.prepare({})
