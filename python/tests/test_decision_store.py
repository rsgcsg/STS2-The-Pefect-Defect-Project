from pathlib import Path

import pytest
from platform_bundle3_fixture import bundle3
from platform_bundle3_fixture import load as load_json
from test_hub_console import service
from test_hub_member_data import MEMBER, received

from stpd.fullrun.decision_dataset import SelectionRules
from stpd.fullrun.decision_store import load, preview, publish
from stpd.fullrun.platform_bundle3 import archive_bundle
from stpd.hub.decision_jobs import DecisionJobs
from stpd.json_boundary import BoundaryError


def setup(tmp_path: Path):
    owner = service(tmp_path)
    bundle = bundle3(tmp_path)
    upload, source = received(
        owner,
        archive_bundle(bundle),
        content_id=load_json(bundle / "session-bundle-manifest.json")["bundle_content_id"],
    )
    jobs = DecisionJobs(owner)
    jobs.exports.set_collection_access(upload, approved=True, evidence_ref="c" * 64, actor="test")
    with owner.operations.transaction() as db:
        db.execute(
            "INSERT INTO identity_members(id,email,issuer,subject,role,status,enroll_devices,"
            "device_quota,created_at,updated_at) VALUES(?,?,?,?,?,'active',1,3,0,0)",
            ("e" * 32, "member@example.org", "fixture", MEMBER.subject, "member"),
        )
    return owner, upload, source, jobs


def test_immutable_publication_and_reprojection(tmp_path: Path) -> None:
    owner, _, source, _ = setup(tmp_path)
    rules = SelectionRules()
    selected = preview(owner.store, (source,), rules)
    manifest = publish(owner.store, (source,), rules, owner.producer, selected.logical_id)
    assert load(owner.store, manifest.artifact_id)[1] == selected
    with pytest.raises(BoundaryError, match="preview_changed"):
        publish(owner.store, (source,), rules, owner.producer, "f" * 64)


def test_preview_then_build_job_and_revocation(tmp_path: Path) -> None:
    owner, upload, _, jobs = setup(tmp_path)
    body = {
        "uploads": [upload],
        "rules": SelectionRules().to_dict(),
        "preview_id": None,
        "name": "fixture",
    }
    first = jobs.create(MEMBER, body)
    assert jobs.pending() == first["id"]
    assert jobs.read(MEMBER, first["id"])["state"] == "pending"
    jobs.run(first["id"])
    completed = jobs.read(MEMBER, first["id"])
    assert completed["state"] == "completed"
    assert completed["result"]["selected"] == 6
    second = jobs.create(MEMBER, {**body, "preview_id": first["id"]})
    jobs.run(second["id"])
    artifact = jobs.read(MEMBER, second["id"])["result"]["artifact_id"]
    assert len(load(owner.store, artifact)[1].records) == 6
    jobs.exports.set_collection_access(upload, approved=False, evidence_ref="d" * 64, actor="test")
    with pytest.raises(BoundaryError, match="collection_not_shared"):
        jobs.read(MEMBER, second["id"])
    with pytest.raises(BoundaryError, match="source_sharing_not_established"):
        jobs.exports._artifact(artifact)


def test_membership_revoked_before_worker_starts(tmp_path: Path) -> None:
    owner, upload, _, jobs = setup(tmp_path)
    job = jobs.create(
        MEMBER,
        {
            "uploads": [upload],
            "rules": SelectionRules().to_dict(),
            "preview_id": None,
            "name": "fixture",
        },
    )
    with owner.operations.transaction() as db:
        db.execute(
            "UPDATE identity_members SET status='disabled' WHERE subject=?", (MEMBER.subject,)
        )
    jobs.run(job["id"])
    assert jobs.read(MEMBER, job["id"])["error"] == "membership_not_authorized"


def test_automatic_profiles_are_background_and_shared(tmp_path: Path) -> None:
    _, upload, _, jobs = setup(tmp_path)
    assert jobs.games(MEMBER)["items"] == []
    identity = jobs.pending()
    assert identity is not None
    jobs.run(identity)
    result = jobs.games(MEMBER)
    assert len(result["items"]) == 3
    assert result["items"][0]["uploads"] == [upload]
    assert jobs.pending() is None
    jobs.exports.set_collection_access(upload, approved=False, evidence_ref="f" * 64, actor="test")
    assert jobs.games(MEMBER)["items"] == []


def test_payload_tamper_cannot_pass_reprojection(tmp_path: Path) -> None:
    import io
    from dataclasses import replace

    from stpd.json_boundary import json_bytes

    owner, _, source, _ = setup(tmp_path)
    rules = SelectionRules()
    selected = preview(owner.store, (source,), rules)
    manifest = publish(owner.store, (source,), rules, owner.producer, selected.logical_id)
    wrong = owner.store.put_payload(
        "selection", io.BytesIO(json_bytes({"selected": 999})), "application/json"
    )
    tampered = replace(manifest, payloads=(manifest.payload("records"), wrong))
    owner.store.publish(tampered)
    with pytest.raises(BoundaryError, match="selection_reprojection_mismatch"):
        load(owner.store, tampered.artifact_id)


def test_concurrent_worker_claim_runs_once(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import patch

    _, upload, _, jobs = setup(tmp_path)
    job = jobs.create(
        MEMBER,
        {
            "uploads": [upload],
            "rules": SelectionRules().to_dict(),
            "preview_id": None,
            "name": "fixture",
        },
    )
    with (
        patch("stpd.hub.decision_jobs.preview", wraps=preview) as call,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        list(pool.map(jobs.run, [job["id"], job["id"]]))
    assert call.call_count == 1
    assert jobs.read(MEMBER, job["id"])["state"] == "completed"


def test_explicit_retry_keeps_failed_attempt(tmp_path: Path) -> None:
    _, upload, _, jobs = setup(tmp_path)
    job = jobs.create(
        MEMBER,
        {
            "uploads": [upload],
            "rules": SelectionRules().to_dict(),
            "preview_id": None,
            "name": "fixture",
        },
    )
    jobs.fail(job["id"], "worker_resource_or_process_limit")
    retry = jobs.retry(MEMBER, job["id"], {})
    assert retry["id"] != job["id"]
    jobs.run(retry["id"])
    assert jobs.read(MEMBER, job["id"])["state"] == "failed"
    assert jobs.read(MEMBER, retry["id"])["state"] == "completed"


def test_new_dataset_statistics_uses_its_own_loader(tmp_path: Path) -> None:
    from stpd.hub.statistics import refresh_decision_statistics

    owner, _, source, _ = setup(tmp_path)
    rules = SelectionRules()
    selected = preview(owner.store, (source,), rules)
    manifest = publish(owner.store, (source,), rules, owner.producer, selected.logical_id)
    result = refresh_decision_statistics(owner, dataset_ids=(manifest.artifact_id,))
    assert result["items"][0]["availability"] == "available"
