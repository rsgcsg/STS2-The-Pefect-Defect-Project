"""Restart provenance is distinct from exact game/artifact environment identity."""

import hashlib
import json
from pathlib import Path

import pytest
from platform_bundle3_fixture import bundle3, load, rows, seal, stream, write
from test_human_annotator import _record

from spireagent.json_boundary import BoundaryError
from stpd.fullrun.decision_dataset import SelectionRules, select_decisions
from stpd.fullrun.platform_bundle3 import archive_bundle


def environment_bundle(tmp_path: Path, runtimes: tuple[str, ...]) -> Path:
    """Owner-format synthetic canonical evidence with matching per-run runtime metadata."""
    bundle = bundle3(tmp_path, runs=len(runtimes))
    raw = bundle / "raw"
    canonical = rows(raw / "canonical-transitions.jsonl")
    trace = rows(raw / "semantic-boundary-trace.jsonl")
    recording = load(raw / "recording-manifest.json")
    replacements = {}
    for index, runtime in enumerate(runtimes):
        run_id = f"run-{index + 1:04}"
        compatibility = []
        for item in canonical:
            if item["run_id"] != run_id:
                continue
            frames = []
            for name in ("pre_state_ref", "successor_ref"):
                old_ref = item[name]
                frame = load(raw / old_ref["object_ref"])
                frame["snapshot"]["session"]["runtime_instance_id"] = runtime
                for read in frame["reads"]:
                    read["runtime_instance_id"] = runtime
                    read["environment_fingerprint"] = "e" * 64
                content = json.dumps(frame, sort_keys=True, separators=(",", ":")).encode()
                digest = hashlib.sha256(content).hexdigest()
                relative = f"semantic-frames/sha256/{digest[:2]}/{digest}.json"
                target = raw / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                replacements[old_ref["object_ref"]] = {
                    **old_ref, "object_ref": relative, "content_sha256": digest,
                }
                frames.append(frame)
            record = _record()
            record.update(
                schema_version=2, schema="sts2.human-annotator/decision-record-2",
                session_id=recording["session_id"], timeline_id=recording["timeline_id"],
                run_id=run_id, record_id=item["transition_id"].removeprefix("canonical-"),
                sequence=item["action_sequence"], decision=item["decision"],
                pre=frames[0], successor=frames[1], action=item["action"],
            )
            record["environment"].update(
                runtime_instance_id=runtime, environment_fingerprint="e" * 64,
            )
            compatibility.append(record)
        stream(raw / f"{run_id}.jsonl", compatibility)

    def replace_refs(value):
        if isinstance(value, dict):
            if value.get("object_ref") in replacements:
                return replacements[value["object_ref"]]
            return {key: replace_refs(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace_refs(item) for item in value]
        return value

    stream(raw / "canonical-transitions.jsonl", replace_refs(canonical))
    stream(raw / "semantic-boundary-trace.jsonl", replace_refs(trace))
    audit = load(bundle / "audit/audit-report.json")
    audit["valid_records"] = len(canonical)
    write(bundle / "audit/audit-report.json", audit)
    seal(bundle)
    return bundle


def test_restart_within_one_verified_archive_keeps_every_runtime(tmp_path: Path) -> None:
    bundle = environment_bundle(tmp_path, ("runtime-2", "runtime-1", "runtime-2"))
    source = archive_bundle(bundle)
    selected = select_decisions((source,))
    assert len(selected.records) == 6
    environment = selected.report.value()["environments"]["e" * 64]
    assert environment["runtime_instance_ids"] == ["runtime-1", "runtime-2"]
    assert "runtime_instance_id" not in environment
    original = rows(bundle / "raw/run-0001.jsonl")[0]["environment"]
    assert {k: v for k, v in environment.items() if k != "runtime_instance_ids"} == {
        k: v for k, v in original.items() if k != "runtime_instance_id"
    }
    assert archive_bundle(bundle) == source  # No raw identity was rewritten by selection.


def test_single_runtime_preserves_legacy_environment_and_logical_id(tmp_path: Path) -> None:
    bundle = environment_bundle(tmp_path, ("runtime-1",))
    selected = select_decisions((archive_bundle(bundle),))
    expected = rows(bundle / "raw/run-0001.jsonl")[0]["environment"]
    assert selected.report.value()["environments"] == {"e" * 64: expected}
    assert selected.logical_id == "3d60f52c206835ec6c61c3e891ca41ae4751dcac17b9af8214411a6200678482"


@pytest.mark.parametrize("field", [
    ("game", "version"), ("game", "main_assembly_sha256"),
    ("connector", "source_digest_sha256"), ("annotator", "sha256"),
    ("player_environment_protocol",), ("modset_fingerprint",), ("extra_identity",),
])
def test_same_fingerprint_non_runtime_conflicts_remain_rejected(tmp_path: Path, field) -> None:
    bundle = environment_bundle(tmp_path, ("runtime-1", "runtime-2"))
    path = bundle / "raw/run-0002.jsonl"
    records = rows(path)
    for record in records:
        value = record["environment"]
        for key in field[:-1]:
            value = value[key]
        value[field[-1]] = "different-exact-identity"
    stream(path, records)
    seal(bundle)
    with pytest.raises(BoundaryError, match="environment_identity_conflict"):
        select_decisions((archive_bundle(bundle),))


def test_cross_source_restart_union_cache_and_publication_reproject(tmp_path: Path) -> None:
    from test_hub_console import service
    from test_hub_member_data import received

    from stpd.fullrun.decision_cache import VerifiedSourceCache
    from stpd.fullrun.decision_store import load as load_dataset
    from stpd.fullrun.decision_store import preview, preview_union, publish, publish_union

    owner = service(tmp_path / "owner")
    parents = []
    sources = []
    rules = SelectionRules()
    # Two repackaged exports share canonical evidence but retain different compatibility
    # record windows. Both go through the installed verifier, received-source store and
    # immutable dataset loader. This exercises inter-source merging without inventing
    # distinct decisions from packaging aliases.
    for index in (0, 1):
        bundle = environment_bundle(tmp_path / str(index), ("runtime-1", "runtime-2"))
        (bundle / f"raw/run-{2 - index:04}.jsonl").unlink()
        audit = load(bundle / "audit/audit-report.json")
        audit["valid_records"] = 2
        write(bundle / "audit/audit-report.json", audit)
        seal(bundle)
        _, source = received(
            owner, archive_bundle(bundle), number=index + 1,
            content_id=load(bundle / "session-bundle-manifest.json")["bundle_content_id"],
        )
        sources.append(source)
        selected = preview(owner.store, (source,), rules)
        assert "runtime_instance_ids" not in selected.report.value()["environments"]["e" * 64]
        parent = publish(owner.store, (source,), rules, owner.producer, selected.logical_id)
        assert load_dataset(owner.store, parent.artifact_id)[1] == selected
        parents.append(parent)
    cache = VerifiedSourceCache(owner.operations.path, "fixture-owner")
    combined = preview(owner.store, tuple(sources), rules, cache=cache)
    assert preview(owner.store, tuple(reversed(sources)), rules, cache=cache) == combined
    assert cache.hits == 2 and cache.misses == 2
    environment = combined.report.value()["environments"]["e" * 64]
    assert environment["runtime_instance_ids"] == ["runtime-1", "runtime-2"]
    assert len(combined.records) == 4
    manifest = publish(owner.store, tuple(sources), rules, owner.producer, combined.logical_id)
    assert load_dataset(owner.store, manifest.artifact_id)[1] == combined
    merged = preview_union(owner.store, tuple(parents), rules, cache=cache)
    assert merged.report.value()["environments"] == combined.report.value()["environments"]
    assert len(merged.records) == 4
    union = publish_union(owner.store, tuple(parents), rules, owner.producer, merged.logical_id)
    assert load_dataset(owner.store, union.artifact_id)[1] == merged
    nested = preview_union(owner.store, (union, parents[0]), rules)
    assert nested.report.value()["environments"] == merged.report.value()["environments"]
    nested_manifest = publish_union(owner.store, (union, parents[0]), rules,
                                    owner.producer, nested.logical_id)
    assert load_dataset(owner.store, nested_manifest.artifact_id)[1] == nested
    # Prior single-runtime artifacts remain reproducible after composing the new format.
    assert load_dataset(owner.store, parents[0].artifact_id)[0] == parents[0]


@pytest.mark.parametrize("bad_runtime", [None, "", 7])
def test_runtime_mismatch_cannot_erase_unknown_provenance(tmp_path: Path, bad_runtime) -> None:
    bundle = environment_bundle(tmp_path, ("runtime-1", "runtime-2"))
    path = bundle / "raw/run-0002.jsonl"
    records = rows(path)
    for record in records:
        record["environment"]["runtime_instance_id"] = bad_runtime
    stream(path, records)
    seal(bundle)
    with pytest.raises(BoundaryError, match="environment_identity_conflict"):
        select_decisions((archive_bundle(bundle),))


def test_union_does_not_merge_conflicting_exact_environment(tmp_path: Path) -> None:
    from dataclasses import replace

    from spireagent.json_boundary import FrozenObject
    from stpd.fullrun.decision_union import union_decisions

    source = archive_bundle(environment_bundle(tmp_path, ("runtime-1",)))
    original = select_decisions((source,))
    report = original.report.value()
    report["environments"]["e" * 64]["connector"]["sha256"] = "f" * 64
    changed = replace(original, report=FrozenObject.of(report))
    with pytest.raises(BoundaryError, match="environment_identity_conflict") as failure:
        union_decisions((("original", original), ("changed", changed)), SelectionRules())
    assert failure.value.stage == "decision_union"
