# ADR-0007: fixed decision datasets and compatible version mixing

Status: accepted and implemented. Bounded service, data-transfer and member UI qualification
passed; see [closeout evidence](../evidence/DECISION_DATASETS_CLOSEOUT_2026-09-15.md).

## Context

A session may contain several native games or fragments. A verified upload is not an
independent game, and one unresolved decision does not invalidate every proved decision.
The strict fullrun-dataset-v1 contract intentionally requires complete runs. Weakening that
contract would change archived admission and training assumptions.

## Decision

Add `stpd/decision-dataset-v1` with a separate loader/publisher, preserving the strict path.
Platform remains the sole native evidence and finite execution-catalog authority. STPD owns
selection, grouping, duplicate accounting and research partitions. No changes to gameplay,
Recorder dispositions, immutable archives, model architecture or GPU scheduling are implied.

Default selection retains verified canonical ResearchTransitionV2 decisions with exact choice,
Commit, catalog and successor evidence. Incomplete games, defeats and unknown outcomes are
allowed. Optional complete-only, wins-only, no-recording-failures and explicit category/version
filters narrow selection. An unknown value does not satisfy an explicit filter.

Normal cancellation and diagnostic invalidation are not recording failures. Source integrity,
unsupported schemas, conflicting identities and malformed lineage remain hard failures.
Unresolved and missing-canonical decisions remain exclusions; no replacement S or successor
is constructed. Reports retain invalidations and exact source references. Parent acceptance
context remains available when the parent is not selected as a training row.

A dataset fixes sources, rules, seed, selected records, exclusions, aliases and split assignment.
Preview yields an immutable logical digest; publication reprojects the same sources and must
match that digest. The artifact contains Parquet records, selection report and received-source
parents. Loading reprojects source bytes and checks both payloads. New inputs produce a new
artifact, never modify an existing training dataset. UI names are labels, not artifact IDs.

## Identity and versions

| Boundary | Required binding | Update behavior |
|---|---|---|
| Local client to Hub | supported API/auth contract and live member/device authorization | unrelated source commits need not match; unsupported API fails explicitly |
| Native Connector to game | owning native compatibility/legality checks | record actual game identity; never bypass a failed native binding just because the UI opens |
| Collector/tool to an existing queue | exact fixed tool, BOM and immutable outbox identity | finish old queue using its tool; explicit new generation for upgrades |
| Received source | byte hashes, source identity and supported evidence contracts | new game/Connector/Annotator version alone is not a dataset rejection |
| Dataset | exact source/artifact IDs, adapter/selection schema, rules, seed | supported versions may mix; actual environment identities remain in report; unknown formats require an explicit adapter update |
| Training | exact dataset snapshot, input representation, tokenizer/model, code/lock, seed | do not float inputs; mixed versions are an experimental population choice, not proof of equivalent game rules |
| Model execution | supported model representation/action-catalog/runtime contracts | artifact provenance is fixed; deploy checks runtime compatibility independently of dataset provenance |

A game balance update may preserve the recording schema while changing the learning target.
Mixing remains an explicit recorded dataset choice; filter by game/environment for controlled
comparisons. New unsupported native seams or evidence schemas require owner fixes and fresh
qualification. No automatic schema relabeling, old-evidence rewrite or silent legality fallback.
Versions absent from verified environment metadata remain unknown. Existing source archives
retain full exact identities; UI version labels never replace hash/BOM evidence.

## Grouping and duplicates

Session-scoped native run IDs define observed games/fragments. Do not merge different sessions
using seed, character, timing or similar states. Native terminal evidence determines win/loss;
missing terminal remains unknown. A complete claim must already be independently proved by one
source; combining fragments cannot invent an uninterrupted game.

Repeated upload bytes do not multiply records. Same session/run/decision identity with the
same native facts is one selected decision with source aliases; conflicting facts fail closed.
Similar situations in different games remain observations. Whole runs and repeated semantic
components stay within one train/dev/test partition. Fewer than three independent components
are retained with `unassigned` splits, not silently called an evaluation-ready training set.
Original native sequence is persisted; removing a row does not join neighbours into a causal
chain. Recurrent/transition consumers must inspect original lineage and gaps.

## Execution, maintenance and limits

The existing isolated CPU verifier supervisor also runs durable dataset tasks. HTTP reads only
persisted results. Members submit preview/build tasks against explicitly shared verified sources;
revocation is rechecked before work and result access. Shared receipts receive background game
profiles. Source receipts never change because a derived profile fails.

Current bounds: 100 selected uploads, 256 MiB total compressed inputs, ten pending member jobs,
existing isolated worker resource/time limits. Oversize/resource failures remain visible and
require a smaller selection or a measured owner change; there is no GPU fallback or charge.
The game page explicitly covers the latest 100 shared profiles, not a project-wide unique total.
These are bounded CPU capabilities, not a performance claim for 100 long games in one build.

Keep operational SQLite in normal off-host backup/restore. Interrupted jobs become failed;
there is no automatic repeated publication. Explicit retry creates a new task and preserves
the failed attempt. A successful later profile resolves the current failure badge. Existing source grants apply to derived downloads.
Deployment rolls back the image; additive tables and immutable artifacts are retained. Do not
manually edit a completed job or dataset. Re-preview for a new build after fixing its cause.

## Alternatives and consequences

A mutable live query dataset would be convenient but could change an experiment beneath a
running trainer. Strict whole-run-only admission discards useful decisions. The selected
separate immutable contract preserves both use cases at the cost of two deliberate loaders.
Existing Full-Run trainers keep their strict loader; this change does not silently switch their
scientific protocol. A trainer must explicitly consume the decision contract before claiming
partial-run training support. No training, live-model or Human-quality claim follows from a
successful dataset build.

## Evidence

Focused regressions cover partial admission, nested context, exact duplicates, unknown outcomes,
source integrity, immutable reprojection, preview binding, membership/sharing revocation and
background profiles. Full gates and exact deployment/Human UI receipts are recorded separately.
