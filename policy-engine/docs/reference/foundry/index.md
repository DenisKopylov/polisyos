# Foundry
Related explanation: [Causal Engine](../../explanation/causal-engine.md).

`polisyos.foundry` is the execution layer that turns compiled policy programs
into state transitions, calibration loops, and agent-simulation runtime
updates. The public surface is intentionally split between compile/execute,
calibration, methods, runtime state contracts, and agent-sim wiring.

## Page Map

| Page | Scope | Primary modules |
|------|-------|-----------------|
| [Compile Execute](compile-execute.md) | Root API, compile requests, execute requests, input binding bridge | `foundry`, `foundry.compile.api`, `foundry.execute.api`, `foundry.data_plane.bindings` |
| [Calibration](calibration.md) | Calibrator inputs, measurement-aware loss weighting, auxiliary losses | `foundry.calibration.*` |
| [Methods Catalog](methods-catalog.md) | Key causal methods surfaced in Phase 2 | `foundry.methods.catalog.causal.*` |
| [Frontier Methods](frontier-methods.md) | WS-9 causal, ML, agent-sim, and policy frontier additions | `foundry.methods.catalog.causal.frontier`, `foundry.methods.catalog.ml.frontier`, `foundry.methods.catalog.policy.frontier` |
| [Observability](observability-reproducibility.md) | WS-10 tracing, cost attribution, reproducibility, release acceptance, and operator workflows | `foundry.runtime.*`, `foundry.methods.backends.*`, `foundry.methods.catalog_snapshot`, `foundry.methods.selection`, `foundry.release_acceptance` |
| [Agent Sim](agent-sim.md) | Wiring contracts and runtime executors | `foundry.agent_sim.wiring.*` |
| [State](state.md) | Slot layout and JAX state contracts | `foundry.layout`, `foundry.contracts.state` |

## Root API

| Export | Role |
|--------|------|
| `compile()` | Compile a Trinity bundle into an execution plan |
| `execute()` | Execute a compiled plan from a bound state snapshot |
| `compile_program()` | Compatibility alias for `compile()` on the root surface |

## Phase 2 Focus

This documentation pass adds the new measurement-aware calibration surface,
multi-scale state contracts (`CellState`, `HouseholdCellState`,
`ProcurementGraphState`, `AgentSimRuntimeState`), and the agent-sim wiring
executors that were previously source-only.
