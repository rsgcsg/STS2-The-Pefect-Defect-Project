# Project console: local collection and cloud visibility

The project uses one browser interface in two modes. The local console runs beside the
collector. Its personal project views and the cloud console use the same account and scoped
Hub projections. Its additional local scope shows unuploaded records and the owned queue.
Personal sessions, device upload credentials and native evidence authority remain separate.
[ADR-0005](adr/0005-local-cloud-console.md) preserves the original console boundary;
[ADR-0006](adr/0006-project-members-and-local-models.md) defines current member/admin and local
model capabilities. These pages describe current source, not proof that an older deployed
release has the new UI. Use a qualified exact release combination and its service/Human receipts.

Start with the [default project workflow](B_PIPELINE_HANDOFF.md) to obtain an approved exact
combination, install it and complete daily recording setup once. This guide owns screen meaning and
account/recovery behavior. The project cloud entry is [hub.2-fire-2.com](https://hub.2-fire-2.com/);
cloud project data requires an invited login. A successful deployment does not authorize
collection or make historical receipts current evidence.

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

Choose **打开云端** from the local page, or open the configured Hub's `/app/` from another device.
Cloudflare Access handles browser sign-in; the Hub verifies its signed identity and applies
current Hub `member`/`admin` membership. Device uploads continue through `/v1/*`, independently
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

In **账号与电脑**, a computer entry means a registered Workbench profile. Two entries can
come from one physical Mac or PC when it deliberately uses two independent configurations.
Use distinct names and private config/state directories for different accounts. Each owner
uses their own device quota; signing out does not transfer a device or its existing data.
The local queue belongs to that profile, while shared project views follow its signed-in
account. Multiple profiles can stay open in one browser. They do not isolate files from other
processes running as the same OS user; separate OS accounts provide that boundary.

| Page | Purpose |
|---|---|
| 概览 | persisted local setup stages, local/authorized cloud counts, known quality totals and the latest uploads |
| 采集记录 | paginated sessions, native run boundaries, owner quality, transfer stages, receipt and timeline |
| 数据集 | authorized immutable Dataset metadata, source references and research usage |
| 数据统计 | actual received totals, owner summary coverage and available facets; unknown stays unknown |
| 数据下载 | explicitly permitted immutable selection, inventory and checksummed payload downloads |
| 训练与分析 | existing Dataset/job/result lineage and analysis; job submission remains with the owning CLI and budget gates |
| 模型与评估 | model artifact lineage; local catalog, compatibility checks and explicit supported Runtime controls |
| 账号与电脑 | profile available at first verified login; explicit computer pairing and separate upload authorization |
| 录制与上传 | daily default, saved device-owner consent, local preparation/binding/upload activation; topic activities in advanced options |
| 成员管理 | browser-admin invitations, current status, quotas and explicit revocation |
| 系统 | connection, source/lock, role scope, available backup state and explicit operational non-claims |

“已录入” means durable canonical decisions. “真实失败” comes from Platform authoritative
disposition, not free-text error matching. Normal cancellations, diagnostics and unsupported
non-decisions are separate. Failed decision evidence may be successfully uploaded and remains
valuable for maintenance. “云端已验收” means receiver integrity/contract verification; it is
not a Human-origin, complete Full-Run, research-admission or model-quality certificate.

Unknown archival quality is shown as unknown. Global quality counters identify missing/partial
summary coverage; the first page is not used to estimate all history. **数据统计** distinguishes
received sessions, native runs and decisions. Facets are limited to actual owner-provided facts;
missing categorization or unuploaded local sessions do not become zero or guessed categories.
Detailed facets count projected canonical-record occurrences only where profiling succeeded;
they expose missing sources/unknown values and do not claim cross-source deduplication or
complete coverage of every recorded native decision. Research admission depends
on a selected input set and exact code, not just one uploaded collection. Dataset references
show actual use without inventing a current admission report for unassessed data.

Upload attempts include normal receipt checks. A stale cloud connection preserves the latest
confirmed receipt and its observation time. No percentage/ETA or historical phase timestamp is
fabricated. The list supports 25/50 rows; the search box explicitly filters only the current page.

## Recording setup and saved state

**录制与上传** starts with the administrator's daily default. Members review the purpose and
explicitly confirm Human origin, upload and project-member sharing. No checkbox is preselected.
The cloud administrator edits the default with name, description and consent fields; a new
purpose/consent version does not replace already saved declarations. Topic activities and
previous enrollments stay under **高级选项：专题活动与已有授权**.

Local setup distinguishes five stages: account/device, recorded consent, saved configuration,
current game connection and background upload. **准备本机录制配置** creates inactive private
paths; **绑定本机录制目录** uses the packaged Platform helper while the game is closed; after
launching the game, **启用本机上传** requires fresh native binding and delivery preflight.
The binding field accepts a local game directory only on the collector's workbench. Cloud
views cannot bind local files, start the game or activate its uploader.

Refresh and a new browser session read persisted consent/configuration again. They do not
repeat attestation or infer native readiness from a saved file. A stopped game may have a
configured destination without a confirmed loaded identity. A running uploader and a verified
remote receipt are separate observations. Missing or invalid state remains explicit. An existing
attached enrollment remains visible when it is older than the first page or no longer the default.

In **采集记录**, activity names come from the exact verified upload/device/enrollment join.
Unlinked history and not-yet-associated local rows stay explicit; names alone grant neither
sharing permission nor research admission. The current-page filter accepts activity names.

Daily template v2 separates consent/purpose from installed software. Software changes alone do
not renew that consent; every actual tool, native load and outbox keeps an exact identity.
Historical v1 templates keep their original software pins. An existing outbox is not upgraded
by registering another tool, and controlled rollover is not automated in this bounded workflow.
See [maintenance](B_PIPELINE_HANDOFF.md#daily-work-upgrades-and-incidents) before updating.

## Existing data and upgrades

New verified data materializes safe summaries through the owning APIs. Existing immutable
bundles and receipts retain their original IDs. To populate old local metadata, stop the owning
delivery worker and explicitly run the Platform `delivery_cli summarize` command described in
its version-pinned DELIVERY guide, then reopen the project. This re-verifies existing bundles;
it does not repack, upload, reinterpret failed dispositions or change prior receipts.

The Hub operator uses `console-refresh` to index existing verified artifacts. Browser GETs never
perform this work. Updating code or an index is not permission to enroll historical Human data
in a new consent scope. Upgrade the exact developer combination, never just a sibling import.

Category profiles are explicit, bounded owner work. Use `python -m stpd.hub statistics-refresh
--upload EXACT_UPLOAD_ID` (or repeat `--dataset-id EXACT_DATASET_ID`), together with the deployed
state/store arguments, to materialize up to ten sources. The result distinguishes available
profiles from failed projections. It changes no receipt, Dataset admission or source artifact.
The administrator API `POST /app/api/admin/statistics/refresh` accepts the same bounded
`upload_ids` / `dataset_ids` selection with browser Origin/CSRF proof; it performs CPU work and
is not called by page refresh. No UI request infers categories from action labels.

New consented enrollments bind sharing only after exact receiver verification. For a historical
upload, an owner can use `python -m stpd.hub collection-sharing --upload EXACT_UPLOAD_ID
--evidence APPROVAL_SHA256 --approve-sharing` only after reviewing its explicit scoped approval;
`--revoke-sharing` prevents subsequent export reads. Neither action rewrites old consent or
deletes data already downloaded. An automatic verifier retry never overwrites a revoked grant.

## Incidents and future work

Inspect the collection detail for the owning error, exact IDs and last confirmed stage. Preserve
the original recording, bundle and receipts. Public issue reports contain reviewed, redacted
summaries; private evidence is transferred only within its authorized scope. Repair the owning
repository, add a regression, publish a new exact candidate and canary it. Do not erase failures
or copy credentials into screenshots, issues or chat.

Ordinary members may use supported project actions and explicitly shareable data exports.
Research job submission remains with its existing CLI; viewing jobs is not launch permission.
Sensitive administrator actions require a current cloud-browser session; the local workbench
links to that screen rather than reusing its upload or personal token as an admin credential.
Membership removal is immediate at Hub authorization, without restarting a roster file. Turning
membership back on does not silently restore previously revoked computers. Jobs, budgets and
provider uncertainty still belong to their existing owners; no UI action bypasses compute
limits. Zero launch budget does not stop an already active provider job.

### Data selection and local model evaluation

**数据下载** freezes a bounded immutable inventory before downloading selected bytes. It does
not build a new training Dataset or silently repack all history. A raw collection needs an explicit
durable sharing grant tied to its exact verified upload; legacy upload consent alone is
insufficient. Dataset/derived downloads must satisfy the same source-grant policy, and knowing a
sealed test/Gold artifact ID cannot bypass it. Model weights do not grant access to parent training
data. Missing sharing consent is displayed as unavailable while authorized metadata can remain visible.

**模型与评估** keeps cloud artifacts and local execution separate. A downloaded Full-Run model
can appear in the catalog while remaining unsupported for gameplay. Only a reviewed local policy
registry entry selects executable adapter code. Optional Runtime installation uses its exact
package inventory; collectors do not need model dependencies merely to record or browse data.
Readiness checks artifact/config/source hashes, the installed Runtime/Connector, Node, required
checkpoint evidence and backend. Model weights are checked during loading; native compatibility
is checked by the Runtime before decisions. A download or `ready_to_load` does not prove either.

The registered executable selection is the retained **S1 Defect A0 ordinary-combat** lane, bounded
by its exact policy support manifest (`combat_turn`, play/end-turn; no selector or Full Run).
It requires its original checkpoint/support files and CUDA/BF16 backend; a Mac does not become
compatible by installing the UI. Current Full-Run offline views have no qualified online-input
parity/adapter here, so **Full-Run online evaluation remains BLOCKED** until that separate owner
work is implemented and qualified. Do not manufacture missing features or filter the native catalog.

A compatible local selection loads in Human mode first. Shadow, One-Step, Auto, Human and Stop
use typed Platform Runtime requests; deliberate execution is distinct from loading. Cloud pages
never start a local game. An uncertain effectful response is not automatically resent. A workbench
restart requires exact instance recovery before new execution. Local Agent evidence and bounded
operation reports remain separate from Human collection, win-rate evaluation and scientific results.

Runtime commands use the versioned HTTP/2 mutation routes and the process run ID captured at
startup. The Runtime checks that ID before any command, including Stop during Workbench shutdown.
A different process reusing the same port cannot receive the old Workbench's command. An older
HTTP/1 server rejects the new routes; reconnect or upgrade explicitly instead of retrying delivery.
If Stop cannot be confirmed and the Workbench has no owned process handle that proves exit,
shutdown preserves the previous Runtime identity and requires recovery after restart. A failed
recovery observation also retains that requirement; it never turns an uncertain process into idle.

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

Use the exact developer combination selected in reviewed release notes. Git, Python 3.11 with uv,
Node 20+ and the qualified Mod/fixed collection tool remain explicit prerequisites. The
workbench setup installs the locked `cloud` profile; daily collection needs no Torch,
Transformers, model weights, R2 keys or Cloudflare account. It uses the fixed collection tool.
Initial native installation and rollback still use an operator-retained Platform checkout on
the game computer; see [developer kit installation](DEVELOPER_KIT_INSTALL.md).
Full research/CI environments continue to use `--all-extras`.

1. From the approved STPD checkout run the launch command in the
   [project workflow](B_PIPELINE_HANDOFF.md#download-and-connect-once), retaining its explicit `--config` path.
   The launcher installs locked dependencies, preserves existing project settings and opens
   the same loopback workbench on subsequent launches. An upgrade first stops the exact
   predecessor and explicitly refreshes setup; the launcher never changes branches or rewrites it.
2. Open **账号与电脑**, name this computer, and choose **登录并绑定这台电脑**.
   Follow the displayed cloud link. Use an invited project email and its email verification code.
   The first verified invited login establishes the project profile immediately; device binding
   is a separate explicit step. Public self-registration is disabled.
3. Compare the computer name and pairing code on both pages, then approve. The local page
   obtains the grant itself; there is no copying tokens, callback URL or browser-local secret.
   The **查看范围** selector shows project-wide or one authorized computer's cloud data on
   either surface; **这台电脑** additionally shows the local queue.
4. Stop the workbench, register the trusted fixed tool, then reopen the same configuration,
   as shown in [daily recording setup](B_PIPELINE_HANDOFF.md#set-up-daily-recording-once-reopen-it-thereafter).
   Registration holds the stopped-workbench lock; closing a browser tab is insufficient.
5. Open **录制与上传**, review the daily default and give the three explicit declarations.
   Prepare local files, close the game and bind its recording directory, then launch and refresh.
   Enable uploads only after the current native connection passes. No topic activity is required.
   Finish this terminal's bounded Recorder Close-to-receipt check before routine recording.

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

## Decision dataset candidate

[ADR-0007](adr/0007-fixed-decision-datasets.md) adds **对局与片段** and dataset creation.
After a shared verified upload, the bounded background worker prepares its run summary.
The game page shows the latest 100 shared profiles, with incomplete/complete and unknown/win/loss
separated. Failed profiles do not change receiver acceptance. It never calls uploads unique games.

In **数据集**, select received recordings, keep permissive defaults or select optional filters,
then **预览选定记录**. Refresh after background completion, inspect counts/exclusions/run facts,
and use **按此预览生成固定数据集**. The resulting artifact ID identifies an immutable version.
Use **数据下载** to select that artifact's Parquet and selection report. New uploads require a
new preview/build. Existing artifact detail links remain valid. Collection sharing is checked
again; revocation also blocks future downloads of derived decision bytes.

This candidate does not start training. The strict old Full-Run loader remains unchanged;
training integration must explicitly select the new decision-dataset contract.
