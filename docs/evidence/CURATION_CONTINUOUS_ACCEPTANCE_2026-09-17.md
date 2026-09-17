# Dataset curation and continuous recording acceptance

This records bounded engineering, deployed-service and owner-operated evidence.
It does not claim model quality, all native surfaces or unlimited dataset capacity.
PR [#21](https://github.com/rsgcsg/STS2-The-Perfect-Defect-Project/pull/21) and the
release integration receipt own final merge/publication facts. The approved scope
and authority boundaries are in [ADR-0010](../adr/0010-dataset-curation-and-continuous-recording.md).

## Exact running combination

| Item | Verified identity |
| --- | --- |
| Base develop | `415e8e5aa442c0c0b76bfc2cb6b1f266dcfae51c` |
| Workbench / Hub runtime source | `bafef714a767c3d1d2bf9a4d04281595996f8a5c` |
| Python lock SHA-256 | `1dd5f0dc645c7330b4a6e7712da5edad7f04caa6640b69c0cf1d0dfac42f84f7` |
| Hub OCI digest | `sha256:a2183cd6906e2464786166f4a71d04c23292860abde9b002992054cf00cbf9bf` |
| Developer kit SHA-256 | `39df5dbb5f8f1907ee0c9c731b0b862559224be6608e3782c89e3081bc156863` |
| Installed Mod SHA-256 | `52bcd79560de09fdcc212507aab837636a3ed334dc7261ab94b3e2a52ca6ae0e` |
| Installed Mod MVID | `9db537ec-840b-4e2e-aa85-bea9fab6f4f1` |
| Annotator component source | `2f88d529dee3a9d4382cbf7d243377655ed86c39` |
| Collection Tool ID | `0df4e928103e43e1c64d8d2a84f052bb4d7fd0fb9252bdf2aa65a609165f54c8` |
| Tool packaging workspace | `427c646e39b7b354049f96dca14b08809dcac587` |
| macOS STS2 | `v0.111.0/41cef1ea` |
| Game SHA-256 | `9cb4f1ad8c9f284aa8fec3122ffd6d780bbf543d875c817abdd12ff63fbf12b4` |
| Game MVID | `57785517-0b16-42b9-8b36-bad6fb28384b` |

Native installation, exact cold-loaded identity and the existing enrollment's
collection-upgrade prepare/activate passed. Account, consent, device and old
outbox identities were retained. Fourteen predecessor sessions were sealed and
delivery-complete before activation. Later Python/console changes reused the
same native and Collection Tool bytes; source SHAs are not interchangeable with
component or installed identities. Documentation integration does not rebuild them.

## Source and browser checks

Exact-game build and portable native Core 281 / Evidence 110 tests passed.
The final backend Python/repository gate passed: 1,028 tests, three explicit
platform/optional skips and 21 subtests, plus lint, typecheck, CPU E2E, cloud-worker
smoke and packaging. Final console tests: 76 passed.

Runtime source `bafef71` passed the full hosted Linux/Windows aggregate in
[run 35225848126, attempt 2](https://github.com/rsgcsg/STS2-The-Perfect-Defect-Project/actions/runs/35225848126).
Attempt 1's Linux dependency-review request failed with `fetch failed` before
source tests; only failed jobs were rerun after Windows finished. This is not
reported as a passing first attempt or a code-test failure. Windows took 16m04s;
its Python suite took 549.19s (992 passed, 39 explicit platform/optional skips,
21 subtests). The longest individual Python test was 17.44s. The final integration
head has its own required checks, linked by the release receipt.

Synthetic desktop 1440x1000 and mobile 390x844 Chrome checks retained date/purpose/
source drafts and unchanged task nodes across polling, without overflow or page
errors. An additional real signed-in Workbench check during the production batch
observed create navigation 1,149 ms, task navigation 807 ms and cached return 32 ms;
the draft node survived an 11-second polling interval. These are individual
observations, not latency guarantees. No test form was submitted by that check.

## Dataset capacity and policy

[Candidate and repeated capacity evidence](CURATION_CONTINUOUS_CANDIDATE_2026-09-17.md)
retains both failed intermediate measurements and final results. In an isolated
one-CPU / 1,536 MiB / 600 CPU-second-per-invocation container, 37 verified archives
(86,053,480 compressed bytes) selected 14,313 decisions. Cold preparation plus
selection took 809.986 cumulative worker seconds across bounded invocations;
fixed-preview confirmation took 46.093 seconds with a cache hit; on-demand Parquet
materialization took 470.520 seconds. A separate final-image reader verified all
19,082,437 payload bytes and 14,313 rows. No production dataset was created by this
isolated fixture. First-time indexing and full export remain minute-scale work.

The actual previously failing 35-source selection was restarted through the signed-in
Workbench with the same sources and rules, as a new current-purpose preview.
Production job `66c92741fde949349f8ab93ef43652a7` completed without error, selecting
13,474 decisions in 943.318 cumulative worker seconds. Its predecessor
`49f74ea688c94ebf9ab9ee6280a237ad` remains failed as historical evidence. The new
preview is ready for the owner's confirmation; qualification did not publish a
training dataset or reserve those sources against a later Gold choice.

Purpose/annotation/overlap regressions cover whole-run and transitive duplicate
isolation, actual model ancestry, unknown ancestry rejection, concurrent Gold
reservations, Gold-only merging, legacy/raw/derived download guards, retained
reservations after failure, annotation races, parent exclusion and fixed historic
selections. Those are automated engineering tests, not a production Gold corpus
or scientific evaluation. Sealing cannot undo prior access or revoke external
copies. No user data was newly sealed as Gold just to test the release.

## Owner-operated native canary

The owner confirmed completing the requested native actions; the agent did not
play the game. Both sessions used the installed combination above and each
independently passed the owning recording auditor and cloud bundle verifier.

| Session | Accepted | Proved / canonical | Cancelled | Diagnostics | Real failures / unresolved | Native boundary |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `session-20260917T132627Z-f6f296642bfc453b97b8bff306b835ed` | 17 | 15 | 2 | 3 | 0 / 0 | native start + end, abandoned |
| `session-20260917T132714Z-07bca08783d34a149a2798650e4bdf4f` | 10 | 10 | 0 | 3 | 0 / 0 | native start + orderly exit, no terminal |

The first segment sealed automatically on abandonment. With recording still
armed, the second new run obtained its own session and sealed on
`RunManager.CleanUp(graceful=true)`. It remains an unfinished segment, not a defeat
or a complete run. The earlier in-progress observation in the first session is
retained alongside the later exact native launch witness; it is not rewritten.
Coverage includes event choice/proceed, map travel, combat play/end-turn and one
nested event selector. Six native-type-mismatch diagnostics remain diagnostics;
two cancelled actions have no invented successors. The compatibility-view audit
counts (3 and 4) are not substituted for canonical counts (15 and 10).

Automatic upload receipts are respectively
`ddc0ebc13bc730e4777b5222ea600320` and `db709db8cd12eb3f3a0a64d4f6cdef45`, both
`verified` with no verifier findings. Member export
`c3e43106c55f93c6aa762b418a71ecb325889ae4d7fbc0558621e38872f50d40` downloaded both
archives: two files, 164,821 bytes, every file's declared size and SHA-256 verified.
Raw evidence and private receipts remain outside Git. Victory, natural defeat,
forced-crash recovery and unvisited families were not newly Human-tested here.

## Hub promotion and recovery

The authorized candidate rollout verified its exact producer and service, retained
TLS mounts and used the existing database without restoration. External TLS health,
unauthenticated member rejection (401), signed-in member access and object-store
conditional write/readback passed; the store doctor verified 39 indexed manifests
at that observation. Compute budget stayed zero.

The predecessor backup receipt
`26108f687a0d5cb68e17905fbbea87b32fce7f49443f580c1d3dc526c8d381b6`
passed independent download, checksum/schema/integrity and paused restore checks.
After deployment, receipt
`593c4a02e8d5756a88c2f9b46011092145ac329230c81dcc96ba0778d6f21135`
passed the same isolated restore check using the new image; snapshot SHA-256 is
`66492c446f1e030b1b9ccbd47f0d282098c6e59e7bba99c7ad9b768e9af416ec`.
The backup timer was restarted and observed active. No live DB was overwritten.

Retain the old image/config, native package, fixed checkouts, tool and raw queues.
The previous image is `sha256:60654b3b21c7970de2224dfdcd79f8cd7d38e560ff28826f1166be0203b6ec5e`
(source `c334da62c3dce08c86f7743066e4912faea9cdbe`). Once Gold reservations exist,
that old image cannot safely serve affected access: preserve the current DB and
use a compatible enforcing image or pause affected access. Do not restore an old
DB merely to roll back code. The existing TLS bind source remains retained.

No GPU, paid training, model-quality result, universal Full-Run qualification,
Windows/Linux native installation or arbitrary-size resource guarantee is claimed.
