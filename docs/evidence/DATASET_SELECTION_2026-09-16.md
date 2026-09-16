# Dataset selection follow-up — 2026-09-16

This follows [dataset library acceptance](DATASET_LIBRARY_2026-09-16.md) and
[ADR-0009](../../python/docs/adr/0009-project-dataset-selection.md). PR17 owns this
repair; final integration, real batch result and publication receipts are separate
release attachments. Prior failed task evidence remains unchanged.

## Owning defects and changes

The actual twenty-source preview failed because one environment fingerprint had
multiple runtime process IDs, including inside one archive. The fingerprint owner
excludes process IDs. Research now preserves sorted process provenance while requiring
all other environment facts to agree exactly; single-runtime logical IDs are unchanged.

Task HTTP reads previously fetched every source manifest; local identity reads held
the account lock during network requests. Indexed access checks and unlocked network
reads remove this serial work; workers still validate actual bytes and access before
and after processing. Browser navigation uses immediate shells, short identity cache
and stale-account/page guards. Dates filter recording time before pagination; select
all covers the whole matching set within the existing 100-source bound. Failed selection
can be edited, and retry follows its newly created task instead of the old failure.

Authenticated members use accepted project recordings without a second publication
approval. Explicit withdrawal, revoked membership, sealed data and original evidence
contracts remain. Legacy hashed v1 export inventories still pass current access checks.
No existing grant, withdrawal, receipt, raw disposition or immutable artifact is rewritten.

The real twenty-source retry passed the original environment conflict but was stopped
by the single-upload process limit after ten verified sources (last progress 138.426s).
Dataset workers now have separate 900s wall / 600s CPU budgets; upload 150/120s,
1.5GiB address space, 256MiB aggregate source bytes and 100-source cap remain.
No automatic retry or unbounded worker is introduced.

A subsequent twenty-source attempt verified all sources but exited with a resource/process
failure after its last progress at 432.327s; the exact OS cause was not established.
Code review found that coverage re-read and decoded every archive after preview had
already verified it. Coverage now consumes those same verified projections during the
first traversal, preserving source order and overlap handling. A regression rejects any
second source read/resolve and compares the complete coverage output. Final access and
content checks remain; neither selection reports nor logical IDs include this observer.

A further one-pass retry reached selection completion (last progress 437.551s)
but still exited with the same generic resource/process failure. Inspection identified
another whole-batch allocation: logical hashing decoded every record into one list,
then canonicalization copied the full tree. Hashing now emits the identical canonical
bytes one record at a time. Publication writes bounded row groups to scratch files;
loading fully verifies source bytes and compares every ordered row in batches.
Physical Parquet bytes may change; logical ID, report, schema and row content do not.
The 8MiB grouping target is not a hard memory ceiling for a single large record.

Regressions compare the independent original hash formula, including Unicode/escapes,
numeric values and the pinned legacy ID, and reject retaining decoded prior records.
Multiple row groups and legacy single-group files load; valid-hash files with missing,
extra, reordered, modified rows or extra columns fail reprojection. No resource bound
was raised to compensate for these duplicate allocations.

## Exact source, tests and deployed observations

Full root `npm run check` at `a8c5971c2c856087ebff7ef92d0d3ff50940430f` passed
(same application source as deployed `3a4b8997d06011952a2248902c67f64f531dbcff`):
990 Python tests, 3 skipped, 21 subtests; 70 console/identity regressions, component,
type, package and CPU E2E checks. Focused tests exercise unchanged golden legacy
identity, nested union/reload/cache, genuine conflicts, missing grants, withdrawals,
worker receipt rejection, no storage calls on HTTP task reads and concurrent logout.
Supervisor tests retain deadline/shutdown process reaping and verify the distinct
CPU limit with unchanged memory/file bounds. No new native source changes occur.

Workbench source `fedbed097e30fb78bf0e86efff560fd8b1263c99`, kit SHA256
`e598fe9cef5f6f2ba6b97eca6a8b3986c7b4168dc0033c6d8ee277e62d93b53f`,
was installed through managed prepare/initialize in a permanent independent checkout.
Existing composition, profile, credentials, consent, native Tool and queue remain.
Doctor and delivery preflight pass. Desktop launch points to the new source.

Hub source `3a4b8997d06011952a2248902c67f64f531dbcff`, image
`ghcr.io/rsgcsg/spireagent-hub@sha256:74ab9ecc19efd3bb2ea7de08e20ec558bf552b27a5d94d18fd24ee3afdd9db8d`,
lock `44b53f0184ef8ea612eb50550f35f81e32456ba93fb2cf80c336157d41778bd5`,
uses the existing same-schema owner rollout. Exact plan
`d804dd122016f1469dff4fcc6377fd799fb07fae8db558629e51e931c9d9069e`
verified producer, capacity, matching-image fresh backup and unchanged schema.
The earlier attempt was correctly refused until a current-image backup existed;
no check was bypassed. TLS/state mounts and zero-budget paused compute remain.

Actual browser observation on the new UI: 23 selectable accepted recordings;
whole-date selection selected 23; five tab shells 33–81ms; collections 242ms and
task list 268ms. The old 3-file v1 download inventory remained accessible, and there
were no browser page errors. These are one local observation, not a throughput SLA.
Final exact batch processing result is recorded in the release receipt; a task being
queued/running is not claimed as successful data generation.

Backup `19ca96595191f9efe380f896c2ddb87c9842d0eb83805c0eff5063bc4a25611b`
passed isolated paused restore, SHA256
`006b7f1296485fbae1d183c02235e410fe0eef3349d5273f9928d7f1a064b714`.
Immediate pre-batch-image backup
`fb6bd559eacb0c8f2176ce1b27bd528b37ac68620f3edb91ea6c4e6f3b516b24`
was verified off-host with the then-current fedbed image. The immediate pre-one-pass
backup `7742bcbc1cd99001a8d768ae22757d404934b252db9a5a185d4c13e71f6cff4a`
matched the prior 3159 image; the rollout verified that receipt before applying c155.
The final pre-streaming backup
`36a0545a07862bb4f1a39cdcbc54d4fe4d4c5e1fc32ad1cde073f0b9f27c51a5`
matched the c155 image and passed the final owner rollout check. Final post-deployment
backup/restore and actual batch/build results are recorded in release attachments.

## Rollback and non-claims

Retain corrected-reader images/configurations and fixed Workbench installations.
New multi-runtime datasets need the corrected reader; old images only provide
limited fallback, not compatible reprojection. Never restore an old live DB merely
to undo code; preserve current raw data, withdrawals, queues and immutable datasets.
The fedbed image retains the corrected reader but may reproduce the batch timeout.
No new Human, native installation, Windows native, GPU/model or scientific qualification.
