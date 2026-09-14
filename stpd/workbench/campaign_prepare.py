"""Prepare an explicitly consented campaign without changing or starting the game or delivery."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from sts2_platform_evidence.collection_tool import CollectionTool
from sts2_platform_evidence.delivery_config import DeliveryConfig

from ..collection_activity import TEMPLATE_SCHEMA, validate_enrollment
from ..json_boundary import BoundaryError, digest, json_bytes
from .developer import ProjectConfig, atomic_json
from .identity import LocalIdentity, private_read


def _directory(path: Path) -> None:
    if path.is_symlink():
        raise BoundaryError("campaign", "non_symlink_directory_required")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir():
        raise BoundaryError("campaign", "directory_required")


def prepare_campaign(
    config: ProjectConfig, enrollment: object, tool_directory: Path
) -> dict[str, Any]:
    """Caller obtains enrollment through the authenticated Hub; no browser paths are imported.

    This produces inactive configuration only. The application must keep native-root binding,
    exact loaded identity and owning delivery doctor as separate checks before activation.
    """
    selected = validate_enrollment(enrollment)
    device = LocalIdentity(config).device()
    if device.get("device_id") != selected["device_id"] or not device.get("token"):
        raise BoundaryError("campaign", "matching_local_device_required")
    template = selected["template"]
    legacy = template["schema"] == TEMPLATE_SCHEMA
    if legacy and any(
        config.combination.get(key) != template[key]
        for key in ("platform_source_revision", "evidence_source_revision")
    ):
        raise BoundaryError("campaign", "approved_combination_required")
    if not config.hub_url.startswith("https://"):
        raise BoundaryError("campaign", "https_hub_required")
    # A newer registered release is a default for new configuration. It cannot
    # silently replace an existing immutable outbox's tool identity or consent.
    existing = read_preparation(config, selected)
    if existing is not None:
        return existing
    if not tool_directory.is_absolute() or tool_directory.is_symlink():
        raise BoundaryError("campaign", "absolute_non_symlink_tool_required")
    if legacy:
        release_id = template["tool_release_id"]
    else:
        from .collection_tool_registration import current_collection_tool

        registered, release_id = current_collection_tool(config)
        if registered != tool_directory.resolve():
            raise BoundaryError("campaign", "registered_collection_tool_required")
    owner = CollectionTool(tool_directory, release_id)
    _directory(config.state_dir)
    campaigns = config.state_dir / "campaigns"
    _directory(campaigns)
    directory = campaigns / selected["enrollment_id"]
    delivery_path = directory / "delivery.json"
    record_path = directory / "preparation.json"
    expected = {
        "schema": "stpd/local-campaign-preparation-v1",
        "enrollment": selected,
        "enrollment_sha256": hashlib.sha256(json_bytes(selected)).hexdigest(),
        "hub_url": config.hub_url,
        "tool_directory": str(tool_directory.resolve()),
        "delivery_config": str(delivery_path),
        "recordings_root": str(directory / "recordings"),
        "outbox_root": str(directory / "outbox"),
        "status": "native_binding_required",
        "native_binding_verified": False,
        "delivery_started": False,
        "required_native_identity": (
            {"game": template["game"], "mod": template["mod"]} if legacy else None
        ),
    }
    if not legacy:
        expected["tool_release_id"] = release_id
    if directory.exists() or directory.is_symlink():
        if directory.is_symlink() or private_read(record_path) != expected:
            raise BoundaryError("campaign", "preparation_exists_or_incomplete")
        observed = DeliveryConfig.load(delivery_path)
        if observed != _delivery(expected, template, selected):
            raise BoundaryError("campaign", "prepared_config_changed")
        return expected
    os.mkdir(directory, mode=0o700)
    # Each root is created exclusively. No discovery, copy or enrollment of older recordings.
    os.mkdir(directory / "recordings", mode=0o700)
    os.mkdir(directory / "outbox", mode=0o700)
    cfg = _delivery(expected, template, selected)
    atomic_json(
        delivery_path,
        {
            "schema": "sts2.evidence/delivery-config-1",
            "recordings_root": str(cfg.recordings_root),
            "outbox_root": str(cfg.outbox_root),
            "tool_directory": str(cfg.tool_directory),
            "tool_release_id": cfg.tool_release_id,
            "worker_id": cfg.worker_id,
            "campaign_id": cfg.campaign_id,
            "human_origin_attested": cfg.human_origin_attested,
            "hub_url": cfg.hub_url,
            "allowed_upload_hosts": cfg.allowed_upload_hosts,
        },
    )
    # The Platform codec, not this preparation layer, owns actual delivery config admission.
    if DeliveryConfig.load(delivery_path) != cfg or owner.verify() != owner.manifest:
        raise BoundaryError("campaign", "prepared_owner_identity_changed")
    atomic_json(record_path, expected)
    return expected


def _delivery(
    prepared: dict[str, Any], template: dict[str, Any], selected: dict[str, Any]
) -> DeliveryConfig:
    return DeliveryConfig(
        recordings_root=Path(prepared["recordings_root"]),
        outbox_root=Path(prepared["outbox_root"]),
        tool_directory=Path(prepared["tool_directory"]),
        tool_release_id=digest(
            template["tool_release_id"]
            if template["schema"] == TEMPLATE_SCHEMA
            else prepared.get("tool_release_id"),
            "campaign.tool_release_id",
        ),
        worker_id=selected["device_id"],
        campaign_id=selected["campaign_id"],
        human_origin_attested=selected["consent"]["human_origin_attested"],
        hub_url=prepared["hub_url"],
        allowed_upload_hosts=template["allowed_upload_hosts"],
    )


def read_preparation(config: ProjectConfig, enrollment: object) -> dict[str, Any] | None:
    """Read durable configuration, never promote its historical flags to live readiness."""
    selected = validate_enrollment(enrollment)
    if selected["template"]["schema"] == TEMPLATE_SCHEMA and any(
        config.combination.get(key) != selected["template"][key]
        for key in ("platform_source_revision", "evidence_source_revision")
    ):
        raise BoundaryError("campaign", "approved_combination_required")
    root = config.state_dir / "campaigns"
    directory = root / selected["enrollment_id"]
    if root.is_symlink() or directory.is_symlink():
        raise BoundaryError("campaign", "non_symlink_directory_required")
    if not directory.exists():
        return None
    value = private_read(directory / "preparation.json")
    if (
        value.get("schema") != "stpd/local-campaign-preparation-v1"
        or value.get("enrollment") != selected
        or value.get("enrollment_sha256") != hashlib.sha256(json_bytes(selected)).hexdigest()
        or value.get("hub_url") != config.hub_url
        or value.get("recordings_root") != str(directory / "recordings")
        or value.get("outbox_root") != str(directory / "outbox")
        or value.get("delivery_config") != str(directory / "delivery.json")
        or not isinstance(value.get("tool_directory"), str)
        or not Path(value["tool_directory"]).is_absolute()
        or value.get("required_native_identity")
        != (
            {"game": selected["template"]["game"], "mod": selected["template"]["mod"]}
            if selected["template"]["schema"] == TEMPLATE_SCHEMA
            else None
        )
    ):
        raise BoundaryError("campaign", "preparation_exists_or_incomplete")
    for path in (directory / "recordings", directory / "outbox", directory / "delivery.json"):
        if path.is_symlink() or not path.exists():
            raise BoundaryError("campaign", "prepared_config_changed")
    delivery = DeliveryConfig.load(directory / "delivery.json")
    if delivery != _delivery(value, selected["template"], selected):
        raise BoundaryError("campaign", "prepared_config_changed")
    if LocalIdentity(config).device().get("device_id") != delivery.worker_id:
        raise BoundaryError("campaign", "matching_local_device_required")
    CollectionTool(delivery.tool_directory, delivery.tool_release_id)
    return value
