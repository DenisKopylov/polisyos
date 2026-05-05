---
title: Decomposition Blueprint
status: accepted
adr: ADR-0143
owner: team-scientist/team-foundry
created: 2026-05-03
last_verified: 2026-05-03
stability: phase-3a-baseline
---

# Decomposition Blueprint

This is the accepted Phase 3A plan-first artifact for scientist/foundry decomposition.
It authorizes no physical `.py` moves in `src/polisyos/scientist/` or
`src/polisyos/foundry/`; it only freezes contracts for Phase 5/6.

## ADR-0143 Decision

- Phase 5/6 may start only after all Phase 3A gates are green.
- Current audited counts are 12 Scientist non-facade root modules and 28 Foundry
  non-facade root modules. These counts supersede older draft text that mentioned
  17/22 modules.
- Every old source FQN gets a targeted Python re-export shim; star imports in shims
  are forbidden by ADR-0144.
- Shim sunset arithmetic: max(60 days, 2 x max workflow lifetime) = 302 days.
  Draft sunset date for Phase 5/6 shims: created + 302 days.

## Move Map

| Source FQN | Target FQN | Type | Reasoning |
| --- | --- | --- | --- |
| `polisyos.scientist.decision_validity` | `polisyos.scientist.validation.decision_validity` | public | Decision-validity checks belong with the Scientist validation package. |
| `polisyos.scientist.error_semantics` | `polisyos.scientist.engine.error_semantics` | public | Engine error normalization is used by checkpoint/resume flows. |
| `polisyos.scientist.evidence_sources` | `polisyos.scientist.evidence.sources` | public | Evidence source configuration belongs with the evidence package. |
| `polisyos.scientist.feedback` | `polisyos.scientist.feedback.core` | public | Feedback loop logic becomes a package with explicit core/utils modules. |
| `polisyos.scientist.feedback_utils` | `polisyos.scientist.feedback.utils` | public | Feedback helpers should move next to the feedback implementation. |
| `polisyos.scientist.frontier_runtime` | `polisyos.scientist.engine.frontier_runtime` | public | Runtime capability glue is engine-owned and should not shadow top-level runtime. |
| `polisyos.scientist.latent_separation` | `polisyos.scientist.causal.latent_separation` | public | Latent-separation diagnostics are causal-readiness concerns. |
| `polisyos.scientist.llm_cycle` | `polisyos.scientist.llm.cycle` | public | LLM orchestration belongs under the Scientist LLM package. |
| `polisyos.scientist.publisher` | `polisyos.scientist.orchestrator.publisher` | public | Publisher orchestration should live with decision-card orchestration. |
| `polisyos.scientist.reliability_scorecard` | `polisyos.scientist.validation.reliability_scorecard` | public | Reliability scoring is validation/reporting surface. |
| `polisyos.scientist.remediation_status` | `polisyos.scientist.governance.remediation_status` | public | Remediation status is governance evidence, not a package-root module. |
| `polisyos.scientist.replay_backend` | `polisyos.scientist.replay.backend` | public | Replay backend belongs with replay comparators and verification. |
| `polisyos.foundry._execution_posture` | `polisyos.foundry.execute._posture` | internal | Execution posture is internal execute-layer state. |
| `polisyos.foundry._executor_graph` | `polisyos.foundry.execute._graph` | internal | Executor graph internals belong under the execute package. |
| `polisyos.foundry._executor_models` | `polisyos.foundry.execute._models` | internal | Executor payload models are execute-layer internals. |
| `polisyos.foundry._executor_ops` | `polisyos.foundry.execute._ops` | internal | Executor operations belong under the execute package. |
| `polisyos.foundry._executor_patching` | `polisyos.foundry.execute._patching` | internal | Executor patching belongs under the execute package. |
| `polisyos.foundry._executor_snapshots` | `polisyos.foundry.execute._snapshots` | internal | Executor snapshots belong under the execute package. |
| `polisyos.foundry._numeric` | `polisyos.foundry.runtime.numeric` | internal | Numeric runtime guards should sit beside runtime nan/fingerprint helpers. |
| `polisyos.foundry.agent_metrics` | `polisyos.foundry.agent_sim.agent_metrics` | public | Agent-specific metrics belong with agent_sim. |
| `polisyos.foundry.agents` | `polisyos.foundry.agent_sim.agents` | public | Agent declarations belong with agent_sim. |
| `polisyos.foundry.conflict_checker` | `polisyos.foundry.validation.conflict_checker` | public | Conflict checking is validation surface. |
| `polisyos.foundry.constraints_engine` | `polisyos.foundry.validation.constraints_engine` | public | Constraint validation belongs under foundry.validation. |
| `polisyos.foundry.cost_model` | `polisyos.foundry.methods.cost_model` | public | Cost modeling is method-selection evidence. |
| `polisyos.foundry.executor` | `polisyos.foundry.execute.executor` | public | The root executor becomes an execute package implementation. |
| `polisyos.foundry.layout` | `polisyos.foundry.methods.layout` | public | Slot layout is method/catalog metadata. |
| `polisyos.foundry.loss` | `polisyos.foundry.methods.loss` | public | Loss helpers are method execution primitives. |
| `polisyos.foundry.mechanism_design` | `polisyos.foundry.mechanisms.design` | public | Mechanism-design helpers belong with mechanisms. |
| `polisyos.foundry.merge_engine` | `polisyos.foundry.methods.merge_engine` | public | Method merge contracts belong with the methods package. |
| `polisyos.foundry.patch_vm` | `polisyos.foundry.execute.patch_vm` | public | Patch VM is an execution backend. |
| `polisyos.foundry.profiles` | `polisyos.foundry.runtime.profiles` | public | Profiles are runtime configuration, not root API. |
| `polisyos.foundry.queue` | `polisyos.foundry.execute.queue` | public | Execution queueing belongs under execute. |
| `polisyos.foundry.quickstart` | `polisyos.foundry._quickstart` | public | Quickstart remains importable through the facade but leaves the root. |
| `polisyos.foundry.registry` | `polisyos.foundry._registry` | public | Package-level registry remains internal behind explicit facade exports. |
| `polisyos.foundry.release_acceptance` | `polisyos.foundry.validation.release_acceptance` | public | Release acceptance checks are validation contracts. |
| `polisyos.foundry.social_weights` | `polisyos.foundry.welfare.social_weights` | public | Social weights belong with welfare analysis. |
| `polisyos.foundry.specs` | `polisyos.foundry.contracts.specs` | public | Specs are Foundry contract models. |
| `polisyos.foundry.trace` | `polisyos.foundry.runtime.trace` | public | Tracing helpers belong with runtime support. |
| `polisyos.foundry.utils` | `polisyos.foundry._internal.utils` | public | Root utils are internal helpers and should not be a public root module. |
| `polisyos.foundry.welfare_bounds` | `polisyos.foundry.welfare.bounds` | public | Welfare bounds deserve an explicit welfare package. |

