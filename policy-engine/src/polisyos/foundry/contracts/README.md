# Contracts (`polisyos.foundry.contracts`)

`contracts` - shared runtime contracts for Foundry execution, agent simulation and
state/patch semantics.

## Role in System

- **Depends on:** `polisyos.foundry.agent_sim.distributions`, `polisyos.ir.observation`
- **Used by:** Foundry executor, data_plane bindings, agent_sim wiring and state loaders
- Defines the common state objects and patch-oriented protocol boundary for runtime code.

## Key Concepts

- **State dataclasses** - `GlobalState`, `AgentState`, `FirmState`, `MarketState`.
- **Multiscale runtime** - `CellState`, `HouseholdCellState`, `AgentSimRuntimeState`.
- **Procurement graph** - `ProcurementGraphState` stores edge-level procurement dynamics.
- **Mechanism contracts** - patch-oriented interfaces and complex mechanism wrappers.
- **Fidelity** - explicit fidelity levels for execution and contract gating.

## Public API

| Type/Function | Description |
|---|---|
| `GlobalState` | Top-level runtime state for Foundry / agent simulation. |
| `AgentState` | Household/agent state array bundle. |
| `FirmState` | Firm state array bundle. |
| `MarketState` | Aggregate market state. |
| `CellState` | Regional cell-level state for multiscale runs. |
| `HouseholdCellState` | Household-cell aggregation state. |
| `AgentSimRuntimeState` | Runtime wrapper with RNG and multiscale substate. |
| `ProcurementGraphState` | Edge-oriented procurement graph state. |
| `Mechanism` | Base mechanism contract. |
| `ComplexMechanism` | Composite mechanism contract. |
| `PatchMap` | Patch mapping used by merge/runtime layers. |
| `PatchRecord` | Recorded patch emitted by mechanisms. |
| `FidelityLevel` | Execution fidelity enum. |

→ Full reference: [docs/reference/foundry/index.md](../../../../docs/reference/foundry/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 4 Python files
- Exports: 13
