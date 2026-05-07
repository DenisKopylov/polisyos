# Fabric Connector Unit Tests

- Owner: team-fabric
- Purpose: isolated tests for Fabric connector contracts, ingestion adapters, and source platform behavior.
- Allowed contents: connector unit tests, contract fixtures, fake source clients, and source-family test subtrees.
- Local verification: `uv run pytest tests/unit/fabric/connectors -q`
- Maintenance: new connector families need local fixtures and owner docs; external service credentials must not be committed here.
