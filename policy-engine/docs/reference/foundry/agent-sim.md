# Foundry Agent Sim
Related explanation: [Causal Engine](../../explanation/causal-engine.md).

The agent-simulation wiring layer bridges intervention contracts into runtime
updates over population, firm networks, and distribution-aware policy
mechanisms.

## What belongs here

- Use the `agent_sim` surface when a Foundry run needs endogenous agent behavior, population turnover, graph spillovers, or distribution-aware rewards.
- Reach for the executor variants in stages: `DistributionAwareExecutor` for inequality metrics, `GraphAwareExecutor` for graph rewiring, and `PopulationAwareExecutor` when lifecycle events must run around the base executor step.
- Treat the config/result bundles in this package as runtime state carriers and replay receipts, not as generic DTOs. They exist so training, dashboards, and experiment tracking can persist the same simulation lifecycle.

## State and Measurement Boundaries

- `FirmLifecycleEventBatch`, `ProcurementShockBatch`, and
  `InterventionMechanismConfig` are synthetic control inputs for
  `GlobalState` updates.
- `Contracts*Executor.apply()` mutates synthetic runtime state and returns
  runtime diagnostics only; observed-data comparison and loss weighting belong
  to calibration modules, not this wiring layer.
- Helper functions with a leading underscore remain internal implementation
  details. The stable public surface is the set re-exported from
  `polisyos.foundry.agent_sim.wiring`.

## Public Surface

| API | Role |
|-----|------|
| `FirmLifecycleEventBatch` | Vectorized firm entry/exit/type-transition input |
| `ProcurementShockBatch` | Vectorized procurement shock input |
| `InterventionMechanismConfig` | Normalized mechanism parameters for tax/transfer wiring |
| `ContractsPopulationAwareExecutor` | Population and firm-lifecycle updates |
| `ContractsGraphAwareExecutor` | Procurement shock propagation |
| `ContractsDistributionAwareExecutor` | Combined tax, transfer, population, and graph execution |

## Typical Lifecycle

1. Initialize policy, distribution, and population configs.
2. Build an executor stack that matches the mechanisms you need to simulate.
3. Roll trajectories or training episodes while the executor refreshes graphs, distributions, and lifecycle events on schedule.
4. Persist experiment outputs, dashboards, and diagnostics from the emitted runtime bundles.

## Reference

::: polisyos.foundry.agent_sim.wiring

::: polisyos.foundry.agent_sim.wiring.contracts

::: polisyos.foundry.agent_sim.wiring.executors
