# Foundry Agent Sim

Related explanation: [Causal Engine](../../explanation/causal-engine.md).

The `polisyos.foundry.agent_sim` package is the low-level ABM/RL runtime for
agent dynamics, population evolution, graph effects, and training-heavy
simulation workflows. It maps primarily to Phase 3 JAX semantics, Phase 4
performance/reproducibility, and Phase 6 agent-simulation frontier work.

Freshness: 2026-04-17
Owner: `@foundry-owners`
Source plan: `docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md`, D1-L3 section in `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/foundry/agent_sim/**`, `src/polisyos/foundry/agent_sim/wiring/**`, and the linked agent-sim tests/ADR

`polisyos.foundry.agent_sim` exports its own
`polisyos.foundry.agent_sim.state.GlobalState` for standalone ABM/RL workloads.
That type is distinct from `polisyos.foundry.contracts.state.GlobalState`,
which is the compile/execute state contract documented on [State](state.md).

## What Belongs Here

- Use `agent_sim` when a Foundry run needs endogenous agent behavior,
  population turnover, graph spillovers, distribution-aware rewards, or
  training loops.

- Use executor variants by need: pure executor for deterministic stepping,
  distribution-aware executor for inequality metrics, graph-aware executor for
  network updates, and population-aware executor for lifecycle events.

- Use the `wiring` layer when contracts need to drive firm lifecycle,
  procurement shock, tax/transfer, or multiscale runtime updates.

- Treat runtime bundles and result records as replay receipts, not generic DTOs.

## State and Measurement Boundaries

- `GlobalState`, `AgentState`, `FirmState`, and optional multiscale fields are
  synthetic runtime state.

- `FirmLifecycleEventBatch`, `ProcurementShockBatch`, and
  `InterventionMechanismConfig` are synthetic control inputs.

- Observed-data comparison and loss weighting belong to calibration modules.
- Policy-facing causal validation belongs to Scientist governance and the causal
  workflow, not to the low-level executor itself.

## Public Surface

| API                                    | Role                                                                                                      |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `GlobalState`                          | Agent-sim-specific state of arrays plus policy, aggregates, distributions, graph, and population manager. |
| `PureExecutor`                         | Deterministic base executor for agent-sim steps.                                                          |
| `create_distribution_aware_executor()` | Adds distribution metrics updates.                                                                        |
| `create_graph_aware_executor()`        | Adds graph-aware updates.                                                                                 |
| `create_population_manager()`          | Initializes population lifecycle and slot allocation.                                                     |
| `ContractsPopulationAwareExecutor`     | Contract-aware executor for population and firm lifecycle updates.                                        |
| `ContractsGraphAwareExecutor`          | Contract-aware procurement shock propagation.                                                             |
| `ContractsDistributionAwareExecutor`   | Combined tax, transfer, population, and graph execution.                                                  |

## Evidence Links

- JIT compatibility:
  `tests/unit/foundry/agent_sim/test_jit_compatibility.py`

- Actor-critic numeric guardrails:
  `tests/unit/foundry/agent_sim/test_actor_critic_numerics.py`

- Graph mechanisms:
  `tests/unit/foundry/agent_sim/test_graph_mechanisms.py`

- Population and lifecycle:
  `tests/unit/foundry/agent_sim/test_population.py`

- Wiring contracts:
  `tests/unit/foundry/agent_sim/test_wiring.py`

- ABM bridge tolerance ADR:
  [`docs/adr/0082-abm-bridge-adaptive-tolerance.md`](../../adr/0082-abm-bridge-adaptive-tolerance.md)

## Typical Lifecycle

1. Initialize policy, distribution, graph, and population configs.
2. Build an executor stack that matches the simulated mechanisms.
3. Roll trajectories or training episodes while executors refresh graphs,
   distributions, and lifecycle events on schedule.
4. Persist experiment outputs, dashboards, diagnostics, and runtime bundles.
5. If the result supports policy claims, hand the evidence to causal/Scientist
   governance rather than treating ABM output as self-validating.

## Reference

::: polisyos.foundry.agent_sim

::: polisyos.foundry.agent_sim.wiring

::: polisyos.foundry.agent_sim.wiring.contracts

::: polisyos.foundry.agent_sim.wiring.executors