## External Importers

### `polisyos.scientist.decision_validity`
- `src/polisyos/runtime/http/services/control.py:94` (literal_fqn)
- `src/polisyos/runtime/http/services/debug.py:48` (literal_fqn)
- `src/polisyos/runtime/http/services/run_index.py:18` (literal_fqn)
- `src/polisyos/scientist/feedback.py:41` (literal_fqn)
- `src/polisyos/scientist/frontier_runtime.py:208` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py:121` (literal_fqn)
- `tests/fixtures/scientist_runtime.py:25` (literal_fqn)
- `tests/integration/scientist/test_workflow_reliability_scenarios.py:9` (literal_fqn)
- `tests/unit/runtime/http/test_control_api.py:17` (literal_fqn)
- `tests/unit/runtime/http/test_decision_validity_api.py:16` (literal_fqn)
- `tests/unit/scientist/validation/test_decision_validity_service.py:23` (literal_fqn)
- `tools/ops/runtime/backfill_decision_validity.py:9` (literal_fqn)

### `polisyos.scientist.error_semantics`
- `src/polisyos/scientist/agent/formalizer.py:33` (literal_fqn)
- `src/polisyos/scientist/agent/tools/tool_loop.py:18` (literal_fqn)
- `src/polisyos/scientist/causal/readiness.py:76` (literal_fqn)
- `src/polisyos/scientist/compute/runner.py:28` (literal_fqn)
- `src/polisyos/scientist/engine/async_executor.py:63` (literal_fqn)
- `src/polisyos/scientist/engine/checkpoint.py:32` (literal_fqn)
- `src/polisyos/scientist/engine/convergence.py:34` (literal_fqn)
- `src/polisyos/scientist/engine/executor.py:38` (literal_fqn)
- `src/polisyos/scientist/engine/fan_out.py:33` (literal_fqn)
- `src/polisyos/scientist/engine/locks/dynamodb_lock.py:29` (literal_fqn)
- `src/polisyos/scientist/engine/locks/redis_lock.py:16` (literal_fqn)
- `src/polisyos/scientist/engine/retry.py:36` (literal_fqn)
- `src/polisyos/scientist/engine/runner/_activity_worker.py:20` (literal_fqn)
- `src/polisyos/scientist/engine/runner/distributed_tier.py:21` (literal_fqn)
- `src/polisyos/scientist/engine/runner/fallback_runner.py:22` (literal_fqn)
- `src/polisyos/scientist/engine/runner/ray_runner.py:43` (literal_fqn)
- `src/polisyos/scientist/engine/runner/serialization.py:23` (literal_fqn)
- `src/polisyos/scientist/engine/runner/temporal_runner.py:46` (literal_fqn)
- `src/polisyos/scientist/engine/telemetry.py:10` (literal_fqn)
- `src/polisyos/scientist/governance/passes/_artifact_resolution.py:15` (literal_fqn)
- `src/polisyos/scientist/governance/passes/confidence_pass.py:16` (literal_fqn)
- `src/polisyos/scientist/governance/passes/literature_gate_pass.py:23` (literal_fqn)
- `src/polisyos/scientist/governance/passes/quality_gate_pass.py:24` (literal_fqn)
- `src/polisyos/scientist/governance/passes/strategic_response_pass.py:19` (literal_fqn)
- `src/polisyos/scientist/governance/passes/transportability_required_pass.py:22` (literal_fqn)
- `src/polisyos/scientist/governance/pipeline.py:22` (literal_fqn)
- `src/polisyos/scientist/governance/preflight.py:15` (literal_fqn)
- `src/polisyos/scientist/llm/budget_enforcer.py:16` (literal_fqn)
- `src/polisyos/scientist/llm/fallback_router.py:11` (literal_fqn)
- `src/polisyos/scientist/llm/gateway_client.py:18` (literal_fqn)
- `src/polisyos/scientist/llm/provider_verification.py:17` (literal_fqn)
- `src/polisyos/scientist/llm/streaming.py:13` (literal_fqn)
- `src/polisyos/scientist/llm/token_estimator.py:9` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/c6c_runtime_support.py:49` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/data/build_data_snapshot.py:18` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py:126` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/decide/build_policy_output_bundle.py:23` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/governance/data_plane_gate.py:22` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/governance/legal_check.py:24` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/governance/run_governance.py:55` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/governance/run_normative_arbitration.py:53` (literal_fqn)
- `src/polisyos/scientist/search/controller.py:16` (literal_fqn)
- `tests/unit/scientist/engine/test_error_semantics.py:5` (literal_fqn)

### `polisyos.scientist.evidence_sources`
- `src/polisyos/scientist/cross_graph/compiler.py:52` (literal_fqn)
- `src/polisyos/scientist/discovery/prior_miner.py:21` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_request.py:14` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py:52` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/planning/compile_cross_graph_evidence.py:51` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/planning/run_discovery_blueprint_runtime.py:50` (literal_fqn)
- `src/polisyos/scientist/policy_verified/service.py:33` (literal_fqn)
- `src/polisyos/scientist/workflows/selection.py:14` (literal_fqn)
- `tests/unit/scientist/evidence/test_evidence_sources_direct.py:6` (literal_fqn)
- `tests/unit/scientist/search/test_policy_blueprint_runtime_guards.py:37` (literal_fqn)

### `polisyos.scientist.feedback`
- `src/polisyos/fabric/data_plane/README.md:52` (literal_fqn)
- `src/polisyos/runtime/http/services/feedback.py:23` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py:128` (literal_fqn)
- `tests/fixtures/scientist_runtime.py:32` (literal_fqn)
- `tests/integration/scientist/test_workflow_reliability_scenarios.py:13` (literal_fqn)
- `tests/integration/scientist/test_workflow_reliability_scenarios.py:169` (literal_fqn)
- `tests/unit/scientist/engine/test_feedback_runtime.py:6` (literal_fqn)

