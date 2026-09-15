"""Same-schema deployment guards; no Docker, network or actual state changes."""

from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import closing

import preflight
import pytest
import rollout

OLD = "registry.example/hub@sha256:" + "a" * 64
NEW = "registry.example/hub@sha256:" + "b" * 64


def configs(tmp_path, monkeypatch):
    old = {key: "synthetic" for key in preflight.PUBLIC_KEYS}
    old.update(STPD_WORKER_IMAGE=OLD, STPD_HUB_BUDGET_UNITS="0")
    new = dict(old, STPD_WORKER_IMAGE=NEW)
    paths = tmp_path / "old.env", tmp_path / "new.env"
    for p, value in zip(paths, (old, new), strict=True):
        p.write_text("\n".join(f"{k}={v}" for k, v in value.items()) + "\n")
        p.chmod(0o600)
    # Windows cannot enforce Unix private modes; production preflight keeps its own checks.
    original = preflight.read_env
    monkeypatch.setattr(preflight, "read_env", lambda p, keys, **kw: original(p, keys))
    monkeypatch.setattr(rollout, "image", lambda: OLD)
    return paths


def test_plan_changes_only_hub_and_pins_inputs(tmp_path, monkeypatch):
    old, new = configs(tmp_path, monkeypatch)
    result = rollout.plan(old, new, "c" * 40, "d" * 64)
    assert result["services"] == ["hub"]
    assert result["database"] == "same_schema_only_no_restore"
    assert rollout.plan(old, old, "c" * 40, "d" * 64)["services"] == []
    original = result["plan_sha256"]
    new.write_text(new.read_text() + "\n")
    assert rollout.plan(old, new, "c" * 40, "d" * 64)["plan_sha256"] != original
    new.write_text(new.read_text().replace("STPD_HUB_BUDGET_UNITS=0", "STPD_HUB_BUDGET_UNITS=1"))
    with pytest.raises(preflight.PreflightError, match="configuration"):
        rollout.plan(old, new, "c" * 40, "d" * 64)


def test_running_image_and_loaded_producer_both_must_match(tmp_path, monkeypatch):
    old, new = configs(tmp_path, monkeypatch)
    result = rollout.plan(old, new, "c" * 40, "d" * 64)
    monkeypatch.setattr(rollout, "image", lambda: NEW)
    with pytest.raises(preflight.PreflightError, match="running_image"):
        rollout.plan(old, new, "c" * 40, "d" * 64)
    monkeypatch.setattr(rollout, "health", lambda: {"producer": {"source_revision": "x"}})
    with pytest.raises(preflight.PreflightError, match="producer"):
        rollout.verify(result)
    monkeypatch.setattr(rollout, "health", lambda: {"producer": result["expected_producer"]})
    assert rollout.verify(result)["status"] == "service_identity_verified"


def test_schema_probe_has_no_state_secrets_network_or_gpu(tmp_path, monkeypatch):
    db_path = tmp_path / "operations.sqlite"
    with closing(sqlite3.connect(db_path)) as db:
        db.execute("PRAGMA user_version=4")
    monkeypatch.setattr(
        preflight, "read_env", lambda *a, **kw: {"STPD_HUB_STATE_DIR": str(tmp_path)}
    )
    calls = []

    def probe(args):
        calls.append(args)
        return "5"

    monkeypatch.setattr(rollout, "command", probe)
    with pytest.raises(preflight.PreflightError, match="schema_change"):
        rollout.require_same_schema(tmp_path / "config", NEW)
    args = calls[0]
    assert "--network" in args and "none" in args and "--read-only" in args
    assert not {"--mount", "--volume", "--env-file", "--gpus"} & set(args)
    assert "Operations(" not in args[-1]
    monkeypatch.setattr(rollout, "command", lambda _: "4")
    rollout.require_same_schema(tmp_path / "config", NEW)
    with closing(sqlite3.connect(db_path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 4


def test_plan_output_contains_no_runtime_credentials(tmp_path, monkeypatch):
    old, new = configs(tmp_path, monkeypatch)
    result = rollout.plan(old, new, "c" * 40, "d" * 64)
    assert "synthetic" not in json.dumps(result)


@pytest.mark.skipif(sys.platform == "win32", reason="production apply uses Linux flock")
@pytest.mark.parametrize("failure", ["backup", "drift", "compose", None])
def test_apply_preserves_recovery_and_never_restores_database(tmp_path, monkeypatch, failure):
    old, new = configs(tmp_path, monkeypatch)
    initial = old.read_bytes()
    selected = rollout.plan(old, new, "c" * 40, "d" * 64)
    receipts = tmp_path / "receipts"
    receipts.mkdir(mode=0o700)
    backup_path = tmp_path / "backup.json"
    backup_path.write_text(json.dumps({"worker_image": OLD, "last_backup_receipt": "e" * 64}))
    monkeypatch.setattr(preflight, "host_checks", lambda: {})
    monkeypatch.setattr(preflight, "check_configuration", lambda _: {})
    monkeypatch.setattr(preflight, "check_capacity", lambda *a, **kw: {"status": "ok"})
    from types import SimpleNamespace

    monkeypatch.setattr(
        preflight,
        "operational_owner",
        lambda _: SimpleNamespace(
            freshness=lambda _: {"freshness": "attention" if failure == "backup" else "ok"},
        ),
    )
    monkeypatch.setattr(rollout, "require_same_schema", lambda *a: None)
    monkeypatch.setattr(rollout, "verify", lambda _: {"status": "service_identity_verified"})
    calls = []

    def execute(args):
        calls.append(args)
        if "inspect" in args and failure == "drift":
            new.write_bytes(new.read_bytes() + b"\n")
        if "up" in args and failure == "compose":
            raise preflight.PreflightError("simulated_interruption")
        return ""

    monkeypatch.setattr(rollout, "command", execute)
    args = (old, new, "c" * 40, "d" * 64, selected["plan_sha256"], receipts, backup_path, tmp_path)
    if failure:
        with pytest.raises(preflight.PreflightError):
            rollout.apply(*args)
        assert old.read_bytes() == initial
    else:
        assert rollout.apply(*args)["status"] == "applied_service_verified"
        assert old.read_bytes() == new.read_bytes()
    if failure in {"backup", "drift"}:
        assert not any("up" in args for args in calls)
    saved = list(receipts.glob("*/previous.env"))
    if failure != "backup":
        assert len(saved) == 1 and saved[0].read_bytes() == initial
        receipt = json.loads(saved[0].with_name("receipt.json").read_bytes())
        assert receipt["database_restore"] is False
        assert receipt["status"] == (
            "attention_required_inspect_before_recovery" if failure else "applied_service_verified"
        )
    assert not any("restore" in arg or "prune" in arg for args in calls for arg in args)
