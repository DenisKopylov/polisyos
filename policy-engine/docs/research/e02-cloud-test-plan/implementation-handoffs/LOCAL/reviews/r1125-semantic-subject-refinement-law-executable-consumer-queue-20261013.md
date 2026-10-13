# R1125 — executable semantic subject/refinement/law consumer queue

**Disposition:** read-only selector audit. The queue is ready for a root test wave, but no tests were executed here; no source change, G adjudication, or closure is claimed.

**Current source frame:** `codex/e02-unified-local-20261009` HEAD `1ccb8368df94735006cbfd16d5bc2d220d8e66b4`, tree `aec287e84229ee2c20c3f88ab1ad057d543177a4`; root frame `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/root-author-source-frame-r1134-20261013.json` @ `81b47b6e7f1cb846959aa7d711a8853c123d6eb194f9aa40ff8be3683a21e5ad` covers 568 postimages, all verified byte-for-byte. The frame binds branch source only, not acceptance.

## Scope and rebinding

The original assigned denominator remains 20 unique IDs, 21 criterion pointers and 22 S1/S2/S3 memberships over 127 bundles / 282 findings / 291 criterion occurrences. S1 has 15 IDs, S2 has 6, and S3 has B31. LA-023 retains PLG-02 and PLG-03; LA-036 remains in S1/S2; B31 remains one finding with separate S1 and S3 dimensions. The tasks remain `execution_remaining`, coverage remains `not_adjudicated`, and `closure_ids=[]`. LA-021 and LA-029 remain outside the assigned set.

The current selected evidence denominator is **77 files**: 33 product Python, 33 test Python, 4 JSON and 7 Markdown. This is an explicit selected set, not a repository-wide census. It consists of the prior 64 selected files with the frame rebound to R1134, plus 13 additional test modules for fresh consumers and topology/method discriminators. Of the prior 53 source/test files, 52 are byte-identical and one differs: `generation_cycle.py` (prior `9a0808…`, current `e5bfe3…`). Its 87-line diff is formatting plus an optional producer-budget callback at the controller boundary; the B31/B33 routes are unchanged. The root’s current 34 tracked worktree deltas are disjoint from the 66 selected code/test paths. Prior R1026 report and historical-frame hashes are separately recorded as lineage; every current evidence hash and added witness is in the JSON companion.

## How to run the queue

Use the root harness’s already-provisioned supported Python runtime. From `policy-engine/`, execute the exact node IDs in each batch as `python -m pytest -q <selectors...>`; do not install dependencies or create a new environment. Keep the native training selector last. The JSON companion contains argv arrays for every batch.

### simulation-selection-and-horizon

Criteria: B07, B19, B20, B21, B22.

Selectors:

- `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_runs_individual_pairwise_joint_on_real_ncm_with_content_bound_receipt`
- `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_n5_fresh_cas_reader_rejects_forged_replicate_mean`
- `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_v4_sampling_and_interaction_summaries_are_recomputed_and_required`
- `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_unsupported_coupling_is_gated_not_summed`
- `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_supported_shared_resource_runs_on_coupled_engine_with_gate_receipt`
- `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_program_graph_plan_refuses_conflicting_shared_slot_before_execution`
- `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_matching_coupled_engine_runs_individual_pairwise_joint_with_real_interaction`
- `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_served_program_graph_output_lineage_keeps_selected_manifest_profiles`

Runtime note: Run with the already-provisioned supported Python environment; do not install or create an environment.

### subject-bound-intervals-and-graph-topology

Criteria: B31, B33, B214.

Selectors:

- `tests/unit/remediation/test_emp_01.py::test_identification_set_and_statistical_uncertainty_remain_separate`
- `tests/unit/remediation/test_emp_01.py::test_asymmetric_interval_is_preserved_by_value_projection`
- `tests/unit/remediation/test_emp_01.py::test_selection_diagram_requires_verified_causal_artifact`
- `tests/unit/remediation/test_emp_01.py::test_raw_graph_without_artifact_bridge_fails_closed`
- `tests/unit/runtime/quality/test_b31_owner_run_basis_v2.py::test_two_real_method_reports_share_owner_coordinate_and_fresh_cas_basis`
- `tests/unit/runtime/quality/test_b31_owner_run_basis_v2.py::test_manifest_lineage_requires_exact_complete_input_multiset`
- `tests/unit/runtime/quality/test_value_gate.py::test_partial_identification_contract_projects_exact_native_bounds`
- `tests/unit/runtime/quality/test_value_gate.py::test_partial_value_outer_set_width_tracks_real_did_interval`
- `tests/unit/runtime/quality/test_cycle_substrate.py::test_cycle_substrate_context_job_v4_persists_profile_selected_graph_ref`
- `tests/unit/runtime/quality/test_cycle_substrate.py::test_real_transport_gateway_uses_selected_graph_topology_and_measured_rows`
- `tests/unit/scientist/nodes/builtins/causal/test_transport_resolution_inputs.py::test_graph_and_capability_resolution_reads_typed_cas_refs_and_rejects_foreign_kind`
- `tests/unit/ir/test_causal_graph_contract.py::test_causal_graph_artifact_roundtrip`
- `tests/unit/ir/test_causal_graph_contract.py::test_causal_graph_pag_artifact_roundtrip_uses_fresh_reader`
- `tests/unit/ir/test_causal_graph_contract.py::test_causal_graph_pag_artifact_reader_refuses_persisted_duplicate_adjacencies`
- `tests/unit/remediation/test_grf_03.py::test_projection_rejects_unresolved_cpdag_triangle_instead_of_labeling_cycle_dag`
- `tests/unit/remediation/test_grf_03.py::test_graph_projection_admission_covers_full_profile_endpoint_product`
- `tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py::test_static_profile_refuses_original_graph_before_surgery_rewrite_or_noop`
- `tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py::test_id_refuses_before_pag_orientation_or_optimistic_commitment`
- `tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py::test_partial_graph_tags_refuse_direct_scalar_query_for_all_endpoint_pairs`
- `tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py::test_public_causal_engine_returns_typed_nonidentified_refusal_for_partial_graph`
- `tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py::test_remove_static_id_profile_gate_reopens_fully_oriented_pag_identification`

Runtime note: Run with the already-provisioned supported Python environment; no installation.

### modality-training-and-inventory

Criteria: B36, LA-023, LA-032.

Selectors:

