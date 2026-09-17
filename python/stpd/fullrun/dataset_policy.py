"""Purpose and exact-content checks also enforced by offline research entry points."""

from __future__ import annotations

from collections.abc import Sequence

from spireagent.artifact_contracts import Manifest
from spireagent.json_boundary import BoundaryError
from spireagent.storage.store import ArtifactStore

from .contracts import ResearchTransitionV1


def training_sources(store: ArtifactStore, identity: str) -> tuple[Manifest, ...]:
    """Walk model/checkpoint ancestry too: a wrapper cannot relabel held-out data."""
    pending = [identity]
    found: dict[str, Manifest] = {}
    while pending:
        current = pending.pop()
        if current in found:
            continue
        if len(found) >= 512:
            raise BoundaryError("curation", "lineage_limit")
        item = store.get_manifest(current)
        found[current] = item
        if item.kind == "dataset" and item.parameters.value().get("purpose") in {"test", "gold"}:
            raise BoundaryError("curation", "held_out_data_cannot_train")
        pending.extend(parent.artifact_id for parent in item.parents)
    return tuple(item for item in found.values() if item.kind == "dataset")


def check_dataset_pair(store: ArtifactStore, training: str, test: str) -> dict[str, object]:
    from .curated_dataset import SCHEMA as CURATED_SCHEMA
    from .curated_dataset import load_selection
    from .data import DATASET_SCHEMA, load_dataset
    from .decision_store import load
    from .representation import decision_fingerprint

    def records(identity: str) -> Sequence[ResearchTransitionV1]:
        manifest = store.get_manifest(identity)
        schema = manifest.parameters.value().get("schema")
        if schema == CURATED_SCHEMA:
            return load_selection(store, manifest, cache=None).records
        if schema == DATASET_SCHEMA:
            return load_dataset(store, identity)[1].records
        return load(store, identity)[1].records

    training_sources(store, training)
    left = records(training)
    left_runs = {r.run_id for r in left}
    left_facts = {decision_fingerprint(r) for r in left}
    repeated_runs = set()
    repeated_facts = set()
    for record in records(test):
        if record.run_id in left_runs:
            repeated_runs.add(record.run_id)
        fact = decision_fingerprint(record)
        if fact in left_facts:
            repeated_facts.add(fact)
    if repeated_runs or repeated_facts:
        raise BoundaryError("curation", "training_test_overlap")
    return {"overlap": False, "basis": "whole_run_and_duplicate_decisions"}
