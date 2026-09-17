"""Synthetic owner-format coverage checks, not native Human qualification."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from platform_bundle3_fixture import bundle3, load, rows, seal, stream, write

from spireagent.json_boundary import BoundaryError, FrozenObject
from stpd.fullrun.decision_dataset import select_decisions
from stpd.fullrun.platform_bundle3 import PlatformBundle3SourceAdapter, archive_bundle
from stpd.fullrun.run_coverage import summarize_run_coverage


def _projection(bundle: Path):
    seal(bundle)
    return PlatformBundle3SourceAdapter().project(archive_bundle(bundle))


def _event(bundle: Path, kind: str, when: str, run_id: str = "run-0001") -> None:
    path = bundle / "raw/run-journal.jsonl"
    journal = rows(path)
    event = {**journal[0], "kind": kind, "recorded_at": when, "run_id": run_id,
             "event_id": "added-" + str(len(journal))}
    journal.insert(-1, event)
    journal.sort(key=lambda item: item["recorded_at"])
    for sequence, item in enumerate(journal, 1):
        item["sequence"] = sequence
    stream(path, journal)
    manifest_path = bundle / "session-bundle-manifest.json"
    manifest = load(manifest_path)
    manifest["run_ids"] = sorted(set(manifest["run_ids"]) | {run_id})
    write(manifest_path, manifest)


@pytest.mark.parametrize(("victory", "outcome"), [(True, "win"), (False, "loss")])
def test_victory_and_defeat_have_the_same_native_coverage(tmp_path, victory, outcome):
    bundle = bundle3(tmp_path, runs=1)
    path = bundle / "raw/run-journal.jsonl"
    journal = rows(path)
    for event in journal:
        if event["kind"] == "run_ended_native":
            event["detail"] = f"RunManager.OnEnded(isVictory={str(victory).lower()})"
    stream(path, journal)
    projection = _projection(bundle)
    original = deepcopy(projection.accounting.value())
    source = archive_bundle(bundle)
    logical = select_decisions((source,)).logical_id
    run = summarize_run_coverage(projection)["runs"][0]
    assert run["native_boundary_complete"] is True
    assert run["recording_continuity"] == "complete"
    assert run["sequence_complete"] is True
    assert run["outcome"] == outcome
    assert projection.accounting.value() == original
    assert select_decisions((source,)).logical_id == logical


def test_abandonment_requires_native_flag_and_keeps_start_end_coverage(tmp_path):
    bundle = bundle3(tmp_path, runs=1)
    path = bundle / "raw/run-journal.jsonl"
    journal = rows(path)
    terminal = next(event for event in journal if event["kind"] == "run_ended_native")
    terminal["detail"] = "RunManager.OnEnded(isVictory=false)"
    journal.insert(journal.index(terminal) + 1, {
        **terminal, "event_id": "abandon-witness", "kind": "run_abandoned_native",
        "detail": "RunManager.OnEnded observed IsAbandoned=true.",
    })
    for index, event in enumerate(journal, 1):
        event["sequence"] = index
    stream(path, journal)
    projection = _projection(bundle)
    coverage = summarize_run_coverage(projection)["runs"][0]
    assert coverage["outcome"] == "abandoned"
    assert coverage["native_boundary_complete"] is True
    selected = select_decisions((archive_bundle(bundle),))
    assert selected.report.value()["runs"][0]["outcome"] == "abandoned"
    from sts2_platform_evidence import summarize_verified_human_bundle, verify_human_session_bundle

    summary = summarize_verified_human_bundle(verify_human_session_bundle(bundle).require_value())
    assert summary["runs"][0]["outcome"] == "abandoned"


def test_native_complete_does_not_invent_a_missing_canonical_successor(tmp_path):
    bundle = bundle3(tmp_path, runs=1)
    raw = bundle / "raw"
    canonical = rows(raw / "canonical-transitions.jsonl")[:-1]
    trace = rows(raw / "semantic-boundary-trace.jsonl")
    trace[-1] = {key: value for key, value in trace[-1].items()
                 if key not in {"execution_pre_ref", "successor_ref"}}
    trace[-1]["kind"] = "transition_unknown"
    stream(raw / "canonical-transitions.jsonl", canonical)
    stream(raw / "semantic-boundary-trace.jsonl", trace)
    for path in (bundle / "session-bundle-manifest.json", bundle / "audit/audit-report.json"):
        value = load(path)
        value["canonical_count"] = len(canonical)
        write(path, value)
    projection = _projection(bundle)
    run = summarize_run_coverage(projection)["runs"][0]
    assert run["native_boundary_complete"] is True
    assert run["recording_continuity"] == "complete"
    assert run["sequence_complete"] is False
    original = select_decisions((archive_bundle(bundle),)).report.value()["runs"][0]
    assert original["complete"] is False
    assert original["real_failures"] == 1


@pytest.mark.parametrize("kind", [
    "recording_paused", "recording_resumed", "run_resumed_native", "run_abandoned",
    "run_reloaded_native", "run_ended_unproved", "run_launched_native_origin_unknown",
])
def test_lifecycle_gap_inside_boundaries_is_not_uninterrupted(tmp_path, kind):
    bundle = bundle3(tmp_path, runs=1)
    _event(bundle, kind, "2026-09-01T00:02:30Z")
    run = summarize_run_coverage(_projection(bundle))["runs"][0]
    assert run["native_boundary_complete"] is True
    assert run["recording_continuity"] == "gap"
    assert run["lifecycle_gaps"] == {kind: 1}


def test_recorder_paused_across_native_start_even_if_tagged_previous_run(tmp_path):
    bundle = bundle3(tmp_path, runs=1)
    _event(bundle, "recording_paused", "2026-09-01T00:00:30Z", "run-unassigned")
    run = summarize_run_coverage(_projection(bundle))["runs"][0]
    assert run["recording_continuity"] == "gap"
    assert run["lifecycle_gaps"] == {"recording_paused": 1}


def test_pause_after_terminal_does_not_change_coverage_or_old_strict_proof(tmp_path):
    bundle = bundle3(tmp_path, runs=1)
    _event(bundle, "recording_paused", "2026-09-01T00:04:00Z")
    projection = _projection(bundle)
    run = summarize_run_coverage(projection)["runs"][0]
    assert run["native_boundary_complete"] is True
    assert run["recording_continuity"] == "complete"
    assert run["lifecycle_gaps"] == {}
    # Historical strict research semantics intentionally remain unchanged.
    assert run["sequence_complete"] is False
    assert not projection.run_proofs.value()


def test_resumed_before_start_and_other_run_reload_do_not_make_current_gap(tmp_path):
    bundle = bundle3(tmp_path, runs=1)
    _event(bundle, "recording_paused", "2026-09-01T00:00:10Z")
    _event(bundle, "recording_resumed", "2026-09-01T00:00:20Z")
    _event(bundle, "run_reloaded_native", "2026-09-01T00:02:30Z", "run-0002")
    run = summarize_run_coverage(_projection(bundle))["runs"][0]
    assert run["recording_continuity"] == "complete"


@pytest.mark.parametrize(("old", "new", "status"), [
    ("run_started_native", "run_resumed_native", "missing_start"),
    ("run_started_native", "run_observed_in_progress", "missing_start"),
    ("run_ended_native", "run_ended_unproved", "missing_end"),
])
def test_poll_resume_or_close_cannot_supply_missing_native_boundary(tmp_path, old, new, status):
    bundle = bundle3(tmp_path, runs=1)
    path = bundle / "raw/run-journal.jsonl"
    journal = rows(path)
    for event in journal:
        if event["kind"] == old:
            event["kind"] = new
    stream(path, journal)
    run = summarize_run_coverage(_projection(bundle))["runs"][0]
    assert run["native_boundary_complete"] is False
    assert run["boundary_status"] == status
    assert run["recording_continuity"] == "unknown"


@pytest.mark.parametrize(("change", "status"), [
    ("duplicate_start", "ambiguous"), ("reverse_end", "out_of_order"),
    ("reverse_sequence", "out_of_order"), ("missing_timezone", "unknown"),
])
def test_ambiguous_or_invalid_boundary_metadata_stays_unproved(tmp_path, change, status):
    projection = _projection(bundle3(tmp_path, runs=1))
    accounting = projection.accounting.value()
    journal = accounting["journal"]
    if change == "duplicate_start":
        journal.insert(2, {**journal[1], "event_id": "duplicate-start"})
    elif change == "reverse_end":
        journal[-2]["recorded_at"] = "2026-09-01T00:00:30Z"
    elif change == "reverse_sequence":
        journal[-2]["sequence"] = journal[1]["sequence"] - 1
    else:
        journal[-2]["recorded_at"] = "2026-09-01T00:03:00"
    run = summarize_run_coverage(replace(projection, accounting=FrozenObject.of(accounting)))[
        "runs"
    ][0]
    assert run["boundary_status"] == status
    assert run["native_boundary_complete"] is False
    assert run["recording_continuity"] == "unknown"


def test_coverage_is_available_without_any_canonical_rows_and_not_for_unassigned(tmp_path):
    projection = _projection(bundle3(tmp_path, runs=1))
    projection = replace(projection, transitions=(), run_proofs=FrozenObject())
    result = summarize_run_coverage(projection)
    assert len(result["runs"]) == 1
    assert result["runs"][0]["native_boundary_complete"] is True
    assert result["runs"][0]["sequence_complete"] is False
    assert result["runs"][0]["outcome"] == "unknown"


def test_untrusted_projection_kind_is_not_accepted(tmp_path):
    projection = _projection(bundle3(tmp_path, runs=1))
    with pytest.raises(BoundaryError, match="verified_platform_projection_required"):
        summarize_run_coverage(replace(projection, adapter_id="other"))