- `tests/unit/foundry/methods/test_selection_advisor.py::test_required_panel_modality_is_preserved_and_only_real_runnable_value_owner_is_selected`
- `tests/unit/foundry/methods/test_selection_advisor.py::test_value_advisor_builds_content_bound_selection_receipt_from_real_trace`
- `tests/unit/foundry/methods/test_selection_advisor.py::test_required_modalities_require_one_method_with_the_full_source_union`
- `tests/unit/foundry/methods/catalog/econometrics/test_advanced.py::test_event_study_runs`
- `tests/unit/remediation/test_plg_03.py::test_economics_training_updates_policy_and_produces_readable_artifact`
- `tests/unit/remediation/test_plg_03.py::test_training_uses_supplied_tenant_store_for_persist_and_readback`
- `tests/unit/remediation/test_plg_03.py::test_unsupported_composite_remains_bridge_pending`
- `tests/unit/remediation/test_plg_03.py::test_zero_effective_gradient_is_typed_pending_without_policy_or_cas_persistence`
- `tests/unit/remediation/test_plg_02.py::test_train_with_labor_market_disabled_is_typed_bridge_pending`
- `tests/unit/data_forge/domains/ukraine/test_demography_source_inventory.py::test_inventory_candidate_reaches_all_real_readers_and_foundry`
- `tests/unit/data_forge/domains/ukraine/test_demography_source_inventory.py::test_candidate_readers_refuse_malformed_present_members`
- `tests/unit/data_forge/domains/ukraine/test_demography_source_inventory.py::test_inventory_stage_manifest_rejects_inexact_selected_input_membership`
- `tests/unit/data_forge/domains/ukraine/test_demography_source_inventory.py::test_same_shape_state_order_drift_is_rejected_by_the_real_resolver`
- `tests/unit/data_forge/domains/ukraine/test_demography_source_inventory.py::test_inventory_facts_cannot_claim_independent_provenance`

Runtime note: Run training selectors only in the existing supported native/JAX environment; do not provision dependencies.

### conditional-shap-refusal-and-marginal-control

Criteria: LA-036.

Selectors:

- `tests/unit/remediation/test_ber_01.py::test_gaussian_conditional_shapley_discriminator_is_not_mislabeled_marginal`
- `tests/unit/remediation/test_ber_01.py::test_default_conditional_kernel_shap_refuses_without_conditional_law`
- `tests/unit/remediation/test_ber_01.py::test_service_request_guard_overrides_custom_kernel_adapter_for_conditional_request`
- `tests/unit/remediation/test_ber_01.py::test_tree_shap_fallback_is_explicit_and_does_not_claim_tree_exactness`
- `tests/unit/berl/test_adapters.py::test_kernel_shap_direct_call_refuses_unverified_conditional_route`
- `tests/unit/berl/test_adapters.py::test_kernel_shap_exact_enumeration_matches_linear_model`
- `tests/unit/berl/test_contracts.py::test_conditional_bundle_requires_a_verified_observed_feature_law`
- `tests/unit/berl/test_contracts.py::test_unknown_feature_dependence_profile_fails_closed`
- `tests/unit/berl/test_contracts.py::test_method_profile_must_match_bundle_feature_dependence_profile`
- `tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_correlated_rho_08_source_bundle_keeps_conditional_refused_and_marginal_control_distinct`

Runtime note: Run with the existing supported NumPy/SciPy/PyTorch1 environment; do not install dependencies.

### source-bound-risk-and-backtest-consumers

Criteria: B161, B172, B173.

Selectors:

- `tests/unit/scientist/methods/search/funnel/test_source_bound_risk_candidate.py::test_actual_welfare_producer_persists_candidate_observation_for_fresh_funnel_consumer`
- `tests/unit/scientist/methods/search/funnel/test_source_bound_risk_candidate.py::test_valid_foreign_data_snapshot_stays_candidate_only_and_never_becomes_refinement`
- `tests/unit/scientist/methods/search/funnel/test_source_bound_risk_candidate.py::test_same_snapshot_bytes_with_a_different_selected_profile_stays_candidate_only`
- `tests/unit/scientist/methods/search/funnel/test_source_bound_risk_candidate.py::test_nominal_component_source_change_is_withheld_with_markers_intact`
- `tests/unit/scientist/methods/search/funnel/test_source_bound_risk_candidate.py::test_missing_nominal_components_keeps_markers_but_is_withheld`
- `tests/unit/scientist/methods/search/funnel/test_source_bound_risk_candidate.py::test_missing_source_method_edge_keeps_candidate_markers_from_admitting_observation`
- `tests/unit/ir/mirror_contracts/test_backtest.py::test_source_reconciliation_accepts_real_rows_and_keeps_legacy_candidate_untrusted`
- `tests/unit/ir/mirror_contracts/test_backtest.py::test_source_reconciliation_rejects_marker_retaining_scenario_flip_and_metric_set_gaps`
- `tests/unit/ir/mirror_contracts/test_backtest.py::test_source_reconciliation_recomputes_mape_and_interval_summaries`
- `tests/unit/ir/mirror_contracts/test_backtest.py::test_source_reconciliation_rejects_forged_availability_and_t_statistic`
- `tests/unit/scientist/governance/test_backtest_matrix.py::test_s1_backtest_matrix_preserves_selected_split_gap_and_basis_refs`
- `tests/unit/scientist/governance/test_backtest_matrix.py::test_s1_backtest_matrix_refuses_conflicting_role_requests`
- `tests/unit/scientist/methods/backtesting/test_backtesting.py::test_s1_backtesting_report_persists_nonsignificant_method_identity`
- `tests/unit/scientist/methods/backtesting/test_backtesting.py::test_s1_historical_plan_retains_named_split_roles`
- `tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_s1_nested_backtest_diagnostic_surfaces_after_fresh_decision_packet_read`
- `tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_s1_c5b_fresh_backtest_binding_reaches_packet_and_rejects_kept_markers`
- `tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_s1_exact_zero_trust_recomputes_through_cas_c5b_and_packet`

Runtime note: Run using the supported SciPy environment. Keep controlled fixture rows/roles and source refs exact; do not rewrite test inputs.

### effective-config-jacobian-denominator-covariance-dependence

Criteria: B157, B190, B194, B197, B200.

Selectors:

- `tests/unit/scientist/search/funnel/test_level3_medium.py::test_reduced_config_injected`
- `tests/unit/scientist/search/funnel/test_level3_medium.py::test_fidelity_config_in_feedback`
- `tests/unit/scientist/search/funnel/test_orchestrator.py::test_stage_b_reuses_cached_stage_a_progress`
- `tests/unit/scientist/search/funnel/test_orchestrator.py::test_stage_b_cache_miss_falls_back_to_full_execution`
- `tests/unit/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py::test_build_propagation_fn_keeps_unknown_sensitivity_unmapped`
- `tests/unit/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py::test_build_propagation_fn_preserves_zero_baseline_effect`
- `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_b194_exact_symmetric_partial_draws_reach_fresh_normative_consumer`
- `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_b194_typed_transient_retries_the_same_draw_without_changing_its_denominator`
- `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_b194_sampler_transient_is_not_retried_as_an_evaluator_call`
- `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_b194_exhausted_typed_transient_fails_closed_after_one_same_draw_retry`
- `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_normative_admission_recomputes_denominator_while_markers_stay_true`
- `tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py::test_v2_report_without_projection_does_not_use_v1_name_identity`
- `tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py::test_v2_projection_must_cover_every_reported_calibrated_field`
- `tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py::test_tied_projection_is_invariant_to_coordinate_name`
- `tests/unit/foundry/uncertainty/test_aggregation_strategies.py::test_precision_weighted_equal_variance_does_not_trust_independence_label`
- `tests/unit/foundry/uncertainty/test_aggregation_strategies.py::test_precision_weighted_does_not_favor_a_source_without_resolved_relation`
- `tests/unit/foundry/uncertainty/test_aggregation_strategies.py::test_bayesian_combination_without_resolved_relation_does_not_narrow`

