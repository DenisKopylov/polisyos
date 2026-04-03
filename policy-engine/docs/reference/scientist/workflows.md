# Scientist Workflows
Related explanation: [Governance Model](../../explanation/governance-model.md).

Workflow specs are pure DAG declarations built from `WorkflowSpec` and `NodeInvocation`. They define required binds, execution order, and orchestration notes without embedding business logic directly in the spec.

## Workflow Catalog

| Spec | `workflow_id` | Required binds | Purpose |
|------|---------------|----------------|---------|
| `causal_full_workflow_spec()` | `scientist_causal_full` | `run_id`, `inputs.trinity_bundle_ref`, `inputs.registry_bundle_ref` | Full causal evaluation DAG from prior building through governance and decision packet |
| `policy_design_workflow_spec()` | `scientist_policy_design` | `run_id`, `inputs.registry_bundle_ref` | Verified policy-design DAG with legal-source verification, hierarchical search, readiness, and translation |

## `scientist_causal_full`

Key phases:

| Phase | Representative nodes | Outcome |
|-------|----------------------|---------|
| Prior and graph assembly | `build_literature_prior`, `reconcile_causal_graph`, `compile_cross_graph_evidence` | Reconciled graph plus evidence profile |
| Foundry preparation | `build_execution_plan`, `bind_foundry_inputs`, `compile_foundry`, `resolve_parameters` | Executable simulation plan and runtime parameters |
| Causal evaluation | `run_causal_evaluation`, `run_causal_queries`, `run_causal_ensemble`, `run_transportability` | Causal estimates, ensemble uncertainty, transportability decision |
| Governance and output | `run_normative_arbitration`, `run_governance`, `run_evaluator`, `build_decision_packet` | Governance verdict and final packet |

## `scientist_policy_design`

Key phases:

| Phase | Representative nodes | Outcome |
|-------|----------------------|---------|
| Policy sourcing | `plan_policy_request`, `assemble_legal_candidate_pack`, `expand_legal_source_pack`, `run_source_verification`, `run_source_gap_review` | Policy request frame plus verified legal/source packs and a source-verification report |
| Search and gating | `draft_policy_options`, `run_hierarchical_policy_search`, `run_causal_readiness`, `counterfactual_identification_gate` | Champion policy candidate, frontier artifacts, and readiness gates |
| Runtime preparation | `build_execution_plan`, `build_method_catalog_snapshot`, `run_preflight`, `ready_to_run`, `bind_foundry_inputs`, `compile_foundry` | Executable Foundry plan, method-catalog snapshot, and ready-to-run gate verdict |
| Simulation and review | `run_simulation`, `legal_check`, `run_governance`, `run_evaluator`, `build_verified_policy_report` | Verified policy report plus evaluator verdict and governance packet |
| Translation | `run_policy_blueprint_runtime`, `run_policy_translation`, `run_translator_compliance` | Policy output bundle, translator compliance result, and replayable delivery artifacts |

## API Reference

::: polisyos.scientist.workflows

::: polisyos.scientist.workflows.builder

::: polisyos.scientist.workflows.selection

::: polisyos.scientist.workflows.causal_full

::: polisyos.scientist.workflows.policy_design

::: polisyos.scientist.workflows.policy_verified

::: polisyos.scientist.workflows.discovery

::: polisyos.scientist.workflows.default
