"""Synthetic graph/gradient checks, never pretrained efficacy or native evidence."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
import torch
from torch import nn

from stpd.models.losses import listwise_rank_loss
from stpd.models.stage1a import RECIPES, BTokenScorer, DSimpleTokenScorer, build_scorer
from stpd.models.token_core import ScratchShape, ScratchTokenCore
from stpd.qwen.portable_backend import PortableQwenBackend
from stpd.qwen.readout_backend import FrozenQwenTokenCore


def core(*, frozen=False, max_tokens=64):
    torch.manual_seed(43)
    value = ScratchTokenCore(ScratchShape(
        vocab_size=32, width=16, layers=2, heads=2, feedforward=32,
        dropout=0.1, max_tokens=max_tokens,
    ))
    value.frozen = frozen
    if frozen:
        value.requires_grad_(False).eval()
        value.supports_bidirectional = False
    return value


def sample():
    return torch.tensor([1, 2, 3]), (torch.tensor([4, 5]), torch.tensor([6, 7, 8]))


@pytest.mark.parametrize("recipe", list(RECIPES))
def test_complete_catalog_permutation_and_other_candidate_isolation(recipe):
    recipe_spec = RECIPES[recipe]
    backbone = core(frozen=recipe_spec.backbone == "pf")
    initial = torch.ones(16) if recipe_spec.family == "b" else None
    model = build_scorer(recipe, backbone, readout_initial=initial).eval()
    state, actions = sample()
    original = model(state, actions)
    torch.testing.assert_close(model(state, actions[::-1]), original.flip(0))
    torch.testing.assert_close(model(state, actions[:1])[0], original[0])
    replaced = model(state, (actions[0], torch.tensor([11, 12])))
    torch.testing.assert_close(replaced[0], original[0])
    assert original.shape == (2,) and torch.isfinite(original).all()


@pytest.mark.parametrize("family", ["b", "dsimple"])
@pytest.mark.parametrize("frozen", [False, True])
def test_train_scope_and_real_parameter_updates(family, frozen):
    backbone = core(frozen=frozen)
    model = build_scorer(
        f"stage1a.{family}.{'pf' if frozen else 's'}.v1", backbone,
        readout_initial=torch.randn(16) if family == "b" else None,
    ).train()
    before = {name: p.detach().clone() for name, p in backbone.named_parameters()}
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=0.01)
    state, actions = sample()
    loss = listwise_rank_loss(model(state, actions), 0)
    loss.backward()
    if frozen:
        assert not backbone.training
        assert all(p.grad is None for p in backbone.parameters())
    else:
        assert backbone.training
        assert backbone.embedding.weight.grad.abs().sum() > 0
    if family == "b":
        assert model.readout.grad is not None and model.readout.grad.abs().sum() > 0
    else:
        assert model.transition[0].weight.grad.abs().sum() > 0
    optimizer.step()
    changed = [not torch.equal(before[n], p) for n, p in backbone.named_parameters()]
    assert any(changed) == (not frozen)


def test_d_state_encoded_once_and_cached_vectors_match():
    model = DSimpleTokenScorer(core(frozen=True)).eval()
    state, actions = sample()
    with patch.object(model, "encode", wraps=model.encode) as encode:
        result = model(state, actions)
        assert encode.call_count == 1 + len(actions)
        assert torch.equal(encode.call_args_list[0].args[0], state)
    current = model.encode(state)
    vectors = torch.stack([model.encode(a) for a in actions])
    torch.testing.assert_close(model.score_vectors(current, vectors), result)


def test_b_single_transformer_and_action_order_is_expressible():
    model = BTokenScorer(core()).eval()
    assert sum(isinstance(m, nn.TransformerEncoder) for m in model.modules()) == 1
    state, actions = sample()
    scores = model(state, (actions[0], actions[0].flip(0)))
    assert not torch.allclose(scores[0], scores[1], atol=1e-7, rtol=1e-7)


def test_b_checks_all_lengths_before_backbone_execution():
    model = BTokenScorer(core(max_tokens=6))
    state, actions = sample()  # first branch 6, second 7 including the query
    with patch.object(model.core, "contextualize", wraps=model.core.contextualize) as forward:
        with pytest.raises(ValueError, match="token limit"):
            model(state, actions)
        forward.assert_not_called()


def test_scope_and_malformed_inputs_fail_explicitly():
    with pytest.raises(ValueError, match="scope"):
        build_scorer("stage1a.b.pf.v1", core())
    with pytest.raises(ValueError, match="EOS"):
        BTokenScorer(core(frozen=True))
    model = DSimpleTokenScorer(core())
    state, actions = sample()
    with pytest.raises(ValueError, match="nonempty"):
        model(state, ())
    with pytest.raises(ValueError, match="int64"):
        model(state.float(), actions)
    with pytest.raises(ValueError, match="vocabulary"):
        model(state, (torch.tensor([32]),))
    with pytest.raises(ValueError, match="vectors"):
        model.score_vectors(torch.zeros(16), torch.full((2, 16), float("nan")))


def test_frozen_qwen_input_gradients_on_tiny_real_architecture_without_download():
    from transformers import Qwen3Config, Qwen3Model

    torch.manual_seed(53)
    tiny = Qwen3Model(Qwen3Config(
        vocab_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=2,
        num_attention_heads=2, num_key_value_heads=1, head_dim=8,
        max_position_embeddings=64,
    )).eval().requires_grad_(False)
    # Deliberately synthetic loader double. Production constructor verifies the pin.
    backend = object.__new__(PortableQwenBackend)
    backend._base_model = tiny
    backend.hidden_size = 16
    backend.identity = SimpleNamespace()
    backend.pin = SimpleNamespace(l1=SimpleNamespace(hard_limit=64))
    backend._tokenizer = SimpleNamespace(eos_token_id=1)
    with patch("stpd.qwen.readout_backend.validate_engineering_identity"):
        frozen = FrozenQwenTokenCore(backend)
    model = BTokenScorer(frozen, readout_initial=frozen.readout_initial()).train()
    state, actions = sample()
    listwise_rank_loss(model(state, actions), 1).backward()
    assert model.readout.grad.abs().sum() > 0
    assert all(p.grad is None for p in tiny.parameters())
    assert not tiny.training
    with pytest.raises(ValueError, match="causal"):
        frozen.contextualize(frozen.embed_tokens(state), causal=False)


def test_same_graph_state_dict_roundtrip():
    state, actions = sample()
    model = BTokenScorer(core()).eval()
    restored = BTokenScorer(core()).eval()
    restored.load_state_dict(model.state_dict(), strict=True)
    torch.testing.assert_close(restored(state, actions), model(state, actions), rtol=0, atol=0)
