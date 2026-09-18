"""Frozen decision-level allocations and model views, distinct from Full-Run admission.

Only the existing verified decision loader admits rows. This N/M0 path never consumes
successors, outcomes or history as model inputs. Later sequence/target views need their
own dependency-aware admission rather than inheriting this allocation claim.
"""

from __future__ import annotations

import io
from collections import Counter
from dataclasses import asdict, dataclass

from spireagent.artifact_contracts import Manifest, Parent, Producer
from spireagent.json_boundary import (
    BoundaryError,
    FrozenObject,
    decode_json,
    json_bytes,
    object_fields,
)
from spireagent.storage.store import ArtifactStore

from ..canonical import semantic_hash
from .dataset_policy import training_sources
from .decision_dataset import DecisionDataset, _identity
from .decision_spool import SpoolSelection, row_summary
from .decision_store import load
from .representation import FullRunSerializer

ALLOCATION_SCHEMA = "stpd/decision-allocation-v1"
VIEW_SCHEMA = "stpd/decision-model-view-v1"


@dataclass(frozen=True)
class AllocationSpec:
    isolation: str = "run"
    seed: int = 1701
    dev_fraction: float = 0.2
    max_train: int = 100
    max_dev: int = 32

    def __post_init__(self) -> None:
        if self.isolation not in {"run", "decision"}:
            raise BoundaryError("allocation", "unsupported_isolation")
        if type(self.seed) is not int or not 0 <= self.seed < 2**63:
            raise BoundaryError("allocation", "invalid_seed")
        if type(self.dev_fraction) not in {int, float} or not 0 < self.dev_fraction < 1:
            raise BoundaryError("allocation", "invalid_dev_fraction")
        if any(type(n) is not int or not 1 <= n <= 100000 for n in (self.max_train, self.max_dev)):
            raise BoundaryError("allocation", "invalid_sample_limit")

    @classmethod
    def decode(cls, value: object) -> AllocationSpec:
        return cls(**object_fields(value, set(cls.__dataclass_fields__), "allocation.spec"))


def allocate(dataset: DecisionDataset, spec: AllocationSpec) -> dict:
    summaries = (
        dataset.records.summaries()
        if isinstance(dataset.records, SpoolSelection)
        else (row_summary(_identity(r), r) for r in dataset.records)
    )
    rows = {row["id"]: row for row in summaries}
    if not rows:
        raise BoundaryError("allocation", "empty_dataset")
    # Union duplicate visible inputs across runs only for the conservative run protocol.
    parent: dict[str, str] = {}

    def root(key: str) -> str:
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    facts: dict[str, str] = {}
    groups = {}
    for key, record in rows.items():
        group = record["run_id"] if spec.isolation == "run" else key
        root(group)
        if spec.isolation == "run":
            fingerprint = record["fingerprint"]
            previous = facts.setdefault(fingerprint, group)
            a, b = root(previous), root(group)
            parent[max(a, b)] = min(a, b)
        groups[key] = group
    components = sorted(
        {root(g) for g in groups.values()}, key=lambda g: semantic_hash([spec.seed, g])
    )
    if len(components) < 2:
        raise BoundaryError("allocation", "insufficient_independent_components")
    dev_count = min(len(components) - 1, max(1, int(len(components) * spec.dev_fraction)))
    dev = set(components[:dev_count])
    members = []
    counts: Counter[str] = Counter()
    for key in sorted(rows, key=lambda k: semantic_hash([spec.seed, k])):
        record = rows[key]
        split = "dev" if root(groups[key]) in dev else "train"
        if counts[split] >= (spec.max_train if split == "train" else spec.max_dev):
            continue
        members.append(
            {
                "occurrence": key,
                "transition_id": record["transition_id"],
                "source_archive_sha256": record["source"],
                "run_id": record["run_id"],
                "split": split,
            }
        )
        counts[split] += 1
    return {
        "schema": ALLOCATION_SCHEMA,
        "spec": asdict(spec),
        "members": members,
        "counts": dict(counts),
        "available": len(rows),
        "components": len(components),
        "input_dependencies": "current_observation_and_candidates_only",
        "interpretation": "unseen_runs"
        if spec.isolation == "run"
        else "unseen_decisions_may_share_runs",
    }


def publish_allocation(
    store: ArtifactStore, dataset_id: str, spec: AllocationSpec, producer: Producer
) -> Manifest:
    training_sources(store, dataset_id)
    manifest, dataset = load(store, dataset_id)
    if manifest.parameters.value().get("purpose") != "training":
        raise BoundaryError("allocation", "explicit_training_dataset_required")
    value = allocate(dataset, spec)
    payload = store.put_payload("members", io.BytesIO(json_bytes(value)), "application/json")
    result = Manifest(
        "protocol",
        producer,
        (Parent("dataset", dataset_id),),
        (payload,),
        FrozenObject.of(
            {
                "schema": ALLOCATION_SCHEMA,
                "spec": asdict(spec),
                "dataset_logical_id": dataset.logical_id,
                "counts": value["counts"],
                "purpose": "engineering",
            }
        ),
    )
    store.publish(result)
    return result


