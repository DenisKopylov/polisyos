# Foundry Agent Simulation

Related explanation: [Causal Engine](../../explanation/causal-engine.md).

`polisyos.foundry.agent_sim` is a standalone agent-based and reinforcement-
learning runtime. It advances its own array-backed simulation state through
mechanisms and executor layers for population, graphs, and distributional
metrics. Contract-aware adapters can apply typed intervention inputs to that
state. This package is distinct from the Trinity `compile()` / Foundry
`execute()` path described in [Compile and Execute](compile-execute.md).

Owner: @foundry-owners
Source of truth: `src/polisyos/foundry/agent_sim/**` and the linked tests under `tests/unit/foundry/agent_sim/**`.
Evidence level: implementation and linked test sources were inspected at the pinned revision; tests were not run for this docs-only update.

Historical freshness receipt: 2026-04-17 (an earlier documentation pass; not a
current verification receipt). Code inspection for this refresh is pinned to
[`bafca83bff9ff49eef1466bc491a8420b5cd1dbb`](https://github.com/DenisKopylov/polisyos/tree/bafca83bff9ff49eef1466bc491a8420b5cd1dbb).

## Runtime boundary

The package's `GlobalState` is its standalone agent-simulation state. It is
separate from `polisyos.foundry.contracts.state.GlobalState`, which carries the
Foundry compile/execute state contract. `PureExecutor` topologically orders
mechanisms by declared read/write dependencies, applies them to the agent-sim
state, and returns runtime metrics. Its `run()` uses a JAX scan for a sequence
of steps.

The distribution-, graph-, and population-aware executors add those dynamics to
the same synthetic state. The contract-aware wiring layer accepts typed batches
such as firm lifecycle events and procurement shocks, applies them through
executor methods, and returns metrics. The wiring tests show a compiled tax
intervention configuration driving a synthetic state update. This is an adapter
boundary; its presence does not mean every Foundry `ExecPlan` is routed through
these executors.

`AgentPolicyArtifact` stores trained policy weights with training metrics,
environment fingerprint, and I/O shape metadata. The CAS writer persists the
weights and a typed manifest; schema 1.1 records the selected Economics training
profile, while schema 1.0 remains a legacy profileless form. These records
describe a trained agent policy and its runtime compatibility context, not a
validated real-world treatment effect.

## Synthetic world tools

`polisyos.foundry.agent_sim.world` is the truth-centric generator for synthetic
benchmark data. `SyntheticWorld` materializes a configured DGP and exposes
`sample()`, `truth()`, `evaluate()`, and `artifact()`. For a cross-sectional
example, the DGP creates potential outcomes `y0` and `y1`, and its truth builder
computes ATE/ATT/ATC and individual or conditional effects from those values.
Those targets are oracle truth for the generated world and can score a method;
they do not show what an actual policy did to an observed population.

`world.artifact()` returns hashed lineage metadata whose locators use the
`synthetic-world://` scheme. It does not write Foundry CAS refs or compose the
runtime `WorldModelRecord` consumed by the N5 design simulator. The benchmark
world, an N5 simulation world, and a grounded effect claim are distinct
artifacts and decisions.

## Source and behavioral evidence

| Behavior described | Code and test evidence at the pinned revision |
| --- | --- |
| Agent-sim state and executor apply ordered mechanisms and return metrics. | [Standalone state](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/agent_sim/state.py#L70-L100), [PureExecutor](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/agent_sim/executor.py#L24-L101), [executor tests](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/foundry/agent_sim/test_executor.py#L29-L54). |
| Contract-aware wiring applies typed inputs to simulation state. | [Wiring contracts](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/agent_sim/wiring/contracts.py#L1-L80), [executor adapters](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/agent_sim/wiring/executors.py#L460-L520), [compiled-intervention wiring test](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/foundry/agent_sim/test_wiring.py#L242-L278). |
| Trained-policy artifacts persist weights and a manifest with environment and I/O metadata. | [Artifact contract and CAS writer](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/agent_sim/artifact.py#L153-L205), [CAS serialization](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/agent_sim/artifact.py#L620-L647), [artifact round-trip tests](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/foundry/agent_sim/test_agent_artifact.py#L81-L110). |
| Synthetic DGP samples and truth manifests support benchmark evaluation; world artifact locators use a synthetic URI scheme. | [World materialization and artifact](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/agent_sim/world/world.py#L111-L160), [truth and artifact construction](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/agent_sim/world/world.py#L222-L278), [synthetic-world locators](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/agent_sim/world/world.py#L67-L68), [cross-sectional potential outcomes](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/agent_sim/world/templates/cross_sectional.py#L40-L68), [causal truth builder](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/agent_sim/world/targets/causal.py#L10-L32), [seed-world behavior tests](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/foundry/agent_sim/world/test_seed_worlds.py#L59-L80). |

## API reference

::: polisyos.foundry.agent_sim

::: polisyos.foundry.agent_sim.wiring

::: polisyos.foundry.agent_sim.wiring.contracts

::: polisyos.foundry.agent_sim.wiring.executors
