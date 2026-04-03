# Foundry State
Related explanation: [Trinity](../../explanation/trinity.md).

Foundry runtime state is expressed as JAX-compatible dataclasses. This page
documents the top-level `GlobalState`, new multi-scale cell state contracts,
and the slot-layout helpers that map slot registry entries onto those state
paths.

## How to read this page

- Read `polisyos.foundry.contracts.state` when you need to know what compiled programs are allowed to read or patch at runtime.
- Read `polisyos.foundry.layout` when you need to turn slot-registry declarations into concrete state paths, family manifests, or docs tables.
- Treat `GlobalState` as the replay boundary: compile and execute flows pass refs around, but JAX executors transform this concrete state bundle.

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

## Common Usage Flow

1. Define or inspect slot specs in the slot registry.
2. Run `build_slot_layout()` to materialize the exact `slot_id -> state_path` mapping expected by compile and execute tooling.
3. Run `build_slot_family_manifest()` when docs, dashboards, or governance tooling need grouped state families instead of raw slot rows.
4. Bind data into a concrete `GlobalState` before execute-time replay.

## Reference

::: polisyos.foundry.layout

::: polisyos.foundry.contracts.state
