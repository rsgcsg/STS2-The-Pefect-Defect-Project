# Hub access and daily maintenance

This is the operator companion to the [deployment runbook](RUNBOOK.md), not another
deployment recipe. It defines the supported access and maintenance procedure; applying it
and recording fresh connection/service checks remain host operations. A source change does
not establish a new firewall, recovery route or monitoring service.

Collectors use the workbench and cloud login. Neither a project `member` nor a Hub browser
`admin` role grants SSH, a Unix account or `sudo`. Host operators separately hold the SSH key,
provider-console access and private recovery inventory. Cloudflare email OTP is not an Ubuntu
console password. Keep compute budget zero unless a separate campaign authorizes compute.

## One saved operator connection

Keep the exact VPS address, Unix user, SSH port, key path and verified server host-key
fingerprint in the operator's private inventory, outside Git. Use the actual deployment
configuration for state directories; `/srv/stpd/hub` in examples is not a discovery rule.
Record the current and previous compatible worker/Caddy digests, database schema, backup
receipt, source revision and external configuration recovery location there as well.

Use the operating system's OpenSSH client. An optional private `~/.ssh/config` entry makes
the daily command `ssh stpd-hub`; replace placeholders and verify the effective configuration
with `ssh -G stpd-hub` before using it. Keep the file/key private. Do not paste configuration
or verbose SSH logs into public issues. A passphrase-protected key must be unlocked locally
through the approved SSH agent before the noninteractive authentication below can succeed.

```sshconfig
Host stpd-hub
    HostName REPLACE_WITH_EXACT_VPS_ADDRESS
    User REPLACE_WITH_OPERATOR_UNIX_USER
    Port 22
    IdentityFile /ABS/PRIVATE/operator-key
    IdentitiesOnly yes
    PreferredAuthentications publickey
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    BatchMode yes
    StrictHostKeyChecking yes
    ConnectTimeout 15
    ForwardAgent no
    ControlMaster no
    ControlPath none
```

