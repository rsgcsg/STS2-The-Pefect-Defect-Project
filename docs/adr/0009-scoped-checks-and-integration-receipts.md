# ADR-0009: Scoped checks and verified integration receipts

Status: Accepted

Date: 2026-09-17

## Problem and exact grounding

The root CI routed nearly all source edits through both complete OS suites.
A reviewed topic, develop merge, release PR and main merge could execute the
same source/tests repeatedly. Git provenance differs across these refs even
when content is identical. Repeating content tests is not the only way to check
new integration provenance. Exact observations belong in the task PR and audit.

## Decision

Keep develop as reviewed daily integration and main as deliberate batch promotion.
Ordinary work stops after develop integration; matching trees need no empty sync.
TESTING owns four scopes: editorial docs, the full Python owner/consumer gate,
full root execution, and verified execution reuse plus current repository guards.

Topic PRs always execute. Protected integration pushes and release PRs to main
may reference an executed dual-OS result for identical tree/workflow content,
within seven days, from this repository's successful CI workflow and attempt.
Main executable promotion requires full scope. Manual/weekly full never reuse.
Current identity/BOM/history checks still execute. Reuse never seals a new
execution receipt or resets its freshness. Missing or invalid proof runs tests.

## Owning fact and authority

The CI planner owns check selection. GitHub owns run status and artifact metadata;
the successful aggregate records actual tested checkout, content, scope and
lane results in an attempt-specific artifact. The verifier validates its digest,
run association and freshness. Git identity tooling owns the new merge provenance.
No CI proof owns installation, native runtime, Human or research qualification.

## Alternatives considered

Always repeat all tests: simple, but dominated small changes and promotion time.
Skip Windows: rejected; OS process/path/consumer contracts remain relevant.
Disable strict PR checks: rejected for this iteration; latest-base integration remains.
Single main: optional future simplification, unnecessary to fix execution duplication.
Unbounded global test cache or copied statuses: rejected; scope and trust would be opaque.

## Evidence and falsification

Tests reject stale, cancelled, foreign, wrong-attempt, wrong-tree/workflow,
insufficient-scope and chained receipts. Lookup failure must select execution.
CI mutations check shared routing, both OSes and aggregate failure handling.
Live task/develop/release/main CI must show executed and referenced scopes honestly.
A receipt accepted after a changed tree or failed lane falsifies this implementation.

## Consequences and tradeoffs

Python changes stop re-running unrelated Platform component suites, while repository
guards and all installed Python consumers remain. This is not per-test impact analysis.
Seven-day reuse preserves the original runner evidence, not a fresh current-image claim.
Routine environment requalification uses forced full runs. API/artifact access is optional
for performance; its failure increases work rather than accepting unknown evidence.

## Compatibility and migration

Required status remains portable; branch protections and merge provenance stay intact.
First rollout has no compatible receipt and runs full. Existing published software and
native artifacts are unaffected. Receipts expire; original CI logs retain their own scope.

## Rollback

Revert this workflow/router change through a topic PR. The previous full dual-OS path
remains available at any time through npm run check or workflow_dispatch. No data or
runtime state migration is involved.

## Non-goals

No deployment, model training, hardware qualification, branch deletion, automated
production update, per-test ML selection or claim that VM UI tests cover browser usability.
