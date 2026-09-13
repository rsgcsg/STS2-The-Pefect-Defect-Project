# New Engineer Guide

STPD studies candidate-ranking models using exact Platform evidence. It does not run a
second game engine. Start with README, AGENTS, [Document Map](DOCUMENT_MAP.md),
[Current Context](memory/CURRENT.md) and the owning source/tests.

For collecting data or viewing uploads, use the [default project workflow](B_PIPELINE_HANDOFF.md)
and [console guide](PROJECT_CONSOLE.md). Select the approved exact release combination, run
the lightweight collector launcher, sign in and bind the computer, then attach the dedicated
campaign once. Collectors do not need research dependencies, model weights, a Platform checkout
or cloud storage keys. The same account sees authorized cloud records from either shell;
the local queue is visible only beside that collector.

For changing code, training tooling or research, use the complete environment and gate:

```bash
uv sync --locked --all-extras
npm ci
uv run --locked python tools/project.py context
uv run --locked python tools/project.py check
```

Resolve the current remote develop and active PRs before work. Historical combat-v0 and H1
smokes remain valuable but are not the next Full-Run research campaign. Learn the authority
boundary before changing data: H != S, public actions != authoritative semantic actions.

[Engineering Governance](ENGINEERING_GOVERNANCE.md) explains evidence and review;
[Testing](TESTING.md) defines the portable gate; [Development Workflow](DEVELOPMENT_WORKFLOW.md)
defines collaboration. Neither a synthetic smoke nor a finished training process is a
scientific result. Source/test evidence, Human runtime evidence and model-quality evidence
must be reported separately.
