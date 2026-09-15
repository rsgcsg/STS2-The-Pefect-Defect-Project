"""Research model-input safety; stable serialization is shared."""
from typing import Any

from spireagent.encoding import (
    CanonicalizationError as CanonicalizationError,
)
from spireagent.encoding import (
    canonical_json as canonical_json,
)
from spireagent.encoding import (
    semantic_hash as semantic_hash,
)
from spireagent.encoding import (
    to_json_value as to_json_value,
)

_FORBIDDEN_MODEL_KEYS = frozenset(
    {
        "bound_action_id",
        "snapshot_id",
        "mutation_request_id",
        "request_id",
        "runtime_instance_id",
        "process_id",
        "controller_lease_id",
        "native_object_id",
        "native_operand",
        "teacher_identity",
        "model_identity",
        "future_outcome",
        "draw_order",
        "hidden_rng",
    }
)

def reject_model_input_leakage(value: Any, *, path: str = "$") -> None:
    """Fail when authority, runtime identity, hidden state, or labels enter model input."""

    tree = to_json_value(value)
    if isinstance(tree, dict):
        for key, item in tree.items():
            normalized = key.lower()
            if normalized in _FORBIDDEN_MODEL_KEYS or normalized.startswith("native_"):
                raise CanonicalizationError(f"forbidden model-input key at {path}.{key}")
            reject_model_input_leakage(item, path=f"{path}.{key}")
    elif isinstance(tree, list):
        for index, item in enumerate(tree):
            reject_model_input_leakage(item, path=f"{path}[{index}]")
