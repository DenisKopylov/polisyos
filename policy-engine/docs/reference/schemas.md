# JSON Schema Catalog
Related explanation: [Trinity](../explanation/trinity.md).

This catalog reflects the current committed schema snapshots in `schemas/snapshots/` and the runtime OpenAPI snapshot in `schemas/runtime_api_v1.openapi.json`. For ABI compatibility rules and versioning policy, see [ADR-0005](../adr/0005-abi-schema-gate-versioning.md).

## Snapshot Summary

- IR snapshot: `82` schemas, generated `2026-03-28T13:16:24+00:00`, all `compat_mode=strict`.
- Fabric world ABI snapshot: `2` schemas, generated `2026-03-28T13:16:21+00:00`, all `compat_mode=strict`.
- Snapshot manifests record `schema_version`, `version_field`, `priority`, `sha256_full`, and `sha256_semantic` for drift checks.
- Current IR priority split: `p0=16`, `p1=32`, `p2=34`. Fabric priority split: `p0=2`.
- Schema-adjacent artifacts also tracked in `schemas/`:
  - `schemas/runtime_api_v1.openapi.json` — committed Runtime API OpenAPI contract
  - `schemas/snapshots/connectors/contracts.json` — connector contract snapshot (not JSON Schema)

## Versioning Notes

- Most IR schemas expose an explicit `schema_version` field in the payload and in `_manifest.json`.
- `version_field` is currently absent for these IR snapshots: `certification_result`, `data_view_request`, `entity_scope`, `governance_pass_alias_status`, `identification_mode`, `multiplex_graph_layer_id`, `observation_family`, `outer_search_result`, `source_confidence_tier`, `strategic_response_channel`.
- Fabric world ABI schemas (`edge_kind`, `node_kind`) are strict snapshots without an inline version field.
- Raw schema locations are shown as repo-relative paths rather than site links because the snapshot files live outside the MkDocs `docs/` tree.

## IR Schemas

### Governance & decision control

| Schema | Type | Version | Description | Key fields | Raw path |
|--------|------|---------|-------------|------------|----------|
| `governance_pass_alias` | `GovernancePassAlias` | `—` | Schema snapshot for Governance Pass Alias. | `canonical_pass_id`, `status` | `../../schemas/snapshots/ir/governance_pass_alias.schema.json` |
| `governance_pass_alias_registry` | `GovernancePassAliasRegistry` | `1.0` | Registry schema for governance pass alias. | `aliases`, `schema_version` | `../../schemas/snapshots/ir/governance_pass_alias_registry.schema.json` |
| `governance_pass_alias_status` | `GovernancePassAliasStatus` | `—` | Schema snapshot for Governance Pass Alias Status. | - | `../../schemas/snapshots/ir/governance_pass_alias_status.schema.json` |
| `governance_pass_mapping_bundle` | `GovernancePassMappingBundle` | `1.0` | Bundle schema for governance pass mapping. | `family_passes`, `alias_registry` | `../../schemas/snapshots/ir/governance_pass_mapping_bundle.schema.json` |
| `gate_context` | `GateContext` | `—` | Schema snapshot for Gate Context. | `workflow_id`, `node_alias`, `phase` | `../../schemas/snapshots/ir/gate_context.schema.json` |
| `gate_request` | `GateRequest` | `1.1` | Schema snapshot for Gate Request. | `request_id`, `run_id`, `reason`, `context` | `../../schemas/snapshots/ir/gate_request.schema.json` |
| `gate_decision` | `GateDecision` | `1.0` | Schema snapshot for Gate Decision. | `request_id`, `run_id`, `verdict`, `approver_id` | `../../schemas/snapshots/ir/gate_decision.schema.json` |
| `gate_event` | `GateEvent` | `1.0` | Schema snapshot for Gate Event. | `event_type`, `run_id`, `request_id` | `../../schemas/snapshots/ir/gate_event.schema.json` |
| `quality_report` | `QualityReport` | `1.0` | Report schema for quality. | `quality_report_id`, `scope`, `run_event_id`, `policy_id` | `../../schemas/snapshots/ir/quality_report.schema.json` |
| `trust_assessment` | `TrustAssessment` | `1.0` | Schema snapshot for Trust Assessment. | `trust_assessment_id`, `policy_id`, `algorithm_version`, `target_world_id` | `../../schemas/snapshots/ir/trust_assessment.schema.json` |
| `certification_result` | `CertificationResult` | `—` | Result of validating a chain of alignment certificates. | `passed`, `effective_confidence` | `../../schemas/snapshots/ir/certification_result.schema.json` |

