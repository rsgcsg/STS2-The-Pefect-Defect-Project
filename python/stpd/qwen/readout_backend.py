"""Input-gradient access to the pinned portable Qwen; not a second Qwen load.

The pre-existing feature backend remains inference-only. This interface explicitly
preserves gradients to soft queries while leaving all pretrained parameters frozen.
"""

from __future__ import annotations

from typing import Any

import torch
from torch import Tensor

from ..models.token_core import TokenCore
from .portable_backend import PortableQwenBackend, validate_engineering_identity


class FrozenQwenTokenCore(TokenCore):
    supports_bidirectional = False

    def __init__(self, backend: PortableQwenBackend) -> None:
        super().__init__()
        validate_engineering_identity(backend.identity)
        self.identity = backend.identity
        self.model = backend._base_model
        self.model.eval().requires_grad_(False)
        self.width = backend.hidden_size
        self.vocab_size = int(self.model.config.vocab_size)
        self.max_tokens = backend.pin.l1.hard_limit
        self.frozen = True
        self.eos_token_id = int(backend._tokenizer.eos_token_id)

    def embed_tokens(self, ids: Tensor) -> Tensor:
        self.validate_tokens(ids)
        return self.model.get_input_embeddings()(ids)  # type: ignore[no-any-return]

    def readout_initial(self) -> Tensor:
        embedding = self.model.get_input_embeddings()
        return embedding.weight[self.eos_token_id].detach().clone()  # type: ignore[no-any-return]

    def contextualize(self, embeddings: Tensor, *, causal: bool) -> Tensor:
        if not causal:
            raise ValueError("pinned Qwen requires causal attention")
        if (
            embeddings.ndim != 2 or embeddings.shape[1] != self.width
            or not 0 < embeddings.shape[0] <= self.max_tokens
        ):
            raise ValueError("invalid embedding shape or input token limit")
        length = embeddings.shape[0]
        # Explicit positions reset for every isolated candidate branch.
        result: Any = self.model(
            inputs_embeds=embeddings.unsqueeze(0),
            attention_mask=torch.ones(1, length, device=embeddings.device, dtype=torch.long),
            position_ids=torch.arange(length, device=embeddings.device)[None, :],
            use_cache=False, return_dict=True,
        )
        return result.last_hidden_state[0]  # type: ignore[no-any-return]
