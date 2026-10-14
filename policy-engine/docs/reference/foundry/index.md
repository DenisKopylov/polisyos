# Foundry

Related explanation: [Causal Engine](../../explanation/causal-engine.md).

`polisyos.foundry` owns executable computation: compiling Trinity bundles into
CAS-backed plans, binding data snapshots into runtime state, executing program
graphs, and exposing reusable methods and the standalone agent-simulation
runtime. The Scientist workflow connects compile and execute artifacts to
downstream analysis and governance. This boundary map reflects code inspected
at [`bafca83bff9ff49eef1466bc491a8420b5cd1dbb`](https://github.com/DenisKopylov/polisyos/tree/bafca83bff9ff49eef1466bc491a8420b5cd1dbb).

Freshness: 2026-10-14
Owner: @foundry-owners
Source of truth: `src/polisyos/foundry/**`, `src/polisyos/scientist/nodes/builtins/compile/compile_foundry.py`,
`src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py`, and their linked tests.
Evidence level: implementation and linked test sources were inspected at the pinned revision above;
tests were not rerun for this docs-only refresh.

## Where to Start

| Surface | What it owns | Implementation and behavioral evidence |
| --- | --- | --- |
| Compile and execute API | `compile()` accepts `ir.trinity_bundle`; it links and lowers to `ProgramGraph`/`ExecPlan` and persists compile artifacts. `execute()` consumes the plan, input bindings, and registry, then persists simulation outputs. | [Compile API](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/compile/api.py#L18-L64), [Trinity compiler persistence](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/compile/trinity_compiler.py#L208-L335), [compile artifact and Scientist-consumer test](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/foundry/compile/test_compile_artifact_contracts.py#L118-L166). |
| Data binding | `build_input_bindings()` checks the snapshot against registry slots and persists input bindings plus a bound state snapshot for `execute()`. | [Binding producer](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/data_plane/bindings.py#L582-L714), [execution input-binding test](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/foundry/runtime/test_execute_input_bindings.py#L76-L115). |
| Scientist bridge | Compile and simulation nodes move Foundry refs through `ExperimentState`; `RunSimulationNode` stores the `SimulationResult` and proof-bridge artifacts. The basic tested bridge case is `SCENARIO`; composition can also be `BOUNDED` or `BLOCKED`, and `IDENTIFIED` requires an admitted producer/verifier. None is observed effect authority. | [Compile node](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/scientist/nodes/builtins/compile/compile_foundry.py#L102-L180), [simulation-node bridge test](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_run_simulation.py#L218-L267), [status composition](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/ir/analytics/simulation_proof_bridge.py#L865-L889), [non-`IDENTIFIED` validator](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/ir/analytics/simulation_proof_bridge.py#L170-L183). |
| Agent simulation | `polisyos.foundry.agent_sim` owns a standalone ABM/RL state, executors, wiring adapters, and training helpers. | [Agent-sim package guide](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/agent_sim/README.md), [executor tests](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/foundry/agent_sim/test_executor.py). |
| Synthetic worlds | `polisyos.foundry.agent_sim.world` generates synthetic DGP samples, truth manifests, and evaluation results for method testing. Its oracle truth is specific to the generated DGP. | [World implementation](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/agent_sim/world/world.py#L248-L310), [seed-world behavior tests](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/foundry/agent_sim/world/test_seed_worlds.py#L59-L80). |

Design-level runs over individual interventions, every pair, and their joint
composition are owned by `polisyos.runtime.quality.joint_simulation_horizon`.
That controller reuses Foundry engines but is not a `polisyos.foundry`
compile/execute API. Its artifacts remain model-based predictions; see
[Causal Engine](../../explanation/causal-engine.md) for the result and grounding
boundary.

## Reference Pages

| Page | Scope |
| --- | --- |
| [Compile Execute](compile-execute.md) | Public APIs, compile artifacts, input binding, execution, and replay contract. |
| [State](state.md) | `GlobalState`, slot layout, snapshots, and state-delta application. |
| [Methods Catalog](methods-catalog.md) | Registry, dispatch, method metadata, and method capability evidence. |
| [Calibration](calibration.md) | Fit loops, measurement-aware loss, penalties, and uncertainty boundaries. |
| [Causal Statistical Validity](causal-statistical-validity.md) | Known-answer, placebo, negative-control, sensitivity, power, missingness, and uncertainty-calibration checks. |
| [Demography](demography.md) | Demographic consistency, donor entrants, and integerized draws. |
| [Agent Sim](agent-sim.md) | ABM/RL runtime layers, contract-aware wiring, and specialized executors. |
| [Frontier Methods](frontier-methods.md) | Research-gated causal, ML, Bayesian/UQ, and policy method families. |
| [Observability Reproducibility](observability-reproducibility.md) | Runtime fingerprints, determinism tiers, and tolerance budgets. |

These reference pages are manually maintained. Generated method snapshots and
operator evidence are inputs to the methods and observability pages; they do not
replace the source owners or certify causal validity. For the distinction
between a model prediction, synthetic benchmark truth, and a grounded effect,
start with [Causal Engine](../../explanation/causal-engine.md).
