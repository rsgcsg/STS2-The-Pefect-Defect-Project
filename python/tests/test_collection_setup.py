"""Durable consent/configuration and current native proof remain separate authorities."""

from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path

import pytest
from test_campaign_onboarding import campaign as campaign
from test_campaign_onboarding import enroll

from spireagent.json_boundary import BoundaryError
from spireagent.workbench.campaign_prepare import prepare_campaign, read_preparation
from spireagent.workbench.collection_setup import CollectionSetup
from spireagent.workbench.collection_tool_registration import register_collection_tool
from spireagent.workbench.developer import atomic_json
from spireagent.workbench.identity import LocalIdentity
from spireagent.workbench.member_client import MemberClient
from stpd.collection_activity import CONSENT_FIELDS


def daily(campaign):
    service, admin, member, _, config, tool = campaign
    template = service.publish_default(
        admin,
        {
            "name": "Daily",
            "description": "Synthetic test",
            "consent_text": "Explicit new recordings",
        },
        ["storage.example.invalid"],
    )
    selected = service.enroll(
        member, template["template_id"], "computer", {key: True for key in CONSENT_FIELDS}
    )
    register_collection_tool(config, tool, campaign[3]["tool_release_id"])
    return selected


def setup(campaign, selected, monkeypatch):
    client = MemberClient(LocalIdentity(campaign[4]))
    calls = []

    def request(route, body=None):
        calls.append(route)
        if route == "collection-settings":
            return {"default": None, "observed_at": "synthetic"}
        if route.startswith("campaigns/enrollments?"):
            return {"items": [], "next_offset": 25}
        assert route == "campaigns/enrollments/" + selected["enrollment_id"]
        return copy.deepcopy(selected)

    monkeypatch.setattr(client, "request", request)
    return CollectionSetup(client), calls


def owner_reply(prepared, template=None):
    return {
        "schema": "sts2.platform/collection-setup-1",
        "recordings_root": prepared["recordings_root"],
        "status": "bound",
        "bound": True,
        "next_action": "none",
        "loaded_identity": {"game": {} if template is None else template["game"]},
        "installed_artifact": {}
        if template is None
        else {
            "sha256": template["mod"]["sha256"],
            "module_version_id": template["mod"]["mvid"],
        },
    }


def test_daily_consent_has_no_software_pin_and_old_consent_remains_immutable(campaign):
    legacy = enroll(campaign)
    selected = daily(campaign)
    assert selected["template"]["schema"] == "stpd/collection-activity-v2"
    assert not {"game", "mod", "tool_release_id"} & selected["template"].keys()
    changed = replace(campaign[4], combination={"platform_source_revision": "e" * 40})
    prepared = prepare_campaign(changed, selected, campaign[5])
    assert prepared["required_native_identity"] is None
    assert read_preparation(changed, selected) == prepared
    assert legacy["template"]["game"] == campaign[3]["game"]
    with pytest.raises(BoundaryError, match="approved_combination_required"):
        prepare_campaign(changed, legacy, campaign[5])


def test_current_registration_never_relabels_existing_queue(campaign, monkeypatch):
    selected = daily(campaign)
    prepared = prepare_campaign(campaign[4], selected, campaign[5])
    monkeypatch.setattr(
        "spireagent.workbench.collection_tool_registration.current_collection_tool",
        lambda config: pytest.fail("Existing queue must keep its exact tool"),
    )
    assert prepare_campaign(campaign[4], selected, Path("/different-new-release")) == prepared


@pytest.mark.parametrize("change", ["missing_game", "game_sha", "mod", "none"])
def test_legacy_identity_checked_against_current_owner_report(campaign, monkeypatch, change):
    selected = enroll(campaign)
    prepared = prepare_campaign(campaign[4], selected, campaign[5])
    result = copy.deepcopy(owner_reply(prepared, campaign[3]))
    if change == "missing_game":
        result["loaded_identity"]["game"] = {}
    elif change == "game_sha":
        result["loaded_identity"]["game"]["assembly_sha256"] = "0" * 64
    elif change == "mod":
        result["installed_artifact"]["module_version_id"] = "wrong"
    monkeypatch.setattr(
        "spireagent.workbench.collection_setup.CollectionTool.setup_status",
        lambda self, **kwargs: result,
        raising=False,
    )
    owner, _ = setup(campaign, selected, monkeypatch)
    observed = owner.preparation(selected, "running")
    assert observed["status"] != "ready"  # No uploader is attached, irrespective of native state.
    assert observed["native_binding"]["bound"] is (change == "none")
    if change != "none":
        with pytest.raises(BoundaryError, match="native_binding_required"):
            owner.activation_config(selected["enrollment_id"])


