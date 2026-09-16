from pathlib import Path

import pytest
from platform_bundle3_fixture import bundle3
from platform_bundle3_fixture import load as load_json
from test_hub_console import service
from test_hub_member_data import MEMBER, received

from spireagent.hub.decision_jobs import DecisionJobs
from spireagent.json_boundary import BoundaryError
from stpd.fullrun.decision_dataset import SelectionRules
from stpd.fullrun.decision_store import load, preview, publish
from stpd.fullrun.platform_bundle3 import archive_bundle


def setup(tmp_path: Path):
    owner = service(tmp_path)
    bundle = bundle3(tmp_path)
    upload, source = received(
        owner,
        archive_bundle(bundle),
        content_id=load_json(bundle / "session-bundle-manifest.json")["bundle_content_id"],
    )
    jobs = DecisionJobs(owner)
    jobs.collections.set_collection_access(
        upload, approved=True, evidence_ref="c" * 64, actor="test"
    )
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
    jobs.collections.set_collection_access(
        upload, approved=False, evidence_ref="d" * 64, actor="test"
    )
    with pytest.raises(BoundaryError, match="collection_not_shared"):
        jobs.read(MEMBER, second["id"])
    with pytest.raises(BoundaryError, match="source_sharing_not_established"):
        jobs.collections.artifact(artifact)


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
    jobs.collections.set_collection_access(
        upload, approved=False, evidence_ref="f" * 64, actor="test"
    )
    assert jobs.games(MEMBER)["items"] == []


def test_payload_tamper_cannot_pass_reprojection(tmp_path: Path) -> None:
    import io
    from dataclasses import replace

    from spireagent.json_boundary import json_bytes

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
        patch("spireagent.hub.decision_jobs.preview", wraps=preview) as call,
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
    from spireagent.hub.statistics import refresh_decision_statistics

    owner, _, source, _ = setup(tmp_path)
    rules = SelectionRules()
    selected = preview(owner.store, (source,), rules)
    manifest = publish(owner.store, (source,), rules, owner.producer, selected.logical_id)
    result = refresh_decision_statistics(owner, dataset_ids=(manifest.artifact_id,))
    assert result["items"][0]["availability"] == "available"


def test_progress_survives_new_service_and_interruption_requires_explicit_retry(
    tmp_path: Path,
) -> None:
    import json

    owner, upload, _, jobs = setup(tmp_path)
    job = jobs.create(MEMBER, {
        "uploads": [upload], "rules": SelectionRules().to_dict(),
        "preview_id": None, "name": "recoverable observation",
    })
    with owner.operations.transaction() as db:
        db.execute("UPDATE decision_jobs SET state='running',updated=0,result=? WHERE id=?",
                   (json.dumps({"progress": {"phase": "verifying_sources",
                                            "completed": 0, "total": 1}}), job["id"]))
    reopened = DecisionJobs(owner)
    before = reopened.read(MEMBER, job["id"])
    assert before["progress"]["phase"] == "verifying_sources"
    assert before["result"] is None
    reopened.pending()
    after = reopened.read(MEMBER, job["id"])
    assert after["state"] == "failed" and after["error"] == "worker_interrupted"
    assert after["recovery"] == "explicit_retry"
    assert after["progress"] == before["progress"]


def test_all_shared_profile_scope_is_not_recent_hundred_or_upload_count(tmp_path: Path) -> None:
    import json
    import time

    owner, upload, _, jobs = setup(tmp_path)
    identity = jobs.pending()
    jobs.run(identity)
    first = jobs.read(MEMBER, identity)
    report = first["result"]
    with owner.operations.transaction() as db:
        for i in range(2, 107):
            next_upload = f"{i:032x}"
            db.execute(
                "INSERT INTO uploads(id,device,content_id,manifest_sha,intent,status) "
                "VALUES(?,?,?,?,?,'verified')",
                (next_upload, "one", f"{i:064x}", "b" * 64, "{}"),
            )
            db.execute("INSERT INTO collection_sharing VALUES(?,1,?,0)",
                       (next_upload, "c" * 64))
            if i < 106:
                db.execute("INSERT INTO decision_jobs VALUES(?, 'receiver', ?, 'completed', "
                           "?, NULL, ?, ?)",
                           (f"{1000+i:032x}", json.dumps({"uploads": [next_upload]}),
                            json.dumps(report), time.time(), time.time()))
    result = jobs.games(MEMBER)
    assert result["scope"] == "all_available_shared_recording_profiles"
    assert result["shared_recordings"] == 106
    assert result["profiled_recordings"] == 105
    assert result["missing_profiles"] == 1 and result["partial"] is True
    assert len(result["items"]) == 3  # Repeated evidence does not create 315 distinct runs.
    assert all(len(run["uploads"]) == 105 for run in result["items"])