### `polisyos.scientist.feedback_utils`
- `src/polisyos/scientist/feedback.py:43` (literal_fqn)

### `polisyos.scientist.frontier_runtime`
- `src/polisyos/scientist/agent/promotion.py:26` (literal_fqn)
- `src/polisyos/scientist/agent/runtime_capabilities.py:13` (literal_fqn)
- `src/polisyos/scientist/causal/validity.py:43` (literal_fqn)
- `src/polisyos/scientist/claims/projections.py:441` (literal_fqn)
- `tests/unit/scientist/agent/test_promotion.py:16` (literal_fqn)
- `tests/unit/scientist/agent/test_runtime_capabilities.py:9` (literal_fqn)
- `tests/unit/scientist/evals/test_authority_integration.py:8` (literal_fqn)
- `tests/unit/scientist/search/test_frontier_runtime.py:3` (literal_fqn)
- `tools/ci/check_scientist_best_in_class_phase1_4.py:94` (literal_fqn)
- `tools/ci/check_scientist_best_in_class_wave1.py:165` (literal_fqn)

### `polisyos.scientist.latent_separation`
- `src/polisyos/scientist/discovery/latent_producers.py:26` (literal_fqn)
- `src/polisyos/scientist/discovery/output.py:89` (literal_fqn)
- `src/polisyos/scientist/search/latent_governance.py:32` (literal_fqn)
- `tests/unit/scientist/causal/test_latent_separation.py:6` (literal_fqn)
- `tests/unit/scientist/discovery/test_schema.py:31` (literal_fqn)