Runtime note: Use the existing supported environment; B194 uses deterministic fixed draws and is the only moderate-cost selector here.

## Criterion queue

### B07 — Check coupling/time applicability before choosing the final engine; a compatible fallback must execute or refusal remain explicit.

- **Queue:** simulation-selection-and-horizon; membership S1; preserved capability label `verification_missing`.
- **Current source route:** JointSimulationRequest/HorizonSpec → candidate selector/coupling checks → result feedback. Current selector checks applicability before final choice; no route executed here.
- **Existing selectors:** `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_unsupported_coupling_is_gated_not_summed`, `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_supported_shared_resource_runs_on_coupled_engine_with_gate_receipt`, `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_matching_coupled_engine_runs_individual_pairwise_joint_with_real_interaction`, `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_program_graph_plan_refuses_conflicting_shared_slot_before_execution`
- **Concrete input/control:** One exact request with equal horizon and atom set: put a coupling-incompatible registered engine before a compatible coupled engine, reverse order, then all-incompatible; only compatible engine may execute and its result must persist, with rejected reasons retained.
- **Property gap:** Existing tests cover support/refusal independently and a compatible engine; no explicit order-sensitive fallback selection with a later compatible engine.
- **Next falsifier or boundary:** Add a producer→CAS→fresh-reader fallback-order control and all-incompatible control; select real registered engines, never a caller-supplied method name.
- **Owner-supplied fact:** Engine capability must be observed through the selected actual engine; no external policy fact is needed.
- **P37 / P38 / P40:** Request/candidate support is recomputed; source law and truth of declared engine capability remain not_established. / A support/method name can select an engine that never executes the requested interaction. / Same selector property; no one-engine patch.

### B19 — Comparator/baseline is factual and aligned to model/scope/horizon; absent state is not zero and no-op is not effect.

- **Queue:** simulation-selection-and-horizon; membership S1; preserved capability label `bridge_missing`.
- **Current source route:** Baseline presence/finite value is checked and subtraction recomputed. comparator_refs/effect_basis status remain not_established; no source artifact/horizon resolution is shown.
- **Existing selectors:** `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_runs_individual_pairwise_joint_on_real_ncm_with_content_bound_receipt`, `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_n5_fresh_cas_reader_rejects_forged_replicate_mean`
- **Concrete input/control:** Three same model/scope/horizon controls: absent baseline; source-selected baseline equal to observed result; source-selected baseline yielding a real delta. Then retain comparator declaration but swap its artifact/model/profile/horizon; fresh consumer must withhold the delta.
- **Property gap:** Current request has finite baseline values and comparator_refs strings; route does not demonstrate factual comparator artifact resolution aligned to model/scope/horizon. Existing N5 reader does not prove comparator basis.
- **Next falsifier or boundary:** Reuse an owner-supported content-bound resolver if available; otherwise record bridge gap and obtain the true baseline schema/artifact from its owner before defining a positive. Missing baseline is not zero.
- **Owner-supplied fact:** Baseline identity, reference frame, scope, time, and meaning are source-owner facts; do not fabricate them.
- **P37 / P38 / P40:** Subtraction recomputes; comparator identity, source, scope/model/horizon and meaning not_established. / A finite caller baseline plus unresolved/mismatched comparator ref produces a plausible number without comparator evidence. / Distinct comparator-binding class.

### B20 — Compatible unordered atoms are permutation-stable; conflicting writes refuse before calculation; no implicit sequence.

- **Queue:** simulation-selection-and-horizon; membership S1; preserved capability label `verification_missing`.
- **Current source route:** Typed writes validate before engine; compatible writes merge and conflicts reject. No explicit sequence contract is visible.
- **Existing selectors:** `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_program_graph_plan_refuses_conflicting_shared_slot_before_execution`, `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_matching_coupled_engine_runs_individual_pairwise_joint_with_real_interaction`
- **Concrete input/control:** Take existing compatible typed atoms and run both permutations on the same coupled engine; compare complete per-step results and persisted output. Reverse conflicting writes and assert both orders refuse before engine callback count changes.
- **Property gap:** Existing checks refuse conflict before execution and cover compatible joint output; permutation invariance is not explicitly selected.
- **Next falsifier or boundary:** Add one property over the complete request atom list, not a hand-picked pair. If sequence is intended, require explicit sequence semantics; never infer order from mapping order.
- **Owner-supplied fact:** No external fact; unordered composition is an internal contract property stated by the criterion.
- **P37 / P38 / P40:** Conflict is recomputed; sequential meaning not_established. / Engine-specific ordering may diverge even when constructor/mapping markers match. / Whole composition across engines; no adapter ladder.

### B21 — Sampling uncertainty follows actual law; one draw is not zero SE and IID/QMC/failure counts differ.

- **Queue:** simulation-selection-and-horizon; membership S1; preserved capability label `producer_missing`.
- **Current source route:** Seeds/count feed engine and typed summary; one sample is standard_error_not_estimated. IID/Sobol law and failed/unattempted denominator are not established from fields.
- **Existing selectors:** `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_v4_sampling_and_interaction_summaries_are_recomputed_and_required`, `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_n5_fresh_cas_reader_rejects_forged_replicate_mean`
- **Concrete input/control:** Preserve real request replication count, produced seeds/draws, actual engine identity, and failure/unattempted records. Compare one vs multiple replications. If actual registry has IID and Sobol engines, use their real registrations and assert persisted sampler identity; never synthesize a law flag.
- **Property gap:** Counts, seeds and summary are recomputed; sampling law and IID-vs-QMC identity are not established by the request/output fields.
- **Next falsifier or boundary:** Probe actual registrations. Add law-specific producer→artifact→fresh-reader tests only for real registered samplers. If unavailable, keep law not_established and do not infer SE from seed uniqueness.
- **Owner-supplied fact:** Sampling law and interpretation of uncertainty require the real engine/source contract, not a seed list.
- **P37 / P38 / P40:** Counts/SE recompute; exchangeability, scrambling and draw relationship not_established without actual sampler contract. / Distinct seeds from deterministic Sobol may yield nonzero SE while failing an IID requirement. / Separate from B194 missingness and B200 dependence.