Enroll the server host key only after comparing its fingerprint through the provider console
or existing protected inventory. `ssh-keyscan` alone is not identity verification. A changed
host key requires investigation, not deleting `known_hosts` or disabling checking. Inspect
any inherited proxy/identity configuration; this recipe requires no jump host, VPN or SSH
service inside Cloudflare. See the [OpenSSH client manual](https://man.openbsd.org/ssh) and
[client configuration](https://man.openbsd.org/ssh_config).

Use the established key-only server policy and preferably a non-root operator with sudo.
Client flags alone do not enforce server policy: inspect `sudo /usr/sbin/sshd -T` and its
connection-specific `-C` output for applicable `Match` blocks. Confirm public-key login is
enabled, password/keyboard-interactive login is disabled, and review any other enabled methods.
Do not rewrite the authentication stack just because a timeout occurred. Requiring
`AuthenticationMethods publickey` or further restricting root login is a separate controlled
change when needed, not an extra gate imposed on an already key-only installation.

If an actual configuration correction is required, first prove a fresh key-only login and
the required sudo access for the intended **non-root** operator before removing any existing
administrative route. If that account is absent, stop for separately authorized provisioning.
Keep the original session open, preserve its configuration privately, validate the proposed
configuration with `sudo /usr/sbin/sshd -t` and inspect effective values before reloading.
Prove a fresh connection after the reload before closing the original. A later-named drop-in
does not necessarily override an earlier value. Follow [Ubuntu's SSH procedure](https://ubuntu.com/server/docs/how-to/security/openssh-server/)
and [`sshd` validation options](https://man.openbsd.org/sshd).

## Default: network-independent, public-key-only SSH

The project owner approved removing source-IP allowlists on 2026-09-15. TCP/22 is reachable
from normal networks; access is authenticated by the existing Unix account and SSH key.
Do not require home/UQ/hotspot source-address registration. Hub member authorization remains
separate. Keep UFW enabled, HTTPS public, and the Hub API on loopback; do not expose Docker
or 8765. A network that independently blocks outbound SSH still needs its own permitted route;
public port reachability is not a promise to bypass institutional network rules.

For the one-time migration, use an already-authorized shell or provider console. A browser
Hub admin cannot modify the host firewall. Preserve the current recovery session throughout.
First inspect the actual SSH configuration, including any applicable Match blocks:

```bash
sudo /usr/sbin/sshd -t
sudo /usr/sbin/sshd -T
sudo ufw status numbered
```

Require `pubkeyauthentication yes`, `passwordauthentication no`, and
`kbdinteractiveauthentication no` before making SSH public. Confirm the port is 22 (use the
actual reviewed port if different). Stop for an owning authentication repair if these checks
fail; never enable password SSH to restore access. Then add the network-independent rule:

```bash
sudo ufw --dry-run allow 22/tcp comment 'STPD public-key SSH'
sudo ufw allow 22/tcp comment 'STPD public-key SSH'
sudo ufw status numbered
```

If the provider firewall also filters SSH by source, align that rule to the same public SSH
policy. Do not reset either firewall or change unrelated services. From the intended network,
use a fresh OpenSSH connection with `BatchMode=yes`, `StrictHostKeyChecking=yes`, and
`ControlMaster=no`; verify expected user and `sudo -n true`. Only after this succeeds remove
redundant historical source-specific SSH rules, preserving unrelated rules. Check another fresh
connection. Retain key/fingerprint, auth-policy evidence and a usable console recovery method
in the private inventory; do not store changing network IPs as access prerequisites.

If a network blocks outbound TCP/22, an operator-only Cloudflare Tunnel/Access SSH route is a
possible separately qualified fallback using the same SSH key. It is not installed merely by
this document, and ordinary project members must not gain host access through their Hub role.
See [Cloudflare's SSH route](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/use-cases/ssh/ssh-cloudflared-authentication/)
and [Ubuntu UFW](https://manpages.ubuntu.com/manpages/noble/man8/ufw.8.html).

## If the host becomes unreachable

Start with the saved exact address/port/key and the last successful source address. Compare
local routing/proxy changes and provider firewall state before changing the host. Preserve
the current working route/session when one exists.

| Observation | Next check |
|---|---|
| SSH timeout | destination, actual IP family/route, source-IP rules, provider network and host availability; a timeout does not prove an authentication failure |
| SSH host-key mismatch | compare the server identity with protected inventory/provider console; do not bypass host-key checking |
| `Permission denied (publickey)` | expected Unix user, selected/unlocked key and server authorization; do not enable password SSH |
| Website fails but SSH works | inspect Caddy/Hub health, DNS/TLS, current image and storage; avoid changing SSH rules |
| KVM shows Ubuntu `login:` | use the independently held Unix console credential; cloud account OTP and SSH private-key bytes are not that password |
| `No space left on device` | measure blocks and inodes on the failing filesystem; the service printing the error is not necessarily the disk consumer |

If legacy restrictions still block the first migration, use an authorized second operator or
the provider console. Do not make returning to the old network the normal workflow. Provider KVM is a
separate recovery route that must be tested and documented privately. If no console credential
exists, report that missing recovery capability explicitly. Provider password reset, rescue
boot or reboot are deliberate separately authorized recovery actions, not automatic responses
to an SSH timeout. A restart can discard the only usable session without repairing its cause.

## Recovery when no Unix console password exists

A key-only installation may have no usable console password. Do not paste an SSH private key,
Cloudflare OTP or provider account password into the Ubuntu `login:` prompt. Use the provider's
rescue mode only after agreeing the service interruption. Preserve the original host-key inventory;
the temporary rescue SSH identity uses a separate known-hosts file and must be checked through the
provider recovery channel. Enter the temporary password interactively, never in a command, chat or log.
An operator may install their existing public key in the temporary rescue system for the repair.

Discover disks with `lsblk` and mount the identified original filesystem read-only first. Inspect
blocks, inodes, the original UFW rules and effective SSH configuration. Before a necessary repair,
remount that filesystem writable and back up only the affected configuration. Offline UFW changes
must preserve its rule metadata and unrelated rules; validate IPv4/IPv6 with the original system's
`iptables-restore --test` / `ip6tables-restore --test`, and SSH with `sshd -t` and `sshd -T`.
Do not apply the original firewall to the rescue network. Sync and unmount before the provider's
normal-disk reboot. Never guess a disk name or reinstall to fix an access rule.

After normal boot, use the original strict host-key check and a fresh key-only non-root login.
Check sudo, actual UFW rules, password authentication remaining disabled, loopback Hub binding,
public HTTPS identity, containers, capacity and the backup timer. Remove obsolete source-IP rules
only after that new login succeeds, then prove another new login. Rescue access alone is not a
successful production recovery. Keep the redacted incident and private rollback files; temporary
rescue credentials do not become everyday credentials.

## Daily check and before any deployment or build

For the normal daily check, open the cloud console as an administrator and inspect **System**:
capacity, the last successful backup and its freshness, then any waiting/failed uploads. No
SSH session or manual backup is needed for a healthy day. A missing/unreadable value is unknown,
not PASS. If the page is unavailable, verify public `/health` and use the saved SSH connection.

On an attention state or before maintenance, use the runbook's `dc` and `hubctl` helpers from
the approved exact deployment checkout. These are diagnostic commands, not a daily checklist
to run without a reason:

```bash
hubctl status
dc ps
sudo python3 /opt/stpd-deploy/source/deploy/hub/maintenance.py status --config /etc/stpd/deployment.env --image-store /ABS/ACTUAL/image-store
sudo systemctl list-timers stpd-backup.timer
df -h
df -i
sudo journalctl --disk-usage
sudo docker system df -v
sudo docker buildx du
```

Check public `/health` separately from browser login. Review pending verification age, real
upload failures, paused/zero-budget state, backup freshness and the host filesystem containing
the **configured** state directory. Missing/unreadable status is not PASS. Keep measurements
and incident output private; publish only redacted source/image identities and findings.

Replace `/ABS/ACTUAL/image-store` with the observed Docker/containerd image-store directory;
do not assume it is on the state filesystem. `maintenance.py status` is read-only, includes
the host capacity result, and exits nonzero for attention/unknown or unhealthy backup status.
Capacity pressure does not itself disable scheduled backups or restart the Hub. The web page
can observe its state filesystem; it cannot qualify a separate host image-store filesystem.

Before admitting a deployment/build, run the owning capacity check with explicitly estimated
additional peak **bytes and inodes**, including temporary build files/layers. Use `0` only for
a verified already-present exact image with no extra operation allocation; an unknown build
peak is not zero. Replace all placeholders with reviewed values:

```bash
sudo python3 deploy/hub/preflight.py --capacity --config /etc/stpd/deployment.env --image-store /ABS/ACTUAL/image-store --additional-bytes APPROVED_PEAK_BYTES --additional-inodes APPROVED_PEAK_INODES
sudo python3 deploy/hub/preflight.py --config /etc/stpd/deployment.env --host
```

Both checks must pass before proceeding. `--capacity` compares available space with the
owner-defined operating margin; it does not reserve disk or validate configuration, identity,
schema or service health. Remeasure just before the operation and coordinate concurrent builds.
The separate `--host` check and runbook qualification still apply. Do not lower the reserve
or hide an unavailable measurement to admit an operation.

On pressure, locate usage with `du -xhd1` on the large filesystem directories, then inspect
the largest child. If `df` and `du` disagree, inspect deleted-but-open files with `lsof +L1`
when available. A historical ENOSPC log does not establish that space is still exhausted;
record the current timestamp, available bytes and inodes. Docker layers can be shared and uv
cache files can be hard-linked to the installed environment; do not add their displayed sizes
and claim that sum is reclaimable disk space.

The default small production Hub is a service host, **not the default full dependency-build
machine**. A full worker build installs the research dependencies and can exceed its spare
disk even when the running service fits. Use an already-authorized separate builder when a
full dependency rebuild is needed; if none exists, report that build prerequisite instead of
silently purchasing compute or trying an oversized build on production. A source-only update
may use the existing [qualified-parent refresh](RUNBOOK.md#source-only-image-refresh-with-an-unchanged-dependency-lock)
only after the capacity check; the recipe must prove an unchanged lock and exact parent/new
source. It does not qualify the new service automatically.

Keep the current and one previous **compatible qualified rollback** image locally, together
with their exact image/config/schema/backup pairing. Older history stays in immutable registry
objects plus protected receipts after remote retrievability has been verified. Before removing
one specifically identified unused local image/cache record, check running/stopped containers,
active builds, qualification tasks and both retained digests. Record before/after physical free
space. Do not run broad `docker system prune -a --volumes`, delete Docker/containerd internals,
or remove all dangling images by habit; an untagged object may still be required for rollback.

Preserve Operations SQLite and its WAL/SHM, configured state and retired recovery directories,
external identity/configuration secrets, Caddy TLS state, backup receipts and raw/quarantined
evidence. Successful scheduled snapshots have their own verified-delete rule; failed/manual
snapshots require reviewed retention, not a blanket age rule. When space is critically low,
do not begin a large build, schema migration, vacuum or another full local backup before
freeing measured disposable space. `hubctl pause` pauses compute dispatch, **not upload
verification**; it is not a disk-write freeze. Follow the runbook to quiesce the actual writers
when recovery requires it, including any already-running backup container.

[Consistent backup](RUNBOOK.md#consistent-private-off-host-backup),
[restore](RUNBOOK.md#restore-into-paused-state) and schema migration remain owned by the runbook.
The backup service covers Operations SQLite, not the full host. Retain provider access, SSH
recovery and external secrets/TLS/configuration through the separate protected recovery
inventory. Prove an isolated compatible restore after schema/deployment changes. Until a
separately tested off-host alert channel exists, inspect status daily; neither the cloud page
nor a dead host can promise to notify the operator of its own outage.
