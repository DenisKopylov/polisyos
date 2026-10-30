# Core contract tests

This suite verifies shared typed contracts at their behavioral boundaries, including
execution plans, refs, scopes, capabilities and request/result projections. Keep a test
with the canonical owner when a contract change affects a specific package.

Run the suite from `policy-engine/` with `uv run pytest tests/unit/core/contracts -q`.
