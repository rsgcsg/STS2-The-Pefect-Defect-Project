# Closed-session delivery

The Evidence `delivery_cli` is an opt-in developer background service. It
observes successful Recorder Close receipts, never game frames or speculative
successor timing. Recorder, native causal source and the one production Mod are
unchanged. Close does not imply a complete native run or research admission.

## Application status projection

Applications use the public owner API rather than reading the private outbox:

```python
from sts2_platform_evidence import inspect_delivery_status
from sts2_platform_evidence.delivery_config import DeliveryConfig

page = inspect_delivery_status(DeliveryConfig.load(config_path), limit=25, offset=0)
detail = inspect_delivery_status(DeliveryConfig.load(config_path), delivery_id=outbox_id)
```

The equivalent CLI is:

```bash
python -m sts2_platform_evidence.delivery_cli status --summary --config /absolute/delivery.json --limit 25 --offset 0
python -m sts2_platform_evidence.delivery_cli status --summary --config /absolute/delivery.json --delivery-id <64-hex-outbox-id>
```

`delivery-status-2` contains `sessions`, global status `counts`, `total`,
`limit`, `offset`, `next_offset`, global `quality` and the read's `observed_at`.
Pages are bounded to 1–100 records, newest enrolled SQLite row first. A detail
lookup never searches all pages. `quality` contains `summaries_available`,
`summaries_missing`, `canonical`, `real_failures` and `partial`. Totals cover
known owner projections across the entire outbox, not just the page. With no
known counts totals are `null`; missing summaries or historical unknown
dispositions set `partial=true`. A partial zero never establishes no failures
across the complete outbox.

Each row exposes outbox `id`, safe `session_id`, worker/campaign IDs, exact
`content_id`/HTTP `upload_id`, delivery `status`, observed `stage`, attempts,
retry time, safe error category, parsed terminal `receipt` and verified
`summary`. Receipt extensions, free-text findings, local source paths and URLs
are omitted. Receipt finding codes remain diagnostic. No receipt ID is guessed
to be an upload ID. `summary_status=not_materialized` means historical or not
yet verified metadata is unavailable, never that recording failed.

Stages are `queued`, `packing`, `locally_verified`, `awaiting_upload`,
`verification_pending`, `retry_wait`, `auth_blocked`, `verified`, `quarantined`, or `incident`.
Global status counts include `auth_blocked`; it is a delivery credential block,
not a recorded Human decision failure.
They are last observed phases, not worker liveness or byte-percent progress.
In particular a crashed worker can leave `packing` as its last observation.
The application displays worker lifecycle separately. Attempts include receipt
polls. `enrolled_at`, row `observed_at` and `transport_observed_at` are separate
observations; older missing timestamps remain `null`. Merely reading status
does not establish fresh cloud contact or overwrite a terminal receipt.
Persisting the first HTTP upload identity before PUT remains mandatory.
Subsequent responses and intent refreshes cannot replace that durable upload ID.
Refreshing optional phase/time telemetry for the same durable identity is
best-effort: unavailable telemetry retains its old observation and cannot hide
an otherwise valid terminal receipt from the outbox.

New packs persist safe summary metadata and numeric aggregate columns in the
existing outbox transaction. Phase and transport sidecars expose already
observed progress without rescanning source or archives. A missing optional
phase index cannot adjudicate delivery. Old `status`/`inspect_outbox` calls
retain `delivery-status-1` for existing operational consumers; that private
diagnostic view may contain local paths and must not be used for browser UI.

To rebuild summaries for an existing outbox, stop its delivery worker and run:

```bash
python -m sts2_platform_evidence.delivery_cli summarize --config /absolute/delivery.json --limit 25 --offset 0
```

Follow `next_offset` until null, then restart the same configured worker.
This explicit owner operation re-verifies existing bundles and updates only
rebuildable metadata. It neither packs again, uploads, retries incidents,
changes delivery status, rewrites raw/bundle/receipt bytes nor invents old
phase/enrollment times. The worker's OS lock prevents concurrent rebuild.
Read-only status supports the old outbox schema without migrating it; the next
owner writer adds nullable projection columns. Corrupt or absent old bundles
remain unavailable and preserve their original receipt/incident.

