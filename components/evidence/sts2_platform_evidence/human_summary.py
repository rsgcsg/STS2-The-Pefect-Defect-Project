"""Safe, non-authorizing summaries of facts already checked by the bundle owner.

Current summaries are materialized during verification from the same loaded
streams. Reading a summary never rescans raw evidence or admits research.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .human_session_bundle import VerifiedHumanSessionBundle

SUMMARY_SCHEMA = "sts2.evidence/human-bundle-summary-1"


def _timestamp(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if parsed.tzinfo is not None else None


def _current_summary(recording: dict[str, Any], trace: list[dict[str, Any]],
                     canonical: list[dict[str, Any]], invalidations: list[dict[str, Any]],
                     journal: list[dict[str, Any]], run_ids: tuple[str, ...]) -> dict[str, Any]:
    """Project verified dispositions, matching CurrentRecordingStore counters.

    Real failures are the unique union of transition_unknown and explicit
    decision_failure identities. Cancel/abort and diagnostic/unsupported are
    independent facts, never guessed from a free-text reason.
    """
    accepted = [event for event in trace if event["kind"] == "action_accepted"]
    kinds = Counter(event["kind"] for event in trace)
    current = recording.get("disposition_schema_version") == 1
    failures = {event["action"]["action_witness_id"] for event in trace
                if event["kind"] == "transition_unknown"}
    failures.update(row["decision_failure"]["decision_witness_id"] for row in invalidations
                    if isinstance(row.get("decision_failure"), dict))
    classified = Counter(row.get("disposition") for row in invalidations)
    child = lambda decision: isinstance(decision, dict) and decision.get("decision_kind") == "nested_selector"
    counts = {
        "accepted": len(accepted), "proved": kinds["transition_proved"],
        "canonical": len(canonical), "real_failures": len(failures) if current else None,
        "cancelled": kinds["action_cancelled_before_start"] + kinds["action_cancelled_after_start"],
        "aborted": kinds["action_aborted_before_commit"],
        "diagnostics": classified["diagnostic"] if current else None,
        "unsupported": classified["unsupported"] if current else None,
        "unresolved": kinds["transition_unknown"], "invalidations": len(invalidations),
        "accepted_children": sum(child(event["action"].get("decision")) for event in accepted),
        "canonical_children": sum(child(row.get("decision")) for row in canonical),
    }
    runs = []
    for run_id in run_ids:
        events = [event for event in journal if event.get("run_id") == run_id]
        starts = [event for event in events if event["kind"] == "run_started_native"]
        ends = [event for event in events if event["kind"] == "run_ended_native"]
        terminal = ends[0] if len(ends) == 1 else None
        # This exact producer string is a typed native bool formatted by the
        # journal owner. Other historical strings stay unknown.
        outcome = {"RunManager.OnEnded(isVictory=true)": "victory",
                   "RunManager.OnEnded(isVictory=false)": "defeat"}.get(
                       None if terminal is None else terminal.get("detail"))
        if outcome == "defeat" and any(
            event["kind"] == "run_abandoned_native"
            and event.get("detail") == "RunManager.OnEnded observed IsAbandoned=true."
            for event in events
        ):
            outcome = "abandoned"
        runs.append({"run_id": run_id,
            "assigned": run_id != "run-unassigned",
            "started_at": _timestamp(starts[0].get("recorded_at")) if len(starts) == 1 else None,
            "ended_at": _timestamp(terminal.get("recorded_at")) if terminal else None,
            "start_observed": bool(starts), "terminal_observed": bool(ends),
            "native_starts": len(starts), "native_ends": len(ends),
            "native_resumes": sum(event["kind"] == "run_resumed_native" for event in events),
            "outcome": outcome})
    # The V3 caller has already required exactly one final session_closed.
    # The durable close-seal timestamp replaces this journal observation when
    # that versioned contract is present; neither is inferred from file mtime.
    return {"created_at": _timestamp(recording.get("created_at")),
        "closed_at": _timestamp(journal[-1].get("recorded_at")),
        "counts": counts, "runs": runs,
        "assigned_run_count": sum(run["assigned"] for run in runs),
        "disposition_status": "current" if current else "historical_unknown",
        "native_starts": sum(run["native_starts"] for run in runs),
        "native_ends": sum(run["native_ends"] for run in runs),
        "recorder_pauses": sum(event["kind"] == "recording_paused" for event in journal)}


def summarize_verified_human_bundle(bundle: VerifiedHumanSessionBundle) -> dict[str, Any]:
    """Return a JSON-safe projection of a successful typed verifier value.

    Call after verification, while its source inventory remains controlled.
    The returned index is rebuildable metadata, not a new evidence artifact.
    V1/V2 remain archival and never receive invented canonical/quality facts.
    """
    from .human_session_bundle import HumanSessionBundle, HumanSessionBundleV2, HumanSessionBundleV3
    if not isinstance(bundle, (HumanSessionBundle, HumanSessionBundleV2, HumanSessionBundleV3)):
        raise TypeError("successful typed Human bundle value required")
    current = isinstance(bundle, HumanSessionBundleV3)
    summary = deepcopy(bundle.summary) if current else {
        "created_at": None, "closed_at": None,
        "disposition_status": "historical_unknown",
        "counts": {name: None for name in ("accepted", "proved", "canonical", "real_failures",
            "cancelled", "aborted", "diagnostics", "unsupported", "unresolved", "accepted_children",
            "canonical_children")},
        "runs": [{"run_id": run_id, "assigned": None, "started_at": None, "ended_at": None,
                  "start_observed": None, "terminal_observed": None, "outcome": None,
                  "native_starts": None, "native_ends": None, "native_resumes": None}
                 for run_id in bundle.run_ids],
        "native_starts": None, "native_ends": None, "recorder_pauses": None, "assigned_run_count": None,
    }
    summary["counts"]["invalidations"] = bundle.invalidations
    packer = bundle.manifest.get("packer", {})
    summary.update(schema=SUMMARY_SCHEMA, availability="available", format="current" if current else "archival",
        session_id=bundle.session_id, timeline_id=getattr(bundle, "timeline_id", None),
        worker_id=bundle.worker_id, campaign_id=bundle.campaign_id, content_id=bundle.bundle_content_id,
        source={"bundle_schema": bundle.manifest["schema"], "bundle_sha256": bundle.bundle_sha256,
            "export_sha256": bundle.export_sha256,
            "packer": {key: packer.get(key) for key in ("product", "version", "source_revision")},
            "verifier": {"type_id": f"human-session-bundle-v{bundle.manifest['schema_version']}",
                         "schema": bundle.manifest["schema"], "version": bundle.manifest["schema_version"]}},
        non_claims=["Human origin", "exhaustive Full-Run coverage", "research admission"])
    return summary
