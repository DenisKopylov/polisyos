# Scientist Orchestration Unit Tests

- Owner: team-scientist
- Purpose: unit coverage for Scientist orchestration, engine protocols, workflows, and orchestrator decision surfaces.
- Allowed contents: package-mirrored orchestration tests, local fakes, workflow fixtures, and engine/orchestrator contract tests.
- Local verification: `uv run pytest tests/unit/scientist/orchestration -q`
- Maintenance: keep assertions aligned to canonical `src/polisyos/scientist/orchestration`; legacy engine paths are compatibility only.