### `polisyos.scientist.llm_cycle`
- `src/polisyos/runtime/http/services/control.py:1461` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/planning/build_execution_plan.py:18` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/planning/run_evaluator.py:24` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/planning/run_preflight.py:20` (literal_fqn)
- `tests/unit/scientist/autotune/test_execution_plan_autotune.py:39` (literal_fqn)
- `tests/unit/scientist/llm/test_llm_cycle_preflight.py:11` (literal_fqn)
- `tests/unit/scientist/search/test_search_loop.py:14` (literal_fqn)

### `polisyos.scientist.publisher`
- `tests/tools/test_scientist_best_in_class_wave2.py:23` (literal_fqn)
- `tests/unit/scientist/orchestrator/test_decision_grade_compiler.py:21` (literal_fqn)
- `tools/ci/check_scientist_best_in_class_phase2_7.py:149` (literal_fqn)
- `tools/ci/check_scientist_best_in_class_wave2.py:301` (literal_fqn)

### `polisyos.scientist.reliability_scorecard`
- `tests/unit/scientist/governance/test_reliability_scorecard.py:3` (literal_fqn)
- `tools/ci/check_scientist_phase1_gate.py:20` (literal_fqn)
- `tools/ci/check_scientist_reliability.py:23` (literal_fqn)

### `polisyos.scientist.remediation_status`
- `tests/unit/scientist/facade/test_remediation_status.py:3` (literal_fqn)

### `polisyos.scientist.replay_backend`
- `src/polisyos/core/components/_cli_replay.py:161` (literal_fqn)
- `tests/unit/scientist/engine/test_reliability_operational_evidence.py:34` (literal_fqn)
- `tests/unit/scientist/replay/test_replay_backend.py:25` (literal_fqn)
- `tests/unit/scientist/replay/test_replay_backend.py:148` (literal_fqn)

### `polisyos.foundry._execution_posture`
- `src/polisyos/foundry/execute/api.py:50` (literal_fqn)
- `src/polisyos/runtime/replay.py:33` (literal_fqn)
- `tests/unit/foundry/runtime/test_executor_private_modules.py:24` (literal_fqn)
- `tests/unit/foundry/runtime/test_executor_private_modules.py:537` (literal_fqn)

### `polisyos.foundry._executor_graph`
- `tests/unit/foundry/runtime/test_executor_fail_semantics.py:22` (literal_fqn)
- `tests/unit/foundry/runtime/test_executor_private_modules.py:25` (literal_fqn)
- `tests/unit/foundry/runtime/test_executor_runtime_semantics.py:249` (literal_fqn)
- `tests/unit/foundry/runtime/test_executor_runtime_semantics.py:377` (literal_fqn)

### `polisyos.foundry._executor_models`
- `src/polisyos/foundry/coupling/coupler.py:11` (literal_fqn)
- `src/polisyos/foundry/runtime/__init__.py:17` (literal_fqn)
- `tests/unit/foundry/runtime/test_constraints_executor.py:13` (literal_fqn)
- `tests/unit/foundry/runtime/test_executor_fail_semantics.py:29` (literal_fqn)
- `tests/unit/foundry/runtime/test_executor_private_modules.py:32` (literal_fqn)
- `tests/unit/foundry/runtime/test_executor_provenance.py:5` (literal_fqn)
- `tests/unit/foundry/runtime/test_executor_runtime_semantics.py:30` (literal_fqn)
- `tests/unit/foundry/runtime/test_executor_snapshots.py:14` (literal_fqn)
- `tests/unit/foundry/runtime/test_patch_executor.py:13` (literal_fqn)
- `tests/unit/foundry/runtime/test_step_specialization.py:9` (literal_fqn)
- `tests/unit/scientist/compute/test_compiler.py:10` (literal_fqn)

### `polisyos.foundry._executor_ops`
- `tests/unit/foundry/runtime/test_executor_private_modules.py:38` (literal_fqn)
- `tests/unit/foundry/runtime/test_executor_private_modules.py:49` (literal_fqn)

### `polisyos.foundry._executor_patching`
- `tests/unit/foundry/runtime/test_executor_private_modules.py:52` (literal_fqn)
- `tests/unit/foundry/runtime/test_patch_vm_parity.py:7` (literal_fqn)

### `polisyos.foundry._executor_snapshots`
- `tests/unit/foundry/contracts/test_state_contracts.py:11` (literal_fqn)
- `tests/unit/foundry/runtime/test_executor_snapshots.py:15` (literal_fqn)

### `polisyos.foundry._numeric`
- `src/polisyos/foundry/agent_sim/actor_critic.py:12` (literal_fqn)
- `src/polisyos/foundry/agent_sim/rewards.py:8` (literal_fqn)
- `src/polisyos/foundry/analysis/distributional.py:10` (literal_fqn)
- `src/polisyos/foundry/calibration/bijectors.py:16` (literal_fqn)
- `src/polisyos/foundry/calibration/loss.py:15` (literal_fqn)
- `src/polisyos/foundry/loss.py:6` (literal_fqn)
- `src/polisyos/foundry/mechanisms/fiscal.py:9` (literal_fqn)

### `polisyos.foundry.agent_metrics`
- `tests/unit/foundry/agent_sim/test_adaptive_agents.py:12` (literal_fqn)

### `polisyos.foundry.agents`
- `src/polisyos/foundry/_executor_graph.py:35` (literal_fqn)
- `src/polisyos/foundry/methods/catalog/mechanism/runtime.py:394` (literal_fqn)
- `tests/unit/foundry/agent_sim/test_adaptive_agents.py:19` (literal_fqn)
- `tests/unit/foundry/coupling/test_adaptive_observations.py:6` (literal_fqn)
- `tools/research/demos/run_laffer_demo.py:24` (literal_fqn)
- `tools/research/demos/run_mechanism_design.py:37` (literal_fqn)

### `polisyos.foundry.conflict_checker`
- `src/polisyos/foundry/compile/trinity_compiler.py:25` (literal_fqn)
- `tests/unit/foundry/analysis/test_conflict_detection.py:12` (literal_fqn)

### `polisyos.foundry.constraints_engine`
- `tests/property/foundry/test_constraints_properties.py:11` (literal_fqn)
- `tests/unit/foundry/validation/test_constraints_v2.py:16` (literal_fqn)

### `polisyos.foundry.cost_model`
- `src/polisyos/foundry/compile/trinity_compiler.py:26` (literal_fqn)
- `src/polisyos/foundry/methods/selection.py:25` (literal_fqn)
- `tests/unit/foundry/analysis/test_cost_model.py:12` (literal_fqn)

### `polisyos.foundry.executor`
- `src/polisyos/foundry/data_plane/bindings.py:35` (literal_fqn)
- `src/polisyos/foundry/execute/api.py:60` (literal_fqn)
- `src/polisyos/foundry/quickstart.py:42` (literal_fqn)
- `src/polisyos/foundry/release_acceptance.py:31` (literal_fqn)
- `src/polisyos/scientist/agent/feasibility.py:231` (literal_fqn)
- `src/polisyos/scientist/compute/runner.py:166` (literal_fqn)
- `src/polisyos/scientist/compute/runner.py:456` (literal_fqn)
- `src/polisyos/scientist/nodes/builtins/simulate/run_distributional_analysis.py:23` (literal_fqn)
- `tests/integration/scientist/test_workflow_tracing.py:16` (literal_fqn)
- `tests/integration/test_c7_synthetic_full_pipeline.py:40` (literal_fqn)
- `tests/unit/foundry/contracts/test_state_contracts.py:19` (literal_fqn)
- `tests/unit/foundry/coupling/test_queue_runtime_contract.py:6` (literal_fqn)
- `tests/unit/foundry/data_plane/test_bindings_multiscale.py:14` (literal_fqn)
- `tests/unit/foundry/facade/test_execute_facade_smoke.py:19` (literal_fqn)
- `tests/unit/foundry/mechanisms/test_fiscal.py:6` (literal_fqn)
- `tests/unit/foundry/mechanisms/test_gradients.py:6` (literal_fqn)
- `tests/unit/foundry/mechanisms/test_labor.py:6` (literal_fqn)
- `tests/unit/foundry/mechanisms/test_welfare_bound_sidecar.py:26` (literal_fqn)
- `tests/unit/foundry/runtime/test_constraints_executor.py:16` (literal_fqn)
- `tests/unit/foundry/runtime/test_execute_feedback.py:28` (literal_fqn)
- `tests/unit/foundry/runtime/test_execute_input_bindings.py:19` (literal_fqn)
- `tests/unit/foundry/runtime/test_executor_runtime_semantics.py:33` (literal_fqn)
- `tests/unit/foundry/runtime/test_jit_stability.py:6` (literal_fqn)
- `tests/unit/foundry/runtime/test_patch_executor.py:16` (literal_fqn)
- `tests/unit/scientist/agent/test_feasibility_probe.py:13` (literal_fqn)
- `tests/unit/scientist/compute/test_compiler.py:13` (literal_fqn)
- `tests/unit/scientist/nodes/builtins/simulate/test_run_distributional_analysis.py:18` (literal_fqn)
- `tests/unit/scientist/nodes/test_bind_foundry_inputs_node.py:17` (literal_fqn)
- `tests/unit/scientist/nodes/test_distributional_analysis_node.py:21` (literal_fqn)
- `tests/unit/scientist/policy_design/test_policy_verified_workflow_e2e.py:11` (literal_fqn)
- `tests/unit/scientist/workflows/test_engine_default_workflow_e1_7.py:11` (literal_fqn)
- `tests/unit/scientist/workflows/test_engine_default_workflow_p8.py:11` (literal_fqn)

### `polisyos.foundry.layout`
- `src/polisyos/data_forge/domains/ukraine/builders/sources.py:17` (literal_fqn)
- `src/polisyos/foundry/compile/trinity_compiler.py:27` (literal_fqn)
- `tests/unit/foundry/contracts/test_layout.py:3` (literal_fqn)

### `polisyos.foundry.loss`
- `tests/unit/foundry/analysis/test_loss_numeric.py:6` (literal_fqn)

### `polisyos.foundry.mechanism_design`
- `src/polisyos/scientist/verification/ic/service.py:26` (literal_fqn)
- `tests/unit/foundry/mechanisms/test_mechanism_design.py:5` (literal_fqn)

### `polisyos.foundry.merge_engine`
- `src/polisyos/foundry/_executor_patching.py:11` (literal_fqn)
- `src/polisyos/foundry/calibration/pure_executor.py:24` (literal_fqn)
- `src/polisyos/foundry/conflict_checker.py:10` (literal_fqn)
- `src/polisyos/foundry/patch_vm.py:13` (literal_fqn)
- `tests/unit/foundry/analysis/test_conflict_detection.py:17` (literal_fqn)
- `tests/unit/foundry/analysis/test_merge_determinism.py:9` (literal_fqn)
- `tests/unit/foundry/analysis/test_merge_engine_regressions.py:6` (literal_fqn)

### `polisyos.foundry.patch_vm`
- `src/polisyos/foundry/_executor_graph.py:36` (literal_fqn)
- `src/polisyos/foundry/_executor_patching.py:12` (literal_fqn)
- `tests/unit/foundry/runtime/test_patch_vm_parity.py:9` (literal_fqn)

### `polisyos.foundry.profiles`
- `tests/unit/foundry/facade/test_public_modules.py:8` (literal_fqn)

### `polisyos.foundry.queue`
- `src/polisyos/foundry/methods/catalog/mechanism/runtime.py:76` (literal_fqn)
- `src/polisyos/foundry/methods/catalog/mechanism/runtime.py:329` (literal_fqn)
- `src/polisyos/foundry/methods/catalog/simulation/dynamics.py:462` (literal_fqn)
- `tests/unit/foundry/analysis/test_health.py:6` (literal_fqn)
- `tests/unit/foundry/facade/test_public_modules.py:9` (literal_fqn)

### `polisyos.foundry.quickstart`
- `src/polisyos/foundry/README.md:72` (literal_fqn)
- `tests/tools/test_docs_gate.py:191` (literal_fqn)
- `tests/unit/foundry/facade/test_quickstart.py:8` (literal_fqn)
- `tests/unit/foundry/runtime/test_execute_feedback.py:29` (literal_fqn)
- `tools/ops/experiments/run_msme_e2e_showcase.py:728` (literal_fqn)
- `tools/ops/experiments/run_msme_e2e_showcase.py:1297` (literal_fqn)
- `tools/ops/experiments/run_msme_grand_tournament_v2.py:1506` (literal_fqn)

### `polisyos.foundry.registry`
- `src/polisyos/foundry/_executor_graph.py:37` (literal_fqn)
- `src/polisyos/foundry/calibration/pure_executor.py:25` (literal_fqn)
- `src/polisyos/foundry/compile/_lowering.py:17` (literal_fqn)
- `src/polisyos/foundry/execute/api.py:78` (literal_fqn)
- `src/polisyos/foundry/methods/catalog/mechanism/runtime.py:104` (literal_fqn)
- `tests/unit/foundry/methods/test_foundry_v2_unified_runtime.py:9` (literal_fqn)
- `tools/research/demos/run_mechanism_design.py:39` (literal_fqn)

### `polisyos.foundry.release_acceptance`
- `src/polisyos/data_forge/domains/ukraine/builders/release.py:10` (literal_fqn)
- `src/polisyos/foundry/methods/cli/__init__.py:270` (literal_fqn)
- `tests/unit/foundry/methods/test_cli.py:232` (literal_fqn)
- `tests/unit/foundry/methods/test_cli.py:270` (literal_fqn)

### `polisyos.foundry.social_weights`
- `src/polisyos/foundry/agent_sim/government_policy.py:18` (literal_fqn)
- `src/polisyos/foundry/agent_sim/modes.py:21` (literal_fqn)
- `src/polisyos/foundry/plugins/economics/objectives.py:11` (literal_fqn)

### `polisyos.foundry.specs`
- `src/polisyos/foundry/registry.py:11` (literal_fqn)
- `tests/unit/foundry/facade/test_public_modules.py:10` (literal_fqn)

### `polisyos.foundry.trace`
- `tests/unit/foundry/facade/test_public_modules.py:15` (literal_fqn)

### `polisyos.foundry.utils`
- `tests/unit/foundry/agent_sim/test_adaptive_agents.py:27` (literal_fqn)
- `tests/unit/foundry/analysis/test_health.py:7` (literal_fqn)

### `polisyos.foundry.welfare_bounds`
- `tests/unit/foundry/mechanisms/test_welfare_bound_sidecar.py:27` (literal_fqn)
- `tests/unit/foundry/runtime/test_execute_feedback.py:30` (literal_fqn)

## Planned Re-export Shims

| Shim FQN | Target FQN | Shape | Draft sunset |
| --- | --- | --- | --- |
| `polisyos.scientist.decision_validity` | `polisyos.scientist.validation.decision_validity` | targeted names only | created + 302 days |
| `polisyos.scientist.error_semantics` | `polisyos.scientist.engine.error_semantics` | targeted names only | created + 302 days |
| `polisyos.scientist.evidence_sources` | `polisyos.scientist.evidence.sources` | targeted names only | created + 302 days |
| `polisyos.scientist.feedback` | `polisyos.scientist.feedback.core` | targeted names only | created + 302 days |
| `polisyos.scientist.feedback_utils` | `polisyos.scientist.feedback.utils` | targeted names only | created + 302 days |
| `polisyos.scientist.frontier_runtime` | `polisyos.scientist.engine.frontier_runtime` | targeted names only | created + 302 days |
| `polisyos.scientist.latent_separation` | `polisyos.scientist.causal.latent_separation` | targeted names only | created + 302 days |
| `polisyos.scientist.llm_cycle` | `polisyos.scientist.llm.cycle` | targeted names only | created + 302 days |
| `polisyos.scientist.publisher` | `polisyos.scientist.orchestrator.publisher` | targeted names only | created + 302 days |
| `polisyos.scientist.reliability_scorecard` | `polisyos.scientist.validation.reliability_scorecard` | targeted names only | created + 302 days |
| `polisyos.scientist.remediation_status` | `polisyos.scientist.governance.remediation_status` | targeted names only | created + 302 days |
| `polisyos.scientist.replay_backend` | `polisyos.scientist.replay.backend` | targeted names only | created + 302 days |
| `polisyos.foundry._execution_posture` | `polisyos.foundry.execute._posture` | targeted names only | created + 302 days |
| `polisyos.foundry._executor_graph` | `polisyos.foundry.execute._graph` | targeted names only | created + 302 days |
| `polisyos.foundry._executor_models` | `polisyos.foundry.execute._models` | targeted names only | created + 302 days |
| `polisyos.foundry._executor_ops` | `polisyos.foundry.execute._ops` | targeted names only | created + 302 days |
| `polisyos.foundry._executor_patching` | `polisyos.foundry.execute._patching` | targeted names only | created + 302 days |
| `polisyos.foundry._executor_snapshots` | `polisyos.foundry.execute._snapshots` | targeted names only | created + 302 days |
| `polisyos.foundry._numeric` | `polisyos.foundry.runtime.numeric` | targeted names only | created + 302 days |
| `polisyos.foundry.agent_metrics` | `polisyos.foundry.agent_sim.agent_metrics` | targeted names only | created + 302 days |
| `polisyos.foundry.agents` | `polisyos.foundry.agent_sim.agents` | targeted names only | created + 302 days |
| `polisyos.foundry.conflict_checker` | `polisyos.foundry.validation.conflict_checker` | targeted names only | created + 302 days |
| `polisyos.foundry.constraints_engine` | `polisyos.foundry.validation.constraints_engine` | targeted names only | created + 302 days |
| `polisyos.foundry.cost_model` | `polisyos.foundry.methods.cost_model` | targeted names only | created + 302 days |
| `polisyos.foundry.executor` | `polisyos.foundry.execute.executor` | targeted names only | created + 302 days |
| `polisyos.foundry.layout` | `polisyos.foundry.methods.layout` | targeted names only | created + 302 days |
| `polisyos.foundry.loss` | `polisyos.foundry.methods.loss` | targeted names only | created + 302 days |
| `polisyos.foundry.mechanism_design` | `polisyos.foundry.mechanisms.design` | targeted names only | created + 302 days |
| `polisyos.foundry.merge_engine` | `polisyos.foundry.methods.merge_engine` | targeted names only | created + 302 days |
| `polisyos.foundry.patch_vm` | `polisyos.foundry.execute.patch_vm` | targeted names only | created + 302 days |
| `polisyos.foundry.profiles` | `polisyos.foundry.runtime.profiles` | targeted names only | created + 302 days |
| `polisyos.foundry.queue` | `polisyos.foundry.execute.queue` | targeted names only | created + 302 days |
| `polisyos.foundry.quickstart` | `polisyos.foundry._quickstart` | targeted names only | created + 302 days |
| `polisyos.foundry.registry` | `polisyos.foundry._registry` | targeted names only | created + 302 days |
| `polisyos.foundry.release_acceptance` | `polisyos.foundry.validation.release_acceptance` | targeted names only | created + 302 days |
| `polisyos.foundry.social_weights` | `polisyos.foundry.welfare.social_weights` | targeted names only | created + 302 days |
| `polisyos.foundry.specs` | `polisyos.foundry.contracts.specs` | targeted names only | created + 302 days |
| `polisyos.foundry.trace` | `polisyos.foundry.runtime.trace` | targeted names only | created + 302 days |
| `polisyos.foundry.utils` | `polisyos.foundry._internal.utils` | targeted names only | created + 302 days |
| `polisyos.foundry.welfare_bounds` | `polisyos.foundry.welfare.bounds` | targeted names only | created + 302 days |

## Pydantic Models And Runtime API Schema Usage

| Model FQN | Source | OpenAPI usage |
| --- | --- | --- |
| `polisyos.foundry._executor_models.FailureCard` | `src/polisyos/foundry/_executor_models.py:61` | none |
| `polisyos.foundry.conflict_checker.ConflictReport` | `src/polisyos/foundry/conflict_checker.py:46` | none |
| `polisyos.foundry.conflict_checker.SlotConflict` | `src/polisyos/foundry/conflict_checker.py:18` | none |
| `polisyos.foundry.cost_model.CostEstimate` | `src/polisyos/foundry/cost_model.py:17` | none |
| `polisyos.foundry.layout.SlotFamily` | `src/polisyos/foundry/layout.py:36` | none |
| `polisyos.foundry.layout.SlotFamilyManifest` | `src/polisyos/foundry/layout.py:47` | none |
| `polisyos.foundry.layout.SlotLayout` | `src/polisyos/foundry/layout.py:26` | none |
| `polisyos.foundry.merge_engine.MergeConflictContract` | `src/polisyos/foundry/merge_engine.py:430` | none |
| `polisyos.foundry.merge_engine.MergeReportContract` | `src/polisyos/foundry/merge_engine.py:441` | none |
| `polisyos.foundry.release_acceptance.ReleaseAcceptanceReport` | `src/polisyos/foundry/release_acceptance.py:102` | none |
| `polisyos.foundry.release_acceptance.ReleaseAcceptanceStep` | `src/polisyos/foundry/release_acceptance.py:92` | none |
| `polisyos.scientist.decision_validity._DecisionDependencyIndex` | `src/polisyos/scientist/decision_validity.py:85` | none |
| `polisyos.scientist.decision_validity._DecisionLineageState` | `src/polisyos/scientist/decision_validity.py:76` | none |
| `polisyos.scientist.decision_validity._DecisionPacketState` | `src/polisyos/scientist/decision_validity.py:51` | none |
| `polisyos.scientist.evidence_sources.EvidenceSourcesConfig` | `src/polisyos/scientist/evidence_sources.py:18` | none |
| `polisyos.scientist.frontier_runtime.FrontierCapability` | `src/polisyos/scientist/frontier_runtime.py:29` | none |
| `polisyos.scientist.frontier_runtime.FrontierRuntimeConfig` | `src/polisyos/scientist/frontier_runtime.py:48` | none |
| `polisyos.scientist.frontier_runtime.FrontierRuntimeReport` | `src/polisyos/scientist/frontier_runtime.py:87` | none |
| `polisyos.scientist.latent_separation.LatentSeparationDiagnosticInputs` | `src/polisyos/scientist/latent_separation.py:196` | none |
| `polisyos.scientist.latent_separation.LatentSeparationEnvironmentInput` | `src/polisyos/scientist/latent_separation.py:180` | none |
| `polisyos.scientist.latent_separation.LatentSeparationMeasurementInput` | `src/polisyos/scientist/latent_separation.py:140` | none |
| `polisyos.scientist.latent_separation.LatentSeparationProxyInput` | `src/polisyos/scientist/latent_separation.py:154` | none |
| `polisyos.scientist.publisher.DecisionGradeExport` | `src/polisyos/scientist/publisher.py:85` | none |
| `polisyos.scientist.publisher.OutputOmissionRecord` | `src/polisyos/scientist/publisher.py:67` | none |

## JAX/Pydantic Top-level Registrations

- No JAX/Pydantic top-level registrations were found in planned move files.

## Pickle And Checkpoint Inventory

- Call sites: 21
- Live artifacts: 2
- Canonical fixtures: `tests/fixtures/checkpoint_compat`

## Dynamic Imports

- Registered dynamic import patterns: 154
- Registry: `architecture/dynamic_imports.toml`

## Import Cycles

- Modules in scientist/foundry graph: 1053
- Edges in graph: 3232
- Pre-existing lazy SCCs: 17
- Allowed lazy cycles are frozen in `architecture/imports/lazy.toml`.
- The baseline graph records the collector mode; this workspace uses the internal
  deterministic AST graph because `pydeps`/`import-linter` are not required dev
  dependencies here.

## Baselines

- `architecture/baselines/structure_remediation/import_graph_pre_decomp.json`
- `architecture/baselines/structure_remediation/import_time_pre_decomp.json`
- `architecture/baselines/structure_remediation/pickle_checkpoint_inventory.json`
- `architecture/baselines/structure_remediation/public_surface_pre_decomp.json`
- `architecture/baselines/structure_remediation/schema_diff_pre_decomp.json`
- `architecture/baselines/structure_remediation/tests_baseline.txt`

`tests_baseline.txt` records why the laptop run was deferred. The final
Phase 7 cloud closeout completed the full-suite baseline on
`phase3a-fulltests-20260503` with 10,975 total tests, 0 failures, 0 errors,
and 35 accepted skips. Evidence:
`gs://lex-1-494208-data/experiments/phase3a_fulltests/phase3a-fulltests-12core-20260504-rerun-20260504T111449Z/`.

## Phase 5/6 Entry Criteria

- `dynamic_imports_gate` green.
- `pickle_compat_gate` green.
- `public_surface_snapshot_gate` green.
- `import_cycles_gate` green.
- `import_time_regression_gate` green in live CI mode.
- `reexport_shim_shape_gate` green.
- Full-suite baseline is green in the Phase 7 cloud closeout.
- No `.py` files in `src/polisyos/scientist/` or `src/polisyos/foundry/` moved during Phase 3A.
