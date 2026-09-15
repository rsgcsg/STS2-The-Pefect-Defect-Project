# Single-repository migration

The project repository is `rsgcsg/STS2-The-Pefect-Defect-Project`.
This document tracks engineering migration, not Human or scientific qualification.

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

## Remaining gates

The initial import is complete locally. Namespace, source-path, packaging and CI
integration are in progress. No new service, installer, Human or training PASS is claimed.
