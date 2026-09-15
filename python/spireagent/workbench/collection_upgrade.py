"""Explicit stopped-workbench software rollover under unchanged daily consent.

Preparation retains the active queue. Activation alone changes ProjectConfig after
the old Evidence owner proves completion and the new native owner proves binding.
"""

from __future__ import annotations

import hashlib
from contextlib import AbstractContextManager
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sts2_platform_evidence.collection_tool import CollectionTool
from sts2_platform_evidence.delivery_config import DeliveryConfig

from spireagent.json_boundary import BoundaryError, digest, json_bytes
from spireagent.workbench.campaign_prepare import _create_preparation, _directory, read_preparation
from spireagent.workbench.collection_setup import CollectionSetup
from spireagent.workbench.collection_tool_registration import current_collection_tool
from spireagent.workbench.developer import ProjectConfig, atomic_json, doctor
from spireagent.workbench.identity import LocalIdentity, private_read
from spireagent.workbench.member_client import MemberClient
from stpd.collection_activity import TEMPLATE_SCHEMA

if TYPE_CHECKING:
    from sts2_platform_evidence.delivery_completion import DeliveryCompletion


def completion(config: DeliveryConfig) -> AbstractContextManager[DeliveryCompletion]:
    # The versioned Evidence package, never a local reconstruction of its ledger.
    from sts2_platform_evidence.delivery_completion import completed_delivery

    return completed_delivery(config)


