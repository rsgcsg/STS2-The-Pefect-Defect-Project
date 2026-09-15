# ADR-0006: Shared project membership and local model evaluation

Status: accepted design; implementation and production qualification are tracked separately.

## Decision and scope

Use two Human roles, `member` and `admin`. Both may inspect the project's shared collection
statistics, research data, training results, models, benchmarks and analysis, and download
explicitly shareable immutable data. Both may prepare a supported model and deliberately
evaluate it on their own computer. Administrators additionally manage membership, enrollment
limits, collection activities and operational access. GitHub contributor rights and machine
credentials are independent; they do not introduce extra Human console roles.

Cloudflare verifies browser identity. The Hub operations database is the only live authority
for project membership. A verified email without an active invitation or membership cannot
read project data or approve a computer. Provisioning changes the Access policy once to admit
the configured authentication method; it does not create an application Bypass. Origin JWT
verification remains mandatory. No Cloudflare administration credential is added to the Hub.

Membership changes take effect through transactional Hub services, not edits to a file followed
by restarts. Initial import is explicit, preserves exact existing subject/device/upload IDs,
and names the administrator separately; an old `operator` is not automatically promoted.
The last administrator cannot be disabled or demoted. An audited operator recovery command
remains separate from ordinary browser operations.

## User experience and ownership

One shared shell provides project views locally and at the Hub. Local scope adds unuploaded
queues and machine operations. The cloud never calls localhost or remotely controls gameplay.
Sensitive administrator mutations run in the cloud browser with current identity, exact
Origin and CSRF checks; local personal tokens cannot become administrator credentials.

New members follow invite -> download -> email login -> explicit computer approval -> choose
an assigned collection activity and declare consent -> native configuration/preflight -> first
Human Close-to-receipt check. A prepared configuration is not proof that the native recorder
uses its root. Consent is an operator declaration, never machine proof of Human origin.

Ordinary logout removes a personal session and keeps the device upload grant. Disabling a
member also revokes their sessions and owned devices; restoring membership does not resurrect
revoked credentials. Historical evidence is retained. Previously issued short-lived storage
grants may remain valid until expiry, so revocation never claims instant cancellation of all
in-flight network bytes.

## Shared data and scientific boundaries

Project-wide visibility does not imply ownership of another member's computer. Device filters
are query scope, not mutable device ownership. Shared metadata contains no other user's email,
credentials, private local paths or raw exception strings.

Totals distinguish received sessions, native runs, proved decisions, authoritative real
failures, and summary coverage. Unknown summary fields stay unknown. Category counts consume
owner-provided facts; UI code never derives validity or reconstructs game semantics.

Downloads select immutable manifests and checksummed payloads. Export creation freezes a bounded
inventory; GET does not build datasets or synchronously repack large archives. References do not
implicitly grant access to parent bytes. A single policy controls discovery and known-ID reads.
Sealed test/Gold artifacts remain protected even when their IDs are known. Old upload consent
is not silently upgraded into a project-wide raw sharing grant. New activities declare sharing
scope explicitly; historical raw grants require exact evidence and an explicit reviewed action.

Existing Datasets and experiments remain frozen. Downloading data or viewing a completed job
does not admit a Dataset, authorize compute, or establish model quality. The compute budget
remains zero until separately authorized.

## Model deployment and evaluation

Model download, integrity verification, supported-input compatibility, adapter startup, native
environment compatibility and actual gameplay are separate states. A downloaded manifest
cannot supply arbitrary shell commands. Only reviewed local adapters and exact public Runtime
packages are executable. Model dependencies are optional so recording does not require Torch,
weights or a GPU.

Platform Runtime owns controller, whole-catalog actions, delivery and Agent evidence. STPD owns
model loading and research evaluation. Local actions start in Human mode; Shadow, One-Step,
Auto and Stop use the Runtime's typed boundary. A timeout on an effectful request is not proof
of non-delivery and must not trigger a replay. AI evaluation records stay separate from Human
collection; stop/partial/technical failure is not a natural win or terminal result.

The existing frozen S1 adapter has a narrow historical support envelope. Current Full-Run
training views include execution facts not automatically available in the public online bundle.
Neither a generic download button nor a successful package install proves online parity. A
new compatible ModelView/adapter needs its own input-parity and native qualification evidence;
unsupported artifacts remain visibly blocked without invented features or game legality.

## Promotion and maintenance

Tests cover legacy migration, last-admin protection, privilege boundaries, new enrollment,
revocation, response loss, known-ID sealed access, export integrity, stale UI contexts, local
Origin/CSRF and non-replayed commands. Exact final source, CI, package, OCI and service receipts
are required. New-member login, computer binding and first Human upload are separate gates.

The default release is one reviewed workbench/Mod/tool combination with optional model packages.
Do not replace code during recording or overwrite an outbox. Backups include the operations
database and separately protected configuration/key recovery. Record a compatible rollback
pair before migration. Incidents retain failed evidence and exact identities.

After final gates, integrate through governed develop and main PRs, publish immutable releases,
and remove only branches whose work is preserved. Keep main/develop as the only long-lived
branches; preserve tags, evidence-bearing worktrees and unrelated unmerged work.