def test_saved_flags_cannot_manufacture_readiness_and_active_entry_survives_pagination(
    campaign,
    monkeypatch,
):
    selected = daily(campaign)
    prepared = prepare_campaign(campaign[4], selected, campaign[5])
    path = Path(prepared["delivery_config"]).with_name("preparation.json")
    atomic_json(path, {**prepared, "native_binding_verified": True, "delivery_started": True})
    owner, calls = setup(campaign, selected, monkeypatch)
    owner.members.account.config = replace(
        campaign[4], delivery_config=Path(prepared["delivery_config"])
    )
    reply = owner_reply(prepared)
    reply.update(status="blocked", bound=False, next_action="launch_game")
    monkeypatch.setattr(
        "spireagent.workbench.collection_setup.CollectionTool.setup_status",
        lambda self, **kwargs: reply,
        raising=False,
    )
    observed = owner.status("running")
    assert len(observed["items"]) == 1
    current = observed["items"][0]["preparation"]
    assert current["configuration_saved"] and current["delivery_selected"]
    assert current["status"] != "ready" and current["next_action"] == "launch_game"
    assert "campaigns/enrollments/" + selected["enrollment_id"] in calls


def test_binding_another_enrollment_cannot_strand_active_uploader(campaign, monkeypatch):
    selected = daily(campaign)
    prepare_campaign(campaign[4], selected, campaign[5])
    owner, _ = setup(campaign, selected, monkeypatch)
    owner.members.account.config = replace(
        campaign[4], delivery_config=Path("/other/delivery.json")
    )
    monkeypatch.setattr(
        owner, "_native", lambda *a, **kw: pytest.fail("No native mutation allowed")
    )
    with pytest.raises(BoundaryError, match="another_collection_attached"):
        owner.bind(selected["enrollment_id"], str(campaign[4].state_dir / "synthetic-game"))


def test_legacy_constraints_cannot_be_removed_from_preparation_file(campaign):
    selected = enroll(campaign)
    prepared = prepare_campaign(campaign[4], selected, campaign[5])
    atomic_json(
        Path(prepared["delivery_config"]).with_name("preparation.json"),
        {**prepared, "required_native_identity": None},
    )
    with pytest.raises(BoundaryError, match="preparation_exists_or_incomplete"):
        read_preparation(campaign[4], selected)


def test_read_cannot_bypass_legacy_source_combination(campaign):
    selected = enroll(campaign)
    prepare_campaign(campaign[4], selected, campaign[5])
    with pytest.raises(BoundaryError, match="approved_combination_required"):
        read_preparation(replace(campaign[4], combination={}), selected)


@pytest.mark.parametrize("failure", ["native", "doctor", "runtime", "none"])
def test_activation_persists_only_after_fresh_checks_and_rolls_back_failed_write(
    campaign,
    monkeypatch,
    failure,
):
    from spireagent.workbench import developer_server as module
    from spireagent.workbench.developer import combination

    selected = daily(campaign)
    config = replace(campaign[4], combination=combination())
    prepared = prepare_campaign(config, selected, campaign[5])
    config_path = config.state_dir / "project.json"
    atomic_json(config_path, config.to_dict())
    app = module.Application(config, config_path=config_path)
    runtime_path = config.state_dir / "runtime.json"
    atomic_json(runtime_path, {"instance_id": app.instance_id, "configuration_id": "old"})
    original = config_path.read_bytes()
    started = []

    def native(identity):
        assert identity == selected["enrollment_id"]
        if failure == "native":
            raise BoundaryError("collection", "native_binding_required")
        return Path(prepared["delivery_config"])

    monkeypatch.setattr(app.collection, "activation_config", native)
    monkeypatch.setattr(
        module, "doctor", lambda cfg: {"status": "FAIL" if failure == "doctor" else "PASS"}
    )
    monkeypatch.setattr(app.collection, "enrollment", lambda identity: selected)
    monkeypatch.setattr(app.collection, "preparation", lambda item, status: {"status": status})
    monkeypatch.setattr(app, "start_delivery", lambda: started.append(True))
    write = module.atomic_json

    def persist(path, value):
        if failure == "runtime" and path == runtime_path:
            raise OSError("synthetic metadata persistence failure")
        write(path, value)

    monkeypatch.setattr(module, "atomic_json", persist)
    if failure != "none":
        with pytest.raises((BoundaryError, OSError)):
            app.activate_collection(selected["enrollment_id"])
        assert config_path.read_bytes() == original and app.config == config and not started
    else:
        app.activate_collection(selected["enrollment_id"])
        updated = module.ProjectConfig.load(config_path)
        assert updated.delivery_config == Path(prepared["delivery_config"])
        assert app.account.config == app.models.config == app.config == updated
        assert started == [True]
        # A restarted workbench reads the selected delivery from durable configuration.
        reopened = module.Application(updated, config_path=config_path)
        assert reopened.config.delivery_config == updated.delivery_config
