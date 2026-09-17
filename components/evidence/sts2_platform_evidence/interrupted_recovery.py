"""Independently verify append-only recovery of an immutable interrupted recording."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .human_session_bundle_v1 import BundleVerificationError, _load_json, _semantic_hash

SCHEMA = "sts2.human-annotator/interrupted-recovery-1"
_TERMINALS = {"transition_proved", "transition_unknown", "action_cancelled_before_start",
              "action_cancelled_after_start", "action_aborted_before_commit"}


def _check(condition: bool) -> None:
    if not condition:
        raise BundleVerificationError("recording_recovery_invalid", "recovery provenance or unknown-only closure differs")


def verify_recovery(raw: Path, recording: Mapping[str, Any], journal: list[dict[str, Any]],
                    trace: list[dict[str, Any]]) -> dict[str, Any] | None:
    _check(recording.get("recovery_schema_version") in (None, 1))
    path = raw / "recording-recovery.json"
    marker = any(row.get("kind") == "recording_interrupted" for row in journal) or any(
        row.get("proof_status") == "process_interrupted" for row in trace)
    close_path = raw / "session-close-receipt.json"
    close = _load_json(close_path) if close_path.is_file() else {}
    if not path.is_file():
        _check(not marker and not close.get("recovery"))
        return None
    _check(recording.get("recovery_schema_version") == recording.get("close_schema_version") == 1)
    receipt = dict(_load_json(path))
    inventory = receipt.get("original_files")
    _check(isinstance(inventory, dict) and 0 < len(inventory) <= 50000)
    assert isinstance(inventory, dict)
    identity = _semantic_hash(inventory)
    _check(receipt.get("schema") == SCHEMA and receipt.get("original_inventory_sha256") == identity
           and receipt.get("disposition") == "interrupted_partial" and close.get("recovery") == SCHEMA)
    names = {p.relative_to(raw).as_posix() for p in raw.rglob("*") if p.is_file()}
    names.discard("recording-owner.lock")
    added_names = {"recording-recovery.json", "session-close-receipt.json"}
    _check(not set(inventory) & added_names and names == set(inventory) | added_names)
    suffixes: dict[str, list[dict[str, Any]]] = {}
    total = 0
    for name, original in inventory.items():
        _check(isinstance(name, str) and not Path(name).is_absolute() and ".." not in Path(name).parts
               and "\\" not in name and isinstance(original, dict))
        size = original.get("bytes")
        _check(type(size) is int and size >= 0)
        total += size
        _check(total <= 1024 ** 3)
        source = raw / name
        _check(source.is_file() and not source.is_symlink() and source.stat().st_size >= size)
        digest = hashlib.sha256()
        with source.open("rb") as stream:
            remaining = size
            last = b""
            while remaining:
                chunk = stream.read(min(65536, remaining))
                _check(bool(chunk))
                digest.update(chunk)
                last = chunk[-1:]
                remaining -= len(chunk)
            _check(digest.hexdigest() == original.get("sha256"))
            if name in {"run-journal.jsonl", "semantic-boundary-trace.jsonl"}:
                _check(size == 0 or last == b"\n")
                suffixes[name] = [json.loads(line) for line in stream]
            else:
                _check(stream.read(1) == b"")
    added_trace = suffixes["semantic-boundary-trace.jsonl"]
    original_trace = trace[:len(trace) - len(added_trace)]
    terminals = {e["action"]["action_witness_id"] for e in original_trace if e["kind"] in _TERMINALS}
    pending = {e["action"]["action_witness_id"]: e for e in original_trace
               if e["kind"] == "action_accepted" and e["action"]["action_witness_id"] not in terminals}
    _check(receipt.get("unknowns_added") == len(pending) == len(added_trace)
           and {e["action"]["action_witness_id"] for e in added_trace} == set(pending))
    for event in added_trace:
        original = pending[event["action"]["action_witness_id"]]
        _check(event.get("kind") == "transition_unknown" and event.get("proof_status") == "process_interrupted"
               and all(event.get(key) is None for key in ("boundary", "successor_ref", "native_completion",
                                                        "native_continuation", "native_human_continuation"))
               and all(event.get(key) == original.get(key) for key in ("action", "human_observation_ref",
                       "execution_pre_ref", "execution_semantic_action_space_ref", "related_action_witness_id")))
    added_journal = suffixes["run-journal.jsonl"]
    _check(len(added_journal) == 2 and added_journal[0].get("kind") == "recording_interrupted"
           and added_journal[1].get("kind") == "session_closed"
           and sum(e.get("kind") == "session_closed" for e in journal) == 1
           and added_journal[0].get("detail") == "Offline recovery of immutable source inventory " + identity)
    return receipt
