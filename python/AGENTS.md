# Python component guide

The repository-root AGENTS.md and docs/DEVELOPMENT_WORKFLOW.md own Git and promotion.
This directory is one Python environment, not an independent repository.

Read README.md, docs/DOCUMENT_MAP.md and the owning code/tests. Current project
applications live in spireagent; model, data projection, training and evaluation
live in stpd. Shared storage/identity/codecs must not depend on application UI.
Hub owns member/device access and durable operations; registries are rebuildable.
Research consumes Platform public APIs and verified bundles. Preserve H != S,
complete candidate catalogs, exact parent/root lineage and Commit/successor separation.

From this directory, uv sync --locked --all-extras prepares developer dependencies.
Use tools/project.py check for the Python component gate; npm run check at the
repository root runs all components. Collector setup uses the cloud extras only.

Normal merges retain source provenance. Use root G0-G6 impact classes with
explicit research/data/model tags; older STPD G-number reports are historical.
Do not rewrite historical schemas, sources, evidence or producer identities.
No raw Human data, credentials, model weights or proprietary files enter Git.
Portable tests do not qualify a service, Human origin or model quality.
