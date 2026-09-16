# Dataset export request work — 2026-09-17

The accepted 20-source dataset contains 7,434 decisions. Its immutable export
inventory was created, but the local request returned `request_unknown` before
receiving the response. The existing inventory is recovered rather than creating
another selection. Dataset generation evidence remains at source
`3a4b8997d06011952a2248902c67f64f531dbcff`.

## Owning correction

`CollectionAccess.artifact` traversed the same remote manifest closure twice:
once for artifact policy and once for source withdrawal. `ExportService.create`
then called `read`, repeating both traversals after writing the inventory.
The access owner now returns its checked closure for withdrawal checks, and
create returns the already-authorized inventory. Each later inventory or payload
request independently checks current membership, sealed lineage and withdrawals.
No authorization result is cached across requests. Inventory schemas, hashes,
payload verification and resource limits are unchanged.

## Validation and promotion

A 20-parent regression counts exactly one read per manifest for create, read and
payload, verifies exact payload bytes, then withdraws a parent and requires all
three subsequent operations to reject access. The existing member, sealed-data,
legacy inventory and dataset-selection tests remain applicable.

The release integration receipt records the exact source/test, image, deployment,
backup/restore and actual download byte-verification results. This document does
not claim a completed rollout from source tests alone. The fixed Workbench,
native Mod/Tool, existing data and compute budget remain unchanged. Rollback can
use the retained 3a4b899 dataset-capable Hub image; it restores the slower export
path. No database restore or record rewrite is required.
