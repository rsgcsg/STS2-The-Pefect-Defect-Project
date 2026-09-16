"""The short collection flow composes consent/native owners and preserves old queues."""

from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path

import pytest
from sts2_platform_evidence.collection_tool import CollectionTool
from test_campaign_onboarding import campaign as campaign

from spireagent.json_boundary import BoundaryError
from spireagent.workbench.campaign_prepare import read_preparation
from spireagent.workbench.collection_flow import (
    PREFERENCE_FILE,
    CollectionFlow,
    save_upload_preference,
    upload_preference,
)
from spireagent.workbench.collection_setup import CollectionSetup
from spireagent.workbench.collection_tool_registration import register_collection_tool
from spireagent.workbench.developer import atomic_json
from spireagent.workbench.identity import LocalIdentity
from spireagent.workbench.member_client import MemberClient


@pytest.fixture
def journey(campaign, monkeypatch):
    service, admin, member, _, config, tool = campaign
    published = service.publish_default(
        admin,
        {"name": "Daily", "description": "Synthetic", "consent_text": "Human/upload/sharing"},
        ["storage.example.invalid"],
    )
    register_collection_tool(config, tool, campaign[3]["tool_release_id"])
    client = MemberClient(LocalIdentity(config))
    state = {
        "enrollments": {},
        "running": False,
        "offline": False,
        "device_revoked": False,
        "binds": 0,
        "activations": 0,
        "native": {
            "schema": "sts2.platform/collection-setup-1",
            "status": "blocked",
            "reason": "recording_root_not_configured",
            "next_action": "bind_recording_root",
            "bound": False,
            "configured": False,
            "game_running": False,
            "game_directory": str(config.state_dir / "synthetic-game"),
        },
    }

    def request(route, body=None):
        if state["offline"]:
            raise BoundaryError("identity", "hub_unavailable")
        if state["device_revoked"]:
            raise BoundaryError("identity", "http_403")
        if route == "collection-settings":
            return {"default": service.default(member), "observed_at": "synthetic"}
        if route.startswith("campaigns/enrollments?"):
            return {"items": list(state["enrollments"].values()), "next_offset": None}
        if route.startswith("campaigns/enrollments/"):
            return copy.deepcopy(state["enrollments"][route.split("/")[-1]])
        if route.endswith("/enroll"):
            value = service.enroll(member, route.split("/")[1], body["device_id"], body["consent"])
            state["enrollments"][value["enrollment_id"]] = value
            return value
        pytest.fail(f"Unexpected route: {route}")

    def device_request(route, *, token):
        assert route == "/v1/identity/device" and token == "x" * 40
        if state["device_revoked"]:
            raise BoundaryError("identity", "http_401")
        return {"device_id": "computer"}

    monkeypatch.setattr(client, "request", request)
    monkeypatch.setattr(client.account, "request", device_request)

    def native_status(_tool, *, recordings_root, game_directory=None):
        return {**copy.deepcopy(state["native"]), "recordings_root": str(recordings_root)}

    def native_bind(_tool, *, recordings_root, game_directory=None):
        state["binds"] += 1
        if state["native"]["game_running"]:
            state["native"].update(
                status="blocked", reason="game_must_be_stopped", next_action="close_game"
            )
        else:
            state["native"].update(
                status="configured", configured=True, next_action="launch_game", bound=False
            )
        return native_status(_tool, recordings_root=recordings_root)

    monkeypatch.setattr(CollectionTool, "setup_status", native_status)
    monkeypatch.setattr(CollectionTool, "bind_recording_root", native_bind)
    setup = CollectionSetup(client)

    def activate(identity):
        path = setup.activation_config(identity)
        state["activations"] += 1
        client.account.config = replace(client.account.config, delivery_config=path)
        state["running"] = upload_preference(client.account.config)["enabled"]
        return setup.preparation(setup.enrollment(identity), process())

    def process():
        return "running" if state["running"] else "stopped"

    def stop():
        # The durable pause must exist before terminating a process.
        assert upload_preference(client.account.config)["enabled"] is False
        state["running"] = False

    flow = CollectionFlow(setup, delivery_process=process, activate=activate, stop_delivery=stop)
    return flow, state, published


