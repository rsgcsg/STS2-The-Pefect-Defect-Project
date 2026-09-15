"""Composition tests; native/transfer authorities are explicit contract spies here."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest
from sts2_platform_evidence.collection_tool import CollectionTool, digest
from test_campaign_onboarding import campaign as campaign
from test_collection_setup import daily

from stpd.json_boundary import BoundaryError
from stpd.workbench import collection_upgrade as module
from stpd.workbench.campaign_prepare import prepare_campaign, read_preparation
from stpd.workbench.collection_setup import CollectionSetup
from stpd.workbench.collection_tool_registration import register_collection_tool
from stpd.workbench.developer import ProjectConfig, atomic_json, combination
from stpd.workbench.identity import LocalIdentity
from stpd.workbench.member_client import MemberClient


@pytest.fixture
def upgrade_case(campaign, tmp_path, monkeypatch):
    selected = daily(campaign)
    config = replace(campaign[4], combination=combination())
    previous = prepare_campaign(config, selected, campaign[5])
    config = replace(config, delivery_config=Path(previous["delivery_config"]))
    config_path = config.state_dir / "project.json"
    atomic_json(config_path, config.to_dict())
    old_bytes = {p: p.read_bytes() for p in config.delivery_config.parent.iterdir() if p.is_file()}
    new = tmp_path / "new-tool"
    shutil.copytree(campaign[5], new)
    binary = new / "sts2-human-annotator.dll"
    binary.write_bytes(b"synthetic second tool")
    manifest = json.loads((new / "collection-tool.json").read_bytes())
    for row in manifest["identity"]["files"]:
        raw = (new / row["path"]).read_bytes()
        row.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    release = digest(manifest["identity"])
    manifest["release_id"] = release
    (new / "collection-tool.json").write_text(json.dumps(manifest))
    register_collection_tool(config, new, release, replace=True)
    state = {
        "root": previous["recordings_root"],
        "running": False,
        "complete": True,
        "drift": False,
        "doctor": "PASS",
        "calls": 0,
    }

    class Receipt:
        def to_dict(self):
            return {"schema": "synthetic-completion-spy", "preserved_recording_failures": 1}

    @contextmanager
    def complete(value):
        assert value.tool_release_id == campaign[3]["tool_release_id"]
        state["calls"] += 1
        if not state["complete"]:
            raise ValueError("owner_completion_rejected")
        yield Receipt()
        if state["drift"]:
            raise ValueError("owner_detected_post_yield_drift")

    def native(self, *, recordings_root, game_directory, **kwargs):
        same = str(recordings_root) == state["root"]
        return {
            "schema": "sts2.platform/collection-setup-1",
            "recordings_root": str(recordings_root),
            "status": ("bound" if state["running"] else "configured") if same else "blocked",
            "configured": same,
            "game_running": state["running"],
            "bound": same and state["running"],
        }

    def bind(self, *, recordings_root, game_directory, **kwargs):
        assert not state["running"]
        state["root"] = str(recordings_root)
        return native(self, recordings_root=recordings_root, game_directory=game_directory)

    def request(self, route, body=None):
        assert body is None  # No new consent, device or remote mutations.
        if route == "collection-settings":
            return {"default": None, "observed_at": "fixture"}
        if route.startswith("campaigns/enrollments?"):
            return {"items": [], "next_offset": None}
        assert route == "campaigns/enrollments/" + selected["enrollment_id"]
        return copy.deepcopy(selected)

    monkeypatch.setattr(MemberClient, "request", request)
    monkeypatch.setattr(module, "completion", complete)
    monkeypatch.setattr(module, "doctor", lambda config: {"status": state["doctor"]})
    monkeypatch.setattr(CollectionTool, "setup_status", native)
    monkeypatch.setattr(CollectionTool, "bind_recording_root", bind)
    return config_path, config, selected, release, state, old_bytes


def invoke(case, phase):
    path, _, selected, release, *_ = case
    return module.upgrade(
        path,
        selected["enrollment_id"],
        release,
        phase=phase,
        game_directory=path.parent / "synthetic-game",
    )


def test_same_consent_fresh_generation_active_pointer_and_reopening(upgrade_case):
    path, config, selected, release, state, originals = upgrade_case
    prepared = invoke(upgrade_case, "prepare")
    assert prepared["status"] == "prepared" and prepared["delivery_started"] is False
    assert ProjectConfig.load(path) == config
    assert read_preparation(config, selected)["delivery_config"] == str(config.delivery_config)
    state["running"] = True
    result = invoke(upgrade_case, "activate")
    active = ProjectConfig.load(path)
    assert result["status"] == "activated" and result["delivery_started"] is False
    assert active.delivery_config == Path(prepared["delivery_config"])
    saved = read_preparation(active, selected)
    assert saved["enrollment"] == selected and saved["tool_release_id"] == release
    assert saved["outbox_root"] != str(config.delivery_config.parent / "outbox")
    assert all(p.read_bytes() == raw for p, raw in originals.items())
    assert state["calls"] == 2
    setup = CollectionSetup(MemberClient(LocalIdentity(active)))
    current = setup.status("running")["items"]
    assert len(current) == 1 and current[0]["preparation"]["status"] == "ready"


@pytest.mark.parametrize("failure", ["owner", "running", "different_root"])
def test_prepare_failure_cannot_rebind_or_select_new_queue(upgrade_case, failure):
    path, config, _, _, state, originals = upgrade_case
    if failure == "owner":
        state["complete"] = False
    elif failure == "running":
        state["running"] = True
    else:
        state["root"] = "/different-account-root"
    root = state["root"]
    with pytest.raises(ValueError):
        invoke(upgrade_case, "prepare")
    assert state["root"] == root and ProjectConfig.load(path) == config
    assert all(p.read_bytes() == raw for p, raw in originals.items())


@pytest.mark.parametrize(
    "failure", ["owner", "native", "doctor", "drift", "recording", "outbox", "receipt"]
)
def test_activation_failure_preserves_old_active_config(upgrade_case, failure):
    path, config, _, _, state, originals = upgrade_case
    proposed = invoke(upgrade_case, "prepare")
    generation = Path(proposed["delivery_config"]).parent
    state["running"] = True
    if failure == "owner":
        state["complete"] = False
    elif failure == "native":
        state["root"] = "wrong-root"
    elif failure == "doctor":
        state["doctor"] = "FAIL"
    elif failure == "drift":
        state["drift"] = True
    elif failure in {"recording", "outbox"}:
        (
            generation / ("recordings" if failure == "recording" else "outbox") / "unexpected"
        ).write_text("retain")
    else:
        (generation / "upgrade.json").write_text("{}")
    with pytest.raises(ValueError):
        invoke(upgrade_case, "activate")
    assert ProjectConfig.load(path) == config
    assert all(p.read_bytes() == raw for p, raw in originals.items())


def test_stopped_workbench_lock_is_required_before_contacting_members(upgrade_case):
    from stpd.workbench.developer_server import instance_lock

    _, config, *rest = upgrade_case
    with (
        instance_lock(config.state_dir / "instance.lock"),
        pytest.raises(BoundaryError, match="already_running"),
    ):
        invoke(upgrade_case, "prepare")


@pytest.mark.parametrize("point", ["proposal_write", "after_native_bind"])
def test_interrupted_prepare_resumes_only_same_proposal_without_switching_queue(
    upgrade_case, monkeypatch, point
):
    path, config, _, _, state, originals = upgrade_case
    write = module.atomic_json
    bind = CollectionTool.bind_recording_root

    def interrupted_write(target, value):
        if target.name == "upgrade.json":
            raise OSError("simulated disk interruption before native binding")
        write(target, value)

    def interrupted_bind(self, **kwargs):
        bind(self, **kwargs)
        raise OSError("simulated process loss after native binding")

    with monkeypatch.context() as failure:
        if point == "proposal_write":
            failure.setattr(module, "atomic_json", interrupted_write)
        else:
            failure.setattr(CollectionTool, "bind_recording_root", interrupted_bind)
        with pytest.raises(OSError):
            invoke(upgrade_case, "prepare")
    assert ProjectConfig.load(path) == config
    if point == "proposal_write":
        assert state["root"] == str(config.delivery_config.parent / "recordings")
    resumed = invoke(upgrade_case, "prepare")
    assert resumed == invoke(upgrade_case, "prepare")
    assert state["root"] == str(Path(resumed["delivery_config"]).parent / "recordings")
    assert ProjectConfig.load(path) == config
    assert all(p.read_bytes() == raw for p, raw in originals.items())


def test_proposal_does_not_authorize_rebinding_another_profile(upgrade_case):
    path, config, _, _, state, _ = upgrade_case
    invoke(upgrade_case, "prepare")
    state["root"] = "/someone-elses-root"
    with pytest.raises(BoundaryError, match="old_root_and_stopped_game_required"):
        invoke(upgrade_case, "prepare")
    assert state["root"] == "/someone-elses-root" and ProjectConfig.load(path) == config


def test_generation_config_write_failure_is_retriable_before_native_binding(
    upgrade_case, monkeypatch
):
    from stpd.workbench import campaign_prepare

    path, config, _, _, state, _ = upgrade_case
    write = campaign_prepare.atomic_json

    def fail_receipt(target, value):
        if target.name == "preparation.json":
            raise OSError("synthetic interrupted staged generation")
        write(target, value)

    with monkeypatch.context() as failure:
        failure.setattr(campaign_prepare, "atomic_json", fail_receipt)
        with pytest.raises(OSError):
            invoke(upgrade_case, "prepare")
    assert state["root"] == str(config.delivery_config.parent / "recordings")
    assert ProjectConfig.load(path) == config
    assert invoke(upgrade_case, "prepare")["status"] == "prepared"


def test_real_setup_writer_cannot_replace_config_during_upgrade_commit(upgrade_case, monkeypatch):
    from stpd.workbench.developer import setup

    path, config, _, _, state, _ = upgrade_case
    invoke(upgrade_case, "prepare")
    state["running"] = True
    write = module.atomic_json
    blocked = []

    def attempted_concurrent_setup(target, value):
        if target == path:
            with pytest.raises(BoundaryError, match="already_running"):
                setup(
                    path,
                    state_dir=config.state_dir,
                    hub_url=config.hub_url,
                    platform_url="http://127.0.0.1:9999",
                    delivery_config=config.delivery_config,
                    replace_config=True,
                    install=False,
                )
            blocked.append(True)
        write(target, value)

    monkeypatch.setattr(module, "atomic_json", attempted_concurrent_setup)
    assert invoke(upgrade_case, "activate")["status"] == "activated"
    assert blocked == [True]
    assert ProjectConfig.load(path).platform_url == config.platform_url


@pytest.mark.parametrize("when", ["doctor", "after_completion"])
@pytest.mark.parametrize("which", ["old", "new"])
def test_preparation_drift_cannot_survive_activation(upgrade_case, monkeypatch, when, which):
    path, config, _, _, state, _ = upgrade_case
    proposal = invoke(upgrade_case, "prepare")
    state["running"] = True
    target = config.delivery_config if which == "old" else Path(proposal["delivery_config"])

    def tamper():
        value = json.loads(target.read_bytes())
        value["allowed_upload_hosts"] = ["different.example.invalid"]
        atomic_json(target, value)

    if when == "doctor":

        def changed_doctor(candidate):
            tamper()
            return {"status": "PASS"}

        monkeypatch.setattr(module, "doctor", changed_doctor)
    else:
        owner_context = module.completion

        @contextmanager
        def changed_completion(value):
            with owner_context(value) as receipt:
                yield receipt
            tamper()

        monkeypatch.setattr(module, "completion", changed_completion)
    with pytest.raises(ValueError):
        invoke(upgrade_case, "activate")
    assert ProjectConfig.load(path) == config
