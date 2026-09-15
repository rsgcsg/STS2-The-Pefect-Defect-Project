# Contributing to the Python components

Follow [root contribution and promotion workflow](../docs/DEVELOPMENT_WORKFLOW.md).
From python/: uv sync --locked --all-extras, npm ci, then
uv run --locked python tools/project.py check. From the root, npm run check covers
all native and Python components on the same commit. Do not maintain a second Git flow.
Read AGENTS.md and the owning model/data/application contract before edits.