## Fixed collection tool

Build once from an exact clean Platform commit:

```bash
npm --prefix components/annotator run publish:collection-tool -- --output /absolute/new-tool-release
```

For an installed collection setup kit, first build the exact clean native Mod,
then add `--mod-provenance /absolute/native-build/build-provenance.json` to that
publication command. Publication verifies current compiled source and the adjacent
DLL SHA before including `game-mod/build-provenance.json` and the bounded Game Mod
setup tooling in the same immutable file inventory. The setup entry requires
Node.js 20+ in addition to the packing tool's .NET runtime.

```python
from sts2_platform_evidence.collection_tool import CollectionTool

tool = CollectionTool(tool_directory, trusted_release_id)
status = tool.setup_status(recordings_root=recordings_root, game_directory=game_directory)
# Only after the operator authorizes this destination, with the game stopped:
prepared = tool.bind_recording_root(recordings_root=recordings_root, game_directory=game_directory)
```

`game_directory` is optional when Host discovery can find Steam's installation.
The default provenance is the inventory-pinned file inside the tool; an explicit
`mod_provenance` must also be in that verified inventory. A legacy packing-only
release cannot claim setup support. `configured` means the next launch's disk
configuration; only a fresh owner status with `bound=true` confirms the actual
current native destination. The owner reports mutation compatibility separately
and never relaxes it. See [Game Mod setup](../../apps/game-mod/README.md#installed-collection-setup).

Publication runs the portable .NET Annotator Tool build (no game files), copies
its complete dependency output and the Platform BOM, and writes
`collection-tool.json`. `release_id` hashes canonical identity plus the exact
file inventory. The developer combination pins that ID independently; trusting
an arbitrary adjacent manifest is not authentication. The release is not a
signature or an assertion that the recorded game used the tool's source.
Recording identity remains the raw manifest; packing-tool identity is separate.

The installed release verifies every file before execution and no longer asks
Git about a developer's working tree. The legacy developer `pack-session` CLI
retains its clean-source check. Neither route weakens current causal audit,
close-seal, canonical, lineage or bundle verification. The .NET runtime is still
required on developer hosts; this is not a self-contained consumer installer.

## Configuration and entry point

Install the exact Evidence package and provide a private JSON config:

```json
{
  "schema": "sts2.evidence/delivery-config-1",
  "recordings_root": "/persistent/recordings",
  "outbox_root": "/persistent/delivery/campaign-a",
  "tool_directory": "/persistent/tools/pinned-release",
  "tool_release_id": "<64 lowercase hexadecimal characters>",
  "worker_id": "developer-a",
  "campaign_id": "campaign-a",
  "human_origin_attested": true,
  "hub_url": "https://hub.example.invalid",
  "allowed_upload_hosts": ["storage.example.invalid"],
  "poll_seconds": 5
}
```

`human_origin_attested` must reflect the actual operator's explicit consent and
attestation for this fixed campaign. It is never inferred from a successful
audit. The Hub token is read only from `STPD_HUB_TOKEN`, not the config or logs.
The token is a transport-edge credential, not STPD research policy.

```bash
python -m sts2_platform_evidence.delivery_cli doctor --config /absolute/delivery.json
python -m sts2_platform_evidence.delivery_cli run --config /absolute/delivery.json
python -m sts2_platform_evidence.delivery_cli status --config /absolute/delivery.json
```

`run --once` performs one discovery cycle and at most ten eligible attempts.
Continuous mode defaults to five seconds between cycles. SIGTERM/SIGINT stops
after the current attempt. HTTP timeouts bound socket inactivity, not total
wall-clock upload duration; a supervising workbench can terminate its own child
and restart from durable state. The collection subprocess has a 600-second
hard timeout. No end-to-end network latency SLO is claimed. The project entry point can manage this
process; it does not need to keep the game alive. An OS lifetime lock prevents
a second background worker, including when its previous parent was killed; it
does not guess ownership from a PID. Local SQLite serializes one
writer with a process-owned transaction, so no expired wall-clock lease can
overlap two delivery attempts. Read-only status uses WAL. A restarted process
rediscovers closed sessions and reuses identical published bytes.

One outbox binds worker/campaign/attestation/tool identity. To change any of
those, create a new outbox and retain the original; do not mutate old receipts.
The outbox must be outside the raw recording root. Nothing deletes local raw
evidence or completed bundles automatically.

## Durable states and incidents

`pending` includes locally enrolled, packed and network-retry work. `auth_blocked`
means a Hub API explicitly rejected the device credential with HTTP 401/403;
it is never automatically selected for another attempt. `verified`
and `quarantined` require matching terminal server receipts. `incident` records
a local seal/source/tool/bundle/protocol failure; it is not automatically retried
under a new interpretation. Status reports attempts and last error independently
from decision dispositions. A network retry re-delivers evidence, never an
unknown gameplay action.

The receiver's explicit `verification_pending` response keeps the outbox `pending`
with no error. Its `content_id` identifies the locally verified bundle; only a
matching terminal receipt can make it `verified` or `quarantined`. Normal receipt
polls still count as attempts and use the same bounded backoff. A real socket
timeout remains a `TimeoutError` diagnostic. Older logs that used `TimeoutError`
for both cases are ambiguous and remain unchanged; they cannot establish a
network failure without additional evidence.

Discovery requires `close_schema_version=1` and matching
`session-close-receipt.json` (`session-close-1`). An absent seal remains
`unsealed` in discovery counts; it is never silently promoted by elapsed time.
Malformed seals become incidents. Legacy and unsealed sessions require explicit
manual archival/diagnostic handling. Full source inventories are captured at
enrollment and checked before and after packing. Post-seal byte changes stop
delivery. Zero-canonical failed-only sessions remain eligible for valid bundle
transport, with their exact failure evidence intact.

SQLite, archives, metadata and receipts belong in a private persistent user
directory. They contain gameplay provenance and may contain local diagnostic
paths; they must not enter Git or public logs. Re-auditing an incident with new
tooling uses a new outbox and produces additional evidence, not a rewritten
original bundle. Automatic incident uploading of corrupt/unsealed raw data is
not provided by the verified-bundle route.

## Explicit credential recovery

The authenticated Hub API edge raises typed `AuthenticationBlocked` for HTTP
401/403. The object-store PUT edge does not: an R2/presigned-URL 403 remains a
transport protocol incident, and 5xx/408/429 retain their network retry behavior.
The outbox stores `auth_blocked`, safe error `hub_authentication_blocked`, and a
private typed block anchor containing exact content/manifest/archive/upload
identity. It records no credential, signed URL or response-body diagnostic.
A block before the first upload intent has an explicit null upload ID.

The account/device owner should first restore authorization for the **same
logical device**, validate that identity against its service, and stop the local
delivery worker. Platform does not own account login or assume a cloud identity
API. Then invoke the public owner recovery operation:

```python
from sts2_platform_evidence import resume_auth

report = resume_auth(config, delivery_id=outbox_id)  # omit ID for all auth-blocked rows
```

```bash
python -m sts2_platform_evidence.delivery_cli resume-auth --config /absolute/delivery.json --delivery-id <64-hex-outbox-id>
```

`resume-auth` acquires the worker's OS lifetime lock and a SQLite writer lock.
It checks the immutable campaign/tool configuration, enrolled source inventory
and successful Close seal, independently verified bundle, exact prepared content
and transfer manifest, saved metadata, archive bytes/hash and original upload
sidecar. It neither repacks nor sends a network request. A valid block becomes
`pending` with retry time zero; attempts, content identity, transport files,
raw evidence, bundle and receipts remain intact. The next normal worker uses
the replacement `STPD_HUB_TOKEN`; an already uploaded object is recovered by its
original receipt GET, and another Hub rejection blocks again. This operation
alone establishes neither working credentials nor remote receipt success.

The `sts2.evidence/delivery-auth-recovery-1` report contains `resumed`,
`unchanged`, `rejected` and `sessions` entries with `id`, `status`, `result`,
`error`. Errors are stable, path-free categories. The all-rows form selects only
`auth_blocked`; an exact ID already pending, verified, quarantined or incident
is unchanged. Unknown IDs/missing outboxes return no matching sessions. Repeated
successful recovery is a no-op. Invalid or missing evidence/identity leaves the
original auth block intact and reports rejection; the CLI returns nonzero.
Transport files are never deleted to manufacture a fresh upload.

Legacy incidents with free-text 401/403 messages remain incidents. Their text
does not distinguish Hub authorization from storage authorization and cannot
justify automatic migration. A writer adds nullable `auth_context` storage;
read-only status still supports older schemas. An unproven typed block without
its exact transport anchor also remains blocked. Terminal receipts and Human
dispositions are never rewritten by credential recovery.

## HTTP receiver protocol

The edge adapter uses the coordinated Hub v1 wire namespace (`stpd/*`); the
protocol carries evidence logistics, not legality, dataset eligibility or
training policy:

1. `POST /v1/uploads`: `schema=stpd/upload-intent-v1`, complete
   `transfer_manifest` (`sts2.evidence/directory-transfer-1`), `archive_sha256`,
   `archive_bytes`, and optional `delivery_metadata` (tool and source provenance).
2. The response supplies `upload_id`, `upload_method=PUT`, `upload_url` and
   `upload_headers`, or the existing terminal receipt for identical content.
3. PUT a persistent deterministic tar.gz containing exactly the manifest's
   files. The archive hash is transport identity, not bundle content ID. No Hub
   bearer is sent to storage. Only explicitly configured HTTPS hosts are allowed;
   loopback HTTP requires the explicit test-only option. Redirects are rejected.
4. `POST /v1/uploads/{id}/complete` starts/queries independent verification.
5. `GET /v1/uploads/{id}` recovers after restart. `verification_pending` is not
   success. A terminal receipt contains `schema=stpd/receive-receipt-v1`,
   `receipt_id`, `status=verified|quarantined`, `content_id`,
   `manifest_sha256`, and findings. Both identities must match the local transfer.

A receiver `transfer_failed` status stops automatic attempts and requires explicit
operator recovery; it is neither a verified nor quarantined semantic receipt.

The server must key retries by content ID and transfer-manifest hash, retain
verified immutable objects, reject content collisions, and independently verify
staged bytes before receipt. Expired presigned URLs are refreshed by repeating
the same intent, reusing the exact archive. Upload, structural verification,
Human origin, Full-Run qualification and STPD admission remain separate facts.

## Stopped-generation completion

Evidence `0.1.0-rc.9` adds an operator-only Python context for consumers that
need to retire a completed queue without rewriting its campaign/tool identity:

```python
from sts2_platform_evidence import completed_delivery
from sts2_platform_evidence.delivery_config import DeliveryConfig

config = DeliveryConfig.load(delivery_config_path)
with completed_delivery(config) as completed:
    proposed_receipt = completed.to_dict()
    # Keep any dependent local operation inside the owner lock.
# Publish only after successful exit, or roll back publication if exit raises.
```

The context takes the existing worker lifetime lock and reads SQLite with
`mode=ro`, including committed WAL state. It does not initialize/migrate an
outbox, pack or re-audit a session, execute a tool, query the cloud, or change
delivery records. The existing lock file and SQLite reader coordination are the
only filesystem effects. A missing old outbox is not a completed generation.

Every recording-root entry must be an enrolled sealed session, with unchanged
Close identity and raw inventory. Every row must be `verified`; pending,
authentication-blocked, incident and quarantined rows block completion. The
check verifies the pinned tool, bundle/session/worker/campaign identities, exact
raw copy and transfer manifest, delivery metadata, archive members and hashes,
durable upload identity and matching local terminal receipt. Symlinks, special
files, extra queue entries and partial artifacts fail closed. A valid empty
configured outbox with an empty recording root is complete. A verified bundle
with failed Human decisions is also transfer-complete; its failures are preserved.

Evidence `0.1.0-rc.10` also reads the historical upload sidecar containing exactly
`upload_id` and `archive_sha256`, written before `dafe61f`. Its missing byte count
is observed from the actual archive only for the new completion receipt: archive
hash, transfer membership/content and terminal receipt checks still all run. No
old sidecar or queue row is rewritten. A present `archive_bytes` must be an exact
integer (not a boolean) matching that archive; missing size with any other shape,
null, malformed values or mismatches fail closed. Worker exclusion and exit-time
revalidation are unchanged. This compatibility does not confer daily enrollment
or consent on a manually configured historical queue.

`DeliveryCompletion` is frozen and `to_dict()` returns an independent dictionary
with schema `sts2.evidence/delivery-completion-1`. The receipt includes the full
normalized config digest; recording/outbox/tool paths; fixed tool, worker and
campaign IDs; session count; full raw inventory and durable outbox byte digests;
and sorted per-session source, bundle content, transfer, metadata, archive,
upload and receiver-receipt identities. `completion_sha256` hashes the canonical
dictionary excluding that field. Metadata/receipt digests name file bytes;
the transfer digest names its canonical protocol manifest. Receipts contain
private local paths and belong in protected local consumer state.

Public receipt equality does not depend on observation time, file timestamps,
inodes, lock metadata, SQLite physical representation or optional UI telemetry.
It binds upload/archive identity without binding the sidecar's observation time.
The context separately guards all persistent queue bytes, full logical database
rows and directory/file replacement, and repeats the complete verification after
normal yield. Until that exit succeeds, its receipt is provisional. A consumer
that publishes an active pointer inside the context must undo it if exit raises.
Exceptions release the worker lock; no context result grants future immutability.

The consumer remains responsible for stopping its Workbench, proving native
game/recorder readiness through Game Mod, preserving the source configuration,
checking current same-device consent and performing one atomic active-pointer
change. This context provides local retained-receipt integrity, not fresh remote
availability, new Human qualification, research admission or rollover authority.

## Qualification

Portable tests cover release tamper/extra dependency detection, changed source,
wrong/missing seals, failed-only evidence, offline restart, crash after receive,
concurrent writers, receiver identity mismatch, pending HTTP recovery, exact
archive membership and credential/host boundaries. Recovery regressions cover
real Hub 401/403 versus storage 403, credential rejection after accepted PUT,
repeated receipt-GET rejection, same-upload recovery with one PUT, sealed-source/
bundle/transfer/archive/upload tampering, idempotent explicit recovery, existing
incident preservation, worker/SQLite locks and changed campaign identity. They do not establish a
real cloud account, real R2/Hub deployment, GPU work, or a new Human delivery
canary. Those belong to the coordinated project's exact runtime gates.

## Terminal preflight and campaign isolation

`doctor` returns the versioned `delivery-doctor-1` report and blocks on invalid config,
missing credential, unusable collection-tool bytes/runtime, conflicting outbox identity or
invalid local paths. It executes the pinned tool's read-only identity command to prove the
actual .NET load. It never sends network requests, initializes/enrolls an outbox or changes
its logical records. SQLite read-only access may create WAL/SHM reader-coordination files;
it does not ignore an existing WAL. `status` likewise does not initialize a missing outbox.

Inspect the reported discovered session count before starting delivery. All sealed sessions
under the selected root are eligible for discovery: use an initially empty dedicated campaign
recording root and separate new outbox for first Human upload. Do not infer consent from
timestamps or assume only the next Close will upload. Configure the Mod's `recording_root`
through its supported config/environment before cold load. Deployment preserves valid
operator recording/status paths and rejects malformed existing configuration. Unset process
environment overrides when expecting the config file to apply.

The fixed tool release is built once by the operator; the exact Evidence package is supplied
by the consuming workbench lock. A local `publish:collection-tool` output is not a hosted
release or self-contained player installer. Distribution instructions are coordinated in
the consumer's versioned terminal handoff; Platform remains the owner of preflight and
recording/tool contracts. A PASS here is local readiness, not Human attestation or cloud IAM.
