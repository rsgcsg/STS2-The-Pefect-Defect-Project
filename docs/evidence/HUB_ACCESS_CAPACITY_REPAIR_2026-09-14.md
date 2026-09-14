# Hub access and storage incident: measured recovery

This report records the 2026-09-14 operator investigation of the predecessor service,
not qualification of the later membership candidate. Historical receipts and Human bytes
were not rewritten. The current operational procedure is [Hub operations](../../deploy/hub/OPERATIONS.md).

## First incorrect operational assumptions

The deployment firewall allowed SSH from the public source address of the original operator
connection. It did not follow the laptop across networks. Returning to that network restored
fresh key authentication to the same host/port/key. Effective server settings allowed public
keys and disabled password and keyboard-interactive authentication. Public HTTPS remained
available while SSH from a different route timed out. No password reset, rescue boot, firewall
disable, public SSH rule, host-key bypass or reboot was needed.

A console `No space left on device` message was evidence of a failed write, not proof that
the journal was the disk consumer or that storage was still full. Current block/inode and
directory measurements identified container images and their compressed/unpacked layers as
the pressure source. The old full-build image remained locally after compatible successors
had been deployed; deployment capacity and local image retention lacked an enforced check.

## Measurements and bounded action

The service identified source `d8c7d48da505603067aa6fd19ea1b04a74ca8c3b`, dependency lock
`422350fbafdf4b6b5938da87f00cce5222235e8846fd28fac5f3a32a9c4514d6`, and image
`ghcr.io/rsgcsg/stpd-worker@sha256:ad854cadbb2f23b846205afa8189b72fe3d7ca2c11336647fc7ef25b8d3c86da`.

| Observation | Measured value |
|---|---|
| Root filesystem before retirement | 40,483,942,400 bytes total; 6,370,762,752 bytes available; 85% used |
| Root inodes | about 6% used; no inode exhaustion |
| `/run` | about 1% used |
| Containerd storage | about 30 GiB: 21 GiB snapshots and 8.4 GiB compressed blobs |
| Application and retained qualification state | about 34 MiB |
| Journals | 45.3 MiB |
| Obsolete full image unique content | about 8.46 GB |
| Recent source refresh unique content | small layers; no evidence of duplicating the entire environment per refresh |
| Root after retirement | 14,834,135,040 bytes available; 64% used |

Only the local copy of
`ghcr.io/rsgcsg/stpd-worker@sha256:0e4a3bfd6a9de7d277c77098264d1ace5b62a756db04822a13ba3103596c33b9`
was retired. Its exact remote manifest was first retrieved successfully; no running/stopped
container referenced it and it was not the selected deployment. Current and compatible
predecessor images were retained. No registry image, volume, database, recovery directory,
Human evidence, journal or Docker internal file was deleted. Free space was remeasured after
the exact Docker image removal; reclaimable/shared accounting was not treated as free space.

The historical journal contains ENOSPC during earlier builds. The current-day journald query
returned no new matching failures. An optional missing `pam_lastlog.so` warning came from the
unmodified distribution login configuration (`dpkg -V` reported no package drift); it did not
explain the TCP timeout. The authentication stack was not changed to suppress that warning.

## Recovery and data checks

Operations remained schema 3 with two verified uploads, one existing account/device and no
compute jobs; dispatch was paused and budget zero. The latest scheduled off-host backup was
retrieved into a new isolated file using the same exact image. Receipt, chunks, full snapshot
hash, compatible schema and paused recovery checks passed. Private before/after inventories
retain row hashes without publishing credentials or raw records.

This is database-backup and host-reachability evidence. It does not qualify full-host disaster
recovery, external notifications, a new member login, changed source, GPU execution or a new
Human collection. The membership migration must separately bind its exact source/image,
pre-migration snapshot, preserved identities/receipts, post-migration backup and browser gates.

## Default prevention

The repair adds a shared filesystem-capacity observation for the deployment check and admin
page, and a pre-launch Linux verifier check that leaves uploads pending without consuming an
attempt when capacity is insufficient. The operational reserve derives from existing bounded
archive, expansion, extraction and backup sizes; it is not a disk quota or concurrent-work
reservation. Deployments must additionally supply their measured peak allocation. Unknown
capacity is visible, never inferred from a percentage or a Docker reclaimable total.

The backup owner publishes a bounded credential-free status projection through a read-only
directory mount so atomic replacements remain visible to the Hub. Successful backup receipts,
projection freshness and service health remain distinct. The existing daily backup mechanism
is reused; no additional service, monitoring platform or cloud account is introduced.

Full dependency builds are not the default job of a small production Hub. Source-only refreshes
may reuse an exact qualified parent after the capacity check; a changed dependency lock needs
an adequately sized separately authorized builder. Current/compatible rollback pairs remain
local, while older retrievable history can remain in the immutable registry and recovery
inventory. See [Docker's storage accounting](https://docs.docker.com/engine/storage/containerd/).
