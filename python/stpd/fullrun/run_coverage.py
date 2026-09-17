"""Display native run coverage without changing immutable research selection.

The input must come from the trusted bundle adapter or its private verified cache.
This is rebuildable metadata: a run can have both native boundaries and recording
failures, while strict sequence proof and research admission remain separate.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from spireagent.json_boundary import BoundaryError

from .contracts import SourceProjection
from .platform_bundle3 import ADAPTER_ID

SCHEMA = "stpd/run-coverage-v1"
_GAPS = frozenset({
    "run_resumed_native", "run_abandoned", "recording_paused", "recording_resumed",
    "run_ended_unproved", "run_reloaded_native", "run_launched_native_origin_unknown",
})
_RECORDING = frozenset({"recording_paused", "recording_resumed"})


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def summarize_run_coverage(projection: SourceProjection) -> dict[str, Any]:
    """Summarize verified journal boundaries; do not verify caller-supplied JSON.

    ``native_boundary_complete`` means exactly one chronologically ordered native
    fresh start and end. ``recording_continuity`` additionally accounts for known
    lifecycle interruptions between them, including a recorder already paused at
    the start. ``complete`` here never means every decision has valid evidence.
    ``sequence_complete`` preserves the adapter's stricter, unchanged run proof.
    """
    if (not isinstance(projection, SourceProjection) or projection.adapter_id != ADAPTER_ID
            or projection.scope != "platform_verified"):
        raise BoundaryError("run_coverage", "verified_platform_projection_required")
    accounting = projection.accounting.value()
    if accounting.get("schema") != "stpd/platform-bundle3-accounting-v1":
        raise BoundaryError("run_coverage", "verified_accounting_required")
    journal = accounting["journal"]
    sessions = {event.get("session_id") for event in journal}
    if len(sessions) != 1 or not isinstance(next(iter(sessions)), str):
        raise BoundaryError("run_coverage", "ambiguous_session")
    session = next(iter(sessions))
    run_ids = {event.get("run_id") for event in journal}
    run_ids.update(item["action"]["run_id"] for item in accounting["occurrences"])
    proofs = projection.run_proofs.value()
    runs = []
    for native_id in sorted(r for r in run_ids if isinstance(r, str) and r != "run-unassigned"):
        events = [event for event in journal if event.get("run_id") == native_id]
        starts = [event for event in events if event["kind"] == "run_started_native"]
        ends = [event for event in events if event["kind"] == "run_ended_native"]
        # Session-only records must not manufacture an observed game.
        if not any(event["kind"].startswith("run_") for event in events) and not any(
            item["action"]["run_id"] == native_id for item in accounting["occurrences"]
        ):
            continue
        start = starts[0] if len(starts) == 1 else None
        end = ends[0] if len(ends) == 1 else None
        start_time = _time(start.get("recorded_at")) if start else None
        end_time = _time(end.get("recorded_at")) if end else None
        if len(starts) > 1 or len(ends) > 1:
            boundary = "ambiguous"
        elif not starts and not ends:
            boundary = "missing_both"
        elif not starts:
            boundary = "missing_start"
        elif not ends:
            boundary = "missing_end"
        elif start_time is None or end_time is None:
            boundary = "unknown"
        elif start_time > end_time or (
            start is not None and end is not None and start["sequence"] >= end["sequence"]
        ):
            boundary = "out_of_order"
        else:
            boundary = "complete"
        gaps: Counter[str] = Counter()
        # An offline seal cannot establish continuous capture up to process loss.
        for event in events:
            if event["kind"] == "recording_interrupted":
                gaps["recording_interrupted"] += 1
        uncertain_gap = False
        if boundary == "complete" and start_time is not None and end_time is not None:
            # Recorder lifecycle is session-wide, even when its event names a
            # preceding run. Native reload/resume facts remain run-scoped.
            before = []
            for event in journal:
                kind = event["kind"]
                if kind not in _GAPS or (
                    kind not in _RECORDING and event.get("run_id") != native_id
                ):
                    continue
                when = _time(event.get("recorded_at"))
                if when is None:
                    uncertain_gap = True
                elif start_time <= when <= end_time:
                    gaps[kind] += 1
                elif kind in _RECORDING and when < start_time:
                    before.append((when, event["sequence"], kind))
            if before and max(before)[2] == "recording_paused":
                gaps["recording_paused"] += 1
        continuity = (
            "gap" if gaps else "complete" if boundary == "complete" and not uncertain_gap
            else "unknown"
        )
        run_id = session + "/" + native_id
        runs.append({
            "run_id": run_id, "session_id": session, "native_run_id": native_id,
            "native_starts": len(starts), "native_ends": len(ends),
            "started_at": start["recorded_at"] if start_time is not None and start else None,
            "ended_at": end["recorded_at"] if end_time is not None and end else None,
            "native_boundary_complete": boundary == "complete", "boundary_status": boundary,
            "recording_continuity": continuity, "lifecycle_gaps": dict(sorted(gaps.items())),
            "sequence_complete": run_id in proofs,
            "outcome": "abandoned" if (
                end and end.get("detail") == "RunManager.OnEnded(isVictory=false)" and any(
                    event["kind"] == "run_abandoned_native"
                    and event.get("detail") == "RunManager.OnEnded observed IsAbandoned=true."
                    for event in events
                )
            ) else {
                "RunManager.OnEnded(isVictory=true)": "win",
                "RunManager.OnEnded(isVictory=false)": "loss",
            }.get(end.get("detail", "") if end else "", "unknown"),
        })
    return {"schema": SCHEMA, "source_sha256": projection.source_sha256, "runs": runs,
            "non_claims": ["all decisions recorded", "strict Full-Run admission", "Human origin"]}
