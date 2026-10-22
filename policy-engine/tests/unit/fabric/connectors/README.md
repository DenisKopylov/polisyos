# Fabric Connector Unit Tests

- Owner: team-fabric
- Purpose: isolated tests for Fabric connector contracts, ingestion adapters, and source platform behavior.
- Allowed contents: connector unit tests, contract fixtures, fake source clients, and source-family test subtrees.
- Local verification: `uv run pytest tests/unit/fabric/connectors -q`
- Maintenance: new connector families need local fixtures and owner docs; external service credentials must not be committed here.
- Runtime-state contract: test_connection_state_contract.py verifies missing versus explicit None, malformed cached values, atomic typed setdefault, nominal executor/observer state owners, and checked bounded HTTP response consumption.
