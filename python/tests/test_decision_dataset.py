"""Decision selection is permissive about coverage, never about source authority."""

from pathlib import Path

import pytest
from platform_bundle3_fixture import bundle3, rows, seal, stream

from spireagent.json_boundary import BoundaryError, FrozenObject
from stpd.fullrun.decision_dataset import SelectionRules, select_decisions
from stpd.fullrun.platform_bundle3 import archive_bundle


def test_partial_native_run_keeps_proved_decisions(tmp_path: Path) -> None:
    bundle = bundle3(tmp_path, runs=1)
    journal = bundle / "raw/run-journal.jsonl"
    stream(journal, [e for e in rows(journal) if e["kind"] != "run_started_native"])
    seal(bundle)
    source = archive_bundle(bundle)
    selected = select_decisions((source,))
    assert len(selected.records) == 2
    report = selected.report.value()
    assert report["runs"][0]["complete"] is False
    assert report["runs"][0]["outcome"] == "unknown"
    assert report["split_status"] == "insufficient_independent_run_components"
    assert not select_decisions((source,), SelectionRules(complete_only=True)).records


def test_filter_keeps_parent_context_without_parent_training_row(tmp_path: Path) -> None:
    source = archive_bundle(bundle3(tmp_path))
    selected = select_decisions(
        (source,), SelectionRules(filters=FrozenObject.of({"decision_kind": ["nested_selector"]}))
    )
    assert len(selected.records) == 3
    assert all(r.occurrence.value()["parent_decision_id"] for r in selected.records)
    contexts = selected.report.value()["context"]
    assert sum(bool(c["parents"]) for c in contexts.values()) == 3
    assert selected.report.value()["exclusion_counts"] == {"filter_decision_kind": 3}


def test_duplicate_upload_does_not_increase_decisions(tmp_path: Path) -> None:
    source = archive_bundle(bundle3(tmp_path))
    first = select_decisions((source,))
    second = select_decisions((source, source))
    assert first.logical_id == second.logical_id
    assert len(first.records) == 6


def test_unknown_outcome_is_not_loss_or_win(tmp_path: Path) -> None:
    source = archive_bundle(bundle3(tmp_path))
    assert not select_decisions((source,), SelectionRules(wins_only=True)).records


def test_bad_archive_cannot_be_salvaged_by_permissive_rules() -> None:
    with pytest.raises((BoundaryError, ValueError)):
        select_decisions((b"not an archive",))


def test_unknown_filter_or_schema_rejected() -> None:
    with pytest.raises(BoundaryError):
        SelectionRules(filters=FrozenObject.of({"arbitrary": ["x"]}))
    with pytest.raises(BoundaryError):
        SelectionRules.decode({**SelectionRules().to_dict(), "schema": "future"})


def test_rule_codec_preserves_no_failure_filter() -> None:
    rules = SelectionRules(no_failures_only=True)
    assert SelectionRules.decode(rules.to_dict()) == rules


def test_repacked_same_decisions_keep_aliases_not_extra_rows(tmp_path: Path) -> None:
    import gzip

    first = archive_bundle(bundle3(tmp_path))
    second = gzip.compress(gzip.decompress(first), mtime=123)
    assert first != second
    dataset = select_decisions((first, second))
    assert len(dataset.records) == 6
    assert dataset.report.value()["exact_duplicate_decisions"] == 6
    assert dataset.logical_id == select_decisions((second, first)).logical_id


def test_unknown_loses_only_affected_decision_by_default(tmp_path: Path) -> None:
    from platform_bundle3_fixture import load, write

    bundle = bundle3(tmp_path)
    raw = bundle / "raw"
    canonical = rows(raw / "canonical-transitions.jsonl")[:-1]
    trace = rows(raw / "semantic-boundary-trace.jsonl")
    trace[-1] = {
        key: value
        for key, value in trace[-1].items()
        if key not in {"execution_pre_ref", "successor_ref"}
    }
    trace[-1]["kind"] = "transition_unknown"
    stream(raw / "canonical-transitions.jsonl", canonical)
    stream(raw / "semantic-boundary-trace.jsonl", trace)
    for path in (bundle / "session-bundle-manifest.json", bundle / "audit/audit-report.json"):
        value = load(path)
        value["canonical_count"] = len(canonical)
        write(path, value)
    seal(bundle)
    source = archive_bundle(bundle)
    dataset = select_decisions((source,))
    assert len(dataset.records) == 5
    assert dataset.report.value()["exclusion_counts"] == {"transition_unknown": 1}
    assert sum(r["real_failures"] for r in dataset.report.value()["runs"]) == 1
    filtered = select_decisions((source,), SelectionRules(no_failures_only=True))
    assert len(filtered.records) == 4
