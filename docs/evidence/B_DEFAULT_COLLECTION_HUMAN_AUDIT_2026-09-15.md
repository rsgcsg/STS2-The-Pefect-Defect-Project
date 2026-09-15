# Daily collection candidate: actual member recording audit

This records a real new-member test of the daily-default workflow, not a Full-Run PASS
or a training-admission decision. Historical failed evidence remains immutable.

## Exact tested candidate

- STPD source: `d478ec1008d7cabe3e5fcd9a0058a17a84f1023c`.
- STPD lock: `7554dbc9b88c1f828e9f08ed96520c53ba59d09ae0e07d6227de227556ab7138`.
- Platform workspace: `0cd01132b6bd056f0035d5a42b5d9ec4b322928d`.
- Fixed tool release: `00b0f68aab4cb8b927087bb60d8100f81dd9fefd54e3239e6336469a4d3ad639`.
- Native Mod SHA256: `38210d6d5c670aa5e06edf93d0da9632e6ed59b743d8859d027d297faf6abc95`;
  MVID: `6572eae4-75f3-44db-9e6a-4b2feebbee07`.
- Exact game: v0.111.0 / 41cef1ea, assembly SHA256
  `9cb4f1ad8c9f284aa8fec3122ffd6d780bbf543d875c817abdd12ff63fbf12b4`.
- Hub OCI: `ghcr.io/rsgcsg/stpd-worker@sha256:fc7c49e3f1ee82165adcdef58d115fa742cec523baad26cfb6553ca6789ff83a`.

The member explicitly confirmed the daily v2 Human/upload/project-sharing declarations.
The actual session began with a native run start and closed at the beginning of act 2.
No automated gameplay supplied the recording. All 932 raw files retained their sizes/hashes
through the read-only audit. Personal identifiers, raw data and credentials stay private.

## Recording results

| Owning fact | Count |
|---|---:|
| Accepted decisions | 270: 234 roots and 36 children |
| Proved / canonical | 269 / 269 |
| Real failure / unresolved | 1 / 1 |
| Canonical children with canonical parents | 36 / 36, across 22 parents |
| Native semantic exact / unknown | 184 / 0 |
| Compatibility records valid / invalid | 99 / 0 |
| Explicit invalidations | 45 diagnostics |
| Native starts / natural ends | 1 / 0 |
| Capture / persistence failures | 0 / 0 |

Canonical success was 99.6296% of accepted decisions. This denominator is observed accepted
decisions, not proof of exhaustive Human-input coverage. The compatibility projection is a
smaller historical view; its 99 rows are not the Full-Run canonical denominator.

The 45 invalidations are all `human_action_native_type_mismatch` diagnostics: 28 internal
`ReadyToBeginEnemyTurnAction` and 17 internal `MoveToMapCoordAction`. They do not represent
lost Human decisions. All 121 observed PlayCard, 41 End Turn, four potion and 36 nested
decisions were canonical. Unobserved surfaces and all possible rapid inputs remain unqualified.

The sole loss was the final event Continue. The native option committed successfully and
synchronously opened the map; the Recorder lacked this exact event-to-map owner-ready
observation. Closing 3.44 seconds later honestly left the decision unresolved. Five event
Continues exercised this path; the preceding four settled only at the next Human pre-execution
boundary. Platform owns this source defect. STPD must not fill its successor from a later
Snapshot, reinterpret Close, or convert the failed archive to a passing one.

Native ends zero is expected for this partial run. The player remained alive on the act 2
map. Recorder Close is not a natural run terminal.

## Delivery and member access

PASS: automatic Close discovery, fixed-tool packaging, local durable outbox, Hub receipt,
complete R2 reads/hash verification of all four evidence roles, exact enrollment/device/consent
association and project-member sharing. The archive was 1,465,315 bytes; member export/download
independently matched SHA256
`24c88f87b1bdbd498f31e7fe61898e251b51c8fa7d8f9bc558093335ebd95853`.
Stopping and reopening the same workbench preserved the single terminal delivery identity,
receipt and attempts; no duplicate upload or new enrollment was needed. Compute remained zero.

The remote verified receipt can precede the local uploader's next scheduled status observation.
That transient pending state is expected asynchronous delivery, not a failed recording.
Cloud acceptance verifies evidence transfer; a bundle containing an honest recording failure
can be accepted without being admitted to training or passing a Human all-valid gate.

## Repair and promotion boundary

Source follow-up addresses the native event Proceed observation, the setup helper's incorrect
interpretation of a closed Recorder's retained session ID/root, and local detail's omitted
verified cloud collection-purpose field. Native source repair requires a new exact candidate,
cold-load and fresh bounded Human evidence. This report cannot qualify those later bytes.

Reproduce with the tested fixed tool's `audit` and `audit-native-semantic`, preserve the raw
inventory, compare exact Hub/R2 payloads, download the member export and compare bytes, then
stop/reopen the same profile and compare durable delivery IDs. Private read-only cloud report
SHA256: `17ca7f32f2e5fe8d3228c4a3d20cc6cfbf09a33159ed86a1436e3ac9e3decef3`.

Do not promote this candidate as zero-failure Full Run. A new canary must cover event Continue
to map followed by Close without another gameplay input, plus the repaired setup status.
An uninterrupted native start through natural terminal is a separate outstanding Full-Run gate.
