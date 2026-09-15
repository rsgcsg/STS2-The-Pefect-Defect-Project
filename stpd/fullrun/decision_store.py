"""Immutable decision dataset artifacts; loading reproduces selection from source bytes."""

from __future__ import annotations

import io

from ..artifact_contracts import Manifest, Parent, Producer
from ..canonical import canonical_json
from ..json_boundary import BoundaryError, FrozenObject, decode_json, json_bytes
from ..storage.store import ArtifactStore
from .decision_dataset import SCHEMA, DecisionDataset, SelectionRules, select_decisions
from .platform_bundle3 import MAX_BYTES


def _sources(store: ArtifactStore, sources: tuple[Manifest, ...]) -> tuple[bytes, ...]:
    if not 1 <= len(sources) <= 100:
        raise BoundaryError("decision_dataset", "source_selection_limit")
    result = []
    total = 0
    for source in sources:
        info = source.parameters.value()
        if (
            source.kind != "evidence"
            or info.get("schema") != "stpd/received-bundle-v1"
            or info.get("disposition") != "verified"
        ):
            raise BoundaryError("decision_dataset", "source_not_verified_receipt")
        payload = source.payload("archive")
        total += payload.size
        if payload.size > MAX_BYTES or total > MAX_BYTES:
            raise BoundaryError("decision_dataset", "source_size_limit")
        result.append(b"".join(store.read_payload(payload)))
    return tuple(result)


def preview(
    store: ArtifactStore, sources: tuple[Manifest, ...], rules: SelectionRules
) -> DecisionDataset:
    dataset = select_decisions(_sources(store, sources), rules)
    contracts = dataset.report.value()["source_contracts"]
    for source in sources:
        if (
            contracts[source.payload("archive").sha256]["bundle_content_id"]
            != source.parameters.value()["content_id"]
        ):
            raise BoundaryError("decision_dataset", "received_content_identity_mismatch")
    return dataset


def publish(
    store: ArtifactStore,
    sources: tuple[Manifest, ...],
    rules: SelectionRules,
    producer: Producer,
    expected_preview: str,
) -> Manifest:
    import pyarrow as pa
    import pyarrow.parquet as pq

    dataset = preview(store, sources, rules)
    if dataset.logical_id != expected_preview:
        raise BoundaryError("decision_dataset", "preview_changed")
    if not dataset.records:
        raise BoundaryError("decision_dataset", "empty_selection")
    splits = dataset.report.value()["splits"]
    rows = [
        {
            "transition_id": r.transition_id,
            "run_id": r.run_id,
            "original_sequence": r.source_evidence.value()["action_sequence"],
            "split": splits[r.run_id],
            "record_json": canonical_json(r.to_dict()),
        }
        for r in dataset.records
    ]
    schema = pa.schema(
        [
            ("transition_id", pa.string()),
            ("run_id", pa.string()),
            ("original_sequence", pa.int64()),
            ("split", pa.string()),
            ("record_json", pa.string()),
        ]
    )
    output = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), output, compression="zstd")
    output.seek(0)
    records = store.put_payload("records", output, "application/vnd.apache.parquet")
    report = store.put_payload(
        "selection", io.BytesIO(json_bytes(dataset.report.value())), "application/json"
    )
    unique = {s.artifact_id: s for s in sources}
    manifest = Manifest(
        "dataset",
        producer,
        parents=tuple(Parent("source_" + key, key) for key in sorted(unique)),
        payloads=(records, report),
        parameters=FrozenObject.of(
            {
                "schema": SCHEMA,
                "logical_id": dataset.logical_id,
                "rules": rules.to_dict(),
                "records": len(dataset.records),
                "scope": "platform_verified",
                "split_status": dataset.report.value()["split_status"],
            }
        ),
    )
    store.publish(manifest)
    return manifest


def load(store: ArtifactStore, artifact_id: str) -> tuple[Manifest, DecisionDataset]:
    import pyarrow.parquet as pq

    manifest = store.get_manifest(artifact_id)
    info = manifest.parameters.value()
    if manifest.kind != "dataset" or info.get("schema") != SCHEMA:
        raise BoundaryError("decision_dataset", "unsupported_dataset_schema")
    sources = tuple(store.get_manifest(parent.artifact_id) for parent in manifest.parents)
    dataset = preview(store, sources, SelectionRules.decode(info["rules"]))
    if info.get("logical_id") != dataset.logical_id or info.get("records") != len(dataset.records):
        raise BoundaryError("decision_dataset", "dataset_reprojection_mismatch")
    if sum(p.size for p in manifest.payloads) > MAX_BYTES:
        raise BoundaryError("decision_dataset", "payload_size_limit")
    report = decode_json(b"".join(store.read_payload(manifest.payload("selection"))))
    if report != dataset.report.value():
        raise BoundaryError("decision_dataset", "selection_reprojection_mismatch")
    table = pq.read_table(io.BytesIO(b"".join(store.read_payload(manifest.payload("records")))))
    expected = [
        {
            "transition_id": r.transition_id,
            "run_id": r.run_id,
            "original_sequence": r.source_evidence.value()["action_sequence"],
            "split": report["splits"][r.run_id],
            "record_json": canonical_json(r.to_dict()),
        }
        for r in dataset.records
    ]
    if table.to_pylist() != expected:
        raise BoundaryError("decision_dataset", "records_reprojection_mismatch")
    return manifest, dataset
