"""Stable JSON encoding; no model or gameplay policy."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any


class CanonicalizationError(ValueError):
    """Raised when a value cannot enter a deterministic research artifact."""

def to_json_value(value: Any) -> Any:
    """Convert supported immutable Python values to a JSON-compatible tree."""

    if is_dataclass(value) and not isinstance(value, type):
        return to_json_value(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        converted: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError("JSON object keys must be strings")
            converted[key] = to_json_value(item)
        return converted
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            raise CanonicalizationError("non-finite floats are not canonical JSON")
        return value
    raise CanonicalizationError(f"unsupported canonical value: {type(value).__name__}")

def canonical_json(value: Any) -> str:
    """Return UTF-8 stable JSON with no insignificant whitespace."""

    return json.dumps(
        to_json_value(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )

def semantic_hash(value: Any) -> str:
    """Hash canonical semantic content without runtime-specific salt."""

    payload = canonical_json(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
