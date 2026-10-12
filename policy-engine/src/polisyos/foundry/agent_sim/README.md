# Agent Simulation (`polisyos.foundry.agent_sim`)

`polisyos.foundry.agent_sim` is the low-level ABM/RL runtime for agent
dynamics, population turnover, graph spillovers, distribution-aware metrics,
and training-heavy policy simulation workflows.

- Last updated: 2026-10-12

Truth-centric synthetic world generation now lives in
`polisyos.foundry.agent_sim.world`. First-party behavior tests and examples use
the Foundry world import directly.

## Purpose

Use `agent_sim` when a Foundry workflow needs endogenous agent behavior rather
than only patch-first mechanism execution over the compile/execute state
contract. This package owns the standalone ABM/RL state, executor variants,
training helpers, and contract-aware wiring adapters.

Classical Gini uses the finite, nonnegative values on active rows; inactive
padding is excluded. The opt-in Economics training profile checks both active
wealth and income at each projection boundary and carries a terminal refusal
through the native training scan before optimizer or artifact output. The
`TrainingConfig.gini_population_profile` selector is a source-defined enum;
the legacy `track_active_wealth` flag remains wealth-only unless the selected
profile is enabled. General signed-resource simulation remains available when
that profile is not selected. Economics artifacts store the selected profile
in schema 1.1; legacy profileless schema 1.0 artifacts remain readable. CAS
writers encode finite floating training metrics as canonical Decimal values in
a manifest-only copy before writing either object; runtime artifact values are
unchanged. The writer validates every required and optional TrainingMetrics
field before either write, while schema 1.0/1.1 readers preserve declared
runtime types and normalize numeric float fields to Python floats. The
legacy numeric-string read cast remains limited to training_steps. A
schema-1.0 manifest with the entire metrics block absent keeps its historical
placeholder defaults; those values are not evidence of observed training
metrics. When a metrics block is present, required fields are strict, while
optional fields may be absent or explicit nulls.

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

- [world/](world/) for Phase 0 seed worlds, truth APIs, DGP templates,
  observation operators, target builders, and synthetic-world evaluation
  hooks.

## Public Entrypoints

| Entrypoint                             | Description                                                        |
| -------------------------------------- | ------------------------------------------------------------------ |
| `GlobalState`                          | Standalone ABM/RL state bundle for agent-sim workloads.            |
| `PureExecutor`                         | Deterministic base executor for agent-sim steps.                   |
| `create_distribution_aware_executor()` | Adds distribution metric updates.                                  |
| `create_graph_aware_executor()`        | Adds graph-aware updates and metrics.                              |
| `create_population_manager()`          | Initializes lifecycle slot allocation and bookkeeping.             |
| `ContractsPopulationAwareExecutor`     | Contract-aware executor for population and firm lifecycle updates. |
| `ContractsGraphAwareExecutor`          | Contract-aware procurement shock propagation.                      |
| `ContractsDistributionAwareExecutor`   | Contract-aware transfer/tax/distribution execution path.           |
| `train_actor_critic()`                 | Baseline actor-critic training loop.                               |

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
uv run pytest tests/unit/foundry/agent_sim/test_executor.py \
  tests/unit/foundry/agent_sim/test_graph_mechanisms.py \
  tests/unit/foundry/agent_sim/test_wiring.py -q

uv run pytest tests/unit/foundry/agent_sim/test_jit_compatibility.py \
  tests/unit/foundry/agent_sim/test_actor_critic_numerics.py \
  tests/unit/foundry/agent_sim/test_training.py -q
```

## Reference Docs

- [docs/reference/foundry/agent-sim.md](../../../../docs/reference/foundry/agent-sim.md)
- [docs/reference/foundry/state.md](../../../../docs/reference/foundry/state.md)
- [docs/adr/0082-abm-bridge-adaptive-tolerance.md](../../../../docs/adr/0082-abm-bridge-adaptive-tolerance.md)
- [docs/how-to/run-benchmarks.md](../../../../docs/how-to/run-benchmarks.md)
