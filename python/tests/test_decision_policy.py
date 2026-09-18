"""Synthetic mechanism checks; the stub is never a real-Qwen qualification run."""

from dataclasses import replace
from pathlib import Path

import pytest
import torch
from test_decision_training import prepared

from spireagent.json_boundary import BoundaryError
from spireagent.storage.run_reporter import ObjectStoreRunReporter
from stpd.contracts import QwenIdentity
from stpd.fullrun.decision_store import load
from stpd.fullrun.decision_training import AllocationSpec, publish_allocation, publish_decision_view
from stpd.fullrun.features import compile_features
from stpd.fullrun.representation import FullRunSerializer
from stpd.policy.decision import DecisionScorer, export_model
from stpd.qwen.fake_backend import DeterministicFakeQwenBackend
from stpd.qwen.l2 import load_l2_pin
from stpd.qwen.portable_backend import PortableQwenBackend, validate_engineering_identity
from stpd.qwen.real_backend import _masked_mean
from stpd.workers.contracts import TrainingConfig, prepare_run, prepare_training_input
from stpd.workers.worker import execute


def identity():
    pin = load_l2_pin()
    return QwenIdentity(
        model_id=pin.model_id,
        model_revision=pin.repo_revision,
        tokenizer_revision=pin.repo_revision,
        dtype="float32",
        device="cpu",
        frozen=True,
        control="pretrained",
        config_sha256=pin.l1.config_sha256,
        tokenizer_sha256=pin.l1.tokenizer_bundle_sha256,
        weights_sha256=pin.weights_sha256,
        attention_implementation="sdpa",
        feature_dtype="float32",
        torch_version=str(torch.__version__),
        transformers_version="test-stub",
    )


def test_portable_identity_does_not_weaken_scientific_cuda_contract():
    value = identity()
    validate_engineering_identity(value)
    with pytest.raises(ValueError):
        value.validate_scientific_v0()
    for wrong in [
        replace(value, weights_sha256="f" * 64),
        replace(value, frozen=False),
        replace(value, dtype="float16"),
        replace(value, control="random"),
    ]:
        with pytest.raises(ValueError):
            validate_engineering_identity(wrong)


def test_portable_pooling_releases_sequence_batches_without_changing_mean(monkeypatch):
    backend = object.__new__(PortableQwenBackend)
    backend.micro_batch_size, backend.device = 1, torch.device("cpu")
    seen = []

    def hidden(texts):
        assert len(texts) == 1
        seen.extend(texts)
        n = len(texts[0])
        h = torch.arange(n * 4, dtype=torch.float32).reshape(1, n, 4)
        return h, torch.ones(1, n, dtype=torch.bool)

    monkeypatch.setattr(backend, "_hidden_chunk", hidden)
    values = backend.encode_joint(["x", "longer"], ["a", "b"])
    expected = torch.cat([_masked_mean(*hidden([t])) for t in ["x\na", "longer\nb"]])
    assert torch.equal(values, expected)
    assert seen[:2] == ["x\na", "longer\nb"]


def test_decision_worker_export_and_new_input_scoring(tmp_path: Path):
    owner, dataset = prepared(tmp_path)
    allocation = publish_allocation(owner.store, dataset, AllocationSpec(), owner.producer)
    view = publish_decision_view(
        owner.store, allocation.artifact_id, FullRunSerializer(), owner.producer
    )
    # This injected deterministic encoder only exercises downstream contracts in tests.
    backend = DeterministicFakeQwenBackend(1024)
    backend.identity = identity()
    features = compile_features(owner.store, view.artifact_id, backend, owner.producer)
    training = prepare_training_input(
        owner.store, features.artifact_id, owner.producer, TrainingConfig(max_steps=3, seed=1701)
    )
    _, run = prepare_run(owner.store, training.artifact_id, owner.producer)
    reporter = ObjectStoreRunReporter(owner.store, owner.store.blobs)
    paused = execute(owner.store, reporter, run.artifact_id, owner.producer, stop_after=1)
    assert paused.state == "paused"
    result = execute(
        owner.store, reporter, run.artifact_id, owner.producer, resume=paused.checkpoint_id
    )
    model_id = owner.store.get_manifest(result.result_id).parent("model")
    directory = tmp_path / "export"
    export_model(owner.store, model_id, directory)
    assert {p.name for p in directory.iterdir()} == {"model.json", "head.safetensors"}
    scorer = DecisionScorer(directory, backend)
    row = load(owner.store, dataset)[1].records[0]
    first = scorer.score(row.state, row.actions)
    assert first == scorer.score(row.state, tuple(reversed(row.actions)))
    assert set(first) == {a.key for a in row.actions}
    with pytest.raises(BoundaryError, match="unique_nonempty"):
        scorer.score(row.state, (row.actions[0], row.actions[0]))
    backend.identity = replace(backend.identity, device="mps")
    with pytest.raises(BoundaryError, match="backend_identity"):
        DecisionScorer(directory, backend)
    backend.identity = identity()
    path = directory / "head.safetensors"
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 1
    path.write_bytes(raw)
    with pytest.raises(BoundaryError, match="weights_digest"):
        DecisionScorer(directory, backend)


def test_all_lengths_checked_before_any_encoder_work(tmp_path: Path):
    owner, dataset = prepared(tmp_path)
    allocation = publish_allocation(owner.store, dataset, AllocationSpec(), owner.producer)
    view = publish_decision_view(
        owner.store, allocation.artifact_id, FullRunSerializer(), owner.producer
    )

    class OverLimit(DeterministicFakeQwenBackend):
        count = 0
        encoded = 0

        def token_lengths(self, texts):
            self.count += 1
            if self.count == 2:
                raise ValueError("input hard limit")
            return [5]

        def encode_joint(self, states, actions):
            self.encoded += 1
            return super().encode_joint(states, actions)

    backend = OverLimit(1024)
    backend.identity = identity()
    with pytest.raises(ValueError, match="input hard limit"):
        compile_features(owner.store, view.artifact_id, backend, owner.producer)
    assert backend.encoded == 0
