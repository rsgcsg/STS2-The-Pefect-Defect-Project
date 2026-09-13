# Project console: local collection and cloud visibility

The project uses one browser interface in two modes. The local console runs beside the
collector. Its personal project views and the cloud console use the same account and scoped
Hub projections. Its additional local scope shows unuploaded records and the owned queue.
Personal read sessions, device upload credentials and native evidence authority remain separate. [ADR-0005](adr/0005-local-cloud-console.md) defines this boundary.

## Daily collection

Run the approved developer combination through the existing entry:

```bash
uv run --locked python -m stpd.workbench project doctor --config /ABS/project.json
uv run --locked python -m stpd.workbench project open --config /ABS/project.json
```

The browser shows the actual loopback address. Device and personal tokens stay in private local files; the device token is injected only
into the delivery child environment. The personal token stays in the local account BFF. It is not pasted into a web form and is never sent to a third-party browser
identity provider. After setup, ordinary uploads do not require a fresh cloud browser login.

The Human uses the qualified game Mod to record and presses Recorder **Close**. The delivery
service packs a sealed collection, uploads its bytes and reconciles the exact remote receipt.
The collection page separately shows recording quality, delivery and research use. A session
may contain several runs or a partial run; the unassigned session context is not another game.

Closing the browser tab does not stop delivery. `project stop --config /ABS/project.json`
stops the owned background service. After a computer restart or an explicit stop, reopen the
same configuration to resume sealed work. This is not an installed OS autostart service.
Local raw sessions and bundles are not automatically deleted after cloud success.

## Cloud login and connection

Choose **打开云端** from the local page, or open `https://<hub>/app/` from another device.
Cloudflare Access handles browser sign-in; the Hub verifies its signed identity and applies
the operator's role/device allowlist. Device uploads continue through `/v1/*`, independently
of browser cookies. Do not distribute Hub admin/R2/Modal credentials to collectors.

The local collection detail links to the exact remote `upload_id`; the content identity is
checked before remote detail is associated with a local row. The cloud page never reaches
into localhost or remotely controls the game. It can show received records while the collector
computer is off, but it does not know that computer's unuploaded queue. The device page shows an explicit last
contact timestamp when reported; that timestamp is not a current-online promise.

The public Hub landing page contains login and developer-guide links. The guide is bound to
the deployed public source revision (also public in health); no account/device/collection
data appears there. Only its packaged stylesheet is served anonymously. Protected routes are unavailable until
browser authentication is configured. Activation and role configuration are documented in
the [Hub runbook](../deploy/hub/RUNBOOK.md). A running API does not prove a successful browser login.

## Pages and interpretation

| Page | Purpose |
|---|---|
| 概览 | local/authorized cloud counts, known quality totals and the latest collections |
| 采集记录 | paginated sessions, native run boundaries, owner quality, transfer stages, receipt and timeline |
| 数据集 | authorized immutable Dataset metadata, source references and research usage |
| 作业 | bounded read-only job/attempt/result state and compute limits |
| 模型与评估 | authorized existing artifacts/lineage; local download receipts remain distinct from loading |
| 账号与电脑 | invited account, explicitly owned/authorized computers, pairing and separate upload authorization |
| 系统 | connection, source/lock, role scope, available backup state and explicit operational non-claims |

“已录入” means durable canonical decisions. “真实失败” comes from Platform authoritative
disposition, not free-text error matching. Normal cancellations, diagnostics and unsupported
non-decisions are separate. Failed decision evidence may be successfully uploaded and remains
valuable for maintenance. “云端已验收” means receiver integrity/contract verification; it is
not a Human-origin, complete Full-Run, research-admission or model-quality certificate.

Unknown archival quality is shown as unknown. Global quality counters identify missing/partial
summary coverage; the first page is not used to estimate all history. Research admission depends
on a selected input set and exact code, not just one uploaded collection. Dataset references
show actual use without inventing a current admission report for unassessed data.

Upload attempts include normal receipt checks. A stale cloud connection preserves the latest
confirmed receipt and its observation time. No percentage/ETA or historical phase timestamp is
fabricated. The list supports 25/50 rows; the search box explicitly filters only the current page.

## Existing data and upgrades

New verified data materializes safe summaries through the owning APIs. Existing immutable
bundles and receipts retain their original IDs. To populate old local metadata, stop the owning
delivery worker and explicitly run the Platform `delivery_cli summarize` command described in
its version-pinned DELIVERY guide, then reopen the project. This re-verifies existing bundles;
it does not repack, upload, reinterpret failed dispositions or change prior receipts.

