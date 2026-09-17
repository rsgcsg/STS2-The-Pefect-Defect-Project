# ADR-0010: Dataset curation and continuous per-run recording

Status: Accepted

Date: 2026-09-17

## Approved scope and owners

The approved batch joins three user journeys, not their domain authorities:

1. Bounded, resumable dataset construction with a persistent verified source
   index, fixed preview selection, deferred materialization, optional local
   execution and stable incremental console updates.
2. Immutable dataset purposes (training, test, sealed Gold), whole-run/source
   overlap checks, atomic Gold reservations and inherited protection of every
   derivative; reversible Human quality annotations preserve raw evidence.
3. An armed recorder starts and seals individual native runs, publishes concise
   outcome/coverage/upload status, continues across runs, and preserves partial
   recordings on orderly exit or subsequent crash recovery.

STPD owns verified projection, selection, grouping and research use. Hub owns
membership, durable tasks, reservations and distribution. Workbench executes
bounded tasks and delivery using existing services. Annotator owns native
witnesses, recording lifecycle and immutable append. Live UI only presents
typed facts/commands. No second legality or causal authority is introduced.

## Required invariants

- A source index is a disposable private derivative of verified bytes and an
  exact implementation identity. It is not an externally trusted projection.
- Dataset processing is bounded by a source/batch, not the sum of archives.
  Canonical content and selected membership are independent of execution host.
- Preview confirmation binds exact source/rules/annotation/reservation versions.
  Resume is for idempotent data processing, never unknown gameplay delivery.
- Train/test isolation follows native occurrences, whole runs, known duplicate
  groups and the actual model ancestry. Unknown ancestry is not an isolation PASS.
- Gold protection follows sources and derivatives, including original downloads,
  caches and local execution. Gold can union only with compatible Gold. Hiding a
  dataset cannot release a reservation. Sealing cannot undo historical exposure.
- Quality annotations do not delete raw evidence or change owner dispositions.
  Exclusions preserve sequence gaps and causal dependencies.
- Native fresh start, resume, victory, defeat and abandonment remain distinct.
  Exit is not a terminal outcome. Missing start/end or interruptions remain visible.
- Sealing waits only for bounded existing bookkeeping; it cannot invent a
  successor. Upload and archive work stay off the game main thread.
- Armed recording continues after a per-run seal. Existing upload preferences,
  consent, tools, old data and pending queues retain their identities.

## Rollout and evidence

Phase 1: source indexing/streaming, durable task handling and browser stability.
Phase 2: purposes, overlap, Gold and annotations through every consuming boundary.
Phase 3: native run lifecycle, UI, per-run seal, delivery and recovery.

Validate historical output parity, corrupted/stale index rejection, interrupted
jobs, original failing selection and larger bounded workloads; browser navigation,
selection/scroll stability; overlap/Gold laundering and concurrency; native boundary
and close-tail regression, exact build/install/load and owner-operated canary.

Implementation, portable tests, deployed CPU jobs, loaded native bytes and Human
canary are distinct gates. No GPU/model-quality claim. The bounded implementation,
capacity, deployed-service and owner-operated canary results are recorded in
[the dated acceptance](../evidence/CURATION_CONTINUOUS_ACCEPTANCE_2026-09-17.md).
PR and release receipts retain exact final integration checks; this decision does
not promote untested native paths or unlimited-capacity claims.

## Compatibility and rollback

Historical manifests and evidence remain unchanged. New purposes do not rewrite
old internal splits. Legacy data starts as purpose/usage unaudited. Reader/writer
compatibility is verified before activating new formats. Preserve old image,
config, tool and pending queue; roll back software without restoring an old DB
over current data or releasing Gold reservations.
