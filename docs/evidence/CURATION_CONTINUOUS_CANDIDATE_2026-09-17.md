# Dataset curation and continuous recording candidate

This is candidate engineering evidence, not a released or Human-qualified result.
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
