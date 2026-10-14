# Foundry

Related explanation: [Causal Engine](../../explanation/causal-engine.md).

Foundry compiles Trinity bundles, binds snapshot data into runtime state,
executes plans, exposes reusable methods, and hosts a standalone
agent-simulation runtime. This map follows implementation and linked test
sources inspected at the source pin below; tests were not rerun for this docs
pass. Simulation outputs remain model-conditioned predictions: the inspected
contracts do not establish an observed policy effect or end-to-end
publishability. Start with [Compile and Execute](compile-execute.md) for the
plan and data path, then read [Causal Engine](../../explanation/causal-engine.md)
for the boundary between model predictions and grounded effects.

Freshness: 2026-10-14
Owner: @foundry-owners
Source of truth: `src/polisyos/foundry/**`, `src/polisyos/ir/analytics/causal_graph.py`,
`src/polisyos/core/contracts/fabric.py`, `src/polisyos/pdc/_impl/world_model_record.py`,
`src/polisyos/runtime/quality/world_model_record.py`,
`src/polisyos/runtime/quality/joint_simulation_horizon.py`,
`src/polisyos/runtime/quality/promotion_sequence.py`,
`src/polisyos/scientist/nodes/builtins/compile/compile_foundry.py`,
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

## Keep observations, models, and effect status distinct

An observed data artifact is not itself the causal model. `DataSnapshot` names
the data payload and may carry evidence, quality, and uncertainty refs; Foundry
input binding maps payload paths into registry slots and persists a bound state
snapshot. That binding makes values executable inputs, but does not validate
the graph or mechanisms those values will be used with. [DataSnapshot contract](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/core/contracts/fabric.py#L161-L181), [binding producer](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/data_plane/bindings.py#L582-L714), [binding behavior test](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/foundry/runtime/test_execute_input_bindings.py#L76-L115).

`CausalGraphModel` holds graph type, nodes, and edges. A `SimulationModelRef`
separately names a model specification, data snapshot, registry bundle,
mechanism/GCM/NCM/program refs, assumptions, fidelity, and calibration state.
These are distinct contracts even when evidence from the same study informs
more than one of them. [Graph IR](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L572-L585), [simulation-model reference](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/pdc/_impl/world_model_record.py#L87-L103).

| Stage | Canonical owner and inspected evidence | Boundary |
| --- | --- | --- |
| Candidate world | The candidate-scenario producer derives a versioned world-model record. [Producer](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/runtime/quality/world_model_record.py#L211-L225); [test](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/runtime/quality/test_world_model_record.py#L624-L647). | The synthetic-model assumption is marked `candidate_only_not_empirically_grounded` with `calibrated=False`; the tested record remains `limited`. A declared or content-bound candidate does not become empirically grounded through schema validity alone. |
| Registered method | `MethodRegistry` resolves methods by FQN/name/version and queries signatures by namespace, tags, slots, or name pattern. [Resolution](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/methods/selection/registry.py#L680-L718); [metadata query](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/methods/selection/registry.py#L805-L855); [Methods Catalog](methods-catalog.md). | Registration and dispatch availability do not establish that study assumptions hold or that a result is an observed policy effect. |
| Executed simulation | Foundry `execute()` consumes a plan, bound state, and registry; the separate N5 controller requests individual, pairwise, and joint horizons. [Execute contract](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/foundry/execute/api.py#L303-L329); [N5 controller](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L1425-L1455); [N5 semantic test](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/runtime/quality/test_joint_simulation_horizon.py#L613-L665). | Simulation trajectories remain model-conditioned predictions; the N5 test retains blockers `simulation_only_k_sim_not_world_evidence` and `simulation_effect_basis_not_established`. |
| Effect-grounding admission | The promotion sequence checks the selected grounding relation, required axis witnesses, binding, and bound atom. [Grounding predicate](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/runtime/quality/promotion_sequence.py#L1621-L1672); [negative test](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/runtime/quality/test_promotion_sequence.py#L4519-L4523). | An ungrounded effect claim fails. Passing this conjunct establishes only that grounding obligation, not whole-policy publishability. |

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

Re-review this map when a cited owner changes its artifact contract, status
composition, workflow bridge, or grounding predicate. Re-inspect the affected
source and linked test, then update the pin and evidence scope; a prior test
link is not a receipt for a new run. Current-code changes belong in this map
and its linked explanation, not in the retained v26 account.
