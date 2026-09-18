# ADR-0011: Fixed decision allocation and portable S01

Status: Accepted

Date: 2026-09-18

## Problem and exact grounding

Verified decision datasets already admit partial trajectories independently of strict
Full-Run qualification. The original frozen-feature worker only accepts Full-Run views
and the pinned CUDA scientific backend. Reinterpreting either historical contract would
hide a change in evidence. Separately, the quality list joined packages through run IDs,
which could display a decision from another package in the same run.

## Decision

Add `stpd/decision-allocation-v1`, `stpd/decision-model-view-v1`, and
`stpd/decision-feature-set-v1`. Allocations are immutable protocol artifacts pointing to
an explicit training-purpose dataset. Their members bind occurrence, transition, source
archive digest, run and train/dev role. Recompute and verify membership when loading.

Offer run-component isolation (including duplicate observations) and explicit decision
isolation. The latter is an engineering diagnostic with possible shared runs, not an
unseen-run generalization claim. Current inputs are N/M0 only: current legal observation
and candidates. History, successor and outcome targets require dependency-aware extensions.
Gold reservations and test-purpose training prohibitions do not become configurable.

CPU/MPS FP32 is a separately identified engineering backend using the exact pinned Qwen
weights/tokenizer and existing mean pooling. Keep scientific CUDA/BF16 qualification
unchanged. Pool micro batches before retaining results to bound token activation memory.
Reuse ArtifactStore, worker, safetensors checkpoint/model codec, Reporter and dev metrics.
Export a small S01 head with its exact backbone/serializer/runtime contract; inference
accepts state and finite candidates, never a human label or successor.

Index source–occurrence membership directly. Legacy whole-run indexes are not proof of
package membership; reproject them through the existing background profile worker.

## Owning fact and authority

STPD owns allocation, model input, learning and inference. SpireAgent owns account access,
current use/Gold reservations, source indexes and operations. Platform still owns native
legal candidates and evidence. No model code is imported by Platform.

## Alternatives considered

Weakening Full-Run or CUDA contracts would make historical evidence ambiguous. A second
training engine or database would duplicate existing identity and recovery logic. Requiring
complete runs for every BC engineering sample would discard otherwise verified decisions.

## Evidence and falsification

Regression checks cover cross-package decisions, legacy index migration, fixed allocation
reload/tampering, explicit same-run diagnostics, held-out rejection, worker resume, export
hashes and candidate permutation. Real Qwen and real Human-data runs require separate dated
receipts; synthetic contract tests do not establish either.

## Consequences and tradeoffs

Allocation stores compact membership rather than copying state payloads. Reverification
cost remains measurable and must not be hidden as training time. Portable FP32 uses more
memory than BF16. Exact runtime identity initially rejects a changed backend; cross-device
numerical compatibility must be measured before expanding this contract.

## Compatibility and migration

New schemas are additive. Legacy models, datasets and CUDA workers keep their original
meaning. New exact source-index markers trigger bounded background backfill. Raw evidence,
quality history, established Gold and old artifacts are unchanged.

## Rollback

Stop issuing the new allocation/view/export formats and use the existing consumers for
old artifacts. Extra index tables may remain; never erase use or Gold reservations to roll
back a UI or worker. Restore the previous application release through its owning runbook.

## Non-goals

No B/D implementation, LoRA, Z/O, sequence training, scientific effect claim, paid cloud run,
new native execution adapter or automated gameplay is part of S01 engineering qualification.
