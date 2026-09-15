# Testing And Evidence

The root suite is the portable source and package gate. It does not require
proprietary STS2 files and does not prove installation, loading, mutation, a
journey, Human evidence, or qualification.

```bash
npm ci
npm run check
```

Repository-system checks and routing can also be run directly:

```bash
npm run project:context
npm run project:check
npm run project:closeout
```

`project:check` is part of the root portable gate. `project:closeout` reports
path-based review signals and never rewrites semantic truth.

## Hosted CI contract

GitHub-hosted CI is intentionally a **source/test portability gate**, not an
exact-game or runtime qualification environment.

The workflow always starts a `plan` job. The same local router is available as:

```bash
npm run check:plan -- --base origin/develop
npm run check:plan -- --base origin/develop --run
```

The first rollout optimizes only modifications to the explicit editorial allowlist
in `tools/check-plan.mjs`. `docs` runs `check:docs` (links, commands, routes,
governance and patch hygiene) with Node alone; no Python/.NET installation.
Governance/ADR/contract/CI/component paths, additions/deletions/type changes,
unknown paths, dirty worktrees and unresolved Git refs select the full root suite
on both Linux and Windows. A `.md` suffix alone never grants an exemption.
For local uncommitted work the conservative result is full; inspect the exact
committed diff for the lighter route. `npm run check` always means full.

`portable` remains the required status and evaluates all job outcomes, including
failure and cancellation. It passes only if the plan succeeded and every selected
lane succeeded; unselected lanes must be skipped. Its summary identifies scope
and exact base/tested checkout. A docs PASS is not full portability evidence.

CI runs on every PR and pushes to `develop` and `main`. Release/hotfix branches
use their PR run, avoiding duplicate push runs. Manual dispatch and weekly Sunday
21:17 UTC runs retain full checks. Main/develop merge commits are tested in their
own right. An executable release requires a full dual-OS result for its candidate;
manual dispatch supplies it when needed. Scheduled results cover the default
branch, so dispatch full checks on an unreleased active integration line before
publication. Do not use whole-workflow path filters: required checks would remain
Pending. Concurrency cancels superseded CI, never a production deployment.

All third-party GitHub Actions are pinned by full commit SHA, checkout fetches
full Git history because identity/history checks require it, and checkout does
not persist write credentials.

`npm run check:ci` is part of the root suite and guards these properties. It
also rejects adding exact-game deploy/load commands to public hosted CI. This is
an evidence boundary, not a convenience restriction: hosted runners do not own
the exact local STS2 installation, admitted Modset, installed artifact, or Human
operator needed to make such claims honestly.

## Focused portable checks

```bash
npm run check:ci
npm run check:identity
npm run check:bom
npm run check:boundaries
npm run check:history
npm --prefix components/connector run check
npm --prefix components/host-runtime run check
npm --prefix components/annotator run test
npm --prefix components/evidence run check
npm --prefix components/policy-runtime run check
npm --prefix apps/workbench run test
npm --prefix apps/ingame-ui run check
npm --prefix apps/game-mod run check
```

The checks have separate meanings:

- CI contract: workflow topology, trigger/concurrency policy, cross-OS aggregate
  gate, action pinning, and hosted/exact-game boundary;
- component identity: path-scoped Git provenance plus component tree, source
  digest, contract digest, version, clean-worktree reporting, and the repository
  EOL policy required to keep byte digests stable across checkout platforms;
- BOM: component source identities, versions, public package pins, retained
  runtime/artifact evidence, and explicit non-claims agree;
- boundary: component dependency direction, active predecessor references,
  local-path leakage, source completeness, and admitted workspace graph;
- migration history: imported predecessor histories still have their exact
  original tree/parent relationship; this is archival integrity, not runtime
  qualification;
- Connector check: public contract/SDK/package/docs/CLI/release tooling and
  portable Connector-local checks;
- Host Runtime check: lifecycle, package, Python consumer, and Host tests;
- Annotator `test`: portable recorder and workstation-tool tests;
- Annotator `check`: portable tests plus exact native compilation against the
  locally installed game and current Connector artifact;
