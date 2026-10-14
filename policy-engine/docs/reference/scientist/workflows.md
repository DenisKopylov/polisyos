# Scientist Workflows

Related references: [Current workflows and evidence handoffs](current-workflows.md), [Governance Model](../../explanation/governance-model.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/api.py`, `src/polisyos/scientist/orchestration/workflows/builder.py`, `src/polisyos/scientist/orchestration/workflows/selection.py`, `src/polisyos/scientist/orchestration/workflows/default.py`, `src/polisyos/scientist/orchestration/workflows/discovery.py`, `src/polisyos/scientist/orchestration/workflows/causal_full.py`, `src/polisyos/scientist/orchestration/workflows/policy_verified.py`, `src/polisyos/scientist/orchestration/workflows/policy_design.py`, `src/polisyos/scientist/orchestration/engine/workflow_spec.py`, and `tests/unit/scientist/orchestration/workflows/test_workflow_selection.py`.
Source pin: `codex/docs-refresh-e02-20261014` at `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`.
Evidence level: implementation and workflow-selection test sources inspected at this pin; tests not executed for this docs-only update.

> Owner lane: `L6 Scientist`  
> Type: Manual reference (not generated).  
> Source of truth: `src/polisyos/scientist/api.py`, `src/polisyos/scientist/orchestration/workflows/builder.py`, `src/polisyos/scientist/orchestration/workflows/selection.py`, `src/polisyos/scientist/orchestration/workflows/default.py`, `src/polisyos/scientist/orchestration/workflows/discovery.py`, `src/polisyos/scientist/orchestration/workflows/causal_full.py`, `src/polisyos/scientist/orchestration/workflows/policy_verified.py`, `src/polisyos/scientist/orchestration/workflows/policy_design.py`, `src/polisyos/scientist/orchestration/engine/workflow_spec.py`, and `tests/unit/scientist/orchestration/workflows/test_workflow_selection.py`.

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

| `workflow_id`               | Required binds                                                      | Current use                                                                                                                                                 |
| --------------------------- | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scientist_default`         | `run_id`, `inputs.trinity_bundle_ref`, `inputs.registry_bundle_ref` | Baseline governed simulation/governance path.                                                                                                               |
| `scientist_discovery`       | `run_id`, `inputs.registry_bundle_ref`                              | Discovery-only blueprint runtime.                                                                                                                           |
| `scientist_causal_full`     | `run_id`, `inputs.trinity_bundle_ref`, `inputs.registry_bundle_ref` | Escalated causal path with literature prior, graph reconciliation, readiness, queries, ensemble, ABM consistency, and transportability.                     |
| `scientist_policy_verified` | `run_id`, `inputs.registry_bundle_ref`                              | Verified-policy path without hierarchical search or translation bundle stages.                                                                              |
| `scientist_policy_design`   | `run_id`, `inputs.registry_bundle_ref`                              | Policy-design path with verified sourcing, hierarchical search, readiness, counterfactual gate, blueprint runtime, translation, and output bundle assembly. |

This catalog describes workflow-spec wiring, not end-to-end readiness. In
particular, the policy workflows do not require a Trinity ref at bind
validation; the formalizer later checks only for the caller-supplied ref key,
and no request/options-to-Trinity producer is present in the inspected path.
The downstream consequences and other current integration gaps are recorded
in [Current Scientist Workflows and Evidence Handoffs](current-workflows.md).

## Routing Rules

`resolve_workflow_id()` currently applies these rules, in order. When none of
the earlier explicit, discovery, causal-escalation, or serious-profile rules
match, generic policy questions and research-intent signals route to policy
design; the verified-policy route is selected by its explicit async answer
mode or execution profile, not by generic policy intent.

| Priority | Trigger                                                                                                                                                                                                                                                                                | Result                       |
| -------: | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
|        1 | `params.workflow_id` is exactly one of `scientist_discovery`, `scientist_policy_design`, or `scientist_policy_verified`.                                                                                                                                                               | Honor that explicit id.      |
|        2 | Discovery profile/mode, or both discovery data and variable names are present.                                                                                                                                                                                                         | `scientist_discovery`.       |
|        3 | `params.workflow_id` is `scientist_causal_full`.                                                                                                                                                                                                                                       | `scientist_causal_full`.     |
|        4 | Automatic causal escalation: transport required; distinct source and target context fingerprints; an external evidence marker; cross-context reuse; enabled cross-graph evidence config; configured evidence-source paths; expected cross-graph evidence; or a knowledge-bundle input. | `scientist_causal_full`.     |
|        5 | Execution profile is `research`, `governed`, or `production`.                                                                                                                                                                                                                          | `scientist_causal_full`.     |
|        6 | `policy_answer_mode=verified_async` or execution profile `policy_verified_async`.                                                                                                                                                                                                      | `scientist_policy_verified`. |
|        7 | Execution profile `policy_design`; otherwise boolean `policy_mode=true` or a string token in `1`, `true`, `yes`, `on`; otherwise a design-problem ref/payload, research-intent ref, or non-empty policy question/request/problem statement/research question.                          | `scientist_policy_design`.   |
|        8 | No earlier rule matches.                                                                                                                                                                                                                                                               | `scientist_default`.         |

For priority 7, a boolean or string `policy_mode` is resolved directly: only
boolean `true` or the listed truth tokens enable policy-design routing; any
other boolean/string value suppresses that helper's later request-signal
inference. The `policy_design` execution profile is checked first. An
unrecognized explicit workflow id, including `scientist_default`, does not
force a route; other matching rules can still select a different workflow.

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
