# Project Development Workflow

The single active repository is `rsgcsg/STS2-The-Pefect-Defect-Project`.
This is the one owner of branch, release and deployment coordination. Native installation,
cloud commands and research admission remain in their focused guides; do not copy new
versions of those procedures into campaigns or incident notes.

## Branches: integration, publication and work

| Ref | Purpose | What it does not do |
|---|---|---|
| `develop` | shared integration of reviewed changes | automatically deploy a Hub or update collectors |
| `main` | reviewed release/integration record | claim that every running machine executes its latest SHA |
| one short-lived topic branch | one task/repair and its PR to develop | become a permanent component or engineer branch |
| temporary `release/**` or `hotfix/**` | prepare an explicit main promotion or urgent correction | create a second long-lived development line |
| immutable release tag / exact artifact | an identified distributable candidate and its evidence | silently follow a branch or overwrite an older artifact |

Main and develop are the only long-lived branches. Fetch/prune and inspect status, exact
refs and open PRs before work. Start normal work from current origin/develop, with one
writable branch/worktree per writer. Never edit the running collector checkout, direct-push
main/develop, force-push, bypass required CI or reuse an already merged topic branch.
Root AGENTS.md and Engineering Governance own G0-G6; historical STPD classes are not a
second governance system. A PR may cross components when one causal change requires it.

## Normal change and release sequence

1. Create a topic branch from current origin/develop; record exact base/head and owner.
   Implement the first owning correction, add the cheapest faithful regression, run the
   relevant component/root gates, closeout and diff review. Open a PR to develop.
2. Review the latest head and its Linux/Windows/portable CI. If integration requires a
   newer base, merge that base into the topic branch, review conflicts and revalidate.
   Use a normal merge commit for any component source change; docs-only squash remains
   permitted by root policy. Preserve path-scoped component provenance.
3. Merge the reviewed PR to develop and verify the actual merge-head CI. No service is
   deployed merely because that merge happened. Several compatible improvements may be
   grouped into one intentional release; do not make every commit a user update.
4. When promotion is intended, create a temporary release branch from the exact selected
   develop commit and open a PR to main. Merge current main into that release branch if
   needed for strict up-to-date rules. Review the final diff and latest checks. If main
   contains a hotfix absent from develop, first reconcile it through a PR to develop;
   do not allow independent implementations to diverge.
5. For changed executable artifacts, build one immutable candidate, qualify affected
   build/install/runtime/Human/cloud boundaries and retain rollback before recommending
   promotion. A docs-only release needs source/doc checks, not a new Mod, image or canary.
   An explicitly authorized candidate deployment stays identified as a candidate until
   its own gate passes. Never use a failed Human gate as a green release receipt.
6. Merge the release PR normally and verify exact main CI. If stabilization/hotfix changes
   occurred only on the release/main line, synchronize them back to develop through a PR
   and check its merge head. When main/develop trees already match, a merge-only ancestry
   difference does not require an empty synchronization PR.
7. Publish the same verified bytes and their source/lock/artifact/compatibility/rollback
   receipts. Download and verify the published files. Delete only merged temporary
   branches after checks; retain detached runtime/evidence worktrees and historical tags.

Urgent fixes start in a new hotfix branch from the actual affected release/main ancestry,
use a PR to main and then a PR to develop where needed. Emergency authorized pause/revoke/
rollback may contain an incident, but direct host edits are not the final repair: follow
with an owning source/config-template PR and regression. Preserve evidence throughout.

## One source repository, independently pinned running components

Use a development worktree for changing code and a durable detached release worktree for
collection. The Hub runs an exact OCI digest and external private configuration; workers
are independently selected profiles of the same codebase. Models are separate immutable
artifacts. These components may run different compatible release SHAs. Equality to current
main, to another computer or to the Hub is not a general compatibility requirement.

| Thing | Normal update boundary | Evidence to retain |
|---|---|---|
| docs/governance | reviewed PR and main promotion when desired | source/CI; keep working runtime producer unchanged |
| local Workbench | deliberate application release, owned process stopped | old/new source+lock and private configuration |
| Mod / fixed collection tool | affected native/tool compatibility and explicit upgrade | game/Mod/tool identities, old queue/tool, cold-load and affected canary |
| Hub | operator schedules a compatible immutable image rollout | old/new image/profile/config, schema, backup and service receipt |
| worker/provider | separate compatible worker qualification and authorized budget | producer, input/job/attempt/checkpoint and provider result |
| model | explicit artifact/adapter/environment admission | weights, representation, support, training/evaluation identities |
| dataset | new immutable selection or derived version | original bytes, policy, included/excluded IDs, dedupe and split |