def upgrade(
    config_path: Path,
    enrollment_id: str,
    release_id: str,
    *,
    phase: str,
    game_directory: Path | None = None,
) -> dict[str, Any]:
    from spireagent.workbench.developer_server import instance_lock

    if phase not in {"prepare", "activate"}:
        raise BoundaryError("collection_upgrade", "unknown_phase")
    config = ProjectConfig.load(config_path)
    digest(release_id, "collection_upgrade.tool_release_id")
    with instance_lock(config.state_dir / "instance.lock"):
        if config_path.is_symlink() or ProjectConfig.load(config_path) != config:
            raise BoundaryError("collection_upgrade", "configuration_changed")
        members = MemberClient(LocalIdentity(config))
        try:
            owner = CollectionSetup(members)
            selected = owner.enrollment(enrollment_id)
            if selected["template"]["schema"] == TEMPLATE_SCHEMA:
                raise BoundaryError("collection_upgrade", "daily_v2_consent_required")
            tool_directory, registered = current_collection_tool(config)
            if registered != release_id:
                raise BoundaryError("collection_upgrade", "registered_tool_mismatch")
            previous = read_preparation(config, selected)
            if previous is None or config.delivery_config != Path(previous["delivery_config"]):
                raise BoundaryError("collection_upgrade", "matching_attached_collection_required")
            old = DeliveryConfig.load(config.delivery_config)
            if old.tool_release_id == release_id:
                raise BoundaryError("collection_upgrade", "tool_already_active")
            base = config.state_dir / "campaigns" / enrollment_id
            generations = base / "generations"
            directory = generations / release_id
            for path in (base, generations, directory):
                if path.is_symlink():
                    raise BoundaryError("collection_upgrade", "non_symlink_directory_required")
            target = directory / "delivery.json"
            candidate = replace(config, delivery_config=target)
            config_digest = hashlib.sha256(json_bytes(config.to_dict())).hexdigest()
            receipt_path = directory / "upgrade.json"
            if receipt_path.is_symlink():
                raise BoundaryError("collection_upgrade", "unsafe_proposal_path")
            tool = CollectionTool(tool_directory, release_id)
            changed = False
            try:
                with completion(old) as finished:
                    receipt = {
                        "schema": "stpd/collection-upgrade-v1",
                        "enrollment_id": enrollment_id,
                        "tool_release_id": release_id,
                        "predecessor_project_sha256": config_digest,
                        "predecessor_delivery_config": str(config.delivery_config),
                        "delivery_config": str(target),
                        "completion": finished.to_dict(),
                    }
                    if phase == "prepare":
                        if game_directory is None or not game_directory.is_absolute():
                            raise BoundaryError(
                                "collection_upgrade", "absolute_game_directory_required"
                            )
                        existing_receipt = private_read(receipt_path)
                        if existing_receipt and existing_receipt != receipt:
                            raise BoundaryError("collection_upgrade", "upgrade_receipt_changed")
                        inspection = tool.setup_status(
                            recordings_root=old.recordings_root, game_directory=game_directory
                        )
                        if inspection.get("configured") is not True and existing_receipt == receipt:
                            # Resume the same durable proposal, not an arbitrary current root.
                            inspection = tool.setup_status(
                                recordings_root=directory / "recordings",
                                game_directory=game_directory,
                            )
                        if (
                            inspection.get("status") != "configured"
                            or inspection.get("game_running") is not False
                            or inspection.get("configured") is not True
                        ):
                            raise BoundaryError(
                                "collection_upgrade", "old_root_and_stopped_game_required"
                            )
                        _directory(generations)
                        prepared = _create_preparation(config, selected, tool, directory)
                        for name in ("recordings_root", "outbox_root"):
                            if any(Path(prepared[name]).iterdir()):
                                raise BoundaryError(
                                    "collection_upgrade", "fresh_generation_required"
                                )
                        # Publish intent before binding. If interrupted on either side of the
                        # native write, repeating preparation checks this same proposal/root.
                        # Its presence never proves native binding or activates delivery.
                        if not existing_receipt:
                            atomic_json(receipt_path, receipt)
                        binding = owner._native(prepared, bind=str(game_directory))
                        if binding.get("status") != "configured" or not binding.get("configured"):
                            raise BoundaryError("collection_upgrade", "new_root_binding_failed")
                    elif phase == "activate":
                        if private_read(receipt_path) != receipt:
                            raise BoundaryError(
                                "collection_upgrade", "predecessor_or_proposal_changed"
                            )
                        active_prepared = read_preparation(candidate, selected)
                        if active_prepared is None:
                            raise BoundaryError("collection_upgrade", "preparation_required")
                        for name in ("recordings_root", "outbox_root"):
                            if any(Path(active_prepared[name]).iterdir()):
                                raise BoundaryError(
                                    "collection_upgrade", "fresh_generation_required"
                                )

                        def check_preparations() -> None:
                            if (
                                read_preparation(config, selected) != previous
                                or read_preparation(candidate, selected) != active_prepared
                                or private_read(receipt_path) != receipt
                                or tool.verify() != tool.manifest
                            ):
                                raise BoundaryError("collection_upgrade", "preparation_changed")
                            for name in ("recordings_root", "outbox_root"):
                                if any(Path(active_prepared[name]).iterdir()):
                                    raise BoundaryError(
                                        "collection_upgrade", "fresh_generation_required"
                                    )

                        native = owner._native(active_prepared)
                        if native.get("status") != "bound" or native.get("bound") is not True:
                            raise BoundaryError(
                                "collection_upgrade", "current_native_binding_required"
                            )
                        if doctor(candidate)["status"] != "PASS":
                            raise BoundaryError("collection_upgrade", "delivery_preflight_blocked")
                        if ProjectConfig.load(config_path) != config:
                            raise BoundaryError("collection_upgrade", "configuration_changed")
                        check_preparations()
                        atomic_json(config_path, candidate.to_dict())
                        changed = True
                    else:
                        raise BoundaryError("collection_upgrade", "unknown_phase")
                if phase == "activate":
                    check_preparations()
                    if ProjectConfig.load(config_path) != candidate:
                        raise BoundaryError("collection_upgrade", "configuration_changed")
                return {
                    "schema": "stpd/collection-upgrade-result-v1",
                    "status": "prepared" if phase == "prepare" else "activated",
                    "delivery_config": str(target),
                    "previous_delivery_config": str(config.delivery_config),
                    "tool_release_id": release_id,
                    "enrollment_id": enrollment_id,
                    "delivery_started": False,
                    "next_action": "cold_load_then_activate"
                    if phase == "prepare"
                    else "open_workbench",
                }
            except BaseException:
                # A post-yield owner drift invalidates publication. Never retain a new active
                # pointer after its completion guard failed; preserve all generation evidence.
                if changed and ProjectConfig.load(config_path) == candidate:
                    atomic_json(config_path, config.to_dict())
                raise
        finally:
            members.close()
