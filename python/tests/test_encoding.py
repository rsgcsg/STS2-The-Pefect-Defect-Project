"""Canonical bytes are artifact identity: fast JSON paths must preserve them."""

from collections import UserDict, UserList
from dataclasses import dataclass
from enum import IntEnum, StrEnum

import pytest

from spireagent.encoding import CanonicalizationError, canonical_json


def test_plain_json_and_extended_types_keep_identical_canonical_bytes() -> None:
    class Number(IntEnum):
        ONE = 1

    class Word(StrEnum):
        VALUE = "测试"

    @dataclass
    class Example:
        z: object
        a: object

    plain = {"z": [None, True, 1, 1.25, "测试", {"nested": -0.0}], "a": []}
    extended = Example(
        UserList([None, True, Number.ONE, 1.25, Word.VALUE, UserDict({"nested": -0.0})]), (),
    )
    expected = '{"a":[],"z":[null,true,1,1.25,"测试",{"nested":-0.0}]}'
    assert canonical_json(plain) == canonical_json(extended) == expected


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan"),
                                    {1: "bad key"}, b"bytes", object()])
def test_fast_paths_still_reject_invalid_nested_json(value: object) -> None:
    with pytest.raises(CanonicalizationError):
        canonical_json({"outer": [value]})
