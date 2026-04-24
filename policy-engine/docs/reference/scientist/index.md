# Scientist

Related explanation: [Governance Model](../../explanation/governance-model.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/__init__.py`, `src/polisyos/scientist/api.py`, `src/polisyos/scientist/workflows/**`, `src/polisyos/scientist/nodes/**`, `src/polisyos/scientist/governance/**`, `src/polisyos/scientist/causal/validity.py`, `src/polisyos/scientist/agent/**`, `src/polisyos/scientist/search/**`, `src/polisyos/scientist/reliability_scorecard.py`, and the linked tests/tools on each page

> Owner lane: `L6 Scientist`  
> Type: Manual reference (not generated).  
> Source of truth: `src/polisyos/scientist/__init__.py`, `src/polisyos/scientist/api.py`, `src/polisyos/scientist/workflows/**`, `src/polisyos/scientist/nodes/**`, `src/polisyos/scientist/governance/**`, `src/polisyos/scientist/causal/validity.py`, `src/polisyos/scientist/agent/**`, `src/polisyos/scientist/search/**`, `src/polisyos/scientist/reliability_scorecard.py`, and the linked tests/tools on each page.

`polisyos.scientist` is the orchestration layer that turns an `ExperimentState`
into a routed workflow run, executes builtin nodes against a CAS-backed
execution context, applies governance, and publishes replayable decision
artifacts.

## Stable Facade

| Export            | Source                            | Role                                               |
| ----------------- | --------------------------------- | -------------------------------------------------- |
| `run_experiment`  | `polisyos.scientist.api`          | Top-level execution entrypoint.                    |
| `ExperimentState` | `polisyos.scientist.engine.state` | Workflow state contract passed across nodes.       |
| `get_metrics`     | `polisyos.core.observability`     | Shared metrics factory exposed through the facade. |
| `get_tracer`      | `polisyos.core.observability`     | Shared tracer factory exposed through the facade.  |

`run_experiment()` rejects unknown top-level state keys, resolves observability,
selects a workflow id through `resolve_workflow_id()`, and delegates execution
to the workflow builder/runtime.

## Workflow Surface

The current routed workflow surface consists of five builtin workflow ids:

| `workflow_id`               | Primary module                 | Current role                                                                                                                      |
| --------------------------- | ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| `scientist_default`         | `workflows/default.py`         | Baseline governed simulation path.                                                                                                |
| `scientist_discovery`       | `workflows/discovery.py`       | Discovery-only blueprint runtime without Foundry/governance execution.                                                            |
| `scientist_causal_full`     | `workflows/causal_full.py`     | Serious/governed causal path with literature prior, graph reconciliation, readiness, transportability, and downstream governance. |
| `scientist_policy_verified` | `workflows/policy_verified.py` | Verified-policy path without hierarchical search.                                                                                 |
| `scientist_policy_design`   | `workflows/policy_design.py`   | Policy-design path with verified sourcing, hierarchical search, readiness, and translation/output bundle stages.                  |

## Reference Map

| Topic                                                | Reference                                              | Source of truth                                                                                                                                            |
| ---------------------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Workflow engine, routing, and builtin DAGs           | [workflows.md](workflows.md)                           | `src/polisyos/scientist/workflows/**`, `src/polisyos/scientist/api.py`, `tests/scientist/workflows/**`, `tests/scientist/test_workflow_selection.py`       |
| Builtin node contract and registry                   | [nodes.md](nodes.md)                                   | `src/polisyos/scientist/nodes/**`, `src/polisyos/scientist/engine/protocol.py`, `tests/scientist/nodes/**`                                                 |
| Governance registry and runtime pipeline             | [governance-passes.md](governance-passes.md)           | `src/polisyos/scientist/governance/**`, `pyproject.toml`, `tests/scientist/governance/**`                                                                  |
| Exact IC verification and implementation conformance | [governance-passes.md](governance-passes.md)           | `src/polisyos/scientist/verification/ic/**`, `tests/scientist/test_ic_verification.py`, `tests/scientist/test_ic_conformance.py`                           |
| Default-path causal-validity diagnostics             | [causal-validity.md](causal-validity.md)               | `src/polisyos/scientist/causal/validity.py`, `src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py`, decision-packet tests              |
| Agent reasoning and advanced search rollout gates    | [agent-search-reasoning.md](agent-search-reasoning.md) | `src/polisyos/scientist/agent/reasoning.py`, `src/polisyos/scientist/agent/eval_harness.py`, `src/polisyos/scientist/search/strategies/advanced_policy.py` |
| Reliability scorecard and phase gates                | [reliability-scorecard.md](reliability-scorecard.md)   | `src/polisyos/scientist/reliability_scorecard.py`, `tools/ci/check_scientist_*.py`, `tests/scientist/test_reliability_scorecard.py`                        |

## D1 To D2 Evidence Map

| D1 phase | Current D2 reference anchor                                                                                                                    | Primary evidence                                                                                                                                             |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Phase 0  | [reliability-scorecard.md](reliability-scorecard.md), [workflows.md](workflows.md), [nodes.md](nodes.md)                                       | `tools/ci/check_scientist_phase0_gate.py`, `tests/tools/test_scientist_phase0_gate.py`                                                                       |
| Phase 1  | [workflows.md](workflows.md), [nodes.md](nodes.md), [reliability-scorecard.md](reliability-scorecard.md)                                       | `tools/ci/check_scientist_phase1_gate.py`, `tests/tools/test_scientist_phase1_gate.py`, `tests/scientist/integration/test_workflow_reliability_scenarios.py` |
| Phase 2  | [workflows.md](workflows.md), [nodes.md](nodes.md), [reliability-scorecard.md](reliability-scorecard.md)                                       | `tools/ci/check_scientist_phase2_ratchet.py`, `tests/tools/test_scientist_phase2_ratchet.py`, `tests/performance/test_scientist_runtime_paths.py`            |
| Phase 3  | [governance-passes.md](governance-passes.md), [causal-validity.md](causal-validity.md), [agent-search-reasoning.md](agent-search-reasoning.md) | governance, causal-evaluation, eval-harness, and advanced-policy tests cited on each page                                                                    |
| Phase 4  | [causal-validity.md](causal-validity.md), [agent-search-reasoning.md](agent-search-reasoning.md)                                               | `frontier_runtime.py`, `tests/scientist/test_frontier_runtime.py`, `tests/scientist/search/test_benchmark_registry.py`                                       |

Historical planning material stays archived under `docs/archive/plans/SCIENTIST_AGENT_SOTA_ROADMAP.md` and is not part of the published factual reference surface.

## Validation

```bash
uv run pytest tests/scientist/workflows/test_workflow_specs.py tests/scientist/test_workflow_selection.py -q
uv run pytest tests/scientist/governance/test_pass_registry.py tests/scientist/test_reliability_scorecard.py -q
uv run pytest tests/scientist/test_ic_verification.py tests/scientist/test_ic_conformance.py tests/scientist/governance/test_incentive_compatibility_pass.py -q
uv run pytest tests/scientist/agent/test_reasoning.py tests/scientist/agent/test_eval_harness.py tests/scientist/search/strategies/test_advanced_policy.py -q
```

## API Reference

::: polisyos.scientist

::: polisyos.scientist.api

::: polisyos.scientist.engine.state
