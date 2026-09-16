# ADR-0008: selected decision unions and bounded verification reuse

Status: implemented and portable-tested; deployment and Human UI qualification are separate.

## Context

Members need to combine already filtered datasets without accidentally reintroducing excluded
decisions. Preview and publication currently re-read and re-project identical source archives.
The existing background worker is already asynchronous; moving a button to a background task
alone does not address this repeated work. The latest-100 profile view also cannot describe
all available project profiles.

## Decision

Keep `stpd/decision-dataset-v1` unchanged. Add `stpd/decision-union-v1` as a new immutable artifact
whose `dataset_<artifact_id>` parents are existing decision datasets or unions. The same owning
`decision_store.load` dispatches both contracts; the strict Full-Run trainer is unchanged.

Load and verify each parent, take only its **selected** rows, deduplicate by exact native
decision identity, reject conflicting facts, and optionally narrow that union with the same
selection rules. Parent-filter exclusions cannot return through source re-expansion. The
union report retains each parent's artifact/logical identity, rules and exclusion counts,
decision-to-parent links, original source aliases, parent occurrence context, native sequence,
version distribution and invalidations. Similar states do not constitute duplicates.

Each new union freezes a fresh whole-run-safe split using its recorded seed. It does not inherit
multiple conflicting parent partitions. A researcher must explicitly admit the new experiment;
previously used or sealed data does not become a fresh unbiased holdout by re-splitting it.
Completeness and outcome require an existing verified source claim; two fragments cannot
manufacture a complete run. Union counts never imply continuity across missing decisions.

Preview/publication still agree on the exact logical digest. Publication preserves old artifacts
and writes a new Parquet/report/manifest. Loading reconstructs the selected union and compares
both payloads. Bounds: 100 selected parents, at most 256 dataset nodes, depth 8, and at most
100 unique source archives/256 MiB compressed source input across the graph, in addition to
existing isolated worker limits. Resource failures remain visible, not silently truncated.

## Private verification reuse

The Hub worker may reuse a derived `SourceProjection` in its existing private Operations SQLite.
The key binds original archive SHA/size, exact Producer source/lock, the installed Evidence
verifier's Python bytes, projection/contract code bytes and the cache schema. Original archive
bytes are still fetched through verified artifact storage and hashed on every request. Only
successful owner verification/projecting populates cache entries; requests, manifests and raw
uploads cannot supply a trusted-looking cache entry. Default research loaders without a cache
continue full verification. The cache never grants membership or sharing permission.

Cache results are typed-decoded and checksummed. Corrupt entries are discarded and original
bytes reverified; a changed verifier/source/lock misses the cache. The private operational DB
is a trusted service boundary (it already controls membership/sharing), not an untrusted
exchange format. Checksums detect corruption, not a hostile actor with DB write authority.
Entries are limited to 16 MiB; total retained body bytes to 64 MiB with least-recent-use eviction.
Large entries bypass caching. This is disposable derivative state, not another source ledger;
deleting cache rows cannot delete records, datasets or authorizations. Existing DB backups
cover the table; removing rows does not imply shrinking SQLite's allocated file immediately.

Source transfer remains uncached here. The measured local result is CPU/projection reuse,
not a guarantee for R2 transfer time, large real Human recordings or 100-run throughput.

## Durable jobs and visibility

Existing upload requests retain their exact shape. A union request substitutes `datasets` for
`uploads`, with `rules`, `preview_id`, and `name` unchanged. These two source fields cannot be
mixed in one request. A null preview ID previews; the returned completed ID freezes exactly
the same inputs/rules during build. Member and ancestor-source sharing are checked on create,
work, completion, read and download, even for cache hits.

Job state remains pending/running/completed/failed. Progress is a persisted observation of
phase, completed/total work units, observed time, elapsed seconds and cache counters. It is not
a percentage or resumable checkpoint. Reopening the UI observes the existing task. Interrupted
workers remain failed; explicit retry creates a new attempt and retains the failure.

Game summaries read **all available shared recording profiles**, with shared/profiled/missing
counts and a partial flag. They still count session-scoped observed games, not globally deduced
independent games. Duplicate source exports retain aliases. Missing profiles, overlapping
exports and failures remain explicit; failure details have a stated 100-item display cap.

## Alternatives and consequences

Concatenating Parquet would bypass conflict and lineage checks. Expanding parent raw sources
with new default rules would recover intentionally excluded decisions. A mutable dataset would
change an experiment underneath training. None is accepted.

A second workflow engine, remote cache service or speculative object-store rewrite is not
needed. Reuse the existing worker, artifact store, operations DB and source loaders. Union is
an explicit new selection contract, not a promise that current Full-Run training or online
model adapters already consume it.

## Evidence

`test_decision_union.py`, `test_decision_cache.py` and `test_decision_store.py` cover selected-set
preservation, nested context, duplicate aliases, conflicts, recursive load, preview binding,
revocation, cache/source/owner drift, corrupt-cache re-verification, interrupted-job observation,
and profile coverage beyond 100. The [bounded synthetic measurement](../evidence/DECISION_TASK_FLOW_PROFILE_2026-09-16.md)
separately records the measured performance scope. No production or Human claim follows.
