"""Compose purpose/quality policy with the existing bounded dataset worker."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from spireagent.artifact_contracts import Manifest, Parent
from spireagent.hub.curation import PURPOSES, CurationLedger
from spireagent.json_boundary import BoundaryError, FrozenObject, digest, object_fields
from stpd.fullrun.contracts import SourceProjection
from stpd.fullrun.curated_dataset import SCHEMA as CURATED_SCHEMA
from stpd.fullrun.curated_dataset import (
    curate,
    load_selection,
    publish_selection,
    selection_annotations,
)
from stpd.fullrun.decision_cache import VerifiedSourceCache
from stpd.fullrun.decision_dataset import SCHEMA, DecisionDataset, SelectionRules
from stpd.fullrun.decision_preview import PreviewCache
from stpd.fullrun.decision_store import Progress, load, materialize_records, preview
from stpd.fullrun.decision_union import UNION_SCHEMA, union_decisions

if TYPE_CHECKING:
    from spireagent.hub.uploads import UploadService


def specification(value: object) -> dict[str, Any]:
    obj = object_fields(value, {"purpose", "paired_training"}, "curation")
    if not isinstance(obj["purpose"], str) or obj["purpose"] not in PURPOSES:
        raise BoundaryError("curation", "invalid_dataset_purpose")
    if obj["paired_training"] is not None:
        digest(obj["paired_training"], "curation.paired_training")
        if obj["purpose"] == "training":
            raise BoundaryError("curation", "training_cannot_pair_itself")
    return obj


class DatasetCuration:
    def __init__(self, service: UploadService, cache: VerifiedSourceCache) -> None:
        self.service, self.cache = service, cache
        self.ledger = CurationLedger(service.operations)

    def load(self, manifest: Manifest) -> DecisionDataset:
        if manifest.parameters.value().get("schema") == CURATED_SCHEMA:
            return load_selection(self.service.store, manifest, cache=self.cache)
        return load(self.service.store, manifest.artifact_id, cache=self.cache)[1]

    def materialize(self, source: Manifest, progress: Progress) -> Manifest:
        from spireagent.hub.curation_access import record_use

        record_use(self.service.operations, self.service.store, source, "download")
        progress("preparing_download", 0, 1)
        dataset = self.load(source)
        records = materialize_records(self.service.store, dataset)
        progress("publishing_dataset", 0, 1)
        record_use(self.service.operations, self.service.store, source, "download")
        result = Manifest(
            "analysis",
            self.service.producer,
            parents=(Parent("dataset", source.artifact_id),),
            payloads=(records, source.payload("selection")),
            parameters=FrozenObject.of(
                {
                    "schema": "stpd/dataset-materialization-v1",
                    "logical_id": dataset.logical_id,
                    "purpose": source.parameters.value()["purpose"],
                    "records": len(dataset.records),
                    "scope": "platform_verified",
                }
            ),
        )
        self.service.store.publish(result)
        return result

    def paired(self, dataset: DecisionDataset, spec: dict[str, Any]) -> dict[str, Any] | None:
        if spec["paired_training"] is None:
            return None
        parent = self.service.store.get_manifest(spec["paired_training"])
        if parent.parameters.value().get("purpose") in {"test", "gold"}:
            raise BoundaryError("curation", "paired_training_required")
        training = self.load(parent)
        # Legacy sets may predate the durable source index. Compare their actual
        # records too, so a missing index never becomes a false isolation PASS.
        from stpd.fullrun.representation import decision_fingerprint

        facts = {decision_fingerprint(record) for record in training.records}
        if any(decision_fingerprint(record) in facts for record in dataset.records):
            raise BoundaryError("curation", "training_test_overlap")
        result = self.ledger.overlap(
            (r.run_id for r in dataset.records), (r.run_id for r in training.records)
        )
        if result["overlap"]:
            raise BoundaryError("curation", "training_test_overlap")
        return result

    def _key(self, sources: tuple[Manifest, ...], request: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": CURATED_SCHEMA,
            "sources": sorted(s.artifact_id for s in sources),
            "rules": request["rules"],
            "curation": request["curation"],
            "merging": "datasets" in request,
        }

    def select(
        self,
        sources: tuple[Manifest, ...],
        request: dict[str, Any],
        progress: Progress,
        *,
        on_projection: Callable[[SourceProjection], None] | None = None,
        reservation: str | None = None,
    ) -> DecisionDataset:
        spec = specification(request["curation"])
        if "datasets" in request:
            purposes = {s.parameters.value().get("purpose", "training") for s in sources}
            if "gold" in purposes and (purposes != {"gold"} or spec["purpose"] != "gold"):
                raise BoundaryError("curation", "gold_merge_requires_only_gold")
            if spec["purpose"] == "gold" and purposes != {"gold"}:
                raise BoundaryError("curation", "gold_merge_requires_only_gold")
            if "test" in purposes and (purposes != {"test"} or spec["purpose"] != "test"):
                raise BoundaryError("curation", "test_merge_requires_only_test")
            base = union_decisions(
                tuple((s.artifact_id, self.load(s)) for s in sources),
                SelectionRules.decode(request["rules"]),
            )
        else:
            identities = {s.payload("archive").sha256: s.artifact_id for s in sources}

            def projected(value: SourceProjection) -> None:
                self.ledger.index_source(identities[value.source_sha256], value)
                if on_projection:
                    on_projection(value)

            base = preview(
                self.service.store,
                sources,
                SelectionRules.decode(request["rules"]),
                cache=self.cache,
                progress=progress,
                on_projection=projected,
            )
        selected = curate(
            base,
            spec["purpose"],
            self.ledger.annotations(
                base.records, runs=(r["run_id"] for r in base.report.value()["runs"])
            ),
        )
        with self.service.operations.transaction() as db:
            related = self.ledger._groups(db, (r.run_id for r in selected.records))
            protected = any(
                purpose == "gold" and claim != reservation
                for claim, (purpose, _) in self.ledger._claims(db, related).items()
            )
            if protected and "datasets" not in request:
                raise BoundaryError(
                    "curation",
                    "gold_requires_gold_merge"
                    if spec["purpose"] == "gold"
                    else "gold_reserved_data",
                )
        self.paired(selected, spec)
        PreviewCache(self.cache).put(self._key(sources, request), selected)
        return selected

    def _prepare_gold(self, progress: Progress) -> None:
        """One-time background reconciliation; never scan/reproject during an HTTP GET."""
        with self.service.operations.transaction() as db:
            receipts = db.execute("SELECT receipt FROM uploads WHERE status='verified'").fetchall()
        for index, row in enumerate(receipts):
            source = self.service.store.get_manifest(json.loads(row[0])["evidence_id"])
            if self.ledger.source_runs(source.artifact_id) is not None:
                continue
            progress("preparing_isolation", index, len(receipts))

            def projected(value: SourceProjection, source_id: str = source.artifact_id) -> None:
                self.ledger.index_source(source_id, value)

            preview(
                self.service.store,
                (source,),
                SelectionRules(),
                cache=self.cache,
                on_projection=projected,
            )
        # Existing immutable datasets cannot silently become unused when the new
        # ledger is introduced. Account for them before accepting any Gold reservation.
        for identity in self.service.store.manifest_ids():
            manifest = self.service.store.get_manifest(identity)
            if manifest.kind != "dataset" or self.ledger.dataset(identity) is not None:
                continue
            schema = manifest.parameters.value().get("schema")
            if schema in {SCHEMA, UNION_SCHEMA, CURATED_SCHEMA}:
                dataset = self.load(manifest)
                purpose = manifest.parameters.value().get("purpose", "training")
                if purpose == "gold":
                    reservation = manifest.parameters.value().get("reservation")
                    if not isinstance(reservation, str):
                        raise BoundaryError("curation", "gold_ledger_recovery_required")
                    with self.service.operations.transaction() as db:
                        held = db.execute(
                            "SELECT purpose FROM curation_claims WHERE id=?", (reservation,)
                        ).fetchone()
                        runs = {
                            r[0]
                            for r in db.execute(
                                "SELECT run FROM curation_claim_runs WHERE claim=?", (reservation,)
                            )
                        }
                    if not held or held[0] != "gold" or runs != {r.run_id for r in dataset.records}:
                        raise BoundaryError("curation", "gold_ledger_recovery_required")
                    self.ledger.bind(reservation, identity)
                    continue
                self.ledger.claim(identity, purpose, (r.run_id for r in dataset.records))
                self.ledger.bind(identity, identity)
            elif schema == "stpd/fullrun-dataset-v1":
                from stpd.fullrun.data import load_dataset

                _, admitted = load_dataset(self.service.store, identity)
                if admitted.records:
                    self.ledger.claim(identity, "training", (r.run_id for r in admitted.records))
                    self.ledger.bind(identity, identity)

    def publish(
        self,
        identity: str,
        sources: tuple[Manifest, ...],
        request: dict[str, Any],
        progress: Progress,
    ) -> Manifest:
        expected = request["expected"]
        dataset = PreviewCache(self.cache).get(self._key(sources, request), expected)
        if dataset is None:
            dataset = self.select(sources, request, progress, reservation=identity)
        if dataset.logical_id != expected:
            raise BoundaryError("curation", "preview_changed")
        # Source cache reuse does not reuse a stale quality or isolation decision.
        old = dataset.report.value()["curation"]["annotations"]
        current = self.ledger.annotations(
            dataset.records, runs=(r["run_id"] for r in dataset.report.value()["runs"])
        )
        if old["items"] != selection_annotations(current)["items"]:
            raise BoundaryError("curation", "quality_annotations_changed")
        spec = specification(request["curation"])
        self.paired(dataset, spec)
        if spec["purpose"] == "gold":
            self._prepare_gold(progress)
        progress("publishing_dataset", 0, 1)
        self.ledger.claim(
            identity,
            spec["purpose"],
            (r.run_id for r in dataset.records),
            gold_parents=self.gold_parents(sources)
            if "datasets" in request and spec["purpose"] == "gold"
            else (),
            require_inventory=True,
            annotation_revision=current["revision"],
        )
        manifest = publish_selection(
            self.service.store,
            sources,
            SelectionRules.decode(request["rules"]),
            self.service.producer,
            dataset,
            merging="datasets" in request,
            expected=expected,
            paired_training=spec["paired_training"],
            reservation=identity,
        )
        self.ledger.bind(identity, manifest.artifact_id)
        return manifest

    def gold_parents(self, sources: tuple[Manifest, ...]) -> tuple[str, ...]:
        from spireagent.hub.access import lineage

        return tuple(
            sorted(
                {
                    item.artifact_id
                    for source in sources
                    for item in lineage(self.service.store, source)
                    if item.parameters.value().get("purpose") == "gold"
                }
            )
        )
