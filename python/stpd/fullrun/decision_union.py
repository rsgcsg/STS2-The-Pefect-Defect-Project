"""Union of already selected decisions; excluded source rows cannot return through a merge."""

from __future__ import annotations

from collections import Counter
from typing import Any

from spireagent.json_boundary import BoundaryError, FrozenObject

from .data import split_whole_runs
from .decision_dataset import (
    DecisionDataset,
    SelectionRules,
    _facets,
    _fact,
    _identity,
    _merge_environment,
    _metadata,
)
from .decision_spool import DecisionSpool

UNION_SCHEMA = "stpd/decision-union-v1"


def union_decisions(
    parents: tuple[tuple[str, DecisionDataset], ...], rules: SelectionRules,
) -> DecisionDataset:
    """Internal owner composition. Public callers enter through decision_store loaders."""
    if not 1 <= len(parents) <= 100 or len({p[0] for p in parents}) != len(parents):
        raise BoundaryError("decision_union", "invalid_parents")
    records = DecisionSpool()
    facts: dict[str, str] = {}
    environments: dict[str, Any] = {}
    runs: dict[str, Any] = {}
    context: dict[str, Any] = {}
    aliases: dict[str, list[dict[str, str]]] = {}
    parents_by_decision: dict[str, list[str]] = {}
    source_contracts: dict[str, Any] = {}
    invalidations: dict[str, Any] = {}
    summaries = []
    input_count = 0
    for parent_id, dataset in sorted(parents):
        report = dataset.report.value()
        for key, value in report["environments"].items():
            _merge_environment(environments, key, value, boundary="decision_union")
        for key, value in report["source_contracts"].items():
            if key in source_contracts and source_contracts[key] != value:
                raise BoundaryError("decision_union", "source_identity_conflict")
            source_contracts[key] = value
        for item in report["invalidations"]:
            key = item["source_sha256"]
            if key in invalidations and invalidations[key] != item:
                raise BoundaryError("decision_union", "source_identity_conflict")
            invalidations[key] = item
        selected_runs = {r.run_id for r in dataset.records}
        for run in report["runs"]:
            if run["run_id"] not in selected_runs:
                continue
            existing = runs.get(run["run_id"])
            if existing is None:
                runs[run["run_id"]] = run
            elif existing != run:
                known = {r["outcome"] for r in (existing, run) if r["outcome"] != "unknown"}
                if len(known) > 1:
                    raise BoundaryError("decision_union", "run_outcome_conflict")
                variants = existing.get("coverage_variants", [dict(existing)])
                for variant in run.get("coverage_variants", [run]):
                    if variant not in variants:
                        variants.append(variant)
                existing.update(
                    complete=any(v["complete"] for v in variants),
                    outcome=next(iter(known), "unknown"),
                    coverage_variants=variants,
                    coverage_status="overlapping_exports_differ",
                    real_failures=None,
                )
        input_count += len(dataset.records)
        summaries.append({
            "artifact_id": parent_id, "logical_id": dataset.logical_id,
            "rules": report["rules"], "selected": len(dataset.records),
            "exclusion_counts": report["exclusion_counts"],
        })
        for record in dataset.records:
            identity, fact = _identity(record), _fact(record)
            if identity in facts and facts[identity] != fact:
                raise BoundaryError("decision_union", "decision_identity_conflict")
            facts[identity] = fact
            records.setdefault(identity, record)
            context.setdefault(identity, report["context"][identity])
            parents_by_decision.setdefault(identity, []).append(parent_id)
            identities = aliases.setdefault(identity, [])
            for alias in report["aliases"][identity]:
                if alias not in identities:
                    identities.append(alias)
    excluded = []
    for identity in records:
        record = records[identity]
        run = runs[record.run_id]
        metadata = _metadata(record, environments)
        reason = None
        if rules.complete_only and not run["complete"]:
            reason = "incomplete_run"
        elif rules.wins_only and run["outcome"] != "win":
            reason = "outcome_not_win"
        elif rules.no_failures_only and run["real_failures"] != 0:
            reason = "recording_failures_or_unknown"
        else:
            for key, values in sorted(rules.filters.value().items()):
                if metadata[key] not in values:
                    reason = "filter_" + key
                    break
        if reason:
            excluded.append({"decision_id": identity, "reason": reason})
        else:
            records.select(identity)
    chosen = records.selected()
    try:
        splits = split_whole_runs(chosen, rules.seed).value()
        split_status = "assigned"
    except BoundaryError as error:
        if error.code != "insufficient_independent_run_components":
            raise
        splits = {r.run_id: "unassigned" for r in chosen}
        split_status = error.code
    report = {
        "schema": UNION_SCHEMA, "rules": rules.to_dict(),
        "parent_selections": summaries, "parents_by_decision": parents_by_decision,
        "input_selected": input_count, "unique_decisions": len(records),
        "sources": sorted(source_contracts), "source_contracts": source_contracts,
        "environments": environments, "runs": [runs[k] for k in sorted(runs)],
        "selected": len(chosen), "selected_facets": _facets(chosen, environments),
        "excluded": excluded, "exclusion_counts": dict(Counter(e["reason"] for e in excluded)),
        "aliases": aliases, "context": context, "splits": splits, "split_status": split_status,
        "invalidations": [invalidations[k] for k in sorted(invalidations)],
        "exact_duplicate_decisions": input_count - len(records),
        "non_claims": ["complete Full Run qualification", "unobserved outcomes",
                       "continuity across excluded decisions", "model game ability",
                       "automatic training compatibility"],
    }
    return DecisionDataset(chosen, FrozenObject.of(report))
