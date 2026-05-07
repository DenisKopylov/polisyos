# Foundry Property Tests

- Owner: team-foundry
- Purpose: property tests for Foundry methods, runtime behavior, and model execution invariants.
- Allowed contents: Foundry-specific strategies, invariant tests, reusable property fixtures, and method-family subtrees.
- Local verification: `uv run pytest tests/property/foundry -q`
- Maintenance: keep tests mapped to the Foundry source topology; obsolete method-family fixtures should be removed with the owning migration.
