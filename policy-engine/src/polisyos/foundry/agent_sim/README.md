# Agent Simulation (`polisyos.foundry.agent_sim`)

`agent_sim` - micro-level ABM/RL subsystem Foundry for agent dynamics, population
evolution, graph effects and training-heavy simulation workflows.

## Role in System

- **Depends on:** `polisyos.foundry.contracts`, `polisyos.ir.observation`, JAX stack
- **Used by:** `polisyos.foundry.plugins`, research flows that need direct low-level sim access
- Canonical Foundry surface теперь дополняется `wiring/`, когда нужны contract-aware executors.

## Key Concepts

- **State-of-arrays runtime** - `AgentState`, `FirmState`, `MarketState`, `GlobalState`.
- **Multiscale state** - `CellState`, `HouseholdCellState`, `ProcurementGraphState`, `AgentSimRuntimeState`.
- **Execution layers** - pure, distribution, graph, population и temporal executors.
- **Training stack** - actor-critic, RL, JIT training, MPC, VFI и evolution strategies.
- **Wiring layer** - contracts-based executors and event batches for firm lifecycle / procurement shocks.
- **Analytics** - distribution metrics, demographics, visualization and dashboard helpers.

## Public API

| Type/Function | Description |
|---|---|
| `GlobalState` | Композиция agent, firm, market и optional multiscale state. |
| `PureExecutor` | Базовый deterministic executor для agent-sim steps. |
| `create_distribution_aware_executor()` | Создает executor с distribution metrics updates. |
| `create_graph_aware_executor()` | Создает executor с graph-aware updates. |
| `create_population_manager()` | Инициализирует population lifecycle and slot allocation. |
| `ContractsPopulationAwareExecutor` | Contracts-aware executor для multiscale scenario wiring. |
| `FirmLifecycleEventBatch` | Batch событий entry/exit/type transition для firms. |
| `ProcurementShockBatch` | Batch shocks для procurement graph propagation. |

→ Full reference: [docs/reference/foundry/index.md](../../../../docs/reference/foundry/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 42 Python files
- Exports: 185
