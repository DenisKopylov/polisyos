# Foundry State

Related explanation: [Trinity](../../explanation/trinity.md).

Foundry runtime state is expressed as JAX-compatible dataclasses and persisted
through CAS snapshots. This page documents the boundary between compile-time
slot layout, execute-time state snapshots, and agent-simulation runtime state.

Freshness: 2026-04-17
Owner: `@foundry-owners`
Source plan: `docs/FOUNDRY_REMEDIATION_PLAN.md`, D1-L3 section in `docs/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/foundry/contracts/state.py`, `src/polisyos/foundry/layout.py`, `src/polisyos/foundry/_executor_snapshots.py`, `src/polisyos/foundry/executor.py`

This page documents `polisyos.foundry.contracts.state.GlobalState`, the
compile/execute and release-acceptance state contract. The standalone
ABM/RL package `polisyos.foundry.agent_sim.state` defines a different
`GlobalState`; use [Agent Sim](agent-sim.md) when working on that runtime
directly.

## Phase Coverage

| Source phase | State meaning |
|---|---|
| Phase 1 | Missing, malformed, or non-finite state is rejected through fail-closed guards where the runtime contract requires it. |
| Phase 2 | ProgramGraph nodes patch state through explicit slot paths, merge rules, state deltas, and snapshots. |
| Phase 3 | State objects must remain JAX-compatible for hot paths; JAX claims link to JIT and cross-backend tests. |
| Phase 4 | Snapshots, state deltas, and environment fingerprints form the replay boundary. |
| Phase 6 | Multiscale and agent-sim state fields support population, graph, and distribution-aware policy simulation. |

## How to Read This Page

- Read `polisyos.foundry.contracts.state` for what compiled programs can read
  or patch at runtime.
- Read `polisyos.foundry.layout` for `slot_id -> state_path` materialization and
  family manifests.
- Read `polisyos.foundry.executor` for state snapshot, state delta, and
  merge/apply helpers.
- Treat `GlobalState` as the replay boundary: compile and execute flows pass
  artifact refs around, while JAX executors transform the concrete state bundle.

## State Contracts

| Contract | Role |
|---|---|
| `AgentState` | Household-level agent arrays. |
| `FirmState` | Firm-level production and finance arrays. |
| `MarketState` | Aggregate market tensors. |
| `CellState` | Regional/sectoral aggregates. |
| `HouseholdCellState` | Household-cell welfare aggregates. |
| `ProcurementGraphState` | Procurement network runtime tensors. |
| `AgentSimRuntimeState` | RNG plus runtime-only distribution/network state. |
| `GlobalState` | Top-level execution state. |

## Common Usage Flow

1. Define or inspect slot specs in the slot registry.
2. Run `build_slot_layout()` to materialize the exact `slot_id -> state_path`
   mapping expected by compile and execute tooling.
3. Run `build_slot_family_manifest()` when docs, dashboards, or governance need
   grouped state families instead of raw slot rows.
4. Bind data into a concrete `GlobalState` before execute-time replay.
5. Persist the post-step snapshot from `ExecuteResult` and compare through
   replay semantics from [Observability Reproducibility](observability-reproducibility.md).

## Evidence Links

- Global state:
  `tests/foundry/test_global_state.py`
- Contract state compatibility:
  `tests/foundry/contracts/test_state_contracts.py`
- Slot layout:
  `tests/foundry/test_layout.py`
- Snapshot behavior:
  `tests/foundry/test_executor_snapshots.py`
- Merge determinism:
  `tests/foundry/test_merge_determinism.py`

## Reference

::: polisyos.foundry.layout

::: polisyos.foundry.contracts.state

::: polisyos.foundry.executor
