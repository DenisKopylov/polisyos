# ADR-0056: WGI/WDI via fabric WorldBankConnector, WVS as new fabric connector

## Status
Proposed

## Date
2026-02-28

## Context
The policy engine needs access to World Governance Indicators (WGI) and World
Development Indicators (WDI) datasets, both published by the World Bank. A
WorldBankConnector already exists in the fabric layer and handles authentication,
rate-limiting, and caching for World Bank APIs. The World Values Survey (WVS) is
a separate data source with its own access patterns and wave-based temporal
structure that does not fit into the existing World Bank connector.

## Decision
1. Route all WGI and WDI data requests through the existing
   `fabric.connectors.sources.WorldBankConnector`, reusing its pagination and
   retry logic.
2. Introduce a new `fabric.connectors.sources.WVSConnector` dedicated to WVS,
   implementing wave-aware temporal resolution and its own download/cache
   strategy.
3. Register both connectors in `builtin_profiles.py` so they are discoverable
   via the standard source profile mechanism.
4. Add contract tests (`wvs_contracts.py`) that validate the WVS connector
   against the shared `SourceConnector` protocol.

## Consequences
### Positive
- Reusing WorldBankConnector for WGI/WDI avoids duplicating auth, retry, and
  caching logic across multiple connectors.
- A dedicated WVS connector can model wave-based temporal semantics accurately
  without polluting the World Bank abstraction.
- Both connectors follow the established fabric source protocol, keeping the
  connector surface uniform.

### Negative
- Adding a new connector increases the maintenance surface and requires its own
  integration test suite.
- WVS data access patterns may evolve across survey waves, requiring periodic
  connector updates that are decoupled from World Bank release cadences.
