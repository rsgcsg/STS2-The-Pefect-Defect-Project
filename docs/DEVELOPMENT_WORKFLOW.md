# Project Development Workflow

The single active development repository is rsgcsg/STS2-The-Pefect-Defect-Project.
Platform components, project applications and STPD research share one PR workflow.

## Branches and merge

Start from current origin/develop after fetch/prune. Use one short-lived topic
branch/worktree per writer. Normal changes target develop through a PR. Release
and hotfix branches target main, then synchronize back into develop. Main and
develop are the only long-lived branches. Do not force-push or bypass required CI.
Use normal merge commits: component provenance must survive integration.

The empty destination has one controlled history-import bootstrap. That exception
creates main/develop once and does not permit future protected direct pushes.
Old repositories remain available until the new release/service/Human gates pass.

## One change, explicit owners

A PR may span native, application and research code where one change requires it.
Record base/head, owning fact, affected contracts/components, source identity,
actual evidence, rollback and non-claims. Root Engineering Governance owns G0-G6;
add research/data/model tags when applicable. Old STPD classifications are historical.
Keep source import and behavior refactoring in separate commits.

## Checks and promotion

From the root: npm ci, npm ci --prefix python, npm run setup:python, npm run check.
Use npm run project:closeout before PR review. All affected tests run; Linux and
Windows must both pass the full portable aggregate. Native/build/install changes
add the local exact-game and runtime gates from TESTING.md. Human/scientific
claims require their own evidence. Source merge never promotes evidence.

## Dependencies and delivery

Consume declared package APIs. Same-repository development may use qualified local
workspace packages; installed distributions bind exact artifacts. Do not import
another component's private source or alter its database. Preserve historical
released dependencies needed to read old data; current installation must have one
reviewed release composition. Replacing a pin requires consumer compatibility tests.

Build an immutable candidate, verify it, promote the same bytes, and retain the
previous image/config. Keep a running collector in a separate checkout at the sealed
release commit; do development and merges in another worktree. Never move the live
collector checkout underneath a recording or upload process. Rebuilds are new artifacts.
One production scheduler owns
operations state; backup/restore remains independent of rebuildable indexes.

## Retirement

After exact candidate acceptance and main/develop CI, mark old repository READMEs
as historical, stop duplicate deployment workflows and preserve releases/tags.
Archive old repositories only after retained links/dependencies are verified.
Delete merged topic branches; keep detached worktrees containing private evidence.
