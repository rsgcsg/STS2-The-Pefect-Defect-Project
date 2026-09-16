"""Real public verifier, durable membership and existing artifact store boundary."""

from __future__ import annotations

import base64
import copy
import json

import pytest
from agent_evaluation_fixture import evidence
from test_hub_member_api import api as api
from test_hub_member_api import campaign as campaign
from test_hub_member_api import signed as signed

from spireagent.hub.live_evaluations import LiveEvaluations
from spireagent.json_boundary import BoundaryError
from spireagent.live_evaluation import SHARE_SCHEMA, decode_evidence, encoded_evidence


@pytest.fixture
def shared(api, tmp_path):
    router, service, admin, member, _ = api
    directory, expected = evidence(tmp_path / "synthetic")
    body = {
        "schema": SHARE_SCHEMA,
        "device_id": "one",
        "share_authorized": True,
        "expected": expected,
        "files": encoded_evidence(directory, expected),
    }
    return LiveEvaluations(service, router.identity.membership), body, member, service, admin


def test_hub_reverifies_runtime_bytes_and_publishes_once_outside_human_ingest(shared):
    owner, body, member, service, _ = shared
    first = owner.publish(member, body)
    assert owner.publish(member, body) == first
    report = first["report"]
    assert report["event_counts"] == {"stopped": 1}
    assert report["native_outcome_status"] == report["game_outcome"] == "not_measured"
    assert report["native_run_completeness"] == "not_measured"
    assert report["human_origin_verified"] is False
    assert report["scientific_verdict"] == "not_claimed"
    artifact = service.store.get_manifest(first["artifact_id"])
    assert artifact.kind == "live_evaluation" and len(artifact.payloads) == 7
    with service.operations.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM uploads").fetchone()[0] == 0
        assert (
            db.execute(
                "SELECT COUNT(*) FROM events WHERE operation='live_evaluation_shared'"
            ).fetchone()[0]
            == 1
        )


@pytest.mark.parametrize(
    "change", ["consent", "owner", "device_revoked", "member_revoked", "forged_win", "tampered"]
)
def test_rejects_unauthorized_or_unverifiable_publication(shared, change):
    owner, body, member, service, admin = shared
    if change == "consent":
        body["share_authorized"] = False
    elif change == "owner":
        member = admin
    elif change == "forged_win":
        body["wins"] = 99
    elif change == "tampered":
        raw = json.loads(base64.b64decode(body["files"]["manifest.json"]))
        raw["tainted"] = True
        body["files"]["manifest.json"] = base64.b64encode(json.dumps(raw).encode()).decode()
    else:
        with service.operations.transaction() as db:
            if change == "device_revoked":
                db.execute("UPDATE devices SET active=0 WHERE id='one'")
            else:
                db.execute(
                    "UPDATE identity_members SET status='disabled' WHERE subject=?",
                    (member.subject,),
                )
    with pytest.raises(BoundaryError):
        owner.publish(member, body)
    with service.operations.transaction() as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM events WHERE operation='live_evaluation_shared'"
            ).fetchone()[0]
            == 0
        )


def test_revocation_during_verification_prevents_manifest_publication(shared, monkeypatch):
    import spireagent.hub.live_evaluations as module

    owner, body, member, service, _ = shared
    verify = module.verified_report

    def revoke_then_verify(*args):
        result = verify(*args)
        with service.operations.transaction() as db:
            db.execute("UPDATE devices SET active=0 WHERE id='one'")
        return result

    monkeypatch.setattr(module, "verified_report", revoke_then_verify)
    with pytest.raises(BoundaryError, match="owned_active_device_required"):
        owner.publish(member, body)


def test_wire_cannot_choose_paths_or_exceed_bound(shared, tmp_path, monkeypatch):
    import spireagent.live_evaluation as module

    _, body, _, _, _ = shared
    altered = copy.deepcopy(body["files"])
    altered["../outside"] = ""
    target = tmp_path / "decoded"
    target.mkdir()
    with pytest.raises(BoundaryError, match="missing_or_unknown_fields"):
        decode_evidence(altered, target)
    monkeypatch.setattr(module, "MAX_EVIDENCE_BYTES", 8)
    with pytest.raises(BoundaryError, match="exceeds_16_mib"):
        decode_evidence(body["files"], target)
    body["files"]["adapter-attestation.json"] = "!invalid"
    with pytest.raises(BoundaryError, match="invalid_evidence_encoding"):
        decode_evidence(body["files"], target)
