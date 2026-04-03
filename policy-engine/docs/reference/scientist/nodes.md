# Scientist Builtin Nodes
Related explanation: [Governance Model](../../explanation/governance-model.md).

Builtin nodes expose a `spec` property with `state_reads`, `state_writes`, and `produces`, then implement `execute(ctx, state) -> NodeOutcome`. Workflow specs compose these nodes into larger DAGs.

## Causal Builtins

| Node | `node_id` | Reads | Writes |
|------|-----------|-------|--------|
| `BuildLiteraturePriorNode` | `scientist.node_build_literature_prior@1.0.0` | causal variables, SKG paths, literature thresholds, discovery audit inputs, `inputs.knowledge_bundle_ref` | literature prior refs, projected graph ref, environment audit summary |
| `ReconcileCausalGraphNode` | `scientist.node_reconcile_causal_graph@1.0.0` | literature prior ref, discovered data graph, fragment refs, LLM hints, alignment config, query-preservation settings | reconciled graph ref, alignment + interface artifacts, composition diagnostics, `params.needs_expert_review` |
| `RunCausalReadinessNode` | `scientist.node_run_causal_readiness@1.0.0` | proxy / transport / strategic / counterfactual / interference bundles, calendars, reconciled graph, causal report | readiness bundle ref, primary transportability ref, primary strategic-response ref |
| `ResolveParametersNode` | `scientist.node_resolve_parameters@1.0.0` | target context, required parameters, SKG paths, reconciled graph, cross-graph profile | context-adaptive parameter bundle ref, literature priors, runtime parameter intervals |
| `RunCausalQueriesNode` | `scientist.node_run_causal_queries@1.0.0` | random seed, `params.causal_query`, SCM ref | query result ref, query envelope ref, method evidence refs |
| `RunCausalEnsembleNode` | `scientist.node_run_causal_ensemble@1.0.0` | causal query, ensemble member payloads, SCM spec, prior query result | ensemble ref, ensemble envelope ref, aggregate causal envelope |
| `RunABMConsistencyCheckNode` | `scientist.node_run_abm_consistency@1.0.0` | ABM mappings, run stats, SCM effects, finite-state abstraction payloads, causal report | ABM alignment report, abstraction map, abstraction certificate, consistency flags |
| `RunTransportabilityNode` | `scientist.node_run_transportability@1.0.0` | source / target context, treatment + outcome, dataset / legal / SKG paths, causal report, capability contract, reconciled graph | transportability status fields, updated causal report, capability contract, transport result ref |
| `RunCausalContractExecutionNode` | `scientist.node_run_causal_contract_execution@1.0.0` | `params.bounds_estimation_tasks`, `params.temporal_dtr_tasks` | causal execution bundle ref, bounds bundle ref, DTR ref, effect-trajectory ref |
| `CounterfactualIdentificationGateNode` | `scientist.node_counterfactual_identification_gate@1.0.0` | causal readiness bundle ref, required query ids | `params.counterfactual_gate_blocked`, `params.counterfactual_gate_summary` |

## Planning Builtins