The Hub operator uses `console-refresh` to index existing verified artifacts. Browser GETs never
perform this work. Updating code or an index is not permission to enroll historical Human data
in a new consent scope. Upgrade the exact developer combination, never just a sibling import.

## Incidents and future work

Inspect the collection detail for the owning error, exact IDs and last confirmed stage. Preserve
the original recording, bundle and receipts. Public issue reports contain reviewed, redacted
summaries; private evidence is transferred only within its authorized scope. Repair the owning
repository, add a regression, publish a new exact candidate and canary it. Do not erase failures
or copy credentials into screenshots, issues or chat.

Project data views remain read-only. Browser mutations are limited to deliberate identity
approval/denial; local account actions also permit explicit owner-auth recovery. Jobs, budgets
and operator credential rotation remain with owning CLI/SSH procedures. Zero launch budget does not stop an already active provider
job. There is no new Full-Run model adapter or live model activation button. Offline/online
evaluation, cloud game/RL and scientific qualification have separate contracts and gates.

The system page is not an outside-host alerting service. A backup status is not the backup bytes,
and an SQLite restore is not whole-host disaster recovery. Missing evidence is displayed explicitly.

After upgrading checkout/dependencies, `project status` and `project stop` can still
address the predecessor's validated local runtime even if its combination is old.
Starting a new service, doctor and model downloads still require current setup.
Stop first, run explicit replacement setup with the preserved campaign/configuration,
rebuild summaries while delivery is stopped, then reopen. No manual process kill is needed.

The legacy Hub `verify_attempts` field counts operational verification exceptions
within the current retry cycle, not all verification invocations. A successful
verified receipt can correctly have zero. The UI labels it as processing anomalies;
explicit operator re-delivery resets the counter. Quarantine is a separate disposition.

## Download, sign in, bind once

Use the exact developer candidate supplied by the operator. Git, Python 3.11 with uv,
Node 20+ and the qualified Mod/fixed collection tool remain explicit prerequisites. The
workbench setup installs the locked `cloud` profile; collector computers do not need Torch,
Transformers, model weights, a Platform checkout, R2 keys or a Cloudflare account.
Full research/CI environments continue to use `--all-extras`.

1. From the approved STPD checkout run `python tools/open_workbench.py --hub-url https://YOUR-HUB`.
   The launcher installs locked dependencies, preserves existing project settings and opens
   the same loopback workbench on subsequent launches. An upgrade first stops the exact
   predecessor and explicitly refreshes setup; the launcher never changes branches or rewrites it.
2. Open **账号与电脑**, name this computer, and choose **登录并绑定这台电脑**.
   Follow the displayed cloud link. Use an invited project email and its email verification code.
   The first approved login creates the project profile. Public self-registration is disabled.
3. Compare the computer name and pairing code on both pages, then approve. The local page
   obtains the grant itself; there is no copying tokens, callback URL or browser-local secret.
   The **查看范围** selector shows project-wide or one authorized computer's cloud data on
   either surface; **这台电脑** additionally shows the local queue.
4. A new device still needs the operator's dedicated campaign configuration and explicit
   Human-origin/upload attestation. Pairing never enrolls an old recording or grants consent.
   Reopen that configuration, pass owning preflight, and perform its bounded Close-to-receipt gate.

The device may remain authorized when the person logs out. Local logout clears personal pages
and revokes its short-lived personal session when Hub is reachable; otherwise expiry bounds
that remote session. It retains the upload grant. Closing the browser does not stop background
work; restarting the computer requires opening the workbench again. Account switching never
reassigns an existing device, campaign, bundle or outbox to another person.

## Credential recovery

Hub 401/403 becomes Platform's typed `auth_blocked`, separate from R2 transfer rejection or a
native recording failure. Correct the credential for the **same logical device** first. An
operator rotates that device in Hub and supplies a private replacement JSON containing
`hub_url`, `device_id`, `token`. Stop the workbench, then run:

```bash
uv run --locked python -m stpd.workbench project credential --config /ABS/project.json --credential-file /PRIVATE/replacement.json
uv run --locked python -m stpd.workbench project open --config /ABS/project.json
```

Choose **恢复已修正授权的上传** in **账号与电脑**. The workbench validates the actual Hub device,
stops the owned delivery child, invokes the versioned Platform `resume-auth` API under its
stopped-worker lock, then restarts the child. Exact archive/seal/upload/receipt identity is
preserved. Other incidents are not cleared; legacy free-text failures require separate owning
audits. Device token rotation never substitutes a new device ID or deletes transport state.

Credential publication fsyncs the file and, on POSIX, its containing directory before
acknowledging a pairing result. Windows retains atomic file replacement and process-restart
recovery; arbitrary filesystem or power-loss survival is not a qualified claim.