### B22 — Preserve complete/short/empty grid; no tail fill, interpolation, or silent unit conversion.

- **Queue:** simulation-selection-and-horizon; membership S1; preserved capability label `absent/unallocated`.
- **Current source route:** HorizonSpec defines integer steps and coverage checks exact expected steps/scopes; physical origin/unit are absent from this basis.
- **Existing selectors:** `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_runs_individual_pairwise_joint_on_real_ncm_with_content_bound_receipt`, `tests/unit/runtime/quality/test_joint_simulation_horizon.py::test_n5_fresh_cas_reader_rejects_forged_replicate_mean`
- **Concrete input/control:** HorizonSpec start=0,end=3,step=1 expects (0,1,2,3). Retain full case; remove final step; empty output; duplicate one step; shift to 1..4 with same count. Mismatch must type a gap/refusal, never fill/interpolate.
- **Property gap:** Typed integer step coverage exists; physical origin/unit are absent, and no existing test covers short/empty/full/duplicate/shifted cases as a matrix.
- **Next falsifier or boundary:** Add an expected-step-identity property rather than count-only test. Bind origin/unit only from selected source profile; without it keep limitation visible.
- **Owner-supplied fact:** Time origin, unit, calendar and transformations are selected-source/owner facts.
- **P37 / P38 / P40:** Step coverage recomputes; physical unit, origin and transformation law not_established. / Same point count on shifted origin or different unit passes cardinality but means wrong period. / Distinct temporal grid/unit class.

### B31 — Identification bounds stay separate from native statistical/model uncertainty for same estimand/unit; zero-width bound is not certainty.

- **Queue:** subject-bound-intervals-and-graph-topology; membership S1, S3; preserved capability label `absent/unallocated`.
- **Current source route:** Owner-run basis → candidate fixture → ValueOuterSet and native uncertainty; fixture/run-basis types are candidate-only. S3 additionally demands exact refs, resolved subject/unit and fresh reader.
- **Existing selectors:** `tests/unit/remediation/test_emp_01.py::test_identification_set_and_statistical_uncertainty_remain_separate`, `tests/unit/remediation/test_emp_01.py::test_asymmetric_interval_is_preserved_by_value_projection`, `tests/unit/runtime/quality/test_b31_owner_run_basis_v2.py::test_two_real_method_reports_share_owner_coordinate_and_fresh_cas_basis`, `tests/unit/runtime/quality/test_b31_owner_run_basis_v2.py::test_manifest_lineage_requires_exact_complete_input_multiset`, `tests/unit/runtime/quality/test_value_gate.py::test_partial_identification_contract_projects_exact_native_bounds`, `tests/unit/runtime/quality/test_value_gate.py::test_partial_value_outer_set_width_tracks_real_did_interval`
- **Concrete input/control:** Exact projection control: identification point lower=upper=(4.0,), native statistical lower=(1.0,), upper=(10.0,). B31 v2 owner-basis fixture has explicit candidate_fixture_only assignment (2.125,2.125); compare actual method output/native interval without promoting the fixture.
- **Property gap:** In-memory projection and a real persist/fresh-CAS candidate route exist. The persisted basis fixture explicitly forbids production-value eligibility; S3 still requires source-owned subject/unit identity and fresh consumer.
- **Next falsifier or boundary:** Run both. Only if owner supplies true same-estimand/unit/custody inputs, add source→producer→persisted basis→fresh consumer; mutate/remove subject/unit/ref with interval markers intact.
- **Owner-supplied fact:** Estimand, measurement unit, source law and production eligibility are owner-supplied.
- **P37 / P38 / P40:** Envelope arithmetic recomputes; factual law/native provenance/subject-unit-time identity not_established by fixture label. / Correctly shaped intervals attached to wrong subject/unit pass a marker/shape-only check. / One finding/two acceptance dimensions; memberships are not closure.

### B33 — Use typed source graph topology, not names/marginals/template; different topology must change selection evidence.

- **Queue:** subject-bound-intervals-and-graph-topology; membership S1; preserved capability label `bridge_missing`.
- **Current source route:** Generation-cycle resolves selected graph ref/profile/content, validates graph IR and builds SelectionDiagram; unresolved ref returns acquisition reason. No fresh route run.
- **Existing selectors:** `tests/unit/runtime/quality/test_cycle_substrate.py::test_cycle_substrate_context_job_v4_persists_profile_selected_graph_ref`, `tests/unit/runtime/quality/test_cycle_substrate.py::test_real_transport_gateway_uses_selected_graph_topology_and_measured_rows`, `tests/unit/remediation/test_emp_01.py::test_selection_diagram_requires_verified_causal_artifact`, `tests/unit/scientist/nodes/builtins/causal/test_transport_resolution_inputs.py::test_graph_and_capability_resolution_reads_typed_cas_refs_and_rejects_foreign_kind`
- **Concrete input/control:** Use same declared nodes and measured rows with two persisted selected graph profiles: T→Y,S→Y vs T→S→Y. The real gateway should carry different edge topology and the measured row refs. Remove selected ref or select a sibling profile while retaining names/values; fresh route refuses.
- **Property gap:** Fresh selected graph ref and topology-sensitive gateway are exercised; no scoped test demonstrates a persisted SelectionDiagram artifact resolved by a fresh consumer. Direct helper refusal exists.
- **Next falsifier or boundary:** Extend only an existing SelectionDiagram persistence consumer if one exists; otherwise record precise bridge/surface gap. Graph presence or equal names/marginals is not topology proof.
- **Owner-supplied fact:** Graph truth, population and time coverage are not established by content hash alone.
- **P37 / P38 / P40:** Ref/profile/content recompute; graph truth/population/time/topology authority not_established from presence. / Equal names/marginals but different edges should produce different diagram. / Distinct from B214 endpoint projection.

### B36 — Required modality is hard; selection does not prove transform production; unsupported remains refused.

