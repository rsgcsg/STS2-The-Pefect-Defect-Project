# Dataset curation and continuous recording candidate

This is candidate engineering evidence, not a released or Human-qualified result.
Later bounded results are recorded in [the acceptance report](CURATION_CONTINUOUS_ACCEPTANCE_2026-09-17.md).
Base: `415e8e5aa442c0c0b76bfc2cb6b1f266dcfae51c`, branch
`feat/data/curation-and-run-recording`. ADR-0010 owns the approved scope.

## Measured local selection performance

An isolated local macOS CPU fixture used 14 existing verified recording archives
(39,479,125 compressed bytes), selecting 6,398 decisions. Originals were read only;
the test store, cache, generated manifests and logs remain private. No production
dataset was published and no training ran.

| Path | Before compact spool operations | After |
| --- | ---: | ---: |
| First preview and verified source index | 227.462 s | 65.472 s |
| Another preview with all 14 source indexes present | 185.413 s | 27.968 s |
| Curate selection and publish manifest | 217.732 s | 4.649 s |
| Process peak RSS | 903,675,904 bytes | 889,864,192 bytes |

The baseline was `b2ce8c5`; the optimized selection implementation is `ab0f476`.
The measurements are single runs, not capacity guarantees. Some baseline work
overlapped unrelated checks. They do not include cloud object-store latency, the
full Hub permission/Gold reconciliation path, or confirmation cache retrieval.
The final row is an already previewed selection in the same process, not a claim
that every cloud create request finishes within five seconds.

Profiling found repeated canonicalization and decoding of complete state/action
payloads. Typed rows now produce compact private summaries and canonical bytes
once; filtering, facets, run grouping, logical hashing and manifest publication
reuse them. Byte-identity, whole-run/duplicate grouping and non-decoding regression
tests compare this path with materialized records. Cache misses/corruption still
go through the installed verifier. No evidence gate was removed.

## Browser and native evidence

Current console assets were exercised in headless Chrome at 1440x1000 and 390x844
with explicit synthetic API responses. Date entry, select-all, training/test
choice and returning to the creation form retained their draft and selection.
The 10-second refresh preserved form and unchanged task DOM identities; neither
viewport had horizontal page overflow or page errors. Screenshots and request
logs are private. This is browser behavior evidence, not deployed member access.

The exact-game build completed for the native component bytes recorded by
`b2ce8c5`. Portable Core and Evidence tests cover continuous arming, boundary seal,
manual stop, interrupted-copy verification and completion mapping. Installation,
cold load, native end-to-end exercise and fresh Human canary remain separate gates.

Shared canonical JSON optimization changes the S1 adapter's implementation
digest. A new v6 manifest records that identity; v5 and historical manifests are
unchanged. Checkpoint, model semantics, game requirements and support are retained.
This does not qualify that historical checkpoint against a newly installed Mod.

## Rollback boundary

Retain prior image/config, fixed source, native artifacts and collection tools.
Do not restore an old operations database to undo a code update. Once Gold claims
exist, an old image without curation enforcement is not an access-safe rollback:
keep affected data access paused until a compatible enforcing image is restored.
Raw recordings, old artifacts, reservations and pending delivery identities stay
intact. No GPU, paid training, Windows/Linux native installation, complete-game
policy result or scientific qualification is claimed.

## Linux capacity finding and follow-up

An isolated existing-VPS container (one CPU, 1536 MiB address-space and memory
limits, 600 CPU seconds) read 37 verified archives totaling 86,053,480 compressed
bytes. The first cold preview did not complete: 34 sources were indexed before
the process exited with status 137 after about 724 wall seconds. The available
observations do not establish whether CPU enforcement or another external kill
caused that exit; no Docker OOM event was observed. Observed RSS stayed below 600 MiB.
This is a failed capacity qualification, not a passing production measurement.

The follow-up prepares at most four cold source indexes per worker invocation,
then checkpoints the same job back to pending. Each continuation rechecks member
and source access. A warm invocation performs selection/publication; failed or
unknown publication is never automatically retried. Cancellation/attempt fencing
stays in force. The private source index now has a 1 GiB logical quota in a
separate mode-0600 disposable SQLite file, avoiding authority-database backup
bloat and long cache readers blocking account/heartbeat writers. If a selection
cannot make forward progress within that quota, it fails explicitly rather than
looping indefinitely. The repeated qualification is recorded below.

The local `427c646` kit passed install, cold-loaded identity and collection-upgrade
activation with the existing enrollment and device. Fourteen predecessor sessions
were sealed and delivery-complete; their originals and outbox remain unchanged.
The prior activation failure was a stale Evidence pin in combination-v1, corrected
to the pyproject/uv.lock pin with a regression. Native gameplay has not been
performed by the agent. Later owner-operated evidence is recorded in the acceptance
report; it does not retroactively change this intermediate candidate's evidence.

## Repeated bounded Linux qualification

The final backend `ecd787c73f6928c4527f889c4f1418ef5c46116e` used the same
37-source input and limits. Producer `bafef714a767c3d1d2bf9a4d04281595996f8a5c`
changes only console JavaScript and its tests relative to that backend.

| Operation | Observed elapsed time | Result |
| --- | ---: | --- |
| Cold source preparation, ten bounded invocations | 473.631 s | 37/37 indexed |
| Selection invocation | 336.537 s | 14,313 decisions |
| Cold preview cumulative worker time | 809.986 s | completed |
| Confirm fixed preview | 46.093 s | completed, one preview-cache hit |
| Materialize full records on demand | 470.520 s | completed |

Maximum observed RSS across these invocations was 432,768 KiB. The confirmed
manifest is `e0c0899f20291c0bfbad1e0aed722ae28ba7e057c9809fd7713ac7e008a9a605`;
materialization is `7b495f63e335e7bfd3c73b1498069fed83db5cbcfdb265d608ae1409864c5bc7`.
A separate read with the final `bafef71` image verified the Parquet payload:
14,313 rows, 19,082,437 bytes, SHA-256
`f66da4b07091346ed1e0c6ad12221bf09430528c3e8e08771249b29f417a8dbf`.
The fixture store and operations DB were isolated; no production dataset was
published by this qualification. Timings are single observations on the existing
VPS, with other bounded checks running during part of the measurement, not an SLA.

An intermediate uncompressed-preview implementation exceeded its 16 MiB metadata
entry bound and missed the cache, taking 355.273 s to confirm. The final cache
compresses metadata with a 64 MiB expansion bound and verifies source-row checksums;
corrupt, evicted or oversized entries still reproduce the verified selection.
This observation is retained rather than reporting the intermediate optimization
as successful. First-time indexing and requested Parquet export remain minute-scale
background operations; manifest-first creation does not make those costs disappear.