def consent(journey):
    flow, _, published = journey
    return flow.consent({"template_id": published["template_id"], "accepted": True})


def loaded(state):
    state["native"].update(
        status="bound", configured=True, bound=True, game_running=True, next_action="none"
    )


def test_one_explicit_action_retains_declarations_and_never_manufactures_human_proof(journey):
    flow, state, published = journey
    assert flow.status()["stage"] == "consent_required"
    result = consent(journey)
    assert result["human_origin_verified"] is False
    assert result["enrollment"]["consent"] == {
        "human_origin_attested": True,
        "upload_authorized": True,
        "project_sharing_authorized": True,
    }
    assert not state["running"] and state["binds"] == 0
    assert flow.consent({"template_id": published["template_id"], "accepted": True}) == result
    assert len(state["enrollments"]) == 1


@pytest.mark.parametrize("accepted", [False, None, 1, "true"])
def test_opening_or_invalid_consent_cannot_authorize(journey, accepted):
    flow, state, published = journey
    with pytest.raises(BoundaryError, match="explicit_collection_consent_required"):
        flow.consent({"template_id": published["template_id"], "accepted": accepted})
    with pytest.raises(BoundaryError, match="collection_consent_required"):
        flow.prepare({})
    assert not state["enrollments"] and not (flow.config.state_dir / PREFERENCE_FILE).exists()


def test_notice_change_requires_the_notice_actually_displayed(journey):
    flow, state, _ = journey
    with pytest.raises(BoundaryError, match="collection_notice_changed"):
        flow.consent({"template_id": "f" * 64, "accepted": True})
    assert not state["enrollments"]


def test_prepare_reuses_persistent_owner_steps_and_waits_for_native_load(journey):
    flow, state, _ = journey
    selected = consent(journey)["enrollment"]
    result = flow.prepare({})
    assert result["next_action"] == "launch_game"
    assert state["binds"] == 1 and state["activations"] == 0
    prepared = read_preparation(flow.config, selected)
    before = Path(prepared["delivery_config"]).read_bytes()
    assert flow.prepare({})["next_action"] == "launch_game"
    assert state["binds"] == 1
    loaded(state)
    assert flow.prepare({})["stage"] == "ready"
    assert state["activations"] == 1 and state["running"]
    assert Path(prepared["delivery_config"]).read_bytes() == before


def test_running_game_and_unknown_owner_never_auto_rebind(journey):
    flow, state, _ = journey
    consent(journey)
    state["native"].update(game_running=True, next_action="close_game")
    assert flow.prepare({})["next_action"] == "close_game"
    assert state["binds"] == state["activations"] == 0
    state["native"].update(game_running=None, next_action="review_runtime")
    assert flow.prepare({})["next_action"] == "review_runtime"
    assert state["binds"] == state["activations"] == 0


def test_user_directory_still_goes_through_native_stopped_game_guard(journey):
    flow, state, _ = journey
    consent(journey)
    state["native"]["game_running"] = True
    result = flow.prepare({"game_directory": str(flow.config.state_dir / "chosen-game")})
    assert result["next_action"] == "close_game" and state["activations"] == 0
    assert state["binds"] == 1


def test_pause_survives_restart_offline_and_duplicate_consent(journey):
    flow, state, _ = journey
    consent(journey)
    loaded(state)
    flow.prepare({})
    state["offline"] = True
    assert flow.set_upload({"enabled": False})["stage"] == "upload_paused"
    assert not state["running"]
    assert upload_preference(flow.config) == {"enabled": False, "explicit": True}
    assert flow.status()["upload"]["enabled"] is False
    assert flow.status()["stage"] == "unavailable"
    state["offline"] = False
    consent(journey)
    flow.prepare({})
    assert upload_preference(flow.config)["enabled"] is False and not state["running"]
    reopened = CollectionFlow(
        flow.setup,
        delivery_process=flow.delivery_process,
        activate=flow.activate,
        stop_delivery=flow.stop_delivery,
    )
    assert reopened.status()["stage"] == "upload_paused"
    assert reopened.set_upload({"enabled": True})["stage"] == "ready"


