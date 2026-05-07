# Foundry Calibration Unit Tests

- Owner: team-foundry
- Purpose: unit tests for Foundry calibration algorithms, score normalization, and calibration artifact contracts.
- Allowed contents: deterministic calibration tests, small fixtures, golden expectations, and calibration-specific helper modules.
- Local verification: `uv run pytest tests/unit/foundry/calibration -q`
- Maintenance: update tests with calibration contract changes; stale golden data requires owner approval and a refresh note.