### Problem framing & policy design

| Schema | Type | Version | Description | Key fields | Raw path |
|--------|------|---------|-------------|------------|----------|
| `problem_frame` | `ProblemFrame` | `1.0` | ProblemFrame: The "Why" artifact. | `problem_id`, `domain` | `../../schemas/snapshots/ir/problem_frame.schema.json` |
| `policy_spec` | `PolicySpec` | `1.0` | PolicySpec: The "What" artifact. | `policy_id` | `../../schemas/snapshots/ir/policy_spec.schema.json` |
| `policy_portfolio` | `PolicyPortfolio` | `1.0` | Portfolio-level IR artifact for multi-policy optimization. | `portfolio_id` | `../../schemas/snapshots/ir/policy_portfolio.schema.json` |
| `model_spec` | `ModelSpec` | `1.0` | ModelSpec: The "How" artifact (WorldModel). | `model_id`, `data_snapshot_ref` | `../../schemas/snapshots/ir/model_spec.schema.json` |
| `trinity_bundle` | `TrinityBundle` | `1.0` | Bundle containing the three canonical Trinity artifacts. | `problem_frame`, `policy_spec`, `model_spec` | `../../schemas/snapshots/ir/trinity_bundle.schema.json` |
| `context_adaptive_parameter_bundle` | `ContextAdaptiveParameterBundle` | `1.0` | Parameters selected from SKG and adapted for a target simulation context. | `target_context`, `simulation_domain` | `../../schemas/snapshots/ir/context_adaptive_parameter_bundle.schema.json` |
| `policy_recommendation` | `PolicyRecommendation` | `1.0` | Schema snapshot for Policy Recommendation. | `budget_constraint`, `cas_artifact_id`, `hte_result_ref`, `metadata` | `../../schemas/snapshots/ir/policy_recommendation.schema.json` |
| `data_view_request` | `DataViewRequest` | `—` | Schema snapshot for Data View Request. | `request_id`, `run_id`, `view_type`, `metrics` | `../../schemas/snapshots/ir/data_view_request.schema.json` |

### Observation & measurement

