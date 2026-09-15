"""S1-specific installation checks; importing this module never loads model weights."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from spireagent.encoding import canonical_json
from spireagent.json_boundary import BoundaryError, digest
from spireagent.package_identity import file_sha256
from spireagent.policy_files import _inside, _object_file


def _s1_code_digest(root: Path) -> str:
    # Reading this literal keeps collector inspection free of Torch imports and
    # uses the adapter's own closure inventory instead of a second copied list.
    tree = ast.parse((root / "stpd/policy/adapter.py").read_text(encoding="utf-8"))
    inventory: object = None
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "ADAPTER_SOURCE_CLOSURE"
            for target in statement.targets
        ):
            inventory = ast.literal_eval(statement.value)
    if not isinstance(inventory, tuple) or not inventory:
        raise BoundaryError("local_model", "adapter_source_inventory_missing")
    files = [
        {"path": relative, "sha256": file_sha256(_inside(root, relative))} for relative in inventory
    ]
    return hashlib.sha256(canonical_json(files).encode()).hexdigest()


def _backend_check() -> dict[str, str]:
    if any(importlib.util.find_spec(name) is None for name in ("torch", "transformers")):
        return {"status": "blocked", "code": "install_locked_ml_and_l2_dependencies"}
    if sys.platform == "darwin":
        return {"status": "blocked", "code": "s1_requires_cuda_bf16_backend"}
    script = (
        "import json,torch; print(json.dumps({'available':torch.cuda.is_available() "
        "and torch.cuda.is_bf16_supported()}))"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, timeout=15, check=False
        )
        ready = result.returncode == 0 and json.loads(result.stdout).get("available") is True
        return {
            "status": "pass" if ready else "blocked",
            "code": "cuda_bf16_available" if ready else "s1_requires_cuda_bf16_backend",
        }
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"status": "blocked", "code": "backend_probe_unavailable"}


def inspect(
    root: Path, entry: dict[str, Any], manifest: dict[str, Any], policy_config: dict[str, Any]
) -> dict[str, dict[str, str]]:
    checks: dict[str, dict[str, str]] = {}

    def check(name: str, operation: Callable[[], object]) -> None:
        try:
            operation()
            checks[name] = {"status": "pass"}
        except (OSError, ValueError, KeyError, BoundaryError, subprocess.SubprocessError) as error:
            checks[name] = {
                "status": "blocked",
                "code": error.code
                if isinstance(error, BoundaryError)
                else name + "_missing_or_drifted",
            }

    def exact_file(path: Path, expected: object) -> None:
        if file_sha256(path) != digest(expected, "local_model.sha256"):
            raise BoundaryError("local_model", "artifact_checksum_mismatch")

    def manifest_check() -> None:
        if (
            manifest.get("schema") != "sts2.policy-runtime/policy-manifest-1"
            or manifest.get("adapter", {}).get("code_sha256") != _s1_code_digest(root)
            or manifest.get("artifact", {}).get("sha256") != policy_config["checkpoint_sha256"]
        ):
            raise BoundaryError("local_model", "trusted_policy_identity_drift")
        pin = manifest["adapter_config"]["s1"]["config"]
        if pin["path"] != entry["config"]:
            raise BoundaryError("local_model", "trusted_policy_config_drift")
        exact_file(_inside(root, entry["config"]), pin["sha256"])

    check("policy_identity", manifest_check)
    check(
        "checkpoint",
        lambda: exact_file(
            _inside(root, policy_config["checkpoint_path"]),
            policy_config["checkpoint_sha256"],
        ),
    )
    check(
        "training_ready",
        lambda: exact_file(
            _inside(root, policy_config["ready_path"]), policy_config["ready_sha256"]
        ),
    )
    check(
        "checkpoint_sidecar",
        lambda: (
            _object_file(_inside(root, policy_config["checkpoint_path"] + ".manifest.json"))
            and None
        ),
    )
    checks["backend"] = _backend_check()
    return checks


def arguments(entry: dict[str, Any]) -> list[str]:
    return ["tools/policy_adapter.py", "--config", entry["config"], "--manifest", entry["manifest"]]