| Node | `node_id` | Reads | Writes |
|------|-----------|-------|--------|
| `PlanPolicyRequestNode` | `scientist.node_plan_policy_request@1.0.0` | policy question / jurisdiction params, optional research intent | persisted `policy_request_ref`, request-frame artifact ref, verified execution profile |
| `AssembleLegalCandidatePackNode` | `scientist.node_assemble_legal_candidate_pack@1.0.0` | request frame, optional cross-graph evidence profile, candidate-query limits | `legal_candidate_pack_ref`, legal candidate pack artifact |
| `ExpandLegalSourcePackNode` | `scientist.node_expand_legal_source_pack@1.0.0` | legal candidate pack, source-depth limits | `legal_source_pack_ref`, legal source pack artifact |
| `RunSourceVerificationNode` | `scientist.node_run_source_verification@1.0.0` | request frame, legal candidate pack, legal source pack, verifier-call budget | source verification report ref, verification-cycle counters |
| `RunSourceGapReviewNode` | `scientist.node_run_source_gap_review@1.0.0` | request frame, candidate/source packs, prior verification report, gap-review limits | refreshed candidate/source/report refs, `needs_expert_review`, updated verification cycles |
| `DraftPolicyOptionsNode` | `scientist.node_draft_policy_options@1.0.0` | request frame, source verification report, hypothesis toggle | `policy_option_set_ref`, policy option set artifact |
| `BuildExecutionPlanNode` | `scientist.node_build_execution_plan@1.0.0` | execution-plan params, stop criteria, governance constraints, expected outputs | execution plan ref in params and inputs, execution-plan artifact |
| `BuildMethodCatalogSnapshotNode` | `scientist.node_build_method_catalog_snapshot@1.0.0` | `run_id` | method-catalog snapshot ref, causal capability contract ref |
| `RunPreflightNode` | `scientist.node_run_preflight@1.0.0` | execution-plan ref, method-catalog snapshot ref | preflight report ref, `params.preflight_ready`, diagnostics payload |
| `ReadyToRunNode` | `scientist.node_ready_to_run@1.0.0` | preflight readiness + diagnostics params | gate decision only; fails workflow if preflight blocked execution |
| `RunHierarchicalPolicySearchNode` | `scientist.node_run_hierarchical_policy_search@1.0.0` | existing policy candidate, Lex bundle, loop config, Trinity input, artifacts and reports indexes | champion `policy_candidate_schema`, `policy_search_result`, updated Trinity input, frontier report ref |
| `RunEvaluatorNode` | `scientist.node_run_evaluator@1.0.0` | governance report, budget params, retrieval-quality signals | evaluator report ref, iteration-state ref, replanning / approval verdict |

## Compile and Runtime Builtins

| Node | `node_id` | Reads | Writes |
|------|-----------|-------|--------|
| `LinkTrinityNode` | `scientist.node_link_trinity@1.0.0` | Trinity bundle ref, registry bundle ref | link report ref |
| `FormalizeVerifiedPolicyNode` | `scientist.node_formalize_verified_policy@1.0.0` | policy request frame, policy option set, existing Trinity input | generated Trinity bundle ref when policy options can be formalized |
| `BindFoundryInputsNode` | `scientist.node_bind_foundry_inputs@1.0.0` | data snapshot ref, registry bundle, Trinity input, binding rules | input-bindings ref, bound state snapshot ref, input-binding report ref |
| `CompileFoundryNode` | `scientist.node_compile_foundry@1.0.0` | Trinity bundle ref, registry bundle ref | compile/link reports, exec-plan ref, lowered-IR / program-graph / slot-layout refs |
| `RunSimulationNode` | `scientist.node_run_simulation@1.0.0` | exec-plan ref, input-bindings ref, registry bundle, optional parameter overrides | simulation result, metrics, state delta, snapshots, constraint report, environment manifest |

## Helper Exports

| API | Role |
|-----|------|
| `CounterfactualGateDecision` | Normalized decision object returned by gate helpers |
| `evaluate_counterfactual_gate()` | Evaluate the current workflow state against readiness artifacts |
| `evaluate_counterfactual_readiness_bundle()` | Pure readiness-bundle check for required counterfactual queries |
| `ResolutionState` | Immutable transportability-loop iteration state |
| `TransportabilityResolutionLoop` | Dataset / SKG / legal closure loop used by `RunTransportabilityNode` |

## API Reference

::: polisyos.scientist.nodes

::: polisyos.scientist.nodes.builtins

::: polisyos.scientist.nodes.builtins.causal.counterfactual_identification_gate

::: polisyos.scientist.nodes.builtins.causal.run_causal_readiness

::: polisyos.scientist.nodes.builtins.causal.run_causal_contract_execution

::: polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search
