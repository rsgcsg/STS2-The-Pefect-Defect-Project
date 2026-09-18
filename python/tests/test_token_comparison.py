"""Completed-run comparison rejects mismatched cohorts and misleading row inventories."""
import io
import json
from dataclasses import replace

import pytest
from test_stage1a_training import tiny_config, token_inputs

from spireagent.artifact_contracts import Parent
from spireagent.json_boundary import BoundaryError, json_bytes
from spireagent.storage.run_reporter import ObjectStoreRunReporter
from stpd.fullrun.token_comparison import compare_token_results
from stpd.workers.token_worker import execute_tokens, prepare_token_run


@pytest.fixture
def completed_pair(tmp_path):
    owner, inputs = token_inputs(tmp_path)
    results = []
    for recipe in ("stage1a.dsimple.s.v1", "stage1a.b.s.v1"):
        config = replace(tiny_config(recipe), steps=1)
        run = prepare_token_run(owner.store, inputs, config, owner.producer)
        reporter = ObjectStoreRunReporter(owner.store, owner.store.blobs)
        outcome = execute_tokens(owner.store, reporter, run.artifact_id, owner.producer)
        results.append(outcome.result_id)
    return owner.store, results


def test_comparison_aligns_completed_configs_and_rejects_duplicate_results(completed_pair):
    store, results = completed_pair
    comparison = compare_token_results(store, results)
    left, right = comparison["models"]
    assert left["config"]["recipe"] != right["config"]["recipe"]
    assert left["decision_count"] == right["decision_count"] == 1
    assert left["independent_runs"] == right["independent_runs"] == 1
    assert comparison["paired_delta_from_first"][0]["top1"] == (
        right["decision_weighted"]["top1"] - left["decision_weighted"]["top1"])
    with pytest.raises(BoundaryError, match="distinct_completed"):
        compare_token_results(store, [results[0], results[0]])


@pytest.mark.parametrize("damage", ["duplicate", "omit", "split", "view", "negative"])
def test_comparison_rejects_corrupt_or_different_report(completed_pair, damage):
    store, results = completed_pair
    result = store.get_manifest(results[1])
    report = store.get_manifest(result.parent("offline_evaluation"))
    metrics = json.loads(b"".join(store.read_payload(report.payload("metrics"))))
    if damage == "duplicate":
        metrics["rows"] *= 2
    elif damage == "omit":
        metrics["rows"] = []
    elif damage == "split":
        metrics["rows"][0]["split"] = "train"
    elif damage == "negative":
        metrics["rows"][0]["nll"] = -1
    if damage == "view":
        report = replace(report, parents=tuple(
            Parent(p.role, result.parent("training_input")) if p.role == "model_view" else p
            for p in report.parents))
    else:
        payload = store.put_payload("metrics", io.BytesIO(json_bytes(metrics)), "application/json")
        report = replace(report, payloads=(payload,))
    store.publish(report)
    changed = replace(result, parents=tuple(
        Parent(p.role, report.artifact_id) if p.role == "offline_evaluation" else p
        for p in result.parents))
    store.publish(changed)
    with pytest.raises(BoundaryError, match="token_comparison"):
        compare_token_results(store, [results[0], changed.artifact_id])