| Schema | Type | Version | Description | Key fields | Raw path |
|--------|------|---------|-------------|------------|----------|
| `entity_scope` | `EntityScope` | `—` | Schema snapshot for Entity Scope. | - | `../../schemas/snapshots/ir/entity_scope.schema.json` |
| `observation_family` | `ObservationFamily` | `—` | Family schema for observation. | - | `../../schemas/snapshots/ir/observation_family.schema.json` |
| `observation_family_policy` | `ObservationFamilyPolicy` | `1.0` | Schema snapshot for Observation Family Policy. | `family`, `primary_identification_mode` | `../../schemas/snapshots/ir/observation_family_policy.schema.json` |
| `observation_family_policy_registry` | `ObservationFamilyPolicyRegistry` | `1.0` | Registry schema for observation family policy. | `policies`, `schema_version` | `../../schemas/snapshots/ir/observation_family_policy_registry.schema.json` |
| `observation_panel` | `ObservationPanel` | `1.0` | Panel schema for observation. | `panel_id`, `family`, `time_grain`, `records` | `../../schemas/snapshots/ir/observation_panel.schema.json` |
| `observation_record` | `ObservationRecord` | `1.0` | Record schema for observation. | `observation_id`, `family`, `time_grain`, `period_start` | `../../schemas/snapshots/ir/observation_record.schema.json` |
| `observation_to_contract_manifest` | `ObservationToContractManifest` | `1.0` | Manifest schema for observation to contract. | `routes` | `../../schemas/snapshots/ir/observation_to_contract_manifest.schema.json` |
| `source_confidence_tier` | `SourceConfidenceTier` | `—` | Schema snapshot for Source Confidence Tier. | - | `../../schemas/snapshots/ir/source_confidence_tier.schema.json` |
| `measurement_aware_loss_config` | `MeasurementAwareLossConfig` | `1.0` | Configuration schema for measurement aware loss. | `censoring_discount`, `lag_half_life_days`, `notes`, `regime_boundary_discount` | `../../schemas/snapshots/ir/measurement_aware_loss_config.schema.json` |
| `measurement_aware_target` | `MeasurementAwareTarget` | `1.0` | Schema snapshot for Measurement Aware Target. | `target_id`, `observation_family`, `metric_id`, `identification_mode` | `../../schemas/snapshots/ir/measurement_aware_target.schema.json` |
| `calibration_config` | `CalibrationConfig` | `0.1` | Корневой контракт калибрации. | `clip_grad_norm`, `constraint_loss`, `constraint_values`, `early_stop_min_delta` | `../../schemas/snapshots/ir/calibration_config.schema.json` |
| `calibration_target_bundle_manifest` | `CalibrationTargetBundleManifest` | `1.0` | Bundle manifest schema for calibration target. | `contract_target`, `required_arrays`, `axis_semantics`, `observation_families` | `../../schemas/snapshots/ir/calibration_target_bundle_manifest.schema.json` |
| `lesson_registry_seed_bundle` | `LessonRegistrySeedBundle` | `1.0` | Bundle schema for lesson registry seed. | `contract_target`, `seed_entries` | `../../schemas/snapshots/ir/lesson_registry_seed_bundle.schema.json` |

### Causal graphs, queries & identification

