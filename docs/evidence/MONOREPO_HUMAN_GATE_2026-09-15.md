# Monorepo migration Human acceptance — 2026-09-15

Verdict: **MIGRATION_HUMAN_GATE_PASS** for source
`45ef463e3c13cd82db55601c122a292c37aaae2e`. The owner reported completion of
native Human testing. Machine checks establish evidence integrity and lineage;
they do not independently prove who operated the game.

The machine-readable [qualification](../../migration/human-qualification.json)
contains counts, families and immutable content/receipt hashes. Raw data stays private.

## Native recording

Session `session-20260915T105448Z-6b885bfbe1bc4f028f563da4ec0a2782`,
10:54:48–11:11:40 UTC, closed with a durable native Close receipt.
580 accepted decision occurrences: 499 roots and 81 nested selectors. All 580
proved and canonical; all 81 children join an exact canonical parent/root.
Zero real failures, unresolved, cancelled, aborted or unsupported occurrences.
Compatibility rows: 196 valid / 0 invalid (a subset, not the total decision count).
2,062 materialized Reads, zero failed Reads. Native semantic diagnostic:
415 exact memberships / zero unknown, 27 matched pause/resume pairs.

72 explicit invalidations remain unchanged: 44 `ReadyToBeginEnemyTurnAction`,
28 `MoveToMapCoordAction`, all `human_action_native_type_mismatch` with authoritative
`diagnostic` disposition. RecorderRuntime.WriteInvalidation explicitly classifies
these internal native actions; they are not lost independent Human decisions.

Run 1: native start and natural defeat, 190 canonical decisions. Run 2: native
start, 390 canonical decisions, no terminal before Close; it is incomplete.
Two uploads or two assigned runs must never be reported as two completed games.
Manifest historical/non-claim fields are not rewritten by this audit. No unseen
family, arbitrary game version or all-future-input guarantee follows from this run.

## Transfer and member access

The deployed fixed Collection Tool sealed the session automatically after Close.
Producer audit and independent Evidence bundle-3 verification both passed.
Cloud receipt `ce84ef2f75e3a6d231dd4bc2bebc0c84` is verified with no findings.
A member selected that new collection and downloaded its 3,275,812-byte archive;
it is byte-for-byte identical to the local uploaded archive. This is a new Human
recording, not a reuse of historical evidence. No research/training admission is granted.

## Exact engineering candidate

- Local complete root gate PASS: Python 755 passed, 3 skipped, 21 subtests; native/component gates passed.
- Hosted Linux, Windows and portable PASS: [run 34954599730](https://github.com/rsgcsg/STS2-The-Pefect-Defect-Project/actions/runs/34954599730).
- Exact-game/build/install/cold-load PASS on macOS arm64 game v0.111.0 / 41cef1ea.
- Mod SHA256 `1a8072e02d2c0721bab9f33794302c49181853befdb931881407217af780a001`, MVID `0d5931ad-a7bb-405c-a7d0-200ed18b7443`; native bytes are preserved, packaging/tool/application provenance is new.
- Collection Tool `9a293774b0ac4664bd0cb78dedb2ea09e5185b7c653724811c4c7c0b073e0633`.
- Developer kit SHA256 `14b33ceab0dfe637f53bac1f6e50a05f660fb59dd7cdd382ba0fa16adf572aa7`, also verified by release download.
- Hub OCI `ghcr.io/rsgcsg/spireagent-hub@sha256:8c8c91ccce916483486834d054d23319c3b08c998cc71bc9a42e95ebb12a6c9c`.
- Python lock SHA256 `5f228ae57b5b8610dfd7977a6b465ec391b01eea933c2c80ad87ffb126566ba7`.
- Isolated old-database restore, real R2 conditional write/readback, exact HTTPS producer, unauthenticated rejection and member access passed. Old/new-producer off-host backups were restored into separate paused files. One production Hub remains active, backup timer active, compute budget 0.

## Integration and recovery

[Migration PR](https://github.com/rsgcsg/STS2-The-Pefect-Defect-Project/pull/1)
records final integration and merge-head CI. This report seals the deployed candidate;
later docs/merge refs do not rewrite artifact provenance. No further native code
change was needed from this Human test.

The prior host checkout/image/config and local owner-generated Mod/config rollback
remain available. Do not restore a DB solely to roll back application code. Keep old
release dependencies and raw sessions intact when retiring source repositories.
Imported dependency alerts remain tracked in GitHub, mainly the optional MCP transport;
this gate is not a blanket security clearance or a qualification of an undeployed GPU worker.
