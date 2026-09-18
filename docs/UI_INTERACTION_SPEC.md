# Platform UI and interaction specification

Presentation consumes typed Recording, Policy and Connector services. It never
owns native legality, input delivery, causal proof or research admission.

## Accepted direction: complete in-game workbench (2026-09-18)

The owner requires an in-game primary workbench, with an optional external window.
This is the delivery target, not a claim about the currently installed UI. An
external-browser shortcut alone does not satisfy it. Today the Mod only presents
Recorder and Runtime controls and tells the user to prepare models elsewhere.

Use one application backend and task/state model, exposed through two presentations:
the in-game workspace and the existing external Workbench. Do not create separate
model registries, dataset stores, training jobs, account state or control owners.
The native UI consumes model-neutral typed application APIs; Python owns loading,
research and long-running tasks. Keep that work off the game's main thread and do
not import STPD/Qwen into the Mod. Exact loopback service discovery and bounded
commands need a reviewed contract; never scan arbitrary ports or accept commands
or URLs from untrusted manifests. Backend lifecycle/startup and unavailable-service
recovery must be part of the user flow, not a terminal command left to the player.

Primary game page: selected model, readiness, one **Load and take over** action,
**Pause and take over manually**, **End session**, and compact current activity.
The main action prepares/loads the chosen model as needed, checks current game
binding, completes the existing Recorder handoff, and starts Runtime Auto. It is
idempotent at the application-intent level; repeated clicks cannot create duplicate
loads or replay uncertain native submissions. Pause must remain available during
loading and inference. Both presentations show the same state and cancellation.
One-step and score-only remain secondary diagnostics, not required normal steps.

The workspace also needs navigable recording/history, data/datasets, training/jobs,
models/evaluation and settings pages, progressively disclosed rather than packed
onto the game-control page. Data-intensive operations remain backend jobs; tables
are paginated and incremental status updates preserve selection, scroll and focus.
An **Open external workbench** shortcut is useful during migration and optional
after the in-game workflow is complete. Closing the panel does not stop a task.

Auto is continuous operation across supported decision surfaces, not merely one
play. Advertise **Full-game takeover** only after map, rewards, shop, events,
selectors, combat and terminal handling have a supported model/input/execution
path and bounded integration evidence. Stage 1a registrations currently admit only
whole combat-turn decisions. Until expanded, label their control **Combat takeover**
and explain a handoff on unsupported surfaces. Never silently filter actions,
invent a fallback strategy, retry unknown delivery or describe AI actions as Human
training data. A weak policy can still run continuously; strategy quality and
interface coverage are separate acceptance results.

Delivery order: repair the observed native-run blockers and report verification;
connect in-game discovery/model selection/load/control and external shortcut;
extend supported surfaces and verify continuous takeover; then bring the remaining
Workbench pages into the same in-game navigation. Every increment retains working
manual recovery. Installed UI and native canary evidence must be refreshed for Mod
changes; existing load evidence does not transfer to a rebuilt UI.

## Workspace

A small visible Platform launcher opens Human Recorder or Agent Run. There is
no K shortcut. Escape/Close hide the workspace; controls, drag and resize handles
capture pointer input only within their bounds. Position, size, selected tab and
compact preference are local presentation state, versioned and fail-soft.

Normal Recorder shows lifecycle, primary counts, recording controls and decisions.
Detailed accounting is optional. Selecting a row opens a bounded evidence
inspector: decision/root/parent/native owner, action, state/catalog/Read facts.
Unavailable facts remain unavailable. Child success never proves parent success.

## Compact modes

Recorder compact genuinely reduces panel bounds. Its content is only recorded
canonical actions, real recording failures and latest three decision entries.
Restore/drag remain presentation affordances. Counters come from the owner, never
from the bounded feed or compatible legacy record count. Missing or incomplete
accounting shows `—`; it cannot become zero.

Real failures are in-scope accepted Human decisions whose recording failed
closed, lacks a proved successor, or lost canonical persistence. Native cancel,
pre-Commit abort, presentation-only cancel, unsupported actions and internal
native diagnostic invalidations are separate non-success dispositions. Status4
and event batch2 carry that distinction; UI does not classify reason strings.

Agent compact shows observed Policy mode/controller and latest action/Receipt,
with Return to Human through the existing typed Policy service. It introduces
no gameplay button, legality reconstruction or automatic retry. Missing Policy
service remains unavailable; Human is the safe initial mode.

## Performance and evidence

Closed workspace performs no UI polling. Recorder reads Recording status/events
without fetching Connector Snapshot/HTTP. Agent polls only while visible. Loaded
assembly identity is cached because it is immutable for that process. The feed
is bounded; a reconnect gap rereads retained events and declares lost history.
Totals remain owner-provided even when older rows are evicted.

Loaded UI, launcher toggle and compact bounds are separate verification facts.
None qualifies Human action capture. Current schema counts, exact candidate
identity, native run boundaries and immutable offline audit own the final gate.
