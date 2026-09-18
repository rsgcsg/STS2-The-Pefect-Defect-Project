"""Pinned CPU/MPS frozen encoding for engineering deployment, not CUDA L2 qualification.

Tensor/tokenization semantics reuse RealQwenBackend; only loading and runtime identity
are different. The historical scientific-v0 validator remains unchanged.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import cast

import torch

from ..contracts import QwenIdentity
from .l2 import QwenL2Error, inspect_l2_snapshot, load_l2_pin
from .real_backend import RealQwenBackend, _masked_mean


def validate_engineering_identity(identity: QwenIdentity) -> None:
    if identity.device.startswith("cuda:"):
        identity.validate_scientific_v0()
    elif (
        identity.device not in {"cpu", "mps"}
        or identity.dtype != "float32"
        or identity.control != "pretrained"
        or identity.feature_dtype != "float32"
        or identity.attention_implementation != "sdpa"
        or identity.cache_mode != "none"
    ):
        raise QwenL2Error("unsupported portable engineering encoding identity")
    # Reuse exact pretrained/tokenizer/control checks without asserting CUDA execution.
    else:
        replace(identity, device="cuda:0", dtype="bfloat16").validate_scientific_v0()
    pin = load_l2_pin()
    if (
        identity.model_id != pin.model_id
        or identity.model_revision != pin.repo_revision
        or identity.tokenizer_revision != pin.repo_revision
        or identity.weights_sha256 != pin.weights_sha256
        or identity.config_sha256 != pin.l1.config_sha256
        or identity.tokenizer_sha256 != pin.l1.tokenizer_bundle_sha256
    ):
        raise QwenL2Error("portable backend requires the fixed full-weight pin")


class PortableQwenBackend(RealQwenBackend):
    """Reuse frozen encoder operations; never call the scientific CUDA constructor."""

    def __init__(self, snapshot: Path, *, device: str = "cpu", micro_batch_size: int = 1) -> None:
        if (
            device not in {"cpu", "mps"}
            or type(micro_batch_size) is not int
            or micro_batch_size < 1
        ):
            raise QwenL2Error("portable backend requires cpu/mps and a positive micro batch")
        if device == "mps" and not torch.backends.mps.is_available():
            raise QwenL2Error("MPS unavailable; select another backend explicitly")
        import transformers
        from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

        self.pin = load_l2_pin()
        self.artifact = inspect_l2_snapshot(snapshot, self.pin)
        self.snapshot = snapshot.expanduser().resolve()
        self.device = torch.device("mps:0" if device == "mps" else device)
        self.control = "pretrained"
        self.random_seed = None
        self.micro_batch_size = micro_batch_size
        self.feature_dtype = torch.float32
        config = AutoConfig.from_pretrained(str(self.snapshot), local_files_only=True)
        if tuple(config.architectures or ()) != (self.pin.backend.architecture,):
            raise QwenL2Error("portable backbone architecture mismatch")
        tokenizer = AutoTokenizer.from_pretrained(
            str(self.snapshot), local_files_only=True, use_fast=True
        )
        expected_pad = next(
            t.token_id for t in self.pin.l1.special_tokens if "pad_token" in t.roles
        )
        if tokenizer.pad_token_id != expected_pad or tokenizer.eos_token_id != expected_pad:
            raise QwenL2Error("portable tokenizer special token mismatch")
        tokenizer.padding_side = "right"
        started = perf_counter()
        model = AutoModelForCausalLM.from_pretrained(
            str(self.snapshot),
            config=config,
            local_files_only=True,
            dtype=torch.float32,
            attn_implementation="sdpa",
        )
        cast(torch.nn.Module, model).to(self.device).eval().requires_grad_(False)
        if device == "mps":
            torch.mps.synchronize()
        self.load_seconds = perf_counter() - started
        if type(model).__name__ != self.pin.backend.architecture or not hasattr(model, "model"):
            raise QwenL2Error("portable loaded model mismatch")
        if any(
            p.requires_grad or p.device != self.device or p.dtype != torch.float32
            for p in model.parameters()
        ):
            raise QwenL2Error("portable parameter device/dtype/frozen mismatch")
        self._model = model
        self._base_model = model.model
        self._tokenizer = tokenizer
        self._transformers = transformers
        self.hidden_size = int(config.hidden_size)
        self.parameter_count = sum(p.numel() for p in model.parameters())
        self.identity = QwenIdentity(
            model_id=self.pin.model_id,
            model_revision=self.pin.repo_revision,
            tokenizer_revision=self.pin.repo_revision,
            dtype="float32",
            device=device,
            frozen=True,
            control="pretrained",
            config_sha256=self.pin.l1.config_sha256,
            tokenizer_sha256=self.pin.l1.tokenizer_bundle_sha256,
            weights_sha256=self.artifact.weights_sha256,
            attention_implementation="sdpa",
            feature_dtype="float32",
            cache_mode="none",
            torch_version=str(torch.__version__),
            transformers_version=transformers.__version__,
        )
        validate_engineering_identity(self.identity)

    def runtime_summary(self) -> dict:
        return {
            "identity": self.identity.__dict__,
            "artifact": self.artifact.to_dict(),
            "parameter_count": self.parameter_count,
            "hidden_size": self.hidden_size,
            "micro_batch_size": self.micro_batch_size,
            "load_seconds": self.load_seconds,
            "qualification": "portable_engineering_only",
        }

    def encode_joint(self, state_texts: Sequence[str], action_texts: Sequence[str]) -> torch.Tensor:
        """Pool each micro batch before retaining it, bounding live token activations."""
        if not state_texts or len(state_texts) != len(action_texts):
            raise QwenL2Error("joint state/action batches must be non-empty and equally sized")
        pooled = []
        for start in range(0, len(state_texts), self.micro_batch_size):
            pairs = zip(
                state_texts[start : start + self.micro_batch_size],
                action_texts[start : start + self.micro_batch_size],
                strict=True,
            )
            hidden, mask = self._hidden_chunk([f"{state}\n{action}" for state, action in pairs])
            pooled.append(_masked_mean(hidden, mask).cpu())
        return torch.cat(pooled).to(self.device)
