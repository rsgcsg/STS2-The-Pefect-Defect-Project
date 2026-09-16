"""Selected-set union retains real lineage without reopening excluded source decisions."""

from dataclasses import replace
from pathlib import Path

import pytest
from test_decision_store import setup
from test_hub_member_data import MEMBER

from spireagent.json_boundary import BoundaryError, FrozenObject
from stpd.fullrun.decision_dataset import SelectionRules, _identity
from stpd.fullrun.decision_store import load, preview, preview_union, publish, publish_union
from stpd.fullrun.decision_union import UNION_SCHEMA, union_decisions


def selected(owner, source, rules):
    result = preview(owner.store, (source,), rules)
    return publish(owner.store, (source,), rules, owner.producer, result.logical_id)


def test_union_preserves_selected_set_and_parent_context(tmp_path: Path) -> None:
    owner, _, source, _ = setup(tmp_path)
    a = selected(owner, source, SelectionRules(filters=FrozenObject.of({
        "decision_kind": ["nested_selector"],
    })))
    b = selected(owner, source, SelectionRules(filters=FrozenObject.of({
        "decision_kind": ["nested_selector"],
    }), seed=3))
    merged = preview_union(owner.store, (a, b), SelectionRules())
    assert len(merged.records) == 3  # The three excluded parent actions must not return.
    report = merged.report.value()
    assert report["exact_duplicate_decisions"] == 3
    assert report["input_selected"] == 6
    assert all(report["context"][_identity(r)]["parents"] for r in merged.records)
    assert all(p["exclusion_counts"] == {"filter_decision_kind": 3}
               for p in report["parent_selections"])
    assert merged == preview_union(owner.store, (b, a), SelectionRules())
    manifest = publish_union(owner.store, (a, b), SelectionRules(),
                             owner.producer, merged.logical_id)
    assert manifest.parameters.value()["schema"] == UNION_SCHEMA
    assert {p.artifact_id for p in manifest.parents} == {a.artifact_id, b.artifact_id}
    assert load(owner.store, manifest.artifact_id)[1] == merged
    assert len(load(owner.store, a.artifact_id)[1].records) == 3


def test_union_full_then_filter_and_nested_union(tmp_path: Path) -> None:
    owner, _, source, _ = setup(tmp_path)
    nested = selected(owner, source, SelectionRules(filters=FrozenObject.of({
        "decision_kind": ["nested_selector"],
    })))
    roots = selected(owner, source, SelectionRules(filters=FrozenObject.of({
        "decision_kind": ["root"],
    })))
    first = preview_union(owner.store, (roots, nested), SelectionRules())
    assert len(first.records) == 6
    assert first.report.value()["split_status"] == "assigned"
    manifest = publish_union(owner.store, (roots, nested), SelectionRules(),
                             owner.producer, first.logical_id)
    rules = SelectionRules(filters=FrozenObject.of({"decision_kind": ["root"]}))
    subset = preview_union(owner.store, (manifest, nested), rules)
    assert len(subset.records) == 3
    assert all(r.occurrence.value()["decision_kind"] == "root" for r in subset.records)
    assert subset.report.value()["exact_duplicate_decisions"] == 3
    assert subset.report.value()["exclusion_counts"] == {"filter_decision_kind": 3}
    sealed = publish_union(owner.store, (manifest, nested), rules,
                           owner.producer, subset.logical_id)
    assert load(owner.store, sealed.artifact_id)[1] == subset


def test_union_rejects_duplicate_parent_and_conflicting_fact(tmp_path: Path) -> None:
    owner, _, source, _ = setup(tmp_path)
    dataset = preview(owner.store, (source,), SelectionRules())
    with pytest.raises(BoundaryError, match="invalid_parents"):
        union_decisions((("a", dataset), ("a", dataset)), SelectionRules())
    # This unit exercises a conflicting verified-parent fact, not a raw-import API.
    changed = replace(dataset.records[0], family="conflicting_family")
    other = replace(dataset, records=(changed, *dataset.records[1:]))
    with pytest.raises(BoundaryError, match="decision_identity_conflict"):
        union_decisions((("a", dataset), ("b", other)), SelectionRules())


def test_union_jobs_recheck_ancestor_permission_and_preview(tmp_path: Path) -> None:
    owner, upload, source, jobs = setup(tmp_path)
    a = selected(owner, source, SelectionRules())
    owner.console_index.artifact_closure(owner.store, (a.artifact_id,))
    body = {"datasets": [a.artifact_id], "rules": SelectionRules().to_dict(),
            "preview_id": None, "name": "selected union"}
    job = jobs.create(MEMBER, body)
    jobs.run(job["id"])
    result = jobs.read(MEMBER, job["id"])
    assert result["state"] == "completed" and result["result"]["selected"] == 6
    assert result["progress"]["phase"] == "completed"
    with pytest.raises(BoundaryError, match="preview_mismatch"):
        jobs.create(MEMBER, {**body, "preview_id": job["id"],
                            "rules": SelectionRules(seed=1).to_dict()})
    build = jobs.create(MEMBER, {**body, "preview_id": job["id"]})
    jobs.run(build["id"])
    artifact = jobs.read(MEMBER, build["id"])["result"]["artifact_id"]
    assert len(load(owner.store, artifact)[1].records) == 6
    assert jobs.read(MEMBER, build["id"])["progress"]["cache_hits"] == 1
    jobs.collections.set_collection_access(upload, approved=False,
                                          evidence_ref="d" * 64, actor="test")
    with pytest.raises(BoundaryError, match="source_sharing_not_established"):
        jobs.read(MEMBER, build["id"])


def test_union_statistics_use_verified_union_loader(tmp_path: Path) -> None:
    from spireagent.hub.statistics import refresh_decision_statistics

    owner, _, source, _ = setup(tmp_path)
    parent = selected(owner, source, SelectionRules())
    dataset = preview_union(owner.store, (parent,), SelectionRules())
    manifest = publish_union(owner.store, (parent,), SelectionRules(),
                             owner.producer, dataset.logical_id)
    result = refresh_decision_statistics(owner, dataset_ids=(manifest.artifact_id,))
    assert result["items"][0]["availability"] == "available"


def test_union_cache_cannot_launder_modified_parent_selection(tmp_path: Path) -> None:
    import io

    from spireagent.json_boundary import json_bytes
    from stpd.fullrun.decision_cache import VerifiedSourceCache

    owner, _, source, _ = setup(tmp_path)
    parent = selected(owner, source, SelectionRules())
    cache = VerifiedSourceCache(owner.operations.path, "owner")
    preview_union(owner.store, (parent,), SelectionRules(), cache=cache)
    wrong = owner.store.put_payload("selection", io.BytesIO(json_bytes({"selected": 999})))
    bad_parent = replace(parent, payloads=(parent.payload("records"), wrong))
    owner.store.publish(bad_parent)
    with pytest.raises(BoundaryError, match="selection_reprojection_mismatch"):
        preview_union(owner.store, (bad_parent,), SelectionRules(), cache=cache)
    assert cache.hits == 1  # Cached source cannot replace parent artifact verification.
