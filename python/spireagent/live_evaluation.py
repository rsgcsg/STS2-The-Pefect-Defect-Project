"""Bounded transfer and verified projection of member-submitted Agent evidence.

The Platform verifier owns evidence semantics. This transport never accepts
client-supplied wins, research qualification, or Human-origin declarations.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections import Counter
from pathlib import Path
from typing import Any

from sts2_platform_evidence import verify_agent_run_evidence

from spireagent.json_boundary import BoundaryError, digest, object_fields, text

SHARE_SCHEMA = "stpd/agent-evaluation-share-v1"
REPORT_SCHEMA = "stpd/shared-live-evaluation-v1"
MAX_EVIDENCE_BYTES = 16 * 1024 * 1024
FILES = (
    "adapter-attestation.json",
    "checksums.sha256",
    "events.jsonl",
    "evidence-manifest.json",
    "manifest.json",
    "policy-manifest.json",
)
EXPECTED = {
    "run_id",
    "manifest_id",
    "policy_manifest_sha256",
    "policy_artifact_sha256",
    "runtime_version",
    "runtime_code_sha256",
}


def expected_identity(value: object) -> dict[str, Any]:
    result = object_fields(value, EXPECTED, "evaluation.expected")
    for key in EXPECTED:
        if key.endswith("sha256"):
            digest(result[key], "evaluation." + key)
        else:
            text(result[key], "evaluation." + key, maximum=200)
    return dict(result)


def encoded_evidence(
    directory: Path, expected: object, expected_content_id: str | None = None
) -> dict[str, str]:
    identity = expected_identity(expected)
    if directory.is_symlink() or not directory.is_dir():
        raise BoundaryError("evaluation", "agent_evidence_directory_required")
    total = 0
    encoded = {}
    for name in FILES:
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise BoundaryError("evaluation", "agent_evidence_file_required")
        with path.open("rb") as source:
            content = source.read(MAX_EVIDENCE_BYTES - total + 1)
        total += len(content)
        if total > MAX_EVIDENCE_BYTES:
            raise BoundaryError("evaluation", "agent_evidence_exceeds_16_mib")
        encoded[name] = base64.b64encode(content).decode("ascii")
    report = verified_report(directory, identity)
    if expected_content_id is not None and report["evidence_content_id"] != expected_content_id:
        raise BoundaryError("evaluation", "local_evaluation_content_drift")
    return encoded


def decode_evidence(value: object, directory: Path) -> None:
    fields = object_fields(value, set(FILES), "evaluation.files")
    total = 0
    for name in FILES:
        raw = fields[name]
        if not isinstance(raw, str) or len(raw) > (MAX_EVIDENCE_BYTES + 2) // 3 * 4:
            raise BoundaryError("evaluation", "agent_evidence_exceeds_16_mib")
        try:
            content = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            raise BoundaryError("evaluation", "invalid_evidence_encoding") from None
        total += len(content)
        if total > MAX_EVIDENCE_BYTES:
            raise BoundaryError("evaluation", "agent_evidence_exceeds_16_mib")
        with (directory / name).open("xb") as output:
            output.write(content)


def verified_report(directory: Path, expected: object) -> dict[str, Any]:
    result = verify_agent_run_evidence(directory, expected_identity(expected))
    if result.status != "pass" or result.value is None:
        raise BoundaryError("evaluation", "agent_evidence_verification_failed")
    manifest = result.value.manifest
    counts: Counter[str] = Counter()
    deliveries: Counter[str] = Counter()
    with (directory / "events.jsonl").open(encoding="utf-8") as events:
        for line in events:
            event = json.loads(line)
            counts[event["kind"]] += 1
            if event["kind"] == "receipt":
                deliveries[event["payload"]["receipt"]["delivery"]] += 1
    return {
        "schema": REPORT_SCHEMA,
        "scope": "bounded_runtime_operation",
        "evidence_origin": "member_submitted",
        "verification_scope": "agent_evidence_integrity_and_internal_consistency",
        "evidence_verification": "pass",
        "evidence_content_id": result.value.content_id,
        "run_id": result.value.run_id,
        "model_sha256": manifest["policy_artifact_sha256"],
        "policy_manifest_sha256": manifest["policy_manifest_sha256"],
        "runtime_code_sha256": manifest["runtime_code_sha256"],
        "runtime_status": manifest["status"],
        "tainted": manifest["tainted"],
        "event_count": result.value.event_count,
        "event_counts": dict(counts),
        "delivery_counts": dict(deliveries),
        "game_outcome": "not_measured",
        "native_outcome_status": "not_measured",
        "native_run_completeness": "not_measured",
        "scientific_verdict": "not_claimed",
        "training_admission": "not_claimed",
        "human_origin_verified": False,
    }
