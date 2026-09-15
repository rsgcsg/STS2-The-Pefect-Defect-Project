# Platform diagnostic service

The user console is now the project Workbench (`npm run workbench` at repository root).
This retained compatibility service has no HTML console. It is a dependency-light
Platform diagnostic and typed control API. It reads the
Environment, Policy, Human Data, Evidence, Transfer and Diagnostics domains.
Filesystem status is an explicit fallback, not live truth. The only command
it can issue is a typed Policy Runtime mode change; it cannot submit a
BoundAction, write human evidence, load a model, or start STS2.

## Start

```bash
node bin/workbench.mjs \
  --environment-root /path/to/environment \
  --policy-runtime-url http://127.0.0.1:15527 \
  --policy-root /path/to/policy-runtime-status \
  --annotator-root /path/to/annotator-local \
  --human-data-root /path/to/human-data \
  --evidence-root /path/to/evidence-store \
  --transfer-root /path/to/transfer \
  --diagnostics-root /path/to/diagnostics
```

The same roots can be configured with `--root name=path` or
`WORKBENCH_<NAME>_ROOT`. Configure the Policy Runtime with
`--policy-runtime-url` or `WORKBENCH_POLICY_RUNTIME_URL`; the URL must target a
loopback host. The JSON API is `GET /api/status`; the retired HTML route `GET /` returns 410 with the project-console entry point.
The only command API is `POST /api/policy/mode` with exactly one JSON field:
`{"mode":"human"}`, `shadow`, `one_step`, or `auto`.

Policy Runtime mode changes are accepted only when Workbench is bound to a
loopback address. A non-loopback bind remains available as a read-only status
view and returns `403 policy_mutation_loopback_only` for the mode command. The loopback mode route also requires application/json,
a supported loopback Host with the bound port, and an absent or exact same
Origin. It rejects cross-origin browser requests before forwarding to Runtime.

Policy Runtime live status is fetched from `<base-url>/status` and must match
the strict `sts2.policy-runtime/status-1` shape. Mode changes are forwarded to
`<base-url>/v2/mode` and require the strict `sts2.policy-runtime/http-2` status
envelope. `one_step` then invokes exactly one `<base-url>/v2/tick` and returns the
resulting Runtime status; Workbench never submits a BoundAction itself. Status
requests default to 1.5 seconds and commands to 45 seconds. If a command times
out or returns an undecodable response, its outcome remains unknown: the client
blocks further non-Human commands, permits status and Human handoff, and uses
the first trusted status query begun after the failure to establish the unknown
run baseline. Only a subsequently observed different run ID clears the block;
a cached pre-command ID or earlier in-flight query cannot unlock it. It
never repeats a tick. A caller timeout does not taint or settle the underlying
Runtime delivery by itself. A
configured filesystem policy
status is used only as `filesystem_fallback` when live status is unavailable;
that domain is marked `partial` and `unavailable`, never ready. Other status
files are small JSON objects. A missing root is `absent`; a configured root
without a known status file, unreadable root, or malformed status JSON is
`unknown`. Directory existence alone never implies health.

Known status filenames:

| Service | Files checked in order |
|---|---|
| Environment | `runtime-status.json`, `environment-status.json`, `status.json` |
| Policy fallback | `runtime-status.json`, `policy-runtime-status.json`, `status.json` |
| Annotator | `runtime-status.json`, `recording-status.json`, `status.json` |
| Human Data | `human-data-status.json`, `status.json` |
| Evidence | `store-status.json`, `status.json` |
| Transfer | `transfer-status.json`, `transfer-receipt.json`, `status.json` |
| Diagnostics | `diagnostics.json`, `status.json` |

## Test

```bash
npm test
```

The Workbench status DTO labels every domain with `source`, `freshness`,
`partial` and `unavailable`. `policy_runtime`/`live` is the only live Policy
claim; `filesystem`/`filesystem_fallback` is intentionally weaker evidence.

Policy commands use the HTTP-2 `/v2/*` routes and the previously observed Runtime
run ID. Reuse of the loopback port cannot retarget an outstanding command, even
when an older HTTP-1 server occupies it. Missing observations are read before the
first command; rejected identity checks never retry a command automatically.