| Schema | Type | Version | Description | Key fields | Raw path |
|--------|------|---------|-------------|------------|----------|
| `causal_graph_model` | `CausalGraphModel` | `1.0` | DAG / CPDAG / PAG / MGRAPH / ADMG causal graph IR contract. | `graph_type`, `nodes`, `edges` | `../../schemas/snapshots/ir/causal_graph_model.schema.json` |
| `causal_effect_report` | `CausalEffectReport` | `1.0` | Report schema for causal effect. | `method`, `estimand`, `inference_method`, `sample_size` | `../../schemas/snapshots/ir/causal_effect_report.schema.json` |
| `hte_result` | `HTEResult` | `1.0` | Result schema for hte. | `method`, `ate`, `ate_ci_lower`, `ate_ci_upper` | `../../schemas/snapshots/ir/hte_result.schema.json` |
| `causal_query` | `CausalQuery` | `—` | Schema snapshot for Causal Query. | `query_type`, `treatment_variable`, `outcome_variable` | `../../schemas/snapshots/ir/causal_query.schema.json` |
| `causal_query_result` | `CausalQueryResult` | `1.0` | Result schema for causal query. | `query`, `result_mean`, `result_std`, `result_ci` | `../../schemas/snapshots/ir/causal_query_result.schema.json` |
| `identification_mode` | `IdentificationMode` | `—` | Schema snapshot for Identification Mode. | - | `../../schemas/snapshots/ir/identification_mode.schema.json` |
| `bounds_estimation_bundle` | `BoundsEstimationBundle` | `1.0` | Bundle schema for bounds estimation. | `channels` | `../../schemas/snapshots/ir/bounds_estimation_bundle.schema.json` |
| `partial_identification_result` | `PartialIdentificationResult` | `1.0` | Result of partial identification analysis (e.g., Manski bounds on ATE). | `method`, `lower_bound`, `upper_bound`, `confidence` | `../../schemas/snapshots/ir/partial_identification_result.schema.json` |
| `proxy_identification_bundle` | `ProxyIdentificationBundle` | `1.0` | Bundle schema for proxy identification. | `contract_target`, `proxy_channels` | `../../schemas/snapshots/ir/proxy_identification_bundle.schema.json` |
| `causal_panel_bundle_manifest` | `CausalPanelBundleManifest` | `1.0` | Bundle manifest schema for causal panel. | `contract_target`, `required_columns` | `../../schemas/snapshots/ir/causal_panel_bundle_manifest.schema.json` |
| `dtr_treatment_sequence_bundle_manifest` | `DTRTreatmentSequenceBundleManifest` | `1.0` | Bundle manifest schema for dtr treatment sequence. | `contract_target`, `required_arrays`, `axis_semantics` | `../../schemas/snapshots/ir/dtr_treatment_sequence_bundle_manifest.schema.json` |
| `network_causal_contract_bundle` | `NetworkCausalContractBundle` | `1.0` | Bundle schema for network causal contract. | `contract_target`, `supported_layers` | `../../schemas/snapshots/ir/network_causal_contract_bundle.schema.json` |
| `network_contract_bundle` | `NetworkContractBundle` | `1.0` | Bundle schema for network contract. | `contract_targets`, `graph_layers`, `source_artifacts` | `../../schemas/snapshots/ir/network_contract_bundle.schema.json` |
| `transportability_result` | `TransportabilityResult` | `2.0` | Phase 13 transportability contract with legacy-read compatibility. | `algorithm_version`, `assumes_time_stationarity`, `base_confidence`, `blocking_s_nodes` | `../../schemas/snapshots/ir/transportability_result.schema.json` |
| `refutation_result` | `RefutationResult` | `—` | Result schema for refutation. | `test_type`, `original_estimate`, `refuted_estimate`, `passed` | `../../schemas/snapshots/ir/refutation_result.schema.json` |
| `structural_causal_model_spec` | `StructuralCausalModelSpec` | `1.0` | Specification schema for structural causal model. | `graph` | `../../schemas/snapshots/ir/structural_causal_model_spec.schema.json` |
| `causal_discovery_report` | `CausalDiscoveryReport` | `1.0` | Report schema for causal discovery. | `method`, `graph` | `../../schemas/snapshots/ir/causal_discovery_report.schema.json` |
| `causal_model_ensemble` | `CausalModelEnsemble` | `1.0` | Ensemble of causal models capturing structural uncertainty. | `members` | `../../schemas/snapshots/ir/causal_model_ensemble.schema.json` |
| `literature_causal_prior` | `LiteratureCausalPrior` | `1.0` | Schema snapshot for Literature Causal Prior. | `edges`, `environment_audit`, `metadata`, `schema_version` | `../../schemas/snapshots/ir/literature_causal_prior.schema.json` |

### Temporal, strategic & intervention design

| Schema | Type | Version | Description | Key fields | Raw path |
|--------|------|---------|-------------|------------|----------|
| `temporal_intervention_sequence` | `TemporalInterventionSequence` | `1.0` | Sequence schema for temporal intervention. | `sequence_id`, `dynamic_intervention_id`, `steps` | `../../schemas/snapshots/ir/temporal_intervention_sequence.schema.json` |
| `temporal_intervention_step` | `TemporalInterventionStep` | `—` | Step schema for temporal intervention. | `step_id`, `effective_date`, `intervention_id` | `../../schemas/snapshots/ir/temporal_intervention_step.schema.json` |
| `strategic_response_channel` | `StrategicResponseChannel` | `—` | Schema snapshot for Strategic Response Channel. | - | `../../schemas/snapshots/ir/strategic_response_channel.schema.json` |
| `strategic_response_specs_bundle` | `StrategicResponseSpecsBundle` | `1.0` | Bundle schema for strategic response specs. | `expectations` | `../../schemas/snapshots/ir/strategic_response_specs_bundle.schema.json` |
| `multiplex_graph_layer_id` | `MultiplexGraphLayerId` | `—` | Schema snapshot for Multiplex Graph Layer Id. | - | `../../schemas/snapshots/ir/multiplex_graph_layer_id.schema.json` |