def load_allocation(store: ArtifactStore, identity: str) -> tuple[Manifest, DecisionDataset, dict]:
    manifest = store.get_manifest(identity)
    info = manifest.parameters.value()
    if (
        manifest.kind != "protocol"
        or info.get("schema") != ALLOCATION_SCHEMA
        or [p.role for p in manifest.parents] != ["dataset"]
        or [p.role for p in manifest.payloads] != ["members"]
    ):
        raise BoundaryError("allocation", "unsupported_contract")
    training_sources(store, identity)
    source, dataset = load(store, manifest.parent("dataset"))
    if source.parameters.value().get("purpose") != "training":
        raise BoundaryError("allocation", "explicit_training_dataset_required")
    payload = manifest.payload("members")
    if payload.size > 64 * 1024**2:
        raise BoundaryError("allocation", "members_size_limit")
    actual = decode_json(b"".join(store.read_payload(payload)))
    expected = allocate(dataset, AllocationSpec.decode(info.get("spec")))
    if (
        actual != expected
        or info.get("dataset_logical_id") != dataset.logical_id
        or info.get("counts") != expected["counts"]
        or info.get("purpose") != "engineering"
    ):
        raise BoundaryError("allocation", "membership_or_identity_mismatch")
    return manifest, dataset, expected


def _samples(dataset: DecisionDataset, allocation: dict, serializer: FullRunSerializer) -> tuple:
    from .features import ModelSample

    members = {m["occurrence"]: m for m in allocation["members"]}
    result = []
    records = (
        (dataset.records.owner[key] for key in sorted(members))
        if isinstance(dataset.records, SpoolSelection)
        else iter(dataset.records)
    )
    for record in records:
        member = members.get(_identity(record))
        if member is None:
            continue
        state, actions = serializer.serialize(record)
        keys = tuple(action.key for action in record.actions)
        result.append(
            ModelSample(
                record.transition_id,
                record.run_id,
                member["split"],
                record.surface,
                record.family,
                state,
                actions,
                keys,
                keys.index(record.chosen_key),
            )
        )
    return tuple(result)


def publish_decision_view(
    store: ArtifactStore, allocation_id: str, serializer: FullRunSerializer, producer: Producer
) -> Manifest:
    allocation, dataset, members = load_allocation(store, allocation_id)
    samples = _samples(dataset, members, serializer)
    payload = store.put_payload(
        "samples",
        io.BytesIO(b"".join(json_bytes(sample.to_dict()) for sample in samples)),
        "application/x-ndjson",
    )
    manifest = Manifest(
        "model_view",
        producer,
        (Parent("allocation", allocation_id), Parent("dataset", allocation.parent("dataset"))),
        (payload,),
        FrozenObject.of(
            {
                "schema": VIEW_SCHEMA,
                "serializer": serializer.identity,
                "scope": "platform_verified",
                "samples": len(samples),
                "dataset_logical_id": dataset.logical_id,
                "purpose": "engineering",
            }
        ),
    )
    store.publish(manifest)
    return manifest


def load_decision_view(store: ArtifactStore, manifest: Manifest) -> tuple:
    info = manifest.parameters.value()
    if (
        manifest.kind != "model_view"
        or info.get("schema") != VIEW_SCHEMA
        or sorted(p.role for p in manifest.parents) != ["allocation", "dataset"]
        or [p.role for p in manifest.payloads] != ["samples"]
    ):
        raise BoundaryError("model_view", "unsupported_contract")
    allocation, dataset, members = load_allocation(store, manifest.parent("allocation"))
    if allocation.parent("dataset") != manifest.parent("dataset"):
        raise BoundaryError("model_view", "allocation_dataset_mismatch")
    identity = info.get("serializer", {})
    if not isinstance(identity, dict):
        raise BoundaryError("model_view", "invalid_serializer")
    serializer = FullRunSerializer(identity.get("profile", ""))
    expected = _samples(dataset, members, serializer)
    encoded = b"".join(json_bytes(sample.to_dict()) for sample in expected)
    payload = manifest.payload("samples")
    if (
        info.get("serializer") != serializer.identity
        or info.get("scope") != "platform_verified"
        or info.get("samples") != len(expected)
        or info.get("purpose") != "engineering"
        or info.get("dataset_logical_id") != dataset.logical_id
        or payload.size != len(encoded)
        or b"".join(store.read_payload(payload)) != encoded
    ):
        raise BoundaryError("model_view", "decision_projection_mismatch")
    return manifest, expected