- Evidence check: Python typed verification, immutable store/transfer/receiver
  and failure paths;
- Policy Runtime check: typecheck, tests (including the actual Workbench status
  consumer, command-timeout/replacement boundary, disconnected stop cleanup, and
  direct/proxied HTTP mutation admission), deterministic package build, and clean
  installed-package CPU/CLI smoke with the released Connector SDK;
- Workbench/Live UI/Game Mod portable checks: presentation/service/lifecycle
  source tests that do not claim exact game loading.

## Local exact-game and runtime gates

`npm run build` and `npm run check:exact-game` require the exact local STS2
installation. They build or compile game-bound artifacts; a successful build is
not install, load, Live mutation, Human evidence, or qualification.

Use the smallest evidence ladder required by the change:

| Change class | Minimum additional evidence beyond the selected portable gate |
| --- | --- |
| docs / governance / pure portable tooling | normally none beyond `project:closeout` and `git diff --check` |
| game-bound C# / native seam / unified Mod source | `npm run check:exact-game` plus a clean exact build and source/artifact identity |
| install / lifecycle / runtime packaging | exact build -> install -> cold load -> `verify:loaded` / owning runtime checks -> rollback readiness |
| Human recorder / causal semantics | exact runtime identity plus the bounded Human canary/audit required by the owning evidence contract |
| release | advertised build/package/install/load/runtime gates plus rollback and release evidence; Human/scientific gates only when claimed |

Do not promote a lower row into a higher one. A green GitHub workflow proves
source/test only.

## Merge provenance and component identity

Current component `source_revision` is path-scoped Git commit provenance derived
from `git log -1 -- <component path>`. Component tree and source/contract
digests are separate semantic/content identities.

That distinction has one important Git consequence:

- a normal merge commit preserves the topic commit as the path-scoped component
  source revision;
- squash or rebase integration rewrites that commit provenance even when the
  resulting component tree and content digest are byte-for-byte identical.

The component-identity regression suite proves both cases. Therefore, while the
current BOM/runtime provenance schema carries commit-based component
`source_revision`, **PRs that change any component source path must use a normal
merge commit**. Do not use GitHub `Squash and merge` or `Rebase and merge` for
those PRs. A docs/governance-only PR that changes no component source may still
be squashed.

If the repository later replaces commit provenance with a different stable
identity contract, change the tests, BOM contract, workflow guidance, and merge
policy together. Do not merely weaken `check:bom` after a squash-induced drift.

## Portability notes

The repository pins text materialization with `.gitattributes` as
`* text=auto eol=lf`. This is an identity requirement, not only a style choice:
component source and contract digests hash source bytes, so allowing Windows
`core.autocrlf` to rewrite a clean checkout would make one Git tree acquire a
different digest on another OS. `check:identity` directly guards the repository
EOL rule, and its temporary Git fixture enables `core.autocrlf=true` to prove
that canonical LF still holds. Text parsers that consume external or generated
content should nevertheless remain CRLF-tolerant rather than relying solely on
the checkout rule.

Root Host wrappers retain an explicit nested-npm `--` boundary so profile,
endpoint, and experimental-evidence arguments reach the owning Host CLI on
Windows and POSIX shells.

The Host profile-template test pins its captured file inventory. This prevents
Node-version-specific recursive-copy filter behavior from admitting runtime-only
Windows `logs` or `sentry` files into a reusable profile template. Workspace
package tests use Node's standard automatic discovery rather than depending on
shell-expanded `*.test.mjs` globs, which Windows npm does not expand on the
supported Node 20 baseline.

## Evidence Ladder

Evidence levels are ordered but never implied:

```text
source -> test -> build -> package -> installed -> loaded
       -> Live mutation -> journey -> human_validated -> qualified
```

Predecessor reports and fixtures can test mechanics or migration assumptions,
but cannot qualify a different Platform artifact. Local `.local/` evidence is
not documentation and must not be committed.
