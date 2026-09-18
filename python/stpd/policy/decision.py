"""Portable frozen-Qwen ranking artifact, independent of training data and game execution."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import torch

from spireagent.artifact_contracts import Manifest
from spireagent.json_boundary import BoundaryError, json_bytes, object_fields
from spireagent.storage.store import ArtifactStore

from ..contracts import QwenBackend, QwenIdentity
from ..fullrun.contracts import SemanticAction, SemanticState
from ..fullrun.representation import FullRunSerializer
from ..qwen.portable_backend import validate_engineering_identity
from ..workers.contracts import TrainingConfig
from ..workers.ranking import load_head
from ..workers.worker import MODEL_SCHEMA

SCHEMA = "stpd/decision-ranking-export-v1"
MAX_WEIGHTS = 16 * 1024**2


def _check_model(model: Manifest) -> tuple[dict[str, Any], FullRunSerializer]:
    info = model.parameters.value()
    if (
        model.kind != "model"
        or info.get("schema") != MODEL_SCHEMA
        or info.get("head") != "linear"
        or info.get("hidden_size") != 1024
        or info.get("dtype") != "float32"
        or info.get("scope") != "platform_verified"
        or [p.role for p in model.payloads] != ["weights"]
        or model.payload("weights").size > MAX_WEIGHTS
    ):
        raise BoundaryError("decision_policy", "unsupported_s01_model")
    validate_engineering_identity(QwenIdentity(**info["qwen"]))
    serializer = FullRunSerializer(info.get("serializer", {}).get("profile", ""))
    if info.get("serializer") != serializer.identity:
        raise BoundaryError("decision_policy", "serializer_identity_mismatch")
    return info, serializer


def export_model(store: ArtifactStore, model_id: str, destination: Path) -> dict[str, Any]:
    """Export just the small head and its exact contract, never raw training payloads."""
    model = store.get_manifest(model_id)
    info, _ = _check_model(model)
    weights = b"".join(store.read_payload(model.payload("weights")))
    load_head(weights, 1024, TrainingConfig(head=info["head"]))
    envelope = {
        "schema": SCHEMA,
        "model_id": model.artifact_id,
        "model": json.loads(model.to_bytes()),
        "pooling": "masked_mean",
        "graph": "a.joint.linear.v1",
        "qualification": "engineering_only",
    }
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise BoundaryError("decision_policy", "export_destination_exists")
    with tempfile.TemporaryDirectory(dir=destination.parent) as folder:
        stage = Path(folder) / "model"
        stage.mkdir(mode=0o700)
        (stage / "model.json").write_bytes(json_bytes(envelope))
        (stage / "head.safetensors").write_bytes(weights)
        os.rename(stage, destination)
    return {"schema": SCHEMA, "model_id": model_id, "weight_bytes": len(weights)}


class DecisionScorer:
    def __init__(self, directory: Path, backend: QwenBackend) -> None:
        path = directory / "model.json"
        if path.stat().st_size > 1024**2:
            raise BoundaryError("decision_policy", "manifest_size_limit")
        value = object_fields(
            json.loads(path.read_bytes()),
            {"schema", "model_id", "model", "pooling", "graph", "qualification"},
            "decision_policy",
        )
        if (
            value["schema"] != SCHEMA
            or value["pooling"] != "masked_mean"
            or value["graph"] != "a.joint.linear.v1"
            or value["qualification"] != "engineering_only"
        ):
            raise BoundaryError("decision_policy", "unsupported_export")
        self.model = Manifest.from_bytes(json_bytes(value["model"]), value["model_id"])
        info, self.serializer = _check_model(self.model)
        if backend.identity.__dict__ != info["qwen"]:
            raise BoundaryError("decision_policy", "backend_identity_mismatch")
        file = directory / "head.safetensors"
        expected = self.model.payload("weights")
        if file.stat().st_size != expected.size:
            raise BoundaryError("decision_policy", "weights_size_mismatch")
        raw = file.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected.sha256:
            raise BoundaryError("decision_policy", "weights_digest_mismatch")
        self.head = load_head(raw, 1024, TrainingConfig(head="linear"))
        self.backend = backend

    def score(self, state: SemanticState, actions: tuple[SemanticAction, ...]) -> dict[str, float]:
        if not actions or len({action.key for action in actions}) != len(actions):
            raise BoundaryError("decision_policy", "unique_nonempty_candidates_required")
        observation = self.serializer.serialize_state(state)
        texts = [self.serializer.serialize_action(action) for action in actions]
        with torch.no_grad():
            features = self.backend.encode_joint([observation] * len(actions), texts)
            if features.shape != (len(actions), 1024) or not bool(torch.isfinite(features).all()):
                raise BoundaryError("decision_policy", "invalid_features")
            scores = self.head(features.detach().cpu().float()).flatten()
        if not bool(torch.isfinite(scores).all()):
            raise BoundaryError("decision_policy", "non_finite_scores")
        return {a.key: float(v) for a, v in zip(actions, scores, strict=True)}