- **Queue:** modality-training-and-inventory; membership S1; preserved capability label `producer_missing`.
- **Current source route:** Advisor preserves requested modality and filters catalog; no end-to-end transform producer/output consumer is demonstrated.
- **Existing selectors:** `tests/unit/foundry/methods/test_selection_advisor.py::test_required_panel_modality_is_preserved_and_only_real_runnable_value_owner_is_selected`, `tests/unit/foundry/methods/test_selection_advisor.py::test_value_advisor_builds_content_bound_selection_receipt_from_real_trace`, `tests/unit/foundry/methods/test_selection_advisor.py::test_required_modalities_require_one_method_with_the_full_source_union`, `tests/unit/foundry/methods/catalog/econometrics/test_advanced.py::test_event_study_runs`
- **Concrete input/control:** Explicit required modality panel. Advisor supplies a paired negative (tabular-only catalog blocked with required-modality blocker) and positive selection `econometrics.panel.event_study@1.0.0`. Separate dispatcher test uses controlled 8×8 outcomes, treated rows 4–7, treatment time 4, +0.6 post-treatment shift, and returns uncertainty envelope.
- **Property gap:** Advisor selection and method dispatch are separate tests; no same-request advisor→selected method→persisted output→fresh value consumer chain is demonstrated.
- **Next falsifier or boundary:** Join selected method via existing dispatcher if available, persist output plus selected source ref, resolve using existing value consumer. Remove execution while catalog/selection markers remain and ensure no admissible value output.
- **Owner-supplied fact:** Panel rows, units, subject and time profile are source data, not catalog metadata.
- **P37 / P38 / P40:** Modal filtering recomputes; transform output identity not established by catalog metadata. / Catalog advertises modality while transform never runs or output is dropped. / Whole modality/output property.

### LA-023 — Economics .train route actually updates/persists/reads policy; other profiles bridge_pending; resume needs typed checkpoint basis.

- **Queue:** modality-training-and-inventory; membership S1; preserved capability label `semantic_test_missing`.
- **Current source route:** Facade→Economics adapter→actor-critic trainer→supplied store. Unsupported-profile refusal exists; public promise/checkpoint remain separate owner decisions.
- **Existing selectors:** `tests/unit/remediation/test_plg_03.py::test_economics_training_updates_policy_and_produces_readable_artifact`, `tests/unit/remediation/test_plg_03.py::test_training_uses_supplied_tenant_store_for_persist_and_readback`, `tests/unit/remediation/test_plg_03.py::test_unsupported_composite_remains_bridge_pending`, `tests/unit/remediation/test_plg_03.py::test_zero_effective_gradient_is_typed_pending_without_policy_or_cas_persistence`, `tests/unit/remediation/test_plg_02.py::test_train_with_labor_market_disabled_is_typed_bridge_pending`
- **Concrete input/control:** Actual training test uses seed 7 and small config; compare initial vs trained policy tree delta. Tenant-store test stubs native optimizer, so it is store-route only. Unsupported composite and zero-effective-gradient must remain pending with no policy artifact.
- **Property gap:** Real optimizer/artifact and supplied-tenant persistence/readback are separate tests; none combines actual training with fresh read from supplied store. Resume/checkpoint contract is not proved.
- **Next falsifier or boundary:** Run native training once after light batches. Add one real train→tenant store→fresh load→independent action read chain, preserving unsupported refusal. Keep learned policy candidate-grade.
- **Owner-supplied fact:** Institutional model scope, resume/checkpoint semantics and any policy authority require their owner.
- **P37 / P38 / P40:** Action/update can recompute; public scope/RNG/resume contract needs owner decision and typed input. / Artifact/status marker survives after optimizer update removal. / Two PLG criterion pointers, one finding.

### LA-032 — One versioned snapshot/inventory drives readers; swapped/mixed generation refuses; optional absence explicit.

- **Queue:** modality-training-and-inventory; membership S1; preserved capability label `bridge_missing`.
- **Current source route:** source_inventory.v2/manifest→composite/read API/sibling readers; shared route exists, all-reader fresh control not run.
- **Existing selectors:** `tests/unit/data_forge/domains/ukraine/test_demography_source_inventory.py::test_inventory_candidate_reaches_all_real_readers_and_foundry`, `tests/unit/data_forge/domains/ukraine/test_demography_source_inventory.py::test_candidate_readers_refuse_malformed_present_members`, `tests/unit/data_forge/domains/ukraine/test_demography_source_inventory.py::test_inventory_stage_manifest_rejects_inexact_selected_input_membership`, `tests/unit/data_forge/domains/ukraine/test_demography_source_inventory.py::test_same_shape_state_order_drift_is_rejected_by_the_real_resolver`, `tests/unit/data_forge/domains/ukraine/test_demography_source_inventory.py::test_inventory_facts_cannot_claim_independent_provenance`
- **Concrete input/control:** Use existing source_inventory.v2 fixture across all sibling readers. Mutate one member without filename change; swap same-shape generation; alter state order; present malformed member with inventory markers intact. Fresh resolver/readers must refuse; preserve optional absence.
- **Property gap:** Versioned inventory/real readers already have class-level controls. Institutional authority, source epoch/currentness and independent provenance remain not_established.
- **Next falsifier or boundary:** Run the whole-reader selectors. A production currentness positive needs owner epoch/signature evidence, never an implementation timestamp default.
- **Owner-supplied fact:** Source authority/currentness and institutional provenance are owner supplied; exact bytes/membership are recomputable.
- **P37 / P38 / P40:** Selected hashes/layout/generation recompute; source authority/currentness/domain truth not established by inventory description. / Same filenames with one member from a different generation pass filename-only checks but mix source. / Whole inventory/reader set; no per-file fallback.

### LA-036 — Conditional SHAP requires law-bound sampler; marginal fallback cannot carry conditional label.

- **Queue:** conditional-shap-refusal-and-marginal-control; membership S1, S2; preserved capability label `producer_missing`.
- **Current source route:** Service routes conditional to unavailable/refusal; Kernel adapter refuses conditional ID; TreeSHAP fallback is explicit. This is bounded refusal, not producer.
- **Existing selectors:** `tests/unit/remediation/test_ber_01.py::test_gaussian_conditional_shapley_discriminator_is_not_mislabeled_marginal`, `tests/unit/remediation/test_ber_01.py::test_default_conditional_kernel_shap_refuses_without_conditional_law`, `tests/unit/remediation/test_ber_01.py::test_service_request_guard_overrides_custom_kernel_adapter_for_conditional_request`, `tests/unit/remediation/test_ber_01.py::test_tree_shap_fallback_is_explicit_and_does_not_claim_tree_exactness`, `tests/unit/berl/test_adapters.py::test_kernel_shap_direct_call_refuses_unverified_conditional_route`, `tests/unit/berl/test_adapters.py::test_kernel_shap_exact_enumeration_matches_linear_model`, `tests/unit/berl/test_contracts.py::test_conditional_bundle_requires_a_verified_observed_feature_law`, `tests/unit/berl/test_contracts.py::test_unknown_feature_dependence_profile_fails_closed`, `tests/unit/berl/test_contracts.py::test_method_profile_must_match_bundle_feature_dependence_profile`, `tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_correlated_rho_08_source_bundle_keeps_conditional_refused_and_marginal_control_distinct`
- **Concrete input/control:** Standardized Gaussian rho=.8, f(x1,x2)=x1 at x=(1,1): conditional reference Shapley (.6,.4), marginal SHAP (1,0). Real service must refuse conditional absent a verified observed feature law, retain reason, and keep marginal output explicitly separate. Integration test persists both routes through reliability/closeout consumers.
- **Property gap:** Bounded refusal is the intended current behavior; no source-bound conditional law/sampler positive route exists. Do not synthesize sampler or relabel marginal output.
- **Next falsifier or boundary:** Run refusal and marginal controls as one batch, including correlated and law-absent inputs. A positive conditional route requires a resolved owner-provided law and actual sampler.
- **Owner-supplied fact:** Feature dependence law and data epoch are source-owner inputs; synthetic Gaussian is a discriminator, not a real population law.
- **P37 / P38 / P40:** Method/fallback identity recomputes; law/support/population/order/epoch/sampler not_established. / Correlated f=x1 marginal (1,0) differs from conditional (.6,.4); conditional label on marginal result diverges. / One method class across two queue memberships.