def test_revoked_or_unavailable_authority_cannot_resume(journey):
    flow, state, _ = journey
    consent(journey)
    loaded(state)
    flow.prepare({})
    flow.set_upload({"enabled": False})
    state["device_revoked"] = True
    with pytest.raises(BoundaryError, match="http_403"):
        flow.set_upload({"enabled": True})
    assert upload_preference(flow.config)["enabled"] is False and not state["running"]


def test_stop_failure_cannot_lose_durable_pause(journey):
    flow, state, _ = journey
    consent(journey)

    def failed_stop():
        raise OSError("synthetic process failure")

    flow.stop_delivery = failed_stop
    with pytest.raises(OSError):
        flow.set_upload({"enabled": False})
    assert upload_preference(flow.config)["enabled"] is False


def test_process_still_running_cannot_be_presented_as_paused(journey):
    flow, state, _ = journey
    consent(journey)
    loaded(state)
    flow.prepare({})
    flow.stop_delivery = lambda: None
    result = flow.set_upload({"enabled": False})
    assert result["stage"] == "upload_stop_failed"
    assert result["error"] == "delivery_still_running"
    assert flow.status()["stage"] == "upload_stop_failed"


def test_blocked_attached_collection_never_becomes_a_new_enrollment(journey, monkeypatch):
    flow, state, _ = journey
    selected = consent(journey)["enrollment"]
    loaded(state)
    flow.prepare({})
    monkeypatch.setattr(
        flow.setup,
        "preparation",
        lambda *a, **k: {"status": "blocked", "next_action": "review_setup", "error": "drift"},
    )
    result = flow.status()
    assert result["stage"] == "blocked" and result["consent_required"] is False
    assert result["enrollment"]["enrollment_id"] == selected["enrollment_id"]


def test_prepare_reuses_old_explicit_consent_without_reauthorizing(journey):
    flow, state, _ = journey
    consent(journey)
    (flow.config.state_dir / PREFERENCE_FILE).unlink()
    loaded(state)
    assert flow.prepare({})["stage"] == "ready"
    assert len(state["enrollments"]) == 1


def test_preference_cannot_cross_device_or_hub_and_malformed_is_not_default(journey):
    flow, _, _ = journey
    assert upload_preference(flow.config) == {"enabled": False, "explicit": False}
    legacy = replace(flow.config, delivery_config=flow.config.state_dir / "old-delivery.json")
    assert upload_preference(legacy)["enabled"] is True
    save_upload_preference(flow.config, False)
    with pytest.raises(BoundaryError, match="upload_preference_mismatch"):
        upload_preference(replace(flow.config, hub_url="https://different.example.invalid"))
    atomic_json(flow.config.state_dir / PREFERENCE_FILE, {})
    with pytest.raises(BoundaryError, match="missing_or_unknown_fields"):
        upload_preference(legacy)


def test_resume_revalidates_device_even_with_valid_personal_membership(journey, monkeypatch):
    flow, _, _ = journey
    consent(journey)
    flow.set_upload({"enabled": False})
    monkeypatch.setattr(flow.members.account, "request", lambda *a, **k: {"device_id": "other"})
    with pytest.raises(BoundaryError, match="matching_local_device_required"):
        flow.set_upload({"enabled": True})
    assert upload_preference(flow.config)["enabled"] is False


def test_broken_preference_blocks_upload_but_keeps_status_and_stop(journey, monkeypatch):
    flow, state, _ = journey
    path = flow.config.state_dir / PREFERENCE_FILE
    path.write_text("broken json")
    path.chmod(0o600)
    state["running"] = True
    monkeypatch.setattr(flow, "stop_delivery", lambda: state.update(running=False))
    status = flow.status()
    assert status["stage"] == "upload_blocked"
    assert status["upload"]["enabled"] is False
    stopped = flow.set_upload({"enabled": False})
    assert stopped["upload"]["process"] != "running"
    assert path.read_text() == "broken json"
    assert stopped["error"]