The current Python producer records an exact whole-checkout SHA plus lock hash; native
component identities are path-scoped. Do not confuse those provenance schemes or rewrite
an installed producer because documentation changed. A source edit to docs inside python/
does not require rebuilding or restarting a healthy deployed executable.

## Compatibility and update policy

Record versions and exact origins; decide compatibility using the actual public contracts,
capabilities and affected native facts. See [Versioning](VERSIONING.md). Do not invent a
second compatibility database, infer arbitrary-version support or remove existing exact
native/queue checks to make a mismatch disappear.

A working qualified installation stays pinned until an operator chooses an update for a
needed capability, an observed compatibility failure, a correctness defect or a security
issue. Review dependency/security findings at a regular team maintenance checkpoint and
before releases; triage urgent exposure promptly. Do not run automatic dependency upgrades,
`npm audit fix --force`, restart loops or client self-updaters as a substitute for review.
There is no blanket promise that old software is safe forever or that updates cannot fail.

A game update does not by itself require updating Hub, research, all models or all users.
First inspect the actual native load/read/action/recording compatibility; an unsupported
native check remains blocked until qualified. A model/record format change affects consumers
that use that contract. Data from multiple versions may be selected only under explicit
compatible semantics and recorded policy; a code-version mismatch alone is not a reason
to delete data. Schema IDs, hashes and lineage remain immutable.

Software-only changes do not create another member, device or daily consent. Changed
purpose/sharing requires explicit consent under the owning collection policy. Existing
outboxes retain their original tool; completed-queue generation rollover uses the documented
collection-upgrade command, never an in-place rewrite of pending data.

## Small-team operation and distribution

Hub owns the only project member roster. GitHub collaborator permissions and host/cloud
operator credentials are separate; share neither administrator credentials nor private
profiles with collectors. The existing Hub/domain/R2 are shared services, not something each
new engineer bootstraps. Keep one production scheduler; isolate staging/synthetic state and
keep compute budget zero without an explicit compute authorization.

Use the [member handoff](NEW_MEMBER_HANDOFF.zh-CN.md) for onboarding, the
[collection procedure](../python/docs/B_PIPELINE_HANDOFF.md) for local setup/upgrades,
and the [Hub runbook](../python/deploy/hub/RUNBOOK.md) plus
[operations guide](../python/deploy/hub/OPERATIONS.md) for deployment/recovery.
A release note links these owners rather than duplicating their commands.

The normal member path is reopen the same Workbench profile, record, Close, inspect the
queue and verified remote receipt. No mandatory topic activity or recurring registration.
Keep one accepted developer kit distribution; models download separately. The current kit
still needs operator-assisted native installation, and the Workbench has no installed OS
autostart/update service. Do not claim a one-click installer or remote game control.

Healthy-day maintenance is the existing System capacity/backup view plus waiting/failed
operations and recording quality. On an incident preserve exact source/game/Mod/tool/image,
session/receipt IDs and redacted reasons; report one owning failure mechanism in the new
repository. Automatic issue creation/off-host notification is not currently guaranteed.
After reboot check service identity, mounts, TLS, backup and queue continuity; a missing
status means unknown, not success. Failed decisions remain diagnostic input to repair,
while independently eligible decisions can remain useful under the dataset contract.

Before deployment use the existing preflight, verified off-host backup and compatible
rollback pair. Check both source paths and persistent bind mounts/systemd references when
moving a checkout. Restore into a fresh paused directory and reconcile revocations/unknown
external work; do not restore a DB merely to roll back application code or prune data volumes
for disk space. The deployed source may remain an older accepted release while this guide
advances; operators consult the approved current runbook and actual deployment identity.

## Checks, cleanup and traceability

From root: npm ci, npm ci --prefix python, npm run setup:python, npm run check.
Run npm run project:closeout and git diff --check; match higher gates to TESTING.md.
Review contracts/BOM/pins/version/ADR/docs only where affected. Record exact tested head,
actual evidence, rollback and non-claims in the PR. Source merge never creates Human or
scientific evidence; a flaky retry is not proof that the first failure was harmless.

The initial history import and legacy retirement are complete. The old repositories are
archived; their releases, identities, commit histories and evidence remain for consumers.
Remove obsolete instructions and proven-unused implementation only after checking concrete
callers/tests. Retain schema adapters, package pins, wire/database names and rollback paths
with actual current or archival consumers. Do not rename stpd-prefixed persistent state to
make the tree look new. Keep raw recordings, credentials, models and installed artifacts
outside Git. New work and incident reports belong in this repository only.
