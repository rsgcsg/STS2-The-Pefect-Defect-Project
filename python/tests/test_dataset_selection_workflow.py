"""Project source selection and task navigation exercise the actual HTTP owners."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_decision_store import setup
from test_hub_member_data import MEMBER, received

from spireagent.hub.console_routes import ConsoleRoutes
from spireagent.json_boundary import BoundaryError
from stpd.fullrun.decision_dataset import SelectionRules


def test_dates_filter_recording_clock_before_paging_and_include_project_sources(tmp_path: Path):
    owner, original, _, jobs = setup(tmp_path)
    with owner.operations.transaction() as db:
        db.execute("DELETE FROM collection_sharing WHERE upload_id=?", (original,))
    ids = [original]
    ids += [received(owner, f"source-{i}".encode(), number=i+2,
                     content_id=f"{i+2:064x}")[0] for i in range(30)]
    for i, identity in enumerate(ids):
        # All upload clocks are today. The recording dates are intentionally older.
        owner.console_index.collection(identity, 1, {
            "created_at": f"2026-09-{14 if i == 0 else 15:02d}T23:30:00+10:00",
            "counts": {"canonical": 1},
        })
    jobs.collections.set_collection_access(ids[-1], approved=False,
                                          evidence_ref="d" * 64, actor="owner")
    routes = ConsoleRoutes(owner, 0)
    start = datetime(2026, 9, 15, tzinfo=UTC).timestamp()
    query = f"from={start}&to={start+86400}&selectable=true"
    page = routes.read("collections", query + "&limit=25", MEMBER)
    assert page["total"] == 29 and len(page["items"]) == 25 and page["next_offset"] == 25
    all_rows = routes.read("collections", query + "&limit=100", MEMBER)
    assert {r["id"] for r in all_rows["items"]} == set(ids[1:-1])
    assert all(r["dataset_selectable"] for r in all_rows["items"])
    next_day = routes.read("collections", f"from={start+86400}&selectable=true", MEMBER)
    assert next_day["items"] == []
    for invalid in ["from=NaN", "to=inf", "from=2&to=1", "from=1&from=2", "selectable=yes"]:
        with pytest.raises(BoundaryError, match="invalid_collection_filter"):
            routes.read("collections", invalid, MEMBER)


def test_task_navigation_and_enqueue_do_not_read_object_storage(tmp_path: Path, monkeypatch):
    owner, upload, _, jobs = setup(tmp_path)
    with owner.operations.transaction() as db:
        db.execute("DELETE FROM collection_sharing WHERE upload_id=?", (upload,))
    body = {"uploads": [upload], "name": "one project", "preview_id": None,
            "rules": SelectionRules().to_dict()}
    with monkeypatch.context() as patch:
        patch.setattr(owner.store, "get_manifest",
                      lambda *_: pytest.fail("HTTP fetched object store"))
        created = jobs.create(MEMBER, body)
        assert jobs.read(MEMBER, created["id"])["state"] == "pending"
        assert jobs.list(MEMBER)["items"][0]["id"] == created["id"]
    jobs.run(created["id"])
    assert jobs.read(MEMBER, created["id"])["result"]["selected"] == 6
    # Acceptance is not fabricated by the new cheap HTTP check: worker rechecks bytes.
    with owner.operations.transaction() as db:
        row = db.execute("SELECT receipt FROM uploads WHERE id=?", (upload,)).fetchone()
        receipt = json.loads(row[0])
        receipt["content_id"] = "f" * 64
        db.execute("UPDATE uploads SET receipt=? WHERE id=?", (json.dumps(receipt), upload))
    next_job = jobs.create(MEMBER, body)
    jobs.run(next_job["id"])
    assert jobs.read(MEMBER, next_job["id"])["error"] == "collection_identity_mismatch"


def test_preview_reuses_verified_projection_for_run_coverage(tmp_path: Path, monkeypatch):
    from stpd.fullrun.decision_cache import VerifiedSourceCache
    from stpd.fullrun.run_coverage import summarize_run_coverage

    owner, upload, _, jobs = setup(tmp_path)
    read = owner.store.read_payload
    seen = set()

    def once(payload):
        assert payload.sha256 not in seen, "preview reread an already verified archive"
        seen.add(payload.sha256)
        return read(payload)

    resolve = VerifiedSourceCache.resolve
    projections = []

    def project(cache, raw):
        assert not projections, "preview decoded a second projection for run coverage"
        value = resolve(cache, raw)
        projections.append(value[0])
        return value

    monkeypatch.setattr(owner.store, "read_payload", once)
    monkeypatch.setattr(VerifiedSourceCache, "resolve", project)
    job = jobs.create(MEMBER, {"uploads": [upload], "name": "one traversal", "preview_id": None,
                               "rules": SelectionRules().to_dict()})
    jobs.run(job["id"])
    result = jobs.read(MEMBER, job["id"])
    assert result["state"] == "completed"
    assert result["result"]["selected"] == 6
    assert result["result"]["run_coverage"] == summarize_run_coverage(projections[0])["runs"]
