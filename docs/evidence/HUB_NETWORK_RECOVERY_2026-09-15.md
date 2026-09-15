# Hub network access recovery — 2026-09-15

Scope: operator network access and restart recovery, not new dataset deployment or Human qualification.

The original filesystem independently confirmed UFW allowed SSH only from a historical operator
IPv4 address. The current network reached the provider rescue SSH service; the original key then
worked after restoring normal boot and changing the original UFW rules. No original SSH key,
password-authentication policy, project membership or application data was replaced.

The operator entered provider rescue mode. Original system configuration was inspected read-only,
then backed up privately before adding all-source TCP/22 IPv4 and IPv6 rules. Original-system
`sshd -t`, effective authentication inspection and both restore syntax tests passed. The filesystem
was synced and unmounted before the operator selected normal boot. Temporary rescue host identity
was isolated from the original known-host inventory.

Fresh strict-host-key SSH and sudo succeeded from the current network. UFW remained active; the
obsolete source-specific SSH rule was then removed. Public-key authentication is enabled; password
and keyboard-interactive authentication are disabled. Hub port 8765 listens only on loopback.
Both Hub and TLS containers restarted, Hub reported healthy, public HTTPS health returned the
unchanged source `675309814691e5331dd8f4ba7874c2e8107d9fd6`, and the backup timer was enabled/active.
No systemd services were failed. Root filesystem usage was 64%, with approximately 14 GiB available;
inodes were 5% used during rescue inspection. Historical ENOSPC is not a current exhaustion claim.

This proves the current network and normal boot recovery, not reachability from every external
network or a fresh backup/restore/data-upload qualification. No GPU was started. Normal networks
no longer require source-IP enrollment; externally blocked outbound SSH needs a separately permitted
route. See [the maintenance procedure](../../deploy/hub/OPERATIONS.md).
