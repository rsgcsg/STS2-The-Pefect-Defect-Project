# Single-repository migration

The project repository is `rsgcsg/STS2-The-Pefect-Defect-Project`.
This document defines the default project workflow and links exact qualification evidence.

## Accepted ownership

Platform components retain their native, execution, recording and evidence owners.
Python project applications live in `python/spireagent`; research lives in
`python/stpd`. `python/` is one Python build environment, not another repository.
Hub owns member/device permission and durable operations. Workbench owns local
supervision. Neither owns game rules or research labels. Shared JSON, artifact and
source infrastructure must not depend on either UI. Model adapters own backend
requirements; Policy Runtime owns gameplay command delivery. Provider adapters own
remote handles; Hub owns budgets and durable attempts. Unknown submission is not retry.

## Ordered acceptance

1. Preserve original histories, exact import trees and public-source scan review.
2. Extract shared application infrastructure and retain existing semantic regressions.
3. Unify root guidance, installation, CI, release and deployment entry points.
4. Qualify clean source, installed artifacts, exact game and isolated cloud candidate.
5. Back up production, deploy one candidate, and verify member access and downloads.
6. Human gate: install/cold launch, record, Close, pack, upload, receive, select/download.
7. Audit exact candidate, merge develop/main, verify CI, then retire old repositories.

Until steps 4–6 pass, production and old repositories remain available. No existing
recording, queue, consent, manifest or model is relabelled. No new GPU budget is granted.

## Traceability and rollback

`migration/project-import.json` binds old repository commits to the import commit.
`npm run check:history` checks both this import and earlier component imports.
Historical evidence remains tied to its original producer and bytes. New artifacts
record the new repository, exact source, lock, component and file identities.
Moving source does not transfer install/load/Human qualification.

Cloud cutover preserves domain, members, devices, R2 and persistent state paths.
Only one production scheduler may run. Keep the prior image/config and a consistent
off-host backup; restore paused and reconcile external task/upload state before resume.
Do not use a database restore to silently resurrect revoked access or retry unknown work.

## Accepted release and daily workflow

The sealed code/runtime candidate is `45ef463e3c13cd82db55601c122a292c37aaae2e`.
[Release and exact distribution](https://github.com/rsgcsg/STS2-The-Pefect-Defect-Project/releases/tag/candidate/monorepo-20260915)
contains the tested developer kit, hashes and operational identity.
[The Human acceptance report](evidence/MONOREPO_HUMAN_GATE_2026-09-15.md) records
580/580 decisions proved/canonical, zero real failures, Close packaging, cloud verification
and member download. Root Linux/Windows/local and exact-game gates passed this code ref.

Use this repository for development and `npm run workbench` for the project console.
Members use the existing email login/device registration, default daily consent and automatic
Close upload. Optional activities stay optional. Operators use the one
[Hub runbook](../python/deploy/hub/RUNBOOK.md); developers use the root
[workflow](DEVELOPMENT_WORKFLOW.md). Models are separate artifacts and research stays in STPD.

Release bytes remain sealed to their build source. Documentation and normal integration
commits do not require rebuilding working services, or relabel their producer as the merge
SHA. Resolve integration refs and merge-head CI through the release/PR links. Rebuild only
when the changed component requires a new artifact and qualify that new artifact explicitly.

Watch persistent local preparation/upload status, cloud receipts/incidents and host backup/
capacity status. Retain failed records; they do not erase independently verified decisions.
For an incident, preserve source/kit/Mod/OCI identities, session/receipt IDs and diagnostics;
report through this repository without credentials or raw private data. Repair the owning
layer, test it, publish an immutable replacement and repeat the affected bounded Human gate.

Old source repositories are historical after integration/retirement. Retain their releases
and original identities for archival consumers; new features and fixes belong here. GPU worker
execution, scientific admission and model quality remain separate qualification/budget gates.
