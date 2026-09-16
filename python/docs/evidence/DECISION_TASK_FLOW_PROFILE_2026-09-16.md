# Decision task flow: bounded synthetic projection measurement

Scope: local portable implementation measurement, not deployed Hub/R2 throughput or Human
evidence. The workload used the existing `platform_bundle3_fixture.bundle3(runs=10)` owner-format
synthetic fixture: 20 decisions, 16,276 compressed bytes. A Local ArtifactStore supplied identical
bytes in both lanes. Fixture creation and initial receipt setup were outside the timer.

Each trial timed `preview` followed by `publish` with unchanged default rules. The baseline
used no cache; the candidate used a fresh private `VerifiedSourceCache` shared between those
two operations. Both paths read and hash the original archive; the candidate caches only an
already owner-verified projection. No timing threshold is imposed on CI.

| Trial | Uncached preview + publish (s) | Cached preview + publish (s) | Owner projection calls |
|---|---:|---:|---|
| 1 | 0.294506 | 0.176804 | 2 → 1 |
| 2 | 0.237473 | 0.179937 | 2 → 1 |
| 3 | 0.230662 | 0.184289 | 2 → 1 |
| Median | 0.237473 | 0.179937 | 2 → 1 |

Observed combined median reduction: approximately 24%. The first cached preview cost roughly
0.112–0.119 s compared with 0.099–0.107 s without caching, reflecting cache serialization/write
overhead. Publication benefited from avoiding verification and projection repetition. These
small samples justify bounded reuse, not claims about production latency or universal speedup.

The structural regression `test_persistent_cache_reuses_verified_original_and_matches_fresh`
checks real owner-call counts across newly instantiated cache objects and byte-equivalent
selection results; timing noise cannot make that test green. Corruption/owner-change/source-
change tests require re-verification. Live R2 transfer and larger corpus profiling remain
separate measurements; no real Human archive or credential was used for this test.

An initial synthetic attempt requested 30 fixture runs and hit the fixture's hour-as-run-index
timestamp limitation (`hour must be in 0..23`). It was not a candidate verifier defect. The
reported comparison uses the valid existing 10-run fixture without altering timestamps or
weakening verification.
