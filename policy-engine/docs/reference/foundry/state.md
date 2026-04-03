# Foundry State
Related explanation: [Trinity](../../explanation/trinity.md).

Foundry runtime state is expressed as JAX-compatible dataclasses. This page
documents the top-level `GlobalState`, new multi-scale cell state contracts,
and the slot-layout helpers that map slot registry entries onto those state
paths.

## Multi-Scale State

| Contract | Role |
|----------|------|
| `AgentState` | Household-level agent arrays |
| `FirmState` | Firm-level production and finance arrays |
| `CellState` | Regional/sectoral aggregates |
| `HouseholdCellState` | Household-cell welfare aggregates |
| `ProcurementGraphState` | Procurement network runtime tensors |
| `AgentSimRuntimeState` | RNG plus runtime-only distribution/network state |
| `GlobalState` | Top-level execution state |

## Reference

::: polisyos.foundry.layout

::: polisyos.foundry.contracts.state
