# Local model tasks and explicit shared reports

This is the owning orchestration guide for `workbench.local_models`,
`workbench.native_tasks`, `workbench.evaluation_sharing`, and
`hub.live_evaluations`. Root workflow and existing Policy/Evidence contracts
remain authoritative. This flow does not make arbitrary downloaded checkpoints
executable and does not qualify Human data or model game performance.

## Prepare and load

`LocalModelService.prepare_and_load(selection_id)` accepts only a reviewed registry
selection. It runs existing adapter, artifact, backend and package readiness
checks; missing weights, unsupported hardware or adapter mismatch remain visible.
If the only missing infrastructure is the fixed Runtime package, the existing
hash-pinned Runtime installer prepares it. The existing exact startup and
attestation path then loads the policy in **Human mode**. It never starts a game,
paid compute, training, or an unbounded model download. Inference children set
`HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`; model weights must already exist.
The current S1 adapter's CUDA requirement is unchanged.

This method starts an asynchronous local operation. Existing `status()` reports
`operation.status`, `preparation_stage` and `readiness`. After fixing a displayed
prerequisite, failed preparation can be retried. An active or unresolved Runtime
must first be stopped/recovered before preparing a different one.

## Recorder-to-model handoff

Before `shadow`, `one_step` or `auto`, Workbench reads exact Runtime status and
uses the game Mod's fixed loopback task bridge at `127.0.0.1:15528`:

1. GET `/v1/tasks/status`; match its `runtime_instance_id` to Runtime's environment.
2. If recording is not ready for a model, POST `/v1/tasks/prepare-model` once,
   carrying observed `runtime_instance_id`, `recording_session_id` and a new
   UUID `command_id`. The native Recorder owner closes the actual recording.
3. Continue only with `ready_for_model=true` and consistent `ready`/`closed`
   lifecycle. Recheck Runtime identity before changing its mode.

Bridge schema is `sts2.platform/task-status-1`. Pending/failed Close does not
acquire control. A lost POST response is unknown and is never automatically
retried. Human/Stop recovery does not depend on this bridge. The client bypasses
ambient HTTP proxies and refuses redirects; native server policy owns bridge
request validation.

Human/Stop immediately invalidate earlier control intents. Runtime mutations are
serialized; recovery waits behind an already submitted mutation and is then the
final command. An old Close or mode response cannot subsequently send Auto or
Tick after control was returned. Stop during preparation cancels a late load.

## Finalization without a page request

An independent observer starts after attested Runtime load or explicit recovery.
It observes the exact Runtime's stopped lifecycle, or exit of its locally owned
child process, and runs the existing public `verify_agent_run_evidence` handoff.
It does not send gameplay commands or retry unknown actions. A lost connection
to an unowned/recovered process does not prove termination. Missing, unfinalized
or invalid evidence remains failed. GET status/page reads do not generate reports.

Reports cover bounded Runtime operations. Native victory, complete-run coverage
and autonomous-control coverage remain separate facts. `game_outcome=not_measured`
is not a win, a loss, or an incomplete-game verdict.

## Explicit project sharing

A separate **Share this game-test record** button explains that this finalized
Agent run (model/Runtime identity and recorded observations/actions) will be
shared with approved project members. It calls
`EvaluationSharing.share(evaluation_id, authorized=True)`; Human collection
consent is not reused. This module enables neither automatic sharing nor a
persistent sharing preference. A valid personal member session and owned active
device are required. Account changes before submission cancel it. Logging out
while an already submitted request completes cannot retract submitted bytes;
the exact receipt is retained but hidden from a different session's operation view.

`EvaluationSharing.status()` reports `preparing`, `uploading`, `shared`, `failed`
or `unknown`. Call `close()` on application shutdown. A transport timeout never
causes automatic retry. Explicit retries republish the same immutable content;
Hub deduplicates its manifest and audit event.

The authenticated Hub member write route is
`POST /v1/identity/member/live-evaluations`:

```text
{
  schema: "stpd/agent-evaluation-share-v1",
  device_id: owned active device ID,
  share_authorized: true,
  expected: {
    run_id, manifest_id, policy_manifest_sha256, policy_artifact_sha256,
    runtime_version, runtime_code_sha256
  },
  files: { fixed filename: base64 bytes, ... }
}
```

Exactly six files are accepted: `adapter-attestation.json`, `checksums.sha256`,
`events.jsonl`, `evidence-manifest.json`, `manifest.json`, `policy-manifest.json`.
Decoded evidence is limited to 16 MiB, within the existing 32 MiB HTTP body cap.
Oversize evidence is rejected with a clear error, never truncated. This is a
bounded first sharing path, not streaming arbitrary archives.

`LiveEvaluations(upload_service, identity.membership).publish(principal, body)`
checks current membership/device ownership, decodes only the fixed names and
reruns the public verifier on Hub. It derives counts and report fields rather
than trusting submitted wins. Current authorization is rechecked immediately
before immutable publication. Existing ArtifactStore stores the six payloads
and report as `live_evaluation`; Operations records one `live_evaluation_shared`
event and ConsoleIndex indexes it. Nothing enters Human upload tables, and no
second upload ledger is created.

Response schema is `stpd/shared-evaluation-receipt-v1`: `artifact_id`,
`evidence_content_id`, `status=verified`, and derived `report`. Verified means
**member-submitted Agent evidence integrity and internal consistency**. It does
not independently prove an untrusted member's native gameplay, autonomous victory,
research qualification or Human origin. `native_outcome_status`,
`native_run_completeness` and `game_outcome` remain `not_measured`; scientific and
training admission remain `not_claimed`. Exact Hub producer contributes to the
immutable artifact identity. Local receipts are retained by evaluation ID and
artifact ID, so a future verifier/producer can derive a new report without
overwriting prior receipts.

## Integration and tests

Workbench routes retain local Origin/CSRF protection, strict body shapes and
personal-session checks. Construct one sharing service from existing models and
member client; wire prepare/load to the new method, GET share status and explicit
POST share. Existing catalog/status/command routes remain usable. Hub's member
router retains authentication and browser Origin/CSRF, then delegates publication.
Never put mutations into GET or page rendering.

Focused regressions cover actual verifier bytes, exact native Close binding,
pending/unknown transitions, Human recovery, background finalization, missing
model prerequisites, explicit sharing, member/device revocation including during
verification, invalid bytes/paths/limits, account changes, double clicks, lost
responses and idempotent manual recovery. Portable synthetic tests do not replace
native load, real Human Close or genuine supported-model game operation evidence.
