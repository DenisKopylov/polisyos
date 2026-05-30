# Scientist Workflows

Related explanation: [Governance Model](../../explanation/governance-model.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/api.py`, `src/polisyos/scientist/orchestration/workflows/builder.py`, `src/polisyos/scientist/orchestration/workflows/selection.py`, `src/polisyos/scientist/orchestration/workflows/default.py`, `src/polisyos/scientist/orchestration/workflows/discovery.py`, `src/polisyos/scientist/orchestration/workflows/causal_full.py`, `src/polisyos/scientist/orchestration/workflows/policy_verified.py`, `src/polisyos/scientist/orchestration/workflows/policy_design.py`, `src/polisyos/scientist/orchestration/engine/workflow_spec.py`, and workflow selection tests.

> Owner lane: `L6 Scientist`  
> Type: Manual reference (not generated).  
> Source of truth: `src/polisyos/scientist/api.py`, `src/polisyos/scientist/orchestration/workflows/builder.py`, `src/polisyos/scientist/orchestration/workflows/selection.py`, `src/polisyos/scientist/orchestration/workflows/default.py`, `src/polisyos/scientist/orchestration/workflows/discovery.py`, `src/polisyos/scientist/orchestration/workflows/causal_full.py`, `src/polisyos/scientist/orchestration/workflows/policy_verified.py`, `src/polisyos/scientist/orchestration/workflows/policy_design.py`, `src/polisyos/scientist/orchestration/engine/workflow_spec.py`, and workflow selection tests.

Workflow execution has two layers:

1. `run_experiment()` normalizes `ExperimentState`, resolves observability, and
   chooses a builtin `workflow_id`.
2. The workflow builder pins CAS refs, builds `ExecutionContext`, registers
   builtin/discovered nodes, and executes a `WorkflowSpec`.

## Engine Contract

| Surface                                  | Source                          | Contract                                                                                                         |
| ---------------------------------------- | ------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `WorkflowSpec`                           | `engine/workflow_spec.py`       | Declarative DAG with `workflow_id`, ordered `NodeInvocation`s, `required_binds`, and global `error_policy`.      |
| `NodeInvocation`                         | `engine/workflow_spec.py`       | Per-node alias, registered `node_id`, dependency aliases, and optional params/retry/timeout/condition overrides. |
| `build_execution_context(...)`           | `workflows/builder.py`          | Creates the shared CAS/run context used by nodes and checkpoints.                                                |
| `build_registry_with_builtin_nodes(...)` | `workflows/builder.py`          | Registers engine builtins, Scientist builtin nodes, and optional discovered node providers.                      |
| `resolve_workflow_id(...)`               | `workflows/selection.py`        | Routes an `ExperimentState` to a builtin workflow id.                                                            |
| `SimpleLoopEngine`                       | `workflows/engine_simple.py`    | Minimal sequential adapter used by tests and cheap loop prototypes.                                              |
| `LangGraphEngine`                        | `workflows/engine_langgraph.py` | Legacy adapter kept for compatibility; new production runs should go through the builder/runtime DAG path.       |

## Builtin Workflow Catalog

Current builtin specs are:

| `workflow_id`               | Required binds                                                      | Node count | Current use                                                                                                                                                 |
| --------------------------- | ------------------------------------------------------------------- | ---------: | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scientist_default`         | `run_id`, `inputs.trinity_bundle_ref`, `inputs.registry_bundle_ref` | 21         | Baseline governed simulation/governance path.                                                                                                               |
| `scientist_discovery`       | `run_id`, `inputs.registry_bundle_ref`                              | 2          | Discovery-only blueprint runtime.                                                                                                                           |
| `scientist_causal_full`     | `run_id`, `inputs.trinity_bundle_ref`, `inputs.registry_bundle_ref` | 27         | Escalated causal path with literature prior, graph reconciliation, readiness, queries, ensemble, ABM consistency, and transportability.                     |
| `scientist_policy_verified` | `run_id`, `inputs.registry_bundle_ref`                              | 26         | Verified-policy path without hierarchical search or translation bundle stages.                                                                              |
| `scientist_policy_design`   | `run_id`, `inputs.registry_bundle_ref`                              | 35         | Policy-design path with verified sourcing, hierarchical search, readiness, counterfactual gate, blueprint runtime, translation, and output bundle assembly. |

## Routing Rules

`resolve_workflow_id()` currently applies these rules, in order:

| Trigger                                                                                                                                                                                            | Result                                |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| Explicit `params.workflow_id` equal to `scientist_discovery`, `scientist_policy_design`, or `scientist_policy_verified`                                                                            | Honor the explicit id.                |
| Discovery profile or payload: `execution_profile=discovery`, `discovery_mode`, or both `discovery_data` and `discovery_variable_names` present                                                     | Route to `scientist_discovery`.       |
| Policy-design profile: `execution_profile=policy_design` or truthy `params.policy_mode`                                                                                                            | Route to `scientist_policy_design`.   |
| Verified-policy signals: `policy_answer_mode=verified_async`, `execution_profile=policy_verified_async`, or policy question/research intent without Trinity input                                  | Route to `scientist_policy_verified`. |
| Serious execution profiles: `research`, `governed`, `production`                                                                                                                                   | Route to `scientist_causal_full`.     |
| Auto-escalation signals: `transport_required`, mismatched source/target contexts, external evidence markers, knowledge bundle input, cross-graph evidence enabled, or nested evidence-source paths | Route to `scientist_causal_full`.     |
| Otherwise                                                                                                                                                                                          | Fall back to `scientist_default`.     |

## DAG Shape By Workflow

| Workflow                    | Distinguishing stages                                                                                                                                                                                                              |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scientist_default`         | `build_execution_plan -> run_preflight -> ready_to_run`, Foundry compile/simulation, legal check, normative arbitration, governance, evaluator, decision packet.                                                                   |
| `scientist_discovery`       | `run_discovery_blueprint_runtime` only.                                                                                                                                                                                            |
| `scientist_causal_full`     | Adds `build_literature_prior`, `reconcile_causal_graph`, `run_causal_readiness`, `run_causal_queries`, `run_causal_ensemble`, `run_abm_consistency`, and `run_transportability`.                                                   |
| `scientist_policy_verified` | Adds verified-source planning/drafting path before compile/simulation, but does not run hierarchical search or translation/output-bundle stages.                                                                                   |
| `scientist_policy_design`   | Extends verified-policy flow with `run_hierarchical_policy_search`, `counterfactual_identification_gate`, `run_policy_blueprint_runtime`, `run_policy_translation`, `run_translator_compliance`, and `build_policy_output_bundle`. |

## Phase Evidence

| D1 phase | Workflow-facing evidence                                                                                                        |
| -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Phase 0  | `tools/ci/check_scientist_phase0_gate.py`, retry/locking/budget/idempotency regressions.                                        |
| Phase 1  | `tools/ci/check_scientist_phase1_gate.py`, workflow reliability scenarios, branch-local mutation tests, and benchmark coverage. |
| Phase 2  | `tools/ci/check_scientist_phase2_ratchet.py` plus `tests/performance/test_scientist_runtime_paths.py`.                          |
| Phase 3  | Causal-validity, governance, and search/agent artifacts documented on the linked Scientist reference pages.                     |
| Phase 4  | Frontier paths remain behind explicit rollout evidence and are not part of default workflow routing.                            |

## Validation

```bash
uv run pytest tests/unit/scientist/orchestration/workflows/test_workflow_specs.py tests/unit/scientist/orchestration/workflows/test_builder_pinning.py -q
uv run pytest tests/unit/scientist/orchestration/workflows/test_workflow_selection.py tests/integration/scientist/test_workflow_reliability_scenarios.py -q
uv run pytest tests/performance/test_scientist_runtime_paths.py --benchmark-only --benchmark-warmup=on --benchmark-min-rounds=5 -q
```

## API Reference

::: polisyos.scientist.orchestration.workflows

::: polisyos.scientist.orchestration.workflows.builder

::: polisyos.scientist.orchestration.workflows.selection

::: polisyos.scientist.orchestration.workflows.default

::: polisyos.scientist.orchestration.workflows.discovery

::: polisyos.scientist.orchestration.workflows.causal_full

::: polisyos.scientist.orchestration.workflows.policy_verified

::: polisyos.scientist.orchestration.workflows.policy_design
