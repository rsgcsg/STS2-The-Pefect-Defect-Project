# Local collection task flow

The Workbench `CollectionFlow` composes the existing Hub consent, `CollectionSetup`,
native tool and application activation paths. It does not create recording evidence,
infer Human origin, launch the game, replace a tool, or reclassify an upload receipt.
The same collection remains bound to its original device, consent and outbox.

## Application interface

The loopback application constructs `CollectionFlow` with its existing `CollectionSetup`
and three callbacks: current delivery process status, `activate_collection(enrollment_id)`,
and stop delivery. The application retains process/configuration ownership and its operation
lock. The existing browser cookie and Origin/CSRF boundary protects all writes.

| Operation | Input | Result |
| --- | --- | --- |
| `status()` | none | `stpd/local-collection-flow-v1`: stage, next action, current native preparation, current default notice and upload preference/process |
| `consent()` | exact displayed `template_id`, `accepted: true` | Existing Hub enrollment and `human_origin_verified: false` |
| `prepare()` | `{}` or an absolute `game_directory` | Owner-derived current flow state after completing safe preparation steps |
| `set_upload()` | `enabled: false` or `enabled: true` | Persistent pause or authorized preparation/resume result |

One clearly labelled consent button can replace the three checkboxes. Its displayed notice
must cover Human origin declaration, upload and project-member sharing. The action accepts
that exact displayed template; a changed default requires the current notice to be shown.
Hub still owns and records the existing declarations. A click is not evidence that the
recording originated from a Human. Opening, refreshing or signing into a page grants nothing.
Duplicate submission returns the same enrollment and cannot undo a subsequent pause.

Preparation resolves the already-consented local enrollment, creates its inactive files
through the existing owner, inspects native state and binds the recording root only when
the native owner offers that action with the game stopped. A manually supplied directory
also goes through the native guard. Missing installation, a running game, or required cold
load remain explicit next actions; neither time nor a saved flag implies readiness.
Activation uses the application's existing fresh native proof and delivery preflight.
After interruption or restart, repeat preparation to read the already published owner state.
It cannot replace the active outbox with a newly recommended default or newly registered tool.

## Durable upload preference

`collection-upload-preference.json` is private local configuration, scoped to Hub and device.
It is the only new durable fact: whether this computer is permitted to automatically upload.
It is not a second queue, consent ledger, readiness record, or receipt. The file has exact
schema `stpd/collection-upload-preference-v1` and fields `hub_url`, `device_id`, `enabled`.
An absent preference preserves an already configured legacy uploader. A malformed preference
or device/Hub mismatch fails closed. Every application `start_delivery` path must read this
preference, including process restart, old activation routes and authorization recovery.

Pause persists `enabled: false` before stopping the existing delivery process. The caller
serializes process start/stop under the existing application operation lock. A stop failure
is an error, not a confirmed pause of a still-running process, but the durable preference
prevents a later restart from re-enabling upload. Partial transfer may already have reached
the receiver before stop; pause does not erase those bytes, receipts, or pending rows.

Pause works without contacting Hub. Resume requires current member access to the same
enrollment and a fresh check of the same device authorization. It then uses the existing
native preparation/activation checks. It does not turn an `auth_blocked` queue row into pending:
after authorization is restored the existing explicit `resume-auth` owner remains responsible
for checking original seal, bundle, transfer and upload identity. Unknown game delivery is
never retried by this flow.

This preference stops subsequent automatic upload work. It does not revoke historical
sharing, delete cloud objects or retract members' downloaded copies. Those remain separate
Hub operations. Personal logout retains the device grant and does not silently change this
preference. Removing a member/device still prevents Hub requests and cannot be undone here.

## Regression scope

`tests/test_collection_flow.py` composes the real Hub declaration and local preparation
code with explicit native/service fixtures. It covers a single consent action, stale notices,
duplicate requests, stopped-game binding, uncertain owner state, fresh activation, persistent
pause, offline observation, stop failure, device revocation, incompatible preferences and
reopening. Existing setup/upgrade and Evidence tests remain the authorities for the exact
queue, sealed-session, receiver and generation rules. These tests do not qualify a real game,
Human provenance, deployment or uploaded Human data.
