# Unified task-flow bounded acceptance — 2026-09-16

## Decision and scope

The bounded Human recording-control and Close-to-cloud journey is accepted for
this exact macOS combination, with **one retained expected Close-tail unknown**.
The shared Hub and fixed local Workbench are deployed. Source integration and
formal publication are separate facts: [PR #10](https://github.com/rsgcsg/STS2-The-Perfect-Defect-Project/pull/10)
and the eventual release `integration-receipt.json` record their exact refs/CI.
This record does not describe a zero-failure Human gate or a complete run.

The change unifies daily collection, local model preparation/control, shared
project data and selected-decision dataset unions. Existing permission, consent,
Recorder, evidence and execution owners remain authoritative. Model control has
portable regression evidence; this Human session is not a native model handoff,
recovery, Auto-play, victory or model-quality qualification.

## Exact combination

| Item | Identity |
|---|---|
| Task base | `develop` / `ea9447212f4f4ae317dfe4dd6a391cb7ed34c16d` |
| Workbench / Hub source | `f4a21a2d67392b557c593cd396b894d1c3439779` |
| Python lock SHA256 | `e6de3786b473f3ecf1fa17f43f6fe87b82bcc45ec5fdafa4119211fe831b96d6` |
| Developer-kit ZIP SHA256 | `95155208caaf76f7128c19eefdfad28dab5363f2a20d45a43cb718b8cd6a008b` |
| Native/tool build provenance | `08d9a37c45362a3421e6f52be851541202a5fc8e` |
| Collection Tool ID | `f71c5dc2ce988d3bc16d3dcf72c717b4e5f174fe78ed01138afa5a133091f4a7` |
| Mod SHA256 | `a095db081549fa46a616ff10bc58ad65f87d92f303800963409f5c78340b762c` |
| Mod MVID | `c3cf59cc-5000-44bd-8f98-ce59578f05c8` |
| STS2 | macOS, `v0.111.0` / `41cef1ea` |
| Game assembly SHA256 | `9cb4f1ad8c9f284aa8fec3122ffd6d780bbf543d875c817abdd12ff63fbf12b4` |
| Game assembly MVID | `57785517-0b16-42b9-8b36-bad6fb28384b` |
| Hub image | `ghcr.io/rsgcsg/spireagent-hub@sha256:8ddb8fb36d677cfadd20ed413c3a2ba52081ce0abf808c459c3e17a073c3016a` |
| Evidence dependency | `0.1.0-rc.10`, source `5e8f39dea38cfd68e7605ba6194400ac60cad5df` |
| Policy Runtime dependency | `0.1.0-rc.4`, source `280af4500df298c4b84bfe627472c16ed32388d9` |
| Runtime tarball SHA256 | `760f9054aef7dbecedc53f61138c3667e376c742046e81f3bd62cb83163936d6` |

The [sealed candidate kit](https://github.com/rsgcsg/STS2-The-Perfect-Defect-Project/releases/tag/candidate/task-flow-final-20260916)
was downloaded independently and matched its published ZIP checksum (3,163,321
bytes, 20 entries). It was initialized in a permanent independent release clone.
Later evidence/documentation commits do not rebuild or relabel these native bytes.

## Source, package and local lifecycle evidence

- Exact `f4a21a2` root `npm run check`: PASS, including 937 Python tests, three
  skips and 21 subtests, Evidence 104 tests, Runtime 62 tests, type checks,
  package builds and CPU E2E. Closeout and diff review passed.
- [Exact source CI run 35065784745](https://github.com/rsgcsg/STS2-The-Perfect-Defect-Project/actions/runs/35065784745):
  Linux, Windows and final portable gate passed. Later PR/merge checks must still
  pass on their own heads; this run is not their receipt.
- Exact-game/native build passed at the native provenance above. The owner
  installer deployed those bytes with the game closed at 06:50:21 UTC;
  cold launch, loaded identity and local doctor passed. Previous Mod/config
  rollback is retained.
- Desktop/mobile synthetic UI checks passed with no JavaScript errors or
  overflow. Actual authorized local UI showed collection ready/upload enabled.
- The owner selected and personally approved the existing Hotmail profile.
  A second profile on the same physical computer remains preserved and stopped;
  display names are not hardware identity. No cross-account device takeover or
  raw-data transfer occurred. Existing consent was reused.
- Two old completed deliveries were independently verified before retiring their
  legacy delivery pointer. Raw sessions, old tools and outboxes remain intact.
  The active service was restarted through its owner after completion proof.

## Exact owner-operated Human session

Session `session-20260916T070936Z-026a2cc45b24448e9c09d02e2eb7c03c`, runtime
`8397f54fee4542208c520fd1a57d1f57`, timeline
`timeline-613409a60abd4f8da8ccf1cdd57b10d6` used the identities above and capture
profile `human-full-run-read-rich-v4`, SHA256
`1ed42e6709aaa46b9d38f2f72ce778e731d17aee3f06bf0153ea369b936ff459`.
The owner reported completion; the Agent did not perform gameplay.

The independently invoked published Tool verified its complete inventory and
passed structure, calibration and native-semantic audits. All 176 raw file
hashes were unchanged before/after audit. Raw material and detailed reports stay
in authorized private storage; only this bounded summary is public.

| Fact | Result |
|---|---:|
| Accepted actions | 44 |
| Proved / durable canonical | 43 / 43 |
| Canonical roots / nested selectors | 39 / 4 |
| Successor unresolved / owner real-failure count | 1 / 1 |
| State/action-space unresolved | 0 |
| Capture or persistence failures | 0 |
| Compatibility valid / invalid | 14 / 0 |
| Diagnostic invalidations | 6 |
| Native diagnostic successful / exact-once / unknown | 35 / 35 / 0 |
| Pause / Resume | 2 / 2 |
| Close requested / closed / durable receipt | 1 / 1 / present |

Canonical families: play-card 27, end-turn 5, reward-claim 3,
reward-replacement 2, proceed 2, map-travel 2, combat-hand-selector 2.
Compatibility projection omission of 29 decisions is not loss of 29 canonical
rows. Diagnostic invalidations are not counted as failed actions.

The final accepted End Turn (`game_action_bc7bfd51_63`, action 44) committed at
07:11:01.109415 UTC. Close arrived at 07:11:03.044537 before a successor boundary;
`session_closed_before_successor_boundary` was durably recorded as unknown.
The journal closed and durable Close receipt followed. The last resume preceded
this action by about 42 seconds, with intervening normal actions.

This is the existing immediate-Close contract in
[Annotator architecture](../../components/annotator/docs/ARCHITECTURE.md)
and `RecordingApplicationTests.CloseIsAnImmediateTerminalBoundaryEvenWithPendingWork`
regression, not a missing evidence write or an unexplained attribution failure.
The unknown remains in raw data, quality counts and admission exclusions. Nothing
is backfilled or reclassified; the real-failure count is **not zero**.

Only `run_observed_in_progress` and `run_resumed_native` boundaries exist.
There is no native start or terminal, so the session is an incomplete fragment.
No complete-run, zero-failure G5, training-admission or scientific claim follows.

## Close, cloud receipt and member byte readback

- Upload/receipt: `a9b79d80140c1dcf0912af0869fc7504`, verified, empty findings.
- Content: `304bf4ce02202bf0334878a1d0992aa92cb13f94819b5e4ebaae34d09aab5d2b`.
- Stored evidence: `9d7f4f0aca3eef5124b28bdedb8c373fb5cd52dbf846f0ebcd003ea7e8706c81`.
- Transfer manifest: `dc0144ba536cc5b5a2906351d59a4d393dd4b7b518a32d72a8f8df96b76cab33`.
- Downloaded archive: 250,573 bytes, SHA256
  `20f4d90c0384772bd0f7f8ff0dd38e0f056519016c1beab6ae52d8739535da40`.
- Member export: `3f5434a9b35881363a9ecbfafd1fc3a22ce21973335db0d70d2b7b64910bc474`.
- Completed-delivery proof:
  `e76f6f729e89245aa956ec4b311c684fcfb057304044ac3c3a58055adeca48d1`.

The authenticated device independently fetched the remote receipt and matched the
local one. The member export/download owner verified one file; an independent
SHA256 comparison matched the local transferred archive. The stopped-worker
completed-delivery owner validated entry and exit snapshots. Verification here
means immutable transfer/integrity, not that every decision is a valid label.

## Hub deployment and recovery evidence

Reviewed rollout plan SHA256
`741858e26959eb29e64e25b758e2820ae13333933985743588967b5f8129435a`
changed only the Hub image, with schema 4 and compute budget 0 unchanged.
The isolated candidate image passed source/lock/dependency identity, health,
static assets and expected unauthenticated rejection. Production HTTPS, loaded
producer identity, authorized member views, collections/datasets and conditional
R2 immutable write/readback passed. Both Hub/TLS containers and all persistent
bind sources were checked. The backup timer is active; dispatch remains paused.

Predeploy off-host backup `225e7be0d0582e971fb3677099849559a43422cda17be7722a27fb9139f20323`
and isolated paused restore passed. Postdeploy backup
`92629bff80a6914b4671c1241b5e7ebe18974559119f54e45c6c4a62d1232d0e`
and independent paused restore passed (restore SHA256
`3ba903422c0c7c9a3dd898489c60582d1845daee7091d262b9868dd7a4c89da5`).
After the new Human upload, backup
`81d1ad6df51e53b573fae20e05a4104ad3f1f96fd6d02e5f5ac571c2ddd32193`
succeeded at 07:14:57 UTC under the deployed image.

## Rollback and limits

Retain the previous native installation/config rollback, fixed tool directories,
credentials, consent, raw data and queues. Source corrections use a new PR.

After dataset unions have been persisted, **do not blindly use the automatic
previous-image pointer**: the older `25777cb` / image `9271a619…` cannot read
those requests. The retained functional Hub fallback is source `08d9a37…`, image
`ghcr.io/rsgcsg/spireagent-hub@sha256:394026d82e146813fce03fe26e7a3d470df5087c435eca7f0c18eaf08a1b8e7e`,
with an external matching configuration and isolated smoke evidence. It shares
the persisted union contract. This is not a qualification of rolling the entire
local stack backward. Never restore an old live DB merely to roll back UI/code;
preserve new uploads, revocations and unknown jobs.

No paid compute, new training, AI gameplay, macOS CUDA support, universal game
compatibility, Windows/Linux native installation, model outcome or production
throughput is claimed. PR #9 is an independent Windows inventory-order fix and
is not included here. Historical evidence/releases are unchanged. Publish the
same verified kit bytes, not a rebuild at a later documentation or merge SHA.
