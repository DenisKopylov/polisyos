# Data Forge Domain Unit Tests

- Owner: team-data-forge
- Purpose: unit coverage for Data Forge domain packages and domain-specific ingestion contracts.
- Allowed contents: package-mirrored domain tests, domain fixture builders, and contract tests for source-specific adapters.
- Local verification: `uv run pytest tests/unit/data_forge/domains -q`
- Maintenance: each domain subtree owns its local fixtures; legacy domain paths should not be reintroduced outside migration windows.