### Evaluation, analytics & simulation bundles

| Schema | Type | Version | Description | Key fields | Raw path |
|--------|------|---------|-------------|------------|----------|
| `backtest_plan_bundle` | `BacktestPlanBundle` | `1.0` | Bundle schema for backtest plan. | `contract_target`, `required_fields` | `../../schemas/snapshots/ir/backtest_plan_bundle.schema.json` |
| `backtest_report` | `BacktestReport` | `1.0` | Report schema for backtest. | `report_id` | `../../schemas/snapshots/ir/backtest_report.schema.json` |
| `sensitivity_result` | `SensitivityResult` | `1.0` | Result schema for sensitivity. | `benchmark_covariates`, `benchmark_results`, `conversion_method`, `e_value` | `../../schemas/snapshots/ir/sensitivity_result.schema.json` |
| `specification_curve_bundle` | `SpecificationCurveBundle` | `1.0` | Bundle schema for specification curve. | `source_specifications` | `../../schemas/snapshots/ir/specification_curve_bundle.schema.json` |
| `uncertainty_envelope` | `UncertaintyEnvelope` | `1.0` | Unified uncertainty contract for Policy OS IR layer. | `point_estimate`, `confidence_interval`, `source` | `../../schemas/snapshots/ir/uncertainty_envelope.schema.json` |
| `distributional_report` | `DistributionalReport` | `1.0` | Distributional impact analysis report for policy evaluation. | `breakdowns` | `../../schemas/snapshots/ir/distributional_report.schema.json` |
| `outer_search_result` | `OuterSearchResult` | `—` | Result of bounded grid search over alignment policy knobs. | `best_config`, `best_score`, `configs_evaluated`, `truncated` | `../../schemas/snapshots/ir/outer_search_result.schema.json` |
| `abm_alignment_report` | `ABMAlignmentReport` | `1.0` | SCM to ABM consistency report. | `alignment_results`, `mappings`, `overall_consistent`, `phase_transitions` | `../../schemas/snapshots/ir/abm_alignment_report.schema.json` |
| `panel_econometric_bundle_manifest` | `PanelEconometricBundleManifest` | `1.0` | Bundle manifest schema for panel econometric. | `contract_target`, `required_columns` | `../../schemas/snapshots/ir/panel_econometric_bundle_manifest.schema.json` |
| `leontief_io_bundle` | `LeontiefIOBundle` | `1.0` | Bundle schema for leontief io. | `regions`, `sectors` | `../../schemas/snapshots/ir/leontief_io_bundle.schema.json` |
| `microsim_survey_contract_bundle` | `MicrosimSurveyContractBundle` | `1.0` | Bundle schema for microsim survey contract. | `contract_target`, `required_fields`, `observation_families` | `../../schemas/snapshots/ir/microsim_survey_contract_bundle.schema.json` |
| `survival_data_bundle_manifest` | `SurvivalDataBundleManifest` | `1.0` | Bundle manifest schema for survival data. | `contract_target`, `required_columns` | `../../schemas/snapshots/ir/survival_data_bundle_manifest.schema.json` |

### Legal, normpack & text extraction