### B161 — Only same-subject/value/input/rule/time estimate under allowed procedure may refine early unknown; independent risk remains.

- **Queue:** source-bound-risk-and-backtest-consumers; membership S1; preserved capability label `semantic_test_missing`.
- **Current source route:** SourceBoundRiskObservation is candidate; FunnelOrchestrator preserves historical merge_max and reports producer_law_not_established; no silent promotion.
- **Existing selectors:** `tests/unit/scientist/methods/search/funnel/test_source_bound_risk_candidate.py::test_actual_welfare_producer_persists_candidate_observation_for_fresh_funnel_consumer`, `tests/unit/scientist/methods/search/funnel/test_source_bound_risk_candidate.py::test_valid_foreign_data_snapshot_stays_candidate_only_and_never_becomes_refinement`, `tests/unit/scientist/methods/search/funnel/test_source_bound_risk_candidate.py::test_same_snapshot_bytes_with_a_different_selected_profile_stays_candidate_only`, `tests/unit/scientist/methods/search/funnel/test_source_bound_risk_candidate.py::test_nominal_component_source_change_is_withheld_with_markers_intact`, `tests/unit/scientist/methods/search/funnel/test_source_bound_risk_candidate.py::test_missing_nominal_components_keeps_markers_but_is_withheld`, `tests/unit/scientist/methods/search/funnel/test_source_bound_risk_candidate.py::test_missing_source_method_edge_keeps_candidate_markers_from_admitting_observation`
- **Concrete input/control:** Existing producer uses 100 controlled mixed-nested Monte Carlo draws and persists source-bound observation. Keep refinement not_established, scope relation consumer_asserted, unit unset, and candidate_only. Then run foreign artifact, same bytes/different profile, source edge removal, and marker-retaining component mutation.
- **Property gap:** Real candidate producer and fresh funnel consumer preserve non-authority. Missing positive is a permitted same-subject/value/input/rule/time relation under owner-approved procedure; that input is absent.
- **Next falsifier or boundary:** Run candidate/refusal controls. Do not author min/last/recency promotion. Obtain exact procedure/relations from owner, or preserve bounded candidate-only residual.
- **Owner-supplied fact:** Same subject, value, input, rule, time, unit and permission are source/institution facts, not inferable from IDs or recency.
- **P37 / P38 / P40:** Candidate arithmetic/refs recompute; refinement identity/permission not_established from label or recency. / Later lower value from foreign population/different rule looks like refinement if recency/field match suffices. / Same source-bound refinement class; retain bounded residual, no min/last patch.

### B172 — Nonzero constant residual remains descriptive while zero-variance test unavailable; empty bias list is not neutral.

- **Queue:** source-bound-risk-and-backtest-consumers; membership S1; preserved capability label `None`.
- **Current source route:** Backtest scenarios→IR full metric reconciliation→shared diagnostic/trust verifier→C5b and direct/nested packet. Source has shared recomputation; runtime not rerun.
- **Existing selectors:** `tests/unit/ir/mirror_contracts/test_backtest.py::test_source_reconciliation_accepts_real_rows_and_keeps_legacy_candidate_untrusted`, `tests/unit/ir/mirror_contracts/test_backtest.py::test_source_reconciliation_rejects_marker_retaining_scenario_flip_and_metric_set_gaps`, `tests/unit/ir/mirror_contracts/test_backtest.py::test_source_reconciliation_recomputes_mape_and_interval_summaries`, `tests/unit/ir/mirror_contracts/test_backtest.py::test_source_reconciliation_rejects_forged_availability_and_t_statistic`, `tests/unit/scientist/governance/test_backtest_matrix.py::test_s1_backtest_matrix_preserves_selected_split_gap_and_basis_refs`, `tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_s1_nested_backtest_diagnostic_surfaces_after_fresh_decision_packet_read`, `tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_s1_c5b_fresh_backtest_binding_reaches_packet_and_rejects_kept_markers`, `tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_s1_exact_zero_trust_recomputes_through_cas_c5b_and_packet`
- **Concrete input/control:** Keep scenarios with residuals [10,10,10] and separately [0,0,0]. Constant nonzero residual must retain descriptive MAE=10 while zero-variance test is unavailable. Run producer→CAS→fresh C5b and direct+nested packet. Flip actual scenario, remove/add metric, forge count/availability/trust score/grade/eligible with markers and refs intact; all consumers withhold trust.
- **Property gap:** Whole scenario/metric reconciliation and C5b/direct/nested consumer tests are present. Metric direction, units, materiality/equivalence margin and population interpretation are not established.
- **Next falsifier or boundary:** Run together with B173 as one P40 class, never one statistic/surface at a time. Descriptive diagnostic stays candidate-grade without source-owned qualification basis.
- **Owner-supplied fact:** Metric orientation, units, threshold, population and authority are source-owner inputs.
- **P37 / P38 / P40:** Metric set/count/means/MAE/finite/status recompute; direction/unit/equivalence/dependence/multiplicity/population not_established. / [10,10,10] has no estimable variation, but empty detected list looks neutral if consumer uses list alone. / Same complete diagnostic/trust class as B173; no metric/surface ladder.

### B173 — Missing SciPy yields unavailable test and retained metrics; never substitute normal approximation under t-test label.

