"""Bounded same-schema Hub image rollout using the existing Compose and preflight owners.

Plan is read-only. Apply requires the reviewed plan hash and an already pulled
image; never builds, changes budgets, migrates/restores a DB or updates TLS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import ProxyHandler, build_opener

import preflight

ROOT = Path(__file__).resolve().parent


def checksum(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise preflight.PreflightError("regular_deployment_file_required")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=240)
    if result.returncode:
        raise preflight.PreflightError("deployment_command_failed")
    return result.stdout


def image(container: str = "stpd-hub") -> str:
    value = command(["docker", "inspect", "--format", "{{.Config.Image}}", container]).strip()
    if re.fullmatch(preflight.IMAGE_PATTERN, value) is None:
        raise preflight.PreflightError("running_immutable_image_required")
    return value


def health() -> dict[str, Any]:
    with build_opener(ProxyHandler({})).open("http://127.0.0.1:8765/health", timeout=5) as r:
        value = json.loads(r.read(64 * 1024))
    if not isinstance(value, dict):
        raise preflight.PreflightError("health_object_required")
    return value


def plan(current: Path, candidate: Path, source: str, lock: str) -> dict[str, Any]:
    if re.fullmatch(r"[a-f0-9]{40}", source) is None or re.fullmatch(r"[a-f0-9]{64}", lock) is None:
        raise preflight.PreflightError("exact_candidate_source_and_lock_required")
    old = preflight.read_env(current, preflight.PUBLIC_KEYS, private=True)
    new = preflight.read_env(candidate, preflight.PUBLIC_KEYS, private=True)
    if set(old) != preflight.PUBLIC_KEYS or set(new) != preflight.PUBLIC_KEYS:
        raise preflight.PreflightError("complete_configurations_required")
    changed = sorted(k for k in old if old[k] != new[k])
    if any(k != "STPD_WORKER_IMAGE" for k in changed):
        raise preflight.PreflightError("use_runbook_for_configuration_tls_or_schema_changes")
    if old["STPD_HUB_BUDGET_UNITS"] != "0":
        raise preflight.PreflightError("rollout_requires_zero_compute_budget")
    for values in (old, new):
        if re.fullmatch(preflight.IMAGE_PATTERN, values["STPD_WORKER_IMAGE"]) is None:
            raise preflight.PreflightError("immutable_image_required")
    if image() != old["STPD_WORKER_IMAGE"]:
        raise preflight.PreflightError("running_image_differs_from_current_configuration")
    facts: dict[str, Any] = {
        "schema": "spireagent/hub-rollout-plan-v1",
        "current_config_sha256": checksum(current),
        "candidate_config_sha256": checksum(candidate),
        "compose_sha256": checksum(ROOT / "compose.yaml"),
        "caddyfile_sha256": checksum(ROOT / "Caddyfile"),
        "old_image": old["STPD_WORKER_IMAGE"],
        "new_image": new["STPD_WORKER_IMAGE"],
        "expected_producer": {"source_revision": source, "uv_lock_sha256": lock},
        "services": ["hub"] if changed else [],
        "database": "same_schema_only_no_restore",
        "budget_units": 0,
    }
    facts["plan_sha256"] = hashlib.sha256(
        json.dumps(facts, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return facts


def verify(expected: dict[str, Any]) -> dict[str, Any]:
    if image() != expected["new_image"]:
        raise preflight.PreflightError("loaded_image_mismatch")
    value = health()
    producer = value.get("producer", {})
    if not isinstance(producer, dict) or any(
        producer.get(k) != v for k, v in expected["expected_producer"].items()
    ):
        raise preflight.PreflightError("loaded_producer_mismatch")
    return {"status": "service_identity_verified", "producer": producer}


def require_same_schema(candidate: Path, selected_image: str) -> None:
    values = preflight.read_env(candidate, preflight.PUBLIC_KEYS, private=True)
    database = Path(values["STPD_HUB_STATE_DIR"]) / "operations.sqlite"
    if database.is_symlink() or not database.is_file():
        raise preflight.PreflightError("existing_operations_database_required")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        actual = db.execute("PRAGMA user_version").fetchone()[0]
    # No network, host state, secrets or GPU in this bounded image metadata check.
    declared = command(
        [
            "docker",
            "run",
            "--rm",
            "--pull",
            "never",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--memory",
            "128m",
            "--cpus",
            "1",
            "--pids-limit",
            "32",
            "--user",
            "10001:10001",
            "--entrypoint",
            "/opt/stpd/python/.venv/bin/python",
            selected_image,
            "-c",
            "from spireagent.hub.database import CURRENT_SCHEMA; print(CURRENT_SCHEMA)",
        ]
    ).strip()
    if declared != str(actual):
        raise preflight.PreflightError("schema_change_requires_explicit_migration_runbook")


def apply(
    current: Path,
    candidate: Path,
    source: str,
    lock: str,
    expected_plan: str,
    receipts: Path,
    backup_status: Path,
    image_store: Path,
) -> dict[str, Any]:
    import fcntl  # Host-only Linux command; portable plan/tests do not require it.

    if not receipts.is_absolute() or any(p.is_symlink() for p in (receipts, *receipts.parents)):
        raise preflight.PreflightError("absolute_private_receipt_directory_required")
    receipts.mkdir(mode=0o700, parents=True, exist_ok=True)
    if receipts.stat().st_mode & 0o077:
        raise preflight.PreflightError("private_receipt_directory_required")
    with (receipts / "rollout.lock").open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        value = plan(current, candidate, source, lock)
        if value["plan_sha256"] != expected_plan:
            raise preflight.PreflightError("plan_changed_review_again")
        preflight.host_checks()
        preflight.check_configuration(candidate)
        if not value["services"]:
            return {**value, **verify(value), "changed": False}
        backup = json.loads(backup_status.read_bytes())
        owner = preflight.operational_owner("backup_status")
        if (
            owner.freshness(backup)["freshness"] != "ok"
            or backup.get("worker_image") != value["old_image"]
        ):
            raise preflight.PreflightError("fresh_verified_old_image_backup_required")
        capacity = preflight.check_capacity(
            candidate,
            image_store,
            additional_bytes=0,
            additional_inodes=0,
        )
        if capacity["status"] != "ok":
            raise preflight.PreflightError("capacity_attention_required")
        # Never pull implicitly on a small production disk.
        command(["docker", "image", "inspect", value["new_image"]])
        require_same_schema(candidate, value["new_image"])
        # Unique immutable recovery files. Never overwrite an older receipt or config.
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        directory = receipts / stamp
        directory.mkdir(mode=0o700)
        saved = directory / "previous.env"
        saved.write_bytes(current.read_bytes())
        saved.chmod(0o600)
        result = {
            **value,
            "backup_receipt": backup["last_backup_receipt"],
            "status": "applying",
            "database_restore": False,
        }
        receipt = directory / "receipt.json"

        def persist() -> None:
            with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as stream:
                json.dump(result, stream, sort_keys=True, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
                pending = Path(stream.name)
            pending.replace(receipt)

        persist()
        try:
            # Recheck the plan before the first mutation after preflight and backup checks.
            if plan(current, candidate, source, lock)["plan_sha256"] != expected_plan:
                raise preflight.PreflightError("plan_changed_before_apply")
            command(
                [
                    "docker",
                    "compose",
                    "--env-file",
                    str(candidate),
                    "-f",
                    str(ROOT / "compose.yaml"),
                    "up",
                    "-d",
                    "--no-deps",
                    "--pull",
                    "never",
                    "--wait",
                    "--wait-timeout",
                    "120",
                    "hub",
                ]
            )
            result.update(verify(value))
            if checksum(candidate) != value["candidate_config_sha256"]:
                raise preflight.PreflightError("candidate_changed_during_deployment")
            # The external current config is advanced only after the new service verifies.
            with tempfile.NamedTemporaryFile(dir=current.parent, delete=False) as stream:
                stream.write(candidate.read_bytes())
                stream.flush()
                os.fsync(stream.fileno())
                pending = Path(stream.name)
            pending.replace(current)
            result["status"] = "applied_service_verified"
        except Exception:
            # Automatic DB/image rollback could erase new work or violate a changed schema.
            # Retain exact previous config; recovery follows the owning runbook.
            result["status"] = "attention_required_inspect_before_recovery"
            persist()
            raise
        persist()
        return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("plan", "apply"))
    p.add_argument("--current", required=True, type=Path)
    p.add_argument("--candidate", required=True, type=Path)
    p.add_argument("--source", required=True)
    p.add_argument("--lock", required=True)
    p.add_argument("--plan-sha256")
    p.add_argument("--receipts", type=Path, default=Path("/var/lib/stpd-maintenance/rollouts"))
    p.add_argument(
        "--backup-status", type=Path, default=Path("/var/lib/stpd-maintenance/backup-status.json")
    )
    p.add_argument("--image-store", type=Path, default=Path("/var/lib/docker"))
    a = p.parse_args()
    try:
        if a.command == "plan":
            value = plan(a.current, a.candidate, a.source, a.lock)
        else:
            if not a.plan_sha256:
                raise preflight.PreflightError("reviewed_plan_hash_required")
            value = apply(
                a.current,
                a.candidate,
                a.source,
                a.lock,
                a.plan_sha256,
                a.receipts,
                a.backup_status,
                a.image_store,
            )
        print(json.dumps(value, indent=2))
        return 0
    except Exception as e:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "code": str(e) if isinstance(e, preflight.PreflightError) else type(e).__name__,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