def test_preview_visibility_is_personal_atomic_and_preserves_publication(tmp_path: Path) -> None:
    from dataclasses import replace

    owner, upload, _, jobs = setup(tmp_path)
    body = {"uploads": [upload], "rules": SelectionRules().to_dict(),
            "preview_id": None, "name": "Named defeat dataset"}
    first = jobs.create(MEMBER, body)
    with pytest.raises(BoundaryError, match="active_job_cannot_be_archived"):
        jobs.set_archived(MEMBER, {"ids": [first["id"]], "archived": True})
    jobs.run(first["id"])
    built = jobs.create(MEMBER, {**body, "preview_id": first["id"]})
    jobs.run(built["id"])
    artifact = jobs.read(MEMBER, built["id"])["result"]["artifact_id"]
    other = replace(MEMBER, subject="someone-else", role="admin")
    with pytest.raises(BoundaryError, match="not_found"):
        jobs.set_archived(other, {"ids": [first["id"]], "archived": True})
    with pytest.raises(BoundaryError, match="not_found"):
        jobs.set_archived(MEMBER, {"ids": [first["id"], "f" * 32], "archived": True})
    assert jobs.list(MEMBER)["total"] == 2
    snapshot = jobs.read(MEMBER, first["id"])
    jobs.set_archived(MEMBER, {"ids": [first["id"]], "archived": True})
    reopened = DecisionJobs(owner)
    assert reopened.list(MEMBER)["total"] == 1
    assert reopened.list(MEMBER, archived=True)["items"][0] == snapshot
    assert reopened.read(MEMBER, first["id"]) == snapshot
    assert len(load(owner.store, artifact)[1].records) == 6
    reopened.set_archived(MEMBER, {"ids": [first["id"]], "archived": False})
    assert reopened.list(MEMBER)["total"] == 2
    assert reopened.list(MEMBER, limit=1)["next_offset"] == 1


def test_dataset_catalog_name_search_and_split_survive_legacy_index(tmp_path: Path) -> None:
    import json

    from spireagent.hub.console_routes import ConsoleRoutes

    owner, upload, _, jobs = setup(tmp_path)
    body = {"uploads": [upload], "rules": SelectionRules().to_dict(),
            "preview_id": None, "name": "Failed games collection"}
    first = jobs.create(MEMBER, body)
    jobs.run(first["id"])
    built = jobs.create(MEMBER, {**body, "preview_id": first["id"]})
    jobs.run(built["id"])
    artifact = jobs.read(MEMBER, built["id"])["result"]["artifact_id"]
    with owner.operations.transaction() as db:
        row = db.execute("SELECT summary FROM console_artifacts WHERE artifact_id=?",
                         (artifact,)).fetchone()
        old = json.loads(row[0])
        old["metadata"].pop("split_status", None)
        db.execute("UPDATE console_artifacts SET summary=? WHERE artifact_id=?",
                   (json.dumps(old), artifact))
    routes = ConsoleRoutes(owner, 0)
    found = routes.read("datasets", "q=Failed&limit=1&offset=0", MEMBER)
    assert found["total"] == 1
    assert found["items"][0]["display_name"] == body["name"]
    assert found["items"][0]["metadata"]["split_status"] is not None
    assert routes.read("datasets", "q=missing", MEMBER)["total"] == 0
    assert routes.read("datasets", "q=" + artifact[:12], MEMBER)["total"] == 1
    assert routes.read("datasets", "q=%25", MEMBER)["total"] == 0
    with pytest.raises(BoundaryError, match="invalid_dataset_search"):
        routes.read("datasets", "q=a&q=b", MEMBER)


def test_old_game_profiles_refresh_once_without_rewriting_history(tmp_path: Path) -> None:
    import json

    owner, _, _, jobs = setup(tmp_path)
    old_id = jobs.pending()
    assert old_id is not None
    jobs.run(old_id)
    with owner.operations.transaction() as db:
        row = db.execute("SELECT request,result FROM decision_jobs WHERE id=?",
                         (old_id,)).fetchone()
        request, result = json.loads(row[0]), json.loads(row[1])
        request.pop("profile_schema", None)
        result.pop("run_coverage")
        old_result = json.dumps(result)
        db.execute("UPDATE decision_jobs SET request=?,result=? WHERE id=?",
                   (json.dumps(request), old_result, old_id))
    assert all(r["coverage"] is None for r in jobs.games(MEMBER)["items"])
    refreshed = jobs.pending()
    assert refreshed is not None and refreshed != old_id
    jobs.run(refreshed)
    assert all(r["coverage"] is not None for r in jobs.games(MEMBER)["items"])
    assert jobs.pending() is None
    with owner.operations.transaction() as db:
        saved = db.execute("SELECT result FROM decision_jobs WHERE id=?", (old_id,)).fetchone()
        assert saved[0] == old_result