- **Queue:** source-bound-risk-and-backtest-consumers; membership S1; preserved capability label `None`.
- **Current source route:** Existing ttest_1samp plus backend identity; missing/error typed unavailable; shared fresh verifier checks rows. No runtime availability control run.
- **Existing selectors:** `tests/unit/scientist/methods/backtesting/test_backtesting.py::test_s1_backtesting_report_persists_nonsignificant_method_identity`, `tests/unit/scientist/methods/backtesting/test_backtesting.py::test_s1_historical_plan_retains_named_split_roles`, `tests/unit/scientist/governance/test_backtest_matrix.py::test_s1_backtest_matrix_refuses_conflicting_role_requests`, `tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_s1_nested_backtest_diagnostic_surfaces_after_fresh_decision_packet_read`, `tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_s1_c5b_fresh_backtest_binding_reaches_packet_and_rejects_kept_markers`, `tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_s1_exact_zero_trust_recomputes_through_cas_c5b_and_packet`
- **Concrete input/control:** Named fixture_training/fixture_validation/fixture_holdout; residuals [.5,1.5,2.5]. Actual SciPy ttest_1samp gives p≈.121690; persist real method ID/backend version despite nonsignificance. Keep exact-zero as separate control. Backend missing/raising preserves metrics, marks test unavailable and trust false; never use normal fallback p≈.009375.
- **Property gap:** Actual method identity and fresh consumers exist; run backend available/unavailable cases together. Statistic is descriptive; missing orientation/equivalence threshold cannot be invented.
- **Next falsifier or boundary:** Run installed actual backend plus a controlled missing/error backend path if available. Keep method/version in both significant and nonsignificant reports and do not promote trust.
- **Owner-supplied fact:** Significance direction, multiplicity, assumptions, metric direction and population meaning are not established by the runner.
- **P37 / P38 / P40:** Test values/status recompute when backend exists; installed backend provenance and residual assumptions not established here. / [.5,1.5,2.5] SciPy p≈.121690 versus former normal p≈.009375. / Same whole diagnostic/trust class as B172.

### B214 — Admitted graph profiles preserve known arrows and acyclicity; unresolved endpoints refuse instead of inventing completion.

- **Queue:** subject-bound-intervals-and-graph-topology; membership S1; preserved capability label `None`.
- **Current source route:** Typed graph→project_graph_to_dag validates kind/endpoints/orientation/latent conversion/cycles; ID path refuses unresolved PAG. Fresh consumer not run.
- **Existing selectors:** `tests/unit/ir/test_causal_graph_contract.py::test_causal_graph_artifact_roundtrip`, `tests/unit/ir/test_causal_graph_contract.py::test_causal_graph_pag_artifact_roundtrip_uses_fresh_reader`, `tests/unit/ir/test_causal_graph_contract.py::test_causal_graph_pag_artifact_reader_refuses_persisted_duplicate_adjacencies`, `tests/unit/remediation/test_grf_03.py::test_projection_rejects_unresolved_cpdag_triangle_instead_of_labeling_cycle_dag`, `tests/unit/remediation/test_grf_03.py::test_graph_projection_admission_covers_full_profile_endpoint_product`, `tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py::test_static_profile_refuses_original_graph_before_surgery_rewrite_or_noop`, `tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py::test_id_refuses_before_pag_orientation_or_optimistic_commitment`, `tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py::test_partial_graph_tags_refuse_direct_scalar_query_for_all_endpoint_pairs`, `tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py::test_public_causal_engine_returns_typed_nonidentified_refusal_for_partial_graph`, `tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py::test_remove_static_id_profile_gate_reopens_fully_oriented_pag_identification`
- **Concrete input/control:** Run full endpoint/profile product and fresh persisted reader. Control fully oriented DAG/ADMG against partially oriented CPDAG/PAG triangle; preserve known arrows, refuse scalar ID for unresolved endpoints, reject duplicate/cyclic edges. Removal probe makes the deleted static-profile gate reopen the forbidden ID path.
- **Property gap:** Generic endpoint projector and ID refusal exist; no source basis proving the true graph of a real population is supplied. Keep graph class distinct from causal truth.
- **Next falsifier or boundary:** Run projector endpoint product, actual ID consumer, fresh reader and removal control as one batch; no arbitrary completion of unresolved endpoints.
- **Owner-supplied fact:** Source graph truth/equivalence class and any allowed completion are owner supplied.
- **P37 / P38 / P40:** Endpoint/cycle recompute; source graph truth and arbitrary equivalence-class completion not_established. / Unresolved CPDAG triangle cannot become one arbitrary DAG because downstream accepts DAG. / Existing generic projector/refusal; no endpoint ladder.

### B157 — L3 reduced config cannot mutate caller or alter later L4 full profile; consumed profile/work count must be visible.

- **Queue:** effective-config-jacobian-denominator-covariance-dependence; membership S2; preserved capability label `bridge_missing`.
- **Current source route:** Level3MediumFidelity builds per-stage mappings/overlay. Direct alias path addressed; native engine config/draws/artifacts not measured.
- **Existing selectors:** `tests/unit/scientist/search/funnel/test_level3_medium.py::test_reduced_config_injected`, `tests/unit/scientist/search/funnel/test_level3_medium.py::test_fidelity_config_in_feedback`, `tests/unit/scientist/search/funnel/test_orchestrator.py::test_stage_b_reuses_cached_stage_a_progress`, `tests/unit/scientist/search/funnel/test_orchestrator.py::test_stage_b_cache_miss_falls_back_to_full_execution`
- **Concrete input/control:** Compare direct L4 vs L3→L4 for same candidate. Record actual engine config, draws/work count, persisted output and later reader. Mutate nested config sentinel after L3; it must not alias caller state or alter L4. Preserve cache hit/miss controls.
- **Property gap:** Tests prove L3 config injection/feedback and stage B cache behavior, not actual L4 engine input/artifact identity across both routes.
- **Next falsifier or boundary:** Add recording real-engine control at existing orchestration boundary; engine receipt is the discriminator, not `full` metadata.
- **Owner-supplied fact:** Actual engine fidelity/work is proven by registered engine input/receipt, not caller labels.
- **P37 / P38 / P40:** Copy/overlay recompute; native full/reduced settings/work counts not_established until observed. / L4 says full while engine receives reduced settings; nested mutable values can survive shallow outer copy. / Whole effective-config handoff class.

### B190 — Unknown sensitivity/Jacobian remains unknown; names/zero baseline cannot fabricate derivative or authority.

- **Queue:** effective-config-jacobian-denominator-covariance-dependence; membership S2; preserved capability label `None`.
- **Current source route:** Propagation accepts explicit checked map; missing map empty and output candidate-only/not gate-eligible. No source-owned exact Jacobian.
- **Existing selectors:** `tests/unit/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py::test_build_propagation_fn_keeps_unknown_sensitivity_unmapped`, `tests/unit/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py::test_build_propagation_fn_preserves_zero_baseline_effect`
- **Concrete input/control:** Existing no-map control: base y=10,z=20 at x=2 unchanged at x=3. Explicit map y←x, baseline y=0 at x=2 gives y=1 at x=3 and y=−1 at x=1.
- **Property gap:** Arithmetic for an explicit map and unknown-map refusal are covered; no source-owned typed Jacobian basis is present in this path, so map remains caller-supplied.
- **Next falsifier or boundary:** Run both. Authority-grade route must resolve actual Jacobian source, unit and subject and recompute before propagation. Absent that, keep sensitivity not_established/candidate-only.
- **Owner-supplied fact:** Derivative identity, units and evaluation domain require owning model/source.
- **P37 / P38 / P40:** Map supplied by caller is consumer_asserted; arithmetic recomputes; derivative identity/units not_established. / Numeric delta from name/zero baseline looks like sensitivity while derivative is absent. / Distinct from B197 covariance projection.

