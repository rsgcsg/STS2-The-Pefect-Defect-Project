# ADR-0009: project data selection and runtime provenance

Status: accepted for implementation on 2026-09-16. Runtime acceptance is recorded separately.
Supersedes the extra per-upload grant requirement in ADR-0006/0007 for accepted project data.

## Context

Members could see accepted recordings but could not select older recordings lacking a
second sharing marker. Dataset tabs forced an identity request and task reads fetched every
source manifest from object storage. Selecting multiple recordings could fail because the
research projection compared process identity as part of a stable environment fingerprint.

## Decision

An authenticated project member may use accepted project recordings and discoverable project
datasets without a second publication approval. This is project access, not anonymous Internet
publication. Explicit owner withdrawals, revoked membership, sealed test/Gold restrictions,
receipt/file integrity and native evidence requirements remain effective. Quarantined sources
are not dataset inputs. Their diagnostic archive export still needs the existing owner grant.
Unlinked historical dataset lineage does not create another sharing approval step; dataset
loading must still verify its own declared contract and original bytes.

New export inventories use `stpd/project-sharing-v2`. Existing v1 inventories keep their bytes,
hashes and identifiers and are readable under current access checks. No approval history is
rewritten. The legacy sharing table retains actual grants/withdrawals; absence is not a denial
for an accepted project recording.

The source picker filters the whole catalog before pagination, using recording time with upload
time as a fallback. Date boundaries are inclusive start and exclusive next local day. Members
can select all matching sources within the existing 100-source bound; an oversized selection
is rejected explicitly, never silently truncated. Selected sources persist across pages/tabs.

HTTP task reads and enqueue check current indexed source access. Background execution performs
full manifest, source, receipt, permission and reprojection checks before completing. Navigation
does not serialize unrelated network reads on the local identity lock; a changed account discards
in-flight responses. Ordinary navigation reuses the existing short-lived identity observation;
each Hub request still authenticates. Manual refresh forces a new identity observation.

Connector's environment fingerprint excludes `runtime_instance_id`. Research therefore joins
otherwise identical environment metadata across process restarts and records sorted
`runtime_instance_ids`. All other fields, including future identity fields, must agree exactly.
Batch dataset workers have an explicit 900-second wall and 600-second CPU budget,
separate from the single-upload 150/120-second limits. The 1.5 GiB address-space,
256 MiB aggregate source and 100-source bounds remain. Deadline or shutdown still
reaps the process and cleans scratch; no automatic retry is introduced. The single
verification worker is shared with uploads: a long dataset can defer the next upload
verification until the batch exits (up to its wall budget); HTTP remains responsive.

Single-process reports remain byte-identical so existing dataset logical IDs and reprojection
continue to work. Original source archives and per-decision execution identity are unchanged.

## Alternatives and consequences

Removing all integrity checks would hide damaged data; forcing a fresh grant for already
accepted project data would retain the reported usability failure. Treating a restart as a new
game version misrepresents the native owner. The chosen changes remove those extra gates at
their actual owners while preserving immutable evidence and explicit withdrawal.

Previous research code cannot reproject newly created multi-process datasets. A rollback that
must support those datasets must retain the corrected research reader; an older image is only
a limited service fallback, not a compatible dataset-processing rollback. Never restore an old
database merely to roll back code. Native Mod/tool bytes and compute budget do not change.

## Evidence

Regressions cover real verified archive projection across restarts, unchanged historical
single-process identity, nested union/publish/reload/cache, paginated date selection, accepted
sources without a legacy grant, explicit withdrawal, no object-store calls on task GET/enqueue,
worker integrity recheck, concurrent local navigation, logout races and delayed browser replies.
Synthetic tests establish mechanics, not Human or scientific qualification.
