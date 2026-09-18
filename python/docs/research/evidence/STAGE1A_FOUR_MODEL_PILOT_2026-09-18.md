# Stage 1a four-configuration engineering pilot

All four configurations completed ten updates on the same public-compact model view
`2553accb6bf393809f0f813f94f73a1ccd266cdb6824a38e1591b1a1ebd478fd`.
49 eligible train decisions feed the fixed plan; dev has 16 decisions from one
independent run. No test/Gold labels or game actions are used. This is a pipeline
and comparison check, not architecture selection or evidence of pretrained advantage.

| Configuration | Top-1 | n > 1 Top-1 | NLL | Worker attempt including dev |
|---|---:|---:|---:|---:|
| `stage1a.dsimple.s.v1` | 8/16 | 6/14 | 1.720264 | 9.769 s |
| `stage1a.dsimple.pf.v1` | 4/16 | 2/14 | 1.721246 | 76.375 s |
| `stage1a.b.pf.v2` | 6/16 | 4/14 | 1.714594 | 166.611 s |
| `stage1a.b.s.v2` | 3/16 | 1/14 | 2.362603 | 8.853 s |

The B-S wrapper took 32.818 seconds (CLI 31.584 seconds including input validation).
Its worker attempt was 8.853 seconds. Different scopes must not be conflated;
research preparation, prior failed/paused attempts and validation are additional cost.
The comparison verified exact result closures and common dev identities.

## New B-S artifacts

- source: `5a4bdaddb9c5b9bc42966dbd72de58054c308384`
- run: `b795dba9af1633b72cbf7aad4b60d9fb2112c2d826acd3aa5c54b969ef4a3fb8`
- checkpoint: `12813d4179a0af2a079202100d4111e9484228c692946cdd19b46bc75915181d`
- result: `f3176e481b3a0f6ae688a47a708bd17e256c6b0eb51eafaccb867d1bff75d064`
- model: `01b60f59b01db98021c26fc77f45094c5fa3358b4923231a6836699317abb307`
- evaluation: `9512b1848b16c6cce05019db617bf910243eb9de6aac7d06a1203b774685786c`

Private evidence directory: `stage1a-packed-b-s-20260918-213508` under the research
root. The model export is `stage1a-exports/b-s-packed-v2`.

Checkpoint/published weights were byte-identical. The independent scorer loaded in
0.0646 seconds and scored the 18-candidate snapshot in 0.3362 seconds, without loading
Qwen. Its original-order scores exactly matched the restored engine. Candidate
reversal passed `atol=2e-5, rtol=2e-5`, with maximum difference 5.3644e-7. This is one
snapshot timing without repeated latency statistics, not full-game latency.

- Comparison receipt SHA-256: `13ac5a2f7f9ad59332fe182ea2d847418482f456ce8992a9c8e720358971cbb1`.
- Export receipt SHA-256: `02055edbcbdb3a41622a3e8f9fff2d450075abd6ff476821a9e1dce227fa832f`.

## Game-entry integration work

An additive trusted `token-v1` adapter now connects public snapshot exports to the
existing decision-only NDJSON protocol. Workbench supports an operator-created local
catalog alongside shipped S1; its commands and Runtime package remain fixed by code.
No model has yet been registered for actual native use. Existing S1 support is unchanged.

Focused token-port and Workbench tests passed (101 tests, followed by 16 token-port
checks including an additional no-ML-import regression). A private new-process test
produced ready and a complete 18-score decision from the real B-S export. Public
TypeScript consumer verification is pending: the active worktree had no installed
tsc/dependencies. The dependency/build, consumer and full Python gates will run as
one durable, separately monitored job. No native game qualification follows from these
source, export or protocol checks. Local registration with current game identity,
Workbench/Mod loading and Human/Stop/model-switch controls remain outstanding.


### Integration-check environment failures and isolated-fixture repair

The exact source `c69d59c9210b7e8a7dc1eaa8f5e0591127510b0f` passed the real-export
public Runtime schema check and the Platform portable suite. The first job omitted
the interpreter bin directory from PATH; its retry fixed this but Python's isolated
import test correctly found the borrowed s0 environment still installed the old
worktree. These are retained failed attempts, not successful full-gate receipts.

A dedicated stage1a environment was created from the unchanged lock. Isolated
imports and the real B-S export/TypeScript consumer check passed. However, exporting
`UV_PROJECT_ENVIRONMENT` over the entire job redirected the offline cloud-refresh
fixture's nested `uv sync` into the caller environment. It replaced the caller's
installed dependencies, causing 110 failures and six setup errors in the remaining
suite. This was an environment-isolation failure, not 116 independently diagnosed
model failures. Training artifacts were not an installation target.

The job-wide override is removed. The synthetic refresh fixture now strips that
override and `VIRTUAL_ENV` from its own subprocess environment. A new offline
regression injects a foreign target, performs both dependency versions in the
fixture clone, and verifies that the caller target remains untouched. The cloud
refresh, isolated import and packed-model regressions passed together (28 tests),
then isolated imports of the current worktree, Torch 2.13.0 and Transformers 5.15.1
still passed. The original test assertions remain intact. A complete Python gate
on the repaired source is still required; prior Platform evidence retains its own
source identity, and native registration/game qualification remain outstanding.

