# Small-team operating-flow acceptance — 2026-09-16

**OPERATING_FLOW_BOUNDED_HUMAN_PASS**. The owner reported completion of the
requested local/cloud UI and short native recording check. Machine evidence
independently establishes the identities, recording and transfer below; it does
not establish Human origin or visually inspect the browser. This is Scheme 2
(P0/P1/P2), not a new model, native compatibility or uninterrupted Full-Run gate.

## Qualified combination

| Object | Exact identity |
|---|---|
| Workbench / kit producer | `6fcd735e4618c29967528e9d3457d898d2e8283d` |
| Developer kit ZIP SHA256 | `0652c24b34e3b57a20639f92c2222f287f0e4c4d72d14ef0843350a66f9244a6` |
| Hub producer | `25777cbce106ec9d64ceeef9e55b889abdbc3d3a` |
| Hub OCI | `ghcr.io/rsgcsg/spireagent-hub@sha256:9271a619f16e427f3c338f5589052894467968d46067896d183afd4f5cf30d85` |
| Python lock SHA256 | `5f228ae57b5b8610dfd7977a6b465ec391b01eea933c2c80ad87ffb126566ba7` |
| Retained Mod SHA256 | `1a8072e02d2c0721bab9f33794302c49181853befdb931881407217af780a001` |
| Mod MVID | `0d5931ad-a7bb-405c-a7d0-200ed18b7443` |
| Retained tool release ID | `9a293774b0ac4664bd0cb78dedb2ea09e5185b7c653724811c4c7c0b073e0633` |
| Game | v0.111.0 / `41cef1ea`, macOS arm64 |
| Game assembly SHA256 | `9cb4f1ad8c9f284aa8fec3122ffd6d780bbf543d875c817abdd12ff63fbf12b4` |

The kit reuses the preceding qualified native bytes and BOM with their original
provenance. Its changed Python installation tools do not relabel native source.
The installer-only fix after the Hub build, and later test/documentation changes,
do not require another Hub build or a different runtime kit.

Managed prepare/locked initialization and actual Workbench doctor/start passed.
The first clean installation exposed missing Workbench-side Node SDKs; the
initializer now installs both root and Python consumer lockfiles. With the game
closed, the managed entrypoint invoked the existing native deploy owner, retained
rollback, and preserved the Annotator configuration bytes exactly. Native
launch/verify-loaded passed for process 47031 at 2026-09-15 16:10:43 UTC. Fixed-tool
setup reported configured, connected and bound to the original recording root.
The existing device, consent, tool registration and queue were retained.

## New Human recording and transfer

Session `session-20260915T161503Z-1e4b3f798cd54325a5db82d1e66e6a1e`, closed
2026-09-15 16:16:38 UTC. Producer audit, semantic calibration and independent
Evidence bundle-3 verification passed:

- 60 accepted, 60 proved, 60 durable canonical; 7 accepted/canonical children.
- Zero real failures, unresolved, cancelled, aborted or unsupported occurrences.
- Compatibility projection: 24 valid / 0 invalid; this is a subset, not the total.
- 235 materialized Reads, zero failed Reads. Native semantic diagnostic: 49
  successful exact-once memberships, zero unknown, 3 matched choice pause/resumes.
- 8 explicit invalidations: 1 MoveToMapCoordAction and 7 ReadyToBeginEnemyTurnAction,
  all `human_action_native_type_mismatch` with authoritative `diagnostic`
  disposition. These internal actions are not lost independent Human choices.
- Native starts 0, ends 0, resumes 1: an incomplete resumed-run fragment. No
  uninterrupted-run or exhaustive native family qualification follows.

Automatic Close sealed and uploaded the new recording. Hub returned verified with
no findings. A separate authenticated device read returned the same receipt;
the actual R2 artifact archive was streamed and hashed independently against the
local archive. The owner reported completing the requested member/UI check.

| Evidence | Identity |
|---|---|
| Bundle content | `a4762ce4d67bd2681989d68c6d512339cc8d6742a2fde384e514d86e2b1f2d76` |
| Upload/receipt | `8b36be9d243abb29ef85518a4aa3faf7` |
| Stored evidence manifest | `39775dd2ebfff3a4f025534c94328e7fbb2618e42326b51814b73724708a7483` |
| Transfer manifest SHA256 | `4f8c19353c2c120ed85a7ad52100e66b446f0f0c84a51f2bcde944d6b95d5b0e` |
| Archive SHA256 / bytes | `4d8e27924a1d27c3cf40cc0f0c604ec85e71e7ce433bf70d3866e28bd9ca0372` / 303991 |

Raw sessions, private profiles and archives remain outside Git. Failed or
diagnostic historical evidence has not been rewritten. Research admission,
decision-dataset trainer integration and model quality remain separate.

## Cloud, compatibility and recovery

Reviewed same-schema rollout changed only Hub, verified exact container/HTTPS
producer, and kept operations schema 4 and compute budget 0. Reapplying the
current reviewed plan performed an identity check without restarting the service.
Old image/config and a durable deployment receipt are retained. Existing deployed
maintenance helpers were unchanged; they read the newly selected immutable image
from the private deployment config rather than maintaining another image pin.

New-image R2 backup/readback receipt
`e50c490de5d8baae4c3ea5fc0bb61bcc2e4a4b2bf088a1f4f765c991c5abcc8c`
passed a separate restore-check into an isolated new directory: checksums, schema,
SQLite integrity and paused state passed. No live database was restored. The
backup timer is active. The preceding image/config and native rollback files
remain available; application rollback must not discard newer uploads/revocations.

The actual published `45ef463` Python client read the new Hub's status, uploads,
jobs, incidents and system through its existing scoped device grant. The new
Workbench read the same Hub with a different source SHA. Portable regression
also covers unsupported schema and stale observations. These are bounded
contracts, not arbitrary-version or complete old-runtime qualification.

## Source checks and integration

Full local gates passed on clean `6aa53a6f122f9e18c7421506e9dc630019e7f41b`,
including 777 Python tests, 3 skipped, 21 subtests and the root component gates.
An independent no-dependency checkout with a single README edit selected and
passed the lightweight docs route. Unsafe ZIP/configuration/schema/rollback
guards and UI/compatibility regressions passed.

Two earlier Windows failures are retained: a 500ms wait for unchanged Policy
HTTP stop arrival timed out (local 50/50 recheck and the next hosted attempt
passed), then the unsafe-backslash ZIP fixture was normalized by Python on
Windows. The final fixture preserves the literal archive name on every OS;
rejection assertions and production security behavior were not weakened.

[PR #5](https://github.com/rsgcsg/STS2-The-Pefect-Defect-Project/pull/5) records
final task-head and integration CI. Source integration and formal publication
remain separate gates; resolve the exact main/develop results and release
receipt there rather than interpreting this candidate audit as merge evidence.
Later documentation or integration commits do not inherit a claim of having
built the original bytes. No GPU, paid compute, P3 infrastructure, no-Git installer,
new game support, all-family coverage or scientific result is claimed.