### B194 — Failure filtering cannot make surviving draws unconditional; preserve requested/attempted/succeeded/failed/unattempted.

- **Queue:** effective-config-jacobian-denominator-covariance-dependence; membership S2; preserved capability label `None`.
- **Current source route:** Monte Carlo records attempts/failures/retries/input hashes; IR reader recomputes denominator/summary. Law/missing-mass semantics remain non-authoritative.
- **Existing selectors:** `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_b194_exact_symmetric_partial_draws_reach_fresh_normative_consumer`, `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_b194_typed_transient_retries_the_same_draw_without_changing_its_denominator`, `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_b194_sampler_transient_is_not_retried_as_an_evaluator_call`, `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_b194_exhausted_typed_transient_fails_closed_after_one_same_draw_retry`, `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_normative_admission_recomputes_denominator_while_markers_stay_true`
- **Concrete input/control:** Real producer requests 100 draws: 50 succeed and 50 failures at indices 0–49; estimate 50/99, sample_size 50, heuristic interval, gate_eligible=false, denominator complete. Then verify same-draw retry, sampler/evaluator transient distinction and exhausted retry through fresh normative consumer.
- **Property gap:** Producer, persisted report and fresh normative consumer are tested. Population sampling law/missing mass is not established; successful-only conditional summary is not unconditional population estimate.
- **Next falsifier or boundary:** Run real-node and retry controls. Remove one failure record while 100 request/attempt markers remain; fresh consumer must withhold normative status.
- **Owner-supplied fact:** Sampling population/law and unobserved-mass meaning come from source owner; counts are recomputable.
- **P37 / P38 / P40:** Counts/summaries recompute; population law, missing mass, identity, independence not_established from metadata. / Early stop after easy successes looks complete if failure/unattempted rows disappear but marker remains. / Distinct denominator class from B21/B200.

### B197 — Covariance fields map by actual Jacobian JΣJᵀ including tied coords; no string-name guessing.

- **Queue:** effective-config-jacobian-denominator-covariance-dependence; membership S2; preserved capability label `None`.
- **Current source route:** CalibrationReport v2 projection + Calibrator mapping + adapter JΣJᵀ; legacy/no map unavailable. Tests exist, unrun.
- **Existing selectors:** `tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py::test_v2_report_without_projection_does_not_use_v1_name_identity`, `tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py::test_v2_projection_must_cover_every_reported_calibrated_field`, `tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py::test_tied_projection_is_invariant_to_coordinate_name`
- **Concrete input/control:** Tied map has one coordinate variance Σ=[[.0025]], std=.05; J=[[1],[1]] maps to A.rate and B.rate, so each covariance row is [.0025,.0025]. Rename coordinate and preserve result. v2 without/incomplete map remains unavailable.
- **Property gap:** Adapter recomputes JΣJᵀ and refuses v2 field-name identity; tests do not show Calibrator→persisted v2 report→fresh adapter using actual producer bytes.
- **Next falsifier or boundary:** Add one real producer→CAS→fresh adapter chain with tied coordinates, rename/permutation, missing/extra row controls; consume only source-generated projection.
- **Owner-supplied fact:** Fitted-coordinate ownership and covariance source come from calibration owner.
- **P37 / P38 / P40:** Projection recomputes; fitted coordinate ownership and covariance provenance are source-produced inputs. / Two tied fields become independent if field-name order substitutes for actual mapping. / Whole coordinate-to-field set.

### B200 — Duplicate artifact is not independent evidence; exact repeats dedupe, conflicts reject, source count stays distinct from effective information count.

- **Queue:** effective-config-jacobian-denominator-covariance-dependence; membership S2; preserved capability label `None`.
- **Current source route:** Aggregator reconciles exact origin/equality; exact repeats dedupe, conflict rejects, distinct refs remain dependency-unknown; label alone cannot combine.
- **Existing selectors:** `tests/unit/foundry/uncertainty/test_aggregation_strategies.py::test_precision_weighted_equal_variance_does_not_trust_independence_label`, `tests/unit/foundry/uncertainty/test_aggregation_strategies.py::test_precision_weighted_does_not_favor_a_source_without_resolved_relation`, `tests/unit/foundry/uncertainty/test_aggregation_strategies.py::test_bayesian_combination_without_resolved_relation_does_not_narrow`
- **Concrete input/control:** Exact pair: means 10/12, std 1/1, both labeled independent; result stays unresolved hull. Also mean 10/std .5 vs 20/std 5 and Bayesian means 10/10.5 without relation; no narrowing.
- **Property gap:** Direct aggregator ignores caller independence label and preserves hull; no persisted producer→fresh consumer/source-owner relation path shown in selected tests.
- **Next falsifier or boundary:** Run direct controls. Extend existing artifact relation only if owner-supported relation exists; exact duplicate/conflict through fresh consumer. Different refs alone must never imply independence.
- **Owner-supplied fact:** Independence/dependence and overlapping source rows are source-owner facts, not distinct-ID or caller-label implications.
- **P37 / P38 / P40:** Identity/equality recompute; independence/dependence relation not_established absent source evidence. / Different refs may overlap data despite metadata saying independent. / Distinct dependency class from B194/B197.

## Cross-cutting disposition

Run reuse-first against the existing producers, artifacts and consumers named above. Current tests are a selector queue, not test results. Where producer→persisted artifact→fresh consumer exists (LA-032, B161 candidate-only, B172/B173 diagnostics, B194), run the full path and marker-retaining negative. Where only a direct helper/selector exists (B19 comparator binding, B20 permutation, B22 shifted/empty coverage, B36 transform, B157 actual L4 handoff, B197 Calibrator-to-fresh-adapter, B200 source relation), record that exact missing bridge and propose the smallest test/extension after root has the run results.

Keep candidate and authority bands separate. The queue can establish recomputed mechanics and typed refusals; it cannot establish externally signed comparator facts, source currentness, owner permission, sampling law, measurement units, graph truth, or conditional dependence law. Missing owner inputs keep the protected claim blocked or candidate-limited, while controlled candidate diagnostics may still run.

P40 was applied before selection: B172/B173 remain one complete scenario×metric×backend×consumer verifier class; do not repair one statistic or surface at a time. B161 remains one source-bound refinement class and candidate-only unless the actual owner relation exists. LA-036 remains one conditional-method refusal across both memberships. B31 remains one finding with separate uncertainty-channel and S3 subject/unit acceptance checks. Other IDs keep their distinct original properties. No own test red exists because no test was run; P41 ownership is not established by this audit.

**Closure:** `closure_ids=[]`.