Private failed attempts: `stage1a-integration-check-20260918-214945`,
`stage1a-integration-retry-20260918-215115`, and
`stage1a-python-env-check-20260918-220513`. The last directory retains the successful
new-environment real-export contract receipt as well as the failed overall status.

### Repaired full Python gate and local registration preparation

Source `e5f925b101256ec584ebb90e35a0c86b2cbe36c4` passed the complete Python
portable gate from its own locked environment: 1,122 tests passed, three skipped,
21 subtests passed; lint, typecheck, engineering checks and wheel/sdist packaging
also completed. Total job time was 133.421 seconds. The private receipt is
`stage1a-python-gate-20260918-221415/status.json`, SHA-256
`4cd716f1b771dcfd6ebc3eb72478c5d5744cb10a5a5101e12ca12bd0cc33ac7e`.
The earlier Platform pass remains bound to `c69d59c`; this is not hosted CI or
native-game qualification.

Four private token registrations now point to the verified exports and current
observed native environment. The loaded Mod SHA/MVID match the retained curation
acceptance artifact (`52bcd795…ae0e`, `9db537ec-840b-4e2e-aa85-bea9fab6f4f1`).
Registration admits only whole `combat_turn` decisions containing `play`, `use`
and `end_turn`; no candidates are removed to fit this scope. Broader game surfaces
remain unsupported by these registrations. No full-run support is claimed.

The current game process reports `artifact_unqualified` and
`execution_available=false`: passive observation is available, model actions are
not. Its recorder is Ready with no open session. A cold launch through the owning
Game Mod lifecycle is needed for explicit exact-source execution admission. Do
not weaken compatibility checks or rebuild an unchanged Mod to hide this state.
The running released Workbench has not yet been switched to Stage 1a source;
pinned Runtime installation/readiness, Workbench load and game controls are next.

### Cold load and B-S Workbench load

After the owner closed STS2, the retained exact Mod's lifecycle launcher cold-started
the game without replacing its installed bytes. `verify-loaded` passed; Connector
reported `canary_exact` and `execution_available=true`, runtime instance
`343a26af3a704d028e520edff2dd78ef`. This is process-local exact-source canary
admission, not new general artifact qualification.

Workbench was gracefully restarted from source
`07d82eb9b5c49096d196e9c32028d5c63e203edf`, using the same project configuration,
account state and delivery queue. The pinned Runtime rc.4 installation passed all
four registration readiness checks. An initial B-S load in Human mode was stopped
before any decision; the cold process's changed observed Modset fingerprint was
bound in new manifest files, preserving the prior files. The second B-S load passed
the actual Workbench prepare/load and adapter attestation path:

- Runtime run: `run-4595d3c0-3298-431a-b412-221007898cbb`.
- Manifest: `stage1a-b-s-live-pilot-20260918-36df5154`.
- Runtime code: `0a436e79dab4833223a6fb9b3ccd9ba600111f44cd5b9d119b32ebe46aa071ec`.
- State: loaded, Human mode, controller released, untainted, no Runtime errors.
- `/v2/environment` confirmed the same game instance and recovery epoch 0.

Private evidence: `stage1a-live-load-20260918-222647`; loaded-status SHA-256
`3b52b8617c937b271dda2c7e8bbee92c845679ff345565dce38892162550a8d1`,
environment receipt SHA-256
`7cd59d07b40bbd188e28333a0fe4413add8c23ea7f26ab169dea14ba974e522e`.
The browser was opened to the model page; automated visual inspection was unavailable.
No native model decision has yet been executed. Game UI visibility, one-step delivery,
pause/recovery and model-switch operation remain pending user-assisted acceptance.

### Owner-triggered Auto attempt: bounded delivery, unresolved integration defects

The owner subsequently reported completion and poor interaction flow. The same
run's raw log has 22 events: four decisions and four receipts, three `delivered`
(two card plays and one end-turn) and one `not_delivered` because the exact snapshot
changed. These are directly inspected producer records, not a passed evidence
verification or settled causal-transition claim. The log records two Auto entries,
an `action_not_delivered` handoff, a later `successor_not_stable` taint, Human mode
and Stop. Do not call this successful continuous control or complete Stage 1a.

The installed Evidence verifier rejects the run with `schema_keys`: "receipt
successor read contains unknown or missing fields". Preserve its raw bytes; inspect
the current public Read contract and reader version before any repair. Workbench
also records a subsequent failed load with `runtime_port_already_in_use`; current
inspection finds no listener. Inspect stop/restart port lifecycle rather than asking
the owner to repeatedly reload. No automatic retry or untaint was performed.

Required follow-up is owned by Runtime/Connector lifecycle, Evidence contract
compatibility and Workbench restart handling respectively. The in-game interaction
requirements are recorded in the root UI specification. No new training, release,
UI deployment or full-game support is claimed by this follow-up.