| Schema | Type | Version | Description | Key fields | Raw path |
|--------|------|---------|-------------|------------|----------|
| `norm_pack` | `NormPack` | `1.0` | Package of applicable norms for policy evaluation. | `pack_id`, `jurisdiction` | `../../schemas/snapshots/ir/norm_pack.schema.json` |
| `norm_ref` | `NormRef` | `1.0` | Reference to a normative document provision. | `provision_id` | `../../schemas/snapshots/ir/norm_ref.schema.json` |
| `norm_rule` | `NormRule` | `1.0` | Single rule within a norm pack. | `norm_id`, `rule_type`, `description` | `../../schemas/snapshots/ir/norm_rule.schema.json` |
| `article_extraction_result` | `ArticleExtractionResult` | `1.5` | Primary IR contract for literature extraction pipeline. | `openalex_id`, `title`, `extraction_model`, `extraction_timestamp` | `../../schemas/snapshots/ir/article_extraction_result.schema.json` |

### Knowledge, provenance & evidence logs

| Schema | Type | Version | Description | Key fields | Raw path |
|--------|------|---------|-------------|------------|----------|
| `claim` | `Claim` | `1.0` | Schema snapshot for Claim. | `claim_id`, `predicate_id`, `value_text`, `confidence` | `../../schemas/snapshots/ir/claim.schema.json` |
| `conflict_set` | `ConflictSet` | `1.0` | Schema snapshot for Conflict Set. | `conflict_set_id`, `conflict_key`, `conflict_kind`, `member_claim_ids` | `../../schemas/snapshots/ir/conflict_set.schema.json` |
| `conflict_resolution` | `ConflictResolution` | `1.0` | Schema snapshot for Conflict Resolution. | `conflict_set_id`, `policy_id`, `algorithm_version`, `candidates` | `../../schemas/snapshots/ir/conflict_resolution.schema.json` |
| `conflict_set_resolution` | `ConflictSetResolution` | `—` | Schema snapshot for Conflict Set Resolution. | `winner_claim_id`, `policy_id`, `confidence`, `rationale` | `../../schemas/snapshots/ir/conflict_set_resolution.schema.json` |
| `doc_fragment` | `DocFragment` | `1.0` | Schema snapshot for Doc Fragment. | `fragment_id`, `doc_version_id`, `locator`, `text_hash` | `../../schemas/snapshots/ir/doc_fragment.schema.json` |
| `doc_meta` | `DocMeta` | `1.0` | Schema snapshot for Doc Meta. | `doc_source_id`, `doc_version_id`, `retrieved_at`, `mime` | `../../schemas/snapshots/ir/doc_meta.schema.json` |
| `fact` | `Fact` | `1.0` | Schema snapshot for Fact. | `fact_id`, `subject_id`, `predicate_id`, `provenance` | `../../schemas/snapshots/ir/fact.schema.json` |
| `fact_segment_manifest` | `FactSegmentManifest` | `1.0` | Manifest schema for fact segment. | `segment_id`, `path`, `row_count`, `sha256` | `../../schemas/snapshots/ir/fact_segment_manifest.schema.json` |
| `prov_activity` | `ProvActivity` | `—` | Schema snapshot for Prov Activity. | `activity_id`, `activity_type`, `label`, `started_at` | `../../schemas/snapshots/ir/prov_activity.schema.json` |
| `world_event` | `WorldEvent` | `1.0` | Schema snapshot for World Event. | `event_id`, `event_kind`, `agent`, `activity` | `../../schemas/snapshots/ir/world_event.schema.json` |

## Fabric World ABI

| Schema | Type | Version | Description | Key fields | Raw path |
|--------|------|---------|-------------|------------|----------|
| `edge_kind` | `EdgeKind` | `—` | Schema snapshot for Edge Kind. | - | `../../schemas/snapshots/fabric/edge_kind.schema.json` |
| `node_kind` | `NodeKind` | `—` | Schema snapshot for Node Kind. | - | `../../schemas/snapshots/fabric/node_kind.schema.json` |

## Connector Contract Snapshot

`schemas/snapshots/connectors/contracts.json` is not a JSON Schema bundle, but it is part of the same compatibility baseline. It currently snapshots three source-connector contracts: `eurostat.data.generic`, `ukons.datasets.generic`, and `worldbank.wdi.generic`.
