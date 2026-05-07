# Foundry Runtime Unit Tests

- Owner: team-foundry
- Purpose: unit coverage for Foundry runtime execution, lifecycle boundaries, and method orchestration behavior.
- Allowed contents: runtime unit tests, local fakes, execution fixtures, and contract tests for runtime-facing APIs.
- Local verification: `uv run pytest tests/unit/foundry/runtime -q`
- Maintenance: keep runtime tests fast and isolated; broad integration coverage belongs under `tests/integration`.
