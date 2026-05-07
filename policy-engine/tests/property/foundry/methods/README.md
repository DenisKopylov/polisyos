# Foundry Methods Property Tests

- Owner: team-foundry
- Purpose: generative coverage for Foundry method catalog behavior, estimator contracts, calibration boundaries, and selection invariants.
- Allowed contents: method-level property tests, shared strategy modules, and fixtures that exercise public method contracts.
- Local verification: `uv run pytest tests/property/foundry/methods -q`
- Maintenance: add or update property coverage with each new method family; retired method fixtures require a dated removal note.
