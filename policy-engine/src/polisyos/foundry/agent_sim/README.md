# Agent Simulation (`polisyos.foundry.agent_sim`)

`polisyos.foundry.agent_sim` is the low-level ABM/RL runtime for agent
dynamics, population turnover, graph spillovers, distribution-aware metrics,
and training-heavy policy simulation workflows.

- Last updated: 2026-04-17

## Purpose

Use `agent_sim` when a Foundry workflow needs endogenous agent behavior rather
than only patch-first mechanism execution over the compile/execute state
contract. This package owns the standalone ABM/RL state, executor variants,
training helpers, and contract-aware wiring adapters.

## Where to Start

- [state.py](state.py) for the standalone agent-sim `GlobalState`.
- [executor.py](executor.py) for `PureExecutor` and deterministic mechanism
  ordering.
- [distribution_executor.py](distribution_executor.py),
  [graph_executor.py](graph_executor.py), and
  [population_executor.py](population_executor.py) for specialized executor
  layers.
- [training.py](training.py), [jit_training.py](jit_training.py), and
  [government_policy.py](government_policy.py) for learning-oriented flows.
- [wiring/contracts.py](wiring/contracts.py) and
  [wiring/executors.py](wiring/executors.py) for contract-aware runtime
  adapters.

## Public Entrypoints

| Entrypoint | Description |
|---|---|
| `GlobalState` | Standalone ABM/RL state bundle for agent-sim workloads. |
| `PureExecutor` | Deterministic base executor for agent-sim steps. |
| `create_distribution_aware_executor()` | Adds distribution metric updates. |
| `create_graph_aware_executor()` | Adds graph-aware updates and metrics. |
| `create_population_manager()` | Initializes lifecycle slot allocation and bookkeeping. |
| `ContractsPopulationAwareExecutor` | Contract-aware executor for population and firm lifecycle updates. |
| `ContractsGraphAwareExecutor` | Contract-aware procurement shock propagation. |
| `ContractsDistributionAwareExecutor` | Contract-aware transfer/tax/distribution execution path. |
| `train_actor_critic()` | Baseline actor-critic training loop. |

## Depends On / Depended On By

- Depends on: JAX/chex numerical stack, `polisyos.foundry.contracts` fidelity
  and wiring state contracts, and optional graph/distribution/training helpers
  within this package tree.
- Depended on by: `polisyos.foundry.plugins`, contract-aware runtime wiring,
  ABM benchmarks, and simulation-heavy research flows.

## Common Commands

Smoke-tested on 2026-04-17:

```bash
uv run python - <<'PY'
from polisyos.foundry.agent_sim import GlobalState, PureExecutor, TaxationMechanism

state = GlobalState.empty(n_agents=4, seed=0, max_agents=4)
executor = PureExecutor([TaxationMechanism(progressive_factor=0.1)])
next_state, metrics = executor.step(state)
print(int(next_state.time_step))
print(sorted(metrics))
PY
```

## Test / Verification Commands

```bash
uv run pytest tests/foundry/agent_sim/test_executor.py \
  tests/foundry/agent_sim/test_graph_mechanisms.py \
  tests/foundry/agent_sim/test_wiring.py -q

uv run pytest tests/foundry/agent_sim/test_jit_compatibility.py \
  tests/foundry/agent_sim/test_actor_critic_numerics.py \
  tests/foundry/agent_sim/test_training.py -q
```

## Reference Docs

- [docs/reference/foundry/agent-sim.md](../../../../docs/reference/foundry/agent-sim.md)
- [docs/reference/foundry/state.md](../../../../docs/reference/foundry/state.md)
- [docs/adr/0082-abm-bridge-adaptive-tolerance.md](../../../../docs/adr/0082-abm-bridge-adaptive-tolerance.md)
- [docs/how-to/run-benchmarks.md](../../../../docs/how-to/run-benchmarks.md)
