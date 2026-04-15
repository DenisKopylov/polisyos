# IR Schema Catalog
Related reference: [Schemas](../schemas.md).

> This page is generated from `polisyos.ir.schema_catalog` and the current package facades.

## Summary

- Total IR types: `899`.
- Public/root-or-package facade types: `463`.
- ABI snapshot-backed types: `82`.
- Export enumeration covers these public packages:

| Package | Export count |
|---------|--------------|
| `polisyos.ir` | 171 |
| `polisyos.ir.analytics` | 95 |
| `polisyos.ir.artifacts` | 33 |
| `polisyos.ir.data` | 10 |
| `polisyos.ir.governance` | 84 |
| `polisyos.ir.kernel` | 52 |
| `polisyos.ir.linker` | 9 |
| `polisyos.ir.migrations` | 10 |
| `polisyos.ir.observation` | 167 |
| `polisyos.ir.passes` | 17 |
| `polisyos.ir.trinity` | 4 |
| `polisyos.ir.world` | 54 |

## Section Summary

| Section | Type count | Public types | Snapshot-backed |
|---------|------------|--------------|-----------------|
| `analytics` | 391 | 100 | 24 |
| `artifacts` | 25 | 25 | 0 |
| `governance` | 75 | 75 | 8 |
| `kernel` | 39 | 38 | 0 |
| `linker` | 7 | 7 | 0 |
| `migrations` | 7 | 2 | 0 |
| `observation` | 139 | 138 | 30 |
| `trinity` | 2 | 1 | 1 |
| `world` | 32 | 32 | 12 |
| `canon` | 2 | 0 | 0 |
| `citations` | 4 | 0 | 0 |
| `connectors` | 21 | 4 | 0 |
| `data` | 7 | 7 | 0 |
| `fact_log` | 7 | 2 | 2 |
| `loaders` | 1 | 0 | 0 |
| `migration_report` | 3 | 0 | 0 |
| `model_spec` | 8 | 8 | 1 |
| `norm_pack` | 5 | 4 | 3 |
| `passes` | 16 | 16 | 0 |
| `portfolio` | 5 | 4 | 1 |
| `predicate` | 5 | 0 | 0 |
| `queries` | 9 | 0 | 0 |
| `refs` | 49 | 4 | 0 |
| `registry_fragments` | 28 | 0 | 0 |
| `schema_catalog` | 6 | 6 | 0 |
| `types` | 6 | 0 | 0 |

## Analytics

### `polisyos.ir.analytics.abm_bridge.ABMAlignmentReport` { #polisyos-ir-analytics-abm-bridge-abmalignmentreport }

- Kind: `pydantic_model`
- Public status: `snapshot_only`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `abm_alignment_report` / `schemas/snapshots/ir/abm_alignment_report.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.abm_bridge.AlignmentResult`, `polisyos.ir.analytics.abm_bridge.MacroMicroMapping`, `polisyos.ir.analytics.abm_bridge.PhaseTransition`
- Summary: SCM to ABM consistency report.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `alignment_results` | `dict[str, polisyos.ir.analytics.abm_bridge.AlignmentResult]` | `no` | `—` | `polisyos.ir.analytics.abm_bridge.AlignmentResult` |
| `mappings` | `list[polisyos.ir.analytics.abm_bridge.MacroMicroMapping]` | `no` | `—` | `polisyos.ir.analytics.abm_bridge.MacroMicroMapping` |
| `overall_consistent` | `bool` | `no` | `False` | — |
| `phase_transitions` | `list[polisyos.ir.analytics.abm_bridge.PhaseTransition]` | `no` | `—` | `polisyos.ir.analytics.abm_bridge.PhaseTransition` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.abm_bridge.AggregationFunction` { #polisyos-ir-analytics-abm-bridge-aggregationfunction }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Aggregation function public type.

| Enum values |
|-------------|
| `mean` |
| `median` |
| `gini` |
| `sum` |
| `count` |

### `polisyos.ir.analytics.abm_bridge.AlignmentResult` { #polisyos-ir-analytics-abm-bridge-alignmentresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.abm_bridge.AlignmentStatus`
- Summary: Per-variable alignment output.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `abm_effect` | `float | NoneType` | `no` | `—` | — |
| `delta` | `float | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `n_runs` | `int` | `no` | `0` | — |
| `scm_effect` | `float | NoneType` | `no` | `—` | — |
| `status` | `polisyos.ir.analytics.abm_bridge.AlignmentStatus` | `yes` | `—` | `polisyos.ir.analytics.abm_bridge.AlignmentStatus` |
| `tolerance_used` | `float | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.abm_bridge.AlignmentStatus` { #polisyos-ir-analytics-abm-bridge-alignmentstatus }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Alignment status between SCM macro effect and ABM macro aggregate.

| Enum values |
|-------------|
| `consistent` |
| `inconsistent` |
| `non_linear_divergence` |
| `insufficient_runs` |

### `polisyos.ir.analytics.abm_bridge.MacroMicroMapping` { #polisyos-ir-analytics-abm-bridge-macromicromapping }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.abm_bridge.AggregationFunction`, `polisyos.ir.analytics.abm_bridge.ToleranceMethod`
- Summary: Mapping from SCM macro variable to ABM aggregate metric.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `abm_aggregation` | `str` | `yes` | `—` | — |
| `agent_property` | `str` | `yes` | `—` | — |
| `aggregation_function` | `polisyos.ir.analytics.abm_bridge.AggregationFunction` | `yes` | `—` | `polisyos.ir.analytics.abm_bridge.AggregationFunction` |
| `macro_variable` | `str` | `yes` | `—` | — |
| `tolerance` | `float | NoneType` | `no` | `—` | — |
| `tolerance_method` | `polisyos.ir.analytics.abm_bridge.ToleranceMethod` | `no` | `<ToleranceMethod.ADAPTIVE: 'adaptive'>` | `polisyos.ir.analytics.abm_bridge.ToleranceMethod` |

### `polisyos.ir.analytics.abm_bridge.PhaseTransition` { #polisyos-ir-analytics-abm-bridge-phasetransition }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Detected ABM phase transition event.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `jump_value` | `float | NoneType` | `no` | `—` | — |
| `post_regime` | `str` | `yes` | `—` | — |
| `pre_regime` | `str` | `yes` | `—` | — |
| `threshold_value` | `float` | `yes` | `—` | — |
| `variable` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.abm_bridge.ToleranceMethod` { #polisyos-ir-analytics-abm-bridge-tolerancemethod }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Tolerance method public type.

| Enum values |
|-------------|
| `adaptive` |
| `fixed` |

### `polisyos.ir.analytics.abstraction.AbstractionCertificate` { #polisyos-ir-analytics-abstraction-abstractioncertificate }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.abstraction.AbstractionPreservationType`, `polisyos.ir.refs.ArtifactRefModel`, `polisyos.ir.refs.FiniteStateAbstractionMapRef`
- Summary: Certificate for query-preserving finite-state abstraction.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `abstraction_map_ref` | `polisyos.ir.refs.FiniteStateAbstractionMapRef` | `yes` | `—` | `polisyos.ir.refs.FiniteStateAbstractionMapRef` |
| `error_bound` | `float | NoneType` | `no` | `—` | — |
| `macro_graph_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `micro_graph_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `preservation_type` | `polisyos.ir.analytics.abstraction.AbstractionPreservationType` | `yes` | `—` | `polisyos.ir.analytics.abstraction.AbstractionPreservationType` |
| `preserved_queries` | `tuple[str]` | `no` | `()` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `validation_notes` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.abstraction.AbstractionPreservationType` { #polisyos-ir-analytics-abstraction-abstractionpreservationtype }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Abstraction preservation type public type.

| Enum values |
|-------------|
| `exact` |
| `approximate` |
| `policy_value_only` |
| `invalid` |

### `polisyos.ir.analytics.abstraction.FiniteStateAbstractionMap` { #polisyos-ir-analytics-abstraction-finitestateabstractionmap }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.abstraction.VariableStateAbstraction`
- Summary: Exact finite-state variable/state quotient map for micro-to-macro verification.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `variable_maps` | `tuple[polisyos.ir.analytics.abstraction.VariableStateAbstraction]` | `yes` | `—` | `polisyos.ir.analytics.abstraction.VariableStateAbstraction` |

### `polisyos.ir.analytics.abstraction.VariableStateAbstraction` { #polisyos-ir-analytics-abstraction-variablestateabstraction }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: One-to-one variable/state quotient used by the exact finite-state verifier.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `macro_variable` | `str` | `yes` | `—` | — |
| `micro_variable` | `str` | `yes` | `—` | — |
| `state_map` | `dict[str, str]` | `yes` | `—` | — |

### `polisyos.ir.analytics.actual_causality.ContingencySet` { #polisyos-ir-analytics-actual-causality-contingencyset }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Contingency set W used in HP AC2 condition.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `size` | `int` | `no` | `0` | — |
| `values` | `dict[str, float]` | `no` | `—` | — |
| `variables` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.actual_causality.HPResult` { #polisyos-ir-analytics-actual-causality-hpresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.actual_causality.ContingencySet`
- Summary: Result of an HP actual cause check (Halpern & Pearl 2005, updated 2016).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `ac1_satisfied` | `bool` | `yes` | `—` | — |
| `ac2_satisfied` | `bool` | `yes` | `—` | — |
| `ac3_satisfied` | `bool` | `yes` | `—` | — |
| `blame_ci` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `cause_value` | `float` | `yes` | `—` | — |
| `cause_values` | `dict[str, float] | NoneType` | `no` | `—` | — |
| `cause_variable` | `str` | `yes` | `—` | — |
| `cause_variables` | `list[str] | NoneType` | `no` | `—` | — |
| `contingency` | `polisyos.ir.analytics.actual_causality.ContingencySet | NoneType` | `no` | `—` | `polisyos.ir.analytics.actual_causality.ContingencySet` |
| `counterfactual_cause_value` | `float` | `yes` | `—` | — |
| `counterfactual_cause_values` | `dict[str, float] | NoneType` | `no` | `—` | — |
| `degree_of_blame` | `float | NoneType` | `no` | `—` | — |
| `degree_of_responsibility` | `float` | `no` | `0.0` | — |
| `effect_value` | `float` | `yes` | `—` | — |
| `effect_variable` | `str` | `yes` | `—` | — |
| `explanation` | `str` | `no` | `''` | — |
| `is_actual_cause` | `bool` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.analytics.actual_causality.PNPSBounds` { #polisyos-ir-analytics-actual-causality-pnpsbounds }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Tian & Pearl (2000) PN/PS/PNS bounds from observational data.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `is_monotone_compatible` | `bool | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `monotone_pns` | `float | NoneType` | `no` | `—` | — |
| `p_x1` | `float | NoneType` | `no` | `—` | — |
| `p_y1_x0` | `float` | `yes` | `—` | — |
| `p_y1_x1` | `float` | `yes` | `—` | — |
| `pn_lower` | `float` | `yes` | `—` | — |
| `pn_upper` | `float` | `yes` | `—` | — |
| `pns_lower` | `float` | `yes` | `—` | — |
| `pns_upper` | `float` | `yes` | `—` | — |
| `ps_lower` | `float` | `yes` | `—` | — |
| `ps_upper` | `float` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.analytics.actual_causality.PNResult` { #polisyos-ir-analytics-actual-causality-pnresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Probability of Necessity result.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bounds_lower` | `float | NoneType` | `no` | `—` | — |
| `bounds_upper` | `float | NoneType` | `no` | `—` | — |
| `computation_method` | `str` | `no` | `'simulation'` | — |
| `counterfactual_value` | `float` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `n_samples` | `int` | `no` | `0` | — |
| `outcome` | `str` | `yes` | `—` | — |
| `pn` | `float` | `yes` | `—` | — |
| `pn_ci` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `treatment` | `str` | `yes` | `—` | — |
| `treatment_value` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.actual_causality.PNSResult` { #polisyos-ir-analytics-actual-causality-pnsresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Probability of Necessity and Sufficiency result.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `computation_method` | `str` | `no` | `'simulation'` | — |
| `counterfactual_value` | `float` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `n_samples` | `int` | `no` | `0` | — |
| `outcome` | `str` | `yes` | `—` | — |
| `pn` | `float | NoneType` | `no` | `—` | — |
| `pns` | `float` | `yes` | `—` | — |
| `pns_ci` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `ps` | `float | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `treatment` | `str` | `yes` | `—` | — |
| `treatment_value` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.actual_causality.PSResult` { #polisyos-ir-analytics-actual-causality-psresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Probability of Sufficiency result.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bounds_lower` | `float | NoneType` | `no` | `—` | — |
| `bounds_upper` | `float | NoneType` | `no` | `—` | — |
| `computation_method` | `str` | `no` | `'simulation'` | — |
| `counterfactual_value` | `float` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `n_samples` | `int` | `no` | `0` | — |
| `outcome` | `str` | `yes` | `—` | — |
| `ps` | `float` | `yes` | `—` | — |
| `ps_ci` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `treatment` | `str` | `yes` | `—` | — |
| `treatment_value` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.alignment_certification.AlignmentCertificate` { #polisyos-ir-analytics-alignment-certification-alignmentcertificate }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.alignment_certification.AlignmentCertificateType`
- Summary: Single alignment certificate between a source and target variable.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `cert_type` | `polisyos.ir.analytics.alignment_certification.AlignmentCertificateType` | `yes` | `—` | `polisyos.ir.analytics.alignment_certification.AlignmentCertificateType` |
| `confidence` | `float` | `yes` | `—` | — |
| `evidence_refs` | `list[str]` | `no` | `—` | — |
| `source_variable` | `str` | `yes` | `—` | — |
| `target_variable` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.alignment_certification.AlignmentCertificateType` { #polisyos-ir-analytics-alignment-certification-alignmentcertificatetype }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Alignment certificate type public type.

| Enum values |
|-------------|
| `exact` |
| `scale_link` |
| `latent_link_irt` |
| `proxy_bundle` |
| `text_concept_map` |

### `polisyos.ir.analytics.alignment_certification.AlignmentCertificationPolicy` { #polisyos-ir-analytics-alignment-certification-alignmentcertificationpolicy }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.alignment_certification.AlignmentCertificateType`
- Summary: Policy governing how alignment certificates are validated.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `allowed_types` | `tuple[polisyos.ir.analytics.alignment_certification.AlignmentCertificateType]` | `no` | `(<AlignmentCertificateType.EXACT: 'exact'>, <AlignmentCertificateType.LATENT_LINK_IRT: 'latent_link_irt'>, <AlignmentCertificateType.PROXY_BUNDLE: 'proxy_bundle'>, <AlignmentCertificateType.SCALE_LINK: 'scale_link'>, <AlignmentCertificateType.TEXT_CONCEPT_MAP: 'text_concept_map'>)` | `polisyos.ir.analytics.alignment_certification.AlignmentCertificateType` |
| `composition_rule` | `Literal[harmonic, multiplicative]` | `no` | `'harmonic'` | — |
| `max_chain_length` | `int` | `no` | `5` | — |
| `tau_min` | `float` | `no` | `0.65` | — |

### `polisyos.ir.analytics.alignment_certification.AlignmentDegradedOutcome` { #polisyos-ir-analytics-alignment-certification-alignmentdegradedoutcome }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.alignment_certification.AlignmentDegradedOutcomeCode`
- Summary: Structured degraded outcome captured inside alignment-report metadata.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `code` | `polisyos.ir.analytics.alignment_certification.AlignmentDegradedOutcomeCode` | `yes` | `—` | `polisyos.ir.analytics.alignment_certification.AlignmentDegradedOutcomeCode` |
| `detail` | `str` | `yes` | `—` | — |
| `fragment_pair` | `tuple[str, str]` | `yes` | `—` | — |

### `polisyos.ir.analytics.alignment_certification.AlignmentDegradedOutcomeCode` { #polisyos-ir-analytics-alignment-certification-alignmentdegradedoutcomecode }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Typed degraded outcomes for optional alignment diagnostics.

| Enum values |
|-------------|
| `ontology_warning_build_failed` |

### `polisyos.ir.analytics.alignment_certification.AlignmentOverallStatus` { #polisyos-ir-analytics-alignment-certification-alignmentoverallstatus }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Alignment overall status public type.

| Enum values |
|-------------|
| `aligned` |
| `partially_aligned` |
| `incompatible` |

### `polisyos.ir.analytics.alignment_certification.AlignmentReport` { #polisyos-ir-analytics-alignment-certification-alignmentreport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.1`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.alignment_certification.AlignmentOverallStatus`, `polisyos.ir.analytics.alignment_certification.AlignmentReviewStatus`, `polisyos.ir.analytics.alignment_certification.MeasurementComparabilityGrade`, `polisyos.ir.analytics.alignment_certification.VariableAlignmentCertificate`
- Summary: Aggregate semantic alignment status across stitched SCM fragments.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `alignment_assumptions` | `list[str]` | `no` | `—` | — |
| `fragment_ids` | `list[str]` | `no` | `—` | — |
| `incompatible_pairs` | `list[tuple[str, str]]` | `no` | `—` | — |
| `measurement_comparability_grade` | `polisyos.ir.analytics.alignment_certification.MeasurementComparabilityGrade` | `yes` | `—` | `polisyos.ir.analytics.alignment_certification.MeasurementComparabilityGrade` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `ontology_mismatch_warnings` | `list[str]` | `no` | `—` | — |
| `overall_status` | `polisyos.ir.analytics.alignment_certification.AlignmentOverallStatus` | `yes` | `—` | `polisyos.ir.analytics.alignment_certification.AlignmentOverallStatus` |
| `per_variable_certificates` | `list[polisyos.ir.analytics.alignment_certification.VariableAlignmentCertificate]` | `no` | `—` | `polisyos.ir.analytics.alignment_certification.VariableAlignmentCertificate` |
| `review_status` | `polisyos.ir.analytics.alignment_certification.AlignmentReviewStatus` | `no` | `<AlignmentReviewStatus.CLEAR: 'clear'>` | `polisyos.ir.analytics.alignment_certification.AlignmentReviewStatus` |
| `schema_version` | `str` | `no` | `'1.1'` | — |

### `polisyos.ir.analytics.alignment_certification.AlignmentReviewStatus` { #polisyos-ir-analytics-alignment-certification-alignmentreviewstatus }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Alignment review status public type.

| Enum values |
|-------------|
| `clear` |
| `pending_review` |

### `polisyos.ir.analytics.alignment_certification.AlignmentReviewerState` { #polisyos-ir-analytics-alignment-certification-alignmentreviewerstate }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Alignment reviewer state data model.

| Enum values |
|-------------|
| `automated` |
| `pending_review` |
| `human_verified` |

### `polisyos.ir.analytics.alignment_certification.AlignmentType` { #polisyos-ir-analytics-alignment-certification-alignmenttype }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Alignment type public type.

| Enum values |
|-------------|
| `exact` |
| `scale_linked` |
| `proxy` |
| `latent_bridge` |
| `incompatible` |

### `polisyos.ir.analytics.alignment_certification.AlignmentVerificationConfig` { #polisyos-ir-analytics-alignment-certification-alignmentverificationconfig }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Deterministic verification rules for SCM fragment interface alignment.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `explicit_latent_bridges` | `dict[str, str]` | `no` | `—` | — |
| `human_verified_pairs` | `list[str]` | `no` | `—` | — |
| `known_unit_transforms` | `dict[str, str | NoneType]` | `no` | `—` | — |
| `metadata_comparator_overrides` | `dict[str, str]` | `no` | `—` | — |
| `min_candidate_score` | `float` | `no` | `0.45` | — |
| `min_definition_overlap` | `float` | `no` | `0.25` | — |
| `min_exact_semantic_score` | `float` | `no` | `0.85` | — |
| `min_proxy_score` | `float` | `no` | `0.55` | — |
| `seed_alignments_path` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.alignment_certification.CertificationResult` { #polisyos-ir-analytics-alignment-certification-certificationresult }

- Kind: `pydantic_model`
- Public status: `snapshot_only`
- Current version: `—`
- Exported from: —
- ABI snapshot: `certification_result` / `schemas/snapshots/ir/certification_result.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Result of validating a chain of alignment certificates.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `effective_confidence` | `float` | `yes` | `—` | — |
| `long_chain_warning` | `str | NoneType` | `no` | `—` | — |
| `passed` | `bool` | `yes` | `—` | — |
| `violations` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.alignment_certification.MeasurementComparabilityGrade` { #polisyos-ir-analytics-alignment-certification-measurementcomparabilitygrade }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Measurement comparability grade public type.

| Enum values |
|-------------|
| `high` |
| `medium` |
| `low` |
| `insufficient` |

### `polisyos.ir.analytics.alignment_certification.MetadataCheckStatus` { #polisyos-ir-analytics-alignment-certification-metadatacheckstatus }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Metadata check status public type.

| Enum values |
|-------------|
| `match` |
| `compatible` |
| `warning` |
| `mismatch` |
| `unknown` |

### `polisyos.ir.analytics.alignment_certification.OuterObjectiveResult` { #polisyos-ir-analytics-alignment-certification-outerobjectiveresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.alignment_certification.AlignmentCertificationPolicy`
- Summary: Result of evaluating the outer objective for one policy configuration.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `config` | `polisyos.ir.analytics.alignment_certification.AlignmentCertificationPolicy` | `yes` | `—` | `polisyos.ir.analytics.alignment_certification.AlignmentCertificationPolicy` |
| `conflict_norm` | `float` | `yes` | `—` | — |
| `coverage` | `float` | `yes` | `—` | — |
| `is_feasible` | `bool` | `yes` | `—` | — |
| `lambda_conflict` | `float` | `yes` | `—` | — |
| `score` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.alignment_certification.OuterSearchResult` { #polisyos-ir-analytics-alignment-certification-outersearchresult }

- Kind: `pydantic_model`
- Public status: `snapshot_only`
- Current version: `—`
- Exported from: —
- ABI snapshot: `outer_search_result` / `schemas/snapshots/ir/outer_search_result.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.alignment_certification.AlignmentCertificationPolicy`, `polisyos.ir.analytics.alignment_certification.OuterObjectiveResult`
- Summary: Result of bounded grid search over alignment policy knobs.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `all_scores` | `list[polisyos.ir.analytics.alignment_certification.OuterObjectiveResult]` | `no` | `—` | `polisyos.ir.analytics.alignment_certification.OuterObjectiveResult` |
| `best_config` | `polisyos.ir.analytics.alignment_certification.AlignmentCertificationPolicy` | `yes` | `—` | `polisyos.ir.analytics.alignment_certification.AlignmentCertificationPolicy` |
| `best_score` | `float` | `yes` | `—` | — |
| `configs_evaluated` | `int` | `yes` | `—` | — |
| `truncated` | `bool` | `yes` | `—` | — |

### `polisyos.ir.analytics.alignment_certification.VariableAlignmentCertificate` { #polisyos-ir-analytics-alignment-certification-variablealignmentcertificate }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.1`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.alignment_certification.AlignmentReviewerState`, `polisyos.ir.analytics.alignment_certification.AlignmentType`, `polisyos.ir.analytics.alignment_certification.VariableMetadataCheck`
- Summary: B.1 IR contract for semantic alignment between fragment interface variables.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `alignment_type` | `polisyos.ir.analytics.alignment_certification.AlignmentType` | `yes` | `—` | `polisyos.ir.analytics.alignment_certification.AlignmentType` |
| `assumptions_introduced` | `list[str]` | `no` | `—` | — |
| `fragment_a_id` | `str` | `yes` | `—` | — |
| `fragment_b_id` | `str` | `yes` | `—` | — |
| `latent_bridge_ref` | `str | NoneType` | `no` | `—` | — |
| `measurement_model_a_ref` | `str | NoneType` | `no` | `—` | — |
| `measurement_model_b_ref` | `str | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `metadata_checks` | `list[polisyos.ir.analytics.alignment_certification.VariableMetadataCheck]` | `no` | `—` | `polisyos.ir.analytics.alignment_certification.VariableMetadataCheck` |
| `proxy_evidence_ref` | `str | NoneType` | `no` | `—` | — |
| `reviewer` | `polisyos.ir.analytics.alignment_certification.AlignmentReviewerState` | `no` | `<AlignmentReviewerState.AUTOMATED: 'automated'>` | `polisyos.ir.analytics.alignment_certification.AlignmentReviewerState` |
| `schema_version` | `str` | `no` | `'1.1'` | — |
| `transform_ref` | `str | NoneType` | `no` | `—` | — |
| `variable_a` | `str` | `yes` | `—` | — |
| `variable_b` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.alignment_certification.VariableMetadataCheck` { #polisyos-ir-analytics-alignment-certification-variablemetadatacheck }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.alignment_certification.MetadataCheckStatus`
- Summary: Variable metadata check public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `comparator` | `str` | `yes` | `—` | — |
| `key` | `str` | `yes` | `—` | — |
| `left_value` | `Any` | `no` | `—` | — |
| `note` | `str | NoneType` | `no` | `—` | — |
| `right_value` | `Any` | `no` | `—` | — |
| `status` | `polisyos.ir.analytics.alignment_certification.MetadataCheckStatus` | `yes` | `—` | `polisyos.ir.analytics.alignment_certification.MetadataCheckStatus` |

### `polisyos.ir.analytics.applicability.ApplicabilityEntitySelector` { #polisyos-ir-analytics-applicability-applicabilityentityselector }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.applicability.IdSelector`
- Summary: Applicability entity selector public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `actors` | `polisyos.ir.analytics.applicability.IdSelector` | `no` | `—` | `polisyos.ir.analytics.applicability.IdSelector` |
| `concepts` | `polisyos.ir.analytics.applicability.IdSelector` | `no` | `—` | `polisyos.ir.analytics.applicability.IdSelector` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.analytics.applicability.ConditionExpr` { #polisyos-ir-analytics-applicability-conditionexpr }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Condition expr public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `expr` | `str` | `yes` | `—` | — |
| `language` | `str` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `refs` | `dict[str, str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.analytics.applicability.IdSelector` { #polisyos-ir-analytics-applicability-idselector }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: ID selector public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `all_of` | `list[str]` | `no` | `—` | — |
| `any_of` | `list[str]` | `no` | `—` | — |
| `none_of` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.analytics.applicability.NormApplicability` { #polisyos-ir-analytics-applicability-normapplicability }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.applicability.ApplicabilityEntitySelector`, `polisyos.ir.analytics.applicability.ConditionExpr`, `polisyos.ir.analytics.applicability.IdSelector`, `polisyos.ir.analytics.applicability.NormApplicability`, `polisyos.ir.analytics.applicability.TimeWindow`
- Summary: Norm applicability public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `conditions` | `list[polisyos.ir.analytics.applicability.ConditionExpr]` | `no` | `—` | `polisyos.ir.analytics.applicability.ConditionExpr` |
| `exceptions` | `list[polisyos.ir.analytics.applicability.NormApplicability]` | `no` | `—` | `polisyos.ir.analytics.applicability.NormApplicability` |
| `jurisdiction` | `polisyos.ir.analytics.applicability.IdSelector` | `no` | `—` | `polisyos.ir.analytics.applicability.IdSelector` |
| `notes` | `list[str]` | `no` | `—` | — |
| `object` | `polisyos.ir.analytics.applicability.ApplicabilityEntitySelector` | `no` | `—` | `polisyos.ir.analytics.applicability.ApplicabilityEntitySelector` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `subject` | `polisyos.ir.analytics.applicability.ApplicabilityEntitySelector` | `no` | `—` | `polisyos.ir.analytics.applicability.ApplicabilityEntitySelector` |
| `time` | `polisyos.ir.analytics.applicability.TimeWindow` | `no` | `—` | `polisyos.ir.analytics.applicability.TimeWindow` |

### `polisyos.ir.analytics.applicability.TimeWindow` { #polisyos-ir-analytics-applicability-timewindow }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Time window public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `valid_from` | `str | NoneType` | `no` | `—` | — |
| `valid_to` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.backtest.BacktestReport` { #polisyos-ir-analytics-backtest-backtestreport }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:BacktestReport`, `polisyos.ir:BacktestReport`
- ABI snapshot: `backtest_report` / `schemas/snapshots/ir/backtest_report.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.backtest.BacktestScenario`, `polisyos.ir.analytics.backtest.BiasDirection`, `polisyos.ir.analytics.backtest.SystematicBias`
- Summary: Summarize historical validation quality and trust diagnostics for one model/policy pair.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `backtest_config_ref` | `str | NoneType` | `no` | `—` | — |
| `cas_artifact_id` | `str | NoneType` | `no` | `—` | — |
| `decision_packet_ref` | `str | NoneType` | `no` | `—` | — |
| `degraded` | `bool` | `no` | `False` | — |
| `degraded_reasons` | `list[str]` | `no` | `—` | — |
| `detected_biases` | `list[polisyos.ir.analytics.backtest.SystematicBias]` | `no` | `—` | `polisyos.ir.analytics.backtest.SystematicBias` |
| `historical_data_ref` | `str | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `model_spec_ref` | `str | NoneType` | `no` | `—` | — |
| `n_metrics_evaluated` | `int` | `no` | `0` | — |
| `n_scenarios` | `int` | `no` | `0` | — |
| `overall_bias_direction` | `polisyos.ir.analytics.backtest.BiasDirection` | `no` | `<BiasDirection.NEUTRAL: 'neutral'>` | `polisyos.ir.analytics.backtest.BiasDirection` |
| `overall_coverage_probability` | `float | NoneType` | `no` | `—` | — |
| `overall_mae` | `float | NoneType` | `no` | `—` | — |
| `overall_mape` | `float | NoneType` | `no` | `—` | — |
| `overall_r_squared` | `float | NoneType` | `no` | `—` | — |
| `overall_rmse` | `float | NoneType` | `no` | `—` | — |
| `policy_spec_ref` | `str | NoneType` | `no` | `—` | — |
| `prediction_mode_effective` | `str | NoneType` | `no` | `—` | — |
| `prediction_mode_requested` | `str | NoneType` | `no` | `—` | — |
| `report_id` | `str` | `yes` | `—` | — |
| `scenarios` | `list[polisyos.ir.analytics.backtest.BacktestScenario]` | `no` | `—` | `polisyos.ir.analytics.backtest.BacktestScenario` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `trust_eligible` | `bool` | `no` | `True` | — |
| `trust_grade` | `str | NoneType` | `no` | `—` | — |
| `trust_score` | `float | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.backtest.BacktestScenario` { #polisyos-ir-analytics-backtest-backtestscenario }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:BacktestScenario`, `polisyos.ir:BacktestScenario`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.backtest.OutcomeComparison`
- Summary: Historical validation scenario with per-metric forecast comparisons.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `coverage_probability` | `float | NoneType` | `no` | `—` | — |
| `data_source` | `str` | `no` | `''` | — |
| `intervention_date` | `str` | `no` | `''` | — |
| `jurisdiction` | `str` | `no` | `''` | — |
| `mae` | `float | NoneType` | `no` | `—` | — |
| `mape` | `float | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `outcome_comparisons` | `list[polisyos.ir.analytics.backtest.OutcomeComparison]` | `no` | `—` | `polisyos.ir.analytics.backtest.OutcomeComparison` |
| `rmse` | `float | NoneType` | `no` | `—` | — |
| `scenario_id` | `str` | `yes` | `—` | — |
| `scenario_label` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.backtest.BiasDirection` { #polisyos-ir-analytics-backtest-biasdirection }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:BiasDirection`, `polisyos.ir:BiasDirection`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Direction of systematic bias detected in historical validation.

| Enum values |
|-------------|
| `optimistic` |
| `pessimistic` |
| `neutral` |
| `mixed` |

### `polisyos.ir.analytics.backtest.OutcomeComparison` { #polisyos-ir-analytics-backtest-outcomecomparison }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:OutcomeComparison`, `polisyos.ir:OutcomeComparison`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Comparison between predicted and observed outcomes for one metric.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `absolute_error` | `float` | `yes` | `—` | — |
| `ci_lower` | `float | NoneType` | `no` | `—` | — |
| `ci_upper` | `float | NoneType` | `no` | `—` | — |
| `metric_name` | `str` | `yes` | `—` | — |
| `relative_error` | `float | NoneType` | `no` | `—` | — |
| `within_ci` | `bool` | `no` | `False` | — |
| `y_pred` | `float` | `yes` | `—` | — |
| `y_true` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.backtest.SystematicBias` { #polisyos-ir-analytics-backtest-systematicbias }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:SystematicBias`, `polisyos.ir:SystematicBias`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.backtest.BiasDirection`
- Summary: Structured bias pattern detected across backtest scenarios.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `affected_metrics` | `list[str]` | `no` | `—` | — |
| `bias_type` | `str` | `yes` | `—` | — |
| `description` | `str` | `no` | `''` | — |
| `direction` | `polisyos.ir.analytics.backtest.BiasDirection` | `yes` | `—` | `polisyos.ir.analytics.backtest.BiasDirection` |
| `magnitude` | `float` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `p_value` | `float | NoneType` | `no` | `—` | — |
| `statistical_test` | `str` | `no` | `''` | — |

### `polisyos.ir.analytics.calibration.CalibrationConfig` { #polisyos-ir-analytics-calibration-calibrationconfig }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `0.1`
- Exported from: `polisyos.ir:CalibrationConfig`
- ABI snapshot: `calibration_config` / `schemas/snapshots/ir/calibration_config.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.calibration.CalibrationTarget`, `polisyos.ir.analytics.calibration.ConstraintLossConfig`, `polisyos.ir.analytics.calibration.FidelityConfig`, `polisyos.ir.analytics.calibration.GradNormConfig`, `polisyos.ir.analytics.calibration.HessianConfig`, `polisyos.ir.analytics.calibration.MultiStartConfig`, `polisyos.ir.analytics.calibration.PriorLossConfig`, `polisyos.ir.analytics.calibration.TrainableParamRef`
- Summary: Configure a full calibration run over targets, trainables, and penalties.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `clip_grad_norm` | `float | NoneType` | `no` | `—` | — |
| `constraint_loss` | `polisyos.ir.analytics.calibration.ConstraintLossConfig` | `no` | `—` | `polisyos.ir.analytics.calibration.ConstraintLossConfig` |
| `constraint_values` | `dict[str, float] | NoneType` | `no` | `—` | — |
| `early_stop_min_delta` | `float` | `no` | `0.0` | — |
| `early_stop_min_steps` | `int` | `no` | `0` | — |
| `early_stop_patience` | `int` | `no` | `0` | — |
| `fidelity` | `polisyos.ir.analytics.calibration.FidelityConfig` | `no` | `—` | `polisyos.ir.analytics.calibration.FidelityConfig` |
| `grad_norm` | `polisyos.ir.analytics.calibration.GradNormConfig` | `no` | `—` | `polisyos.ir.analytics.calibration.GradNormConfig` |
| `hessian` | `polisyos.ir.analytics.calibration.HessianConfig` | `no` | `—` | `polisyos.ir.analytics.calibration.HessianConfig` |
| `learning_rate` | `float` | `no` | `0.01` | — |
| `literature_priors` | `dict[str, dict[str, Any]] | NoneType` | `no` | `—` | — |
| `max_steps` | `int` | `no` | `200` | — |
| `multi_start` | `polisyos.ir.analytics.calibration.MultiStartConfig | NoneType` | `no` | `—` | `polisyos.ir.analytics.calibration.MultiStartConfig` |
| `prior_loss` | `polisyos.ir.analytics.calibration.PriorLossConfig` | `no` | `—` | `polisyos.ir.analytics.calibration.PriorLossConfig` |
| `schema_version` | `str` | `no` | `'0.1'` | — |
| `seed` | `int` | `no` | `0` | — |
| `seed_strategy` | `str` | `no` | `'fixed'` | — |
| `steps` | `int | NoneType` | `no` | `—` | — |
| `targets` | `list[polisyos.ir.analytics.calibration.CalibrationTarget]` | `no` | `—` | `polisyos.ir.analytics.calibration.CalibrationTarget` |
| `time_axis` | `list[float] | NoneType` | `no` | `—` | — |
| `trainables` | `list[polisyos.ir.analytics.calibration.TrainableParamRef]` | `no` | `—` | `polisyos.ir.analytics.calibration.TrainableParamRef` |

### `polisyos.ir.analytics.calibration.CalibrationTarget` { #polisyos-ir-analytics-calibration-calibrationtarget }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:CalibrationTarget`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.calibration.TargetAlignConfig`, `polisyos.ir.analytics.calibration.TargetLossConfig`
- Summary: Bind one observed Fabric series to the simulation metric being calibrated.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `aggregation` | `str` | `no` | `'none'` | — |
| `align` | `polisyos.ir.analytics.calibration.TargetAlignConfig` | `no` | `—` | `polisyos.ir.analytics.calibration.TargetAlignConfig` |
| `fabric_metric` | `str | NoneType` | `no` | `—` | — |
| `fabric_query` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `loss` | `polisyos.ir.analytics.calibration.TargetLossConfig` | `no` | `—` | `polisyos.ir.analytics.calibration.TargetLossConfig` |
| `model_metric_path` | `str` | `yes` | `—` | — |
| `target_id` | `str` | `yes` | `—` | — |
| `trainables` | `List['TrainableParamRef']` | `no` | `—` | — |

### `polisyos.ir.analytics.calibration.ConstraintLossConfig` { #polisyos-ir-analytics-calibration-constraintlossconfig }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Настройки штрафов по ограничениям.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `constraint_ids` | `list[str]` | `no` | `—` | — |
| `enabled` | `bool` | `no` | `False` | — |
| `epsilon` | `float` | `no` | `1e-08` | — |
| `mode` | `str` | `no` | `'trajectory'` | — |
| `reduction` | `str` | `no` | `'mean'` | — |
| `weight` | `float` | `no` | `1.0` | — |

### `polisyos.ir.analytics.calibration.FidelityConfig` { #polisyos-ir-analytics-calibration-fidelityconfig }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Настройки режима исполнения для калибрации.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `force_override` | `bool` | `no` | `True` | — |
| `mode` | `str` | `no` | `'relaxed'` | — |
| `temperature` | `float` | `no` | `1.0` | — |

### `polisyos.ir.analytics.calibration.GradNormConfig` { #polisyos-ir-analytics-calibration-gradnormconfig }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Настройки GradNorm (выравнивание норм градиентов по таргетам).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `alpha` | `float` | `no` | `1.0` | — |
| `enabled` | `bool` | `no` | `False` | — |
| `epsilon` | `float` | `no` | `1e-08` | — |
| `lr` | `float` | `no` | `0.1` | — |
| `max_weight` | `float` | `no` | `10.0` | — |
| `min_weight` | `float` | `no` | `0.1` | — |
| `update_every` | `int` | `no` | `1` | — |

### `polisyos.ir.analytics.calibration.HessianConfig` { #polisyos-ir-analytics-calibration-hessianconfig }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Настройки оценки неопределённости через Hessian.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `condition_warn` | `float` | `no` | `100000000.0` | — |
| `damping` | `float` | `no` | `1e-06` | — |
| `enabled` | `bool` | `no` | `True` | — |
| `max_params` | `int | NoneType` | `no` | `—` | — |
| `rank_tol` | `float` | `no` | `1e-06` | — |
| `std_warn` | `float` | `no` | `1000000.0` | — |

### `polisyos.ir.analytics.calibration.MultiStartConfig` { #polisyos-ir-analytics-calibration-multistartconfig }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Configuration for multi-start optimization.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `condition_threshold` | `float` | `no` | `100000000.0` | — |
| `n_starts` | `int` | `no` | `5` | — |
| `perturbation_scale` | `float` | `no` | `0.1` | — |
| `selection` | `str` | `no` | `'best_loss'` | — |

### `polisyos.ir.analytics.calibration.PriorLossConfig` { #polisyos-ir-analytics-calibration-priorlossconfig }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Настройки Gaussian priors по trainable параметрам.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `enabled` | `bool` | `no` | `False` | — |
| `epsilon` | `float` | `no` | `1e-08` | — |
| `weight` | `float` | `no` | `1.0` | — |

### `polisyos.ir.analytics.calibration.TargetAlignConfig` { #polisyos-ir-analytics-calibration-targetalignconfig }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.types.TimeFrequency`
- Summary: Настройки выравнивания исторического ряда под шаг симуляции.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `fill_value` | `float | NoneType` | `no` | `—` | — |
| `frequency` | `polisyos.ir.types.TimeFrequency | NoneType` | `no` | `—` | `polisyos.ir.types.TimeFrequency` |
| `method` | `str` | `no` | `'linear'` | — |
| `steps` | `int | NoneType` | `no` | `—` | — |
| `time_column` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.calibration.TargetLossConfig` { #polisyos-ir-analytics-calibration-targetlossconfig }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Параметры расчёта ошибки по таргету.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `epsilon` | `float` | `no` | `1e-08` | — |
| `kind` | `str` | `no` | `'mse'` | — |
| `relative` | `bool` | `no` | `True` | — |
| `scale` | `str` | `no` | `'mean_abs'` | — |
| `weight` | `float` | `no` | `1.0` | — |

### `polisyos.ir.analytics.calibration.TrainableParamRef` { #polisyos-ir-analytics-calibration-trainableparamref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Ссылка на параметр механизма, который нужно калибровать.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `mechanism_type` | `str | NoneType` | `no` | `—` | — |
| `node_id` | `str | NoneType` | `no` | `—` | — |
| `param_id` | `str` | `yes` | `—` | — |
| `selector` | `Any | NoneType` | `no` | `—` | — |
| `tie_id` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.causal.CausalEffectReport` { #polisyos-ir-analytics-causal-causaleffectreport }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:CausalEffectReport`, `polisyos.ir:CausalEffectReport`
- ABI snapshot: `causal_effect_report` / `schemas/snapshots/ir/causal_effect_report.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal.CausalMethod`, `polisyos.ir.analytics.causal.DiagnosticTest`, `polisyos.ir.analytics.causal.EstimationStatus`, `polisyos.ir.analytics.causal.PlaceboResult`, `polisyos.ir.analytics.causal.RefutationResult`, `polisyos.ir.analytics.transportability.TransportabilityResult`
- Summary: Canonical causal effect artifact emitted by Foundry methods.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `assumptions` | `dict[str, str]` | `no` | `—` | — |
| `confidence_interval` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `confidence_level` | `float | NoneType` | `no` | `0.95` | — |
| `diagnostics` | `list[polisyos.ir.analytics.causal.DiagnosticTest]` | `no` | `—` | `polisyos.ir.analytics.causal.DiagnosticTest` |
| `effect_size_cohen_d` | `float | NoneType` | `no` | `—` | — |
| `estimand` | `str` | `yes` | `—` | — |
| `estimand_type` | `str | NoneType` | `no` | `—` | — |
| `graph_ref` | `str | NoneType` | `no` | `—` | — |
| `identified_estimand` | `str | NoneType` | `no` | `—` | — |
| `inference_method` | `str` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `method` | `polisyos.ir.analytics.causal.CausalMethod` | `yes` | `—` | `polisyos.ir.analytics.causal.CausalMethod` |
| `method_params` | `dict[str, Any]` | `no` | `—` | — |
| `n_bootstrap_samples` | `int | NoneType` | `no` | `—` | — |
| `n_control` | `int` | `yes` | `—` | — |
| `n_treated` | `int` | `yes` | `—` | — |
| `p_value` | `float | NoneType` | `no` | `—` | — |
| `placebo_p_value` | `float | NoneType` | `no` | `—` | — |
| `placebo_results` | `list[polisyos.ir.analytics.causal.PlaceboResult]` | `no` | `—` | `polisyos.ir.analytics.causal.PlaceboResult` |
| `point_estimate` | `float | NoneType` | `no` | `—` | — |
| `post_periods` | `int` | `yes` | `—` | — |
| `pre_periods` | `int` | `yes` | `—` | — |
| `pre_treatment_fit` | `dict[str, float]` | `no` | `—` | — |
| `refutation_results` | `list[polisyos.ir.analytics.causal.RefutationResult]` | `no` | `—` | `polisyos.ir.analytics.causal.RefutationResult` |
| `sample_size` | `int` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `standard_error` | `float | NoneType` | `no` | `—` | — |
| `status` | `polisyos.ir.analytics.causal.EstimationStatus` | `no` | `<EstimationStatus.SUCCESS: 'success'>` | `polisyos.ir.analytics.causal.EstimationStatus` |
| `status_reason` | `str | NoneType` | `no` | `—` | — |
| `sutva_assumed` | `bool` | `no` | `True` | — |
| `sutva_violation_risk` | `Literal[high, medium, low] | NoneType` | `no` | `—` | — |
| `time_effects` | `dict[str, list[float]]` | `no` | `—` | — |
| `transport_result` | `polisyos.ir.analytics.transportability.TransportabilityResult | NoneType` | `no` | `—` | `polisyos.ir.analytics.transportability.TransportabilityResult` |

### `polisyos.ir.analytics.causal.CausalMethod` { #polisyos-ir-analytics-causal-causalmethod }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:CausalMethod`, `polisyos.ir:CausalMethod`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Declare which estimator family produced a ``CausalEffectReport``.

| Enum values |
|-------------|
| `synthetic_control` |
| `difference_in_differences` |
| `regression_discontinuity` |
| `structural_time_series` |
| `dowhy_backdoor` |
| `dowhy_iv` |
| `dowhy_frontdoor` |
| `proximal_bridge` |
| `distributional_treatment_effect` |
| `interference_cate` |
| `causal_forest` |
| `forest_dr` |
| `causal_bcf` |
| `double_ml` |
| `s_learner` |
| `t_learner` |
| `x_learner` |
| `policy_tree` |
| `g_computation` |
| `ice_g_formula` |
| `ltmle` |
| `g_estimation` |
| `q_learning_dtr` |
| `a_learning_dtr` |
| `outcome_weighted_learning` |
| `doubly_robust_dtr` |
| `off_policy_evaluation` |
| `causal_bandit` |

### `polisyos.ir.analytics.causal.DataReadinessReport` { #polisyos-ir-analytics-causal-datareadinessreport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal.PositivityDiagnosticReport`
- Summary: Canonical pre-estimation readiness gate for causal execution.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `blocking_reasons` | `list[str]` | `no` | `—` | — |
| `can_compile_estimation` | `bool` | `yes` | `—` | — |
| `can_run_estimation` | `bool` | `yes` | `—` | — |
| `decision` | `Literal[pass, warn, block, unknown]` | `yes` | `—` | — |
| `fallback_data_available` | `bool` | `no` | `False` | — |
| `measurement_quality` | `Literal[known_good, proxy_only, unknown]` | `no` | `'unknown'` | — |
| `metrics` | `dict[str, float]` | `no` | `—` | — |
| `positivity` | `polisyos.ir.analytics.causal.PositivityDiagnosticReport | NoneType` | `no` | `—` | `polisyos.ir.analytics.causal.PositivityDiagnosticReport` |
| `sample_size` | `int | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `support_mismatch` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.causal.DiagnosticTest` { #polisyos-ir-analytics-causal-diagnostictest }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:DiagnosticTest`, `polisyos.ir:DiagnosticTest`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Named diagnostic emitted alongside a causal estimate.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `details` | `dict[str, Any]` | `no` | `—` | — |
| `p_value` | `float | NoneType` | `no` | `—` | — |
| `passed` | `bool` | `yes` | `—` | — |
| `statistic` | `float | NoneType` | `no` | `—` | — |
| `test_name` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.causal.EstimationStatus` { #polisyos-ir-analytics-causal-estimationstatus }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:EstimationStatus`, `polisyos.ir:EstimationStatus`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Report whether a causal run produced decision-grade output or failed a gate.

| Enum values |
|-------------|
| `success` |
| `input_invalid` |
| `assumption_failed` |
| `numerical_failure` |

### `polisyos.ir.analytics.causal.PlaceboResult` { #polisyos-ir-analytics-causal-placeboresult }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:PlaceboResult`, `polisyos.ir:PlaceboResult`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Per-unit placebo diagnostic for synthetic-control style methods.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `effect_estimate` | `float` | `yes` | `—` | — |
| `rmspe_post` | `float | NoneType` | `no` | `—` | — |
| `rmspe_pre` | `float | NoneType` | `no` | `—` | — |
| `rmspe_ratio` | `float | NoneType` | `no` | `—` | — |
| `unit_id` | `str | int` | `yes` | `—` | — |

### `polisyos.ir.analytics.causal.PositivityDiagnosticReport` { #polisyos-ir-analytics-causal-positivitydiagnosticreport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.SideConditionKind`
- Summary: Positivity / overlap diagnostic result for causal identification governance.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `effective_sample_size` | `float` | `yes` | `—` | — |
| `ess_fraction` | `float` | `yes` | `—` | — |
| `max_propensity_observed` | `float` | `yes` | `—` | — |
| `min_propensity_observed` | `float` | `yes` | `—` | — |
| `n_obs` | `int` | `yes` | `—` | — |
| `n_trimmed` | `int` | `no` | `0` | — |
| `overlap_score` | `float` | `yes` | `—` | — |
| `passes_positivity` | `bool` | `yes` | `—` | — |
| `recommendations` | `list[str]` | `no` | `—` | — |
| `side_conditions_violated` | `list[polisyos.ir.analytics.estimand.SideConditionKind]` | `no` | `—` | `polisyos.ir.analytics.estimand.SideConditionKind` |

### `polisyos.ir.analytics.causal.ProofBundle` { #polisyos-ir-analytics-causal-proofbundle }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Canonical public proof artifact for causal identification.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `assumptions` | `list[str]` | `no` | `—` | — |
| `completeness_regime` | `Literal[complete, sound_incomplete, heuristic_backed]` | `yes` | `—` | — |
| `estimand_ast` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `graph_ref` | `str | NoneType` | `no` | `—` | — |
| `implementation_coverage` | `str` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `negative_certificate_summary` | `str | NoneType` | `no` | `—` | — |
| `proof_status` | `Literal[identified, non_identified, oracle_needed]` | `yes` | `—` | — |
| `proof_stratum` | `Literal[A0_trusted, A1_extended, A2_oracle_backed]` | `yes` | `—` | — |
| `proof_trace` | `list[str]` | `no` | `—` | — |
| `query_ref` | `str | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `theorem_family` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.causal.RefutationResult` { #polisyos-ir-analytics-causal-refutationresult }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:RefutationResult`, `polisyos.ir:RefutationResult`
- ABI snapshot: `refutation_result` / `schemas/snapshots/ir/refutation_result.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal.RefutationTestType`
- Summary: Outcome of a single causal refutation or robustness check.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `details` | `dict[str, Any]` | `no` | `—` | — |
| `effect_ratio` | `float` | `yes` | `—` | — |
| `original_estimate` | `float` | `yes` | `—` | — |
| `p_value` | `float | NoneType` | `no` | `—` | — |
| `passed` | `bool` | `yes` | `—` | — |
| `refuted_estimate` | `float` | `yes` | `—` | — |
| `test_type` | `polisyos.ir.analytics.causal.RefutationTestType` | `yes` | `—` | `polisyos.ir.analytics.causal.RefutationTestType` |

### `polisyos.ir.analytics.causal.RefutationTestType` { #polisyos-ir-analytics-causal-refutationtesttype }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:RefutationTestType`, `polisyos.ir:RefutationTestType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Identify which robustness/refutation check generated a diagnostic result.

| Enum values |
|-------------|
| `placebo_treatment` |
| `random_common_cause` |
| `data_subset` |
| `bootstrap` |
| `unobserved_common_cause` |

### `polisyos.ir.analytics.causal_capabilities.CausalBackendCapability` { #polisyos-ir-analytics-causal-capabilities-causalbackendcapability }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_capabilities.CausalBackendId`, `polisyos.ir.analytics.causal_capabilities.CausalIdentificationFamily`
- Summary: Causal backend capability public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `available` | `bool` | `no` | `True` | — |
| `backend_id` | `polisyos.ir.analytics.causal_capabilities.CausalBackendId` | `yes` | `—` | `polisyos.ir.analytics.causal_capabilities.CausalBackendId` |
| `disabled_reason` | `str | NoneType` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `supported_families` | `list[polisyos.ir.analytics.causal_capabilities.CausalIdentificationFamily]` | `no` | `—` | `polisyos.ir.analytics.causal_capabilities.CausalIdentificationFamily` |

### `polisyos.ir.analytics.causal_capabilities.CausalBackendId` { #polisyos-ir-analytics-causal-capabilities-causalbackendid }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Causal backend ID public type.

| Enum values |
|-------------|
| `y0` |
| `r_causaleffect` |
| `simplified_legacy` |
| `bounds_only` |

### `polisyos.ir.analytics.causal_capabilities.CausalCapabilityContract` { #polisyos-ir-analytics-causal-capabilities-causalcapabilitycontract }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_capabilities.CausalBackendCapability`, `polisyos.ir.analytics.causal_capabilities.CausalBackendId`, `polisyos.ir.analytics.causal_capabilities.CausalIdentificationFamily`
- Summary: Causal capability contract data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `backends` | `list[polisyos.ir.analytics.causal_capabilities.CausalBackendCapability]` | `no` | `—` | `polisyos.ir.analytics.causal_capabilities.CausalBackendCapability` |
| `degradation_policy` | `str` | `no` | `'full_then_bounds_explicit_simplified'` | — |
| `dependency_fingerprint` | `str` | `yes` | `—` | — |
| `disabled_families` | `dict[str, str]` | `no` | `—` | — |
| `full_backend_order` | `list[polisyos.ir.analytics.causal_capabilities.CausalBackendId]` | `no` | `—` | `polisyos.ir.analytics.causal_capabilities.CausalBackendId` |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `supported_families` | `list[polisyos.ir.analytics.causal_capabilities.CausalIdentificationFamily]` | `no` | `—` | `polisyos.ir.analytics.causal_capabilities.CausalIdentificationFamily` |

### `polisyos.ir.analytics.causal_capabilities.CausalIdentificationFamily` { #polisyos-ir-analytics-causal-capabilities-causalidentificationfamily }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Causal identification family public type.

| Enum values |
|-------------|
| `direct` |
| `frontdoor` |
| `do_calculus_rule2` |
| `do_calculus_rule3` |
| `c_component_factorization` |
| `bounds_manski` |

### `polisyos.ir.analytics.causal_discovery.AlgebraicBlockSpec` { #polisyos-ir-analytics-causal-discovery-algebraicblockspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintFamily`
- Summary: Declare one variable block whose implied algebraic constraints should be tested.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `block_id` | `str` | `yes` | `—` | — |
| `expected_rank` | `int | NoneType` | `no` | `—` | — |
| `family` | `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintFamily` | `yes` | `—` | `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintFamily` |
| `max_residual_energy` | `float | NoneType` | `no` | `—` | — |
| `quadruples` | `tuple[tuple[str, str, str, str]]` | `no` | `()` | — |
| `variables` | `tuple[str]` | `yes` | `—` | — |

### `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintFamily` { #polisyos-ir-analytics-causal-discovery-algebraicconstraintfamily }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Select the family of algebraic test implied by a graph or latent-factor block.

| Enum values |
|-------------|
| `ci` |
| `tetrad` |
| `overcomplete` |

### `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintReport` { #polisyos-ir-analytics-causal-discovery-algebraicconstraintreport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintFamily`, `polisyos.ir.analytics.causal_discovery.ConstraintEvaluationResult`, `polisyos.ir.analytics.causal_discovery.ImpliedConstraintSpec`, `polisyos.ir.refs.ArtifactRefModel`
- Summary: Summarize implied/violated algebraic constraints and suggested graph repairs.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `families_run` | `list[polisyos.ir.analytics.causal_discovery.AlgebraicConstraintFamily]` | `no` | `—` | `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintFamily` |
| `implied_constraints_preview` | `list[polisyos.ir.analytics.causal_discovery.ImpliedConstraintSpec]` | `no` | `—` | `polisyos.ir.analytics.causal_discovery.ImpliedConstraintSpec` |
| `implied_constraints_ref` | `polisyos.ir.refs.ArtifactRefModel | NoneType` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `n_implied_constraints` | `int` | `no` | `0` | — |
| `n_violated_constraints` | `int` | `no` | `0` | — |
| `severity` | `Literal[info, warning, blocker]` | `no` | `'info'` | — |
| `suggested_repairs` | `list[str]` | `no` | `—` | — |
| `tested_by_family` | `dict[str, int]` | `no` | `—` | — |
| `violated_by_family` | `dict[str, int]` | `no` | `—` | — |
| `violated_constraints_preview` | `list[polisyos.ir.analytics.causal_discovery.ConstraintEvaluationResult]` | `no` | `—` | `polisyos.ir.analytics.causal_discovery.ConstraintEvaluationResult` |
| `violated_constraints_ref` | `polisyos.ir.refs.ArtifactRefModel | NoneType` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.causal_discovery.CausalDiscoveryReport` { #polisyos-ir-analytics-causal-discovery-causaldiscoveryreport }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:CausalDiscoveryReport`, `polisyos.ir:CausalDiscoveryReport`
- ABI snapshot: `causal_discovery_report` / `schemas/snapshots/ir/causal_discovery_report.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintReport`, `polisyos.ir.analytics.causal_discovery.LatentDiscoveryBundle`, `polisyos.ir.analytics.causal_graph.CausalGraphModel`
- Summary: Output of a causal-discovery run, including optional latent diagnostics.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `algebraic_constraints` | `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintReport | NoneType` | `no` | `—` | `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintReport` |
| `bootstrap_stability` | `dict[str, float]` | `no` | `—` | — |
| `computation_time_seconds` | `float` | `no` | `0.0` | — |
| `graph` | `polisyos.ir.analytics.causal_graph.CausalGraphModel` | `yes` | `—` | `polisyos.ir.analytics.causal_graph.CausalGraphModel` |
| `latent_discovery` | `polisyos.ir.analytics.causal_discovery.LatentDiscoveryBundle | NoneType` | `no` | `—` | `polisyos.ir.analytics.causal_discovery.LatentDiscoveryBundle` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `method` | `str` | `yes` | `—` | — |
| `n_bootstrap` | `int` | `no` | `0` | — |
| `resolved_graph` | `polisyos.ir.analytics.causal_graph.CausalGraphModel | NoneType` | `no` | `—` | `polisyos.ir.analytics.causal_graph.CausalGraphModel` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `significance_level` | `float` | `no` | `0.05` | — |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.causal_discovery.ConstraintEvaluationResult` { #polisyos-ir-analytics-causal-discovery-constraintevaluationresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintFamily`
- Summary: Store the test outcome for one implied or user-declared algebraic constraint.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `adjusted_p_value` | `float | NoneType` | `no` | `—` | — |
| `constraint_id` | `str` | `yes` | `—` | — |
| `family` | `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintFamily` | `yes` | `—` | `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintFamily` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `p_value` | `float | NoneType` | `no` | `—` | — |
| `severity` | `Literal[info, warning, blocker]` | `no` | `'info'` | — |
| `statistic` | `float | NoneType` | `no` | `—` | — |
| `status` | `Literal[passed, violated, skipped, error, unsupported]` | `yes` | `—` | — |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.causal_discovery.DataCharacteristics` { #polisyos-ir-analytics-causal-discovery-datacharacteristics }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_discovery.DataType`, `polisyos.ir.analytics.causal_discovery.DimensionRegime`
- Summary: Summarize discovery dataset shape, stationarity, and latent-confounding risk.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `data_type` | `polisyos.ir.analytics.causal_discovery.DataType` | `yes` | `—` | `polisyos.ir.analytics.causal_discovery.DataType` |
| `dimension_regime` | `polisyos.ir.analytics.causal_discovery.DimensionRegime` | `yes` | `—` | `polisyos.ir.analytics.causal_discovery.DimensionRegime` |
| `estimated_density` | `float` | `yes` | `—` | — |
| `has_mixed_types` | `bool` | `yes` | `—` | — |
| `is_stationary` | `bool | NoneType` | `no` | `—` | — |
| `max_lag` | `int | NoneType` | `no` | `—` | — |
| `n_samples` | `int` | `yes` | `—` | — |
| `n_variables` | `int` | `yes` | `—` | — |
| `suspected_latent_confounders` | `bool` | `yes` | `—` | — |

### `polisyos.ir.analytics.causal_discovery.DataType` { #polisyos-ir-analytics-causal-discovery-datatype }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Classify whether discovery inputs are cross-sectional or time-series.

| Enum values |
|-------------|
| `cross_sectional` |
| `time_series` |

### `polisyos.ir.analytics.causal_discovery.DimensionRegime` { #polisyos-ir-analytics-causal-discovery-dimensionregime }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Bucket discovery inputs by variable-count regime for algorithm selection.

| Enum values |
|-------------|
| `low_dim` |
| `med_dim` |
| `high_dim` |

### `polisyos.ir.analytics.causal_discovery.DiscoveryPipelineReport` { #polisyos-ir-analytics-causal-discovery-discoverypipelinereport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_discovery.CausalDiscoveryReport`, `polisyos.ir.analytics.causal_discovery.DataCharacteristics`, `polisyos.ir.analytics.causal_discovery.EdgeAgreement`, `polisyos.ir.analytics.causal_graph.CausalGraphModel`
- Summary: Aggregate discovery results, consensus PAG output, and algorithm agreement metrics.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `algorithm_weights` | `dict[str, float]` | `yes` | `—` | — |
| `computation_time_seconds` | `float` | `no` | `0.0` | — |
| `data_characteristics` | `polisyos.ir.analytics.causal_discovery.DataCharacteristics` | `yes` | `—` | `polisyos.ir.analytics.causal_discovery.DataCharacteristics` |
| `edge_agreements` | `list[polisyos.ir.analytics.causal_discovery.EdgeAgreement]` | `yes` | `—` | `polisyos.ir.analytics.causal_discovery.EdgeAgreement` |
| `individual_results` | `list[polisyos.ir.analytics.causal_discovery.CausalDiscoveryReport]` | `yes` | `—` | `polisyos.ir.analytics.causal_discovery.CausalDiscoveryReport` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `n_algorithms_run` | `int` | `yes` | `—` | — |
| `pag_validity_violations` | `list[str]` | `no` | `—` | — |
| `skeleton_agreement` | `dict[str, float]` | `no` | `—` | — |
| `temporal_dag` | `polisyos.ir.analytics.causal_graph.CausalGraphModel | NoneType` | `no` | `—` | `polisyos.ir.analytics.causal_graph.CausalGraphModel` |
| `unified_pag` | `polisyos.ir.analytics.causal_graph.CausalGraphModel` | `yes` | `—` | `polisyos.ir.analytics.causal_graph.CausalGraphModel` |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.causal_discovery.EdgeAgreement` { #polisyos-ir-analytics-causal-discovery-edgeagreement }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Summarize bootstrap or multi-algorithm agreement for one candidate edge.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `contributing_algorithms` | `list[str]` | `yes` | `—` | — |
| `edge_key` | `str` | `yes` | `—` | — |
| `mark_dst` | `str` | `yes` | `—` | — |
| `mark_src` | `str` | `yes` | `—` | — |
| `orientation_confidence` | `float` | `yes` | `—` | — |
| `presence_score` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.causal_discovery.ImpliedConstraintSpec` { #polisyos-ir-analytics-causal-discovery-impliedconstraintspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintFamily`
- Summary: Represent one graph-implied constraint and its optional conditioning set.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `conditioning_set` | `tuple[str]` | `no` | `()` | — |
| `constraint_id` | `str` | `yes` | `—` | — |
| `family` | `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintFamily` | `yes` | `—` | `polisyos.ir.analytics.causal_discovery.AlgebraicConstraintFamily` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `source_block_id` | `str | NoneType` | `no` | `—` | — |
| `statement` | `str` | `yes` | `—` | — |
| `variables` | `tuple[str]` | `yes` | `—` | — |

### `polisyos.ir.analytics.causal_discovery.LatentAssumptionCard` { #polisyos-ir-analytics-causal-discovery-latentassumptioncard }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Document one latent-variable assumption and its falsification hook.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `assumption_id` | `str` | `yes` | `—` | — |
| `description` | `str` | `yes` | `—` | — |
| `evidence_basis` | `list[str]` | `no` | `—` | — |
| `falsification_hook` | `str | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `title` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.causal_discovery.LatentDiscoveryBundle` { #polisyos-ir-analytics-causal-discovery-latentdiscoverybundle }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_discovery.LatentAssumptionCard`, `polisyos.ir.analytics.causal_discovery.LatentTrustLevel`
- Summary: Disclose proposed latent nodes, test hooks, and promotion limits.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `assumption_cards` | `list[polisyos.ir.analytics.causal_discovery.LatentAssumptionCard]` | `no` | `—` | `polisyos.ir.analytics.causal_discovery.LatentAssumptionCard` |
| `falsification_tests` | `list[str]` | `no` | `—` | — |
| `human_gate_required` | `bool` | `no` | `True` | — |
| `identification_conditions` | `list[str]` | `no` | `—` | — |
| `inducing_environments` | `list[str]` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `no_promotion_reasons` | `list[str]` | `no` | `—` | — |
| `not_for_decision_support` | `bool` | `no` | `True` | — |
| `promotion_allowed` | `bool` | `no` | `False` | — |
| `proposed_latent_nodes` | `list[str]` | `no` | `—` | — |
| `readiness_cap` | `Literal[proof_only]` | `no` | `'proof_only'` | — |
| `trust_level` | `polisyos.ir.analytics.causal_discovery.LatentTrustLevel` | `no` | `<LatentTrustLevel.RESEARCH: 'research'>` | `polisyos.ir.analytics.causal_discovery.LatentTrustLevel` |

### `polisyos.ir.analytics.causal_discovery.LatentTrustLevel` { #polisyos-ir-analytics-causal-discovery-latenttrustlevel }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Declare whether a proposed latent structure is research-only, conditional, or validated.

| Enum values |
|-------------|
| `research` |
| `conditional` |
| `validated` |

### `polisyos.ir.analytics.causal_ensemble.CausalModelEnsemble` { #polisyos-ir-analytics-causal-ensemble-causalmodelensemble }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:CausalModelEnsemble`, `polisyos.ir:CausalModelEnsemble`
- ABI snapshot: `causal_model_ensemble` / `schemas/snapshots/ir/causal_model_ensemble.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_ensemble.EnsembleMember`
- Summary: Ensemble of causal models capturing structural uncertainty.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `consensus_graph_ref` | `str | NoneType` | `no` | `—` | — |
| `edge_inclusion_frequency` | `dict[str, float]` | `no` | `—` | — |
| `members` | `list[polisyos.ir.analytics.causal_ensemble.EnsembleMember]` | `yes` | `—` | `polisyos.ir.analytics.causal_ensemble.EnsembleMember` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.analytics.causal_ensemble.EnsembleMember` { #polisyos-ir-analytics-causal-ensemble-ensemblemember }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:EnsembleMember`, `polisyos.ir:EnsembleMember`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: One graph candidate inside a structural-uncertainty ensemble.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bootstrap_stability` | `float` | `yes` | `—` | — |
| `discovery_method` | `str` | `yes` | `—` | — |
| `graph_ref` | `str` | `yes` | `—` | — |
| `weight` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.causal_graph.CausalEdge` { #polisyos-ir-analytics-causal-graph-causaledge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:CausalEdge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_graph.EdgeMark`, `polisyos.ir.analytics.causal_graph.EdgeSource`
- Summary: Causal edge public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `combined_confidence` | `float | NoneType` | `no` | `—` | — |
| `data_confidence` | `float | NoneType` | `no` | `—` | — |
| `dst` | `str` | `yes` | `—` | — |
| `evidence_refs` | `list[str]` | `no` | `—` | — |
| `expert_confidence` | `float | NoneType` | `no` | `—` | — |
| `lag` | `int | NoneType` | `no` | `—` | — |
| `literature_confidence` | `float | NoneType` | `no` | `—` | — |
| `llm_confidence` | `float | NoneType` | `no` | `—` | — |
| `mark_dst` | `polisyos.ir.analytics.causal_graph.EdgeMark` | `no` | `<EdgeMark.ARROW: 'arrow'>` | `polisyos.ir.analytics.causal_graph.EdgeMark` |
| `mark_src` | `polisyos.ir.analytics.causal_graph.EdgeMark` | `no` | `<EdgeMark.TAIL: 'tail'>` | `polisyos.ir.analytics.causal_graph.EdgeMark` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `p_value` | `float | NoneType` | `no` | `—` | — |
| `simulation_confidence` | `float | NoneType` | `no` | `—` | — |
| `sources` | `list[polisyos.ir.analytics.causal_graph.EdgeSource]` | `no` | `—` | `polisyos.ir.analytics.causal_graph.EdgeSource` |
| `src` | `str` | `yes` | `—` | — |
| `unsupported_by_evidence` | `bool` | `no` | `False` | — |

### `polisyos.ir.analytics.causal_graph.CausalGraphModel` { #polisyos-ir-analytics-causal-graph-causalgraphmodel }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:CausalGraphModel`
- ABI snapshot: `causal_graph_model` / `schemas/snapshots/ir/causal_graph_model.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_graph.CausalEdge`, `polisyos.ir.analytics.causal_graph.GraphType`, `polisyos.ir.analytics.causal_graph.PAGIdentificationPolicy`
- Summary: DAG / CPDAG / PAG / MGRAPH / ADMG causal graph IR contract.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `discovery_method` | `str` | `no` | `''` | — |
| `edges` | `list[polisyos.ir.analytics.causal_graph.CausalEdge]` | `yes` | `—` | `polisyos.ir.analytics.causal_graph.CausalEdge` |
| `graph_type` | `polisyos.ir.analytics.causal_graph.GraphType` | `yes` | `—` | `polisyos.ir.analytics.causal_graph.GraphType` |
| `id_confidence_under_pag` | `float | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `nodes` | `list[str]` | `yes` | `—` | — |
| `pag_identification_policy` | `polisyos.ir.analytics.causal_graph.PAGIdentificationPolicy` | `no` | `<PAGIdentificationPolicy.CONSERVATIVE: 'conservative'>` | `polisyos.ir.analytics.causal_graph.PAGIdentificationPolicy` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `skg_version_id` | `int | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.causal_graph.EdgeMark` { #polisyos-ir-analytics-causal-graph-edgemark }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:EdgeMark`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Edge mark public type.

| Enum values |
|-------------|
| `tail` |
| `arrow` |
| `circle` |

### `polisyos.ir.analytics.causal_graph.EdgeSource` { #polisyos-ir-analytics-causal-graph-edgesource }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:EdgeSource`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Edge source public type.

| Enum values |
|-------------|
| `data` |
| `literature` |
| `llm_prior` |
| `expert` |
| `simulation` |

### `polisyos.ir.analytics.causal_graph.GraphType` { #polisyos-ir-analytics-causal-graph-graphtype }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:GraphType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Graph type public type.

| Enum values |
|-------------|
| `dag` |
| `cpdag` |
| `pag` |
| `mgraph` |
| `admg` |

### `polisyos.ir.analytics.causal_graph.PAGIdentificationPolicy` { #polisyos-ir-analytics-causal-graph-pagidentificationpolicy }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:PAGIdentificationPolicy`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: PAG identification policy data model.

| Enum values |
|-------------|
| `conservative` |
| `optimistic` |
| `probabilistic` |

### `polisyos.ir.analytics.causal_graph_kuzu.CausalGraphKuzuError` { #polisyos-ir-analytics-causal-graph-kuzu-causalgraphkuzuerror }

- Kind: `class`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Base error for causal graph Kuzu materialization.

### `polisyos.ir.analytics.causal_graph_kuzu.CausalGraphKuzuNotAvailableError` { #polisyos-ir-analytics-causal-graph-kuzu-causalgraphkuzunotavailableerror }

- Kind: `class`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Raised when optional dependency `kuzu` is not available.

### `polisyos.ir.analytics.causal_graph_kuzu.CausalGraphKuzuSchemaError` { #polisyos-ir-analytics-causal-graph-kuzu-causalgraphkuzuschemaerror }

- Kind: `class`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Raised when Kuzu schema cannot be applied.

### `polisyos.ir.analytics.causal_queries.CausalInterventionSpec` { #polisyos-ir-analytics-causal-queries-causalinterventionspec }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:CausalInterventionSpec`, `polisyos.ir:CausalInterventionSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_queries.InterventionType`
- Summary: Expose the causal-query intervention payload under the legacy public name.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bounds` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `distribution` | `str | NoneType` | `no` | `—` | — |
| `legal_constraint_id` | `str | NoneType` | `no` | `—` | — |
| `shift` | `float | NoneType` | `no` | `—` | — |
| `type` | `polisyos.ir.analytics.causal_queries.InterventionType` | `no` | `<InterventionType.ATOMIC: 'atomic'>` | `polisyos.ir.analytics.causal_queries.InterventionType` |
| `value` | `float | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.causal_queries.CausalQuery` { #polisyos-ir-analytics-causal-queries-causalquery }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:CausalQuery`, `polisyos.ir:CausalQuery`
- ABI snapshot: `causal_query` / `schemas/snapshots/ir/causal_query.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_queries.InterventionSpec`, `polisyos.ir.analytics.causal_queries.QueryType`
- Summary: Fully specified causal query contract for execution or persistence.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `condition` | `dict[str, float]` | `no` | `—` | — |
| `intervention_spec` | `polisyos.ir.analytics.causal_queries.InterventionSpec | NoneType` | `no` | `—` | `polisyos.ir.analytics.causal_queries.InterventionSpec` |
| `n_samples` | `int` | `no` | `1000` | — |
| `outcome_variable` | `str` | `yes` | `—` | — |
| `query_type` | `polisyos.ir.analytics.causal_queries.QueryType` | `yes` | `—` | `polisyos.ir.analytics.causal_queries.QueryType` |
| `treatment_value` | `float | NoneType` | `no` | `—` | — |
| `treatment_variable` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.causal_queries.CausalQueryResult` { #polisyos-ir-analytics-causal-queries-causalqueryresult }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:CausalQueryResult`, `polisyos.ir:CausalQueryResult`
- ABI snapshot: `causal_query_result` / `schemas/snapshots/ir/causal_query_result.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_queries.CausalQuery`
- Summary: Result payload returned for a persisted or in-memory causal query.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `computation_time_seconds` | `float` | `no` | `0.0` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `query` | `polisyos.ir.analytics.causal_queries.CausalQuery` | `yes` | `—` | `polisyos.ir.analytics.causal_queries.CausalQuery` |
| `result_ci` | `tuple[float, float]` | `yes` | `—` | — |
| `result_distribution` | `list[float] | NoneType` | `no` | `—` | — |
| `result_mean` | `float` | `yes` | `—` | — |
| `result_std` | `float` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.analytics.causal_queries.InterventionSpec` { #polisyos-ir-analytics-causal-queries-interventionspec }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:InterventionSpec`, `polisyos.ir:InterventionSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_queries.InterventionType`
- Summary: Treatment perturbation attached to a causal query.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bounds` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `distribution` | `str | NoneType` | `no` | `—` | — |
| `legal_constraint_id` | `str | NoneType` | `no` | `—` | — |
| `shift` | `float | NoneType` | `no` | `—` | — |
| `type` | `polisyos.ir.analytics.causal_queries.InterventionType` | `no` | `<InterventionType.ATOMIC: 'atomic'>` | `polisyos.ir.analytics.causal_queries.InterventionType` |
| `value` | `float | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.causal_queries.InterventionType` { #polisyos-ir-analytics-causal-queries-interventiontype }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:InterventionType`, `polisyos.ir:InterventionType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Mechanics of the treatment perturbation encoded in a query.

| Enum values |
|-------------|
| `atomic` |
| `truncated` |
| `shifted` |
| `stochastic` |

### `polisyos.ir.analytics.causal_queries.QueryType` { #polisyos-ir-analytics-causal-queries-querytype }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:QueryType`, `polisyos.ir:QueryType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: High-level family of causal query requested from the engine.

| Enum values |
|-------------|
| `interventional` |
| `counterfactual` |
| `attribution` |
| `soft_intervention` |

### `polisyos.ir.analytics.causal_rl.CausalDecisionProcessType` { #polisyos-ir-analytics-causal-rl-causaldecisionprocesstype }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:CausalDecisionProcessType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Decision-process families supported by the IR surface.

| Enum values |
|-------------|
| `causal_mdp` |
| `causal_pomdp` |

### `polisyos.ir.analytics.causal_rl.CausalRLContract` { #polisyos-ir-analytics-causal-rl-causalrlcontract }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:CausalRLContract`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_rl.CausalDecisionProcessType`, `polisyos.ir.analytics.causal_rl.CounterfactualPolicyOptimizationSpec`, `polisyos.ir.analytics.causal_rl.OnlineGraphLearningSpec`
- Summary: Contract surface for causal MDP/POMDP policy optimization.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `action_variables` | `tuple[str]` | `yes` | `—` | — |
| `confounder_variables` | `tuple[str]` | `no` | `()` | — |
| `contract_id` | `str` | `yes` | `—` | — |
| `graph_learning` | `polisyos.ir.analytics.causal_rl.OnlineGraphLearningSpec` | `no` | `—` | `polisyos.ir.analytics.causal_rl.OnlineGraphLearningSpec` |
| `latent_state_variables` | `tuple[str]` | `no` | `()` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `optimization` | `polisyos.ir.analytics.causal_rl.CounterfactualPolicyOptimizationSpec` | `yes` | `—` | `polisyos.ir.analytics.causal_rl.CounterfactualPolicyOptimizationSpec` |
| `process_type` | `polisyos.ir.analytics.causal_rl.CausalDecisionProcessType` | `yes` | `—` | `polisyos.ir.analytics.causal_rl.CausalDecisionProcessType` |
| `reward_variable` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `state_variables` | `tuple[str]` | `yes` | `—` | — |

### `polisyos.ir.analytics.causal_rl.CausalRLResult` { #polisyos-ir-analytics-causal-rl-causalrlresult }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:CausalRLResult`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Frozen result contract for causal-RL runs.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `contract_id` | `str` | `yes` | `—` | — |
| `learned_graph_confidence` | `float | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `off_policy_value` | `float | NoneType` | `no` | `—` | — |
| `policy_value_estimate` | `float` | `yes` | `—` | — |
| `regret_upper_bound` | `float | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `warnings` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.causal_rl.CounterfactualPolicyOptimizationSpec` { #polisyos-ir-analytics-causal-rl-counterfactualpolicyoptimizationspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:CounterfactualPolicyOptimizationSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_rl.PolicyOptimizationObjective`
- Summary: Optimization surface for counterfactual policy search.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `evaluation_horizon` | `int` | `yes` | `—` | — |
| `objective` | `polisyos.ir.analytics.causal_rl.PolicyOptimizationObjective` | `yes` | `—` | `polisyos.ir.analytics.causal_rl.PolicyOptimizationObjective` |
| `risk_aversion` | `float` | `no` | `0.0` | — |
| `rollout_budget` | `int` | `no` | `1` | — |

### `polisyos.ir.analytics.causal_rl.GraphUpdateMode` { #polisyos-ir-analytics-causal-rl-graphupdatemode }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: How online graph learning is incorporated into RL.

| Enum values |
|-------------|
| `frozen` |
| `periodic` |
| `every_episode` |

### `polisyos.ir.analytics.causal_rl.OnlineGraphLearningSpec` { #polisyos-ir-analytics-causal-rl-onlinegraphlearningspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_rl.GraphUpdateMode`
- Summary: How graph updates happen during online causal-RL execution.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `exploration_budget` | `float` | `no` | `0.0` | — |
| `max_graph_edits_per_update` | `int` | `no` | `0` | — |
| `update_interval_steps` | `int | NoneType` | `no` | `—` | — |
| `update_mode` | `polisyos.ir.analytics.causal_rl.GraphUpdateMode` | `no` | `<GraphUpdateMode.FROZEN: 'frozen'>` | `polisyos.ir.analytics.causal_rl.GraphUpdateMode` |

### `polisyos.ir.analytics.causal_rl.PolicyOptimizationObjective` { #polisyos-ir-analytics-causal-rl-policyoptimizationobjective }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Optimization objective for causal-RL training/evaluation.

| Enum values |
|-------------|
| `counterfactual_return` |
| `safe_improvement` |
| `off_policy_value` |

### `polisyos.ir.analytics.causal_run_snapshot.CausalRunSnapshot` { #polisyos-ir-analytics-causal-run-snapshot-causalrunsnapshot }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:CausalRunSnapshot`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_run_snapshot.MethodInvocationRecord`
- Summary: Complete reproducibility snapshot for one causal engine run.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `algorithm_version` | `str` | `no` | `''` | — |
| `created_at` | `str` | `no` | `''` | — |
| `dataset_fingerprints` | `dict[str, str]` | `no` | `—` | — |
| `dataset_n_obs` | `dict[str, int]` | `no` | `—` | — |
| `estimand_fingerprint` | `str` | `no` | `''` | — |
| `estimand_shape` | `str` | `no` | `''` | — |
| `graph_fingerprint` | `str` | `no` | `''` | — |
| `graph_schema_version` | `str` | `no` | `''` | — |
| `method_catalog_hash` | `str | NoneType` | `no` | `—` | — |
| `method_invocations` | `tuple[polisyos.ir.analytics.causal_run_snapshot.MethodInvocationRecord]` | `no` | `()` | `polisyos.ir.analytics.causal_run_snapshot.MethodInvocationRecord` |
| `n_edges` | `int` | `no` | `0` | — |
| `n_nodes` | `int` | `no` | `0` | — |
| `plan_hash` | `str | NoneType` | `no` | `—` | — |
| `python_version` | `str` | `no` | `''` | — |
| `query_str` | `str` | `no` | `''` | — |
| `run_id` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `warnings` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.causal_run_snapshot.MethodInvocationRecord` { #polisyos-ir-analytics-causal-run-snapshot-methodinvocationrecord }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Record of a single method invocation during estimation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `backend` | `str` | `no` | `''` | — |
| `determinism_tier` | `str` | `no` | `''` | — |
| `is_nuisance` | `bool` | `no` | `False` | — |
| `library_versions` | `dict[str, str]` | `no` | `—` | — |
| `method_fqn` | `str` | `yes` | `—` | — |
| `method_version` | `str | NoneType` | `no` | `—` | — |
| `params_hash` | `str` | `no` | `''` | — |

### `polisyos.ir.analytics.context.ContextEnrichmentIssue` { #polisyos-ir-analytics-context-contextenrichmentissue }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.context.ContextEnrichmentIssueCode`
- Summary: Structured diagnostic for degraded datasource enrichment.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `code` | `polisyos.ir.analytics.context.ContextEnrichmentIssueCode` | `yes` | `—` | `polisyos.ir.analytics.context.ContextEnrichmentIssueCode` |
| `context_id` | `str` | `no` | `''` | — |
| `detail` | `str` | `yes` | `—` | — |
| `source` | `str` | `yes` | `—` | — |
| `year` | `int` | `yes` | `—` | — |

### `polisyos.ir.analytics.context.ContextEnrichmentIssueCode` { #polisyos-ir-analytics-context-contextenrichmentissuecode }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Typed degraded outcomes for optional datasource enrichment.

| Enum values |
|-------------|
| `fetch_failed` |
| `finder_failed` |
| `invalid_payload` |

### `polisyos.ir.analytics.context.ContextProfile` { #polisyos-ir-analytics-context-contextprofile }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.context.ContextProfileInferenceLevel`, `polisyos.ir.analytics.context.IncomeLevel`
- Summary: Context profile for transport-aware literature reuse.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `context_id` | `str` | `no` | `''` | — |
| `context_label` | `str` | `no` | `''` | — |
| `corruption_level` | `float | NoneType` | `no` | `—` | — |
| `countries` | `list[str]` | `no` | `—` | — |
| `cultural_cluster` | `str | NoneType` | `no` | `—` | — |
| `data_sources` | `list[str]` | `no` | `—` | — |
| `economic_openness` | `float | NoneType` | `no` | `—` | — |
| `gdp_per_capita` | `float | NoneType` | `no` | `—` | — |
| `income_level` | `polisyos.ir.analytics.context.IncomeLevel` | `no` | `<IncomeLevel.UNKNOWN: 'unknown'>` | `polisyos.ir.analytics.context.IncomeLevel` |
| `inference_level` | `polisyos.ir.analytics.context.ContextProfileInferenceLevel` | `no` | `<ContextProfileInferenceLevel.INFERRED_BASIC: 'inferred_basic'>` | `polisyos.ir.analytics.context.ContextProfileInferenceLevel` |
| `institutional_quality` | `float | NoneType` | `no` | `—` | — |
| `post_communist` | `bool` | `no` | `False` | — |
| `post_conflict` | `bool` | `no` | `False` | — |
| `publication_year` | `int | NoneType` | `no` | `—` | — |
| `social_trust` | `float | NoneType` | `no` | `—` | — |
| `state_capacity` | `float | NoneType` | `no` | `—` | — |
| `time_period` | `str` | `no` | `''` | — |

### `polisyos.ir.analytics.context.ContextProfileInferenceLevel` { #polisyos-ir-analytics-context-contextprofileinferencelevel }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Context profile inference level public type.

| Enum values |
|-------------|
| `inferred_basic` |
| `enriched` |
| `manual` |

### `polisyos.ir.analytics.context.IncomeLevel` { #polisyos-ir-analytics-context-incomelevel }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Income level public type.

| Enum values |
|-------------|
| `low` |
| `lower_middle` |
| `upper_middle` |
| `high` |
| `non_high` |
| `unknown` |

### `polisyos.ir.analytics.covariate_balance.CovariateBalanceReport` { #polisyos-ir-analytics-covariate-balance-covariatebalancereport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Per-variable and aggregate balance statistics after weighting or matching.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `imbalance_threshold` | `float` | `no` | `0.1` | — |
| `max_smd` | `float` | `no` | `0.0` | — |
| `mean_smd` | `float` | `no` | `0.0` | — |
| `n_imbalanced` | `int` | `no` | `0` | — |
| `n_vars_total` | `int` | `no` | `0` | — |
| `passes_balance_check` | `bool` | `no` | `True` | — |
| `recommendations` | `tuple[str]` | `no` | `()` | — |
| `variable_smd` | `dict[str, float]` | `no` | `—` | — |
| `weighted` | `bool` | `no` | `False` | — |

### `polisyos.ir.analytics.cross_graph.BridgeRelation` { #polisyos-ir-analytics-cross-graph-bridgerelation }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Bridge relation public type.

| Enum values |
|-------------|
| `metric_to_variable` |
| `parameter_to_variable` |
| `legal_to_metric` |
| `legal_to_variable` |
| `dataset_var_to_variable` |
| `claim_to_variable` |
| `claim_to_edge` |
| `context_dimension_to_variable` |

### `polisyos.ir.analytics.cross_graph.CanonicalConcept` { #polisyos-ir-analytics-cross-graph-canonicalconcept }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.cross_graph.ConceptKind`
- Summary: Canonical concept public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `concept_id` | `str` | `yes` | `—` | — |
| `concept_kind` | `polisyos.ir.analytics.cross_graph.ConceptKind` | `yes` | `—` | `polisyos.ir.analytics.cross_graph.ConceptKind` |
| `join_keys` | `dict[str, list[str]]` | `no` | `—` | — |
| `label` | `str` | `no` | `''` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |

### `polisyos.ir.analytics.cross_graph.CompositionCertificate` { #polisyos-ir-analytics-cross-graph-compositioncertificate }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.1`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Composition certificate public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `alignment_assumptions` | `list[str]` | `no` | `—` | — |
| `alignment_report_ref` | `str` | `yes` | `—` | — |
| `blocking_reasons` | `list[str]` | `no` | `—` | — |
| `checked_queries` | `dict[str, Literal[preserved, broken, unknown]]` | `no` | `—` | — |
| `composed_graph_ref` | `str | NoneType` | `no` | `—` | — |
| `failure_card_bundle_ref` | `str | NoneType` | `no` | `—` | — |
| `interface_mapping_ref` | `str` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `newly_required_assumptions` | `list[str]` | `no` | `—` | — |
| `review_status` | `Literal[clear, pending_review]` | `no` | `'clear'` | — |
| `schema_version` | `str` | `no` | `'1.1'` | — |
| `source_fragment_graph_refs` | `dict[str, str]` | `no` | `—` | — |
| `source_fragment_refs` | `dict[str, str]` | `no` | `—` | — |
| `status` | `Literal[preserved, deferred, broken, unknown]` | `no` | `'unknown'` | — |
| `structural_assumptions` | `list[str]` | `no` | `—` | — |
| `structure_status` | `Literal[valid, invalid]` | `no` | `'valid'` | — |
| `witness_ref` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.cross_graph.ConceptBridge` { #polisyos-ir-analytics-cross-graph-conceptbridge }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.cross_graph.BridgeRelation`
- Summary: Concept bridge public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `confidence` | `float` | `no` | `1.0` | — |
| `dst_concept_id` | `str` | `yes` | `—` | — |
| `provenance` | `list[str]` | `no` | `—` | — |
| `relation` | `polisyos.ir.analytics.cross_graph.BridgeRelation` | `yes` | `—` | `polisyos.ir.analytics.cross_graph.BridgeRelation` |
| `src_id` | `str` | `yes` | `—` | — |
| `src_kind` | `str` | `yes` | `—` | — |
| `src_system` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.cross_graph.ConceptKind` { #polisyos-ir-analytics-cross-graph-conceptkind }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Concept kind public type.

| Enum values |
|-------------|
| `metric` |
| `variable` |
| `parameter` |
| `legal_concept` |
| `legal_constraint` |
| `dataset` |
| `dataset_variable` |
| `scholar_claim` |
| `context_dimension` |

### `polisyos.ir.analytics.cross_graph.CrossGraphDiagnostic` { #polisyos-ir-analytics-cross-graph-crossgraphdiagnostic }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Cross graph diagnostic public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `code` | `str` | `yes` | `—` | — |
| `details` | `dict[str, Any]` | `no` | `—` | — |
| `message` | `str` | `yes` | `—` | — |
| `need_id` | `str | NoneType` | `no` | `—` | — |
| `severity` | `str` | `no` | `'warn'` | — |

### `polisyos.ir.analytics.cross_graph.CrossGraphEvidenceProfile` { #polisyos-ir-analytics-cross-graph-crossgraphevidenceprofile }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `2.1`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.context.ContextProfile`, `polisyos.ir.analytics.cross_graph.CanonicalConcept`, `polisyos.ir.analytics.cross_graph.ConceptBridge`, `polisyos.ir.analytics.cross_graph.CrossGraphDiagnostic`, `polisyos.ir.analytics.cross_graph.CrossGraphEvidenceSummary`, `polisyos.ir.analytics.cross_graph.CrossGraphSourceRefs`, `polisyos.ir.analytics.cross_graph.EvidenceNeedAssessment`, `polisyos.ir.analytics.cross_graph.EvidenceSourceStatus`
- Summary: Cross graph evidence profile data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `benchmark_summary` | `dict[str, Any]` | `no` | `—` | — |
| `bridges` | `list[polisyos.ir.analytics.cross_graph.ConceptBridge]` | `no` | `—` | `polisyos.ir.analytics.cross_graph.ConceptBridge` |
| `diagnostics` | `list[polisyos.ir.analytics.cross_graph.CrossGraphDiagnostic]` | `no` | `—` | `polisyos.ir.analytics.cross_graph.CrossGraphDiagnostic` |
| `needs` | `list[polisyos.ir.analytics.cross_graph.EvidenceNeedAssessment]` | `no` | `—` | `polisyos.ir.analytics.cross_graph.EvidenceNeedAssessment` |
| `notes` | `list[str]` | `no` | `—` | — |
| `ontology_snapshot` | `list[polisyos.ir.analytics.cross_graph.CanonicalConcept]` | `no` | `—` | `polisyos.ir.analytics.cross_graph.CanonicalConcept` |
| `schema_version` | `str` | `no` | `'2.1'` | — |
| `source_refs` | `polisyos.ir.analytics.cross_graph.CrossGraphSourceRefs` | `no` | `—` | `polisyos.ir.analytics.cross_graph.CrossGraphSourceRefs` |
| `source_statuses` | `dict[str, polisyos.ir.analytics.cross_graph.EvidenceSourceStatus]` | `no` | `—` | `polisyos.ir.analytics.cross_graph.EvidenceSourceStatus` |
| `summary` | `polisyos.ir.analytics.cross_graph.CrossGraphEvidenceSummary` | `yes` | `—` | `polisyos.ir.analytics.cross_graph.CrossGraphEvidenceSummary` |
| `target_context` | `polisyos.ir.analytics.context.ContextProfile | NoneType` | `no` | `—` | `polisyos.ir.analytics.context.ContextProfile` |

### `polisyos.ir.analytics.cross_graph.CrossGraphEvidenceSummary` { #polisyos-ir-analytics-cross-graph-crossgraphevidencesummary }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Cross graph evidence summary data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `blocking_need_ids` | `list[str]` | `no` | `—` | — |
| `evidence_status_counts` | `dict[str, int]` | `no` | `—` | — |
| `legal_status_counts` | `dict[str, int]` | `no` | `—` | — |
| `observability_status_counts` | `dict[str, int]` | `no` | `—` | — |
| `requires_expert_review_count` | `int` | `no` | `0` | — |
| `status` | `str` | `no` | `'ok'` | — |
| `total_needs` | `int` | `no` | `0` | — |
| `transport_status_counts` | `dict[str, int]` | `no` | `—` | — |

### `polisyos.ir.analytics.cross_graph.CrossGraphSourceRefs` { #polisyos-ir-analytics-cross-graph-crossgraphsourcerefs }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Cross graph source refs public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `academic_db_path` | `str | NoneType` | `no` | `—` | — |
| `academic_index_dir` | `str | NoneType` | `no` | `—` | — |
| `datasets_db_path` | `str | NoneType` | `no` | `—` | — |
| `legal_db_path` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.cross_graph.EvidenceNeed` { #polisyos-ir-analytics-cross-graph-evidenceneed }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.cross_graph.EvidenceNeedType`
- Summary: Evidence need public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `cause` | `str | NoneType` | `no` | `—` | — |
| `constraint_id` | `str | NoneType` | `no` | `—` | — |
| `criterion_id` | `str | NoneType` | `no` | `—` | — |
| `effect` | `str | NoneType` | `no` | `—` | — |
| `geography` | `str | NoneType` | `no` | `—` | — |
| `intervention_id` | `str | NoneType` | `no` | `—` | — |
| `intervention_kind` | `str | NoneType` | `no` | `—` | — |
| `jurisdiction` | `str | NoneType` | `no` | `—` | — |
| `kpi_id` | `str | NoneType` | `no` | `—` | — |
| `labels` | `list[str]` | `no` | `—` | — |
| `metric_id` | `str | NoneType` | `no` | `—` | — |
| `need_id` | `str` | `yes` | `—` | — |
| `need_type` | `polisyos.ir.analytics.cross_graph.EvidenceNeedType` | `yes` | `—` | `polisyos.ir.analytics.cross_graph.EvidenceNeedType` |
| `param_path` | `str | NoneType` | `no` | `—` | — |
| `parameter_name` | `str | NoneType` | `no` | `—` | — |
| `policy_domain` | `str | NoneType` | `no` | `—` | — |
| `slot_id` | `str | NoneType` | `no` | `—` | — |
| `source_path` | `str` | `no` | `''` | — |
| `target_context_id` | `str | NoneType` | `no` | `—` | — |
| `time_window` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.cross_graph.EvidenceNeedAssessment` { #polisyos-ir-analytics-cross-graph-evidenceneedassessment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.cross_graph.CrossGraphDiagnostic`, `polisyos.ir.analytics.cross_graph.EvidenceNeed`, `polisyos.ir.analytics.cross_graph.EvidenceStatus`, `polisyos.ir.analytics.cross_graph.LegalStatus`, `polisyos.ir.analytics.cross_graph.ObservabilityStatus`, `polisyos.ir.analytics.cross_graph.TransportStatus`, `polisyos.ir.analytics.transportability.TransportMode`
- Summary: Evidence need assessment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `blocking_reasons` | `list[str]` | `no` | `—` | — |
| `confidence` | `float` | `no` | `0.0` | — |
| `diagnostics` | `list[polisyos.ir.analytics.cross_graph.CrossGraphDiagnostic]` | `no` | `—` | `polisyos.ir.analytics.cross_graph.CrossGraphDiagnostic` |
| `evidence_status` | `polisyos.ir.analytics.cross_graph.EvidenceStatus` | `no` | `<EvidenceStatus.INSUFFICIENT: 'insufficient'>` | `polisyos.ir.analytics.cross_graph.EvidenceStatus` |
| `legal_status` | `polisyos.ir.analytics.cross_graph.LegalStatus` | `no` | `<LegalStatus.UNKNOWN: 'unknown'>` | `polisyos.ir.analytics.cross_graph.LegalStatus` |
| `need` | `polisyos.ir.analytics.cross_graph.EvidenceNeed` | `yes` | `—` | `polisyos.ir.analytics.cross_graph.EvidenceNeed` |
| `observability_status` | `polisyos.ir.analytics.cross_graph.ObservabilityStatus` | `no` | `<ObservabilityStatus.UNKNOWN: 'unknown'>` | `polisyos.ir.analytics.cross_graph.ObservabilityStatus` |
| `provenance_refs` | `list[str]` | `no` | `—` | — |
| `recommended_actions` | `list[str]` | `no` | `—` | — |
| `requires_expert_review` | `bool` | `no` | `False` | — |
| `resolved_concept_ids` | `list[str]` | `no` | `—` | — |
| `transport_mode` | `polisyos.ir.analytics.transportability.TransportMode` | `no` | `<TransportMode.NONE: 'none'>` | `polisyos.ir.analytics.transportability.TransportMode` |
| `transport_status` | `polisyos.ir.analytics.cross_graph.TransportStatus` | `no` | `<TransportStatus.UNSUPPORTED: 'unsupported'>` | `polisyos.ir.analytics.cross_graph.TransportStatus` |

### `polisyos.ir.analytics.cross_graph.EvidenceNeedType` { #polisyos-ir-analytics-cross-graph-evidenceneedtype }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Evidence need type public type.

| Enum values |
|-------------|
| `objective_metric` |
| `kpi_metric` |
| `success_criterion_metric` |
| `constraint_metric_or_slot` |
| `parameter_need` |
| `mechanism_need` |
| `legal_applicability_need` |
| `causal_edge_need` |

### `polisyos.ir.analytics.cross_graph.EvidenceSourceKind` { #polisyos-ir-analytics-cross-graph-evidencesourcekind }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Evidence source kind public type.

| Enum values |
|-------------|
| `academic` |
| `datasets` |
| `legal` |
| `benchmark` |

### `polisyos.ir.analytics.cross_graph.EvidenceSourceState` { #polisyos-ir-analytics-cross-graph-evidencesourcestate }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Evidence source state data model.

| Enum values |
|-------------|
| `available` |
| `missing_config` |
| `missing_path` |
| `init_failed` |
| `query_failed` |
| `disabled` |

### `polisyos.ir.analytics.cross_graph.EvidenceSourceStatus` { #polisyos-ir-analytics-cross-graph-evidencesourcestatus }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.cross_graph.EvidenceSourceKind`, `polisyos.ir.analytics.cross_graph.EvidenceSourceState`
- Summary: Evidence source status public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `configured` | `bool` | `no` | `False` | — |
| `detail` | `str | NoneType` | `no` | `—` | — |
| `path` | `str | NoneType` | `no` | `—` | — |
| `provenance_refs` | `list[str]` | `no` | `—` | — |
| `source` | `polisyos.ir.analytics.cross_graph.EvidenceSourceKind` | `yes` | `—` | `polisyos.ir.analytics.cross_graph.EvidenceSourceKind` |
| `status` | `polisyos.ir.analytics.cross_graph.EvidenceSourceState` | `no` | `<EvidenceSourceState.MISSING_CONFIG: 'missing_config'>` | `polisyos.ir.analytics.cross_graph.EvidenceSourceState` |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.cross_graph.EvidenceStatus` { #polisyos-ir-analytics-cross-graph-evidencestatus }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Evidence status public type.

| Enum values |
|-------------|
| `supported` |
| `mixed` |
| `insufficient` |
| `unsupported` |

### `polisyos.ir.analytics.cross_graph.FragmentInterfaceSchema` { #polisyos-ir-analytics-cross-graph-fragmentinterfaceschema }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.cross_graph.InterfaceVariableSchema`
- Summary: Fragment interface schema data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `fragment_id` | `str` | `yes` | `—` | — |
| `semantic_namespace` | `str` | `yes` | `—` | — |
| `variables` | `list[polisyos.ir.analytics.cross_graph.InterfaceVariableSchema]` | `no` | `—` | `polisyos.ir.analytics.cross_graph.InterfaceVariableSchema` |

### `polisyos.ir.analytics.cross_graph.InterfaceMapping` { #polisyos-ir-analytics-cross-graph-interfacemapping }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.cross_graph.InterfaceMappingEntry`
- Summary: Interface mapping public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `entries` | `list[polisyos.ir.analytics.cross_graph.InterfaceMappingEntry]` | `no` | `—` | `polisyos.ir.analytics.cross_graph.InterfaceMappingEntry` |
| `fragment_ids` | `list[str]` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.analytics.cross_graph.InterfaceMappingEntry` { #polisyos-ir-analytics-cross-graph-interfacemappingentry }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.cross_graph.InterfaceVariableBinding`
- Summary: Interface mapping entry data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `alignment_type` | `Literal[exact, scale_linked, proxy, latent_bridge, incompatible]` | `no` | `'exact'` | — |
| `assumptions_introduced` | `list[str]` | `no` | `—` | — |
| `bindings` | `list[polisyos.ir.analytics.cross_graph.InterfaceVariableBinding]` | `no` | `—` | `polisyos.ir.analytics.cross_graph.InterfaceVariableBinding` |
| `canonical_node_id` | `str` | `yes` | `—` | — |
| `interface_id` | `str` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `observed` | `bool` | `no` | `True` | — |
| `reviewer` | `Literal[automated, pending_review, human_verified]` | `no` | `'automated'` | — |

### `polisyos.ir.analytics.cross_graph.InterfaceRole` { #polisyos-ir-analytics-cross-graph-interfacerole }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Interface role public type.

| Enum values |
|-------------|
| `input` |
| `output` |
| `shared` |

### `polisyos.ir.analytics.cross_graph.InterfaceVariableBinding` { #polisyos-ir-analytics-cross-graph-interfacevariablebinding }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Interface variable binding public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `definition` | `str` | `no` | `''` | — |
| `fragment_id` | `str` | `yes` | `—` | — |
| `measurement_model_ref` | `str | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `observed` | `bool` | `no` | `True` | — |
| `unit` | `str | NoneType` | `no` | `—` | — |
| `variable_name` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.cross_graph.InterfaceVariableSchema` { #polisyos-ir-analytics-cross-graph-interfacevariableschema }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.cross_graph.InterfaceRole`
- Summary: Interface variable schema data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `definition` | `str` | `no` | `''` | — |
| `measurement_model_ref` | `str | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `observed` | `bool` | `no` | `True` | — |
| `role` | `polisyos.ir.analytics.cross_graph.InterfaceRole` | `no` | `<InterfaceRole.SHARED: 'shared'>` | `polisyos.ir.analytics.cross_graph.InterfaceRole` |
| `unit` | `str | NoneType` | `no` | `—` | — |
| `variable_name` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.cross_graph.LegalStatus` { #polisyos-ir-analytics-cross-graph-legalstatus }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Legal status public type.

| Enum values |
|-------------|
| `allowed` |
| `constrained` |
| `prohibited` |
| `unknown` |

### `polisyos.ir.analytics.cross_graph.ObservabilityStatus` { #polisyos-ir-analytics-cross-graph-observabilitystatus }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Observability status public type.

| Enum values |
|-------------|
| `direct` |
| `proxy_only` |
| `missing` |
| `unknown` |

### `polisyos.ir.analytics.cross_graph.SCMFragment` { #polisyos-ir-analytics-cross-graph-scmfragment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.1`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: SCM fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `exposed_inputs` | `list[str]` | `no` | `—` | — |
| `exposed_outputs` | `list[str]` | `no` | `—` | — |
| `fragment_id` | `str` | `yes` | `—` | — |
| `graph_ref` | `str` | `yes` | `—` | — |
| `interface_variables` | `list[str]` | `no` | `—` | — |
| `latent_summary` | `dict[str, str]` | `no` | `—` | — |
| `measurement_models` | `dict[str, str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.1'` | — |
| `semantic_namespace` | `str` | `yes` | `—` | — |
| `variable_definitions` | `dict[str, str]` | `no` | `—` | — |
| `variable_metadata` | `dict[str, dict[str, Any]]` | `no` | `—` | — |
| `variable_units` | `dict[str, str]` | `no` | `—` | — |

### `polisyos.ir.analytics.cross_graph.TransportStatus` { #polisyos-ir-analytics-cross-graph-transportstatus }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Transport status public type.

| Enum values |
|-------------|
| `identified` |
| `partially_identified` |
| `bounded_non_identified` |
| `unsupported` |

### `polisyos.ir.analytics.data_fusion.DataCombinationPlan` { #polisyos-ir-analytics-data-fusion-datacombinationplan }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Variance-optimal weights for combining estimates across datasets.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `combination_method` | `str` | `no` | `'inverse_variance_weighted'` | — |
| `expected_variance` | `float | NoneType` | `no` | `—` | — |
| `query` | `str` | `yes` | `—` | — |
| `required_datasets` | `tuple[str]` | `no` | `()` | — |
| `source_weights` | `dict[str, float]` | `yes` | `—` | — |

### `polisyos.ir.analytics.data_fusion.FusionDataset` { #polisyos-ir-analytics-data-fusion-fusiondataset }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Description of a single data source for multi-study fusion.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `available_interventions` | `tuple[str]` | `no` | `()` | — |
| `dataset_ref` | `str` | `yes` | `—` | — |
| `domain_id` | `str` | `yes` | `—` | — |
| `n_obs` | `int` | `yes` | `—` | — |
| `quality_score` | `float` | `no` | `1.0` | — |
| `selection_bias_vars` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.data_fusion.FusionResult` { #polisyos-ir-analytics-data-fusion-fusionresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Result of a data fusion identification step.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `fusion_formula_latex` | `str | NoneType` | `no` | `—` | — |
| `identification_algorithm` | `str` | `no` | `'mz-id'` | — |
| `is_identified` | `bool` | `yes` | `—` | — |
| `proof_steps` | `tuple[str]` | `no` | `()` | — |
| `query` | `str` | `yes` | `—` | — |
| `required_datasets` | `tuple[str]` | `no` | `()` | — |
| `required_interventions` | `tuple[str]` | `no` | `()` | — |
| `warnings` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.data_fusion.ValidityReport` { #polisyos-ir-analytics-data-fusion-validityreport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: External validity assessment via transportability analysis.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `non_transportable_variables` | `tuple[str]` | `no` | `()` | — |
| `overall_transportability` | `bool` | `yes` | `—` | — |
| `recommended_adjustments` | `tuple[str]` | `no` | `()` | — |
| `source_population` | `str` | `yes` | `—` | — |
| `target_population` | `str` | `yes` | `—` | — |
| `transport_formula_latex` | `str | NoneType` | `no` | `—` | — |
| `transportable_variables` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.data_views.AccessTier` { #polisyos-ir-analytics-data-views-accesstier }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:AccessTier`, `polisyos.ir:AccessTier`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Access-sensitivity tier required to materialize a data view.

| Enum values |
|-------------|
| `public` |
| `internal` |
| `sensitive` |

### `polisyos.ir.analytics.data_views.DataFilter` { #polisyos-ir-analytics-data-views-datafilter }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:DataFilter`, `polisyos.ir:DataFilter`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Predicate applied while slicing a materialized data view.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `column` | `str` | `yes` | `—` | — |
| `op` | `str` | `yes` | `—` | — |
| `value` | `str | int | float | bool` | `yes` | `—` | — |

### `polisyos.ir.analytics.data_views.DataViewRequest` { #polisyos-ir-analytics-data-views-dataviewrequest }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:DataViewRequest`, `polisyos.ir:DataViewRequest`
- ABI snapshot: `data_view_request` / `schemas/snapshots/ir/data_view_request.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.data_views.AccessTier`, `polisyos.ir.analytics.data_views.DataFilter`, `polisyos.ir.analytics.data_views.DataViewType`
- Summary: Request for a panel, snapshot, or network view over execution data.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `access_tier` | `polisyos.ir.analytics.data_views.AccessTier` | `yes` | `—` | `polisyos.ir.analytics.data_views.AccessTier` |
| `aggregation` | `str | NoneType` | `no` | `'mean'` | — |
| `ego_node_id` | `str | NoneType` | `no` | `—` | — |
| `filters` | `list[polisyos.ir.analytics.data_views.DataFilter]` | `no` | `—` | `polisyos.ir.analytics.data_views.DataFilter` |
| `hop_depth` | `int` | `no` | `1` | — |
| `metrics` | `list[str]` | `yes` | `—` | — |
| `relation_types` | `list[str] | NoneType` | `no` | `—` | — |
| `request_id` | `str` | `yes` | `—` | — |
| `run_id` | `str` | `yes` | `—` | — |
| `step_end` | `int | NoneType` | `no` | `—` | — |
| `step_start` | `int | NoneType` | `no` | `—` | — |
| `view_type` | `polisyos.ir.analytics.data_views.DataViewType` | `yes` | `—` | `polisyos.ir.analytics.data_views.DataViewType` |

### `polisyos.ir.analytics.data_views.DataViewType` { #polisyos-ir-analytics-data-views-dataviewtype }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:DataViewType`, `polisyos.ir:DataViewType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Logical shape of a runtime data view request.

| Enum values |
|-------------|
| `panel` |
| `snapshot` |
| `network` |

### `polisyos.ir.analytics.diagnostic_dashboard.DiagnosticDashboardData` { #polisyos-ir-analytics-diagnostic-dashboard-diagnosticdashboarddata }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.covariate_balance.CovariateBalanceReport`, `polisyos.ir.analytics.falsification_report.FalsificationReport`, `polisyos.ir.analytics.falsification_report.FalsificationTest`
- Summary: Aggregated diagnostic view for one causal analysis run.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `covariate_balance` | `polisyos.ir.analytics.covariate_balance.CovariateBalanceReport | NoneType` | `no` | `—` | `polisyos.ir.analytics.covariate_balance.CovariateBalanceReport` |
| `created_at` | `str` | `no` | `''` | — |
| `falsification` | `polisyos.ir.analytics.falsification_report.FalsificationReport | NoneType` | `no` | `—` | `polisyos.ir.analytics.falsification_report.FalsificationReport` |
| `has_balance_issues` | `bool` | `no` | `False` | — |
| `has_falsification_failures` | `bool` | `no` | `False` | — |
| `has_overlap_issues` | `bool` | `no` | `False` | — |
| `has_robustness_concerns` | `bool` | `no` | `False` | — |
| `n_diagnostics_run` | `int` | `no` | `0` | — |
| `n_failed` | `int` | `no` | `0` | — |
| `n_passed` | `int` | `no` | `0` | — |
| `n_warnings` | `int` | `no` | `0` | — |
| `overall_passed` | `bool` | `no` | `True` | — |
| `parallel_trends` | `polisyos.ir.analytics.falsification_report.FalsificationTest | NoneType` | `no` | `—` | `polisyos.ir.analytics.falsification_report.FalsificationTest` |
| `positivity` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `query_str` | `str` | `no` | `''` | — |
| `run_id` | `str` | `yes` | `—` | — |
| `sensitivity` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `support_mismatch` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `warnings` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.distributional.CohortDimension` { #polisyos-ir-analytics-distributional-cohortdimension }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:CohortDimension`, `polisyos.ir:CohortDimension`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Select the cohort axis used when slicing winners/losers summaries.

| Enum values |
|-------------|
| `income_quintile` |
| `income_decile` |
| `geography` |
| `age_group` |
| `gender` |
| `ethnicity` |
| `education` |
| `employment_status` |
| `custom` |

### `polisyos.ir.analytics.distributional.CohortImpact` { #polisyos-ir-analytics-distributional-cohortimpact }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:CohortImpact`, `polisyos.ir:CohortImpact`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.distributional.ImpactDirection`
- Summary: Distributional impact summary for one cohort within a breakdown.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `cohort_id` | `str` | `yes` | `—` | — |
| `cohort_label` | `str` | `yes` | `—` | — |
| `impact_direction` | `polisyos.ir.analytics.distributional.ImpactDirection` | `no` | `<ImpactDirection.NEUTRAL: 'neutral'>` | `polisyos.ir.analytics.distributional.ImpactDirection` |
| `is_vulnerable` | `bool` | `no` | `False` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `metric_deltas` | `dict[str, float]` | `no` | `—` | — |
| `metric_values` | `dict[str, float]` | `no` | `—` | — |
| `population_share` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.distributional.CouplingDiagnostics` { #polisyos-ir-analytics-distributional-couplingdiagnostics }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Summarize optimal-transport coupling quality and identifiability assumptions.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `convergence_delta` | `float | NoneType` | `no` | `—` | — |
| `identifiability_assumptions` | `list[str]` | `no` | `—` | — |
| `mass_conservation_error` | `float` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `regularization_strength` | `float | NoneType` | `no` | `—` | — |
| `sinkhorn_iterations` | `int | NoneType` | `no` | `—` | — |
| `source_marginal_l1_error` | `float` | `no` | `0.0` | — |
| `support_mismatch_note` | `str | NoneType` | `no` | `—` | — |
| `target_marginal_l1_error` | `float` | `no` | `0.0` | — |
| `weighting_mode` | `str` | `no` | `'uniform'` | — |

### `polisyos.ir.analytics.distributional.DimensionBreakdown` { #polisyos-ir-analytics-distributional-dimensionbreakdown }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:DimensionBreakdown`, `polisyos.ir:DimensionBreakdown`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.distributional.CohortDimension`, `polisyos.ir.analytics.distributional.CohortImpact`, `polisyos.ir.analytics.distributional.MetricUnit`
- Summary: Distributional comparison grouped by one cohort dimension.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `cohorts` | `list[polisyos.ir.analytics.distributional.CohortImpact]` | `yes` | `—` | `polisyos.ir.analytics.distributional.CohortImpact` |
| `dimension` | `polisyos.ir.analytics.distributional.CohortDimension` | `yes` | `—` | `polisyos.ir.analytics.distributional.CohortDimension` |
| `dimension_label` | `str` | `yes` | `—` | — |
| `gini_after` | `float | NoneType` | `no` | `—` | — |
| `gini_before` | `float | NoneType` | `no` | `—` | — |
| `gini_delta` | `float | NoneType` | `no` | `—` | — |
| `primary_metric` | `str` | `yes` | `—` | — |
| `primary_metric_unit` | `polisyos.ir.analytics.distributional.MetricUnit` | `no` | `<MetricUnit.PERCENT: 'percent'>` | `polisyos.ir.analytics.distributional.MetricUnit` |

### `polisyos.ir.analytics.distributional.DiscreteDistributionSummary` { #polisyos-ir-analytics-distributional-discretedistributionsummary }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.distributional.DistributionBin`
- Summary: Describe a weighted discrete outcome distribution over histogram bins.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bins` | `list[polisyos.ir.analytics.distributional.DistributionBin]` | `yes` | `—` | `polisyos.ir.analytics.distributional.DistributionBin` |
| `max_value` | `float | NoneType` | `no` | `—` | — |
| `mean_value` | `float | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `min_value` | `float | NoneType` | `no` | `—` | — |
| `outcome_name` | `str` | `yes` | `—` | — |
| `sample_size` | `int` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `total_weight` | `float` | `yes` | `—` | — |
| `weighting_mode` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.distributional.DistributionBin` { #polisyos-ir-analytics-distributional-distributionbin }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Store one histogram bin in a normalized discrete distribution summary.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `index` | `int` | `yes` | `—` | — |
| `lower_edge` | `float` | `yes` | `—` | — |
| `midpoint` | `float` | `yes` | `—` | — |
| `probability` | `float` | `yes` | `—` | — |
| `sample_count` | `int` | `yes` | `—` | — |
| `upper_edge` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.distributional.DistributionalEffectBundle` { #polisyos-ir-analytics-distributional-distributionaleffectbundle }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.distributional.CouplingDiagnostics`, `polisyos.ir.analytics.distributional.DistributionalJustification`, `polisyos.ir.refs.ArtifactRefModel`
- Summary: Persist the leaf artifact refs that make up a full distributional analysis bundle.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `baseline_distribution_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `causal_assumptions` | `list[str]` | `no` | `—` | — |
| `counterfactual_distribution_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `coupling_diagnostics` | `polisyos.ir.analytics.distributional.CouplingDiagnostics` | `yes` | `—` | `polisyos.ir.analytics.distributional.CouplingDiagnostics` |
| `coupling_ref` | `polisyos.ir.refs.ArtifactRefModel | NoneType` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `justification` | `polisyos.ir.analytics.distributional.DistributionalJustification` | `yes` | `—` | `polisyos.ir.analytics.distributional.DistributionalJustification` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `outcome_name` | `str` | `yes` | `—` | — |
| `quantile_shift_ref` | `polisyos.ir.refs.ArtifactRefModel | NoneType` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `readiness_cap` | `str` | `no` | `'simulation_ready'` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `subgroup_distribution_refs` | `list[polisyos.ir.refs.ArtifactRefModel]` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `tail_risk_delta_ref` | `polisyos.ir.refs.ArtifactRefModel | NoneType` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `wasserstein_distance` | `float | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.distributional.DistributionalJustification` { #polisyos-ir-analytics-distributional-distributionaljustification }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Declare whether a distributional claim is identified, bounded, or scenario-based.

| Enum values |
|-------------|
| `identified` |
| `bounded` |
| `scenario` |

### `polisyos.ir.analytics.distributional.DistributionalReport` { #polisyos-ir-analytics-distributional-distributionalreport }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:DistributionalReport`, `polisyos.ir:DistributionalReport`
- ABI snapshot: `distributional_report` / `schemas/snapshots/ir/distributional_report.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.distributional.DimensionBreakdown`, `polisyos.ir.analytics.distributional.WinnersLosersTable`
- Summary: Top-level distributional impact report for a policy evaluation run.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `breakdowns` | `list[polisyos.ir.analytics.distributional.DimensionBreakdown]` | `yes` | `—` | `polisyos.ir.analytics.distributional.DimensionBreakdown` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `methodology` | `str` | `no` | `'agent_aggregation'` | — |
| `overall_gini_after` | `float | NoneType` | `no` | `—` | — |
| `overall_gini_before` | `float | NoneType` | `no` | `—` | — |
| `overall_gini_delta` | `float | NoneType` | `no` | `—` | — |
| `palma_ratio_after` | `float | NoneType` | `no` | `—` | — |
| `palma_ratio_before` | `float | NoneType` | `no` | `—` | — |
| `palma_ratio_delta` | `float | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `source_simulation_ref` | `str | NoneType` | `no` | `—` | — |
| `winners_losers` | `polisyos.ir.analytics.distributional.WinnersLosersTable` | `no` | `—` | `polisyos.ir.analytics.distributional.WinnersLosersTable` |

### `polisyos.ir.analytics.distributional.ImpactDirection` { #polisyos-ir-analytics-distributional-impactdirection }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:ImpactDirection`, `polisyos.ir:ImpactDirection`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Coarse direction of a cohort or KPI impact.

| Enum values |
|-------------|
| `positive` |
| `negative` |
| `neutral` |
| `mixed` |

### `polisyos.ir.analytics.distributional.MetricUnit` { #polisyos-ir-analytics-distributional-metricunit }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:MetricUnit`, `polisyos.ir:MetricUnit`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Declare how distributional magnitudes should be rendered downstream.

| Enum values |
|-------------|
| `percent` |
| `ratio` |
| `absolute` |

### `polisyos.ir.analytics.distributional.OTCouplingSummary` { #polisyos-ir-analytics-distributional-otcouplingsummary }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Store a transport matrix and support diagnostics for optimal-transport analysis.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `convergence_delta` | `float` | `yes` | `—` | — |
| `density_ratio_diagnostics` | `dict[str, Any]` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `regularization_strength` | `float` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `sinkhorn_iterations` | `int` | `yes` | `—` | — |
| `source_support` | `tuple[float]` | `yes` | `—` | — |
| `target_support` | `tuple[float]` | `yes` | `—` | — |
| `transport_matrix` | `tuple[tuple[float]]` | `yes` | `—` | — |
| `weighting_mode` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.distributional.QuantileShiftEntry` { #polisyos-ir-analytics-distributional-quantileshiftentry }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Store one baseline-to-counterfactual shift at a specific quantile.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `baseline_value` | `float` | `yes` | `—` | — |
| `counterfactual_value` | `float` | `yes` | `—` | — |
| `quantile` | `float` | `yes` | `—` | — |
| `shift` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.distributional.QuantileShiftSummary` { #polisyos-ir-analytics-distributional-quantileshiftsummary }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.distributional.QuantileShiftEntry`
- Summary: Collect sorted quantile-shift entries for one outcome variable.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `entries` | `list[polisyos.ir.analytics.distributional.QuantileShiftEntry]` | `yes` | `—` | `polisyos.ir.analytics.distributional.QuantileShiftEntry` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `outcome_name` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.analytics.distributional.SubgroupDistributionComparison` { #polisyos-ir-analytics-distributional-subgroupdistributioncomparison }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.distributional.CohortDimension`, `polisyos.ir.analytics.distributional.CouplingDiagnostics`, `polisyos.ir.refs.ArtifactRefModel`
- Summary: Compare baseline and counterfactual distributions for one subgroup.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `baseline_distribution_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `baseline_sample_size` | `int` | `yes` | `—` | — |
| `causal_assumptions` | `list[str]` | `no` | `—` | — |
| `counterfactual_distribution_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `counterfactual_sample_size` | `int` | `yes` | `—` | — |
| `coupling_diagnostics` | `polisyos.ir.analytics.distributional.CouplingDiagnostics` | `yes` | `—` | `polisyos.ir.analytics.distributional.CouplingDiagnostics` |
| `coupling_ref` | `polisyos.ir.refs.ArtifactRefModel | NoneType` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `quantile_shift_ref` | `polisyos.ir.refs.ArtifactRefModel | NoneType` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `subgroup_dimension` | `polisyos.ir.analytics.distributional.CohortDimension` | `yes` | `—` | `polisyos.ir.analytics.distributional.CohortDimension` |
| `subgroup_id` | `str` | `yes` | `—` | — |
| `subgroup_label` | `str` | `yes` | `—` | — |
| `tail_risk_delta_ref` | `polisyos.ir.refs.ArtifactRefModel | NoneType` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `wasserstein_distance` | `float | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.distributional.TailRiskDeltaEntry` { #polisyos-ir-analytics-distributional-tailriskdeltaentry }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Store the exceedance and expected-shortfall delta at one baseline quantile.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `baseline_exceedance_probability` | `float` | `yes` | `—` | — |
| `baseline_expected_shortfall` | `float | NoneType` | `no` | `—` | — |
| `baseline_quantile` | `float` | `yes` | `—` | — |
| `counterfactual_exceedance_probability` | `float` | `yes` | `—` | — |
| `counterfactual_expected_shortfall` | `float | NoneType` | `no` | `—` | — |
| `exceedance_probability_delta` | `float` | `yes` | `—` | — |
| `expected_shortfall_delta` | `float | NoneType` | `no` | `—` | — |
| `threshold_value` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.distributional.TailRiskDeltaSummary` { #polisyos-ir-analytics-distributional-tailriskdeltasummary }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.distributional.TailRiskDeltaEntry`
- Summary: Collect tail-risk deltas for one outcome variable.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `entries` | `list[polisyos.ir.analytics.distributional.TailRiskDeltaEntry]` | `yes` | `—` | `polisyos.ir.analytics.distributional.TailRiskDeltaEntry` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `outcome_name` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.analytics.distributional.WinnersLosersEntry` { #polisyos-ir-analytics-distributional-winnerslosersentry }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:WinnersLosersEntry`, `polisyos.ir:WinnersLosersEntry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.distributional.CohortDimension`, `polisyos.ir.analytics.distributional.ImpactDirection`
- Summary: Flattened cohort record used in winners/losers summaries.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `cohort_id` | `str` | `yes` | `—` | — |
| `cohort_label` | `str` | `yes` | `—` | — |
| `dimension` | `polisyos.ir.analytics.distributional.CohortDimension` | `yes` | `—` | `polisyos.ir.analytics.distributional.CohortDimension` |
| `impact_direction` | `polisyos.ir.analytics.distributional.ImpactDirection` | `yes` | `—` | `polisyos.ir.analytics.distributional.ImpactDirection` |
| `is_vulnerable` | `bool` | `no` | `False` | — |
| `key_metric` | `str` | `no` | `''` | — |
| `key_metric_delta` | `float` | `no` | `0.0` | — |
| `net_impact` | `float` | `yes` | `—` | — |
| `population_share` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.distributional.WinnersLosersTable` { #polisyos-ir-analytics-distributional-winnersloserstable }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:WinnersLosersTable`, `polisyos.ir:WinnersLosersTable`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.distributional.CohortDimension`, `polisyos.ir.analytics.distributional.WinnersLosersEntry`
- Summary: Partition of affected cohorts into winners, losers, and neutral groups.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `canonical_dimension` | `polisyos.ir.analytics.distributional.CohortDimension | NoneType` | `no` | `—` | `polisyos.ir.analytics.distributional.CohortDimension` |
| `losers` | `list[polisyos.ir.analytics.distributional.WinnersLosersEntry]` | `no` | `—` | `polisyos.ir.analytics.distributional.WinnersLosersEntry` |
| `neutral` | `list[polisyos.ir.analytics.distributional.WinnersLosersEntry]` | `no` | `—` | `polisyos.ir.analytics.distributional.WinnersLosersEntry` |
| `winners` | `list[polisyos.ir.analytics.distributional.WinnersLosersEntry]` | `no` | `—` | `polisyos.ir.analytics.distributional.WinnersLosersEntry` |

### `polisyos.ir.analytics.dynamic_regime.BanditResult` { #polisyos-ir-analytics-dynamic-regime-banditresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Result of causal bandit simulation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `arm_cis` | `dict[str, tuple[float, float]]` | `yes` | `—` | — |
| `arm_estimates` | `dict[str, float]` | `yes` | `—` | — |
| `arm_pull_counts` | `dict[str, int]` | `yes` | `—` | — |
| `cumulative_regret` | `float | NoneType` | `no` | `—` | — |
| `exploration_strategy` | `str` | `no` | `'ucb1'` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `n_rounds` | `int` | `yes` | `—` | — |
| `optimal_arm` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.dynamic_regime.ContinuousTimeQuery` { #polisyos-ir-analytics-dynamic-regime-continuoustimequery }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.dynamic_regime.InterventionInterpolationPolicy`, `polisyos.ir.analytics.dynamic_regime.TemporalQueryMode`, `polisyos.ir.analytics.dynamic_regime.TemporalSamplingScheme`, `polisyos.ir.analytics.dynamic_regime.TemporalTargetFunctional`, `polisyos.ir.refs.ArtifactRefModel`
- Summary: Continuous-time causal query over a bounded time horizon.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `horizon_end` | `float` | `yes` | `—` | — |
| `horizon_start` | `float` | `yes` | `—` | — |
| `interpolation_policy` | `polisyos.ir.analytics.dynamic_regime.InterventionInterpolationPolicy` | `no` | `<InterventionInterpolationPolicy.PIECEWISE_CONSTANT: 'piecewise_constant'>` | `polisyos.ir.analytics.dynamic_regime.InterventionInterpolationPolicy` |
| `intervention_trajectory_ref` | `polisyos.ir.refs.ArtifactRefModel | NoneType` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `outcome_process` | `str` | `yes` | `—` | — |
| `query_mode` | `polisyos.ir.analytics.dynamic_regime.TemporalQueryMode` | `no` | `<TemporalQueryMode.FIXED_INTERVENTION: 'fixed_intervention'>` | `polisyos.ir.analytics.dynamic_regime.TemporalQueryMode` |
| `sampling_scheme` | `polisyos.ir.analytics.dynamic_regime.TemporalSamplingScheme` | `no` | `<TemporalSamplingScheme.REGULAR_GRID: 'regular_grid'>` | `polisyos.ir.analytics.dynamic_regime.TemporalSamplingScheme` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `target_functional` | `polisyos.ir.analytics.dynamic_regime.TemporalTargetFunctional` | `no` | `<TemporalTargetFunctional.EFFECT_PATH: 'effect_path'>` | `polisyos.ir.analytics.dynamic_regime.TemporalTargetFunctional` |
| `time_scale` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.dynamic_regime.DTRResult` { #polisyos-ir-analytics-dynamic-regime-dtrresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.dynamic_regime.DynamicTreatmentRegime`
- Summary: Result of Dynamic Treatment Regime estimation (Q-learning, A-learning, OWL, DR-DTR).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `method` | `Literal[q_learning, a_learning, owl, dr_dtr]` | `yes` | `—` | — |
| `n_stages` | `int` | `yes` | `—` | — |
| `n_units` | `int` | `yes` | `—` | — |
| `optimal_regime` | `polisyos.ir.analytics.dynamic_regime.DynamicTreatmentRegime` | `yes` | `—` | `polisyos.ir.analytics.dynamic_regime.DynamicTreatmentRegime` |
| `stage_coefficients` | `tuple[tuple[float]]` | `yes` | `—` | — |
| `value_ci` | `tuple[float, float]` | `yes` | `—` | — |
| `value_estimate` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.dynamic_regime.DynamicTreatmentRegime` { #polisyos-ir-analytics-dynamic-regime-dynamictreatmentregime }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.dynamic_regime.RegimeRule`
- Summary: Specification of a dynamic treatment regime d = (d_0, ..., d_{T-1}).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `outcome` | `str` | `yes` | `—` | — |
| `regime_coefficients` | `tuple[float] | NoneType` | `no` | `—` | — |
| `rule` | `polisyos.ir.analytics.dynamic_regime.RegimeRule` | `no` | `<RegimeRule.ALWAYS_TREAT: 'always_treat'>` | `polisyos.ir.analytics.dynamic_regime.RegimeRule` |
| `scheduled_actions` | `tuple[int] | NoneType` | `no` | `—` | — |
| `threshold_covariate_index` | `int` | `no` | `0` | — |
| `threshold_value` | `float` | `no` | `0.0` | — |
| `time_points` | `tuple[int]` | `yes` | `—` | — |
| `time_varying_covariates` | `tuple[str]` | `yes` | `—` | — |
| `treatment_variables` | `tuple[str]` | `yes` | `—` | — |

### `polisyos.ir.analytics.dynamic_regime.EffectTrajectoryBundle` { #polisyos-ir-analytics-dynamic-regime-effecttrajectorybundle }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.dynamic_regime.InterventionInterpolationPolicy`, `polisyos.ir.analytics.dynamic_regime.StrategicAdaptationMode`, `polisyos.ir.analytics.dynamic_regime.TemporalPathRepresentation`, `polisyos.ir.refs.ArtifactRefModel`, `polisyos.ir.refs.ContinuousTimeQueryRef`
- Summary: Canonical public contract for temporal effect trajectories and diagnostics.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `confidence_band_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `continuous_time_degraded` | `bool` | `no` | `False` | — |
| `discretization_error` | `float | NoneType` | `no` | `—` | — |
| `discretization_note` | `str | NoneType` | `no` | `—` | — |
| `interpolation_policy` | `polisyos.ir.analytics.dynamic_regime.InterventionInterpolationPolicy` | `no` | `<InterventionInterpolationPolicy.PIECEWISE_CONSTANT: 'piecewise_constant'>` | `polisyos.ir.analytics.dynamic_regime.InterventionInterpolationPolicy` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `path_representation` | `polisyos.ir.analytics.dynamic_regime.TemporalPathRepresentation` | `yes` | `—` | `polisyos.ir.analytics.dynamic_regime.TemporalPathRepresentation` |
| `query_ref` | `polisyos.ir.refs.ContinuousTimeQueryRef` | `yes` | `—` | `polisyos.ir.refs.ContinuousTimeQueryRef` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `solver_diagnostics_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `solver_family` | `str` | `yes` | `—` | — |
| `strategic_adaptation_mode` | `polisyos.ir.analytics.dynamic_regime.StrategicAdaptationMode` | `no` | `<StrategicAdaptationMode.ABSENT: 'absent'>` | `polisyos.ir.analytics.dynamic_regime.StrategicAdaptationMode` |
| `time_scale` | `str` | `yes` | `—` | — |
| `trajectory_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |

### `polisyos.ir.analytics.dynamic_regime.GComputationResult` { #polisyos-ir-analytics-dynamic-regime-gcomputationresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Result of g-computation E[Y^{ā}] under a dynamic treatment regime.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `confidence_interval` | `tuple[float, float]` | `yes` | `—` | — |
| `confidence_level` | `float` | `no` | `0.95` | — |
| `convergence_warnings` | `tuple[str]` | `no` | `()` | — |
| `counterfactual_mean` | `float` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `method` | `Literal[parametric_g, ice_g, ltmle]` | `no` | `'ice_g'` | — |
| `n_periods` | `int` | `yes` | `—` | — |
| `n_units` | `int` | `yes` | `—` | — |
| `regime` | `str` | `yes` | `—` | — |
| `sequential_ignorability_assumed` | `bool` | `no` | `True` | — |
| `standard_error` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.dynamic_regime.InterventionInterpolationPolicy` { #polisyos-ir-analytics-dynamic-regime-interventioninterpolationpolicy }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: How interventions are interpolated between observed control points.

| Enum values |
|-------------|
| `piecewise_constant` |
| `linear` |

### `polisyos.ir.analytics.dynamic_regime.OPEResult` { #polisyos-ir-analytics-dynamic-regime-operesult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Result of Off-Policy Evaluation (IS or DR estimator).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `confidence_interval` | `tuple[float, float]` | `yes` | `—` | — |
| `effective_sample_size` | `float` | `yes` | `—` | — |
| `importance_weight_max` | `float` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `method` | `Literal[is, dr]` | `yes` | `—` | — |
| `n_trajectories` | `int` | `yes` | `—` | — |
| `policy_value` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.dynamic_regime.RegimeRule` { #polisyos-ir-analytics-dynamic-regime-regimerule }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: How a dynamic treatment regime assigns treatment at each time point.

| Enum values |
|-------------|
| `always_treat` |
| `never_treat` |
| `threshold` |
| `linear_blip` |
| `explicit_schedule` |

### `polisyos.ir.analytics.dynamic_regime.RuntimeSupportStatus` { #polisyos-ir-analytics-dynamic-regime-runtimesupportstatus }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Machine-readable runtime support surface for temporal contracts.

| Enum values |
|-------------|
| `supported` |
| `degraded` |
| `blocked_research` |
| `blocked_unsupported` |

### `polisyos.ir.analytics.dynamic_regime.SNMMResult` { #polisyos-ir-analytics-dynamic-regime-snmmresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.dynamic_regime.DynamicTreatmentRegime`
- Summary: Result of Structural Nested Mean Model (SNMM) fitted via g-estimation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `blip_model` | `Literal[linear, interaction, quadratic]` | `no` | `'linear'` | — |
| `convergence_iterations` | `int | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `n_periods` | `int` | `yes` | `—` | — |
| `n_units` | `int` | `yes` | `—` | — |
| `optimal_regime` | `polisyos.ir.analytics.dynamic_regime.DynamicTreatmentRegime | NoneType` | `no` | `—` | `polisyos.ir.analytics.dynamic_regime.DynamicTreatmentRegime` |
| `psi_estimates` | `tuple[float]` | `yes` | `—` | — |
| `psi_std_errors` | `tuple[float]` | `yes` | `—` | — |

### `polisyos.ir.analytics.dynamic_regime.StrategicAdaptationMode` { #polisyos-ir-analytics-dynamic-regime-strategicadaptationmode }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Whether strategic response is excluded or modeled outside the trajectory.

| Enum values |
|-------------|
| `absent` |
| `modeled_separately` |

### `polisyos.ir.analytics.dynamic_regime.TemporalInterventionTrajectory` { #polisyos-ir-analytics-dynamic-regime-temporalinterventiontrajectory }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.dynamic_regime.InterventionInterpolationPolicy`
- Summary: Executable intervention trajectory contract for continuous-time queries.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `interpolation_policy` | `polisyos.ir.analytics.dynamic_regime.InterventionInterpolationPolicy` | `no` | `<InterventionInterpolationPolicy.PIECEWISE_CONSTANT: 'piecewise_constant'>` | `polisyos.ir.analytics.dynamic_regime.InterventionInterpolationPolicy` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `time_points` | `tuple[float]` | `yes` | `—` | — |
| `time_scale` | `str` | `yes` | `—` | — |
| `values` | `tuple[float]` | `yes` | `—` | — |

### `polisyos.ir.analytics.dynamic_regime.TemporalPathRepresentation` { #polisyos-ir-analytics-dynamic-regime-temporalpathrepresentation }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Model family used to represent the trajectory-level causal object.

| Enum values |
|-------------|
| `linear_sde` |
| `ode` |
| `discrete_replay` |
| `neural_cde` |
| `neural_sde` |

### `polisyos.ir.analytics.dynamic_regime.TemporalQueryMode` { #polisyos-ir-analytics-dynamic-regime-temporalquerymode }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Canonical execution mode for a temporal causal query.

| Enum values |
|-------------|
| `fixed_intervention` |
| `optimal_policy_discovery` |

### `polisyos.ir.analytics.dynamic_regime.TemporalSamplingScheme` { #polisyos-ir-analytics-dynamic-regime-temporalsamplingscheme }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Observation schedule used to connect the temporal query to data.

| Enum values |
|-------------|
| `regular_grid` |
| `irregular_grid` |

### `polisyos.ir.analytics.dynamic_regime.TemporalTargetFunctional` { #polisyos-ir-analytics-dynamic-regime-temporaltargetfunctional }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Functionals over an intervention-induced effect path on a time horizon.

| Enum values |
|-------------|
| `effect_path` |
| `integral_effect` |
| `time_to_threshold` |
| `occupancy_probability` |

### `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget` { #polisyos-ir-analytics-ecosystem-bridges-causalbridgetarget }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:CausalBridgeTarget`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: External causal ecosystem targets supported by the bridge layer.

| Enum values |
|-------------|
| `dowhy` |
| `econml` |
| `causalnex` |
| `pgmpy` |
| `tigramite_pcmci` |

### `polisyos.ir.analytics.ecosystem_bridges.CausalNexGraphBridge` { #polisyos-ir-analytics-ecosystem-bridges-causalnexgraphbridge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:CausalNexGraphBridge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget`
- Summary: CausalNex edge-list exchange with optional confidence weights.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `directed_edges` | `list[tuple[str, str]]` | `yes` | `—` | — |
| `nodes` | `list[str]` | `yes` | `—` | — |
| `target` | `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget` | `no` | `<CausalBridgeTarget.CAUSALNEX: 'causalnex'>` | `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget` |
| `weighted_confidence` | `dict[str, float]` | `no` | `—` | — |

### `polisyos.ir.analytics.ecosystem_bridges.DoWhyGraphBridge` { #polisyos-ir-analytics-ecosystem-bridges-dowhygraphbridge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:DoWhyGraphBridge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget`
- Summary: DoWhy-ready graph bridge using DOT plus explicit role hints.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `common_causes` | `list[str]` | `no` | `—` | — |
| `effect_modifiers` | `list[str]` | `no` | `—` | — |
| `graph_dot` | `str` | `yes` | `—` | — |
| `instruments` | `list[str]` | `no` | `—` | — |
| `outcome` | `str` | `yes` | `—` | — |
| `target` | `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget` | `no` | `<CausalBridgeTarget.DOWHY: 'dowhy'>` | `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget` |
| `treatment` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.ecosystem_bridges.EconMLDesignBridge` { #polisyos-ir-analytics-ecosystem-bridges-econmldesignbridge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:EconMLDesignBridge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget`
- Summary: EconML-ready design contract derived from an IR causal graph.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `confounders` | `list[str]` | `no` | `—` | — |
| `effect_modifiers` | `list[str]` | `no` | `—` | — |
| `features` | `list[str]` | `no` | `—` | — |
| `instruments` | `list[str]` | `no` | `—` | — |
| `outcome` | `str` | `yes` | `—` | — |
| `target` | `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget` | `no` | `<CausalBridgeTarget.ECONML: 'econml'>` | `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget` |
| `treatment` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.ecosystem_bridges.PgmpyGraphBridge` { #polisyos-ir-analytics-ecosystem-bridges-pgmpygraphbridge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:PgmpyGraphBridge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget`
- Summary: pgmpy/adjacency exchange covering directed and latent confounding edges.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `directed_edges` | `list[tuple[str, str]]` | `yes` | `—` | — |
| `latent_bidirected_edges` | `list[tuple[str, str]]` | `no` | `—` | — |
| `nodes` | `list[str]` | `yes` | `—` | — |
| `target` | `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget` | `no` | `<CausalBridgeTarget.PGMPY: 'pgmpy'>` | `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget` |

### `polisyos.ir.analytics.ecosystem_bridges.TigramiteEdge` { #polisyos-ir-analytics-ecosystem-bridges-tigramiteedge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:TigramiteEdge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: One Tigramite/PCMCI lagged edge.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `dst` | `str` | `yes` | `—` | — |
| `lag` | `int` | `yes` | `—` | — |
| `src` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.ecosystem_bridges.TigramitePCMCIBridge` { #polisyos-ir-analytics-ecosystem-bridges-tigramitepcmcibridge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:TigramitePCMCIBridge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget`, `polisyos.ir.analytics.ecosystem_bridges.TigramiteEdge`
- Summary: Tigramite PCMCI bridge preserving lagged-edge semantics.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `lagged_edges` | `list[polisyos.ir.analytics.ecosystem_bridges.TigramiteEdge]` | `no` | `—` | `polisyos.ir.analytics.ecosystem_bridges.TigramiteEdge` |
| `max_lag` | `int` | `yes` | `—` | — |
| `target` | `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget` | `no` | `<CausalBridgeTarget.TIGRAMITE_PCMCI: 'tigramite_pcmci'>` | `polisyos.ir.analytics.ecosystem_bridges.CausalBridgeTarget` |
| `variables` | `list[str]` | `yes` | `—` | — |

### `polisyos.ir.analytics.estimand.ConditionalInterventionNode` { #polisyos-ir-analytics-estimand-conditionalinterventionnode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionDomain`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode`
- Summary: Conditional intervention estimand: P(Y | do(X | Z=z)).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `condition_vars` | `tuple[str]` | `yes` | `—` | — |
| `dataset_ref` | `str | NoneType` | `no` | `—` | — |
| `domain` | `polisyos.ir.analytics.estimand.DistributionDomain` | `no` | `<DistributionDomain.SOURCE: 'source'>` | `polisyos.ir.analytics.estimand.DistributionDomain` |
| `inner_do_node` | `polisyos.ir.analytics.estimand.DistributionRef | polisyos.ir.analytics.estimand.SumNode | polisyos.ir.analytics.estimand.ProductNode | polisyos.ir.analytics.estimand.RatioNode | polisyos.ir.analytics.estimand.NuisanceNode | polisyos.ir.analytics.estimand.ExpectationNode | polisyos.ir.analytics.estimand.IntegralNode | polisyos.ir.analytics.estimand.PathSpecificNode | polisyos.ir.analytics.estimand.RecoveredDistNode | polisyos.ir.analytics.estimand.StochasticInterventionNode | polisyos.ir.analytics.estimand.ConditionalInterventionNode | polisyos.ir.analytics.estimand.ProxyAdjustmentNode | polisyos.ir.analytics.estimand.CounterfactualNode | polisyos.ir.analytics.estimand.NestedCounterfactualNode | polisyos.ir.analytics.estimand.CrossWorldNode | polisyos.ir.analytics.estimand.CtfInterventionNode` | `yes` | `—` | `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode` |
| `node_type` | `Literal[conditional_do]` | `no` | `'conditional_do'` | — |
| `outcome` | `str` | `yes` | `—` | — |
| `treatment` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.estimand.CounterfactualNode` { #polisyos-ir-analytics-estimand-counterfactualnode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.DistributionDomain`
- Summary: Y_{x}(u) — counterfactual random variable (Pearl's Layer 3, Ch. 7).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `conditioning` | `tuple[str]` | `no` | `()` | — |
| `dataset_ref` | `str | NoneType` | `no` | `—` | — |
| `domain` | `polisyos.ir.analytics.estimand.DistributionDomain` | `no` | `<DistributionDomain.SOURCE: 'source'>` | `polisyos.ir.analytics.estimand.DistributionDomain` |
| `intervention` | `dict[str, Any]` | `yes` | `—` | — |
| `node_type` | `Literal[counterfactual]` | `no` | `'counterfactual'` | — |
| `variable` | `str` | `yes` | `—` | — |
| `world_index` | `int` | `no` | `0` | — |

### `polisyos.ir.analytics.estimand.CrossWorldNode` { #polisyos-ir-analytics-estimand-crossworldnode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode`
- Summary: Cross-world query node for joint/independent counterfactual collections.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `joint` | `bool` | `no` | `True` | — |
| `node_type` | `Literal[cross_world]` | `no` | `'cross_world'` | — |
| `worlds` | `tuple[polisyos.ir.analytics.estimand.DistributionRef | polisyos.ir.analytics.estimand.SumNode | polisyos.ir.analytics.estimand.ProductNode | polisyos.ir.analytics.estimand.RatioNode | polisyos.ir.analytics.estimand.NuisanceNode | polisyos.ir.analytics.estimand.ExpectationNode | polisyos.ir.analytics.estimand.IntegralNode | polisyos.ir.analytics.estimand.PathSpecificNode | polisyos.ir.analytics.estimand.RecoveredDistNode | polisyos.ir.analytics.estimand.StochasticInterventionNode | polisyos.ir.analytics.estimand.ConditionalInterventionNode | polisyos.ir.analytics.estimand.ProxyAdjustmentNode | polisyos.ir.analytics.estimand.CounterfactualNode | polisyos.ir.analytics.estimand.NestedCounterfactualNode | polisyos.ir.analytics.estimand.CrossWorldNode | polisyos.ir.analytics.estimand.CtfInterventionNode]` | `yes` | `—` | `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode` |

### `polisyos.ir.analytics.estimand.CtfInterventionNode` { #polisyos-ir-analytics-estimand-ctfinterventionnode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionDomain`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode`
- Summary: Counterfactual intervention node for ctf-calculus rewriting.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `ctf_context` | `polisyos.ir.analytics.estimand.DistributionRef | polisyos.ir.analytics.estimand.SumNode | polisyos.ir.analytics.estimand.ProductNode | polisyos.ir.analytics.estimand.RatioNode | polisyos.ir.analytics.estimand.NuisanceNode | polisyos.ir.analytics.estimand.ExpectationNode | polisyos.ir.analytics.estimand.IntegralNode | polisyos.ir.analytics.estimand.PathSpecificNode | polisyos.ir.analytics.estimand.RecoveredDistNode | polisyos.ir.analytics.estimand.StochasticInterventionNode | polisyos.ir.analytics.estimand.ConditionalInterventionNode | polisyos.ir.analytics.estimand.ProxyAdjustmentNode | polisyos.ir.analytics.estimand.CounterfactualNode | polisyos.ir.analytics.estimand.NestedCounterfactualNode | polisyos.ir.analytics.estimand.CrossWorldNode | polisyos.ir.analytics.estimand.CtfInterventionNode` | `yes` | `—` | `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode` |
| `dataset_ref` | `str | NoneType` | `no` | `—` | — |
| `domain` | `polisyos.ir.analytics.estimand.DistributionDomain` | `no` | `<DistributionDomain.SOURCE: 'source'>` | `polisyos.ir.analytics.estimand.DistributionDomain` |
| `intervention` | `dict[str, Any]` | `yes` | `—` | — |
| `node_type` | `Literal[ctf_intervention]` | `no` | `'ctf_intervention'` | — |
| `variable` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.estimand.DistributionDomain` { #polisyos-ir-analytics-estimand-distributiondomain }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Which population / domain a probability factor comes from.

| Enum values |
|-------------|
| `source` |
| `target` |
| `experimental` |

### `polisyos.ir.analytics.estimand.DistributionRef` { #polisyos-ir-analytics-estimand-distributionref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.DistributionDomain`, `polisyos.ir.analytics.estimand.SideCondition`
- Summary: Atomic leaf of EstimandAST — a single probability distribution factor.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `conditioning` | `tuple[str]` | `no` | `()` | — |
| `dataset_ref` | `str | NoneType` | `no` | `—` | — |
| `domain` | `polisyos.ir.analytics.estimand.DistributionDomain` | `yes` | `—` | `polisyos.ir.analytics.estimand.DistributionDomain` |
| `intervention_set` | `tuple[str]` | `no` | `()` | — |
| `node_type` | `Literal[dist]` | `no` | `'dist'` | — |
| `side_conditions` | `tuple[polisyos.ir.analytics.estimand.SideCondition]` | `no` | `()` | `polisyos.ir.analytics.estimand.SideCondition` |
| `variables` | `tuple[str]` | `yes` | `—` | — |

### `polisyos.ir.analytics.estimand.EstimandAST` { #polisyos-ir-analytics-estimand-estimandast }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.SideCondition`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode`
- Summary: Root container for a fully symbolic causal estimand.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `all_variables` | `tuple[str]` | `yes` | `—` | — |
| `identification_method` | `str` | `no` | `''` | — |
| `outcome` | `str` | `yes` | `—` | — |
| `query_str` | `str` | `yes` | `—` | — |
| `root` | `polisyos.ir.analytics.estimand.DistributionRef | polisyos.ir.analytics.estimand.SumNode | polisyos.ir.analytics.estimand.ProductNode | polisyos.ir.analytics.estimand.RatioNode | polisyos.ir.analytics.estimand.NuisanceNode | polisyos.ir.analytics.estimand.ExpectationNode | polisyos.ir.analytics.estimand.IntegralNode | polisyos.ir.analytics.estimand.PathSpecificNode | polisyos.ir.analytics.estimand.RecoveredDistNode | polisyos.ir.analytics.estimand.StochasticInterventionNode | polisyos.ir.analytics.estimand.ConditionalInterventionNode | polisyos.ir.analytics.estimand.ProxyAdjustmentNode | polisyos.ir.analytics.estimand.CounterfactualNode | polisyos.ir.analytics.estimand.NestedCounterfactualNode | polisyos.ir.analytics.estimand.CrossWorldNode | polisyos.ir.analytics.estimand.CtfInterventionNode` | `yes` | `—` | `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `side_conditions` | `tuple[polisyos.ir.analytics.estimand.SideCondition]` | `no` | `()` | `polisyos.ir.analytics.estimand.SideCondition` |
| `treatment` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.estimand.ExpectationNode` { #polisyos-ir-analytics-estimand-expectationnode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.DistributionDomain`
- Summary: Expectation leaf — E[Y | X] or counterfactual E[Y | do(X)].

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `conditioning` | `tuple[str]` | `no` | `()` | — |
| `counterfactual` | `bool` | `no` | `False` | — |
| `dataset_ref` | `str | NoneType` | `no` | `—` | — |
| `domain` | `polisyos.ir.analytics.estimand.DistributionDomain` | `no` | `<DistributionDomain.SOURCE: 'source'>` | `polisyos.ir.analytics.estimand.DistributionDomain` |
| `intervention_set` | `tuple[str]` | `no` | `()` | — |
| `node_type` | `Literal[expectation]` | `no` | `'expectation'` | — |
| `outcome` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.estimand.IntegralNode` { #polisyos-ir-analytics-estimand-integralnode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode`
- Summary: Continuous marginalisation: ∫ operand d(integration_vars).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `integration_vars` | `tuple[str]` | `yes` | `—` | — |
| `measure` | `str` | `no` | `'lebesgue'` | — |
| `node_type` | `Literal[integral]` | `no` | `'integral'` | — |
| `operand` | `polisyos.ir.analytics.estimand.DistributionRef | polisyos.ir.analytics.estimand.SumNode | polisyos.ir.analytics.estimand.ProductNode | polisyos.ir.analytics.estimand.RatioNode | polisyos.ir.analytics.estimand.NuisanceNode | polisyos.ir.analytics.estimand.ExpectationNode | polisyos.ir.analytics.estimand.IntegralNode | polisyos.ir.analytics.estimand.PathSpecificNode | polisyos.ir.analytics.estimand.RecoveredDistNode | polisyos.ir.analytics.estimand.StochasticInterventionNode | polisyos.ir.analytics.estimand.ConditionalInterventionNode | polisyos.ir.analytics.estimand.ProxyAdjustmentNode | polisyos.ir.analytics.estimand.CounterfactualNode | polisyos.ir.analytics.estimand.NestedCounterfactualNode | polisyos.ir.analytics.estimand.CrossWorldNode | polisyos.ir.analytics.estimand.CtfInterventionNode` | `yes` | `—` | `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode` |

### `polisyos.ir.analytics.estimand.NestedCounterfactualNode` { #polisyos-ir-analytics-estimand-nestedcounterfactualnode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionDomain`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode`
- Summary: Nested counterfactual query for ctf-calculus.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `dataset_ref` | `str | NoneType` | `no` | `—` | — |
| `domain` | `polisyos.ir.analytics.estimand.DistributionDomain` | `no` | `<DistributionDomain.SOURCE: 'source'>` | `polisyos.ir.analytics.estimand.DistributionDomain` |
| `inner_counterfactual` | `polisyos.ir.analytics.estimand.DistributionRef | polisyos.ir.analytics.estimand.SumNode | polisyos.ir.analytics.estimand.ProductNode | polisyos.ir.analytics.estimand.RatioNode | polisyos.ir.analytics.estimand.NuisanceNode | polisyos.ir.analytics.estimand.ExpectationNode | polisyos.ir.analytics.estimand.IntegralNode | polisyos.ir.analytics.estimand.PathSpecificNode | polisyos.ir.analytics.estimand.RecoveredDistNode | polisyos.ir.analytics.estimand.StochasticInterventionNode | polisyos.ir.analytics.estimand.ConditionalInterventionNode | polisyos.ir.analytics.estimand.ProxyAdjustmentNode | polisyos.ir.analytics.estimand.CounterfactualNode | polisyos.ir.analytics.estimand.NestedCounterfactualNode | polisyos.ir.analytics.estimand.CrossWorldNode | polisyos.ir.analytics.estimand.CtfInterventionNode` | `yes` | `—` | `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode` |
| `node_type` | `Literal[nested_counterfactual]` | `no` | `'nested_counterfactual'` | — |
| `outer_intervention` | `dict[str, Any]` | `yes` | `—` | — |
| `outer_variable` | `str` | `yes` | `—` | — |
| `world_indices` | `tuple[int]` | `no` | `()` | — |

### `polisyos.ir.analytics.estimand.NuisanceNode` { #polisyos-ir-analytics-estimand-nuisancenode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.DistributionDomain`
- Summary: Nuisance function leaf — a statistical model fitted as an intermediate step.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `conditioning` | `tuple[str]` | `no` | `()` | — |
| `dataset_ref` | `str | NoneType` | `no` | `—` | — |
| `domain` | `polisyos.ir.analytics.estimand.DistributionDomain` | `no` | `<DistributionDomain.SOURCE: 'source'>` | `polisyos.ir.analytics.estimand.DistributionDomain` |
| `node_type` | `Literal[nuisance]` | `no` | `'nuisance'` | — |
| `nuisance_type` | `Literal[propensity, outcome, density_ratio, mediator_density]` | `yes` | `—` | — |
| `target_variable` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.estimand.PathSpecificNode` { #polisyos-ir-analytics-estimand-pathspecificnode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.DistributionDomain`
- Summary: Path-specific effect leaf — E[Y(t, M_{active}(t'))] via active/fixed paths.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `active_paths` | `tuple[tuple[str]]` | `no` | `()` | — |
| `active_treatment` | `float` | `no` | `1.0` | — |
| `dataset_ref` | `str | NoneType` | `no` | `—` | — |
| `domain` | `polisyos.ir.analytics.estimand.DistributionDomain` | `no` | `<DistributionDomain.SOURCE: 'source'>` | `polisyos.ir.analytics.estimand.DistributionDomain` |
| `frozen_paths` | `tuple[tuple[str]]` | `no` | `()` | — |
| `node_type` | `Literal[path_specific]` | `no` | `'path_specific'` | — |
| `outcome` | `str` | `yes` | `—` | — |
| `reference_treatment` | `float` | `no` | `0.0` | — |
| `treatment` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.estimand.ProductNode` { #polisyos-ir-analytics-estimand-productnode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode`
- Summary: Product of factors: factor₁ · factor₂ · …

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `factors` | `tuple[polisyos.ir.analytics.estimand.DistributionRef | polisyos.ir.analytics.estimand.SumNode | polisyos.ir.analytics.estimand.ProductNode | polisyos.ir.analytics.estimand.RatioNode | polisyos.ir.analytics.estimand.NuisanceNode | polisyos.ir.analytics.estimand.ExpectationNode | polisyos.ir.analytics.estimand.IntegralNode | polisyos.ir.analytics.estimand.PathSpecificNode | polisyos.ir.analytics.estimand.RecoveredDistNode | polisyos.ir.analytics.estimand.StochasticInterventionNode | polisyos.ir.analytics.estimand.ConditionalInterventionNode | polisyos.ir.analytics.estimand.ProxyAdjustmentNode | polisyos.ir.analytics.estimand.CounterfactualNode | polisyos.ir.analytics.estimand.NestedCounterfactualNode | polisyos.ir.analytics.estimand.CrossWorldNode | polisyos.ir.analytics.estimand.CtfInterventionNode]` | `yes` | `—` | `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode` |
| `node_type` | `Literal[product]` | `no` | `'product'` | — |

### `polisyos.ir.analytics.estimand.ProxyAdjustmentNode` { #polisyos-ir-analytics-estimand-proxyadjustmentnode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionDomain`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode`
- Summary: Proxy-adjusted estimand under measurement error (Kuroki & Pearl 2014).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `dataset_ref` | `str | NoneType` | `no` | `—` | — |
| `domain` | `polisyos.ir.analytics.estimand.DistributionDomain` | `no` | `<DistributionDomain.SOURCE: 'source'>` | `polisyos.ir.analytics.estimand.DistributionDomain` |
| `identification_theorem` | `str` | `no` | `'Kuroki-Pearl-2014-Thm2'` | — |
| `inner_do_node` | `polisyos.ir.analytics.estimand.DistributionRef | polisyos.ir.analytics.estimand.SumNode | polisyos.ir.analytics.estimand.ProductNode | polisyos.ir.analytics.estimand.RatioNode | polisyos.ir.analytics.estimand.NuisanceNode | polisyos.ir.analytics.estimand.ExpectationNode | polisyos.ir.analytics.estimand.IntegralNode | polisyos.ir.analytics.estimand.PathSpecificNode | polisyos.ir.analytics.estimand.RecoveredDistNode | polisyos.ir.analytics.estimand.StochasticInterventionNode | polisyos.ir.analytics.estimand.ConditionalInterventionNode | polisyos.ir.analytics.estimand.ProxyAdjustmentNode | polisyos.ir.analytics.estimand.CounterfactualNode | polisyos.ir.analytics.estimand.NestedCounterfactualNode | polisyos.ir.analytics.estimand.CrossWorldNode | polisyos.ir.analytics.estimand.CtfInterventionNode` | `yes` | `—` | `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode` |
| `measurement_model` | `Literal[known, estimated, unknown]` | `no` | `'unknown'` | — |
| `node_type` | `Literal[proxy_adjustment]` | `no` | `'proxy_adjustment'` | — |
| `proxy_map` | `tuple[tuple[str, str]]` | `yes` | `—` | — |

### `polisyos.ir.analytics.estimand.RatioNode` { #polisyos-ir-analytics-estimand-rationode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode`
- Summary: Ratio: numerator / denominator.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `denominator` | `polisyos.ir.analytics.estimand.DistributionRef | polisyos.ir.analytics.estimand.SumNode | polisyos.ir.analytics.estimand.ProductNode | polisyos.ir.analytics.estimand.RatioNode | polisyos.ir.analytics.estimand.NuisanceNode | polisyos.ir.analytics.estimand.ExpectationNode | polisyos.ir.analytics.estimand.IntegralNode | polisyos.ir.analytics.estimand.PathSpecificNode | polisyos.ir.analytics.estimand.RecoveredDistNode | polisyos.ir.analytics.estimand.StochasticInterventionNode | polisyos.ir.analytics.estimand.ConditionalInterventionNode | polisyos.ir.analytics.estimand.ProxyAdjustmentNode | polisyos.ir.analytics.estimand.CounterfactualNode | polisyos.ir.analytics.estimand.NestedCounterfactualNode | polisyos.ir.analytics.estimand.CrossWorldNode | polisyos.ir.analytics.estimand.CtfInterventionNode` | `yes` | `—` | `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode` |
| `node_type` | `Literal[ratio]` | `no` | `'ratio'` | — |
| `numerator` | `polisyos.ir.analytics.estimand.DistributionRef | polisyos.ir.analytics.estimand.SumNode | polisyos.ir.analytics.estimand.ProductNode | polisyos.ir.analytics.estimand.RatioNode | polisyos.ir.analytics.estimand.NuisanceNode | polisyos.ir.analytics.estimand.ExpectationNode | polisyos.ir.analytics.estimand.IntegralNode | polisyos.ir.analytics.estimand.PathSpecificNode | polisyos.ir.analytics.estimand.RecoveredDistNode | polisyos.ir.analytics.estimand.StochasticInterventionNode | polisyos.ir.analytics.estimand.ConditionalInterventionNode | polisyos.ir.analytics.estimand.ProxyAdjustmentNode | polisyos.ir.analytics.estimand.CounterfactualNode | polisyos.ir.analytics.estimand.NestedCounterfactualNode | polisyos.ir.analytics.estimand.CrossWorldNode | polisyos.ir.analytics.estimand.CtfInterventionNode` | `yes` | `—` | `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode` |

### `polisyos.ir.analytics.estimand.RecoveredDistNode` { #polisyos-ir-analytics-estimand-recovereddistnode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.DistributionDomain`
- Summary: A distribution factor P(V_i | V_{<i}) recovered via the ordered fixing operator.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `conditioning` | `tuple[str]` | `no` | `()` | — |
| `dataset_ref` | `str | NoneType` | `no` | `—` | — |
| `domain` | `polisyos.ir.analytics.estimand.DistributionDomain` | `no` | `<DistributionDomain.SOURCE: 'source'>` | `polisyos.ir.analytics.estimand.DistributionDomain` |
| `missingness_indicator` | `str` | `yes` | `—` | — |
| `missingness_kind` | `str` | `yes` | `—` | — |
| `node_type` | `Literal[recovered_dist]` | `no` | `'recovered_dist'` | — |
| `proxy_variable` | `str` | `yes` | `—` | — |
| `variable` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.estimand.SideCondition` { #polisyos-ir-analytics-estimand-sidecondition }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.SideConditionKind`
- Summary: A formal assumption that must hold for the estimand to be valid.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `description` | `str` | `no` | `''` | — |
| `kind` | `polisyos.ir.analytics.estimand.SideConditionKind` | `yes` | `—` | `polisyos.ir.analytics.estimand.SideConditionKind` |
| `required` | `bool` | `no` | `True` | — |
| `variables` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.estimand.SideConditionKind` { #polisyos-ir-analytics-estimand-sideconditionkind }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Semantic categories of identification side-conditions.

| Enum values |
|-------------|
| `positivity` |
| `overlap` |
| `sutva` |
| `consistency` |
| `no_interference` |
| `time_stationarity` |
| `exclusion_restriction` |
| `selection` |

### `polisyos.ir.analytics.estimand.StochasticInterventionNode` { #polisyos-ir-analytics-estimand-stochasticinterventionnode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionDomain`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.StochasticPolicy`, `polisyos.ir.analytics.estimand.SumNode`
- Summary: Stochastic intervention estimand: E_π[Y] = ∫ P(Y|do(X=x)) π(x|Z) dx.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `domain` | `polisyos.ir.analytics.estimand.DistributionDomain` | `no` | `<DistributionDomain.SOURCE: 'source'>` | `polisyos.ir.analytics.estimand.DistributionDomain` |
| `inner_do_node` | `polisyos.ir.analytics.estimand.DistributionRef | polisyos.ir.analytics.estimand.SumNode | polisyos.ir.analytics.estimand.ProductNode | polisyos.ir.analytics.estimand.RatioNode | polisyos.ir.analytics.estimand.NuisanceNode | polisyos.ir.analytics.estimand.ExpectationNode | polisyos.ir.analytics.estimand.IntegralNode | polisyos.ir.analytics.estimand.PathSpecificNode | polisyos.ir.analytics.estimand.RecoveredDistNode | polisyos.ir.analytics.estimand.StochasticInterventionNode | polisyos.ir.analytics.estimand.ConditionalInterventionNode | polisyos.ir.analytics.estimand.ProxyAdjustmentNode | polisyos.ir.analytics.estimand.CounterfactualNode | polisyos.ir.analytics.estimand.NestedCounterfactualNode | polisyos.ir.analytics.estimand.CrossWorldNode | polisyos.ir.analytics.estimand.CtfInterventionNode` | `yes` | `—` | `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode` |
| `integration_var` | `str` | `yes` | `—` | — |
| `node_type` | `Literal[stochastic_intervention]` | `no` | `'stochastic_intervention'` | — |
| `policy` | `polisyos.ir.analytics.estimand.StochasticPolicy` | `yes` | `—` | `polisyos.ir.analytics.estimand.StochasticPolicy` |
| `treatment_var` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.estimand.StochasticPolicy` { #polisyos-ir-analytics-estimand-stochasticpolicy }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Policy specification for a stochastic / soft intervention.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `conditioning_vars` | `tuple[str]` | `no` | `()` | — |
| `policy_expr` | `str | NoneType` | `no` | `—` | — |
| `policy_type` | `Literal[soft, shift, conditional, threshold]` | `yes` | `—` | — |
| `shift_delta` | `float | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.estimand.SumNode` { #polisyos-ir-analytics-estimand-sumnode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode`
- Summary: Marginalisation: Σ_{summation_vars} operand.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `node_type` | `Literal[sum]` | `no` | `'sum'` | — |
| `operand` | `polisyos.ir.analytics.estimand.DistributionRef | polisyos.ir.analytics.estimand.SumNode | polisyos.ir.analytics.estimand.ProductNode | polisyos.ir.analytics.estimand.RatioNode | polisyos.ir.analytics.estimand.NuisanceNode | polisyos.ir.analytics.estimand.ExpectationNode | polisyos.ir.analytics.estimand.IntegralNode | polisyos.ir.analytics.estimand.PathSpecificNode | polisyos.ir.analytics.estimand.RecoveredDistNode | polisyos.ir.analytics.estimand.StochasticInterventionNode | polisyos.ir.analytics.estimand.ConditionalInterventionNode | polisyos.ir.analytics.estimand.ProxyAdjustmentNode | polisyos.ir.analytics.estimand.CounterfactualNode | polisyos.ir.analytics.estimand.NestedCounterfactualNode | polisyos.ir.analytics.estimand.CrossWorldNode | polisyos.ir.analytics.estimand.CtfInterventionNode` | `yes` | `—` | `polisyos.ir.analytics.estimand.ConditionalInterventionNode`, `polisyos.ir.analytics.estimand.CounterfactualNode`, `polisyos.ir.analytics.estimand.CrossWorldNode`, `polisyos.ir.analytics.estimand.CtfInterventionNode`, `polisyos.ir.analytics.estimand.DistributionRef`, `polisyos.ir.analytics.estimand.ExpectationNode`, `polisyos.ir.analytics.estimand.IntegralNode`, `polisyos.ir.analytics.estimand.NestedCounterfactualNode`, `polisyos.ir.analytics.estimand.NuisanceNode`, `polisyos.ir.analytics.estimand.PathSpecificNode`, `polisyos.ir.analytics.estimand.ProductNode`, `polisyos.ir.analytics.estimand.ProxyAdjustmentNode`, `polisyos.ir.analytics.estimand.RatioNode`, `polisyos.ir.analytics.estimand.RecoveredDistNode`, `polisyos.ir.analytics.estimand.StochasticInterventionNode`, `polisyos.ir.analytics.estimand.SumNode` |
| `summation_vars` | `tuple[str]` | `yes` | `—` | — |

### `polisyos.ir.analytics.evidence_bundle.CompilationStep` { #polisyos-ir-analytics-evidence-bundle-compilationstep }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Records the transition from EstimandAST → ExecutorGraph.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `compiler_warnings` | `tuple[str]` | `no` | `()` | — |
| `estimand_shape` | `str` | `yes` | `—` | — |
| `estimation_strategy` | `str` | `yes` | `—` | — |
| `n_executor_nodes` | `int` | `yes` | `—` | — |
| `nuisance_components` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.evidence_bundle.DataProvenance` { #polisyos-ir-analytics-evidence-bundle-dataprovenance }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Provenance record for a single data source used in estimation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `availability_status` | `str` | `no` | `'available'` | — |
| `dataset_ref` | `str` | `yes` | `—` | — |
| `domain` | `str` | `no` | `'source'` | — |
| `n_obs` | `int | NoneType` | `no` | `—` | — |
| `quality_score` | `float` | `no` | `1.0` | — |

### `polisyos.ir.analytics.evidence_bundle.EstimationStep` { #polisyos-ir-analytics-evidence-bundle-estimationstep }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Records the execution of one MethodDagNode in the executor.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `backend` | `str` | `no` | `''` | — |
| `determinism_tier` | `str` | `no` | `''` | — |
| `is_nuisance` | `bool` | `no` | `False` | — |
| `method_fqn` | `str` | `yes` | `—` | — |
| `method_version` | `str | NoneType` | `no` | `—` | — |
| `node_id` | `str` | `yes` | `—` | — |
| `params_hash` | `str` | `no` | `''` | — |
| `wall_time_ms` | `float | NoneType` | `no` | `—` | — |
| `warnings` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.evidence_bundle.EvidenceBundle` { #polisyos-ir-analytics-evidence-bundle-evidencebundle }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.evidence_bundle.CompilationStep`, `polisyos.ir.analytics.evidence_bundle.DataProvenance`, `polisyos.ir.analytics.evidence_bundle.EstimationStep`, `polisyos.ir.analytics.evidence_bundle.ProofStep`, `polisyos.ir.refs.BoundsBundleRef`, `polisyos.ir.refs.DataReadinessReportRef`, `polisyos.ir.refs.NegativeCertificateRef`, `polisyos.ir.refs.ProofBundleRef`
- Summary: Machine-readable audit trail for a causal identification and estimation run.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `algorithm_version` | `str` | `no` | `''` | — |
| `bounds_bundle_ref` | `polisyos.ir.refs.BoundsBundleRef | NoneType` | `no` | `—` | `polisyos.ir.refs.BoundsBundleRef` |
| `compilation_steps` | `tuple[polisyos.ir.analytics.evidence_bundle.CompilationStep]` | `no` | `()` | `polisyos.ir.analytics.evidence_bundle.CompilationStep` |
| `created_at` | `str` | `no` | `''` | — |
| `data_provenance` | `tuple[polisyos.ir.analytics.evidence_bundle.DataProvenance]` | `no` | `()` | `polisyos.ir.analytics.evidence_bundle.DataProvenance` |
| `data_readiness_report_ref` | `polisyos.ir.refs.DataReadinessReportRef | NoneType` | `no` | `—` | `polisyos.ir.refs.DataReadinessReportRef` |
| `diagnostic_dashboard` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `diagnostic_scores` | `dict[str, float]` | `no` | `—` | — |
| `estimand_ast` | `dict[str, Any]` | `no` | `—` | — |
| `estimand_fingerprint` | `str` | `no` | `''` | — |
| `estimation_steps` | `tuple[polisyos.ir.analytics.evidence_bundle.EstimationStep]` | `no` | `()` | `polisyos.ir.analytics.evidence_bundle.EstimationStep` |
| `graph_fingerprint` | `str` | `no` | `''` | — |
| `identification_status` | `str` | `no` | `''` | — |
| `method_config` | `dict[str, Any]` | `no` | `—` | — |
| `negative_certificate_ref` | `polisyos.ir.refs.NegativeCertificateRef | NoneType` | `no` | `—` | `polisyos.ir.refs.NegativeCertificateRef` |
| `proof_bundle_ref` | `polisyos.ir.refs.ProofBundleRef | NoneType` | `no` | `—` | `polisyos.ir.refs.ProofBundleRef` |
| `proof_steps` | `tuple[polisyos.ir.analytics.evidence_bundle.ProofStep]` | `no` | `()` | `polisyos.ir.analytics.evidence_bundle.ProofStep` |
| `quality_report` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `query_str` | `str` | `yes` | `—` | — |
| `run_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.evidence_bundle.EvidenceFingerprintError` { #polisyos-ir-analytics-evidence-bundle-evidencefingerprinterror }

- Kind: `class`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Raised when audit evidence cannot be reduced to a stable fingerprint.

### `polisyos.ir.analytics.evidence_bundle.ProofStep` { #polisyos-ir-analytics-evidence-bundle-proofstep }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: A single step in a do-calculus / identification proof.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `applicable_theorem` | `str` | `no` | `''` | — |
| `description` | `str` | `yes` | `—` | — |
| `graph_state_after` | `str` | `no` | `''` | — |
| `graph_state_before` | `str` | `no` | `''` | — |
| `graph_subset` | `str` | `no` | `''` | — |
| `rule_formal_name` | `str` | `no` | `''` | — |
| `rule_name` | `str` | `yes` | `—` | — |
| `variables_affected` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.experiment_plan.ExperimentPlan` { #polisyos-ir-analytics-experiment-plan-experimentplan }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Minimum-cost experimental design plan.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `adjustment_set` | `frozenset[str] | NoneType` | `no` | `—` | — |
| `already_identified_observationally` | `bool` | `no` | `False` | — |
| `cost_estimate` | `float | NoneType` | `no` | `—` | — |
| `n_stages` | `int` | `no` | `1` | — |
| `query` | `str` | `yes` | `—` | — |
| `rationale` | `str` | `no` | `''` | — |
| `recommended_interventions` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.experiment_plan.OptimalAdjustmentResult` { #polisyos-ir-analytics-experiment-plan-optimaladjustmentresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Result of O-set computation (Henckel, Perković & Maathuis 2022).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `all_valid_adjustment_sets` | `list[frozenset[str]]` | `no` | `—` | — |
| `graphical_criterion_used` | `str` | `no` | `'henckel-2022-o-set'` | — |
| `o_set` | `frozenset[str]` | `yes` | `—` | — |
| `o_set_is_valid_backdoor` | `bool` | `no` | `True` | — |
| `outcome` | `str` | `yes` | `—` | — |
| `treatment` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.experiment_plan.OptimalIVResult` { #polisyos-ir-analytics-experiment-plan-optimalivresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Result of optimal instrument set selection.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `all_valid_iv_sets` | `list[frozenset[str]]` | `no` | `—` | — |
| `exclusion_restriction_verified` | `bool` | `no` | `True` | — |
| `optimal_iv_set` | `frozenset[str]` | `yes` | `—` | — |
| `outcome` | `str` | `yes` | `—` | — |
| `treatment` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.fairness.CausalFairnessReport` { #polisyos-ir-analytics-fairness-causalfairnessreport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.fairness.FairnessDecomposition`
- Summary: Full causal fairness audit result.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `counterfactual_fairness_satisfied` | `bool` | `yes` | `—` | — |
| `decomposition` | `polisyos.ir.analytics.fairness.FairnessDecomposition` | `yes` | `—` | `polisyos.ir.analytics.fairness.FairnessDecomposition` |
| `direct_discrimination` | `float` | `yes` | `—` | — |
| `indirect_discrimination` | `float` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `path_specific_fairness` | `dict[str, bool]` | `yes` | `—` | — |
| `primary_unfair_pathway` | `str | NoneType` | `yes` | `—` | — |
| `recommendation` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.analytics.fairness.FairnessDecomposition` { #polisyos-ir-analytics-fairness-fairnessdecomposition }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: TV = DE + IE + SE decomposition (Plecko & Bareinboim 2022, Theorem 1).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `de_ci` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `decomposition_residual` | `float` | `yes` | `—` | — |
| `direct_effect` | `float` | `yes` | `—` | — |
| `estimation_method` | `str` | `yes` | `—` | — |
| `ie_ci` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `indirect_effect` | `float` | `yes` | `—` | — |
| `mediators` | `tuple[str]` | `no` | `()` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `n_obs` | `int` | `yes` | `—` | — |
| `outcome` | `str` | `yes` | `—` | — |
| `protected_attribute` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `se_ci` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `spurious_effect` | `float` | `yes` | `—` | — |
| `tv` | `float` | `yes` | `—` | — |
| `tv_ci` | `tuple[float, float] | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.falsification_report.FalsificationReport` { #polisyos-ir-analytics-falsification-report-falsificationreport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.falsification_report.FalsificationTest`
- Summary: Aggregated results of all falsification tests run for a causal analysis.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `critical_failures` | `tuple[str]` | `no` | `()` | — |
| `n_failed` | `int` | `no` | `0` | — |
| `n_passed` | `int` | `no` | `0` | — |
| `overall_passed` | `bool` | `no` | `True` | — |
| `tests` | `tuple[polisyos.ir.analytics.falsification_report.FalsificationTest]` | `no` | `()` | `polisyos.ir.analytics.falsification_report.FalsificationTest` |

### `polisyos.ir.analytics.falsification_report.FalsificationTest` { #polisyos-ir-analytics-falsification-report-falsificationtest }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.falsification_report.FalsificationTestKind`
- Summary: Result of a single falsification / refutation test.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `effect_ratio` | `float | NoneType` | `no` | `—` | — |
| `interpretation` | `str` | `no` | `''` | — |
| `is_critical` | `bool` | `no` | `False` | — |
| `p_value` | `float | NoneType` | `no` | `—` | — |
| `passed` | `bool` | `yes` | `—` | — |
| `statistic` | `float | NoneType` | `no` | `—` | — |
| `test_kind` | `polisyos.ir.analytics.falsification_report.FalsificationTestKind` | `yes` | `—` | `polisyos.ir.analytics.falsification_report.FalsificationTestKind` |
| `test_name` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.falsification_report.FalsificationTestKind` { #polisyos-ir-analytics-falsification-report-falsificationtestkind }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Category of falsification / refutation test.

| Enum values |
|-------------|
| `placebo_treatment` |
| `random_common_cause` |
| `data_subset` |
| `bootstrap_refutation` |
| `independence_test` |
| `invariance_test` |
| `parallel_trends` |
| `exclusion_restriction` |

### `polisyos.ir.analytics.hte.FeatureImportance` { #polisyos-ir-analytics-hte-featureimportance }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:FeatureImportance`, `polisyos.ir:FeatureImportance`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Ranking signal for a feature used in heterogeneous-effect modeling.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `feature_name` | `str` | `yes` | `—` | — |
| `importance_rank` | `int` | `yes` | `—` | — |
| `importance_score` | `float` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `method` | `str` | `no` | `'tree_based'` | — |

### `polisyos.ir.analytics.hte.HTEResult` { #polisyos-ir-analytics-hte-hteresult }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:HTEResult`, `polisyos.ir:HTEResult`
- ABI snapshot: `hte_result` / `schemas/snapshots/ir/hte_result.schema.json`
- Compatibility mode: `full`
- References: `polisyos.ir.analytics.causal.CausalMethod`, `polisyos.ir.analytics.hte.FeatureImportance`, `polisyos.ir.analytics.hte.SubgroupEffect`
- Summary: Canonical artifact for heterogeneous treatment effect estimation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `ate` | `float` | `yes` | `—` | — |
| `ate_ci_lower` | `float` | `yes` | `—` | — |
| `ate_ci_upper` | `float` | `yes` | `—` | — |
| `ate_p_value` | `float | NoneType` | `no` | `—` | — |
| `cas_artifact_id` | `str | NoneType` | `no` | `—` | — |
| `cate_ci_lower_values` | `list[float]` | `no` | `—` | — |
| `cate_ci_upper_values` | `list[float]` | `no` | `—` | — |
| `cate_std_values` | `list[float]` | `no` | `—` | — |
| `cate_values` | `list[float]` | `no` | `—` | — |
| `causal_effect_report_ref` | `str | NoneType` | `no` | `—` | — |
| `confidence_level` | `float` | `no` | `0.95` | — |
| `econml_estimator_class` | `str` | `no` | `''` | — |
| `econml_params` | `dict[str, Any]` | `no` | `—` | — |
| `feature_display_map` | `dict[str, str]` | `no` | `—` | — |
| `feature_importances` | `list[polisyos.ir.analytics.hte.FeatureImportance]` | `no` | `—` | `polisyos.ir.analytics.hte.FeatureImportance` |
| `feature_names` | `list[str]` | `no` | `—` | — |
| `feature_transformations` | `dict[str, str]` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `method` | `polisyos.ir.analytics.causal.CausalMethod` | `yes` | `—` | `polisyos.ir.analytics.causal.CausalMethod` |
| `model_fit_metrics` | `dict[str, float]` | `no` | `—` | — |
| `n_control` | `int` | `no` | `0` | — |
| `n_features` | `int` | `no` | `0` | — |
| `n_samples` | `int` | `no` | `0` | — |
| `n_treated` | `int` | `no` | `0` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `subgroup_effects` | `list[polisyos.ir.analytics.hte.SubgroupEffect]` | `no` | `—` | `polisyos.ir.analytics.hte.SubgroupEffect` |

### `polisyos.ir.analytics.hte.PolicyRecommendation` { #polisyos-ir-analytics-hte-policyrecommendation }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:PolicyRecommendation`, `polisyos.ir:PolicyRecommendation`
- ABI snapshot: `policy_recommendation` / `schemas/snapshots/ir/policy_recommendation.schema.json`
- Compatibility mode: `full`
- References: `polisyos.ir.analytics.hte.TargetingRule`
- Summary: Budget-aware targeting recommendation derived from an HTE result.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `budget_constraint` | `float | NoneType` | `no` | `—` | — |
| `cas_artifact_id` | `str | NoneType` | `no` | `—` | — |
| `hte_result_ref` | `str | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `n_targeted_units` | `int` | `no` | `0` | — |
| `n_total_units` | `int` | `no` | `0` | — |
| `optimization_objective` | `str` | `no` | `'maximize_total_effect'` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `targeting_efficiency` | `float | NoneType` | `no` | `—` | — |
| `targeting_rules` | `list[polisyos.ir.analytics.hte.TargetingRule]` | `no` | `—` | `polisyos.ir.analytics.hte.TargetingRule` |
| `total_cost` | `float` | `no` | `0.0` | — |
| `total_expected_effect` | `float` | `no` | `0.0` | — |
| `tree_depth` | `int | NoneType` | `no` | `—` | — |
| `tree_n_leaves` | `int | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.hte.SubgroupEffect` { #polisyos-ir-analytics-hte-subgroupeffect }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:SubgroupEffect`, `polisyos.ir:SubgroupEffect`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Estimated conditional treatment effect for one labeled subgroup.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `cate_ci_lower` | `float` | `yes` | `—` | — |
| `cate_ci_upper` | `float` | `yes` | `—` | — |
| `cate_mean` | `float` | `yes` | `—` | — |
| `cate_std` | `float` | `yes` | `—` | — |
| `confidence_level` | `float` | `no` | `0.95` | — |
| `is_significant` | `bool` | `no` | `False` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `n_units` | `int` | `yes` | `—` | — |
| `p_value` | `float | NoneType` | `no` | `—` | — |
| `subgroup_id` | `str` | `yes` | `—` | — |
| `subgroup_label` | `str` | `yes` | `—` | — |
| `subgroup_label_human` | `str | NoneType` | `no` | `—` | — |
| `subgroup_query` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.hte.TargetingRule` { #polisyos-ir-analytics-hte-targetingrule }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:TargetingRule`, `polisyos.ir:TargetingRule`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Operational rule for targeting treatment to high-value units.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `cumulative_budget_share` | `float` | `yes` | `—` | — |
| `expected_cate` | `float` | `yes` | `—` | — |
| `expected_cost_per_unit` | `float` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `n_eligible_units` | `int` | `yes` | `—` | — |
| `predicate` | `str` | `yes` | `—` | — |
| `predicate_human` | `str | NoneType` | `no` | `—` | — |
| `priority` | `int` | `yes` | `—` | — |
| `rule_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.interference.ExposureMappingType` { #polisyos-ir-analytics-interference-exposuremappingtype }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: How neighborhood treatment is mapped to a unit's exposure level.

| Enum values |
|-------------|
| `fractional` |
| `threshold` |
| `count` |
| `kernel` |
| `bipartite` |

### `polisyos.ir.analytics.interference.InteractionComplex` { #polisyos-ir-analytics-interference-interactioncomplex }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.refs.ArtifactRefModel`
- Summary: Topology contract reserved for future hypergraph interference reasoning.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `exposure_operator_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `hyperedges` | `tuple[tuple[str]]` | `no` | `()` | — |
| `nodes` | `tuple[str]` | `yes` | `—` | — |
| `reduction_policy` | `Literal[pairwise_projection, cluster_projection, full_complex]` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `simplices` | `tuple[tuple[str]]` | `no` | `()` | — |

### `polisyos.ir.analytics.interference.InterferenceCertificate` { #polisyos-ir-analytics-interference-interferencecertificate }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Disclosure contract for topology-to-pairwise/cluster reduction behavior.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `exposure_assumptions` | `tuple[str]` | `no` | `()` | — |
| `fallback_mode` | `Literal[pairwise, clustered, unsupported]` | `yes` | `—` | — |
| `reduction_error_bound` | `float | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `supported_query_family` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.interference.InterferenceEffectDecomposition` { #polisyos-ir-analytics-interference-interferenceeffectdecomposition }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Full decomposition of treatment effects under interference.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `alpha_high` | `float` | `no` | `0.5` | — |
| `alpha_low` | `float` | `no` | `0.0` | — |
| `ci_direct` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `ci_spillover` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `ci_total` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `confidence_level` | `float` | `no` | `0.95` | — |
| `direct_effect` | `float` | `yes` | `—` | — |
| `indirect_effect` | `float | NoneType` | `no` | `—` | — |
| `interference_detected` | `bool` | `no` | `False` | — |
| `n_treated` | `int` | `yes` | `—` | — |
| `n_units` | `int` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `se_direct` | `float | NoneType` | `no` | `—` | — |
| `se_spillover` | `float | NoneType` | `no` | `—` | — |
| `se_total` | `float | NoneType` | `no` | `—` | — |
| `spillover_effect` | `float` | `yes` | `—` | — |
| `total_effect` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.interference.InterferenceMethod` { #polisyos-ir-analytics-interference-interferencemethod }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Identifies the interference estimator used.

| Enum values |
|-------------|
| `partial_interference_ipw` |
| `network_aipw` |
| `spatial_kernel` |
| `bipartite_interference` |

### `polisyos.ir.analytics.interference.NetworkInterferenceReport` { #polisyos-ir-analytics-interference-networkinterferencereport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.interference.ExposureMappingType`, `polisyos.ir.analytics.interference.InterferenceEffectDecomposition`, `polisyos.ir.analytics.interference.InterferenceMethod`
- Summary: Top-level result returned by all interference estimation methods.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `assumptions` | `dict[str, str]` | `no` | `—` | — |
| `average_cluster_size` | `float | NoneType` | `no` | `—` | — |
| `effects` | `polisyos.ir.analytics.interference.InterferenceEffectDecomposition | NoneType` | `no` | `—` | `polisyos.ir.analytics.interference.InterferenceEffectDecomposition` |
| `exposure_mapping` | `polisyos.ir.analytics.interference.ExposureMappingType` | `yes` | `—` | `polisyos.ir.analytics.interference.ExposureMappingType` |
| `exposure_mapping_params` | `dict[str, Any]` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `method` | `polisyos.ir.analytics.interference.InterferenceMethod` | `yes` | `—` | `polisyos.ir.analytics.interference.InterferenceMethod` |
| `n_clusters` | `int | NoneType` | `no` | `—` | — |
| `n_treated` | `int` | `yes` | `—` | — |
| `n_units` | `int` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `status` | `Literal[success, input_invalid, assumption_failed, numerical_failure]` | `yes` | `—` | — |
| `status_reason` | `str | NoneType` | `no` | `—` | — |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.invariance.EnvironmentShiftType` { #polisyos-ir-analytics-invariance-environmentshifttype }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:EnvironmentShiftType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Distribution shift classes observed across environments.

| Enum values |
|-------------|
| `covariate` |
| `interventional` |
| `selection` |
| `temporal` |

### `polisyos.ir.analytics.invariance.EnvironmentSpec` { #polisyos-ir-analytics-invariance-environmentspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.invariance.EnvironmentShiftType`
- Summary: One observed environment or deployment regime.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `context_features` | `tuple[str]` | `no` | `()` | — |
| `environment_id` | `str` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `role` | `str` | `no` | `'source'` | — |
| `shift_type` | `polisyos.ir.analytics.invariance.EnvironmentShiftType` | `yes` | `—` | `polisyos.ir.analytics.invariance.EnvironmentShiftType` |

### `polisyos.ir.analytics.invariance.InvarianceMethod` { #polisyos-ir-analytics-invariance-invariancemethod }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:InvarianceMethod`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Frontier multi-environment causal methods.

| Enum values |
|-------------|
| `icp` |
| `irm` |
| `anchor_regression` |
| `environment_aware_discovery` |

### `polisyos.ir.analytics.invariance.InvarianceResult` { #polisyos-ir-analytics-invariance-invarianceresult }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:InvarianceResult`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.invariance.InvarianceMethod`, `polisyos.ir.analytics.invariance.InvarianceVerdict`, `polisyos.ir.analytics.invariance.InvariantMechanismHypothesis`
- Summary: Frozen result contract for multi-environment invariance analysis.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `accepted_hypothesis_ids` | `tuple[str]` | `no` | `()` | — |
| `contract_id` | `str` | `yes` | `—` | — |
| `environment_risks` | `dict[str, float]` | `no` | `—` | — |
| `hypotheses` | `list[polisyos.ir.analytics.invariance.InvariantMechanismHypothesis]` | `no` | `—` | `polisyos.ir.analytics.invariance.InvariantMechanismHypothesis` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `method` | `polisyos.ir.analytics.invariance.InvarianceMethod` | `yes` | `—` | `polisyos.ir.analytics.invariance.InvarianceMethod` |
| `rejected_hypothesis_ids` | `tuple[str]` | `no` | `()` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `verdict` | `polisyos.ir.analytics.invariance.InvarianceVerdict` | `yes` | `—` | `polisyos.ir.analytics.invariance.InvarianceVerdict` |
| `warnings` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.invariance.InvarianceVerdict` { #polisyos-ir-analytics-invariance-invarianceverdict }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:InvarianceVerdict`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Outcome of an invariance evaluation run.

| Enum values |
|-------------|
| `accepted` |
| `partial` |
| `rejected` |
| `inconclusive` |

### `polisyos.ir.analytics.invariance.InvariantMechanismHypothesis` { #polisyos-ir-analytics-invariance-invariantmechanismhypothesis }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: One hypothesis about an invariant mechanism across environments.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `hypothesis_id` | `str` | `yes` | `—` | — |
| `invariant_parents` | `tuple[str]` | `no` | `()` | — |
| `notes` | `tuple[str]` | `no` | `()` | — |
| `score` | `float | NoneType` | `no` | `—` | — |
| `target_variable` | `str` | `yes` | `—` | — |
| `violating_environments` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.invariance.MultiEnvironmentCausalContract` { #polisyos-ir-analytics-invariance-multienvironmentcausalcontract }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:MultiEnvironmentCausalContract`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.invariance.EnvironmentSpec`, `polisyos.ir.analytics.invariance.InvarianceMethod`
- Summary: Contract surface for multi-environment causal identification.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `assumptions` | `tuple[str]` | `no` | `()` | — |
| `contract_id` | `str` | `yes` | `—` | — |
| `environments` | `list[polisyos.ir.analytics.invariance.EnvironmentSpec]` | `yes` | `—` | `polisyos.ir.analytics.invariance.EnvironmentSpec` |
| `intervention_field` | `str | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `method` | `polisyos.ir.analytics.invariance.InvarianceMethod` | `yes` | `—` | `polisyos.ir.analytics.invariance.InvarianceMethod` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `target_variable` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.knowledge_base.DataKnowledgeBase` { #polisyos-ir-analytics-knowledge-base-dataknowledgebase }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.knowledge_base.DatasetEntry`
- Summary: Registry of available datasets / probability distributions across domains.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `datasets` | `tuple[polisyos.ir.analytics.knowledge_base.DatasetEntry]` | `no` | `()` | `polisyos.ir.analytics.knowledge_base.DatasetEntry` |

### `polisyos.ir.analytics.knowledge_base.DatasetEntry` { #polisyos-ir-analytics-knowledge-base-datasetentry }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.estimand.DistributionDomain`, `polisyos.ir.analytics.knowledge_base.DistributionAvailability`
- Summary: Describes a single available dataset / distribution in some domain.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `availability` | `polisyos.ir.analytics.knowledge_base.DistributionAvailability` | `no` | `<DistributionAvailability.AVAILABLE: 'available'>` | `polisyos.ir.analytics.knowledge_base.DistributionAvailability` |
| `available_interventions` | `tuple[tuple[str]]` | `no` | `()` | — |
| `dataset_ref` | `str` | `yes` | `—` | — |
| `domain` | `polisyos.ir.analytics.estimand.DistributionDomain` | `yes` | `—` | `polisyos.ir.analytics.estimand.DistributionDomain` |
| `n_obs` | `int | NoneType` | `no` | `—` | — |
| `quality_score` | `float` | `no` | `1.0` | — |
| `variables` | `tuple[str]` | `yes` | `—` | — |

### `polisyos.ir.analytics.knowledge_base.DistributionAvailability` { #polisyos-ir-analytics-knowledge-base-distributionavailability }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: How well a required distribution is covered by a known dataset.

| Enum values |
|-------------|
| `available` |
| `partial` |
| `proxy_only` |
| `unavailable` |

### `polisyos.ir.analytics.literature.ArticleExtractionResult` { #polisyos-ir-analytics-literature-articleextractionresult }

- Kind: `pydantic_model`
- Public status: `snapshot_only`
- Current version: `1.5`
- Exported from: —
- ABI snapshot: `article_extraction_result` / `schemas/snapshots/ir/article_extraction_result.schema.json`
- Compatibility mode: `backward`
- References: `polisyos.ir.analytics.context.ContextProfile`, `polisyos.ir.analytics.literature.BoundaryCondition`, `polisyos.ir.analytics.literature.CausalClaim`, `polisyos.ir.analytics.literature.ContextAttribute`, `polisyos.ir.analytics.literature.EvidenceParameter`, `polisyos.ir.analytics.literature.EvidenceSpan`, `polisyos.ir.analytics.literature.EvidenceStrength`, `polisyos.ir.analytics.literature.HeterogeneityResult`, `polisyos.ir.analytics.literature.Mechanism`, `polisyos.ir.analytics.literature.ModerationEdge`, `polisyos.ir.analytics.literature.PaperKind`, `polisyos.ir.analytics.literature.SourceBasis`, `polisyos.ir.analytics.literature.TextQuality`
- Summary: Primary IR contract for literature extraction pipeline.
- Declared readable versions: `1.0`

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `boundary_conditions` | `list[polisyos.ir.analytics.literature.BoundaryCondition]` | `no` | `—` | `polisyos.ir.analytics.literature.BoundaryCondition` |
| `causal_claims` | `list[polisyos.ir.analytics.literature.CausalClaim]` | `no` | `—` | `polisyos.ir.analytics.literature.CausalClaim` |
| `citation_summary` | `str` | `no` | `''` | — |
| `cited_by_count` | `int` | `no` | `0` | — |
| `context_attributes` | `list[polisyos.ir.analytics.literature.ContextAttribute]` | `no` | `—` | `polisyos.ir.analytics.literature.ContextAttribute` |
| `doi` | `str` | `no` | `''` | — |
| `empirical_parameters` | `list[polisyos.ir.analytics.literature.EvidenceParameter]` | `no` | `—` | `polisyos.ir.analytics.literature.EvidenceParameter` |
| `external_validity_assessment` | `str` | `no` | `''` | — |
| `extraction_confidence` | `float` | `yes` | `—` | — |
| `extraction_cost_usd` | `float` | `no` | `0.0` | — |
| `extraction_model` | `str` | `yes` | `—` | — |
| `extraction_timestamp` | `str` | `yes` | `—` | — |
| `extraction_warnings` | `list[str]` | `no` | `—` | — |
| `heterogeneity_results` | `list[polisyos.ir.analytics.literature.HeterogeneityResult]` | `no` | `—` | `polisyos.ir.analytics.literature.HeterogeneityResult` |
| `llm_error_class` | `str` | `no` | `''` | — |
| `mechanisms` | `list[polisyos.ir.analytics.literature.Mechanism]` | `no` | `—` | `polisyos.ir.analytics.literature.Mechanism` |
| `method_spans` | `list[polisyos.ir.analytics.literature.EvidenceSpan]` | `no` | `—` | `polisyos.ir.analytics.literature.EvidenceSpan` |
| `methodology` | `str` | `no` | `''` | — |
| `methodology_enum` | `polisyos.ir.analytics.literature.EvidenceStrength` | `no` | `<EvidenceStrength.UNKNOWN: 'unknown'>` | `polisyos.ir.analytics.literature.EvidenceStrength` |
| `moderation_edges` | `list[polisyos.ir.analytics.literature.ModerationEdge]` | `no` | `—` | `polisyos.ir.analytics.literature.ModerationEdge` |
| `openalex_id` | `str` | `yes` | `—` | — |
| `paper_kind` | `polisyos.ir.analytics.literature.PaperKind` | `no` | `<PaperKind.EMPIRICAL_CAUSAL: 'empirical_causal'>` | `polisyos.ir.analytics.literature.PaperKind` |
| `paper_relevance` | `bool` | `no` | `True` | — |
| `paper_relevance_reason` | `str` | `no` | `''` | — |
| `provider_finish_reason` | `str` | `no` | `''` | — |
| `provider_latency_ms` | `float` | `no` | `0.0` | — |
| `publication_year` | `int | NoneType` | `no` | `—` | — |
| `reconciliation_diagnostics` | `dict[str, Any]` | `no` | `—` | — |
| `sample_size` | `int | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.5'` | — |
| `screening_cost_usd` | `float` | `no` | `0.0` | — |
| `source_basis` | `polisyos.ir.analytics.literature.SourceBasis` | `no` | `<SourceBasis.FULLTEXT: 'fulltext'>` | `polisyos.ir.analytics.literature.SourceBasis` |
| `source_context` | `polisyos.ir.analytics.context.ContextProfile | NoneType` | `no` | `—` | `polisyos.ir.analytics.context.ContextProfile` |
| `supporting_spans` | `list[polisyos.ir.analytics.literature.EvidenceSpan]` | `no` | `—` | `polisyos.ir.analytics.literature.EvidenceSpan` |
| `text_quality` | `polisyos.ir.analytics.literature.TextQuality` | `no` | `<TextQuality.EXTRACTED_FULLTEXT: 'extracted_fulltext'>` | `polisyos.ir.analytics.literature.TextQuality` |
| `title` | `str` | `yes` | `—` | — |
| `token_count_completion` | `int` | `no` | `0` | — |
| `token_count_prompt` | `int` | `no` | `0` | — |
| `truncated_output` | `bool` | `no` | `False` | — |
| `year` | `int | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.literature.BoundaryCondition` { #polisyos-ir-analytics-literature-boundarycondition }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Boundary condition public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `condition_type` | `str` | `no` | `''` | — |
| `confidence` | `float` | `no` | `0.0` | — |
| `consequence_if_violated` | `str` | `no` | `''` | — |
| `operator` | `str` | `no` | `''` | — |
| `required_value` | `str | float | NoneType` | `no` | `—` | — |
| `scope_text` | `str` | `no` | `''` | — |
| `threshold_value` | `str` | `no` | `''` | — |
| `variable` | `str` | `no` | `''` | — |
| `violated_by` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.literature.CausalClaim` { #polisyos-ir-analytics-literature-causalclaim }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.literature.CausalDirection`, `polisyos.ir.analytics.literature.ClaimExplicitness`, `polisyos.ir.analytics.literature.ClaimType`, `polisyos.ir.analytics.literature.DesignFamily`, `polisyos.ir.analytics.literature.EvidenceSpan`, `polisyos.ir.analytics.literature.EvidenceStrength`, `polisyos.ir.analytics.literature.IdentificationStrategy`, `polisyos.ir.analytics.literature.SourceBasis`, `polisyos.ir.analytics.literature.UncertaintyBudget`
- Summary: Causal claim public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `cause_variable` | `str` | `yes` | `—` | — |
| `claim_explicitness` | `polisyos.ir.analytics.literature.ClaimExplicitness` | `no` | `<ClaimExplicitness.UNCLEAR: 'unclear'>` | `polisyos.ir.analytics.literature.ClaimExplicitness` |
| `claim_extraction_confidence` | `float | NoneType` | `no` | `—` | — |
| `claim_id` | `str` | `no` | `''` | — |
| `claim_text` | `str` | `no` | `''` | — |
| `claim_type` | `polisyos.ir.analytics.literature.ClaimType` | `no` | `<ClaimType.UNCLEAR: 'unclear'>` | `polisyos.ir.analytics.literature.ClaimType` |
| `counterevidence_notes` | `str` | `no` | `''` | — |
| `design_family_hint` | `polisyos.ir.analytics.literature.DesignFamily` | `no` | `<DesignFamily.UNCLEAR: 'unclear'>` | `polisyos.ir.analytics.literature.DesignFamily` |
| `design_quality_tier` | `int | NoneType` | `no` | `—` | — |
| `direction` | `polisyos.ir.analytics.literature.CausalDirection` | `no` | `<CausalDirection.MIXED: 'mixed'>` | `polisyos.ir.analytics.literature.CausalDirection` |
| `effect_size` | `float | NoneType` | `no` | `—` | — |
| `effect_variable` | `str` | `yes` | `—` | — |
| `evidence_strength` | `polisyos.ir.analytics.literature.EvidenceStrength` | `no` | `<EvidenceStrength.UNKNOWN: 'unknown'>` | `polisyos.ir.analytics.literature.EvidenceStrength` |
| `extraction_warnings` | `list[str]` | `no` | `—` | — |
| `identification_strategy` | `polisyos.ir.analytics.literature.IdentificationStrategy | NoneType` | `no` | `—` | `polisyos.ir.analytics.literature.IdentificationStrategy` |
| `magnitude_qualitative` | `str | NoneType` | `no` | `—` | — |
| `method_span_ids` | `list[str]` | `no` | `—` | — |
| `method_spans` | `list[polisyos.ir.analytics.literature.EvidenceSpan]` | `no` | `—` | `polisyos.ir.analytics.literature.EvidenceSpan` |
| `publish_blockers` | `list[str]` | `no` | `—` | — |
| `publish_to_graph` | `bool` | `no` | `False` | — |
| `scope_conditions` | `list[str]` | `no` | `—` | — |
| `source_basis` | `polisyos.ir.analytics.literature.SourceBasis` | `no` | `<SourceBasis.FULLTEXT: 'fulltext'>` | `polisyos.ir.analytics.literature.SourceBasis` |
| `span_contamination_detected` | `bool` | `no` | `False` | — |
| `strong_design_evidence` | `bool` | `no` | `False` | — |
| `supporting_span_ids` | `list[str]` | `no` | `—` | — |
| `supporting_spans` | `list[polisyos.ir.analytics.literature.EvidenceSpan]` | `no` | `—` | `polisyos.ir.analytics.literature.EvidenceSpan` |
| `uncertainty_budget` | `polisyos.ir.analytics.literature.UncertaintyBudget | NoneType` | `no` | `—` | `polisyos.ir.analytics.literature.UncertaintyBudget` |

### `polisyos.ir.analytics.literature.CausalCredibility` { #polisyos-ir-analytics-literature-causalcredibility }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Causal credibility public type.

| Enum values |
|-------------|
| `strong` |
| `moderate` |
| `weak` |
| `not_causal` |
| `unclear` |

### `polisyos.ir.analytics.literature.CausalDirection` { #polisyos-ir-analytics-literature-causaldirection }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Causal direction public type.

| Enum values |
|-------------|
| `positive` |
| `negative` |
| `null` |
| `mixed` |
| `ambiguous` |
| `non_linear` |

### `polisyos.ir.analytics.literature.ClaimAdjudicationResult` { #polisyos-ir-analytics-literature-claimadjudicationresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.literature.CausalCredibility`, `polisyos.ir.analytics.literature.ClaimType`, `polisyos.ir.analytics.literature.DesignFamily`, `polisyos.ir.analytics.literature.RiskOfBias`, `polisyos.ir.analytics.literature.SourceBasis`, `polisyos.ir.analytics.literature.SupportStatus`
- Summary: Claim-level causal adjudication contract.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `adjudication_confidence` | `float` | `no` | `0.0` | — |
| `adjudication_notes` | `str` | `no` | `''` | — |
| `causal_credibility` | `polisyos.ir.analytics.literature.CausalCredibility` | `no` | `<CausalCredibility.UNCLEAR: 'unclear'>` | `polisyos.ir.analytics.literature.CausalCredibility` |
| `cause_variable` | `str` | `yes` | `—` | — |
| `claim_id` | `str` | `yes` | `—` | — |
| `claim_type` | `polisyos.ir.analytics.literature.ClaimType` | `no` | `<ClaimType.ASSOCIATION: 'association'>` | `polisyos.ir.analytics.literature.ClaimType` |
| `claim_type_confidence` | `float | NoneType` | `no` | `—` | — |
| `claim_validity_score` | `float` | `no` | `0.0` | — |
| `consensus_passes` | `int` | `no` | `1` | — |
| `consensus_stability` | `float` | `no` | `1.0` | — |
| `design_family` | `polisyos.ir.analytics.literature.DesignFamily` | `no` | `<DesignFamily.UNCLEAR: 'unclear'>` | `polisyos.ir.analytics.literature.DesignFamily` |
| `design_family_confidence` | `float | NoneType` | `no` | `—` | — |
| `direction_confidence` | `float | NoneType` | `no` | `—` | — |
| `effect_variable` | `str` | `yes` | `—` | — |
| `intra_paper_contradiction` | `bool` | `no` | `False` | — |
| `openalex_id` | `str` | `yes` | `—` | — |
| `paper_asserts_causality_score` | `float` | `no` | `0.0` | — |
| `publishable_edge` | `bool` | `no` | `False` | — |
| `risk_of_bias` | `polisyos.ir.analytics.literature.RiskOfBias` | `no` | `<RiskOfBias.UNCLEAR: 'unclear'>` | `polisyos.ir.analytics.literature.RiskOfBias` |
| `source_basis` | `polisyos.ir.analytics.literature.SourceBasis` | `no` | `<SourceBasis.FULLTEXT: 'fulltext'>` | `polisyos.ir.analytics.literature.SourceBasis` |
| `support_status` | `polisyos.ir.analytics.literature.SupportStatus` | `no` | `<SupportStatus.INSUFFICIENT: 'insufficient'>` | `polisyos.ir.analytics.literature.SupportStatus` |

### `polisyos.ir.analytics.literature.ClaimExplicitness` { #polisyos-ir-analytics-literature-claimexplicitness }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Claim explicitness public type.

| Enum values |
|-------------|
| `explicit` |
| `implicit` |
| `unclear` |

### `polisyos.ir.analytics.literature.ClaimType` { #polisyos-ir-analytics-literature-claimtype }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Claim type public type.

| Enum values |
|-------------|
| `causal_claim` |
| `causal_assertion` |
| `associative` |
| `association` |
| `mechanism` |
| `descriptive` |
| `normative` |
| `review_summary` |
| `unclear` |
| `not_applicable` |

### `polisyos.ir.analytics.literature.ContextAttribute` { #polisyos-ir-analytics-literature-contextattribute }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.literature.EvidenceSpan`
- Summary: A context attribute extracted from literature (Track B).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `attribute_name` | `str` | `yes` | `—` | — |
| `canonical_name` | `str` | `no` | `''` | — |
| `confidence` | `float` | `no` | `0.5` | — |
| `country_codes` | `list[str]` | `no` | `—` | — |
| `evidence_spans` | `list[polisyos.ir.analytics.literature.EvidenceSpan]` | `no` | `—` | `polisyos.ir.analytics.literature.EvidenceSpan` |
| `measurement_method` | `str` | `no` | `''` | — |
| `time_period` | `str` | `no` | `''` | — |
| `unit` | `str | NoneType` | `no` | `—` | — |
| `value` | `float | NoneType` | `no` | `—` | — |
| `value_qualitative` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.literature.DesignFamily` { #polisyos-ir-analytics-literature-designfamily }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Design family public type.

| Enum values |
|-------------|
| `rct` |
| `iv` |
| `did` |
| `rdd` |
| `synthetic_control` |
| `event_study` |
| `quasi_experimental_other` |
| `quasi_experimental_did` |
| `quasi_experimental_rdd` |
| `panel_fe` |
| `ols` |
| `ols_cross_sectional` |
| `meta_analysis` |
| `review` |
| `review_narrative` |
| `review_meta_analysis` |
| `theoretical` |
| `structural_model` |
| `time_series_cointegration` |
| `unclear` |

### `polisyos.ir.analytics.literature.EnvironmentAuditReport` { #polisyos-ir-analytics-literature-environmentauditreport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Environment audit report data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `icp_p_values` | `dict[str, float]` | `no` | `—` | — |
| `icp_passed` | `bool | NoneType` | `no` | `—` | — |
| `icp_run` | `bool` | `no` | `False` | — |
| `invariant_features` | `list[int]` | `no` | `—` | — |
| `ks_p_values` | `dict[str, float]` | `no` | `—` | — |
| `ks_passed` | `bool | NoneType` | `no` | `—` | — |
| `ks_rejected_variables` | `list[int]` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `n_environments` | `int` | `no` | `0` | — |
| `provenance_refs` | `list[str]` | `no` | `—` | — |
| `status` | `Literal[ok, warning, skipped, degraded]` | `no` | `'skipped'` | — |
| `variant_features` | `list[int]` | `no` | `—` | — |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.literature.EvidenceParameter` { #polisyos-ir-analytics-literature-evidenceparameter }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.literature.EvidenceStrength`, `polisyos.ir.analytics.literature.ParameterType`
- Summary: Evidence parameter public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `aggregation_level` | `str` | `no` | `''` | — |
| `confidence_interval` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `display_name` | `str` | `no` | `''` | — |
| `evidence_strength` | `polisyos.ir.analytics.literature.EvidenceStrength` | `no` | `<EvidenceStrength.UNKNOWN: 'unknown'>` | `polisyos.ir.analytics.literature.EvidenceStrength` |
| `geographic_scope` | `str` | `no` | `''` | — |
| `heterogeneity_note` | `str | NoneType` | `no` | `—` | — |
| `name` | `str` | `yes` | `—` | — |
| `parameter_type` | `polisyos.ir.analytics.literature.ParameterType` | `no` | `<ParameterType.QUANTITATIVE: 'quantitative'>` | `polisyos.ir.analytics.literature.ParameterType` |
| `std_error` | `float | NoneType` | `no` | `—` | — |
| `subgroup_estimates` | `dict[str, float]` | `no` | `—` | — |
| `time_period` | `str` | `no` | `''` | — |
| `transfer_conditions` | `list[str]` | `no` | `—` | — |
| `transferability` | `str` | `no` | `'unknown'` | — |
| `unit` | `str | NoneType` | `no` | `—` | — |
| `value` | `float | NoneType` | `no` | `—` | — |
| `value_qualitative` | `str | NoneType` | `no` | `—` | — |
| `value_range` | `tuple[float, float] | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.literature.EvidenceSpan` { #polisyos-ir-analytics-literature-evidencespan }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Evidence span public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `score` | `float` | `no` | `0.0` | — |
| `section` | `str` | `no` | `''` | — |
| `sentence_index` | `int | NoneType` | `no` | `—` | — |
| `span_id` | `str` | `no` | `''` | — |
| `text` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.literature.EvidenceStrength` { #polisyos-ir-analytics-literature-evidencestrength }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Evidence strength public type.

| Enum values |
|-------------|
| `rct` |
| `quasi_natural` |
| `quasi_natural_event` |
| `meta_analysis` |
| `panel_fe` |
| `structural` |
| `observational` |
| `cross_sectional` |
| `theoretical` |
| `unknown` |

### `polisyos.ir.analytics.literature.HeterogeneityResult` { #polisyos-ir-analytics-literature-heterogeneityresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Result of a heterogeneity/moderation test within a single study.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `confidence` | `float | NoneType` | `no` | `—` | — |
| `dimension` | `str` | `no` | `''` | — |
| `finding` | `str` | `no` | `''` | — |
| `interaction_coefficient` | `float | NoneType` | `no` | `—` | — |
| `interaction_pvalue` | `float | NoneType` | `no` | `—` | — |
| `moderator` | `str` | `yes` | `—` | — |
| `subgroup_effects` | `dict[str, float]` | `no` | `—` | — |

### `polisyos.ir.analytics.literature.IdentificationStrategy` { #polisyos-ir-analytics-literature-identificationstrategy }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: How a causal effect was identified (instrument, design assumptions, etc.).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `design_assumptions` | `list[str]` | `no` | `—` | — |
| `exclusion_restrictions` | `list[str]` | `no` | `—` | — |
| `identification_confidence` | `float | NoneType` | `no` | `—` | — |
| `identification_method` | `str` | `no` | `''` | — |
| `instrument` | `str` | `no` | `''` | — |

### `polisyos.ir.analytics.literature.LiteratureCausalPrior` { #polisyos-ir-analytics-literature-literaturecausalprior }

- Kind: `pydantic_model`
- Public status: `snapshot_only`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `literature_causal_prior` / `schemas/snapshots/ir/literature_causal_prior.schema.json`
- Compatibility mode: `full`
- References: `polisyos.ir.analytics.literature.EnvironmentAuditReport`, `polisyos.ir.analytics.literature.LiteratureEdgePrior`
- Summary: Literature causal prior public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `edges` | `list[polisyos.ir.analytics.literature.LiteratureEdgePrior]` | `no` | `—` | `polisyos.ir.analytics.literature.LiteratureEdgePrior` |
| `environment_audit` | `polisyos.ir.analytics.literature.EnvironmentAuditReport | NoneType` | `no` | `—` | `polisyos.ir.analytics.literature.EnvironmentAuditReport` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `skg_snapshot_ref` | `str | NoneType` | `no` | `—` | — |
| `skg_version_id` | `int | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.literature.LiteratureEdgePrior` { #polisyos-ir-analytics-literature-literatureedgeprior }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.literature.CausalDirection`, `polisyos.ir.analytics.literature.EvidenceStrength`
- Summary: Literature edge prior public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `article_refs` | `list[str]` | `no` | `—` | — |
| `confidence` | `float` | `yes` | `—` | — |
| `direction` | `polisyos.ir.analytics.literature.CausalDirection` | `no` | `<CausalDirection.MIXED: 'mixed'>` | `polisyos.ir.analytics.literature.CausalDirection` |
| `dst` | `str` | `yes` | `—` | — |
| `evidence_strength` | `polisyos.ir.analytics.literature.EvidenceStrength` | `no` | `<EvidenceStrength.UNKNOWN: 'unknown'>` | `polisyos.ir.analytics.literature.EvidenceStrength` |
| `meta_effect_size` | `float | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `n_articles` | `int` | `no` | `0` | — |
| `scope_conditions` | `list[str]` | `no` | `—` | — |
| `src` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.literature.Mechanism` { #polisyos-ir-analytics-literature-mechanism }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Mechanism public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `description` | `str` | `yes` | `—` | — |
| `evidence_type` | `str` | `no` | `''` | — |
| `mediating_variables` | `list[str]` | `no` | `—` | — |
| `theoretical_framework` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.literature.ModerationEdge` { #polisyos-ir-analytics-literature-moderationedge }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: A context variable that moderates a causal edge (Track C).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `alignment_source` | `str` | `no` | `''` | — |
| `base_cause` | `str` | `yes` | `—` | — |
| `base_claim_id` | `str | NoneType` | `no` | `—` | — |
| `base_effect` | `str` | `yes` | `—` | — |
| `confidence` | `float` | `no` | `0.5` | — |
| `direction_of_moderation` | `str` | `no` | `''` | — |
| `evidence_count` | `int` | `no` | `1` | — |
| `evidence_text` | `str` | `no` | `''` | — |
| `interaction_pvalue` | `float | NoneType` | `no` | `—` | — |
| `match_quality` | `str` | `no` | `''` | — |
| `moderator` | `str` | `yes` | `—` | — |
| `quantitative_interaction` | `float | NoneType` | `no` | `—` | — |
| `source_openalex_ids` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.literature.PaperKind` { #polisyos-ir-analytics-literature-paperkind }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Paper kind public type.

| Enum values |
|-------------|
| `empirical_causal` |
| `context_characterization` |
| `heterogeneity_analysis` |
| `review_systematic` |
| `theoretical` |
| `descriptive` |
| `mixed` |

### `polisyos.ir.analytics.literature.ParameterType` { #polisyos-ir-analytics-literature-parametertype }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Parameter type public type.

| Enum values |
|-------------|
| `quantitative` |
| `qualitative` |
| `ordinal` |
| `distributional` |

### `polisyos.ir.analytics.literature.ReconciliationDiagnostics` { #polisyos-ir-analytics-literature-reconciliationdiagnostics }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Reconciliation diagnostics public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `curl_norm` | `float` | `no` | `0.0` | — |
| `cyclic_inconsistency_norm` | `float` | `no` | `0.0` | — |
| `d0_shape` | `tuple[int, int]` | `no` | `(0, 0)` | — |
| `d1_shape` | `tuple[int, int]` | `no` | `(0, 0)` | — |
| `delta0_shape` | `tuple[int, int]` | `no` | `(0, 0)` | — |
| `delta1_shape` | `tuple[int, int]` | `no` | `(0, 0)` | — |
| `diagnostics_truncated` | `bool` | `no` | `False` | — |
| `gradient_norm` | `float` | `no` | `0.0` | — |
| `harmonic_norm` | `float` | `no` | `0.0` | — |
| `irreducible_conflict_norm` | `float` | `no` | `0.0` | — |
| `n_components` | `int` | `no` | `0` | — |
| `n_edges` | `int` | `no` | `0` | — |
| `n_sources` | `int` | `no` | `0` | — |
| `n_triangles` | `int` | `no` | `0` | — |
| `operators` | `dict[str, Any]` | `no` | `—` | — |
| `truncation_reason` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.literature.RiskOfBias` { #polisyos-ir-analytics-literature-riskofbias }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Risk of bias public type.

| Enum values |
|-------------|
| `low` |
| `moderate` |
| `serious` |
| `critical` |
| `unclear` |

### `polisyos.ir.analytics.literature.SourceBasis` { #polisyos-ir-analytics-literature-sourcebasis }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Source basis public type.

| Enum values |
|-------------|
| `fulltext` |
| `abstract_only` |

### `polisyos.ir.analytics.literature.SupportStatus` { #polisyos-ir-analytics-literature-supportstatus }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Support status public type.

| Enum values |
|-------------|
| `supported` |
| `mixed` |
| `counterevidence` |
| `insufficient` |
| `insufficient_evidence` |
| `not_applicable` |

### `polisyos.ir.analytics.literature.TextQuality` { #polisyos-ir-analytics-literature-textquality }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Text quality public type.

| Enum values |
|-------------|
| `structured_fulltext` |
| `extracted_fulltext` |
| `abstract_only` |
| `degraded` |

### `polisyos.ir.analytics.literature.UncertaintyBudget` { #polisyos-ir-analytics-literature-uncertaintybudget }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Three-axis uncertainty decomposition for a causal estimate.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `conflict_residual` | `float` | `no` | `0.0` | — |
| `graph_uncertainty` | `float` | `no` | `0.0` | — |
| `sampling_uncertainty` | `float` | `no` | `0.0` | — |

### `polisyos.ir.analytics.mediation_effects.MediationDecomposition` { #polisyos-ir-analytics-mediation-effects-mediationdecomposition }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Full mediation decomposition: NDE, NIE, total effect.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `cde` | `float | NoneType` | `no` | `—` | — |
| `estimation_method` | `str` | `no` | `'eif_cross_fit'` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `n_folds` | `int` | `no` | `2` | — |
| `n_obs` | `int` | `no` | `0` | — |
| `nde` | `float` | `yes` | `—` | — |
| `nde_ci` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `nde_se` | `float | NoneType` | `no` | `—` | — |
| `nie` | `float` | `yes` | `—` | — |
| `nie_ci` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `nie_se` | `float | NoneType` | `no` | `—` | — |
| `proportion_mediated` | `float | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `sensitivity_nde` | `tuple[float] | NoneType` | `no` | `—` | — |
| `sensitivity_nie` | `tuple[float] | NoneType` | `no` | `—` | — |
| `sensitivity_rho_range` | `tuple[float] | NoneType` | `no` | `—` | — |
| `total_effect` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.mediation_effects.PathSpecificQuery` { #polisyos-ir-analytics-mediation-effects-pathspecificquery }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Query specification for path-specific effects.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `active_paths` | `tuple[tuple[str]]` | `no` | `()` | — |
| `active_treatment` | `float` | `no` | `1.0` | — |
| `fixed_paths` | `tuple[tuple[str]]` | `no` | `()` | — |
| `mediators` | `tuple[str]` | `no` | `()` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `outcome` | `str` | `yes` | `—` | — |
| `reference_treatment` | `float` | `no` | `0.0` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `treatment` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.mgraph.MGraphMetadata` { #polisyos-ir-analytics-mgraph-mgraphmetadata }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.mgraph.ProxyNode`, `polisyos.ir.analytics.mgraph.RNode`
- Summary: Semantic metadata for a CausalGraphModel with graph_type=MGRAPH.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `fully_observed_vars` | `tuple[str]` | `no` | `()` | — |
| `proxy_nodes` | `tuple[polisyos.ir.analytics.mgraph.ProxyNode]` | `no` | `()` | `polisyos.ir.analytics.mgraph.ProxyNode` |
| `r_nodes` | `tuple[polisyos.ir.analytics.mgraph.RNode]` | `no` | `()` | `polisyos.ir.analytics.mgraph.RNode` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `substantive_vars` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.mgraph.MissingnessKind` { #polisyos-ir-analytics-mgraph-missingnesskind }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Missingness mechanism classification.

| Enum values |
|-------------|
| `mcar` |
| `mar` |
| `mnar` |

### `polisyos.ir.analytics.mgraph.ProxyNode` { #polisyos-ir-analytics-mgraph-proxynode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Observed proxy variable X_star in an M-graph.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `proxy_name` | `str` | `yes` | `—` | — |
| `target_variable` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.mgraph.RNode` { #polisyos-ir-analytics-mgraph-rnode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.mgraph.MissingnessKind`
- Summary: Missingness indicator node R_X in an M-graph.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `description` | `str` | `no` | `''` | — |
| `missingness_kind` | `polisyos.ir.analytics.mgraph.MissingnessKind` | `yes` | `—` | `polisyos.ir.analytics.mgraph.MissingnessKind` |
| `target_variable` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.ncm.ExogenousSpec` { #polisyos-ir-analytics-ncm-exogenousspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Specification for a latent exogenous noise variable U_i.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `associated_endogenous` | `str` | `yes` | `—` | — |
| `distribution_family` | `str` | `no` | `'normal'` | — |
| `distribution_params` | `dict[str, Any]` | `no` | `—` | — |
| `domain` | `Literal[real, binary, categorical, simplex]` | `no` | `'real'` | — |
| `is_shared` | `bool` | `no` | `False` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `shared_with` | `list[str]` | `no` | `—` | — |
| `variable` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.ncm.NCMSpec` { #polisyos-ir-analytics-ncm-ncmspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.ncm.ExogenousSpec`, `polisyos.ir.analytics.ncm.StructuralEquation`, `polisyos.ir.analytics.structural_causal_model.StructuralCausalModelSpec`
- Summary: Non-parametric Causal Model specification.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `endogenous_vars` | `list[str]` | `no` | `—` | — |
| `exogenous_specs` | `list[polisyos.ir.analytics.ncm.ExogenousSpec]` | `no` | `—` | `polisyos.ir.analytics.ncm.ExogenousSpec` |
| `fit_method` | `str | NoneType` | `no` | `—` | — |
| `independence_model` | `Literal[dag_markov, mdag_markov, unknown]` | `no` | `'unknown'` | — |
| `is_acyclic` | `bool` | `no` | `True` | — |
| `markov_condition_verified` | `bool` | `no` | `False` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `scm_spec` | `polisyos.ir.analytics.structural_causal_model.StructuralCausalModelSpec | NoneType` | `no` | `—` | `polisyos.ir.analytics.structural_causal_model.StructuralCausalModelSpec` |
| `source_graph_ref` | `str | NoneType` | `no` | `—` | — |
| `structural_equations` | `list[polisyos.ir.analytics.ncm.StructuralEquation]` | `no` | `—` | `polisyos.ir.analytics.ncm.StructuralEquation` |

### `polisyos.ir.analytics.ncm.StructuralEquation` { #polisyos-ir-analytics-ncm-structuralequation }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: One structural equation: V_i := f_i(Pa_i, U_i).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `equation_params` | `dict[str, Any]` | `no` | `—` | — |
| `equation_type` | `Literal[linear, nonlinear, lookup, neural, unknown]` | `no` | `'unknown'` | — |
| `exogenous` | `str` | `yes` | `—` | — |
| `is_recursive` | `bool` | `no` | `True` | — |
| `mechanism_ref` | `str | NoneType` | `no` | `—` | — |
| `parents` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `variable` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.negative_certificate.BlockingType` { #polisyos-ir-analytics-negative-certificate-blockingtype }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Category of the identification barrier.

| Enum values |
|-------------|
| `hedge_structure` |
| `s_node_unresolved` |
| `positivity_violation` |
| `support_mismatch` |
| `missing_distribution` |

### `polisyos.ir.analytics.negative_certificate.EpistemicTier` { #polisyos-ir-analytics-negative-certificate-epistemictier }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Epistemic strength of a fallback artifact.

| Enum values |
|-------------|
| `exact_nonparametric` |
| `partial_identification` |
| `assumption_dependent` |
| `diagnostic_guidance` |

### `polisyos.ir.analytics.negative_certificate.FallbackResult` { #polisyos-ir-analytics-negative-certificate-fallbackresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.negative_certificate.EpistemicTier`, `polisyos.ir.analytics.negative_certificate.ParametricRescueResult`, `polisyos.ir.analytics.negative_certificate.SuggestedExperiment`, `polisyos.ir.analytics.partial_identification.PartialIdentificationResult`, `polisyos.ir.analytics.partial_identification.SensitivitySweepResult`
- Summary: Typed hedge fallback chain output with explicit epistemic tiers.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bounds` | `polisyos.ir.analytics.partial_identification.PartialIdentificationResult | NoneType` | `no` | `—` | `polisyos.ir.analytics.partial_identification.PartialIdentificationResult` |
| `bounds_tier` | `polisyos.ir.analytics.negative_certificate.EpistemicTier | NoneType` | `no` | `—` | `polisyos.ir.analytics.negative_certificate.EpistemicTier` |
| `experiments_tier` | `polisyos.ir.analytics.negative_certificate.EpistemicTier | NoneType` | `no` | `—` | `polisyos.ir.analytics.negative_certificate.EpistemicTier` |
| `fallback_level` | `int` | `no` | `0` | — |
| `highest_tier_reached` | `polisyos.ir.analytics.negative_certificate.EpistemicTier | NoneType` | `no` | `—` | `polisyos.ir.analytics.negative_certificate.EpistemicTier` |
| `notes` | `tuple[str]` | `no` | `()` | — |
| `parametric_rescue` | `polisyos.ir.analytics.negative_certificate.ParametricRescueResult | NoneType` | `no` | `—` | `polisyos.ir.analytics.negative_certificate.ParametricRescueResult` |
| `parametric_tier` | `polisyos.ir.analytics.negative_certificate.EpistemicTier | NoneType` | `no` | `—` | `polisyos.ir.analytics.negative_certificate.EpistemicTier` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `sensitivity_sweep` | `polisyos.ir.analytics.partial_identification.SensitivitySweepResult | NoneType` | `no` | `—` | `polisyos.ir.analytics.partial_identification.SensitivitySweepResult` |
| `sensitivity_tier` | `polisyos.ir.analytics.negative_certificate.EpistemicTier | NoneType` | `no` | `—` | `polisyos.ir.analytics.negative_certificate.EpistemicTier` |
| `suggested_experiments` | `tuple[polisyos.ir.analytics.negative_certificate.SuggestedExperiment]` | `no` | `()` | `polisyos.ir.analytics.negative_certificate.SuggestedExperiment` |

### `polisyos.ir.analytics.negative_certificate.NegativeCertificate` { #polisyos-ir-analytics-negative-certificate-negativecertificate }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.negative_certificate.BlockingType`, `polisyos.ir.analytics.negative_certificate.FallbackResult`, `polisyos.ir.analytics.negative_certificate.RecoveryPlan`, `polisyos.ir.analytics.negative_certificate.SuggestedExperiment`, `polisyos.ir.analytics.partial_identification.BoundsBundle`, `polisyos.ir.analytics.partial_identification.PartialIdentificationResult`
- Summary: Constructive certificate of non-identification.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `blocking_description` | `str` | `yes` | `—` | — |
| `blocking_type` | `polisyos.ir.analytics.negative_certificate.BlockingType` | `yes` | `—` | `polisyos.ir.analytics.negative_certificate.BlockingType` |
| `bounds_bundle` | `polisyos.ir.analytics.partial_identification.BoundsBundle | NoneType` | `no` | `—` | `polisyos.ir.analytics.partial_identification.BoundsBundle` |
| `constructive_message` | `str` | `no` | `''` | — |
| `fallback_result` | `polisyos.ir.analytics.negative_certificate.FallbackResult | NoneType` | `no` | `—` | `polisyos.ir.analytics.negative_certificate.FallbackResult` |
| `missing_dataset_refs` | `tuple[str]` | `no` | `()` | — |
| `partial_bounds` | `polisyos.ir.analytics.partial_identification.PartialIdentificationResult | NoneType` | `no` | `—` | `polisyos.ir.analytics.partial_identification.PartialIdentificationResult` |
| `quantitative_diagnostics` | `dict[str, Any]` | `no` | `—` | — |
| `recovery_plan` | `polisyos.ir.analytics.negative_certificate.RecoveryPlan | NoneType` | `no` | `—` | `polisyos.ir.analytics.negative_certificate.RecoveryPlan` |
| `required_distributions` | `tuple[dict[str, Any]]` | `no` | `()` | — |
| `suggested_experiments` | `tuple[polisyos.ir.analytics.negative_certificate.SuggestedExperiment]` | `no` | `()` | `polisyos.ir.analytics.negative_certificate.SuggestedExperiment` |
| `technical_detail` | `str` | `no` | `''` | — |

### `polisyos.ir.analytics.negative_certificate.ParametricRescueResult` { #polisyos-ir-analytics-negative-certificate-parametricrescueresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.partial_identification.PartialIdentificationResult`
- Summary: Assumption-dependent fallback artifact.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `assumption` | `str` | `yes` | `—` | — |
| `bounds` | `polisyos.ir.analytics.partial_identification.PartialIdentificationResult | NoneType` | `no` | `—` | `polisyos.ir.analytics.partial_identification.PartialIdentificationResult` |
| `description` | `str` | `no` | `''` | — |
| `diagnostics` | `dict[str, Any]` | `no` | `—` | — |
| `estimand_formula` | `str | NoneType` | `no` | `—` | — |
| `method` | `str` | `no` | `''` | — |
| `point_estimate` | `float | NoneType` | `no` | `—` | — |
| `standard_error` | `float | NoneType` | `no` | `—` | — |
| `supporting_variables` | `tuple[str]` | `no` | `()` | — |
| `warnings` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.negative_certificate.RecoveryPlan` { #polisyos-ir-analytics-negative-certificate-recoveryplan }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Canonical next-step artifact for non-identification paths.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `blocking_reason` | `str` | `yes` | `—` | — |
| `candidate_actions` | `list[str]` | `no` | `—` | — |
| `expected_width_reduction` | `float | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `minimal_oracle_sets` | `list[list[str]]` | `no` | `—` | — |

### `polisyos.ir.analytics.negative_certificate.SuggestedExperiment` { #polisyos-ir-analytics-negative-certificate-suggestedexperiment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Structured description of an experiment or data collection strategy.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `description` | `str` | `no` | `''` | — |
| `design_type` | `str` | `no` | `'observational'` | — |
| `domain` | `str` | `no` | `'target'` | — |
| `required_variables` | `tuple[str]` | `yes` | `—` | — |

### `polisyos.ir.analytics.normative_arbitration.ArbitrationOption` { #polisyos-ir-analytics-normative-arbitration-arbitrationoption }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Arbitration option public type.

| Enum values |
|-------------|
| `baseline` |
| `proposal` |
| `indeterminate` |

### `polisyos.ir.analytics.normative_arbitration.HardConstraintAuditEntry` { #polisyos-ir-analytics-normative-arbitration-hardconstraintauditentry }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.normative_arbitration.NormativeAuditStatus`
- Summary: Hard constraint audit entry data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `baseline_value` | `float | int | str | bool | NoneType` | `no` | `—` | — |
| `constraint_id` | `str` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `operator` | `str | NoneType` | `no` | `—` | — |
| `proposal_value` | `float | int | str | bool | NoneType` | `no` | `—` | — |
| `status` | `polisyos.ir.analytics.normative_arbitration.NormativeAuditStatus` | `yes` | `—` | `polisyos.ir.analytics.normative_arbitration.NormativeAuditStatus` |
| `threshold` | `float | int | str | bool | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.normative_arbitration.NormativeArbitrationResult` { #polisyos-ir-analytics-normative-arbitration-normativearbitrationresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.normative_arbitration.ArbitrationOption`, `polisyos.ir.analytics.normative_arbitration.HardConstraintAuditEntry`, `polisyos.ir.analytics.normative_arbitration.NormativeModelCompleteness`, `polisyos.ir.analytics.normative_arbitration.NormativeProvenance`, `polisyos.ir.analytics.normative_arbitration.OptionOutcomeMatrix`, `polisyos.ir.analytics.normative_arbitration.PolicyOutcome`, `polisyos.ir.analytics.normative_arbitration.ResidualDissent`, `polisyos.ir.analytics.normative_arbitration.RightsAuditEntry`, `polisyos.ir.analytics.normative_arbitration.StakeholderUtilitySummary`, `polisyos.ir.analytics.normative_arbitration.TradeoffCertificate`, `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy`
- Summary: Normative arbitration result data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `comparison_mode` | `str` | `no` | `'proposal_vs_baseline'` | — |
| `hard_constraint_audit` | `list[polisyos.ir.analytics.normative_arbitration.HardConstraintAuditEntry]` | `no` | `—` | `polisyos.ir.analytics.normative_arbitration.HardConstraintAuditEntry` |
| `losers` | `list[str]` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `model_completeness` | `polisyos.ir.analytics.normative_arbitration.NormativeModelCompleteness` | `no` | `<NormativeModelCompleteness.PARTIAL: 'partial'>` | `polisyos.ir.analytics.normative_arbitration.NormativeModelCompleteness` |
| `option_matrix` | `list[polisyos.ir.analytics.normative_arbitration.OptionOutcomeMatrix]` | `no` | `—` | `polisyos.ir.analytics.normative_arbitration.OptionOutcomeMatrix` |
| `per_stakeholder_utility` | `list[polisyos.ir.analytics.normative_arbitration.StakeholderUtilitySummary]` | `no` | `—` | `polisyos.ir.analytics.normative_arbitration.StakeholderUtilitySummary` |
| `policy_outcomes` | `list[polisyos.ir.analytics.normative_arbitration.PolicyOutcome]` | `no` | `—` | `polisyos.ir.analytics.normative_arbitration.PolicyOutcome` |
| `provenance` | `polisyos.ir.analytics.normative_arbitration.NormativeProvenance` | `no` | `—` | `polisyos.ir.analytics.normative_arbitration.NormativeProvenance` |
| `residual_dissent` | `list[polisyos.ir.analytics.normative_arbitration.ResidualDissent]` | `no` | `—` | `polisyos.ir.analytics.normative_arbitration.ResidualDissent` |
| `rights_audit` | `list[polisyos.ir.analytics.normative_arbitration.RightsAuditEntry]` | `no` | `—` | `polisyos.ir.analytics.normative_arbitration.RightsAuditEntry` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `selected_option` | `polisyos.ir.analytics.normative_arbitration.ArbitrationOption` | `yes` | `—` | `polisyos.ir.analytics.normative_arbitration.ArbitrationOption` |
| `selected_policy` | `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy` | `yes` | `—` | `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy` |
| `tradeoff_certificate` | `polisyos.ir.analytics.normative_arbitration.TradeoffCertificate` | `yes` | `—` | `polisyos.ir.analytics.normative_arbitration.TradeoffCertificate` |
| `warnings` | `list[str]` | `no` | `—` | — |
| `winners` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.normative_arbitration.NormativeAuditStatus` { #polisyos-ir-analytics-normative-arbitration-normativeauditstatus }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Normative audit status public type.

| Enum values |
|-------------|
| `satisfied` |
| `violated` |
| `unevaluated` |

### `polisyos.ir.analytics.normative_arbitration.NormativeModelCompleteness` { #polisyos-ir-analytics-normative-arbitration-normativemodelcompleteness }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Normative model completeness public type.

| Enum values |
|-------------|
| `complete` |
| `partial` |

### `polisyos.ir.analytics.normative_arbitration.NormativeProvenance` { #polisyos-ir-analytics-normative-arbitration-normativeprovenance }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Normative provenance public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `distributional_report_ref` | `str | NoneType` | `no` | `—` | — |
| `legal_report_ref` | `str | NoneType` | `no` | `—` | — |
| `metrics_ref` | `str | NoneType` | `no` | `—` | — |
| `simulation_result_ref` | `str | NoneType` | `no` | `—` | — |
| `trinity_bundle_ref` | `str | NoneType` | `no` | `—` | — |
| `uncertainty_refs` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.normative_arbitration.OptionOutcomeMatrix` { #polisyos-ir-analytics-normative-arbitration-optionoutcomematrix }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.normative_arbitration.ArbitrationOption`
- Summary: Option outcome matrix data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `binding_values` | `dict[str, float]` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `option` | `polisyos.ir.analytics.normative_arbitration.ArbitrationOption` | `yes` | `—` | `polisyos.ir.analytics.normative_arbitration.ArbitrationOption` |

### `polisyos.ir.analytics.normative_arbitration.PolicyOutcome` { #polisyos-ir-analytics-normative-arbitration-policyoutcome }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.normative_arbitration.ArbitrationOption`, `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy`
- Summary: Policy outcome public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `confidence` | `float | NoneType` | `no` | `—` | — |
| `metrics` | `dict[str, float | int | str | bool | NoneType]` | `no` | `—` | — |
| `policy` | `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy` | `yes` | `—` | `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy` |
| `rationale` | `str` | `yes` | `—` | — |
| `selected_option` | `polisyos.ir.analytics.normative_arbitration.ArbitrationOption` | `yes` | `—` | `polisyos.ir.analytics.normative_arbitration.ArbitrationOption` |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.normative_arbitration.ResidualDissent` { #polisyos-ir-analytics-normative-arbitration-residualdissent }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.normative_arbitration.ArbitrationOption`, `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy`
- Summary: Residual dissent public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `policy` | `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy` | `yes` | `—` | `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy` |
| `preferred_option` | `polisyos.ir.analytics.normative_arbitration.ArbitrationOption` | `yes` | `—` | `polisyos.ir.analytics.normative_arbitration.ArbitrationOption` |
| `rationale` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.normative_arbitration.RightsAuditEntry` { #polisyos-ir-analytics-normative-arbitration-rightsauditentry }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.normative_arbitration.NormativeAuditStatus`
- Summary: Rights audit entry data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `binding_ref` | `str | NoneType` | `no` | `—` | — |
| `compare_to` | `str` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `observed_value` | `float | int | str | bool | NoneType` | `no` | `—` | — |
| `operator` | `str` | `yes` | `—` | — |
| `right_id` | `str` | `yes` | `—` | — |
| `stakeholder_id` | `str` | `yes` | `—` | — |
| `status` | `polisyos.ir.analytics.normative_arbitration.NormativeAuditStatus` | `yes` | `—` | `polisyos.ir.analytics.normative_arbitration.NormativeAuditStatus` |
| `threshold` | `float | int | str | bool | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.normative_arbitration.StakeholderUtilitySummary` { #polisyos-ir-analytics-normative-arbitration-stakeholderutilitysummary }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Stakeholder utility summary data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `baseline_utility` | `float` | `no` | `0.0` | — |
| `delta_utility` | `float` | `no` | `0.0` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `proposal_utility` | `float` | `no` | `0.0` | — |
| `stakeholder_id` | `str` | `yes` | `—` | — |
| `welfare_weight` | `float` | `no` | `1.0` | — |

### `polisyos.ir.analytics.normative_arbitration.TradeoffCertificate` { #polisyos-ir-analytics-normative-arbitration-tradeoffcertificate }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.normative_arbitration.ArbitrationOption`, `polisyos.ir.analytics.normative_arbitration.ResidualDissent`, `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy`
- Summary: Tradeoff certificate public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `hard_constraint_violations` | `list[str]` | `no` | `—` | — |
| `losers` | `list[str]` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `residual_dissent` | `list[polisyos.ir.analytics.normative_arbitration.ResidualDissent]` | `no` | `—` | `polisyos.ir.analytics.normative_arbitration.ResidualDissent` |
| `rights_violations` | `list[str]` | `no` | `—` | — |
| `selected_option` | `polisyos.ir.analytics.normative_arbitration.ArbitrationOption` | `yes` | `—` | `polisyos.ir.analytics.normative_arbitration.ArbitrationOption` |
| `selected_policy` | `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy` | `yes` | `—` | `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy` |
| `winners` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.parameters.ContextAdaptiveParameterBundle` { #polisyos-ir-analytics-parameters-contextadaptiveparameterbundle }

- Kind: `pydantic_model`
- Public status: `snapshot_only`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `context_adaptive_parameter_bundle` / `schemas/snapshots/ir/context_adaptive_parameter_bundle.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.context.ContextProfile`, `polisyos.ir.analytics.literature.EvidenceParameter`, `polisyos.ir.analytics.parameters.ParameterApplicability`
- Summary: Parameters selected from SKG and adapted for a target simulation context.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `applicability` | `dict[str, polisyos.ir.analytics.parameters.ParameterApplicability]` | `no` | `—` | `polisyos.ir.analytics.parameters.ParameterApplicability` |
| `parameters` | `dict[str, polisyos.ir.analytics.literature.EvidenceParameter]` | `no` | `—` | `polisyos.ir.analytics.literature.EvidenceParameter` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `selection_timestamp` | `str` | `no` | `''` | — |
| `simulation_domain` | `str` | `yes` | `—` | — |
| `skg_snapshot_ref` | `str` | `no` | `''` | — |
| `skg_version_id` | `int | NoneType` | `no` | `—` | — |
| `target_context` | `polisyos.ir.analytics.context.ContextProfile` | `yes` | `—` | `polisyos.ir.analytics.context.ContextProfile` |
| `unsupported_parameters` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.parameters.ParameterApplicability` { #polisyos-ir-analytics-parameters-parameterapplicability }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.transportability.TransportMode`, `polisyos.ir.analytics.transportability.TransportabilityStatus`
- Summary: Applicability assessment for a parameter in a target context.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `adjustment_required` | `bool` | `yes` | `—` | — |
| `context_distance` | `float` | `yes` | `—` | — |
| `is_applicable` | `bool` | `yes` | `—` | — |
| `parameter_id` | `str` | `yes` | `—` | — |
| `recommended_value` | `float | NoneType` | `no` | `—` | — |
| `target_context_id` | `str` | `yes` | `—` | — |
| `transport_confidence` | `float` | `yes` | `—` | — |
| `transport_mode` | `polisyos.ir.analytics.transportability.TransportMode` | `no` | `<TransportMode.NONE: 'none'>` | `polisyos.ir.analytics.transportability.TransportMode` |
| `transport_notes` | `list[str]` | `no` | `—` | — |
| `transport_status` | `polisyos.ir.analytics.transportability.TransportabilityStatus` | `yes` | `—` | `polisyos.ir.analytics.transportability.TransportabilityStatus` |
| `uncertainty_multiplier` | `float` | `no` | `1.0` | — |

### `polisyos.ir.analytics.partial_identification.BoundMethod` { #polisyos-ir-analytics-partial-identification-boundmethod }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Bound method public type.

| Enum values |
|-------------|
| `manski_bounds` |
| `transport_bounds` |
| `iv_bounds` |
| `monotone_treatment` |
| `lp_balke_pearl` |
| `imbens_manski_ci` |
| `mtr_bounds` |
| `miv_bounds` |
| `mts_bounds` |
| `general_lp_bounds` |
| `copula_bounds` |
| `tan_bounds` |
| `intersection_bounds` |
| `rosenbaum_sharp` |

### `polisyos.ir.analytics.partial_identification.BoundsBundle` { #polisyos-ir-analytics-partial-identification-boundsbundle }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.partial_identification.BoundsMethodSummary`
- Summary: Canonical public bounds contract for non-point-identified queries.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `consensus_lower` | `float | NoneType` | `no` | `—` | — |
| `consensus_upper` | `float | NoneType` | `no` | `—` | — |
| `estimand_type` | `str` | `no` | `'ate'` | — |
| `lower_bound` | `float | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `method_summaries` | `list[polisyos.ir.analytics.partial_identification.BoundsMethodSummary]` | `no` | `—` | `polisyos.ir.analytics.partial_identification.BoundsMethodSummary` |
| `point_identified` | `bool` | `no` | `False` | — |
| `rescue_actions` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `sharpness_status` | `Literal[sharp, inner_approx, outer_approx, unknown]` | `no` | `'unknown'` | — |
| `upper_bound` | `float | NoneType` | `no` | `—` | — |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.partial_identification.BoundsMethodSummary` { #polisyos-ir-analytics-partial-identification-boundsmethodsummary }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.partial_identification.BoundMethod`
- Summary: Canonical summary of one bounds method in a public bounds artifact.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `assumptions_used` | `list[str]` | `no` | `—` | — |
| `bound_width` | `float` | `yes` | `—` | — |
| `bounds_type` | `str` | `no` | `'manski'` | — |
| `display_label` | `str` | `no` | `''` | — |
| `lower_bound` | `float` | `yes` | `—` | — |
| `method` | `polisyos.ir.analytics.partial_identification.BoundMethod` | `yes` | `—` | `polisyos.ir.analytics.partial_identification.BoundMethod` |
| `upper_bound` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.partial_identification.BoundsReport` { #polisyos-ir-analytics-partial-identification-boundsreport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.partial_identification.BoundMethod`, `polisyos.ir.analytics.partial_identification.PartialIdentificationResult`
- Summary: Aggregated result from running multiple partial identification methods.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `assumptions_used` | `list[str]` | `no` | `—` | — |
| `consensus_lower` | `float | NoneType` | `no` | `—` | — |
| `consensus_upper` | `float | NoneType` | `no` | `—` | — |
| `estimand_type` | `str` | `no` | `'ate'` | — |
| `is_informative` | `bool` | `no` | `False` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `results` | `list[polisyos.ir.analytics.partial_identification.PartialIdentificationResult]` | `yes` | `—` | `polisyos.ir.analytics.partial_identification.PartialIdentificationResult` |
| `run_id` | `str` | `no` | `''` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `tightest_lower` | `float | NoneType` | `no` | `—` | — |
| `tightest_method` | `polisyos.ir.analytics.partial_identification.BoundMethod | NoneType` | `no` | `—` | `polisyos.ir.analytics.partial_identification.BoundMethod` |
| `tightest_upper` | `float | NoneType` | `no` | `—` | — |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.partial_identification.PartialIdentificationResult` { #polisyos-ir-analytics-partial-identification-partialidentificationresult }

- Kind: `pydantic_model`
- Public status: `snapshot_only`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `partial_identification_result` / `schemas/snapshots/ir/partial_identification_result.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.partial_identification.BoundMethod`
- Summary: Result of partial identification analysis (e.g., Manski bounds on ATE).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `assumptions_used` | `list[str]` | `no` | `—` | — |
| `assumptions_violated` | `list[str]` | `no` | `—` | — |
| `bound_width` | `float` | `no` | `0.0` | — |
| `bounds_type` | `Literal[sharp_lp, relaxed_polynomial, manski]` | `no` | `'manski'` | — |
| `chart_type` | `str` | `no` | `'interval'` | — |
| `confidence` | `float` | `yes` | `—` | — |
| `discretization_converged` | `bool | NoneType` | `no` | `—` | — |
| `discretization_method` | `str | NoneType` | `no` | `—` | — |
| `display_label` | `str` | `no` | `''` | — |
| `informativeness_threshold` | `float` | `no` | `0.5` | — |
| `is_informative` | `bool` | `no` | `True` | — |
| `lower_bound` | `float` | `yes` | `—` | — |
| `method` | `polisyos.ir.analytics.partial_identification.BoundMethod` | `yes` | `—` | `polisyos.ir.analytics.partial_identification.BoundMethod` |
| `n_bins_final` | `int | NoneType` | `no` | `—` | — |
| `n_refinement_steps` | `int` | `no` | `0` | — |
| `relaxation_gap` | `float | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `upper_bound` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.partial_identification.SensitivitySweepResult` { #polisyos-ir-analytics-partial-identification-sensitivitysweepresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.partial_identification.BoundMethod`
- Summary: Bounds expressed as a function of a sensitivity parameter (γ or λ).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `critical_value` | `float | NoneType` | `no` | `—` | — |
| `display_label` | `str` | `no` | `''` | — |
| `lower_bounds` | `tuple[float]` | `yes` | `—` | — |
| `method` | `polisyos.ir.analytics.partial_identification.BoundMethod` | `no` | `<BoundMethod.ROSENBAUM_SHARP: 'rosenbaum_sharp'>` | `polisyos.ir.analytics.partial_identification.BoundMethod` |
| `parameter_name` | `str` | `yes` | `—` | — |
| `parameter_values` | `tuple[float]` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `upper_bounds` | `tuple[float]` | `yes` | `—` | — |

### `polisyos.ir.analytics.quality_report.CausalQualityReport` { #polisyos-ir-analytics-quality-report-causalqualityreport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.quality_report.QualityDimension`
- Summary: Composite quality report for a single causal analysis run.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `caveats` | `tuple[str]` | `no` | `()` | — |
| `composite_grade` | `str` | `yes` | `—` | — |
| `composite_score` | `float` | `yes` | `—` | — |
| `created_at` | `str` | `no` | `''` | — |
| `data_quality` | `polisyos.ir.analytics.quality_report.QualityDimension` | `yes` | `—` | `polisyos.ir.analytics.quality_report.QualityDimension` |
| `is_publication_ready` | `bool` | `yes` | `—` | — |
| `method_quality` | `polisyos.ir.analytics.quality_report.QualityDimension` | `yes` | `—` | `polisyos.ir.analytics.quality_report.QualityDimension` |
| `query_str` | `str` | `no` | `''` | — |
| `robustness` | `polisyos.ir.analytics.quality_report.QualityDimension` | `yes` | `—` | `polisyos.ir.analytics.quality_report.QualityDimension` |
| `run_id` | `str` | `yes` | `—` | — |
| `weights` | `dict[str, float]` | `no` | `—` | — |

### `polisyos.ir.analytics.quality_report.QualityDimension` { #polisyos-ir-analytics-quality-report-qualitydimension }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Score and breakdown for one quality dimension.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `components` | `dict[str, float]` | `no` | `—` | — |
| `grade` | `str` | `yes` | `—` | — |
| `is_blocking` | `bool` | `no` | `False` | — |
| `score` | `float` | `yes` | `—` | — |
| `warnings` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.query_validation_report.QueryValidationReport` { #polisyos-ir-analytics-query-validation-report-queryvalidationreport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.query_validation_report.ValidationError`, `polisyos.ir.analytics.query_validation_report.ValidationWarning`
- Summary: Schema for the result of validating a causal query against a graph and knowledge base.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `checked_at` | `str` | `no` | `''` | — |
| `errors` | `tuple[polisyos.ir.analytics.query_validation_report.ValidationError]` | `no` | `()` | `polisyos.ir.analytics.query_validation_report.ValidationError` |
| `is_valid` | `bool` | `yes` | `—` | — |
| `query_str` | `str` | `no` | `''` | — |
| `warnings` | `tuple[polisyos.ir.analytics.query_validation_report.ValidationWarning]` | `no` | `()` | `polisyos.ir.analytics.query_validation_report.ValidationWarning` |

### `polisyos.ir.analytics.query_validation_report.ValidationError` { #polisyos-ir-analytics-query-validation-report-validationerror }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.query_validation_report.ValidationSeverity`
- Summary: A fatal validation error that makes the query non-executable.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `code` | `str` | `yes` | `—` | — |
| `context` | `dict[str, Any]` | `no` | `{}` | — |
| `message` | `str` | `yes` | `—` | — |
| `severity` | `polisyos.ir.analytics.query_validation_report.ValidationSeverity` | `no` | `<ValidationSeverity.ERROR: 'error'>` | `polisyos.ir.analytics.query_validation_report.ValidationSeverity` |

### `polisyos.ir.analytics.query_validation_report.ValidationIssue` { #polisyos-ir-analytics-query-validation-report-validationissue }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.query_validation_report.ValidationSeverity`
- Summary: Base class for a single validation issue (error or warning).

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `code` | `str` | `yes` | `—` | — |
| `context` | `dict[str, Any]` | `no` | `{}` | — |
| `message` | `str` | `yes` | `—` | — |
| `severity` | `polisyos.ir.analytics.query_validation_report.ValidationSeverity` | `yes` | `—` | `polisyos.ir.analytics.query_validation_report.ValidationSeverity` |

### `polisyos.ir.analytics.query_validation_report.ValidationSeverity` { #polisyos-ir-analytics-query-validation-report-validationseverity }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Severity level of a validation issue.

| Enum values |
|-------------|
| `error` |
| `warning` |
| `info` |

### `polisyos.ir.analytics.query_validation_report.ValidationWarning` { #polisyos-ir-analytics-query-validation-report-validationwarning }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.query_validation_report.ValidationSeverity`
- Summary: A non-fatal validation warning — query can proceed but may give unreliable results.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `code` | `str` | `yes` | `—` | — |
| `context` | `dict[str, Any]` | `no` | `{}` | — |
| `message` | `str` | `yes` | `—` | — |
| `severity` | `polisyos.ir.analytics.query_validation_report.ValidationSeverity` | `no` | `<ValidationSeverity.WARNING: 'warning'>` | `polisyos.ir.analytics.query_validation_report.ValidationSeverity` |

### `polisyos.ir.analytics.recourse.ContrastiveExplanation` { #polisyos-ir-analytics-recourse-contrastiveexplanation }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:ContrastiveExplanation`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Contrastive explanation for why one outcome happened instead of another.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `decisive_factors` | `tuple[str]` | `no` | `()` | — |
| `explanation_id` | `str` | `yes` | `—` | — |
| `factual_label` | `str` | `yes` | `—` | — |
| `foil_label` | `str` | `yes` | `—` | — |
| `narrative` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.recourse.CounterfactualExplanation` { #polisyos-ir-analytics-recourse-counterfactualexplanation }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:CounterfactualExplanation`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.recourse.RecourseAction`
- Summary: Counterfactual explanation anchored to a set of recourse actions.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `changed_features` | `tuple[str]` | `no` | `()` | — |
| `counterfactual_outcome` | `str` | `yes` | `—` | — |
| `explanation_id` | `str` | `yes` | `—` | — |
| `factual_outcome` | `str` | `yes` | `—` | — |
| `notes` | `tuple[str]` | `no` | `()` | — |
| `supporting_actions` | `list[polisyos.ir.analytics.recourse.RecourseAction]` | `no` | `—` | `polisyos.ir.analytics.recourse.RecourseAction` |

### `polisyos.ir.analytics.recourse.RecourseAction` { #polisyos-ir-analytics-recourse-recourseaction }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:RecourseAction`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.recourse.RecourseActionType`
- Summary: One actionable change suggested by a recourse engine.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `action_type` | `polisyos.ir.analytics.recourse.RecourseActionType` | `yes` | `—` | `polisyos.ir.analytics.recourse.RecourseActionType` |
| `cost` | `float | NoneType` | `no` | `—` | — |
| `feature_path` | `str` | `yes` | `—` | — |
| `from_value` | `str | int | bool | float | NoneType` | `no` | `—` | — |
| `immutable` | `bool` | `no` | `False` | — |
| `to_value` | `str | int | bool | float | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.recourse.RecourseActionType` { #polisyos-ir-analytics-recourse-recourseactiontype }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:RecourseActionType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Canonical action types for algorithmic recourse.

| Enum values |
|-------------|
| `set` |
| `increase` |
| `decrease` |
| `toggle` |

### `polisyos.ir.analytics.recourse.RecourseFeasibility` { #polisyos-ir-analytics-recourse-recoursefeasibility }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:RecourseFeasibility`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Feasibility status of a recourse plan.

| Enum values |
|-------------|
| `feasible` |
| `conditional` |
| `infeasible` |

### `polisyos.ir.analytics.recourse.RecoursePlan` { #polisyos-ir-analytics-recourse-recourseplan }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:RecoursePlan`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.recourse.RecourseAction`, `polisyos.ir.analytics.recourse.RecourseFeasibility`
- Summary: Actionable recourse plan with cost/robustness annotations.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `actions` | `list[polisyos.ir.analytics.recourse.RecourseAction]` | `no` | `—` | `polisyos.ir.analytics.recourse.RecourseAction` |
| `feasibility` | `polisyos.ir.analytics.recourse.RecourseFeasibility` | `yes` | `—` | `polisyos.ir.analytics.recourse.RecourseFeasibility` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `plan_id` | `str` | `yes` | `—` | — |
| `robustness_score` | `float | NoneType` | `no` | `—` | — |
| `total_cost` | `float | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.recourse.RecourseReport` { #polisyos-ir-analytics-recourse-recoursereport }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:RecourseReport`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.recourse.ContrastiveExplanation`, `polisyos.ir.analytics.recourse.CounterfactualExplanation`, `polisyos.ir.analytics.recourse.RecoursePlan`
- Summary: Frozen report contract for recourse and explanation outputs.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `contrastive_explanations` | `list[polisyos.ir.analytics.recourse.ContrastiveExplanation]` | `no` | `—` | `polisyos.ir.analytics.recourse.ContrastiveExplanation` |
| `counterfactual_explanations` | `list[polisyos.ir.analytics.recourse.CounterfactualExplanation]` | `no` | `—` | `polisyos.ir.analytics.recourse.CounterfactualExplanation` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `plans` | `list[polisyos.ir.analytics.recourse.RecoursePlan]` | `no` | `—` | `polisyos.ir.analytics.recourse.RecoursePlan` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `subject_id` | `str | NoneType` | `no` | `—` | — |
| `warnings` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.representation_learning.LatentConfounderContract` { #polisyos-ir-analytics-representation-learning-latentconfoundercontract }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:LatentConfounderContract`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.representation_learning.LatentTrustLevel`, `polisyos.ir.analytics.representation_learning.LatentVariableSpec`, `polisyos.ir.analytics.representation_learning.RepresentationEncoderSpec`, `polisyos.ir.analytics.representation_learning.RepresentationModelFamily`
- Summary: Research-track contract for latent confounder / representation models.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `contract_id` | `str` | `yes` | `—` | — |
| `decision_support_allowed` | `bool` | `no` | `False` | — |
| `encoder` | `polisyos.ir.analytics.representation_learning.RepresentationEncoderSpec` | `yes` | `—` | `polisyos.ir.analytics.representation_learning.RepresentationEncoderSpec` |
| `identifiability_assumptions` | `tuple[str]` | `no` | `()` | — |
| `latent_variables` | `list[polisyos.ir.analytics.representation_learning.LatentVariableSpec]` | `no` | `—` | `polisyos.ir.analytics.representation_learning.LatentVariableSpec` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `model_family` | `polisyos.ir.analytics.representation_learning.RepresentationModelFamily` | `yes` | `—` | `polisyos.ir.analytics.representation_learning.RepresentationModelFamily` |
| `observed_covariates` | `tuple[str]` | `no` | `()` | — |
| `outcome_field` | `str` | `yes` | `—` | — |
| `research_gate_required` | `bool` | `no` | `True` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `treatment_field` | `str` | `yes` | `—` | — |
| `trust_level` | `polisyos.ir.analytics.representation_learning.LatentTrustLevel` | `no` | `<LatentTrustLevel.RESEARCH: 'research'>` | `polisyos.ir.analytics.representation_learning.LatentTrustLevel` |

### `polisyos.ir.analytics.representation_learning.LatentTrustLevel` { #polisyos-ir-analytics-representation-learning-latenttrustlevel }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Promotion level for latent/representation-learning outputs.

| Enum values |
|-------------|
| `research` |
| `conditional` |
| `validated` |

### `polisyos.ir.analytics.representation_learning.LatentVariableSpec` { #polisyos-ir-analytics-representation-learning-latentvariablespec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: One latent variable family introduced by a representation model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `dimension` | `int` | `yes` | `—` | — |
| `latent_id` | `str` | `yes` | `—` | — |
| `observed_children` | `tuple[str]` | `no` | `()` | — |
| `parents` | `tuple[str]` | `no` | `()` | — |
| `regularization_weight` | `float | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.representation_learning.RepresentationEncoderSpec` { #polisyos-ir-analytics-representation-learning-representationencoderspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Encoder metadata for a latent causal representation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `architecture_hint` | `str` | `yes` | `—` | — |
| `encoder_id` | `str` | `yes` | `—` | — |
| `input_fields` | `tuple[str]` | `yes` | `—` | — |
| `latent_dimensions` | `dict[str, int]` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |

### `polisyos.ir.analytics.representation_learning.RepresentationLearningResult` { #polisyos-ir-analytics-representation-learning-representationlearningresult }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:RepresentationLearningResult`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.representation_learning.LatentTrustLevel`, `polisyos.ir.analytics.representation_learning.RepresentationModelFamily`
- Summary: Frozen result contract for latent/representation-learning runs.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `contract_id` | `str` | `yes` | `—` | — |
| `counterfactual_consistency_score` | `float | NoneType` | `no` | `—` | — |
| `elbo` | `float | NoneType` | `no` | `—` | — |
| `environment_invariance_score` | `float | NoneType` | `no` | `—` | — |
| `learned_latent_ids` | `tuple[str]` | `no` | `()` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `model_family` | `polisyos.ir.analytics.representation_learning.RepresentationModelFamily` | `yes` | `—` | `polisyos.ir.analytics.representation_learning.RepresentationModelFamily` |
| `reconstruction_loss` | `float | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `trust_level` | `polisyos.ir.analytics.representation_learning.LatentTrustLevel` | `no` | `<LatentTrustLevel.RESEARCH: 'research'>` | `polisyos.ir.analytics.representation_learning.LatentTrustLevel` |
| `warnings` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.representation_learning.RepresentationModelFamily` { #polisyos-ir-analytics-representation-learning-representationmodelfamily }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:RepresentationModelFamily`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Frontier representation-learning families carried as IR contracts.

| Enum values |
|-------------|
| `cevae` |
| `latent_scm` |
| `neural_causal_model` |
| `causal_generative_model` |

### `polisyos.ir.analytics.sensitivity.BenchmarkResult` { #polisyos-ir-analytics-sensitivity-benchmarkresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Cinelli-Hazlett benchmarking result relative to a named observed covariate.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bias_scale` | `float | NoneType` | `no` | `—` | — |
| `covariate_name` | `str` | `yes` | `—` | — |
| `interpretation` | `str` | `no` | `''` | — |
| `r2td_x` | `float | NoneType` | `no` | `—` | — |
| `r2yd_x` | `float | NoneType` | `no` | `—` | — |
| `rv_benchmarked` | `float | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.sensitivity.EValueResult` { #polisyos-ir-analytics-sensitivity-evalueresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: E value result data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `ci_crosses_null` | `bool` | `no` | `False` | — |
| `ci_rr` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `details` | `dict[str, Any]` | `no` | `—` | — |
| `method` | `str` | `yes` | `—` | — |
| `raw_effect` | `float` | `yes` | `—` | — |
| `rr_equivalent` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.sensitivity.SensitivityResult` { #polisyos-ir-analytics-sensitivity-sensitivityresult }

- Kind: `pydantic_model`
- Public status: `snapshot_only`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `causal_sensitivity_result` / `schemas/snapshots/ir/sensitivity_result.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.sensitivity.BenchmarkResult`, `polisyos.ir.analytics.sensitivity.EValueResult`
- Summary: Sensitivity result data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `benchmark_covariates` | `list[str]` | `no` | `—` | — |
| `benchmark_results` | `list[polisyos.ir.analytics.sensitivity.BenchmarkResult]` | `no` | `—` | `polisyos.ir.analytics.sensitivity.BenchmarkResult` |
| `conversion_method` | `str | NoneType` | `no` | `—` | — |
| `e_value` | `float | NoneType` | `no` | `—` | — |
| `e_value_ci_lower` | `float | NoneType` | `no` | `—` | — |
| `e_value_result` | `polisyos.ir.analytics.sensitivity.EValueResult | NoneType` | `no` | `—` | `polisyos.ir.analytics.sensitivity.EValueResult` |
| `interpretation` | `str` | `no` | `''` | — |
| `is_robust` | `bool` | `no` | `False` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `partial_r2_treatment` | `float | NoneType` | `no` | `—` | — |
| `robustness_value` | `float | NoneType` | `no` | `—` | — |
| `rosenbaum_gamma` | `float | NoneType` | `no` | `—` | — |
| `rosenbaum_p_value` | `float | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.analytics.sensitivity_report.SensitivityReport` { #polisyos-ir-analytics-sensitivity-report-sensitivityreport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.partial_identification.BoundsReport`, `polisyos.ir.analytics.sensitivity.SensitivityResult`
- Summary: Aggregated sensitivity and robustness analysis for a causal estimate.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `actionable_recommendations` | `list[str]` | `no` | `—` | — |
| `bounds_report` | `polisyos.ir.analytics.partial_identification.BoundsReport | NoneType` | `no` | `—` | `polisyos.ir.analytics.partial_identification.BoundsReport` |
| `estimand_type` | `str` | `no` | `'ate'` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `negative_certificate` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `overall_robustness_assessment` | `str` | `no` | `''` | — |
| `run_id` | `str` | `no` | `''` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `sensitivity_result` | `polisyos.ir.analytics.sensitivity.SensitivityResult` | `yes` | `—` | `polisyos.ir.analytics.sensitivity.SensitivityResult` |
| `threshold_breaches` | `dict[str, float]` | `no` | `—` | — |

### `polisyos.ir.analytics.strategic.EquilibriumSelectionSummary` { #polisyos-ir-analytics-strategic-equilibriumselectionsummary }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Persisted selected equilibrium disclosure.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `equilibrium_selection_dependence` | `str` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `selected_equilibrium` | `dict[str, str]` | `yes` | `—` | — |

### `polisyos.ir.analytics.strategic.EquilibriumSetSummary` { #polisyos-ir-analytics-strategic-equilibriumsetsummary }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Persisted equilibrium surface disclosure.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `equilibrium_count` | `int` | `no` | `0` | — |
| `equilibrium_profiles` | `tuple[dict[str, str]]` | `no` | `()` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `multiplicity_note` | `str | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.analytics.strategic.FiniteStrategicPayoffTable` { #polisyos-ir-analytics-strategic-finitestrategicpayofftable }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:FiniteStrategicPayoffTable`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Dense normal-form payoff surface over finite action spaces.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `action_spaces` | `dict[str, tuple[str]]` | `yes` | `—` | — |
| `agent` | `str` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `payoffs` | `dict[str, float]` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `strategic_agents` | `tuple[str]` | `yes` | `—` | — |

### `polisyos.ir.analytics.strategic.PerformativeShiftSummary` { #polisyos-ir-analytics-strategic-performativeshiftsummary }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Persisted strategic performative shift disclosure.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `baseline_policy_value` | `float | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `performative_shift` | `float` | `yes` | `—` | — |
| `post_adaptation_policy_value` | `float | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.analytics.strategic.PostAdaptationPolicyValueSummary` { #polisyos-ir-analytics-strategic-postadaptationpolicyvaluesummary }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.strategic.StrategicFallbackMode`
- Summary: Persisted post-adaptation policy-value disclosure.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `baseline_policy_value` | `float | NoneType` | `no` | `—` | — |
| `blocked_reason` | `str | NoneType` | `no` | `—` | — |
| `fallback_mode` | `polisyos.ir.analytics.strategic.StrategicFallbackMode` | `yes` | `—` | `polisyos.ir.analytics.strategic.StrategicFallbackMode` |
| `lower_bound` | `float | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `point_value` | `float | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `upper_bound` | `float | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.strategic.StrategicClosureSummary` { #polisyos-ir-analytics-strategic-strategicclosuresummary }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.strategic.StrategicEquilibriumConcept`, `polisyos.ir.analytics.strategic.StrategicFallbackMode`
- Summary: Persisted strategic fallback / equilibrium closure summary.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `blocked_reason` | `str | NoneType` | `no` | `—` | — |
| `equilibrium_concept` | `polisyos.ir.analytics.strategic.StrategicEquilibriumConcept | NoneType` | `no` | `—` | `polisyos.ir.analytics.strategic.StrategicEquilibriumConcept` |
| `equilibrium_count` | `int` | `no` | `0` | — |
| `equilibrium_selection_dependence` | `str` | `yes` | `—` | — |
| `fallback_mode` | `polisyos.ir.analytics.strategic.StrategicFallbackMode` | `yes` | `—` | `polisyos.ir.analytics.strategic.StrategicFallbackMode` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `profile_count` | `int` | `no` | `0` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `warnings` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.strategic.StrategicEquilibriumConcept` { #polisyos-ir-analytics-strategic-strategicequilibriumconcept }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:StrategicEquilibriumConcept`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Select the equilibrium notion used by strategic-response solvers.

| Enum values |
|-------------|
| `nash` |
| `stackelberg` |
| `best_response_fixed_point` |

### `polisyos.ir.analytics.strategic.StrategicFallbackMode` { #polisyos-ir-analytics-strategic-strategicfallbackmode }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Report whether strategic evaluation used exact, bounded, abstracted, or blocked fallback.

| Enum values |
|-------------|
| `exact_equilibrium` |
| `strategic_bounds` |
| `macro_abstracted` |
| `blocked` |

### `polisyos.ir.analytics.strategic.StrategicResponseBundle` { #polisyos-ir-analytics-strategic-strategicresponsebundle }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:StrategicResponseBundle`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.strategic.StrategicFallbackMode`, `polisyos.ir.refs.ArtifactRefModel`
- Summary: Disclosed strategic closure around a causal policy recommendation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `behavioral_assumption_sensitivity_ref` | `polisyos.ir.refs.ArtifactRefModel | NoneType` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `blocked_reason` | `str | NoneType` | `no` | `—` | — |
| `causal_component_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `equilibrium_selection_dependence` | `str` | `yes` | `—` | — |
| `equilibrium_set_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `fallback_mode` | `polisyos.ir.analytics.strategic.StrategicFallbackMode` | `no` | `<StrategicFallbackMode.EXACT_EQUILIBRIUM: 'exact_equilibrium'>` | `polisyos.ir.analytics.strategic.StrategicFallbackMode` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `multiplicity_note` | `str | NoneType` | `no` | `—` | — |
| `performative_shift_ref` | `polisyos.ir.refs.ArtifactRefModel | NoneType` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `post_adaptation_policy_value_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `selected_equilibrium_ref` | `polisyos.ir.refs.ArtifactRefModel | NoneType` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `strategic_closure_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |

### `polisyos.ir.analytics.strategic.StrategicSCM` { #polisyos-ir-analytics-strategic-strategicscm }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:StrategicSCM`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.strategic.StrategicEquilibriumConcept`, `polisyos.ir.refs.ArtifactRefModel`, `polisyos.ir.refs.StrategicPayoffTableRef`
- Summary: Strategic augmentation of a causal policy rule over a small finite game.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `base_graph_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `compute_budget` | `ComputeBudget` | `no` | `—` | — |
| `equilibrium_concept` | `polisyos.ir.analytics.strategic.StrategicEquilibriumConcept` | `yes` | `—` | `polisyos.ir.analytics.strategic.StrategicEquilibriumConcept` |
| `macro_utility_refs` | `dict[str, polisyos.ir.refs.StrategicPayoffTableRef] | NoneType` | `no` | `—` | `polisyos.ir.refs.StrategicPayoffTableRef` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `policy_rule_ref` | `polisyos.ir.refs.ArtifactRefModel` | `yes` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `strategic_agents` | `tuple[str]` | `yes` | `—` | — |
| `utility_refs` | `dict[str, polisyos.ir.refs.StrategicPayoffTableRef]` | `yes` | `—` | `polisyos.ir.refs.StrategicPayoffTableRef` |

### `polisyos.ir.analytics.structural_causal_model.MechanismFamily` { #polisyos-ir-analytics-structural-causal-model-mechanismfamily }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:MechanismFamily`, `polisyos.ir:MechanismFamily`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Allowed mechanism families for SCM node equations.

| Enum values |
|-------------|
| `linear` |
| `additive_noise` |
| `post_nonlinear` |
| `classifier` |
| `empirical` |
| `parametric_prior` |

### `polisyos.ir.analytics.structural_causal_model.MechanismSource` { #polisyos-ir-analytics-structural-causal-model-mechanismsource }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:MechanismSource`, `polisyos.ir:MechanismSource`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Where a node mechanism was sourced from.

| Enum values |
|-------------|
| `data_fitted` |
| `literature_prior` |
| `hybrid` |
| `default` |

### `polisyos.ir.analytics.structural_causal_model.NodeMechanism` { #polisyos-ir-analytics-structural-causal-model-nodemechanism }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:NodeMechanism`, `polisyos.ir:NodeMechanism`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.structural_causal_model.MechanismFamily`, `polisyos.ir.analytics.structural_causal_model.MechanismSource`
- Summary: Structural equation metadata for one variable in an SCM.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `family` | `polisyos.ir.analytics.structural_causal_model.MechanismFamily` | `yes` | `—` | `polisyos.ir.analytics.structural_causal_model.MechanismFamily` |
| `family_params` | `dict[str, Any]` | `no` | `—` | — |
| `literature_prior` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `noise_distribution` | `str` | `no` | `'empirical'` | — |
| `parents` | `list[str]` | `no` | `—` | — |
| `sensitivity_to_latent` | `float | NoneType` | `no` | `—` | — |
| `source` | `polisyos.ir.analytics.structural_causal_model.MechanismSource` | `no` | `<MechanismSource.DATA_FITTED: 'data_fitted'>` | `polisyos.ir.analytics.structural_causal_model.MechanismSource` |
| `variable` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.structural_causal_model.StructuralCausalModelSpec` { #polisyos-ir-analytics-structural-causal-model-structuralcausalmodelspec }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:StructuralCausalModelSpec`, `polisyos.ir:StructuralCausalModelSpec`
- ABI snapshot: `structural_causal_model_spec` / `schemas/snapshots/ir/structural_causal_model_spec.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_graph.CausalGraphModel`, `polisyos.ir.analytics.structural_causal_model.NodeMechanism`
- Summary: Serializable structural causal model with graph and node mechanisms.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `fit_method` | `Literal[auto, manual, gcm, hybrid] | NoneType` | `no` | `—` | — |
| `fit_metrics` | `dict[str, float]` | `no` | `—` | — |
| `fitted` | `bool` | `no` | `False` | — |
| `graph` | `polisyos.ir.analytics.causal_graph.CausalGraphModel` | `yes` | `—` | `polisyos.ir.analytics.causal_graph.CausalGraphModel` |
| `mechanism_source_summary` | `dict[str, int]` | `no` | `—` | — |
| `mechanisms` | `list[polisyos.ir.analytics.structural_causal_model.NodeMechanism]` | `no` | `—` | `polisyos.ir.analytics.structural_causal_model.NodeMechanism` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `skg_snapshot_ref` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.temporal_frontier.ActiveExperimentDesign` { #polisyos-ir-analytics-temporal-frontier-activeexperimentdesign }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Experiment-design hint emitted by active discovery tooling.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `budget` | `int` | `yes` | `—` | — |
| `candidate_interventions` | `tuple[str]` | `yes` | `—` | — |
| `design_id` | `str` | `yes` | `—` | — |
| `expected_information_gain` | `float | NoneType` | `no` | `—` | — |
| `objective` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.temporal_frontier.DynamicProcessFamily` { #polisyos-ir-analytics-temporal-frontier-dynamicprocessfamily }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:DynamicProcessFamily`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Underlying process family for temporal-discovery outputs.

| Enum values |
|-------------|
| `var` |
| `hawkes` |
| `sde` |
| `regime_switching` |
| `scm` |

### `polisyos.ir.analytics.temporal_frontier.EquivalenceClassSummary` { #polisyos-ir-analytics-temporal-frontier-equivalenceclasssummary }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.temporal_frontier.EquivalenceClassType`
- Summary: Edge sets for a PAG/MAG/CPDAG equivalence class.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `ambiguous_edges` | `tuple[str]` | `no` | `()` | — |
| `class_type` | `polisyos.ir.analytics.temporal_frontier.EquivalenceClassType` | `yes` | `—` | `polisyos.ir.analytics.temporal_frontier.EquivalenceClassType` |
| `compelled_edges` | `tuple[str]` | `no` | `()` | — |
| `reversible_edges` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.temporal_frontier.EquivalenceClassType` { #polisyos-ir-analytics-temporal-frontier-equivalenceclasstype }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:EquivalenceClassType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Graph-equivalence classes produced by discovery.

| Enum values |
|-------------|
| `pag` |
| `mag` |
| `cpdag` |

### `polisyos.ir.analytics.temporal_frontier.RegimeSwitchSegment` { #polisyos-ir-analytics-temporal-frontier-regimeswitchsegment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: One discovered regime segment in a regime-switching process.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `dominant_drivers` | `tuple[str]` | `no` | `()` | — |
| `end_index` | `int` | `yes` | `—` | — |
| `regime_id` | `str` | `yes` | `—` | — |
| `start_index` | `int` | `yes` | `—` | — |

### `polisyos.ir.analytics.temporal_frontier.TemporalDiscoveryEdge` { #polisyos-ir-analytics-temporal-frontier-temporaldiscoveryedge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:TemporalDiscoveryEdge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.temporal_frontier.TemporalDiscoveryMethod`, `polisyos.ir.analytics.temporal_frontier.TemporalEdgeSign`
- Summary: One lagged temporal edge with confidence metadata.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `confidence` | `float` | `yes` | `—` | — |
| `dst` | `str` | `yes` | `—` | — |
| `lag` | `int` | `yes` | `—` | — |
| `sign` | `polisyos.ir.analytics.temporal_frontier.TemporalEdgeSign` | `no` | `<TemporalEdgeSign.UNKNOWN: 'unknown'>` | `polisyos.ir.analytics.temporal_frontier.TemporalEdgeSign` |
| `source_method` | `polisyos.ir.analytics.temporal_frontier.TemporalDiscoveryMethod` | `yes` | `—` | `polisyos.ir.analytics.temporal_frontier.TemporalDiscoveryMethod` |
| `src` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.temporal_frontier.TemporalDiscoveryFrontierReport` { #polisyos-ir-analytics-temporal-frontier-temporaldiscoveryfrontierreport }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:TemporalDiscoveryFrontierReport`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_graph.CausalGraphModel`, `polisyos.ir.analytics.temporal_frontier.ActiveExperimentDesign`, `polisyos.ir.analytics.temporal_frontier.DynamicProcessFamily`, `polisyos.ir.analytics.temporal_frontier.EquivalenceClassSummary`, `polisyos.ir.analytics.temporal_frontier.RegimeSwitchSegment`, `polisyos.ir.analytics.temporal_frontier.TemporalDiscoveryEdge`, `polisyos.ir.analytics.temporal_frontier.TemporalDiscoveryMethod`
- Summary: Frontier report for time-series discovery and dynamic-process outputs.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `active_experiment_design` | `polisyos.ir.analytics.temporal_frontier.ActiveExperimentDesign | NoneType` | `no` | `—` | `polisyos.ir.analytics.temporal_frontier.ActiveExperimentDesign` |
| `edges` | `list[polisyos.ir.analytics.temporal_frontier.TemporalDiscoveryEdge]` | `no` | `—` | `polisyos.ir.analytics.temporal_frontier.TemporalDiscoveryEdge` |
| `equivalence_class` | `polisyos.ir.analytics.temporal_frontier.EquivalenceClassSummary | NoneType` | `no` | `—` | `polisyos.ir.analytics.temporal_frontier.EquivalenceClassSummary` |
| `execution_semantics` | `Literal[time_series_research, discovery_report]` | `no` | `'time_series_research'` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `method` | `polisyos.ir.analytics.temporal_frontier.TemporalDiscoveryMethod` | `yes` | `—` | `polisyos.ir.analytics.temporal_frontier.TemporalDiscoveryMethod` |
| `process_family` | `polisyos.ir.analytics.temporal_frontier.DynamicProcessFamily` | `yes` | `—` | `polisyos.ir.analytics.temporal_frontier.DynamicProcessFamily` |
| `regime_segments` | `list[polisyos.ir.analytics.temporal_frontier.RegimeSwitchSegment]` | `no` | `—` | `polisyos.ir.analytics.temporal_frontier.RegimeSwitchSegment` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `unified_graph` | `polisyos.ir.analytics.causal_graph.CausalGraphModel | NoneType` | `no` | `—` | `polisyos.ir.analytics.causal_graph.CausalGraphModel` |
| `warnings` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.temporal_frontier.TemporalDiscoveryMethod` { #polisyos-ir-analytics-temporal-frontier-temporaldiscoverymethod }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:TemporalDiscoveryMethod`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Time-series/discovery methods surfaced by the IR.

| Enum values |
|-------------|
| `pcmci` |
| `pcmci_plus` |
| `granger` |
| `hawkes` |
| `regime_switching_scm` |
| `linear_sde` |

### `polisyos.ir.analytics.temporal_frontier.TemporalEdgeSign` { #polisyos-ir-analytics-temporal-frontier-temporaledgesign }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Qualitative sign for a temporal/discovery edge.

| Enum values |
|-------------|
| `positive` |
| `negative` |
| `unknown` |

### `polisyos.ir.analytics.transportability.DataGap` { #polisyos-ir-analytics-transportability-datagap }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Data gap public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `available_proxies` | `list[ProxyCandidate]` | `no` | `—` | — |
| `best_proxy_confidence` | `float` | `no` | `0.0` | — |
| `gap_impact` | `str` | `yes` | `—` | — |
| `required_context` | `str` | `yes` | `—` | — |
| `required_variable` | `str` | `yes` | `—` | — |
| `suggested_action` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.transportability.MultiSourceSelectionDiagram` { #polisyos-ir-analytics-transportability-multisourceselectiondiagram }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_graph.CausalGraphModel`, `polisyos.ir.analytics.context.ContextProfile`, `polisyos.ir.analytics.transportability.SourceDomainSpec`
- Summary: Selection diagram for multi-source (mz-ID) transportability.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `base_graph` | `polisyos.ir.analytics.causal_graph.CausalGraphModel` | `yes` | `—` | `polisyos.ir.analytics.causal_graph.CausalGraphModel` |
| `domains` | `tuple[polisyos.ir.analytics.transportability.SourceDomainSpec]` | `no` | `()` | `polisyos.ir.analytics.transportability.SourceDomainSpec` |
| `target_context` | `polisyos.ir.analytics.context.ContextProfile` | `yes` | `—` | `polisyos.ir.analytics.context.ContextProfile` |

### `polisyos.ir.analytics.transportability.SNode` { #polisyos-ir-analytics-transportability-snode }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.transportability.SNodeOrigin`, `polisyos.ir.analytics.transportability.SNodeRole`
- Summary: S node implementation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `context_dimension` | `str` | `yes` | `—` | — |
| `delta` | `float` | `yes` | `—` | — |
| `legal_constraint_id` | `str | NoneType` | `no` | `—` | — |
| `origin` | `polisyos.ir.analytics.transportability.SNodeOrigin` | `no` | `<SNodeOrigin.CONTEXT_DELTA: 'context_delta'>` | `polisyos.ir.analytics.transportability.SNodeOrigin` |
| `role` | `polisyos.ir.analytics.transportability.SNodeRole | NoneType` | `no` | `—` | `polisyos.ir.analytics.transportability.SNodeRole` |
| `severity` | `Literal[low, medium, high]` | `yes` | `—` | — |
| `source_value` | `float | str` | `yes` | `—` | — |
| `target_value` | `float | str` | `yes` | `—` | — |
| `target_variable` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.transportability.SNodeOrigin` { #polisyos-ir-analytics-transportability-snodeorigin }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Classify why a selection node appears in a transportability diagram.

| Enum values |
|-------------|
| `context_delta` |
| `legal` |
| `data_mismatch` |

### `polisyos.ir.analytics.transportability.SNodeRole` { #polisyos-ir-analytics-transportability-snoderole }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Declare the causal role used when deciding whether an S-node is adjustable.

| Enum values |
|-------------|
| `pre_treatment_covariate` |
| `mediator` |
| `collider` |
| `instrument` |

### `polisyos.ir.analytics.transportability.SelectionDiagram` { #polisyos-ir-analytics-transportability-selectiondiagram }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_graph.CausalGraphModel`, `polisyos.ir.analytics.context.ContextProfile`, `polisyos.ir.analytics.transportability.SNode`
- Summary: Selection diagram public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `base_graph` | `polisyos.ir.analytics.causal_graph.CausalGraphModel` | `yes` | `—` | `polisyos.ir.analytics.causal_graph.CausalGraphModel` |
| `context_distance` | `float` | `no` | `0.0` | — |
| `s_nodes` | `list[polisyos.ir.analytics.transportability.SNode]` | `no` | `—` | `polisyos.ir.analytics.transportability.SNode` |
| `source_context` | `polisyos.ir.analytics.context.ContextProfile` | `yes` | `—` | `polisyos.ir.analytics.context.ContextProfile` |
| `target_context` | `polisyos.ir.analytics.context.ContextProfile` | `yes` | `—` | `polisyos.ir.analytics.context.ContextProfile` |

### `polisyos.ir.analytics.transportability.SelectionDiagramBuilder` { #polisyos-ir-analytics-transportability-selectiondiagrambuilder }

- Kind: `class`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Fluent builder for :class:`SelectionDiagram` without requiring a ContextProfile.

### `polisyos.ir.analytics.transportability.SigmaVariable` { #polisyos-ir-analytics-transportability-sigmavariable }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.transportability.SNodeOrigin`
- Summary: Formal σ-variable (selection variable) for a mechanism shift between domains.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `is_resolved` | `bool` | `no` | `False` | — |
| `node_name` | `str` | `yes` | `—` | — |
| `origin` | `polisyos.ir.analytics.transportability.SNodeOrigin` | `no` | `<SNodeOrigin.CONTEXT_DELTA: 'context_delta'>` | `polisyos.ir.analytics.transportability.SNodeOrigin` |
| `resolving_adjustment_set` | `tuple[str]` | `no` | `()` | — |
| `variable_name` | `str` | `yes` | `—` | — |

### `polisyos.ir.analytics.transportability.SourceDomainSpec` { #polisyos-ir-analytics-transportability-sourcedomainspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.context.ContextProfile`, `polisyos.ir.analytics.transportability.SNode`
- Summary: Specification for a single source domain in a multi-domain transport scenario.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `dataset_ref` | `str | NoneType` | `no` | `—` | — |
| `domain_id` | `str` | `yes` | `—` | — |
| `s_nodes` | `tuple[polisyos.ir.analytics.transportability.SNode]` | `no` | `()` | `polisyos.ir.analytics.transportability.SNode` |
| `source_context` | `polisyos.ir.analytics.context.ContextProfile | NoneType` | `no` | `—` | `polisyos.ir.analytics.context.ContextProfile` |
| `z_interventions` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.analytics.transportability.StratificationVariable` { #polisyos-ir-analytics-transportability-stratificationvariable }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.transportability.SNodeRole`
- Summary: Stratification variable public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `condition_on_treatment` | `str | NoneType` | `no` | `—` | — |
| `name` | `str` | `yes` | `—` | — |
| `requires_conditional` | `bool` | `yes` | `—` | — |
| `role` | `polisyos.ir.analytics.transportability.SNodeRole` | `yes` | `—` | `polisyos.ir.analytics.transportability.SNodeRole` |

### `polisyos.ir.analytics.transportability.TransportFormula` { #polisyos-ir-analytics-transportability-transportformula }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.transportability.StratificationVariable`
- Summary: Transport formula public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `adjustment_type` | `str` | `no` | `'direct'` | — |
| `formula_str` | `str` | `yes` | `—` | — |
| `source_quantities` | `list[str]` | `no` | `—` | — |
| `stratification_details` | `list[polisyos.ir.analytics.transportability.StratificationVariable]` | `no` | `—` | `polisyos.ir.analytics.transportability.StratificationVariable` |
| `stratification_variables` | `list[str]` | `no` | `—` | — |
| `target_quantities` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.transportability.TransportMode` { #polisyos-ir-analytics-transportability-transportmode }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Describe the execution path implied by a ``TransportabilityResult``.

| Enum values |
|-------------|
| `direct` |
| `transport_formula` |
| `bounds_only` |
| `none` |

### `polisyos.ir.analytics.transportability.TransportabilityResult` { #polisyos-ir-analytics-transportability-transportabilityresult }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `2.0`
- Exported from: `polisyos.ir.analytics:TransportabilityResult`, `polisyos.ir:TransportabilityResult`
- ABI snapshot: `transportability_result` / `schemas/snapshots/ir/transportability_result.schema.json`
- Compatibility mode: `backward`
- References: `polisyos.ir.analytics.causal_graph.PAGIdentificationPolicy`, `polisyos.ir.analytics.partial_identification.PartialIdentificationResult`, `polisyos.ir.analytics.transportability.DataGap`, `polisyos.ir.analytics.transportability.SNode`, `polisyos.ir.analytics.transportability.TransportFormula`, `polisyos.ir.analytics.transportability.TransportMode`, `polisyos.ir.analytics.transportability.TransportabilityStatus`
- Summary: Persist the transportability decision, formula, and fallback diagnostics.
- Declared readable versions: `1.0`

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `algorithm_version` | `str` | `no` | `'trso_v2'` | — |
| `assumes_time_stationarity` | `bool` | `no` | `True` | — |
| `base_confidence` | `float` | `no` | `1.0` | — |
| `blocking_s_nodes` | `list[polisyos.ir.analytics.transportability.SNode]` | `no` | `—` | `polisyos.ir.analytics.transportability.SNode` |
| `context_distance_penalty` | `float` | `no` | `0.0` | — |
| `data_availability_penalty` | `float` | `no` | `0.0` | — |
| `data_gaps` | `list[polisyos.ir.analytics.transportability.DataGap]` | `no` | `—` | `polisyos.ir.analytics.transportability.DataGap` |
| `estimand_ast` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `expert_review_reasons` | `list[str]` | `no` | `—` | — |
| `feasible` | `bool` | `no` | `True` | — |
| `final_confidence` | `float` | `no` | `1.0` | — |
| `hard_legal_constraints` | `list[str]` | `no` | `—` | — |
| `id_confidence_under_pag` | `float | NoneType` | `no` | `—` | — |
| `identification_engine` | `str` | `no` | `'simplified_legacy'` | — |
| `identification_trace` | `list[str]` | `no` | `—` | — |
| `identified_region` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `lagged_edge_count` | `int` | `no` | `0` | — |
| `lagged_edges_in_query` | `bool` | `no` | `False` | — |
| `legal_s_nodes` | `list[polisyos.ir.analytics.transportability.SNode]` | `no` | `—` | `polisyos.ir.analytics.transportability.SNode` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `outer_search_best_score` | `float | NoneType` | `no` | `—` | — |
| `outer_search_configs_evaluated` | `int` | `no` | `0` | — |
| `outer_search_truncated` | `bool` | `no` | `False` | — |
| `p_star_values` | `dict[str, PStarZResult]` | `no` | `—` | — |
| `pag_dag_sample_size` | `int | NoneType` | `no` | `—` | — |
| `pag_identification_policy` | `polisyos.ir.analytics.causal_graph.PAGIdentificationPolicy | NoneType` | `no` | `—` | `polisyos.ir.analytics.causal_graph.PAGIdentificationPolicy` |
| `pag_transportable_count` | `int | NoneType` | `no` | `—` | — |
| `partial_identification_result` | `polisyos.ir.analytics.partial_identification.PartialIdentificationResult | NoneType` | `no` | `—` | `polisyos.ir.analytics.partial_identification.PartialIdentificationResult` |
| `proxy_penalties` | `dict[str, float]` | `no` | `—` | — |
| `proxy_validity` | `dict[str, dict[str, Any]]` | `no` | `—` | — |
| `query` | `str` | `no` | `''` | — |
| `required_target_data` | `list[str]` | `no` | `—` | — |
| `requires_expert_review` | `bool` | `no` | `False` | — |
| `resolution_rounds` | `int` | `no` | `1` | — |
| `schema_version` | `str` | `no` | `'2.0'` | — |
| `search_budget_exhausted` | `bool` | `no` | `False` | — |
| `search_events` | `list[str]` | `no` | `—` | — |
| `selection_diagram_ref` | `str` | `no` | `''` | — |
| `source_context_id` | `str` | `no` | `''` | — |
| `status` | `polisyos.ir.analytics.transportability.TransportabilityStatus` | `no` | `<TransportabilityStatus.IDENTIFIED: 'identified'>` | `polisyos.ir.analytics.transportability.TransportabilityStatus` |
| `sutva_assumed` | `bool` | `no` | `True` | — |
| `sutva_violation_risk` | `Literal[high, medium, low] | NoneType` | `no` | `—` | — |
| `target_context_id` | `str` | `no` | `''` | — |
| `temporal_distance_penalty` | `float` | `no` | `0.0` | — |
| `time_stationarity_warning` | `str | NoneType` | `no` | `—` | — |
| `transport_formula` | `polisyos.ir.analytics.transportability.TransportFormula | NoneType` | `no` | `—` | `polisyos.ir.analytics.transportability.TransportFormula` |
| `transport_mode` | `polisyos.ir.analytics.transportability.TransportMode` | `no` | `<TransportMode.DIRECT: 'direct'>` | `polisyos.ir.analytics.transportability.TransportMode` |
| `unsupported_cases` | `list[str]` | `no` | `—` | — |
| `unsupported_reason` | `str | NoneType` | `no` | `—` | — |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.analytics.transportability.TransportabilityStatus` { #polisyos-ir-analytics-transportability-transportabilitystatus }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Report whether transportability is identified, bounded, or blocked.

| Enum values |
|-------------|
| `identified` |
| `partially_identified` |
| `bounded_non_identified` |
| `unsupported` |

### `polisyos.ir.analytics.twin_network.TwinNetworkResult` { #polisyos-ir-analytics-twin-network-twinnetworkresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_queries.InterventionSpec`
- Summary: Output of a twin-network joint counterfactual query.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `abduction_warnings` | `list[str]` | `no` | `—` | — |
| `computation_time_seconds` | `float` | `no` | `0.0` | — |
| `counterfactual_intervention` | `polisyos.ir.analytics.causal_queries.InterventionSpec` | `yes` | `—` | `polisyos.ir.analytics.causal_queries.InterventionSpec` |
| `factual_intervention` | `polisyos.ir.analytics.causal_queries.InterventionSpec` | `yes` | `—` | `polisyos.ir.analytics.causal_queries.InterventionSpec` |
| `ite_ci` | `tuple[float, float]` | `yes` | `—` | — |
| `ite_distribution` | `list[float] | NoneType` | `no` | `—` | — |
| `ite_mean` | `float` | `yes` | `—` | — |
| `ite_std` | `float` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `outcome_variable` | `str` | `yes` | `—` | — |
| `po_correlation` | `float` | `yes` | `—` | — |
| `po_counter_distribution` | `list[float] | NoneType` | `no` | `—` | — |
| `po_counter_mean` | `float` | `yes` | `—` | — |
| `po_counter_std` | `float` | `yes` | `—` | — |
| `po_factual_distribution` | `list[float] | NoneType` | `no` | `—` | — |
| `po_factual_mean` | `float` | `yes` | `—` | — |
| `po_factual_std` | `float` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.analytics.twin_network.TwinWorldSample` { #polisyos-ir-analytics-twin-network-twinworldsample }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: One realisation of the factual + counterfactual world sharing the same U.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `counterfactual_values` | `dict[str, float]` | `yes` | `—` | — |
| `factual_values` | `dict[str, float]` | `yes` | `—` | — |
| `individual_treatment_effect` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.uncertainty.DistributionFamily` { #polisyos-ir-analytics-uncertainty-distributionfamily }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:DistributionFamily`, `polisyos.ir:DistributionFamily`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Declare the assumed sampling/posterior family behind an interval estimate.

| Enum values |
|-------------|
| `normal` |
| `bootstrap` |
| `bayesian` |
| `uniform` |
| `triangular` |
| `unknown` |

### `polisyos.ir.analytics.uncertainty.EnvelopeCombinationMethod` { #polisyos-ir-analytics-uncertainty-envelopecombinationmethod }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Supported combination semantics for compatible uncertainty envelopes.

| Enum values |
|-------------|
| `intersection` |
| `conservative_union` |
| `precision_weighted` |

### `polisyos.ir.analytics.uncertainty.IntervalSemantics` { #polisyos-ir-analytics-uncertainty-intervalsemantics }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:IntervalSemantics`, `polisyos.ir:IntervalSemantics`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Tell governance/reporting whether an interval is statistical or heuristic.

| Enum values |
|-------------|
| `confidence_interval` |
| `credible_interval` |
| `deterministic_bounds` |
| `heuristic_range` |

### `polisyos.ir.analytics.uncertainty.MixtureComponent` { #polisyos-ir-analytics-uncertainty-mixturecomponent }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.uncertainty.DistributionFamily`
- Summary: One component of a mixture distribution carrier.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `family` | `polisyos.ir.analytics.uncertainty.DistributionFamily` | `yes` | `—` | `polisyos.ir.analytics.uncertainty.DistributionFamily` |
| `parameters` | `dict[str, float]` | `yes` | `—` | — |
| `weight` | `float` | `yes` | `—` | — |

### `polisyos.ir.analytics.uncertainty.MixtureDistributionCarrier` { #polisyos-ir-analytics-uncertainty-mixturedistributioncarrier }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.uncertainty.MixtureComponent`
- Summary: Carry a finite mixture approximation of the posterior distribution.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `carrier_type` | `Literal[mixture_distribution]` | `no` | `'mixture_distribution'` | — |
| `components` | `tuple[polisyos.ir.analytics.uncertainty.MixtureComponent]` | `yes` | `—` | `polisyos.ir.analytics.uncertainty.MixtureComponent` |

### `polisyos.ir.analytics.uncertainty.NumericPolicySpec` { #polisyos-ir-analytics-uncertainty-numericpolicyspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.uncertainty.NumericToleranceMode`
- Summary: Explicit numeric policy for envelope canonicalization.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `absolute_tolerance` | `float` | `no` | `1e-12` | — |
| `decimal_places` | `int` | `no` | `12` | — |
| `mode` | `polisyos.ir.analytics.uncertainty.NumericToleranceMode` | `no` | `<NumericToleranceMode.FLOAT_ROUND_12: 'float_round_12'>` | `polisyos.ir.analytics.uncertainty.NumericToleranceMode` |
| `policy_id` | `str` | `no` | `'bounded_float_v1'` | — |

### `polisyos.ir.analytics.uncertainty.NumericToleranceMode` { #polisyos-ir-analytics-uncertainty-numerictolerancemode }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: How float payloads are canonicalized before persistence and composition.

| Enum values |
|-------------|
| `decimal_exact` |
| `float_round_12` |
| `hybrid` |

### `polisyos.ir.analytics.uncertainty.ParametricFitCarrier` { #polisyos-ir-analytics-uncertainty-parametricfitcarrier }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.uncertainty.DistributionFamily`
- Summary: Carry the parameters of a parametric fit used to derive the interval.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `carrier_type` | `Literal[parametric_fit]` | `no` | `'parametric_fit'` | — |
| `family` | `polisyos.ir.analytics.uncertainty.DistributionFamily` | `yes` | `—` | `polisyos.ir.analytics.uncertainty.DistributionFamily` |
| `parameters` | `dict[str, float]` | `yes` | `—` | — |
| `support` | `tuple[float, float] | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.uncertainty.PosteriorSamplesCarrier` { #polisyos-ir-analytics-uncertainty-posteriorsamplescarrier }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Carry posterior/bootstrap draws when an interval alone is not expressive enough.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `carrier_type` | `Literal[posterior_samples]` | `no` | `'posterior_samples'` | — |
| `sample_axis` | `str` | `no` | `'draw'` | — |
| `samples` | `tuple[float]` | `yes` | `—` | — |
| `weights` | `tuple[float] | NoneType` | `no` | `—` | — |

### `polisyos.ir.analytics.uncertainty.PropagationMethod` { #polisyos-ir-analytics-uncertainty-propagationmethod }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:PropagationMethod`, `polisyos.ir:PropagationMethod`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Declare how uncertainty was propagated before the interval reached the IR.

| Enum values |
|-------------|
| `delta_method` |
| `monte_carlo` |
| `analytical` |
| `none` |

### `polisyos.ir.analytics.uncertainty.QuantileSummaryCarrier` { #polisyos-ir-analytics-uncertainty-quantilesummarycarrier }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Carry quantile summaries for calibrated posteriors.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `carrier_type` | `Literal[quantile_summary]` | `no` | `'quantile_summary'` | — |
| `quantiles` | `dict[str, float]` | `yes` | `—` | — |

### `polisyos.ir.analytics.uncertainty.UncertaintyCompatibilityError` { #polisyos-ir-analytics-uncertainty-uncertaintycompatibilityerror }

- Kind: `class`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Raised when envelopes with incompatible interval semantics are combined.

### `polisyos.ir.analytics.uncertainty.UncertaintyEnvelope` { #polisyos-ir-analytics-uncertainty-uncertaintyenvelope }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.analytics:UncertaintyEnvelope`, `polisyos.ir:UncertaintyEnvelope`
- ABI snapshot: `uncertainty_envelope` / `schemas/snapshots/ir/uncertainty_envelope.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.uncertainty.DistributionFamily`, `polisyos.ir.analytics.uncertainty.IntervalSemantics`, `polisyos.ir.analytics.uncertainty.MixtureDistributionCarrier`, `polisyos.ir.analytics.uncertainty.NumericPolicySpec`, `polisyos.ir.analytics.uncertainty.ParametricFitCarrier`, `polisyos.ir.analytics.uncertainty.PosteriorSamplesCarrier`, `polisyos.ir.analytics.uncertainty.PropagationMethod`, `polisyos.ir.analytics.uncertainty.QuantileSummaryCarrier`, `polisyos.ir.analytics.uncertainty.UncertaintySource`
- Summary: Unified uncertainty contract shared across PolicyOS IR artifacts.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `confidence_interval` | `tuple[float, float]` | `yes` | `—` | — |
| `confidence_level` | `float | NoneType` | `no` | `0.95` | — |
| `distribution_family` | `polisyos.ir.analytics.uncertainty.DistributionFamily` | `no` | `<DistributionFamily.UNKNOWN: 'unknown'>` | `polisyos.ir.analytics.uncertainty.DistributionFamily` |
| `distribution_payload` | `polisyos.ir.analytics.uncertainty.PosteriorSamplesCarrier | polisyos.ir.analytics.uncertainty.QuantileSummaryCarrier | polisyos.ir.analytics.uncertainty.ParametricFitCarrier | polisyos.ir.analytics.uncertainty.MixtureDistributionCarrier | NoneType` | `no` | `—` | `polisyos.ir.analytics.uncertainty.MixtureDistributionCarrier`, `polisyos.ir.analytics.uncertainty.ParametricFitCarrier`, `polisyos.ir.analytics.uncertainty.PosteriorSamplesCarrier`, `polisyos.ir.analytics.uncertainty.QuantileSummaryCarrier` |
| `gate_eligible` | `bool` | `no` | `True` | — |
| `interval_semantics` | `polisyos.ir.analytics.uncertainty.IntervalSemantics` | `no` | `<IntervalSemantics.CONFIDENCE_INTERVAL: 'confidence_interval'>` | `polisyos.ir.analytics.uncertainty.IntervalSemantics` |
| `is_heuristic_ci` | `bool` | `no` | `False` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `numeric_policy` | `polisyos.ir.analytics.uncertainty.NumericPolicySpec` | `no` | `—` | `polisyos.ir.analytics.uncertainty.NumericPolicySpec` |
| `point_estimate` | `float` | `yes` | `—` | — |
| `propagation_method` | `polisyos.ir.analytics.uncertainty.PropagationMethod` | `no` | `<PropagationMethod.NONE: 'none'>` | `polisyos.ir.analytics.uncertainty.PropagationMethod` |
| `sample_size` | `int | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `source` | `polisyos.ir.analytics.uncertainty.UncertaintySource` | `yes` | `—` | `polisyos.ir.analytics.uncertainty.UncertaintySource` |

### `polisyos.ir.analytics.uncertainty.UncertaintySource` { #polisyos-ir-analytics-uncertainty-uncertaintysource }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.analytics:UncertaintySource`, `polisyos.ir:UncertaintySource`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Origin of the uncertainty interval carried in the IR.

| Enum values |
|-------------|
| `calibration` |
| `trust` |
| `conflict_resolution` |
| `causal` |
| `bootstrap` |
| `ensemble` |
| `manual` |

## Artifacts

### `polisyos.ir.artifacts.contracts.ArtifactID` { #polisyos-ir-artifacts-contracts-artifactid }

- Kind: `root_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:ArtifactID`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: IR-local artifact ID model compatible with CAS interfaces.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `root` | `str` | `yes` | `—` | — |

### `polisyos.ir.artifacts.contracts.ArtifactStore` { #polisyos-ir-artifacts-contracts-artifactstore }

- Kind: `protocol`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:ArtifactStore`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Minimal CAS protocol required by IR helpers for writing JSON and reading raw bytes.

### `polisyos.ir.artifacts.contracts.CanonInfo` { #polisyos-ir-artifacts-contracts-canoninfo }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:CanonInfo`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Record the canonicalization rules that were in force when an artifact was serialized.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `ensure_ascii` | `bool` | `no` | `False` | — |
| `exclude_none` | `bool` | `no` | `True` | — |
| `forbid_floats` | `bool` | `no` | `True` | — |
| `forbid_nan_inf` | `bool` | `no` | `True` | — |
| `max_depth` | `int` | `no` | `128` | — |
| `name` | `str` | `no` | `'polisyos.canon.json'` | — |
| `separators` | `tuple[str, str]` | `no` | `(',', ':')` | — |
| `sort_keys` | `bool` | `no` | `True` | — |
| `version` | `str` | `no` | `'0.2.0'` | — |

### `polisyos.ir.artifacts.contracts.InputRef` { #polisyos-ir-artifacts-contracts-inputref }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:InputRef`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Identify an upstream artifact that should be recorded in persistence lineage metadata.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `role` | `str` | `yes` | `—` | — |

### `polisyos.ir.artifacts.contracts.PutOptions` { #polisyos-ir-artifacts-contracts-putoptions }

- Kind: `dataclass`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:PutOptions`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Collect the metadata that IR helpers attach when persisting a JSON artifact.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `str` | `yes` | `—` | — |
| `media_type` | `str` | `yes` | `—` | — |
| `schema` | `SchemaInfo | None` | `no` | `None` | — |
| `producer` | `Any` | `no` | `None` | — |
| `env` | `Any` | `no` | `None` | — |
| `inputs` | `list[InputRef] | None` | `no` | `None` | — |
| `canon` | `CanonInfo | None` | `no` | `None` | — |

### `polisyos.ir.artifacts.contracts.SchemaInfo` { #polisyos-ir-artifacts-contracts-schemainfo }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:SchemaInfo`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Describe the schema name and version stamped onto a persisted artifact payload.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `name` | `str` | `yes` | `—` | — |
| `version` | `str` | `yes` | `—` | — |

### `polisyos.ir.artifacts.contracts.StorePutOptions` { #polisyos-ir-artifacts-contracts-storeputoptions }

- Kind: `dataclass`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:StorePutOptions`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Duck-typed options compatible with core FileSystemCAS.put_json.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `str` | `yes` | `—` | — |
| `media_type` | `str` | `yes` | `—` | — |
| `schema` | `dict[str, Any] | None` | `no` | `None` | — |
| `producer` | `Any` | `no` | `None` | — |
| `env` | `Any` | `no` | `None` | — |
| `inputs` | `list[dict[str, Any]] | None` | `no` | `None` | — |
| `canon` | `dict[str, Any] | None` | `no` | `None` | — |

### `polisyos.ir.artifacts.lineage.ArtifactLineageEdge` { #polisyos-ir-artifacts-lineage-artifactlineageedge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:ArtifactLineageEdge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.lineage.ArtifactLineageRelationKind`
- Summary: One directed lineage relation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `relation` | `polisyos.ir.artifacts.lineage.ArtifactLineageRelationKind` | `yes` | `—` | `polisyos.ir.artifacts.lineage.ArtifactLineageRelationKind` |
| `role` | `str | NoneType` | `no` | `—` | — |
| `source_node_id` | `str` | `yes` | `—` | — |
| `target_node_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.artifacts.lineage.ArtifactLineageGraph` { #polisyos-ir-artifacts-lineage-artifactlineagegraph }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.artifacts:ArtifactLineageGraph`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.lineage.ArtifactLineageEdge`, `polisyos.ir.artifacts.lineage.ArtifactLineageNode`
- Summary: Normalized lineage graph built from manifests plus optional task bindings.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `edges` | `tuple[polisyos.ir.artifacts.lineage.ArtifactLineageEdge]` | `no` | `()` | `polisyos.ir.artifacts.lineage.ArtifactLineageEdge` |
| `nodes` | `tuple[polisyos.ir.artifacts.lineage.ArtifactLineageNode]` | `no` | `()` | `polisyos.ir.artifacts.lineage.ArtifactLineageNode` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.artifacts.lineage.ArtifactLineageNode` { #polisyos-ir-artifacts-lineage-artifactlineagenode }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:ArtifactLineageNode`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`, `polisyos.ir.artifacts.lineage.ArtifactLineageNodeKind`
- Summary: One artifact or task vertex in the normalized lineage graph.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID | NoneType` | `no` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `artifact_kind` | `str | NoneType` | `no` | `—` | — |
| `kind` | `polisyos.ir.artifacts.lineage.ArtifactLineageNodeKind` | `yes` | `—` | `polisyos.ir.artifacts.lineage.ArtifactLineageNodeKind` |
| `label` | `str | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `node_id` | `str` | `yes` | `—` | — |
| `task_id` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.artifacts.lineage.ArtifactLineageNodeKind` { #polisyos-ir-artifacts-lineage-artifactlineagenodekind }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:ArtifactLineageNodeKind`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Kinds of nodes that can appear in the lineage graph.

| Enum values |
|-------------|
| `artifact` |
| `task` |

### `polisyos.ir.artifacts.lineage.ArtifactLineageRelationKind` { #polisyos-ir-artifacts-lineage-artifactlineagerelationkind }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:ArtifactLineageRelationKind`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Directed lineage edge semantics.

| Enum values |
|-------------|
| `produced_by` |
| `consumed_by` |
| `derived_from` |
| `invalidated_by` |

### `polisyos.ir.artifacts.lineage.ArtifactTaskBinding` { #polisyos-ir-artifacts-lineage-artifacttaskbinding }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:ArtifactTaskBinding`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Attach semantic task ids to one or more produced/consumed artifacts.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `consumed_artifact_ids` | `tuple[polisyos.ir.artifacts.contracts.ArtifactID]` | `no` | `()` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `invalidated_artifact_ids` | `tuple[polisyos.ir.artifacts.contracts.ArtifactID]` | `no` | `()` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `produced_artifact_ids` | `tuple[polisyos.ir.artifacts.contracts.ArtifactID]` | `no` | `()` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `task_id` | `str` | `yes` | `—` | — |
| `task_kind` | `str` | `no` | `'task'` | — |

### `polisyos.ir.artifacts.transport.ArtifactDeltaEntry` { #polisyos-ir-artifacts-transport-artifactdeltaentry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:ArtifactDeltaEntry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`, `polisyos.ir.artifacts.transport.StreamUpdateOperation`
- Summary: One logical delta item applied against a base artifact family.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `entity_key` | `str` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `operation` | `polisyos.ir.artifacts.transport.StreamUpdateOperation` | `yes` | `—` | `polisyos.ir.artifacts.transport.StreamUpdateOperation` |
| `payload_artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID | NoneType` | `no` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `payload_offset` | `int | NoneType` | `no` | `—` | — |

### `polisyos.ir.artifacts.transport.ArtifactDeltaEnvelope` { #polisyos-ir-artifacts-transport-artifactdeltaenvelope }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.artifacts:ArtifactDeltaEnvelope`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`, `polisyos.ir.artifacts.transport.ArtifactDeltaEntry`, `polisyos.ir.artifacts.transport.DeltaSemantics`
- Summary: Generic delta envelope for incremental IR artifact refresh.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `base_artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID | NoneType` | `no` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `emitted_at` | `datetime` | `yes` | `—` | — |
| `entries` | `list[polisyos.ir.artifacts.transport.ArtifactDeltaEntry]` | `no` | `—` | `polisyos.ir.artifacts.transport.ArtifactDeltaEntry` |
| `family` | `str` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `semantics` | `polisyos.ir.artifacts.transport.DeltaSemantics` | `no` | `<DeltaSemantics.UPSERT: 'upsert'>` | `polisyos.ir.artifacts.transport.DeltaSemantics` |

### `polisyos.ir.artifacts.transport.BinaryWireFormat` { #polisyos-ir-artifacts-transport-binarywireformat }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:BinaryWireFormat`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Enumerate candidate binary wire formats considered by the IR transport layer.

| Enum values |
|-------------|
| `protobuf` |
| `msgpack` |
| `arrow_ipc_stream` |
| `flatbuffers` |

### `polisyos.ir.artifacts.transport.DeltaSemantics` { #polisyos-ir-artifacts-transport-deltasemantics }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:DeltaSemantics`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Describe how a delta artifact should be interpreted against its base payload.

| Enum values |
|-------------|
| `append_only` |
| `upsert` |
| `full_replace` |

### `polisyos.ir.artifacts.transport.IncrementalRelinkManifest` { #polisyos-ir-artifacts-transport-incrementalrelinkmanifest }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.artifacts:IncrementalRelinkManifest`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Describe which linker surfaces must be re-evaluated after a delta lands.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `affected_constraints` | `list[str]` | `no` | `—` | — |
| `affected_mechanisms` | `list[str]` | `no` | `—` | — |
| `affected_queries` | `list[str]` | `no` | `—` | — |
| `affected_slots` | `list[str]` | `no` | `—` | — |
| `bundle_artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `delta_artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID | NoneType` | `no` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `notes` | `list[str]` | `no` | `—` | — |
| `requires_full_relink` | `bool` | `no` | `False` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.artifacts.transport.ObservationBinaryBatchArtifact` { #polisyos-ir-artifacts-transport-observationbinarybatchartifact }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.artifacts:ObservationBinaryBatchArtifact`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`, `polisyos.ir.artifacts.transport.BinaryWireFormat`, `polisyos.ir.artifacts.transport.DeltaSemantics`, `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: Pilot binary sidecar contract for large observation-record batches.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `base_artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID | NoneType` | `no` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `batch_id` | `str` | `yes` | `—` | — |
| `binary_artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `binary_media_type` | `str` | `no` | `'application/vnd.apache.arrow.stream'` | — |
| `delta_semantics` | `polisyos.ir.artifacts.transport.DeltaSemantics` | `no` | `<DeltaSemantics.APPEND_ONLY: 'append_only'>` | `polisyos.ir.artifacts.transport.DeltaSemantics` |
| `family` | `polisyos.ir.observation.contracts.ObservationFamily` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `field_names` | `list[str]` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `record_count` | `int` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `wire_format` | `polisyos.ir.artifacts.transport.BinaryWireFormat` | `no` | `<BinaryWireFormat.ARROW_IPC_STREAM: 'arrow_ipc_stream'>` | `polisyos.ir.artifacts.transport.BinaryWireFormat` |

### `polisyos.ir.artifacts.transport.ObservationStreamCheckpoint` { #polisyos-ir-artifacts-transport-observationstreamcheckpoint }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.artifacts:ObservationStreamCheckpoint`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable resume point for observation-heavy streaming ingestion.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `checkpoint_artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `cursor` | `int` | `yes` | `—` | — |
| `emitted_at` | `datetime` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `stream_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.artifacts.transport.ObservationStreamEntry` { #polisyos-ir-artifacts-transport-observationstreamentry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:ObservationStreamEntry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`, `polisyos.ir.artifacts.transport.StreamUpdateOperation`, `polisyos.ir.observation.contracts.ObservationRecord`
- Summary: One logical observation update emitted by a streaming source.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `operation` | `polisyos.ir.artifacts.transport.StreamUpdateOperation` | `yes` | `—` | `polisyos.ir.artifacts.transport.StreamUpdateOperation` |
| `prior_artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID | NoneType` | `no` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `record` | `polisyos.ir.observation.contracts.ObservationRecord | NoneType` | `no` | `—` | `polisyos.ir.observation.contracts.ObservationRecord` |
| `sequence_no` | `int` | `yes` | `—` | — |

### `polisyos.ir.artifacts.transport.ObservationStreamUpdate` { #polisyos-ir-artifacts-transport-observationstreamupdate }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.artifacts:ObservationStreamUpdate`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.transport.ArtifactDeltaEnvelope`, `polisyos.ir.artifacts.transport.IncrementalRelinkManifest`, `polisyos.ir.artifacts.transport.ObservationBinaryBatchArtifact`, `polisyos.ir.artifacts.transport.ObservationStreamCheckpoint`, `polisyos.ir.artifacts.transport.ObservationStreamEntry`
- Summary: Streaming update envelope for observation ingestion with optional Arrow sidecars.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `binary_batch` | `polisyos.ir.artifacts.transport.ObservationBinaryBatchArtifact | NoneType` | `no` | `—` | `polisyos.ir.artifacts.transport.ObservationBinaryBatchArtifact` |
| `checkpoint` | `polisyos.ir.artifacts.transport.ObservationStreamCheckpoint | NoneType` | `no` | `—` | `polisyos.ir.artifacts.transport.ObservationStreamCheckpoint` |
| `chunk_id` | `str` | `yes` | `—` | — |
| `delta` | `polisyos.ir.artifacts.transport.ArtifactDeltaEnvelope | NoneType` | `no` | `—` | `polisyos.ir.artifacts.transport.ArtifactDeltaEnvelope` |
| `emitted_at` | `datetime` | `yes` | `—` | — |
| `entries` | `list[polisyos.ir.artifacts.transport.ObservationStreamEntry]` | `no` | `—` | `polisyos.ir.artifacts.transport.ObservationStreamEntry` |
| `notes` | `list[str]` | `no` | `—` | — |
| `relink_manifest` | `polisyos.ir.artifacts.transport.IncrementalRelinkManifest | NoneType` | `no` | `—` | `polisyos.ir.artifacts.transport.IncrementalRelinkManifest` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `sequence_end` | `int` | `yes` | `—` | — |
| `sequence_start` | `int` | `yes` | `—` | — |
| `stream_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.artifacts.transport.StreamUpdateOperation` { #polisyos-ir-artifacts-transport-streamupdateoperation }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:StreamUpdateOperation`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Declare whether a streaming update inserts or retracts an observation.

| Enum values |
|-------------|
| `upsert` |
| `retract` |

### `polisyos.ir.artifacts.transport.TransportDescriptor` { #polisyos-ir-artifacts-transport-transportdescriptor }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.artifacts:TransportDescriptor`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.transport.BinaryWireFormat`, `polisyos.ir.artifacts.transport.TransportMode`
- Summary: Document the transport contract for one IR payload family.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `binary_media_type` | `str | NoneType` | `no` | `—` | — |
| `canonical_manifest_required` | `bool` | `no` | `True` | — |
| `family` | `str` | `yes` | `—` | — |
| `json_media_type` | `str` | `no` | `'application/json'` | — |
| `mode` | `polisyos.ir.artifacts.transport.TransportMode` | `yes` | `—` | `polisyos.ir.artifacts.transport.TransportMode` |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `wire_format` | `polisyos.ir.artifacts.transport.BinaryWireFormat | NoneType` | `no` | `—` | `polisyos.ir.artifacts.transport.BinaryWireFormat` |

### `polisyos.ir.artifacts.transport.TransportMode` { #polisyos-ir-artifacts-transport-transportmode }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.artifacts:TransportMode`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Classify whether a family is JSON-only or supports optional binary transport.

| Enum values |
|-------------|
| `json_first` |
| `optional_binary` |

## Governance

### `polisyos.ir.governance.game_design.BayesianTypeSpec` { #polisyos-ir-governance-game-design-bayesiantypespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:BayesianTypeSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Private-type support for one strategic participant.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `player_id` | `str` | `yes` | `—` | — |
| `prior_probabilities` | `dict[str, float]` | `no` | `—` | — |
| `type_space` | `tuple[str]` | `yes` | `—` | — |

### `polisyos.ir.governance.game_design.ExtensiveFormNode` { #polisyos-ir-governance-game-design-extensiveformnode }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:ExtensiveFormNode`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: One node in an extensive-form policy/mechanism game.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `actor_id` | `str | NoneType` | `no` | `—` | — |
| `available_actions` | `tuple[str]` | `no` | `()` | — |
| `chance_probabilities` | `dict[str, float] | NoneType` | `no` | `—` | — |
| `information_set_id` | `str | NoneType` | `no` | `—` | — |
| `node_id` | `str` | `yes` | `—` | — |
| `parent_node_id` | `str | NoneType` | `no` | `—` | — |
| `terminal_payoffs` | `dict[str, float] | NoneType` | `no` | `—` | — |

### `polisyos.ir.governance.game_design.MechanismConstraintType` { #polisyos-ir-governance-game-design-mechanismconstrainttype }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:MechanismConstraintType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Mechanism-design properties disclosed by the policy author.

| Enum values |
|-------------|
| `dominant_strategy_ic` |
| `bayesian_ic` |
| `ex_post_ir` |
| `ex_interim_ir` |
| `budget_balance` |
| `revenue_monotonicity` |

### `polisyos.ir.governance.game_design.MechanismDesignConstraint` { #polisyos-ir-governance-game-design-mechanismdesignconstraint }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:MechanismDesignConstraint`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.game_design.MechanismConstraintType`
- Summary: One incentive-compatibility or participation constraint.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `applies_to_players` | `tuple[str]` | `no` | `()` | — |
| `constraint_id` | `str` | `yes` | `—` | — |
| `constraint_type` | `polisyos.ir.governance.game_design.MechanismConstraintType` | `yes` | `—` | `polisyos.ir.governance.game_design.MechanismConstraintType` |
| `notes` | `tuple[str]` | `no` | `()` | — |
| `tolerance` | `float | NoneType` | `no` | `—` | — |

### `polisyos.ir.governance.game_design.MechanismDesignSpec` { #polisyos-ir-governance-game-design-mechanismdesignspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.governance:MechanismDesignSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.game_design.BayesianTypeSpec`, `polisyos.ir.governance.game_design.ExtensiveFormNode`, `polisyos.ir.governance.game_design.MechanismDesignConstraint`, `polisyos.ir.governance.game_design.MechanismGameRepresentation`, `polisyos.ir.governance.game_design.RepeatedGameMetadata`
- Summary: Richer strategic/mechanism-design metadata for a policy surface.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `action_spaces` | `dict[str, tuple[str]]` | `no` | `—` | — |
| `bayesian_types` | `list[polisyos.ir.governance.game_design.BayesianTypeSpec]` | `no` | `—` | `polisyos.ir.governance.game_design.BayesianTypeSpec` |
| `constraints` | `list[polisyos.ir.governance.game_design.MechanismDesignConstraint]` | `no` | `—` | `polisyos.ir.governance.game_design.MechanismDesignConstraint` |
| `design_id` | `str` | `yes` | `—` | — |
| `extensive_form_nodes` | `list[polisyos.ir.governance.game_design.ExtensiveFormNode]` | `no` | `—` | `polisyos.ir.governance.game_design.ExtensiveFormNode` |
| `mechanism_ids` | `tuple[str]` | `no` | `()` | — |
| `objective` | `str | NoneType` | `no` | `—` | — |
| `players` | `tuple[str]` | `yes` | `—` | — |
| `repeated_game` | `polisyos.ir.governance.game_design.RepeatedGameMetadata | NoneType` | `no` | `—` | `polisyos.ir.governance.game_design.RepeatedGameMetadata` |
| `representation` | `polisyos.ir.governance.game_design.MechanismGameRepresentation` | `yes` | `—` | `polisyos.ir.governance.game_design.MechanismGameRepresentation` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.governance.game_design.MechanismGameRepresentation` { #polisyos-ir-governance-game-design-mechanismgamerepresentation }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:MechanismGameRepresentation`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Supported mechanism/game representations for governance artifacts.

| Enum values |
|-------------|
| `normal_form` |
| `extensive_form` |
| `bayesian` |

### `polisyos.ir.governance.game_design.RepeatedGameHorizon` { #polisyos-ir-governance-game-design-repeatedgamehorizon }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:RepeatedGameHorizon`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Repeated-game horizon semantics.

| Enum values |
|-------------|
| `one_shot` |
| `finite` |
| `infinite` |

### `polisyos.ir.governance.game_design.RepeatedGameMetadata` { #polisyos-ir-governance-game-design-repeatedgamemetadata }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:RepeatedGameMetadata`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.game_design.RepeatedGameHorizon`
- Summary: Repeated-game metadata layered on top of one-shot mechanism design.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `discount_factor` | `float | NoneType` | `no` | `—` | — |
| `horizon` | `polisyos.ir.governance.game_design.RepeatedGameHorizon` | `no` | `<RepeatedGameHorizon.ONE_SHOT: 'one_shot'>` | `polisyos.ir.governance.game_design.RepeatedGameHorizon` |
| `n_rounds` | `int | NoneType` | `no` | `—` | — |
| `public_signal_fields` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.governance.gate.GateContext` { #polisyos-ir-governance-gate-gatecontext }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:GateContext`, `polisyos.ir:GateContext`
- ABI snapshot: `gate_context` / `schemas/snapshots/ir/gate_context.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Execution and risk context presented to a governance approver.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_refs` | `dict[str, str] | NoneType` | `no` | `—` | — |
| `governance_profile` | `str | NoneType` | `no` | `—` | — |
| `is_escalated` | `bool` | `no` | `False` | — |
| `issue_summary` | `dict[str, int] | NoneType` | `no` | `—` | — |
| `iteration` | `int` | `no` | `1` | — |
| `node_alias` | `str` | `yes` | `—` | — |
| `phase` | `str` | `yes` | `—` | — |
| `policy_summary` | `str | NoneType` | `no` | `—` | — |
| `replay_summary` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `risk_indicators` | `list[str]` | `no` | `—` | — |
| `simulation_results` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `transport_summary` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `workflow_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.governance.gate.GateDecision` { #polisyos-ir-governance-gate-gatedecision }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.governance:GateDecision`, `polisyos.ir:GateDecision`
- ABI snapshot: `gate_decision` / `schemas/snapshots/ir/gate_decision.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.gate.GateVerdict`
- Summary: Recorded gate verdict with approver identity and supporting evidence.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `approver_id` | `str` | `yes` | `—` | — |
| `comment` | `str | NoneType` | `no` | `—` | — |
| `decided_at` | `datetime` | `no` | `—` | — |
| `evidence_refs` | `list[str]` | `no` | `—` | — |
| `reason_codes` | `list[str]` | `no` | `—` | — |
| `request_id` | `str` | `yes` | `—` | — |
| `run_id` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `verdict` | `polisyos.ir.governance.gate.GateVerdict` | `yes` | `—` | `polisyos.ir.governance.gate.GateVerdict` |

### `polisyos.ir.governance.gate.GateEvent` { #polisyos-ir-governance-gate-gateevent }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.governance:GateEvent`, `polisyos.ir:GateEvent`
- ABI snapshot: `gate_event` / `schemas/snapshots/ir/gate_event.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.gate.GateEventType`
- Summary: Audit event emitted for gate lifecycle transitions.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `event_type` | `polisyos.ir.governance.gate.GateEventType` | `yes` | `—` | `polisyos.ir.governance.gate.GateEventType` |
| `payload` | `dict[str, Any]` | `no` | `—` | — |
| `request_id` | `str` | `yes` | `—` | — |
| `run_id` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `span_id` | `str | NoneType` | `no` | `—` | — |
| `timestamp` | `datetime` | `no` | `—` | — |
| `trace_id` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.governance.gate.GateEventType` { #polisyos-ir-governance-gate-gateeventtype }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:GateEventType`, `polisyos.ir:GateEventType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Audit-log event type emitted by the gate subsystem.

| Enum values |
|-------------|
| `GATE_REQUESTED` |
| `GATE_DECIDED` |
| `GATE_TIMEOUT` |
| `GATE_CANCELLED` |

### `polisyos.ir.governance.gate.GatePriority` { #polisyos-ir-governance-gate-gatepriority }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:GatePriority`, `polisyos.ir:GatePriority`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Scheduling priority assigned to a gate request.

| Enum values |
|-------------|
| `low` |
| `normal` |
| `high` |
| `critical` |

### `polisyos.ir.governance.gate.GateRequest` { #polisyos-ir-governance-gate-gaterequest }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.1`
- Exported from: `polisyos.ir.governance:GateRequest`, `polisyos.ir:GateRequest`
- ABI snapshot: `gate_request` / `schemas/snapshots/ir/gate_request.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.gate.GateContext`, `polisyos.ir.governance.gate.GatePriority`
- Summary: Approval request payload emitted when execution needs governance review.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `context` | `polisyos.ir.governance.gate.GateContext` | `yes` | `—` | `polisyos.ir.governance.gate.GateContext` |
| `priority` | `polisyos.ir.governance.gate.GatePriority` | `no` | `<GatePriority.NORMAL: 'normal'>` | `polisyos.ir.governance.gate.GatePriority` |
| `reason` | `str` | `yes` | `—` | — |
| `request_id` | `str` | `yes` | `—` | — |
| `requested_at` | `datetime` | `no` | `—` | — |
| `requested_by` | `str` | `no` | `'system'` | — |
| `run_id` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.1'` | — |
| `timeout_seconds` | `int | NoneType` | `no` | `—` | — |

### `polisyos.ir.governance.gate.GateVerdict` { #polisyos-ir-governance-gate-gateverdict }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:GateVerdict`, `polisyos.ir:GateVerdict`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Final outcome produced by a governance gate.

| Enum values |
|-------------|
| `approve` |
| `reject` |
| `escalate` |
| `timeout` |

### `polisyos.ir.governance.policy_composition.PolicyCompatibilityConstraint` { #polisyos-ir-governance-policy-composition-policycompatibilityconstraint }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:PolicyCompatibilityConstraint`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.policy_composition.PolicyCompatibilityMode`
- Summary: Compatibility requirement between a higher and lower policy layer.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `constraint_id` | `str` | `yes` | `—` | — |
| `higher_layer_id` | `str` | `yes` | `—` | — |
| `lower_layer_id` | `str` | `yes` | `—` | — |
| `mode` | `polisyos.ir.governance.policy_composition.PolicyCompatibilityMode` | `yes` | `—` | `polisyos.ir.governance.policy_composition.PolicyCompatibilityMode` |
| `notes` | `tuple[str]` | `no` | `()` | — |
| `required_policy_refs` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.governance.policy_composition.PolicyCompatibilityMode` { #polisyos-ir-governance-policy-composition-policycompatibilitymode }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:PolicyCompatibilityMode`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compatibility contract between stacked policy layers.

| Enum values |
|-------------|
| `strict_subset` |
| `extends` |
| `requires_approval` |
| `incompatible` |

### `polisyos.ir.governance.policy_composition.PolicyCompositionPlan` { #polisyos-ir-governance-policy-composition-policycompositionplan }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.governance:PolicyCompositionPlan`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.policy_composition.PolicyCompatibilityConstraint`, `polisyos.ir.governance.policy_composition.PolicyLayerSpec`, `polisyos.ir.governance.policy_composition.PolicyOverrideRule`, `polisyos.ir.governance.policy_composition.PolicyVersioningMode`
- Summary: Versioned multi-level policy composition plan.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `base_policy_id` | `str` | `yes` | `—` | — |
| `compatibility_constraints` | `list[polisyos.ir.governance.policy_composition.PolicyCompatibilityConstraint]` | `no` | `—` | `polisyos.ir.governance.policy_composition.PolicyCompatibilityConstraint` |
| `composition_id` | `str` | `yes` | `—` | — |
| `layers` | `list[polisyos.ir.governance.policy_composition.PolicyLayerSpec]` | `yes` | `—` | `polisyos.ir.governance.policy_composition.PolicyLayerSpec` |
| `override_rules` | `list[polisyos.ir.governance.policy_composition.PolicyOverrideRule]` | `no` | `—` | `polisyos.ir.governance.policy_composition.PolicyOverrideRule` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `versioning_mode` | `polisyos.ir.governance.policy_composition.PolicyVersioningMode` | `no` | `<PolicyVersioningMode.EXPLICIT_NEGOTIATION: 'explicit_negotiation'>` | `polisyos.ir.governance.policy_composition.PolicyVersioningMode` |

### `polisyos.ir.governance.policy_composition.PolicyLayerLevel` { #polisyos-ir-governance-policy-composition-policylayerlevel }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:PolicyLayerLevel`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Supported override layers in a composed policy stack.

| Enum values |
|-------------|
| `federal` |
| `state` |
| `local` |
| `organizational` |

### `polisyos.ir.governance.policy_composition.PolicyLayerSpec` { #polisyos-ir-governance-policy-composition-policylayerspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:PolicyLayerSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.policy_composition.PolicyLayerLevel`
- Summary: One policy layer participating in a multi-jurisdiction composition.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `effective_from` | `str | NoneType` | `no` | `—` | — |
| `effective_to` | `str | NoneType` | `no` | `—` | — |
| `jurisdiction_id` | `str` | `yes` | `—` | — |
| `layer_id` | `str` | `yes` | `—` | — |
| `level` | `polisyos.ir.governance.policy_composition.PolicyLayerLevel` | `yes` | `—` | `polisyos.ir.governance.policy_composition.PolicyLayerLevel` |
| `policy_id` | `str` | `yes` | `—` | — |
| `precedence` | `int` | `yes` | `—` | — |
| `version_tag` | `str` | `yes` | `—` | — |

### `polisyos.ir.governance.policy_composition.PolicyOverrideMode` { #polisyos-ir-governance-policy-composition-policyoverridemode }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:PolicyOverrideMode`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: How a lower layer interacts with an inherited policy surface.

| Enum values |
|-------------|
| `inherit` |
| `append` |
| `replace` |
| `disable` |

### `polisyos.ir.governance.policy_composition.PolicyOverrideRule` { #polisyos-ir-governance-policy-composition-policyoverriderule }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:PolicyOverrideRule`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.policy_composition.PolicyOverrideMode`
- Summary: Override applied by one policy layer to another.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `justification` | `str` | `yes` | `—` | — |
| `mode` | `polisyos.ir.governance.policy_composition.PolicyOverrideMode` | `yes` | `—` | `polisyos.ir.governance.policy_composition.PolicyOverrideMode` |
| `override_id` | `str` | `yes` | `—` | — |
| `source_layer_id` | `str` | `yes` | `—` | — |
| `target_constraint_id` | `str | NoneType` | `no` | `—` | — |
| `target_intervention_id` | `str | NoneType` | `no` | `—` | — |
| `target_layer_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.governance.policy_composition.PolicyVersioningMode` { #polisyos-ir-governance-policy-composition-policyversioningmode }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:PolicyVersioningMode`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: How versions are negotiated across composed layers.

| Enum values |
|-------------|
| `lockstep` |
| `independent` |
| `explicit_negotiation` |

### `polisyos.ir.governance.policy_spec.InterventionSpec` { #polisyos-ir-governance-policy-spec-interventionspec }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:InterventionSpec`, `polisyos.ir:PolicyInterventionSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.schedule.ScheduleSpec`, `polisyos.ir.governance.selector_expr.SelectorAggregate`, `polisyos.ir.governance.selector_expr.SelectorAll`, `polisyos.ir.governance.selector_expr.SelectorAny`, `polisyos.ir.governance.selector_expr.SelectorNot`, `polisyos.ir.governance.selector_expr.SelectorPredicate`, `polisyos.ir.governance.selector_expr.SelectorQuantifier`, `polisyos.ir.governance.selector_expr.SelectorTemporalPredicate`, `polisyos.ir.observation.contracts.IdentificationMode`, `polisyos.ir.observation.contracts.StrategicResponseChannel`
- Summary: Declare one policy action, its target selector, timing, and mechanism inputs.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `enabled` | `bool` | `no` | `True` | — |
| `identification_mode` | `polisyos.ir.observation.contracts.IdentificationMode | NoneType` | `no` | `—` | `polisyos.ir.observation.contracts.IdentificationMode` |
| `intervention_id` | `str` | `yes` | `—` | — |
| `kind` | `str` | `yes` | `—` | — |
| `lex_provision_ref` | `str | NoneType` | `no` | `—` | — |
| `measurement_expectations` | `dict[str, Any]` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `params` | `dict[str, Any]` | `no` | `—` | — |
| `priority` | `int | NoneType` | `no` | `—` | — |
| `schedule` | `polisyos.ir.governance.schedule.ScheduleSpec` | `yes` | `—` | `polisyos.ir.governance.schedule.ScheduleSpec` |
| `strategic_response_expected` | `bool` | `no` | `False` | — |
| `target` | `polisyos.ir.governance.selector_expr.SelectorPredicate | polisyos.ir.governance.selector_expr.SelectorAll | polisyos.ir.governance.selector_expr.SelectorAny | polisyos.ir.governance.selector_expr.SelectorNot | polisyos.ir.governance.selector_expr.SelectorQuantifier | polisyos.ir.governance.selector_expr.SelectorAggregate | polisyos.ir.governance.selector_expr.SelectorTemporalPredicate` | `yes` | `—` | `polisyos.ir.governance.selector_expr.SelectorAggregate`, `polisyos.ir.governance.selector_expr.SelectorAll`, `polisyos.ir.governance.selector_expr.SelectorAny`, `polisyos.ir.governance.selector_expr.SelectorNot`, `polisyos.ir.governance.selector_expr.SelectorPredicate`, `polisyos.ir.governance.selector_expr.SelectorQuantifier`, `polisyos.ir.governance.selector_expr.SelectorTemporalPredicate` |
| `target_population_type` | `str | NoneType` | `no` | `—` | — |
| `target_region_ids` | `list[str]` | `no` | `—` | — |
| `target_sector_ids` | `list[str]` | `no` | `—` | — |
| `transmission_channels` | `list[polisyos.ir.observation.contracts.StrategicResponseChannel]` | `no` | `—` | `polisyos.ir.observation.contracts.StrategicResponseChannel` |

### `polisyos.ir.governance.policy_spec.MechanismBinding` { #polisyos-ir-governance-policy-spec-mechanismbinding }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:MechanismBinding`, `polisyos.ir:MechanismBinding`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Bind one or more interventions to an executable mechanism registry entry.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `binding_id` | `str` | `yes` | `—` | — |
| `config_overrides` | `dict[str, Any]` | `no` | `—` | — |
| `intervention_ids` | `list[str]` | `yes` | `—` | — |
| `mechanism_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.governance.policy_spec.ParameterSpec` { #polisyos-ir-governance-policy-spec-parameterspec }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:ParameterSpec`, `polisyos.ir:ParameterSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Expose one tunable intervention parameter to calibration and search.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `default_value` | `Any` | `yes` | `—` | — |
| `intervention_id` | `str` | `yes` | `—` | — |
| `max_value` | `Any | NoneType` | `no` | `—` | — |
| `min_value` | `Any | NoneType` | `no` | `—` | — |
| `param_id` | `str` | `yes` | `—` | — |
| `param_path` | `str` | `yes` | `—` | — |
| `sensitivity_priority` | `int` | `no` | `5` | — |
| `tunable` | `bool` | `no` | `True` | — |

### `polisyos.ir.governance.policy_spec.PolicySpec` { #polisyos-ir-governance-policy-spec-policyspec }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.governance:PolicySpec`, `polisyos.ir.trinity:PolicySpec`, `polisyos.ir:PolicySpec`
- ABI snapshot: `policy_spec` / `schemas/snapshots/ir/policy_spec.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.game_design.MechanismDesignSpec`, `polisyos.ir.governance.policy_composition.PolicyCompositionPlan`, `polisyos.ir.governance.policy_spec.InterventionSpec`, `polisyos.ir.governance.policy_spec.MechanismBinding`, `polisyos.ir.governance.policy_spec.ParameterSpec`, `polisyos.ir.governance.schedule.ScheduleSpec`, `polisyos.ir.governance.temporal_logic.TemporalPolicyConstraint`, `polisyos.ir.types.TranslatableString`
- Summary: Define the Trinity intervention/governance contract for policy proposals.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `composition` | `polisyos.ir.governance.policy_composition.PolicyCompositionPlan | NoneType` | `no` | `—` | `polisyos.ir.governance.policy_composition.PolicyCompositionPlan` |
| `description` | `str | NoneType` | `no` | `—` | — |
| `global_schedule` | `polisyos.ir.governance.schedule.ScheduleSpec | NoneType` | `no` | `—` | `polisyos.ir.governance.schedule.ScheduleSpec` |
| `interventions` | `list[polisyos.ir.governance.policy_spec.InterventionSpec]` | `no` | `—` | `polisyos.ir.governance.policy_spec.InterventionSpec` |
| `labels` | `list[str]` | `no` | `—` | — |
| `mechanism_bindings` | `list[polisyos.ir.governance.policy_spec.MechanismBinding]` | `no` | `—` | `polisyos.ir.governance.policy_spec.MechanismBinding` |
| `mechanism_design` | `polisyos.ir.governance.game_design.MechanismDesignSpec | NoneType` | `no` | `—` | `polisyos.ir.governance.game_design.MechanismDesignSpec` |
| `name` | `polisyos.ir.types.TranslatableString | NoneType` | `no` | `—` | `polisyos.ir.types.TranslatableString` |
| `notes` | `list[str]` | `no` | `—` | — |
| `parameters` | `list[polisyos.ir.governance.policy_spec.ParameterSpec]` | `no` | `—` | `polisyos.ir.governance.policy_spec.ParameterSpec` |
| `policy_id` | `str` | `yes` | `—` | — |
| `problem_frame_ref` | `str | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `temporal_constraints` | `list[polisyos.ir.governance.temporal_logic.TemporalPolicyConstraint]` | `no` | `—` | `polisyos.ir.governance.temporal_logic.TemporalPolicyConstraint` |
| `version_tag` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.governance.policy_spec.TemporalInterventionSequence` { #polisyos-ir-governance-policy-spec-temporalinterventionsequence }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.governance:TemporalInterventionSequence`, `polisyos.ir:TemporalInterventionSequence`
- ABI snapshot: `temporal_intervention_sequence` / `schemas/snapshots/ir/temporal_intervention_sequence.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.policy_spec.TemporalInterventionStep`, `polisyos.ir.observation.contracts.IdentificationMode`, `polisyos.ir.observation.contracts.StrategicResponseChannel`
- Summary: Group ordered intervention steps for sequential or DTR-style execution.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `dynamic_intervention_id` | `str` | `yes` | `—` | — |
| `identification_mode` | `polisyos.ir.observation.contracts.IdentificationMode` | `no` | `<IdentificationMode.SEQUENTIAL: 'sequential'>` | `polisyos.ir.observation.contracts.IdentificationMode` |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `sequence_id` | `str` | `yes` | `—` | — |
| `steps` | `list[polisyos.ir.governance.policy_spec.TemporalInterventionStep]` | `yes` | `—` | `polisyos.ir.governance.policy_spec.TemporalInterventionStep` |
| `strategic_response_expected` | `bool` | `no` | `False` | — |
| `transmission_channels` | `list[polisyos.ir.observation.contracts.StrategicResponseChannel]` | `no` | `—` | `polisyos.ir.observation.contracts.StrategicResponseChannel` |

### `polisyos.ir.governance.policy_spec.TemporalInterventionStep` { #polisyos-ir-governance-policy-spec-temporalinterventionstep }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalInterventionStep`, `polisyos.ir:TemporalInterventionStep`
- ABI snapshot: `temporal_intervention_step` / `schemas/snapshots/ir/temporal_intervention_step.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Declare one activation point in a sequential intervention program.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `effective_date` | `str` | `yes` | `—` | — |
| `intervention_id` | `str` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `parameter_overrides` | `dict[str, Any]` | `no` | `—` | — |
| `step_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.governance.problem_frame.ConstraintSpec` { #polisyos-ir-governance-problem-frame-constraintspec }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:ConstraintSpec`, `polisyos.ir:ProblemConstraintSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.problem_frame.ConstraintType`, `polisyos.ir.kernel.values.CountValue`, `polisyos.ir.kernel.values.DurationValue`, `polisyos.ir.kernel.values.MoneyValue`, `polisyos.ir.kernel.values.RateValue`
- Summary: Specify one feasibility boundary or soft penalty attached to a metric slot.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `constraint_id` | `str` | `yes` | `—` | — |
| `constraint_type` | `polisyos.ir.governance.problem_frame.ConstraintType` | `no` | `<ConstraintType.HARD: 'hard'>` | `polisyos.ir.governance.problem_frame.ConstraintType` |
| `notes` | `list[str]` | `no` | `—` | — |
| `operator` | `Literal[<, <=, ==, !=, >=, >] | NoneType` | `no` | `—` | — |
| `penalty_weight` | `Decimal | NoneType` | `no` | `—` | — |
| `slot_id` | `str | NoneType` | `no` | `—` | — |
| `value` | `polisyos.ir.kernel.values.MoneyValue | polisyos.ir.kernel.values.RateValue | polisyos.ir.kernel.values.CountValue | polisyos.ir.kernel.values.DurationValue | Decimal | int | str | bool` | `yes` | `—` | `polisyos.ir.kernel.values.CountValue`, `polisyos.ir.kernel.values.DurationValue`, `polisyos.ir.kernel.values.MoneyValue`, `polisyos.ir.kernel.values.RateValue` |

### `polisyos.ir.governance.problem_frame.ConstraintType` { #polisyos-ir-governance-problem-frame-constrainttype }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:ConstraintType`, `polisyos.ir:ConstraintType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Declare whether a constraint is a hard feasibility gate or a soft penalty.

| Enum values |
|-------------|
| `hard` |
| `soft` |

### `polisyos.ir.governance.problem_frame.KPISpec` { #polisyos-ir-governance-problem-frame-kpispec }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:KPISpec`, `polisyos.ir:KPISpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.types.OptimizationDirection`, `polisyos.ir.types.TranslatableString`
- Summary: Describe one measurable success signal anchored to the metric registry.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `baseline_value` | `Decimal | NoneType` | `no` | `—` | — |
| `direction` | `polisyos.ir.types.OptimizationDirection` | `yes` | `—` | `polisyos.ir.types.OptimizationDirection` |
| `kpi_id` | `str` | `yes` | `—` | — |
| `metric_id` | `str` | `yes` | `—` | — |
| `name` | `polisyos.ir.types.TranslatableString | NoneType` | `no` | `—` | `polisyos.ir.types.TranslatableString` |
| `notes` | `list[str]` | `no` | `—` | — |
| `target_value` | `Decimal | NoneType` | `no` | `—` | — |
| `unit_id` | `str | NoneType` | `no` | `—` | — |
| `weight` | `Decimal` | `no` | `Decimal('1')` | — |

### `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy` { #polisyos-ir-governance-problem-frame-normativearbitrationpolicy }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:NormativeArbitrationPolicy`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Supported formal arbitration policies.

| Enum values |
|-------------|
| `lexicographic_rights` |
| `weighted_welfare` |
| `max_min_harm` |
| `pareto_filter` |

### `polisyos.ir.governance.problem_frame.NormativeComparisonMode` { #polisyos-ir-governance-problem-frame-normativecomparisonmode }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:NormativeComparisonMode`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Supported comparison modes for arbitration.

| Enum values |
|-------------|
| `proposal_vs_baseline` |

### `polisyos.ir.governance.problem_frame.NormativeComparisonTarget` { #polisyos-ir-governance-problem-frame-normativecomparisontarget }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:NormativeComparisonTarget`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Which quantity a right condition evaluates.

| Enum values |
|-------------|
| `proposal` |
| `baseline` |
| `delta` |

### `polisyos.ir.governance.problem_frame.NormativeFrame` { #polisyos-ir-governance-problem-frame-normativeframe }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:NormativeFrame`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy`, `polisyos.ir.governance.problem_frame.NormativeComparisonMode`, `polisyos.ir.governance.problem_frame.StakeholderOutcomeBinding`, `polisyos.ir.governance.problem_frame.StakeholderRightSpec`, `polisyos.ir.governance.problem_frame.StakeholderUtilityTerm`
- Summary: Formal value-conflict model used by normative arbitration.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `comparison_mode` | `polisyos.ir.governance.problem_frame.NormativeComparisonMode` | `no` | `<NormativeComparisonMode.PROPOSAL_VS_BASELINE: 'proposal_vs_baseline'>` | `polisyos.ir.governance.problem_frame.NormativeComparisonMode` |
| `default_policy` | `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy` | `no` | `<NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS: 'lexicographic_rights'>` | `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy` |
| `enabled_policies` | `list[polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy]` | `no` | `—` | `polisyos.ir.governance.problem_frame.NormativeArbitrationPolicy` |
| `hard_constraint_refs` | `list[str]` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `rights_catalog` | `list[polisyos.ir.governance.problem_frame.StakeholderRightSpec]` | `no` | `—` | `polisyos.ir.governance.problem_frame.StakeholderRightSpec` |
| `stakeholder_bindings` | `list[polisyos.ir.governance.problem_frame.StakeholderOutcomeBinding]` | `no` | `—` | `polisyos.ir.governance.problem_frame.StakeholderOutcomeBinding` |
| `utility_terms` | `list[polisyos.ir.governance.problem_frame.StakeholderUtilityTerm]` | `no` | `—` | `polisyos.ir.governance.problem_frame.StakeholderUtilityTerm` |

### `polisyos.ir.governance.problem_frame.NormativeOutcomeChannel` { #polisyos-ir-governance-problem-frame-normativeoutcomechannel }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:NormativeOutcomeChannel`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Canonical channels that can feed normative utilities/rights.

| Enum values |
|-------------|
| `simulation_metric` |
| `distributional_net_impact` |
| `distributional_losers_share` |
| `distributional_winners_share` |
| `distributional_overall_gini_delta` |
| `uncertainty_ci_width_ratio` |
| `synthesized` |

### `polisyos.ir.governance.problem_frame.ObjectiveSpec` { #polisyos-ir-governance-problem-frame-objectivespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:ObjectiveSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.types.OptimizationDirection`
- Summary: Formal objective specification linking to metrics.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `direction` | `polisyos.ir.types.OptimizationDirection` | `yes` | `—` | `polisyos.ir.types.OptimizationDirection` |
| `kpi_refs` | `list[str]` | `no` | `—` | — |
| `metric_id` | `str` | `yes` | `—` | — |
| `objective_id` | `str` | `yes` | `—` | — |
| `target` | `Decimal | NoneType` | `no` | `—` | — |
| `weight` | `Decimal` | `no` | `Decimal('1')` | — |

### `polisyos.ir.governance.problem_frame.ProblemDomain` { #polisyos-ir-governance-problem-frame-problemdomain }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:ProblemDomain`, `polisyos.ir:ProblemDomain`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Classify the domain vocabulary used to route metrics and templates.

| Enum values |
|-------------|
| `fiscal` |
| `monetary` |
| `social` |
| `environmental` |
| `labor` |
| `healthcare` |
| `education` |
| `infrastructure` |
| `regulatory` |
| `trade` |
| `custom` |

### `polisyos.ir.governance.problem_frame.ProblemFrame` { #polisyos-ir-governance-problem-frame-problemframe }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.governance:ProblemFrame`, `polisyos.ir.trinity:ProblemFrame`, `polisyos.ir:ProblemFrame`
- ABI snapshot: `problem_frame` / `schemas/snapshots/ir/problem_frame.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.problem_frame.ConstraintSpec`, `polisyos.ir.governance.problem_frame.KPISpec`, `polisyos.ir.governance.problem_frame.NormativeFrame`, `polisyos.ir.governance.problem_frame.ObjectiveSpec`, `polisyos.ir.governance.problem_frame.ProblemDomain`, `polisyos.ir.governance.problem_frame.StakeholderSpec`, `polisyos.ir.governance.problem_frame.SuccessCriterion`
- Summary: Define the Trinity ``what`` contract for objectives, metrics, and guardrails.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `domain` | `polisyos.ir.governance.problem_frame.ProblemDomain` | `yes` | `—` | `polisyos.ir.governance.problem_frame.ProblemDomain` |
| `hard_constraints` | `list[polisyos.ir.governance.problem_frame.ConstraintSpec]` | `no` | `—` | `polisyos.ir.governance.problem_frame.ConstraintSpec` |
| `kpis` | `list[polisyos.ir.governance.problem_frame.KPISpec]` | `no` | `—` | `polisyos.ir.governance.problem_frame.KPISpec` |
| `labels` | `list[str]` | `no` | `—` | — |
| `narrative` | `str | NoneType` | `no` | `—` | — |
| `normative_frame` | `polisyos.ir.governance.problem_frame.NormativeFrame | NoneType` | `no` | `—` | `polisyos.ir.governance.problem_frame.NormativeFrame` |
| `notes` | `list[str]` | `no` | `—` | — |
| `objectives` | `list[polisyos.ir.governance.problem_frame.ObjectiveSpec]` | `no` | `—` | `polisyos.ir.governance.problem_frame.ObjectiveSpec` |
| `problem_id` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `soft_constraints` | `list[polisyos.ir.governance.problem_frame.ConstraintSpec]` | `no` | `—` | `polisyos.ir.governance.problem_frame.ConstraintSpec` |
| `stakeholders` | `list[polisyos.ir.governance.problem_frame.StakeholderSpec]` | `no` | `—` | `polisyos.ir.governance.problem_frame.StakeholderSpec` |
| `success_criteria` | `list[polisyos.ir.governance.problem_frame.SuccessCriterion]` | `no` | `—` | `polisyos.ir.governance.problem_frame.SuccessCriterion` |

### `polisyos.ir.governance.problem_frame.StakeholderOutcomeBinding` { #polisyos-ir-governance-problem-frame-stakeholderoutcomebinding }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:StakeholderOutcomeBinding`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.problem_frame.NormativeOutcomeChannel`
- Summary: Map a stakeholder to a concrete outcome channel and key.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `binding_id` | `str` | `yes` | `—` | — |
| `channel` | `polisyos.ir.governance.problem_frame.NormativeOutcomeChannel` | `yes` | `—` | `polisyos.ir.governance.problem_frame.NormativeOutcomeChannel` |
| `notes` | `list[str]` | `no` | `—` | — |
| `outcome_key` | `str` | `yes` | `—` | — |
| `stakeholder_id` | `str` | `yes` | `—` | — |
| `weight` | `Decimal` | `no` | `Decimal('1')` | — |

### `polisyos.ir.governance.problem_frame.StakeholderRightSpec` { #polisyos-ir-governance-problem-frame-stakeholderrightspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:StakeholderRightSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.problem_frame.NormativeComparisonTarget`
- Summary: Explicit normative right attached to a stakeholder.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `binding_ref` | `str | NoneType` | `no` | `—` | — |
| `compare_to` | `polisyos.ir.governance.problem_frame.NormativeComparisonTarget` | `no` | `<NormativeComparisonTarget.DELTA: 'delta'>` | `polisyos.ir.governance.problem_frame.NormativeComparisonTarget` |
| `hard` | `bool` | `no` | `True` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `operator` | `Literal[<, <=, ==, !=, >=, >]` | `yes` | `—` | — |
| `right_id` | `str` | `yes` | `—` | — |
| `stakeholder_id` | `str` | `yes` | `—` | — |
| `threshold` | `Decimal | int | str | bool` | `yes` | `—` | — |

### `polisyos.ir.governance.problem_frame.StakeholderSpec` { #polisyos-ir-governance-problem-frame-stakeholderspec }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:StakeholderSpec`, `polisyos.ir:StakeholderSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.types.EntityType`, `polisyos.ir.types.TranslatableString`
- Summary: Capture the affected actor set used by equity and arbitration passes.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `attributes` | `dict[str, str | int | bool]` | `no` | `—` | — |
| `entity_type` | `polisyos.ir.types.EntityType` | `yes` | `—` | `polisyos.ir.types.EntityType` |
| `impact_direction` | `Literal[positive, negative, mixed, neutral] | NoneType` | `no` | `—` | — |
| `name` | `polisyos.ir.types.TranslatableString | NoneType` | `no` | `—` | `polisyos.ir.types.TranslatableString` |
| `priority` | `int` | `no` | `5` | — |
| `role` | `str | NoneType` | `no` | `—` | — |
| `stakeholder_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.governance.problem_frame.StakeholderUtilityTerm` { #polisyos-ir-governance-problem-frame-stakeholderutilityterm }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:StakeholderUtilityTerm`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.problem_frame.UtilityDirection`
- Summary: Explicit utility term for stakeholder welfare aggregation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `binding_refs` | `list[str]` | `no` | `—` | — |
| `coefficient` | `Decimal` | `no` | `Decimal('1')` | — |
| `direction` | `polisyos.ir.governance.problem_frame.UtilityDirection` | `no` | `<UtilityDirection.MAXIMIZE: 'maximize'>` | `polisyos.ir.governance.problem_frame.UtilityDirection` |
| `notes` | `list[str]` | `no` | `—` | — |
| `stakeholder_id` | `str` | `yes` | `—` | — |
| `term_id` | `str` | `yes` | `—` | — |
| `welfare_weight` | `Decimal` | `no` | `Decimal('1')` | — |

### `polisyos.ir.governance.problem_frame.SuccessCriterion` { #polisyos-ir-governance-problem-frame-successcriterion }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:SuccessCriterion`, `polisyos.ir:SuccessCriterion`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.values.CountValue`, `polisyos.ir.kernel.values.MoneyValue`, `polisyos.ir.kernel.values.RateValue`
- Summary: Formal success criterion with threshold and operator.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `confidence_level` | `Decimal | NoneType` | `no` | `—` | — |
| `criterion_id` | `str` | `yes` | `—` | — |
| `kpi_id` | `str` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `operator` | `Literal[<, <=, ==, !=, >=, >]` | `yes` | `—` | — |
| `threshold` | `Decimal | polisyos.ir.kernel.values.MoneyValue | polisyos.ir.kernel.values.RateValue | polisyos.ir.kernel.values.CountValue` | `yes` | `—` | `polisyos.ir.kernel.values.CountValue`, `polisyos.ir.kernel.values.MoneyValue`, `polisyos.ir.kernel.values.RateValue` |

### `polisyos.ir.governance.problem_frame.UtilityDirection` { #polisyos-ir-governance-problem-frame-utilitydirection }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:UtilityDirection`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Utility aggregation direction for a stakeholder term.

| Enum values |
|-------------|
| `maximize` |
| `minimize` |

### `polisyos.ir.governance.schedule.ScheduleSpec` { #polisyos-ir-governance-schedule-schedulespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:ScheduleSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Describe when an intervention or task is active in step-indexed Trinity schedules.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `duration_steps` | `int | NoneType` | `no` | `—` | — |
| `end_step` | `int | NoneType` | `no` | `—` | — |
| `start_step` | `int` | `yes` | `—` | — |

### `polisyos.ir.governance.selector_expr.SelectorAggregate` { #polisyos-ir-governance-selector-expr-selectoraggregate }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:SelectorAggregate`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.selector_expr.SelectorAggregationFunction`, `polisyos.ir.types.SelectorOperator`
- Summary: Aggregate selector predicate over a collection.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `aggregation` | `polisyos.ir.governance.selector_expr.SelectorAggregationFunction` | `yes` | `—` | `polisyos.ir.governance.selector_expr.SelectorAggregationFunction` |
| `collection_field` | `str` | `yes` | `—` | — |
| `kind` | `Literal[aggregate]` | `no` | `'aggregate'` | — |
| `operator` | `polisyos.ir.types.SelectorOperator` | `yes` | `—` | `polisyos.ir.types.SelectorOperator` |
| `value` | `str | int | bool | Decimal` | `yes` | `—` | — |
| `value_field` | `str | NoneType` | `no` | `—` | — |
| `where` | `SelectorExpr | None` | `no` | `—` | — |

### `polisyos.ir.governance.selector_expr.SelectorAggregationFunction` { #polisyos-ir-governance-selector-expr-selectoraggregationfunction }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:SelectorAggregationFunction`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Aggregate functions supported inside selector predicates.

| Enum values |
|-------------|
| `count` |
| `sum` |
| `avg` |
| `min` |
| `max` |

### `polisyos.ir.governance.selector_expr.SelectorAll` { #polisyos-ir-governance-selector-expr-selectorall }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:SelectorAll`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Selector all public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `clauses` | `list['SelectorExpr']` | `yes` | `—` | — |
| `kind` | `Literal[all_of]` | `no` | `'all_of'` | — |

### `polisyos.ir.governance.selector_expr.SelectorAny` { #polisyos-ir-governance-selector-expr-selectorany }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:SelectorAny`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Selector any public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `clauses` | `list['SelectorExpr']` | `yes` | `—` | — |
| `kind` | `Literal[any_of]` | `no` | `'any_of'` | — |

### `polisyos.ir.governance.selector_expr.SelectorNot` { #polisyos-ir-governance-selector-expr-selectornot }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:SelectorNot`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Selector not public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `clause` | `'SelectorExpr'` | `yes` | `—` | — |
| `kind` | `Literal[not]` | `no` | `'not'` | — |

### `polisyos.ir.governance.selector_expr.SelectorPredicate` { #polisyos-ir-governance-selector-expr-selectorpredicate }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:SelectorPredicate`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.types.SelectorOperator`
- Summary: Selector predicate public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `field` | `str` | `yes` | `—` | — |
| `kind` | `Literal[predicate]` | `no` | `'predicate'` | — |
| `operator` | `polisyos.ir.types.SelectorOperator` | `yes` | `—` | `polisyos.ir.types.SelectorOperator` |
| `value` | `str | int | bool | Decimal | list[str | int | bool | Decimal]` | `yes` | `—` | — |

### `polisyos.ir.governance.selector_expr.SelectorQuantifier` { #polisyos-ir-governance-selector-expr-selectorquantifier }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:SelectorQuantifier`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.selector_expr.SelectorQuantifierKind`
- Summary: Quantified selector over a repeated/collection field.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `clause` | `'SelectorExpr'` | `yes` | `—` | — |
| `collection_field` | `str` | `yes` | `—` | — |
| `kind` | `Literal[quantifier]` | `no` | `'quantifier'` | — |
| `quantifier` | `polisyos.ir.governance.selector_expr.SelectorQuantifierKind` | `yes` | `—` | `polisyos.ir.governance.selector_expr.SelectorQuantifierKind` |
| `threshold` | `int | NoneType` | `no` | `—` | — |

### `polisyos.ir.governance.selector_expr.SelectorQuantifierKind` { #polisyos-ir-governance-selector-expr-selectorquantifierkind }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:SelectorQuantifierKind`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Quantified collection selectors.

| Enum values |
|-------------|
| `exists` |
| `for_all` |
| `at_least` |
| `at_most` |
| `exactly` |

### `polisyos.ir.governance.selector_expr.SelectorTemporalOperator` { #polisyos-ir-governance-selector-expr-selectortemporaloperator }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:SelectorTemporalOperator`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Temporal wrappers for selector predicates.

| Enum values |
|-------------|
| `ever` |
| `always_within` |
| `eventually_within` |
| `historically_within` |

### `polisyos.ir.governance.selector_expr.SelectorTemporalPredicate` { #polisyos-ir-governance-selector-expr-selectortemporalpredicate }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:SelectorTemporalPredicate`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.selector_expr.SelectorTemporalOperator`
- Summary: Temporal wrapper around a selector clause.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `clause` | `'SelectorExpr'` | `yes` | `—` | — |
| `clock_field` | `str | NoneType` | `no` | `—` | — |
| `kind` | `Literal[temporal]` | `no` | `'temporal'` | — |
| `lower_bound` | `int` | `no` | `0` | — |
| `temporal_operator` | `polisyos.ir.governance.selector_expr.SelectorTemporalOperator` | `yes` | `—` | `polisyos.ir.governance.selector_expr.SelectorTemporalOperator` |
| `upper_bound` | `int | NoneType` | `no` | `—` | — |

### `polisyos.ir.governance.temporal_logic.TemporalAll` { #polisyos-ir-governance-temporal-logic-temporalall }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalAll`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Conjunction over temporal clauses.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `clauses` | `list['TemporalLogicExpr']` | `yes` | `—` | — |
| `kind` | `Literal[all_of]` | `no` | `'all_of'` | — |

### `polisyos.ir.governance.temporal_logic.TemporalAny` { #polisyos-ir-governance-temporal-logic-temporalany }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalAny`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Disjunction over temporal clauses.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `clauses` | `list['TemporalLogicExpr']` | `yes` | `—` | — |
| `kind` | `Literal[any_of]` | `no` | `'any_of'` | — |

### `polisyos.ir.governance.temporal_logic.TemporalAtom` { #polisyos-ir-governance-temporal-logic-temporalatom }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalAtom`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.selector_expr.SelectorAggregate`, `polisyos.ir.governance.selector_expr.SelectorAll`, `polisyos.ir.governance.selector_expr.SelectorAny`, `polisyos.ir.governance.selector_expr.SelectorNot`, `polisyos.ir.governance.selector_expr.SelectorPredicate`, `polisyos.ir.governance.selector_expr.SelectorQuantifier`, `polisyos.ir.governance.selector_expr.SelectorTemporalPredicate`, `polisyos.ir.types.SelectorOperator`
- Summary: Atomic temporal proposition backed by selector or metric comparison.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `description` | `str | NoneType` | `no` | `—` | — |
| `kind` | `Literal[atom]` | `no` | `'atom'` | — |
| `metric_path` | `str | NoneType` | `no` | `—` | — |
| `operator` | `polisyos.ir.types.SelectorOperator | NoneType` | `no` | `—` | `polisyos.ir.types.SelectorOperator` |
| `proposition_id` | `str | NoneType` | `no` | `—` | — |
| `selector` | `polisyos.ir.governance.selector_expr.SelectorPredicate | polisyos.ir.governance.selector_expr.SelectorAll | polisyos.ir.governance.selector_expr.SelectorAny | polisyos.ir.governance.selector_expr.SelectorNot | polisyos.ir.governance.selector_expr.SelectorQuantifier | polisyos.ir.governance.selector_expr.SelectorAggregate | polisyos.ir.governance.selector_expr.SelectorTemporalPredicate | NoneType` | `no` | `—` | `polisyos.ir.governance.selector_expr.SelectorAggregate`, `polisyos.ir.governance.selector_expr.SelectorAll`, `polisyos.ir.governance.selector_expr.SelectorAny`, `polisyos.ir.governance.selector_expr.SelectorNot`, `polisyos.ir.governance.selector_expr.SelectorPredicate`, `polisyos.ir.governance.selector_expr.SelectorQuantifier`, `polisyos.ir.governance.selector_expr.SelectorTemporalPredicate` |
| `value` | `str | int | bool | Decimal | list[str | int | bool | Decimal] | NoneType` | `no` | `—` | — |

### `polisyos.ir.governance.temporal_logic.TemporalBinaryFormula` { #polisyos-ir-governance-temporal-logic-temporalbinaryformula }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalBinaryFormula`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.temporal_logic.TemporalBinaryOperator`
- Summary: Binary temporal operator application.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[binary]` | `no` | `'binary'` | — |
| `left` | `'TemporalLogicExpr'` | `yes` | `—` | — |
| `operator` | `polisyos.ir.governance.temporal_logic.TemporalBinaryOperator` | `yes` | `—` | `polisyos.ir.governance.temporal_logic.TemporalBinaryOperator` |
| `right` | `'TemporalLogicExpr'` | `yes` | `—` | — |

### `polisyos.ir.governance.temporal_logic.TemporalBinaryOperator` { #polisyos-ir-governance-temporal-logic-temporalbinaryoperator }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalBinaryOperator`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Binary operators used across temporal-logic subsets.

| Enum values |
|-------------|
| `implies` |
| `until` |
| `release` |

### `polisyos.ir.governance.temporal_logic.TemporalBoundedFormula` { #polisyos-ir-governance-temporal-logic-temporalboundedformula }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalBoundedFormula`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: MTL bounded temporal operator application.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `clause` | `TemporalLogicExpr | None` | `no` | `—` | — |
| `kind` | `Literal[bounded]` | `no` | `'bounded'` | — |
| `left` | `TemporalLogicExpr | None` | `no` | `—` | — |
| `lower_bound` | `int` | `no` | `0` | — |
| `operator` | `Literal[eventually, always, until]` | `yes` | `—` | — |
| `right` | `TemporalLogicExpr | None` | `no` | `—` | — |
| `upper_bound` | `int` | `yes` | `—` | — |

### `polisyos.ir.governance.temporal_logic.TemporalEvaluationScope` { #polisyos-ir-governance-temporal-logic-temporalevaluationscope }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalEvaluationScope`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Where a temporal constraint is expected to be evaluated.

| Enum values |
|-------------|
| `policy_simulation` |
| `compliance_trace` |
| `branching_forecast` |

### `polisyos.ir.governance.temporal_logic.TemporalExecutionSemantics` { #polisyos-ir-governance-temporal-logic-temporalexecutionsemantics }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalExecutionSemantics`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Execution semantics expected by the runtime or compliance checker.

| Enum values |
|-------------|
| `finite_trace` |
| `branching_tree` |
| `windowed_trace` |

### `polisyos.ir.governance.temporal_logic.TemporalLogicFamily` { #polisyos-ir-governance-temporal-logic-temporallogicfamily }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalLogicFamily`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Supported temporal-logic subsets for policy/compliance contracts.

| Enum values |
|-------------|
| `ltl` |
| `ctl` |
| `mtl` |

### `polisyos.ir.governance.temporal_logic.TemporalNot` { #polisyos-ir-governance-temporal-logic-temporalnot }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalNot`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Boolean negation over a temporal formula.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `clause` | `'TemporalLogicExpr'` | `yes` | `—` | — |
| `kind` | `Literal[not]` | `no` | `'not'` | — |

### `polisyos.ir.governance.temporal_logic.TemporalPathFormula` { #polisyos-ir-governance-temporal-logic-temporalpathformula }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalPathFormula`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.temporal_logic.TemporalPathQuantifier`
- Summary: CTL path quantifier over a temporal formula.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `clause` | `'TemporalLogicExpr'` | `yes` | `—` | — |
| `kind` | `Literal[path]` | `no` | `'path'` | — |
| `quantifier` | `polisyos.ir.governance.temporal_logic.TemporalPathQuantifier` | `yes` | `—` | `polisyos.ir.governance.temporal_logic.TemporalPathQuantifier` |

### `polisyos.ir.governance.temporal_logic.TemporalPathQuantifier` { #polisyos-ir-governance-temporal-logic-temporalpathquantifier }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalPathQuantifier`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: CTL path quantifiers.

| Enum values |
|-------------|
| `for_all_paths` |
| `exists_path` |

### `polisyos.ir.governance.temporal_logic.TemporalPolicyConstraint` { #polisyos-ir-governance-temporal-logic-temporalpolicyconstraint }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.governance:TemporalPolicyConstraint`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.temporal_logic.TemporalAll`, `polisyos.ir.governance.temporal_logic.TemporalAny`, `polisyos.ir.governance.temporal_logic.TemporalAtom`, `polisyos.ir.governance.temporal_logic.TemporalBinaryFormula`, `polisyos.ir.governance.temporal_logic.TemporalBoundedFormula`, `polisyos.ir.governance.temporal_logic.TemporalEvaluationScope`, `polisyos.ir.governance.temporal_logic.TemporalExecutionSemantics`, `polisyos.ir.governance.temporal_logic.TemporalLogicFamily`, `polisyos.ir.governance.temporal_logic.TemporalNot`, `polisyos.ir.governance.temporal_logic.TemporalPathFormula`, `polisyos.ir.governance.temporal_logic.TemporalTimeDomain`, `polisyos.ir.governance.temporal_logic.TemporalUnaryFormula`
- Summary: Versioned temporal constraint with explicit execution semantics.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `clock_field` | `str | NoneType` | `no` | `—` | — |
| `constraint_id` | `str` | `yes` | `—` | — |
| `evaluation_scope` | `polisyos.ir.governance.temporal_logic.TemporalEvaluationScope` | `yes` | `—` | `polisyos.ir.governance.temporal_logic.TemporalEvaluationScope` |
| `execution_semantics` | `polisyos.ir.governance.temporal_logic.TemporalExecutionSemantics` | `yes` | `—` | `polisyos.ir.governance.temporal_logic.TemporalExecutionSemantics` |
| `finite_horizon` | `int | NoneType` | `no` | `—` | — |
| `formula` | `polisyos.ir.governance.temporal_logic.TemporalAtom | polisyos.ir.governance.temporal_logic.TemporalNot | polisyos.ir.governance.temporal_logic.TemporalAll | polisyos.ir.governance.temporal_logic.TemporalAny | polisyos.ir.governance.temporal_logic.TemporalUnaryFormula | polisyos.ir.governance.temporal_logic.TemporalBinaryFormula | polisyos.ir.governance.temporal_logic.TemporalBoundedFormula | polisyos.ir.governance.temporal_logic.TemporalPathFormula` | `yes` | `—` | `polisyos.ir.governance.temporal_logic.TemporalAll`, `polisyos.ir.governance.temporal_logic.TemporalAny`, `polisyos.ir.governance.temporal_logic.TemporalAtom`, `polisyos.ir.governance.temporal_logic.TemporalBinaryFormula`, `polisyos.ir.governance.temporal_logic.TemporalBoundedFormula`, `polisyos.ir.governance.temporal_logic.TemporalNot`, `polisyos.ir.governance.temporal_logic.TemporalPathFormula`, `polisyos.ir.governance.temporal_logic.TemporalUnaryFormula` |
| `logic_family` | `polisyos.ir.governance.temporal_logic.TemporalLogicFamily` | `yes` | `—` | `polisyos.ir.governance.temporal_logic.TemporalLogicFamily` |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `time_domain` | `polisyos.ir.governance.temporal_logic.TemporalTimeDomain` | `no` | `<TemporalTimeDomain.STEP: 'step'>` | `polisyos.ir.governance.temporal_logic.TemporalTimeDomain` |

### `polisyos.ir.governance.temporal_logic.TemporalTimeDomain` { #polisyos-ir-governance-temporal-logic-temporaltimedomain }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalTimeDomain`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Clock used by temporal-policy evaluation.

| Enum values |
|-------------|
| `step` |
| `event_time` |

### `polisyos.ir.governance.temporal_logic.TemporalUnaryFormula` { #polisyos-ir-governance-temporal-logic-temporalunaryformula }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalUnaryFormula`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.temporal_logic.TemporalUnaryOperator`
- Summary: Unary temporal operator application.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `clause` | `'TemporalLogicExpr'` | `yes` | `—` | — |
| `kind` | `Literal[unary]` | `no` | `'unary'` | — |
| `operator` | `polisyos.ir.governance.temporal_logic.TemporalUnaryOperator` | `yes` | `—` | `polisyos.ir.governance.temporal_logic.TemporalUnaryOperator` |

### `polisyos.ir.governance.temporal_logic.TemporalUnaryOperator` { #polisyos-ir-governance-temporal-logic-temporalunaryoperator }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:TemporalUnaryOperator`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Unary operators used across LTL/MTL subsets.

| Enum values |
|-------------|
| `not` |
| `next` |
| `eventually` |
| `always` |

### `polisyos.ir.governance.validation.ValidationIssue` { #polisyos-ir-governance-validation-validationissue }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:ValidationIssue`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Represent one normalized validation failure that governance/reporting can persist.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `error_type` | `str` | `yes` | `—` | — |
| `input_value` | `Any | NoneType` | `no` | `—` | — |
| `loc` | `list[str | int]` | `yes` | `—` | — |
| `message` | `str` | `yes` | `—` | — |

### `polisyos.ir.governance.validation.ValidationReport` { #polisyos-ir-governance-validation-validationreport }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.governance:ValidationReport`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.validation.ValidationIssue`
- Summary: Bundle issue summaries, optional repair notes, and diffs for a failed validation pass.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `diff_before_after` | `str | NoneType` | `no` | `—` | — |
| `error_summary` | `str` | `yes` | `—` | — |
| `generated_at` | `str` | `no` | `—` | — |
| `issues` | `list[polisyos.ir.governance.validation.ValidationIssue]` | `yes` | `—` | `polisyos.ir.governance.validation.ValidationIssue` |
| `repair_attempt` | `str | NoneType` | `no` | `—` | — |

## Kernel

### `polisyos.ir.kernel.base.KernelModel` { #polisyos-ir-kernel-base-kernelmodel }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:KernelModel`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Kernel model public type.

### `polisyos.ir.kernel.constraints.ConstraintRegistry` { #polisyos-ir-kernel-constraints-constraintregistry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.kernel:ConstraintRegistry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.constraints.ConstraintSpec`
- Summary: Registry of reusable constraints that ``link_trinity`` and governance checks resolve by id.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `constraints` | `dict[str, polisyos.ir.kernel.constraints.ConstraintSpec]` | `no` | `—` | `polisyos.ir.kernel.constraints.ConstraintSpec` |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.kernel.constraints.ConstraintSpec` { #polisyos-ir-kernel-constraints-constraintspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:ConstraintSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Declare one named bound or legal/accounting rule that downstream linkers can validate.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `constraint_id` | `str` | `yes` | `—` | — |
| `constraint_type` | `Literal[accounting, non_negative, budget, legal] | NoneType` | `no` | `—` | — |
| `description` | `str | NoneType` | `no` | `—` | — |
| `operator` | `Literal[<, <=, >, >=, ==, !=] | NoneType` | `no` | `—` | — |
| `policy_by_mode` | `dict[str, str] | NoneType` | `no` | `—` | — |
| `repair_strategy` | `str | NoneType` | `no` | `—` | — |
| `slot_id` | `str | NoneType` | `no` | `—` | — |
| `unit_id` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.kernel.mechanisms.MechanismTypeRegistry` { #polisyos-ir-kernel-mechanisms-mechanismtyperegistry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.kernel:MechanismTypeRegistry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.mechanisms.MechanismTypeSpec`
- Summary: Registry of mechanism contracts that ``link_trinity`` resolves before execution.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `mechanisms` | `dict[str, polisyos.ir.kernel.mechanisms.MechanismTypeSpec]` | `no` | `—` | `polisyos.ir.kernel.mechanisms.MechanismTypeSpec` |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.kernel.mechanisms.MechanismTypeSpec` { #polisyos-ir-kernel-mechanisms-mechanismtypespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:MechanismTypeSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.mechanisms.ParamSpec`
- Summary: Describe one mechanism contract, including params plus slot read/write side effects.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `default_merge` | `dict[str, str]` | `no` | `—` | — |
| `description` | `str | NoneType` | `no` | `—` | — |
| `mechanism_id` | `str` | `yes` | `—` | — |
| `params` | `dict[str, polisyos.ir.kernel.mechanisms.ParamSpec]` | `no` | `—` | `polisyos.ir.kernel.mechanisms.ParamSpec` |
| `reads_slots` | `list[str]` | `no` | `—` | — |
| `writes_slots` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.kernel.mechanisms.ParamSpec` { #polisyos-ir-kernel-mechanisms-paramspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:ParamSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.mechanisms.ParamType`
- Summary: Define one mechanism parameter, including type, bounds, units, and trainability metadata.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `description` | `str | NoneType` | `no` | `—` | — |
| `enum_values` | `list[str] | NoneType` | `no` | `—` | — |
| `max_value` | `Decimal | NoneType` | `no` | `—` | — |
| `min_value` | `Decimal | NoneType` | `no` | `—` | — |
| `param_id` | `str` | `yes` | `—` | — |
| `prior_mean` | `Decimal | NoneType` | `no` | `—` | — |
| `prior_std` | `Decimal | NoneType` | `no` | `—` | — |
| `required` | `bool` | `no` | `False` | — |
| `trainable` | `bool` | `no` | `False` | — |
| `unit_id` | `str | NoneType` | `no` | `—` | — |
| `value_type` | `polisyos.ir.kernel.mechanisms.ParamType` | `no` | `<ParamType.DECIMAL: 'decimal'>` | `polisyos.ir.kernel.mechanisms.ParamType` |

### `polisyos.ir.kernel.mechanisms.ParamType` { #polisyos-ir-kernel-mechanisms-paramtype }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:ParamType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Param type public type.

| Enum values |
|-------------|
| `decimal` |
| `int` |
| `bool` |
| `string` |
| `money` |
| `rate` |
| `count` |
| `duration` |
| `enum` |
| `object` |
| `array` |

### `polisyos.ir.kernel.merge_rules.ConflictResolution` { #polisyos-ir-kernel-merge-rules-conflictresolution }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:ConflictResolution`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Strategy when concurrent writes conflict.

| Enum values |
|-------------|
| `error` |
| `first` |
| `last` |
| `aggregate` |

### `polisyos.ir.kernel.merge_rules.MergeRuleKind` { #polisyos-ir-kernel-merge-rules-mergerulekind }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:MergeRuleKind`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Core merge rule kinds with CRDT semantics.

| Enum values |
|-------------|
| `sum` |
| `override` |
| `priority` |
| `error` |

### `polisyos.ir.kernel.merge_rules.MergeRuleRef` { #polisyos-ir-kernel-merge-rules-mergeruleref }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:MergeRuleRef`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Reference to a merge rule in the registry.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `rule_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.kernel.merge_rules.MergeRuleRegistry` { #polisyos-ir-kernel-merge-rules-mergeruleregistry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `2.0`
- Exported from: `polisyos.ir.kernel:MergeRuleRegistry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.merge_rules.MergeRuleSpec`
- Summary: Registry of all available merge rules.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `notes` | `list[str]` | `no` | `—` | — |
| `rules` | `dict[str, polisyos.ir.kernel.merge_rules.MergeRuleSpec]` | `no` | `—` | `polisyos.ir.kernel.merge_rules.MergeRuleSpec` |
| `schema_version` | `str` | `no` | `'2.0'` | — |

### `polisyos.ir.kernel.merge_rules.MergeRuleSpec` { #polisyos-ir-kernel-merge-rules-mergerulespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:MergeRuleSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.merge_rules.ConflictResolution`, `polisyos.ir.kernel.merge_rules.MergeRuleKind`
- Summary: Formal specification of a merge rule with algebraic properties.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `allowed_value_types` | `list[Literal[bool, int, decimal, string, array]] | NoneType` | `no` | `—` | — |
| `associativity` | `bool | NoneType` | `no` | `—` | — |
| `commutativity` | `bool | NoneType` | `no` | `—` | — |
| `conflict_resolution` | `polisyos.ir.kernel.merge_rules.ConflictResolution` | `no` | `<ConflictResolution.ERROR: 'error'>` | `polisyos.ir.kernel.merge_rules.ConflictResolution` |
| `default_priority` | `int | NoneType` | `no` | `—` | — |
| `description` | `str | NoneType` | `no` | `—` | — |
| `idempotency` | `bool | NoneType` | `no` | `—` | — |
| `kind` | `polisyos.ir.kernel.merge_rules.MergeRuleKind` | `yes` | `—` | `polisyos.ir.kernel.merge_rules.MergeRuleKind` |
| `rule_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.kernel.metrics.MetricRegistry` { #polisyos-ir-kernel-metrics-metricregistry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.kernel:MetricRegistry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.metrics.MetricSpec`
- Summary: Registry of metric definitions that problem frames and compiled artifacts reference by id.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `metrics` | `dict[str, polisyos.ir.kernel.metrics.MetricSpec]` | `no` | `—` | `polisyos.ir.kernel.metrics.MetricSpec` |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.kernel.metrics.MetricSpec` { #polisyos-ir-kernel-metrics-metricspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:MetricSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Describe a named metric id plus the unit and semantics other contracts should reuse.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `description` | `str | NoneType` | `no` | `—` | — |
| `metric_id` | `str` | `yes` | `—` | — |
| `unit_id` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.kernel.selector_fields.SelectorFieldRegistry` { #polisyos-ir-kernel-selector-fields-selectorfieldregistry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.kernel:SelectorFieldRegistry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.selector_fields.SelectorFieldSpec`
- Summary: Registry of selector fields that ``link_trinity`` uses to validate targeting payloads.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `fields` | `dict[str, polisyos.ir.kernel.selector_fields.SelectorFieldSpec]` | `no` | `—` | `polisyos.ir.kernel.selector_fields.SelectorFieldSpec` |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.kernel.selector_fields.SelectorFieldSpec` { #polisyos-ir-kernel-selector-fields-selectorfieldspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:SelectorFieldSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.slots.SlotScope`
- Summary: Describe one target selector field that interventions may use to address entities.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `description` | `str | NoneType` | `no` | `—` | — |
| `field_id` | `str` | `yes` | `—` | — |
| `scope` | `polisyos.ir.kernel.slots.SlotScope` | `yes` | `—` | `polisyos.ir.kernel.slots.SlotScope` |
| `state_path` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.kernel.slots.MergeOverride` { #polisyos-ir-kernel-slots-mergeoverride }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:MergeOverride`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.merge_rules.ConflictResolution`
- Summary: Slot-specific merge configuration.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `conflict_resolution` | `polisyos.ir.kernel.merge_rules.ConflictResolution | NoneType` | `no` | `—` | `polisyos.ir.kernel.merge_rules.ConflictResolution` |
| `default_priority` | `int | NoneType` | `no` | `—` | — |

### `polisyos.ir.kernel.slots.SlotKind` { #polisyos-ir-kernel-slots-slotkind }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:SlotKind`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Slot kind public type.

| Enum values |
|-------------|
| `stock` |
| `flow` |
| `parameter` |

### `polisyos.ir.kernel.slots.SlotRegistry` { #polisyos-ir-kernel-slots-slotregistry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.kernel:SlotRegistry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.slots.SlotSpec`
- Summary: Registry of runtime slots that policy bundles reference when binding reads, writes, and units.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `slots` | `dict[str, polisyos.ir.kernel.slots.SlotSpec]` | `no` | `—` | `polisyos.ir.kernel.slots.SlotSpec` |

### `polisyos.ir.kernel.slots.SlotScope` { #polisyos-ir-kernel-slots-slotscope }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:SlotScope`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Slot scope public type.

| Enum values |
|-------------|
| `global` |
| `per_agent` |
| `per_firm` |
| `per_cell` |
| `per_entity` |

### `polisyos.ir.kernel.slots.SlotSpec` { #polisyos-ir-kernel-slots-slotspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:SlotSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.merge_rules.MergeRuleRef`, `polisyos.ir.kernel.slots.MergeOverride`, `polisyos.ir.kernel.slots.SlotKind`, `polisyos.ir.kernel.slots.SlotScope`, `polisyos.ir.kernel.slots.SlotValueType`, `polisyos.ir.kernel.units.UnitRef`
- Summary: Specification for a state slot with explicit merge semantics.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `axes` | `list[str] | NoneType` | `no` | `—` | — |
| `conservation_group_id` | `str | NoneType` | `no` | `—` | — |
| `description` | `str | NoneType` | `no` | `—` | — |
| `dtype` | `str | NoneType` | `no` | `—` | — |
| `kind` | `polisyos.ir.kernel.slots.SlotKind` | `yes` | `—` | `polisyos.ir.kernel.slots.SlotKind` |
| `merge_override` | `polisyos.ir.kernel.slots.MergeOverride | NoneType` | `no` | `—` | `polisyos.ir.kernel.slots.MergeOverride` |
| `merge_rule` | `polisyos.ir.kernel.merge_rules.MergeRuleRef` | `yes` | `—` | `polisyos.ir.kernel.merge_rules.MergeRuleRef` |
| `resample_rule` | `str | NoneType` | `no` | `—` | — |
| `reset_rule` | `Literal[carry, zero] | NoneType` | `no` | `—` | — |
| `scope` | `polisyos.ir.kernel.slots.SlotScope` | `yes` | `—` | `polisyos.ir.kernel.slots.SlotScope` |
| `shape` | `list[str] | NoneType` | `no` | `—` | — |
| `slot_id` | `str` | `yes` | `—` | — |
| `state_path` | `str | NoneType` | `no` | `—` | — |
| `unit` | `polisyos.ir.kernel.units.UnitRef | NoneType` | `no` | `—` | `polisyos.ir.kernel.units.UnitRef` |
| `value_type` | `polisyos.ir.kernel.slots.SlotValueType` | `yes` | `—` | `polisyos.ir.kernel.slots.SlotValueType` |

### `polisyos.ir.kernel.slots.SlotValueType` { #polisyos-ir-kernel-slots-slotvaluetype }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:SlotValueType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Slot value type public type.

| Enum values |
|-------------|
| `bool` |
| `int` |
| `decimal` |
| `string` |

### `polisyos.ir.kernel.time_semantics.TimeSemantics` { #polisyos-ir-kernel-time-semantics-timesemantics }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:TimeSemantics`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.types.TimeFrequency`
- Summary: Time semantics public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `end_date` | `str | NoneType` | `no` | `—` | — |
| `frequency` | `polisyos.ir.types.TimeFrequency` | `yes` | `—` | `polisyos.ir.types.TimeFrequency` |
| `notes` | `list[str]` | `no` | `—` | — |
| `start_date` | `str` | `yes` | `—` | — |
| `step_count` | `int | NoneType` | `no` | `—` | — |

### `polisyos.ir.kernel.trust.TrustPolicySpec` { #polisyos-ir-kernel-trust-trustpolicyspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:TrustPolicySpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Describe one named trust policy that downstream scoring and arbitration can apply.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `conflict_policy` | `Literal[optimistic, pessimistic] | NoneType` | `no` | `—` | — |
| `description` | `str | NoneType` | `no` | `—` | — |
| `min_confidence` | `float | NoneType` | `no` | `—` | — |
| `policy_id` | `str` | `yes` | `—` | — |
| `thresholds` | `dict[str, float] | NoneType` | `no` | `—` | — |
| `two_pass_compare` | `bool` | `no` | `False` | — |

### `polisyos.ir.kernel.trust.TrustRegistry` { #polisyos-ir-kernel-trust-trustregistry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.kernel:TrustRegistry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.trust.TrustPolicySpec`
- Summary: Registry of trust policies that packages share through stable ids in Trinity payloads.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `notes` | `list[str]` | `no` | `—` | — |
| `policies` | `dict[str, polisyos.ir.kernel.trust.TrustPolicySpec]` | `no` | `—` | `polisyos.ir.kernel.trust.TrustPolicySpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.kernel.units.CountUnit` { #polisyos-ir-kernel-units-countunit }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:CountUnit`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Count unit public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[count]` | `no` | `'count'` | — |
| `label` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.kernel.units.DimensionlessUnit` { #polisyos-ir-kernel-units-dimensionlessunit }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:DimensionlessUnit`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Dimensionless unit public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[dimensionless]` | `no` | `'dimensionless'` | — |
| `label` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.kernel.units.DurationUnit` { #polisyos-ir-kernel-units-durationunit }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:DurationUnit`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Duration unit public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[duration]` | `no` | `'duration'` | — |
| `unit` | `Literal[step, day, month, quarter, year]` | `no` | `'step'` | — |

### `polisyos.ir.kernel.units.GenericUnit` { #polisyos-ir-kernel-units-genericunit }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:GenericUnit`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Generic unit public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `description` | `str | NoneType` | `no` | `—` | — |
| `kind` | `Literal[generic]` | `no` | `'generic'` | — |
| `label` | `str` | `yes` | `—` | — |

### `polisyos.ir.kernel.units.MoneyUnit` { #polisyos-ir-kernel-units-moneyunit }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:MoneyUnit`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Money unit public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `currency` | `str` | `yes` | `—` | — |
| `kind` | `Literal[money]` | `no` | `'money'` | — |
| `nominal_year` | `int | NoneType` | `no` | `—` | — |
| `price_base` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.kernel.units.RateUnit` { #polisyos-ir-kernel-units-rateunit }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:RateUnit`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Rate unit public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `base` | `Literal[ratio, percent]` | `no` | `'ratio'` | — |
| `kind` | `Literal[rate]` | `no` | `'rate'` | — |

### `polisyos.ir.kernel.units.UnitKind` { #polisyos-ir-kernel-units-unitkind }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:UnitKind`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Unit kind public type.

| Enum values |
|-------------|
| `money` |
| `rate` |
| `count` |
| `duration` |
| `dimensionless` |
| `generic` |

### `polisyos.ir.kernel.units.UnitRef` { #polisyos-ir-kernel-units-unitref }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:UnitRef`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Reference a unit-registry entry from another kernel or IR contract.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `unit_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.kernel.units.UnitSpec` { #polisyos-ir-kernel-units-unitspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.units.UnitKind`
- Summary: Unit spec data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `polisyos.ir.kernel.units.UnitKind` | `yes` | `—` | `polisyos.ir.kernel.units.UnitKind` |

### `polisyos.ir.kernel.units.UnitsRegistry` { #polisyos-ir-kernel-units-unitsregistry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.kernel:UnitsRegistry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.units.CountUnit`, `polisyos.ir.kernel.units.DimensionlessUnit`, `polisyos.ir.kernel.units.DurationUnit`, `polisyos.ir.kernel.units.GenericUnit`, `polisyos.ir.kernel.units.MoneyUnit`, `polisyos.ir.kernel.units.RateUnit`
- Summary: Registry of unit definitions that becomes stable once a registry bundle is composed.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `units` | `dict[str, polisyos.ir.kernel.units.MoneyUnit | polisyos.ir.kernel.units.RateUnit | polisyos.ir.kernel.units.CountUnit | polisyos.ir.kernel.units.DurationUnit | polisyos.ir.kernel.units.DimensionlessUnit | polisyos.ir.kernel.units.GenericUnit]` | `no` | `—` | `polisyos.ir.kernel.units.CountUnit`, `polisyos.ir.kernel.units.DimensionlessUnit`, `polisyos.ir.kernel.units.DurationUnit`, `polisyos.ir.kernel.units.GenericUnit`, `polisyos.ir.kernel.units.MoneyUnit`, `polisyos.ir.kernel.units.RateUnit` |

### `polisyos.ir.kernel.values.CountValue` { #polisyos-ir-kernel-values-countvalue }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:CountValue`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Count value public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `label` | `str | NoneType` | `no` | `—` | — |
| `value` | `int` | `yes` | `—` | — |

### `polisyos.ir.kernel.values.DurationValue` { #polisyos-ir-kernel-values-durationvalue }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:DurationValue`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Duration value public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `unit` | `Literal[step, day, month, quarter, year]` | `no` | `'step'` | — |
| `value` | `int` | `yes` | `—` | — |

### `polisyos.ir.kernel.values.MoneyValue` { #polisyos-ir-kernel-values-moneyvalue }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:MoneyValue`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Money value public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `amount` | `Decimal` | `yes` | `—` | — |
| `currency` | `str` | `yes` | `—` | — |
| `nominal_year` | `int | NoneType` | `no` | `—` | — |

### `polisyos.ir.kernel.values.RateValue` { #polisyos-ir-kernel-values-ratevalue }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.kernel:RateValue`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Rate value public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `base` | `Literal[ratio, percent]` | `no` | `'ratio'` | — |
| `value` | `Decimal` | `yes` | `—` | — |

## Linker

### `polisyos.ir.linker._trinity_models.LinkedIntervention` { #polisyos-ir-linker-trinity-models-linkedintervention }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.linker:LinkedIntervention`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Linked intervention public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `intervention_id` | `str` | `yes` | `—` | — |
| `mechanism_id` | `str` | `yes` | `—` | — |
| `reads_slots` | `list[str]` | `no` | `—` | — |
| `schedule_end` | `int` | `yes` | `—` | — |
| `schedule_start` | `int` | `yes` | `—` | — |
| `writes_slots` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.linker._trinity_models.LinkedTrinityBundle` { #polisyos-ir-linker-trinity-models-linkedtrinitybundle }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.linker:LinkedTrinityBundle`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.linker._trinity_models.TrinityBindings`, `polisyos.ir.trinity.TrinityBundle`
- Summary: Bundle a Trinity payload with resolved registry bindings and stable digests after linking.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bindings` | `polisyos.ir.linker._trinity_models.TrinityBindings` | `no` | `—` | `polisyos.ir.linker._trinity_models.TrinityBindings` |
| `bundle` | `polisyos.ir.trinity.TrinityBundle` | `yes` | `—` | `polisyos.ir.trinity.TrinityBundle` |
| `bundle_digest` | `str | NoneType` | `no` | `—` | — |
| `registry_digest` | `str | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.linker._trinity_models.TrinityBindings` { #polisyos-ir-linker-trinity-models-trinitybindings }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.linker:TrinityBindings`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.linker._trinity_models.LinkedIntervention`
- Summary: Trinity bindings public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `interventions` | `list[polisyos.ir.linker._trinity_models.LinkedIntervention]` | `no` | `—` | `polisyos.ir.linker._trinity_models.LinkedIntervention` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `used_constraints` | `list[str]` | `no` | `—` | — |
| `used_mechanisms` | `list[str]` | `no` | `—` | — |
| `used_metrics` | `list[str]` | `no` | `—` | — |
| `used_selector_fields` | `list[str]` | `no` | `—` | — |
| `used_slots_read` | `list[str]` | `no` | `—` | — |
| `used_slots_write` | `list[str]` | `no` | `—` | — |
| `used_units` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.linker.reports.LinkIssue` { #polisyos-ir-linker-reports-linkissue }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.linker:LinkIssue`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.linker.reports.LinkIssueCode`, `polisyos.ir.linker.reports.LinkSeverity`
- Summary: Describe one linker finding about a missing registry item, mismatch, or deprecated binding.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `code` | `polisyos.ir.linker.reports.LinkIssueCode` | `yes` | `—` | `polisyos.ir.linker.reports.LinkIssueCode` |
| `data` | `dict[str, Any]` | `no` | `—` | — |
| `ids` | `dict[str, str]` | `no` | `—` | — |
| `message` | `str` | `yes` | `—` | — |
| `path` | `list[str | int]` | `no` | `—` | — |
| `severity` | `polisyos.ir.linker.reports.LinkSeverity` | `no` | `<LinkSeverity.ERROR: 'error'>` | `polisyos.ir.linker.reports.LinkSeverity` |

### `polisyos.ir.linker.reports.LinkIssueCode` { #polisyos-ir-linker-reports-linkissuecode }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.linker:LinkIssueCode`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Link issue code public type.

| Enum values |
|-------------|
| `unknown_unit` |
| `unknown_concept` |
| `missing_slot` |
| `incompatible_constraint` |
| `unknown_mechanism` |
| `missing_param` |
| `unknown_param` |
| `param_path` |
| `param_type` |
| `param_enum` |
| `param_range` |
| `unit_mismatch` |
| `unknown_metric` |
| `unknown_selector_field` |
| `selector_scope_mismatch` |
| `unknown_merge_rule` |
| `merge_rule_conflict` |
| `unknown_constraint` |
| `unknown_actor` |
| `unknown_jurisdiction` |
| `missing_registry` |
| `unused_registry` |
| `unused_mechanism` |
| `unused_slot` |
| `unused_constraint` |
| `deprecated_mechanism_bindings` |
| `model_fidelity_level_ignored` |
| `unknown_slot` |
| `merge_conflict` |
| `merge_priority_missing` |
| `observation_item_type` |
| `invalid_artifact_id` |
| `missing_action_field` |
| `action_field_type` |
| `action_type` |
| `action_type_mismatch` |
| `policy_model_type` |
| `policy_model_layers` |
| `unknown_utility_field` |
| `money_currency_mismatch` |
| `money_currency_missing` |

### `polisyos.ir.linker.reports.LinkReport` { #polisyos-ir-linker-reports-linkreport }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.linker:LinkReport`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.linker.reports.LinkIssue`
- Summary: Collect deterministic linker findings that gate whether a Trinity bundle is executable.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `issues` | `list[polisyos.ir.linker.reports.LinkIssue]` | `no` | `—` | `polisyos.ir.linker.reports.LinkIssue` |
| `notes` | `list[str]` | `no` | `—` | — |
| `ok` | `bool` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.linker.reports.LinkSeverity` { #polisyos-ir-linker-reports-linkseverity }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.linker:LinkSeverity`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Link severity public type.

| Enum values |
|-------------|
| `error` |
| `warning` |
| `info` |

## Migrations

### `polisyos.ir.migrations.base.CompatibilityMode` { #polisyos-ir-migrations-base-compatibilitymode }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.migrations:CompatibilityMode`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Declared direct-read compatibility mode for a schema version.

| Enum values |
|-------------|
| `full` |
| `backward` |
| `forward` |
| `none` |

### `polisyos.ir.migrations.base.MigrationCompatibilityError` { #polisyos-ir-migrations-base-migrationcompatibilityerror }

- Kind: `class`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Raised when a migration edge violates declared schema compatibility policy.

### `polisyos.ir.migrations.base.MigrationEdge` { #polisyos-ir-migrations-base-migrationedge }

- Kind: `dataclass`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Registered migration edge with its declared compatibility intent.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `to_version` | `str` | `yes` | `—` | — |
| `fn` | `MigrationFn` | `yes` | `—` | — |
| `compatibility` | `CompatibilityMode` | `yes` | `—` | — |

### `polisyos.ir.migrations.base.MigrationError` { #polisyos-ir-migrations-base-migrationerror }

- Kind: `class`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Base error for IR migration compatibility failures.

### `polisyos.ir.migrations.base.MigrationSchemaVersionError` { #polisyos-ir-migrations-base-migrationschemaversionerror }

- Kind: `class`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Raised when a migrator returns an incompatible schema_version.

### `polisyos.ir.migrations.base.SchemaCompatibilityDecision` { #polisyos-ir-migrations-base-schemacompatibilitydecision }

- Kind: `dataclass`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.migrations:SchemaCompatibilityDecision`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Rule-based answer for producer/consumer schema negotiation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact` | `str` | `yes` | `—` | — |
| `producer_version` | `str` | `yes` | `—` | — |
| `consumer_version` | `str` | `yes` | `—` | — |
| `can_read` | `bool` | `yes` | `—` | — |
| `mode` | `CompatibilityMode` | `yes` | `—` | — |
| `migration_required` | `bool` | `no` | `False` | — |
| `reason` | `str` | `no` | `''` | — |

### `polisyos.ir.migrations.base.SchemaCompatibilityRule` { #polisyos-ir-migrations-base-schemacompatibilityrule }

- Kind: `dataclass`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compatibility declaration for one artifact schema version.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact` | `str` | `yes` | `—` | — |
| `version` | `str` | `yes` | `—` | — |
| `mode` | `CompatibilityMode` | `yes` | `—` | — |
| `readable_versions` | `frozenset[str]` | `no` | `frozenset()` | — |
| `writable_versions` | `frozenset[str]` | `no` | `frozenset()` | — |
| `additive_optional_fields` | `frozenset[str]` | `no` | `frozenset()` | — |
| `removed_fields` | `frozenset[str]` | `no` | `frozenset()` | — |
| `renamed_fields` | `frozenset[tuple[str, str]]` | `no` | `frozenset()` | — |
| `canonical_defaults` | `frozenset[tuple[str, str]]` | `no` | `frozenset()` | — |
| `notes` | `tuple[str, ...]` | `no` | `()` | — |

## Observation

### `polisyos.ir.observation.bridges.CdiscDatasetBridge` { #polisyos-ir-observation-bridges-cdiscdatasetbridge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:CdiscDatasetBridge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bridges.ObservationBridgeStandard`
- Summary: CDISC-friendly table mapping for an observation panel.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `dataset_name` | `str` | `yes` | `—` | — |
| `domain` | `str` | `yes` | `—` | — |
| `key_variables` | `list[str]` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `row_count` | `int` | `yes` | `—` | — |
| `standard` | `polisyos.ir.observation.bridges.ObservationBridgeStandard` | `no` | `<ObservationBridgeStandard.CDISC: 'cdisc'>` | `polisyos.ir.observation.bridges.ObservationBridgeStandard` |
| `variable_names` | `list[str]` | `yes` | `—` | — |

### `polisyos.ir.observation.bridges.DdiVariableBridge` { #polisyos-ir-observation-bridges-ddivariablebridge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:DdiVariableBridge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bridges.ObservationBridgeStandard`
- Summary: Expose DDI-friendly variable metadata derived from one observation contract.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `label` | `str` | `yes` | `—` | — |
| `representation_type` | `str` | `yes` | `—` | — |
| `source_reference` | `str` | `yes` | `—` | — |
| `standard` | `polisyos.ir.observation.bridges.ObservationBridgeStandard` | `no` | `<ObservationBridgeStandard.DDI: 'ddi'>` | `polisyos.ir.observation.bridges.ObservationBridgeStandard` |
| `universe_reference` | `str` | `yes` | `—` | — |
| `variable_name` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.bridges.FhirObservationBridge` { #polisyos-ir-observation-bridges-fhirobservationbridge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:FhirObservationBridge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bridges.FhirQuantityBridge`, `polisyos.ir.observation.bridges.ObservationBridgeStandard`
- Summary: FHIR Observation-shaped projection of an IR observation record.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `code` | `str` | `yes` | `—` | — |
| `code_system` | `str` | `yes` | `—` | — |
| `components` | `dict[str, str]` | `no` | `—` | — |
| `effective_end` | `str` | `yes` | `—` | — |
| `effective_start` | `str` | `yes` | `—` | — |
| `identifier` | `str` | `yes` | `—` | — |
| `resource_type` | `str` | `no` | `'Observation'` | — |
| `standard` | `polisyos.ir.observation.bridges.ObservationBridgeStandard` | `no` | `<ObservationBridgeStandard.FHIR: 'fhir'>` | `polisyos.ir.observation.bridges.ObservationBridgeStandard` |
| `status` | `str` | `no` | `'final'` | — |
| `subject_reference` | `str` | `yes` | `—` | — |
| `value_quantity` | `polisyos.ir.observation.bridges.FhirQuantityBridge` | `yes` | `—` | `polisyos.ir.observation.bridges.FhirQuantityBridge` |

### `polisyos.ir.observation.bridges.FhirQuantityBridge` { #polisyos-ir-observation-bridges-fhirquantitybridge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:FhirQuantityBridge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: FHIR quantity payload for one observation value.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `system` | `str` | `no` | `'http://unitsofmeasure.org'` | — |
| `unit` | `str` | `yes` | `—` | — |
| `value` | `float` | `yes` | `—` | — |

### `polisyos.ir.observation.bridges.ObservationBridgeStandard` { #polisyos-ir-observation-bridges-observationbridgestandard }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:ObservationBridgeStandard`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: External standards covered by the observation bridge layer.

| Enum values |
|-------------|
| `sdmx` |
| `ddi` |
| `fhir` |
| `cdisc` |

### `polisyos.ir.observation.bridges.SdmxObservationBridge` { #polisyos-ir-observation-bridges-sdmxobservationbridge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:SdmxObservationBridge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bridges.ObservationBridgeStandard`
- Summary: Map an IR observation record onto an SDMX-like series/observation payload.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `attributes` | `dict[str, str]` | `no` | `—` | — |
| `dataset_id` | `str` | `yes` | `—` | — |
| `observation_dimension` | `str` | `yes` | `—` | — |
| `series_key` | `dict[str, str]` | `yes` | `—` | — |
| `standard` | `polisyos.ir.observation.bridges.ObservationBridgeStandard` | `no` | `<ObservationBridgeStandard.SDMX: 'sdmx'>` | `polisyos.ir.observation.bridges.ObservationBridgeStandard` |
| `unit` | `str` | `yes` | `—` | — |
| `value` | `float` | `yes` | `—` | — |

### `polisyos.ir.observation.bundles.AgentFactorEmbeddingsBundleManifest` { #polisyos-ir-observation-bundles-agentfactorembeddingsbundlemanifest }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:AgentFactorEmbeddingsBundleManifest`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.BundleAxisSemantic`, `polisyos.ir.observation.bundles.BundleLineageRef`, `polisyos.ir.observation.bundles.RequiredArraySpec`
- Summary: Describe latent agent-factor arrays and embedding method provenance.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[agent_factor_embeddings_v1.npz]` | `no` | `'agent_factor_embeddings_v1.npz'` | — |
| `axis_semantics` | `list[polisyos.ir.observation.bundles.BundleAxisSemantic]` | `yes` | `—` | `polisyos.ir.observation.bundles.BundleAxisSemantic` |
| `contract_payload` | `dict[str, Any]` | `no` | `—` | — |
| `embedding_method` | `str` | `yes` | `—` | — |
| `lineage` | `list[polisyos.ir.observation.bundles.BundleLineageRef]` | `no` | `—` | `polisyos.ir.observation.bundles.BundleLineageRef` |
| `required_arrays` | `list[polisyos.ir.observation.bundles.RequiredArraySpec]` | `yes` | `—` | `polisyos.ir.observation.bundles.RequiredArraySpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.bundles.BacktestPlanBundle` { #polisyos-ir-observation-bundles-backtestplanbundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:BacktestPlanBundle`, `polisyos.ir:BacktestPlanBundle`
- ABI snapshot: `backtest_plan_bundle` / `schemas/snapshots/ir/backtest_plan_bundle.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.ContractCompatibilityTarget`
- Summary: Bundle of historical validation plans and their frozen payloads.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[backtest_plan_bundle.json]` | `no` | `'backtest_plan_bundle.json'` | — |
| `contract_target` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` | `yes` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |
| `historical_payloads` | `dict[str, dict[str, Any]]` | `no` | `—` | — |
| `holdout_windows` | `list[str]` | `no` | `—` | — |
| `plans` | `list[HistoricalValidationPlan]` | `no` | `—` | — |
| `required_fields` | `list[str]` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.bundles.BilevelProblemBundle` { #polisyos-ir-observation-bundles-bilevelproblembundle }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:BilevelProblemBundle`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Persist an optimization-ready bilevel problem snapshot and result summary.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `A_lower` | `list[list[float]]` | `yes` | `—` | — |
| `A_upper` | `list[list[float]]` | `yes` | `—` | — |
| `artifact_name` | `Literal[bilevel_problem_bundle_v1.json]` | `no` | `'bilevel_problem_bundle_v1.json'` | — |
| `b_lower` | `list[float]` | `yes` | `—` | — |
| `b_upper` | `list[float]` | `yes` | `—` | — |
| `c_lower` | `list[float]` | `yes` | `—` | — |
| `c_upper` | `list[float]` | `yes` | `—` | — |
| `knob_names` | `list[str]` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `optimization_target` | `str` | `no` | `'optimization.bilevel.bilevel@1.0.0'` | — |
| `result_summary` | `dict[str, Any]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.bundles.BoundsChannelSpec` { #polisyos-ir-observation-bundles-boundschannelspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:BoundsChannelSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: Bounds-estimation policy for one observation family.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bound_strategy` | `str` | `yes` | `—` | — |
| `fallback_reason` | `str` | `yes` | `—` | — |
| `family` | `polisyos.ir.observation.contracts.ObservationFamily` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `notes` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.observation.bundles.BoundsEstimationBundle` { #polisyos-ir-observation-bundles-boundsestimationbundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:BoundsEstimationBundle`, `polisyos.ir:BoundsEstimationBundle`
- ABI snapshot: `bounds_estimation_bundle` / `schemas/snapshots/ir/bounds_estimation_bundle.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.BoundsChannelSpec`
- Summary: Declare available bounds strategies and fallback reasons by observation family.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[bounds_estimation_bundle_v1.json]` | `no` | `'bounds_estimation_bundle_v1.json'` | — |
| `available_estimators` | `list[str]` | `no` | `—` | — |
| `channels` | `list[polisyos.ir.observation.bundles.BoundsChannelSpec]` | `yes` | `—` | `polisyos.ir.observation.bundles.BoundsChannelSpec` |
| `contract_payload` | `dict[str, Any]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.bundles.BundleAxisSemantic` { #polisyos-ir-observation-bundles-bundleaxissemantic }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:BundleAxisSemantic`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Human-readable meaning attached to one bundle axis.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `axis` | `str` | `yes` | `—` | — |
| `description` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.bundles.BundleLineageRef` { #polisyos-ir-observation-bundles-bundlelineageref }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:BundleLineageRef`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.ObservationFamily`, `polisyos.ir.observation.contracts.SourceConfidenceTier`
- Summary: Lineage edge from a bundle back to an upstream observation artifact.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `notes` | `list[str]` | `no` | `—` | — |
| `source_artifact` | `str` | `yes` | `—` | — |
| `source_confidence_tier` | `polisyos.ir.observation.contracts.SourceConfidenceTier` | `no` | `<SourceConfidenceTier.VALIDATED: 'validated'>` | `polisyos.ir.observation.contracts.SourceConfidenceTier` |
| `source_family` | `polisyos.ir.observation.contracts.ObservationFamily | NoneType` | `no` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |

### `polisyos.ir.observation.bundles.CalibrationTargetBundleManifest` { #polisyos-ir-observation-bundles-calibrationtargetbundlemanifest }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:CalibrationTargetBundleManifest`, `polisyos.ir:CalibrationTargetBundleManifest`
- ABI snapshot: `calibration_target_bundle_manifest` / `schemas/snapshots/ir/calibration_target_bundle_manifest.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.BundleAxisSemantic`, `polisyos.ir.observation.bundles.BundleLineageRef`, `polisyos.ir.observation.bundles.ContractCompatibilityTarget`, `polisyos.ir.observation.bundles.RequiredArraySpec`, `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: Declare calibration tensors, axis semantics, and provenance lineage.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[calibration_target_bundle_v1.npz]` | `no` | `'calibration_target_bundle_v1.npz'` | — |
| `axis_semantics` | `list[polisyos.ir.observation.bundles.BundleAxisSemantic]` | `yes` | `—` | `polisyos.ir.observation.bundles.BundleAxisSemantic` |
| `contract_target` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` | `yes` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |
| `lineage` | `list[polisyos.ir.observation.bundles.BundleLineageRef]` | `no` | `—` | `polisyos.ir.observation.bundles.BundleLineageRef` |
| `observation_families` | `list[polisyos.ir.observation.contracts.ObservationFamily]` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `required_arrays` | `list[polisyos.ir.observation.bundles.RequiredArraySpec]` | `yes` | `—` | `polisyos.ir.observation.bundles.RequiredArraySpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.bundles.CausalPanelBundleManifest` { #polisyos-ir-observation-bundles-causalpanelbundlemanifest }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:CausalPanelBundleManifest`, `polisyos.ir:CausalPanelBundleManifest`
- ABI snapshot: `causal_panel_bundle_manifest` / `schemas/snapshots/ir/causal_panel_bundle_manifest.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.BundleLineageRef`, `polisyos.ir.observation.bundles.ContractCompatibilityTarget`, `polisyos.ir.observation.bundles.RequiredColumnSpec`
- Summary: Describe a compiled panel table that satisfies a causal estimator contract.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[causal_panel_bundle_monthly.parquet]` | `no` | `'causal_panel_bundle_monthly.parquet'` | — |
| `contract_payload` | `dict[str, Any]` | `no` | `—` | — |
| `contract_target` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` | `yes` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |
| `lineage` | `list[polisyos.ir.observation.bundles.BundleLineageRef]` | `no` | `—` | `polisyos.ir.observation.bundles.BundleLineageRef` |
| `required_columns` | `list[polisyos.ir.observation.bundles.RequiredColumnSpec]` | `yes` | `—` | `polisyos.ir.observation.bundles.RequiredColumnSpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `table_rows` | `list[dict[str, Any]]` | `no` | `—` | — |

### `polisyos.ir.observation.bundles.CellPrototypeEmbeddingsBundleManifest` { #polisyos-ir-observation-bundles-cellprototypeembeddingsbundlemanifest }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:CellPrototypeEmbeddingsBundleManifest`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.BundleAxisSemantic`, `polisyos.ir.observation.bundles.BundleLineageRef`, `polisyos.ir.observation.bundles.RequiredArraySpec`
- Summary: Describe prototype-cell embedding arrays and clustering provenance.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[cell_prototype_embeddings_v1.npz]` | `no` | `'cell_prototype_embeddings_v1.npz'` | — |
| `axis_semantics` | `list[polisyos.ir.observation.bundles.BundleAxisSemantic]` | `yes` | `—` | `polisyos.ir.observation.bundles.BundleAxisSemantic` |
| `clustering_method` | `str` | `yes` | `—` | — |
| `contract_payload` | `dict[str, Any]` | `no` | `—` | — |
| `lineage` | `list[polisyos.ir.observation.bundles.BundleLineageRef]` | `no` | `—` | `polisyos.ir.observation.bundles.BundleLineageRef` |
| `required_arrays` | `list[polisyos.ir.observation.bundles.RequiredArraySpec]` | `yes` | `—` | `polisyos.ir.observation.bundles.RequiredArraySpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.bundles.ContractCompatibilityTarget` { #polisyos-ir-observation-bundles-contractcompatibilitytarget }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:ContractCompatibilityTarget`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Identifier of a downstream contract that an observation bundle targets.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `contract_fqn` | `str` | `yes` | `—` | — |
| `contract_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.bundles.CounterfactualCheckBundle` { #polisyos-ir-observation-bundles-counterfactualcheckbundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:CounterfactualCheckBundle`, `polisyos.ir:CounterfactualCheckBundle`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.CounterfactualCheckSpec`
- Summary: Bundle of counterfactual queries queued for readiness validation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[counterfactual_check_bundle_v1.json]` | `no` | `'counterfactual_check_bundle_v1.json'` | — |
| `queries` | `list[polisyos.ir.observation.bundles.CounterfactualCheckSpec]` | `yes` | `—` | `polisyos.ir.observation.bundles.CounterfactualCheckSpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.bundles.CounterfactualCheckSpec` { #polisyos-ir-observation-bundles-counterfactualcheckspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:CounterfactualCheckSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: Request to evaluate a counterfactual query before execution.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `family` | `polisyos.ir.observation.contracts.ObservationFamily | NoneType` | `no` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `notes` | `list[str]` | `no` | `—` | — |
| `query` | `dict[str, Any]` | `no` | `—` | — |
| `query_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.bundles.DTRTreatmentSequenceBundleManifest` { #polisyos-ir-observation-bundles-dtrtreatmentsequencebundlemanifest }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:DTRTreatmentSequenceBundleManifest`, `polisyos.ir:DTRTreatmentSequenceBundleManifest`
- ABI snapshot: `dtr_treatment_sequence_bundle_manifest` / `schemas/snapshots/ir/dtr_treatment_sequence_bundle_manifest.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.BundleAxisSemantic`, `polisyos.ir.observation.bundles.BundleLineageRef`, `polisyos.ir.observation.bundles.ContractCompatibilityTarget`, `polisyos.ir.observation.bundles.RequiredArraySpec`
- Summary: Describe the tensor payload required by sequential/DTR estimators.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[dtr_treatment_sequence_bundle_v1.npz]` | `no` | `'dtr_treatment_sequence_bundle_v1.npz'` | — |
| `axis_semantics` | `list[polisyos.ir.observation.bundles.BundleAxisSemantic]` | `yes` | `—` | `polisyos.ir.observation.bundles.BundleAxisSemantic` |
| `contract_payload` | `dict[str, Any]` | `no` | `—` | — |
| `contract_target` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` | `yes` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |
| `lineage` | `list[polisyos.ir.observation.bundles.BundleLineageRef]` | `no` | `—` | `polisyos.ir.observation.bundles.BundleLineageRef` |
| `required_arrays` | `list[polisyos.ir.observation.bundles.RequiredArraySpec]` | `yes` | `—` | `polisyos.ir.observation.bundles.RequiredArraySpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.bundles.GovernancePassMappingBundle` { #polisyos-ir-observation-bundles-governancepassmappingbundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:GovernancePassMappingBundle`, `polisyos.ir:GovernancePassMappingBundle`
- ABI snapshot: `governance_pass_mapping_bundle` / `schemas/snapshots/ir/governance_pass_mapping_bundle.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.governance.GovernancePassAliasRegistry`
- Summary: Persist resolved family-to-pass routing together with alias metadata.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `alias_registry` | `polisyos.ir.observation.governance.GovernancePassAliasRegistry` | `yes` | `—` | `polisyos.ir.observation.governance.GovernancePassAliasRegistry` |
| `artifact_name` | `Literal[governance_pass_mapping_v1.json]` | `no` | `'governance_pass_mapping_v1.json'` | — |
| `family_passes` | `dict[str, list[str]]` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.bundles.HeckmanCorrectionBundle` { #polisyos-ir-observation-bundles-heckmancorrectionbundle }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:HeckmanCorrectionBundle`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.BundleLineageRef`, `polisyos.ir.observation.bundles.ContractCompatibilityTarget`, `polisyos.ir.observation.bundles.RequiredColumnSpec`
- Summary: Describe selection-correction tables and payloads for Heckman estimators.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[heckman_correction_bundle_v1.parquet]` | `no` | `'heckman_correction_bundle_v1.parquet'` | — |
| `contract_payload` | `dict[str, Any]` | `no` | `—` | — |
| `contract_target` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` | `yes` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |
| `lineage` | `list[polisyos.ir.observation.bundles.BundleLineageRef]` | `no` | `—` | `polisyos.ir.observation.bundles.BundleLineageRef` |
| `required_columns` | `list[polisyos.ir.observation.bundles.RequiredColumnSpec]` | `yes` | `—` | `polisyos.ir.observation.bundles.RequiredColumnSpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `table_rows` | `list[dict[str, Any]]` | `no` | `—` | — |

### `polisyos.ir.observation.bundles.InterferenceLossSpecBundle` { #polisyos-ir-observation-bundles-interferencelossspecbundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:InterferenceLossSpecBundle`, `polisyos.ir:InterferenceLossSpecBundle`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.InterferenceLossTargetSpec`
- Summary: Bundle of interference-loss targets for measurement-aware calibration.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[interference_loss_spec_bundle_v1.json]` | `no` | `'interference_loss_spec_bundle_v1.json'` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `specs` | `list[polisyos.ir.observation.bundles.InterferenceLossTargetSpec]` | `yes` | `—` | `polisyos.ir.observation.bundles.InterferenceLossTargetSpec` |

### `polisyos.ir.observation.bundles.InterferenceLossTargetSpec` { #polisyos-ir-observation-bundles-interferencelosstargetspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:InterferenceLossTargetSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.MultiplexGraphLayerId`, `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: Observed spillover target used by interference-aware calibration losses.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `adjacency` | `list[list[float]]` | `yes` | `—` | — |
| `censoring_mask` | `list[bool]` | `no` | `—` | — |
| `coverage_estimate` | `list[float]` | `no` | `—` | — |
| `family` | `polisyos.ir.observation.contracts.ObservationFamily` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `graph_layer` | `polisyos.ir.observation.contracts.MultiplexGraphLayerId` | `yes` | `—` | `polisyos.ir.observation.contracts.MultiplexGraphLayerId` |
| `huber_delta` | `float` | `no` | `1.0` | — |
| `lag_days_estimate` | `list[int]` | `no` | `—` | — |
| `loss_kind` | `Literal[mse, huber]` | `no` | `'mse'` | — |
| `normalization` | `Literal[row, global, none]` | `no` | `'row'` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `observed_spillover` | `list[float]` | `yes` | `—` | — |
| `predicted_metric_path` | `str` | `yes` | `—` | — |
| `schema_regime_id` | `list[str]` | `no` | `—` | — |
| `shock_mask` | `list[bool]` | `no` | `—` | — |
| `spec_id` | `str` | `yes` | `—` | — |
| `trust_weight` | `list[float]` | `no` | `—` | — |

### `polisyos.ir.observation.bundles.LeontiefIOBundle` { #polisyos-ir-observation-bundles-leontiefiobundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:LeontiefIOBundle`, `polisyos.ir:LeontiefIOBundle`
- ABI snapshot: `leontief_io_bundle` / `schemas/snapshots/ir/leontief_io_bundle.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Input bundle for Leontief input-output analysis and optimization.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[leontief_io_bundle_v1.json]` | `no` | `'leontief_io_bundle_v1.json'` | — |
| `contract_payload` | `dict[str, Any]` | `no` | `—` | — |
| `final_demand` | `list[float]` | `no` | `—` | — |
| `optimization_target` | `str` | `no` | `'optimization.io_leontief'` | — |
| `region_index_map` | `dict[str, int]` | `no` | `—` | — |
| `regions` | `list[str]` | `yes` | `—` | — |
| `required_tables` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `sector_index_map` | `dict[str, int]` | `no` | `—` | — |
| `sector_names` | `list[str]` | `no` | `—` | — |
| `sectors` | `list[str]` | `yes` | `—` | — |
| `technical_coefficients` | `list[list[float]]` | `no` | `—` | — |
| `value_added` | `list[float]` | `no` | `—` | — |

### `polisyos.ir.observation.bundles.LessonRegistrySeedBundle` { #polisyos-ir-observation-bundles-lessonregistryseedbundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:LessonRegistrySeedBundle`, `polisyos.ir:LessonRegistrySeedBundle`
- ABI snapshot: `lesson_registry_seed_bundle` / `schemas/snapshots/ir/lesson_registry_seed_bundle.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.ContractCompatibilityTarget`, `polisyos.ir.observation.bundles.LessonRegistrySeedEntry`
- Summary: Bundle of lesson-card seeds emitted from observation-layer governance.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[lesson_registry_seed_v1.json]` | `no` | `'lesson_registry_seed_v1.json'` | — |
| `contract_target` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` | `yes` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `seed_entries` | `list[polisyos.ir.observation.bundles.LessonRegistrySeedEntry]` | `yes` | `—` | `polisyos.ir.observation.bundles.LessonRegistrySeedEntry` |

### `polisyos.ir.observation.bundles.LessonRegistrySeedEntry` { #polisyos-ir-observation-bundles-lessonregistryseedentry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:LessonRegistrySeedEntry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Seed record used to publish lesson cards from observation failures.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `failure_type` | `str` | `yes` | `—` | — |
| `fidelity_level` | `int` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `stage_name` | `str` | `yes` | `—` | — |
| `summary` | `str` | `yes` | `—` | — |
| `tags` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.observation.bundles.MicrosimSurveyContractBundle` { #polisyos-ir-observation-bundles-microsimsurveycontractbundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:MicrosimSurveyContractBundle`, `polisyos.ir:MicrosimSurveyContractBundle`
- ABI snapshot: `microsim_survey_contract_bundle` / `schemas/snapshots/ir/microsim_survey_contract_bundle.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.ContractCompatibilityTarget`, `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: Bundle carrying survey-microdata payloads for microsimulation methods.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[microsim_survey_contract_v1.json]` | `no` | `'microsim_survey_contract_v1.json'` | — |
| `contract_payload` | `dict[str, Any]` | `no` | `—` | — |
| `contract_target` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` | `yes` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |
| `notes` | `list[str]` | `no` | `—` | — |
| `observation_families` | `list[polisyos.ir.observation.contracts.ObservationFamily]` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `required_fields` | `list[str]` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.bundles.NetworkCausalContractBundle` { #polisyos-ir-observation-bundles-networkcausalcontractbundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:NetworkCausalContractBundle`, `polisyos.ir:NetworkCausalContractBundle`
- ABI snapshot: `network_causal_contract_bundle` / `schemas/snapshots/ir/network_causal_contract_bundle.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.ContractCompatibilityTarget`, `polisyos.ir.observation.contracts.MultiplexGraphLayerId`
- Summary: Manifest and payload wrapper for interference-aware network causal inputs.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[network_causal_contract_bundle_v1.json]` | `no` | `'network_causal_contract_bundle_v1.json'` | — |
| `contract_payload` | `dict[str, Any]` | `no` | `—` | — |
| `contract_target` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` | `yes` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |
| `exposure_fields` | `list[str]` | `no` | `—` | — |
| `interference_required` | `bool` | `no` | `True` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `supported_layers` | `list[polisyos.ir.observation.contracts.MultiplexGraphLayerId]` | `yes` | `—` | `polisyos.ir.observation.contracts.MultiplexGraphLayerId` |

### `polisyos.ir.observation.bundles.NetworkContractBundle` { #polisyos-ir-observation-bundles-networkcontractbundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:NetworkContractBundle`, `polisyos.ir:NetworkContractBundle`
- ABI snapshot: `network_contract_bundle` / `schemas/snapshots/ir/network_contract_bundle.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.ContractCompatibilityTarget`, `polisyos.ir.observation.contracts.MultiplexGraphLayerId`
- Summary: Bundle carrying graph structures for network-oriented runtime contracts.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `alignment_keys` | `list[str]` | `no` | `—` | — |
| `artifact_name` | `Literal[network_contract_bundle_v1.json]` | `no` | `'network_contract_bundle_v1.json'` | — |
| `contract_payloads` | `dict[str, dict[str, Any]]` | `no` | `—` | — |
| `contract_targets` | `list[polisyos.ir.observation.bundles.ContractCompatibilityTarget]` | `yes` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |
| `graph_layers` | `list[polisyos.ir.observation.contracts.MultiplexGraphLayerId]` | `yes` | `—` | `polisyos.ir.observation.contracts.MultiplexGraphLayerId` |
| `low_rank_factors` | `dict[str, dict[str, list[list[float]]]]` | `no` | `—` | — |
| `node_index_map` | `dict[str, int]` | `no` | `—` | — |
| `node_order` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `slice_settings` | `dict[str, Any]` | `no` | `—` | — |
| `source_artifacts` | `list[str]` | `yes` | `—` | — |
| `sparse_edges` | `dict[str, list[dict[str, Any]]]` | `no` | `—` | — |

### `polisyos.ir.observation.bundles.ObservationContractArtifact` { #polisyos-ir-observation-bundles-observationcontractartifact }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:ObservationContractArtifact`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.BundleLineageRef`, `polisyos.ir.observation.bundles.ContractCompatibilityTarget`
- Summary: Manifest entry describing one compiled observation artifact.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `str` | `yes` | `—` | — |
| `blocking_reason` | `str | NoneType` | `no` | `—` | — |
| `compiler_id` | `str` | `yes` | `—` | — |
| `lineage` | `list[polisyos.ir.observation.bundles.BundleLineageRef]` | `no` | `—` | `polisyos.ir.observation.bundles.BundleLineageRef` |
| `notes` | `list[str]` | `no` | `—` | — |
| `status` | `Literal[compiled, blocked, skipped]` | `no` | `'compiled'` | — |
| `target_contract` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget | NoneType` | `no` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |

### `polisyos.ir.observation.bundles.ObservationContractRoute` { #polisyos-ir-observation-bundles-observationcontractroute }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:ObservationContractRoute`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.ContractCompatibilityTarget`, `polisyos.ir.observation.contracts.IdentificationMode`, `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: Route from an observation family and identification mode to a contract target.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `family` | `polisyos.ir.observation.contracts.ObservationFamily` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `identification_mode` | `polisyos.ir.observation.contracts.IdentificationMode` | `yes` | `—` | `polisyos.ir.observation.contracts.IdentificationMode` |
| `notes` | `list[str]` | `no` | `—` | — |
| `target_contract` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` | `yes` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |

### `polisyos.ir.observation.bundles.ObservationToContractManifest` { #polisyos-ir-observation-bundles-observationtocontractmanifest }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:ObservationToContractManifest`, `polisyos.ir:ObservationToContractManifest`
- ABI snapshot: `observation_to_contract_manifest` / `schemas/snapshots/ir/observation_to_contract_manifest.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.ObservationContractArtifact`, `polisyos.ir.observation.bundles.ObservationContractRoute`
- Summary: Index of compiled observation artifacts and their contract routes.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[observation_to_contract_manifest.json]` | `no` | `'observation_to_contract_manifest.json'` | — |
| `artifacts` | `list[polisyos.ir.observation.bundles.ObservationContractArtifact]` | `no` | `—` | `polisyos.ir.observation.bundles.ObservationContractArtifact` |
| `routes` | `list[polisyos.ir.observation.bundles.ObservationContractRoute]` | `yes` | `—` | `polisyos.ir.observation.bundles.ObservationContractRoute` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.bundles.PanelEconometricBundleManifest` { #polisyos-ir-observation-bundles-paneleconometricbundlemanifest }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:PanelEconometricBundleManifest`, `polisyos.ir:PanelEconometricBundleManifest`
- ABI snapshot: `panel_econometric_bundle_manifest` / `schemas/snapshots/ir/panel_econometric_bundle_manifest.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.BundleLineageRef`, `polisyos.ir.observation.bundles.ContractCompatibilityTarget`, `polisyos.ir.observation.bundles.RequiredColumnSpec`
- Summary: Describe panel-econometric tables consumed by fixed-effects/IV estimators.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[panel_econometric_bundle_v1.parquet]` | `no` | `'panel_econometric_bundle_v1.parquet'` | — |
| `contract_payload` | `dict[str, Any]` | `no` | `—` | — |
| `contract_target` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` | `yes` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |
| `lineage` | `list[polisyos.ir.observation.bundles.BundleLineageRef]` | `no` | `—` | `polisyos.ir.observation.bundles.BundleLineageRef` |
| `required_columns` | `list[polisyos.ir.observation.bundles.RequiredColumnSpec]` | `yes` | `—` | `polisyos.ir.observation.bundles.RequiredColumnSpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `table_rows` | `list[dict[str, Any]]` | `no` | `—` | — |

### `polisyos.ir.observation.bundles.ProxyChannelSpec` { #polisyos-ir-observation-bundles-proxychannelspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:ProxyChannelSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.ContractCompatibilityTarget`, `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: Proxy-identification contract for one latent measurement pathway.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `family` | `polisyos.ir.observation.contracts.ObservationFamily` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `latent_variable` | `str` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `outcome_variable` | `str | NoneType` | `no` | `—` | — |
| `proxy_variable` | `str` | `yes` | `—` | — |
| `target_contract` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` | `yes` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |
| `treatment_variable` | `str | NoneType` | `no` | `—` | — |
| `verification_method` | `str` | `no` | `'identify_with_proxy'` | — |

### `polisyos.ir.observation.bundles.ProxyIdentificationBundle` { #polisyos-ir-observation-bundles-proxyidentificationbundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:ProxyIdentificationBundle`, `polisyos.ir:ProxyIdentificationBundle`
- ABI snapshot: `proxy_identification_bundle` / `schemas/snapshots/ir/proxy_identification_bundle.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.ContractCompatibilityTarget`, `polisyos.ir.observation.bundles.ProxyChannelSpec`
- Summary: Package proxy-identification channels and the compiler payload they target.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[proxy_identification_bundle_v1.json]` | `no` | `'proxy_identification_bundle_v1.json'` | — |
| `contract_payload` | `dict[str, Any]` | `no` | `—` | — |
| `contract_target` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` | `yes` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |
| `proxy_channels` | `list[polisyos.ir.observation.bundles.ProxyChannelSpec]` | `yes` | `—` | `polisyos.ir.observation.bundles.ProxyChannelSpec` |
| `proxy_map` | `dict[str, str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.bundles.RequiredArraySpec` { #polisyos-ir-observation-bundles-requiredarrayspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:RequiredArraySpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Manifest entry describing a required dense array payload.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `axes` | `list[str]` | `yes` | `—` | — |
| `description` | `str | NoneType` | `no` | `—` | — |
| `dtype` | `str | NoneType` | `no` | `—` | — |
| `name` | `str` | `yes` | `—` | — |
| `required` | `bool` | `no` | `True` | — |

### `polisyos.ir.observation.bundles.RequiredColumnSpec` { #polisyos-ir-observation-bundles-requiredcolumnspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:RequiredColumnSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Manifest entry describing a required tabular column.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `description` | `str | NoneType` | `no` | `—` | — |
| `dtype` | `str | NoneType` | `no` | `—` | — |
| `name` | `str` | `yes` | `—` | — |
| `nullable` | `bool` | `no` | `False` | — |

### `polisyos.ir.observation.bundles.SobolDiagnosticsBundle` { #polisyos-ir-observation-bundles-soboldiagnosticsbundle }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:SobolDiagnosticsBundle`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Persist Sobol indices and target/specification axes for sensitivity diagnostics.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[sobol_diagnostics_bundle_v1.json]` | `no` | `'sobol_diagnostics_bundle_v1.json'` | — |
| `first_order_indices` | `list[list[float]]` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `source_combination_ids` | `list[str]` | `yes` | `—` | — |
| `target_names` | `list[str]` | `yes` | `—` | — |
| `variance` | `list[float]` | `yes` | `—` | — |

### `polisyos.ir.observation.bundles.SpecificationCurveBundle` { #polisyos-ir-observation-bundles-specificationcurvebundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:SpecificationCurveBundle`, `polisyos.ir:SpecificationCurveBundle`
- ABI snapshot: `specification_curve_bundle` / `schemas/snapshots/ir/specification_curve_bundle.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.SpecificationCurveSource`
- Summary: Persist source combinations and estimates for specification-curve analysis.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[specification_curve_input_v1.json]` | `no` | `'specification_curve_input_v1.json'` | — |
| `contract_payload` | `dict[str, Any]` | `no` | `—` | — |
| `estimates` | `list[float]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `source_specifications` | `list[polisyos.ir.observation.bundles.SpecificationCurveSource]` | `yes` | `—` | `polisyos.ir.observation.bundles.SpecificationCurveSource` |
| `specification_ids` | `list[str]` | `no` | `—` | — |
| `standard_errors` | `list[float]` | `no` | `—` | — |

### `polisyos.ir.observation.bundles.SpecificationCurveDiagnosticsBundle` { #polisyos-ir-observation-bundles-specificationcurvediagnosticsbundle }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:SpecificationCurveDiagnosticsBundle`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Persist sorted estimates and stability metrics for specification-curve review.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[specification_curve_diagnostics_v1.json]` | `no` | `'specification_curve_diagnostics_v1.json'` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `share_significant` | `float` | `yes` | `—` | — |
| `sign_consistency` | `float` | `yes` | `—` | — |
| `sorted_estimates` | `list[float]` | `yes` | `—` | — |
| `specification_ids` | `list[str]` | `yes` | `—` | — |

### `polisyos.ir.observation.bundles.SpecificationCurveSource` { #polisyos-ir-observation-bundles-specificationcurvesource }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:SpecificationCurveSource`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: One source-combination entry inside a specification-curve bundle.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `included_families` | `list[polisyos.ir.observation.contracts.ObservationFamily]` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `notes` | `list[str]` | `no` | `—` | — |
| `sensitivity_axes` | `list[str]` | `no` | `—` | — |
| `source_combination_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.bundles.StrategicResponseSpec` { #polisyos-ir-observation-bundles-strategicresponsespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:StrategicResponseSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.StrategicResponseChannel`
- Summary: Expectation that a policy intervention may trigger strategic adaptation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `channels` | `list[polisyos.ir.observation.contracts.StrategicResponseChannel]` | `yes` | `—` | `polisyos.ir.observation.contracts.StrategicResponseChannel` |
| `hook_fqn` | `str` | `no` | `'polisyos.foundry.methods.catalog.causal.strategic.evaluate_strategic_hook'` | — |
| `intervention_kind` | `str` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `strategic_response_expected` | `bool` | `no` | `True` | — |

### `polisyos.ir.observation.bundles.StrategicResponseSpecsBundle` { #polisyos-ir-observation-bundles-strategicresponsespecsbundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:StrategicResponseSpecsBundle`, `polisyos.ir:StrategicResponseSpecsBundle`
- ABI snapshot: `strategic_response_specs_bundle` / `schemas/snapshots/ir/strategic_response_specs_bundle.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.StrategicResponseSpec`
- Summary: Bundle intervention-level strategic-response expectations for readiness checks.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[strategic_response_specs_v1.json]` | `no` | `'strategic_response_specs_v1.json'` | — |
| `expectations` | `list[polisyos.ir.observation.bundles.StrategicResponseSpec]` | `yes` | `—` | `polisyos.ir.observation.bundles.StrategicResponseSpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.bundles.SurvivalDataBundleManifest` { #polisyos-ir-observation-bundles-survivaldatabundlemanifest }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:SurvivalDataBundleManifest`, `polisyos.ir:SurvivalDataBundleManifest`
- ABI snapshot: `survival_data_bundle_manifest` / `schemas/snapshots/ir/survival_data_bundle_manifest.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.BundleLineageRef`, `polisyos.ir.observation.bundles.ContractCompatibilityTarget`, `polisyos.ir.observation.bundles.RequiredColumnSpec`
- Summary: Describe survival-analysis tables consumed by hazard or duration models.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[survival_data_bundle_v1.parquet]` | `no` | `'survival_data_bundle_v1.parquet'` | — |
| `contract_payload` | `dict[str, Any]` | `no` | `—` | — |
| `contract_target` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` | `yes` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |
| `lineage` | `list[polisyos.ir.observation.bundles.BundleLineageRef]` | `no` | `—` | `polisyos.ir.observation.bundles.BundleLineageRef` |
| `required_columns` | `list[polisyos.ir.observation.bundles.RequiredColumnSpec]` | `yes` | `—` | `polisyos.ir.observation.bundles.RequiredColumnSpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `table_rows` | `list[dict[str, Any]]` | `no` | `—` | — |

### `polisyos.ir.observation.bundles.SurvivalHazardBundle` { #polisyos-ir-observation-bundles-survivalhazardbundle }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:SurvivalHazardBundle`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.BundleLineageRef`, `polisyos.ir.observation.bundles.ContractCompatibilityTarget`, `polisyos.ir.observation.bundles.RequiredColumnSpec`
- Summary: Describe hazard-model tables and payloads for survival estimators.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[survival_hazard_bundle_v1.parquet]` | `no` | `'survival_hazard_bundle_v1.parquet'` | — |
| `contract_payload` | `dict[str, Any]` | `no` | `—` | — |
| `contract_target` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` | `yes` | `—` | `polisyos.ir.observation.bundles.ContractCompatibilityTarget` |
| `lineage` | `list[polisyos.ir.observation.bundles.BundleLineageRef]` | `no` | `—` | `polisyos.ir.observation.bundles.BundleLineageRef` |
| `required_columns` | `list[polisyos.ir.observation.bundles.RequiredColumnSpec]` | `yes` | `—` | `polisyos.ir.observation.bundles.RequiredColumnSpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `table_rows` | `list[dict[str, Any]]` | `no` | `—` | — |

### `polisyos.ir.observation.bundles.TransportabilityCheckBundle` { #polisyos-ir-observation-bundles-transportabilitycheckbundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:TransportabilityCheckBundle`, `polisyos.ir:TransportabilityCheckBundle`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.TransportabilityCheckSpec`
- Summary: Bundle of transportability checks queued for readiness validation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_name` | `Literal[transportability_check_bundle_v1.json]` | `no` | `'transportability_check_bundle_v1.json'` | — |
| `checks` | `list[polisyos.ir.observation.bundles.TransportabilityCheckSpec]` | `yes` | `—` | `polisyos.ir.observation.bundles.TransportabilityCheckSpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.bundles.TransportabilityCheckSpec` { #polisyos-ir-observation-bundles-transportabilitycheckspec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:TransportabilityCheckSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.context.ContextProfile`, `polisyos.ir.analytics.transportability.SNode`, `polisyos.ir.observation.contracts.ObservationFamily`, `polisyos.ir.types.TimeFrequency`
- Summary: Request to assess transportability between two regimes or contexts.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `check_id` | `str` | `yes` | `—` | — |
| `explicit_s_nodes` | `list[polisyos.ir.analytics.transportability.SNode]` | `no` | `—` | `polisyos.ir.analytics.transportability.SNode` |
| `family` | `polisyos.ir.observation.contracts.ObservationFamily | NoneType` | `no` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `notes` | `list[str]` | `no` | `—` | — |
| `outcome` | `str` | `yes` | `—` | — |
| `period_end` | `date | NoneType` | `no` | `—` | — |
| `period_start` | `date | NoneType` | `no` | `—` | — |
| `schema_regime_id` | `str | NoneType` | `no` | `—` | — |
| `source_context` | `polisyos.ir.analytics.context.ContextProfile | NoneType` | `no` | `—` | `polisyos.ir.analytics.context.ContextProfile` |
| `source_regime_id` | `str | NoneType` | `no` | `—` | — |
| `target_context` | `polisyos.ir.analytics.context.ContextProfile | NoneType` | `no` | `—` | `polisyos.ir.analytics.context.ContextProfile` |
| `target_regime_id` | `str | NoneType` | `no` | `—` | — |
| `time_grain` | `polisyos.ir.types.TimeFrequency | NoneType` | `no` | `—` | `polisyos.ir.types.TimeFrequency` |
| `treatment` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.causal_execution.BoundsEstimationEntry` { #polisyos-ir-observation-causal-execution-boundsestimationentry }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:BoundsEstimationEntry`, `polisyos.ir:BoundsEstimationEntry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.ObservationFamily`, `polisyos.ir.refs.BoundsBundleRef`
- Summary: Store the outcome of one bounds-estimation task.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bounds_bundle_ref` | `polisyos.ir.refs.BoundsBundleRef | NoneType` | `no` | `—` | `polisyos.ir.refs.BoundsBundleRef` |
| `family` | `polisyos.ir.observation.contracts.ObservationFamily` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `informative` | `bool` | `no` | `False` | — |
| `interval` | `tuple[float, float] | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `status` | `Literal[ok, blocked]` | `yes` | `—` | — |
| `task_id` | `str` | `yes` | `—` | — |
| `warnings` | `list[str]` | `no` | `—` | — |
| `width` | `float | NoneType` | `no` | `—` | — |

### `polisyos.ir.observation.causal_execution.BoundsEstimationTask` { #polisyos-ir-observation-causal-execution-boundsestimationtask }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:BoundsEstimationTask`, `polisyos.ir:BoundsEstimationTask`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.bundles.BoundsEstimationBundle`, `polisyos.ir.observation.contract_compilers.BoundsEstimationInput`
- Summary: Package one bounds-estimation run assembled from observation contracts.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bounds_input` | `polisyos.ir.observation.contract_compilers.BoundsEstimationInput` | `yes` | `—` | `polisyos.ir.observation.contract_compilers.BoundsEstimationInput` |
| `bundle` | `polisyos.ir.observation.bundles.BoundsEstimationBundle` | `yes` | `—` | `polisyos.ir.observation.bundles.BoundsEstimationBundle` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `params` | `dict[str, Any]` | `no` | `—` | — |
| `task_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.causal_execution.CausalExecutionBundle` { #polisyos-ir-observation-causal-execution-causalexecutionbundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:CausalExecutionBundle`, `polisyos.ir:CausalExecutionBundle`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.causal_execution.BoundsEstimationEntry`, `polisyos.ir.observation.causal_execution.TemporalDTRExecutionEntry`
- Summary: Persist bounds and sequential-treatment outputs with status and lineage metadata.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bounds_results` | `list[polisyos.ir.observation.causal_execution.BoundsEstimationEntry]` | `no` | `—` | `polisyos.ir.observation.causal_execution.BoundsEstimationEntry` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `temporal_results` | `list[polisyos.ir.observation.causal_execution.TemporalDTRExecutionEntry]` | `no` | `—` | `polisyos.ir.observation.causal_execution.TemporalDTRExecutionEntry` |

### `polisyos.ir.observation.causal_execution.TemporalDTRExecutionEntry` { #polisyos-ir-observation-causal-execution-temporaldtrexecutionentry }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:TemporalDTRExecutionEntry`, `polisyos.ir:TemporalDTRExecutionEntry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.refs.DynamicTreatmentRegimeRef`, `polisyos.ir.refs.EffectTrajectoryBundleRef`
- Summary: Store one dynamic-treatment execution result and its artifact refs.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `dtr_method` | `Literal[q_learning, a_learning, owl, dr_dtr]` | `yes` | `—` | — |
| `dynamic_intervention_id` | `str | NoneType` | `no` | `—` | — |
| `dynamic_treatment_regime_ref` | `polisyos.ir.refs.DynamicTreatmentRegimeRef | NoneType` | `no` | `—` | `polisyos.ir.refs.DynamicTreatmentRegimeRef` |
| `effect_trajectory_bundle_ref` | `polisyos.ir.refs.EffectTrajectoryBundleRef | NoneType` | `no` | `—` | `polisyos.ir.refs.EffectTrajectoryBundleRef` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `sequence_id` | `str | NoneType` | `no` | `—` | — |
| `status` | `Literal[ok, blocked]` | `yes` | `—` | — |
| `task_id` | `str` | `yes` | `—` | — |
| `value_estimate` | `float | NoneType` | `no` | `—` | — |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.observation.causal_execution.TemporalDTRTask` { #polisyos-ir-observation-causal-execution-temporaldtrtask }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:TemporalDTRTask`, `polisyos.ir:TemporalDTRTask`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.dynamic_regime.ContinuousTimeQuery`, `polisyos.ir.analytics.dynamic_regime.TemporalInterventionTrajectory`, `polisyos.ir.governance.policy_spec.TemporalInterventionSequence`, `polisyos.ir.observation.bundles.DTRTreatmentSequenceBundleManifest`, `polisyos.ir.observation.contracts.IdentificationMode`, `polisyos.ir.observation.contracts.StrategicResponseChannel`
- Summary: Executable dynamic treatment regime task for sequential interventions.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bundle_manifest` | `polisyos.ir.observation.bundles.DTRTreatmentSequenceBundleManifest | NoneType` | `no` | `—` | `polisyos.ir.observation.bundles.DTRTreatmentSequenceBundleManifest` |
| `compiled_interventions` | `Any | NoneType` | `no` | `—` | — |
| `continuous_time_query` | `polisyos.ir.analytics.dynamic_regime.ContinuousTimeQuery | NoneType` | `no` | `—` | `polisyos.ir.analytics.dynamic_regime.ContinuousTimeQuery` |
| `covariate_names` | `list[str]` | `no` | `—` | — |
| `dtr_method` | `Literal[q_learning, a_learning, owl, dr_dtr]` | `no` | `'q_learning'` | — |
| `dynamic_intervention_id` | `str | NoneType` | `no` | `—` | — |
| `dynamic_treatment_data` | `DynamicTreatmentData | NoneType` | `no` | `—` | — |
| `identification_mode` | `polisyos.ir.observation.contracts.IdentificationMode` | `no` | `<IdentificationMode.SEQUENTIAL: 'sequential'>` | `polisyos.ir.observation.contracts.IdentificationMode` |
| `intervention_trajectory` | `polisyos.ir.analytics.dynamic_regime.TemporalInterventionTrajectory | NoneType` | `no` | `—` | `polisyos.ir.analytics.dynamic_regime.TemporalInterventionTrajectory` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `n_units` | `int` | `no` | `10` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `outcome` | `list[float] | NoneType` | `no` | `—` | — |
| `params` | `dict[str, Any]` | `no` | `—` | — |
| `sequence_id` | `str | NoneType` | `no` | `—` | — |
| `steps` | `list[dict[str, Any]]` | `no` | `—` | — |
| `strategic_response_expected` | `bool` | `no` | `False` | — |
| `task_id` | `str` | `yes` | `—` | — |
| `temporal_sequence` | `polisyos.ir.governance.policy_spec.TemporalInterventionSequence | NoneType` | `no` | `—` | `polisyos.ir.governance.policy_spec.TemporalInterventionSequence` |
| `time_ids` | `list[Any]` | `no` | `—` | — |
| `transmission_channels` | `list[polisyos.ir.observation.contracts.StrategicResponseChannel]` | `no` | `—` | `polisyos.ir.observation.contracts.StrategicResponseChannel` |

### `polisyos.ir.observation.causal_readiness.CausalReadinessBundle` { #polisyos-ir-observation-causal-readiness-causalreadinessbundle }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:CausalReadinessBundle`, `polisyos.ir:CausalReadinessBundle`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.causal_readiness.CounterfactualCheckEntry`, `polisyos.ir.observation.causal_readiness.InterferenceReadinessEntry`, `polisyos.ir.observation.causal_readiness.ProxyIdentificationEntry`, `polisyos.ir.observation.causal_readiness.StrategicResponseEntry`, `polisyos.ir.observation.causal_readiness.TransportabilityCheckEntry`
- Summary: Persist the complete pre-execution readiness ledger for causal runners.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `counterfactual_results` | `list[polisyos.ir.observation.causal_readiness.CounterfactualCheckEntry]` | `no` | `—` | `polisyos.ir.observation.causal_readiness.CounterfactualCheckEntry` |
| `interference_specs` | `list[polisyos.ir.observation.causal_readiness.InterferenceReadinessEntry]` | `no` | `—` | `polisyos.ir.observation.causal_readiness.InterferenceReadinessEntry` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `proxy_results` | `list[polisyos.ir.observation.causal_readiness.ProxyIdentificationEntry]` | `no` | `—` | `polisyos.ir.observation.causal_readiness.ProxyIdentificationEntry` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `strategic_results` | `list[polisyos.ir.observation.causal_readiness.StrategicResponseEntry]` | `no` | `—` | `polisyos.ir.observation.causal_readiness.StrategicResponseEntry` |
| `transport_results` | `list[polisyos.ir.observation.causal_readiness.TransportabilityCheckEntry]` | `no` | `—` | `polisyos.ir.observation.causal_readiness.TransportabilityCheckEntry` |

### `polisyos.ir.observation.causal_readiness.CounterfactualCheckEntry` { #polisyos-ir-observation-causal-readiness-counterfactualcheckentry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:CounterfactualCheckEntry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: Store counterfactual query preflight metadata and identification status.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `algorithm_version` | `str` | `no` | `''` | — |
| `estimand_ast` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `family` | `polisyos.ir.observation.contracts.ObservationFamily | NoneType` | `no` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `hedge_certificate` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `normalized_query` | `str` | `no` | `''` | — |
| `normalized_reason` | `str | NoneType` | `no` | `—` | — |
| `query_id` | `str` | `yes` | `—` | — |
| `query_kind` | `str` | `no` | `'generic'` | — |
| `status` | `str` | `yes` | `—` | — |
| `trace` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.observation.causal_readiness.InterferenceReadinessEntry` { #polisyos-ir-observation-causal-readiness-interferencereadinessentry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:InterferenceReadinessEntry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: Declare whether an interference-aware loss target can be materialized.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `family` | `polisyos.ir.observation.contracts.ObservationFamily` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `predicted_metric_path` | `str` | `yes` | `—` | — |
| `ready` | `bool` | `no` | `True` | — |
| `spec_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.causal_readiness.ProxyIdentificationEntry` { #polisyos-ir-observation-causal-readiness-proxyidentificationentry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:ProxyIdentificationEntry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: Record whether a proxy pathway is identified or requires oracle support.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `estimand_ast` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `family` | `polisyos.ir.observation.contracts.ObservationFamily` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `latent_variable` | `str` | `yes` | `—` | — |
| `measurement_model` | `str` | `no` | `'unknown'` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `normalized_reason` | `str | NoneType` | `no` | `—` | — |
| `proof_steps` | `list[dict[str, Any]]` | `no` | `—` | — |
| `proxy_variable` | `str` | `yes` | `—` | — |
| `status` | `Literal[identified, oracle_needed]` | `yes` | `—` | — |
| `trace` | `list[str]` | `no` | `—` | — |
| `verification_method` | `str` | `no` | `'identify_with_proxy'` | — |

### `polisyos.ir.observation.causal_readiness.StrategicResponseEntry` { #polisyos-ir-observation-causal-readiness-strategicresponseentry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:StrategicResponseEntry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.StrategicResponseChannel`, `polisyos.ir.refs.ArtifactRefModel`
- Summary: Summarize whether a strategic-response channel is ready or blocked.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `blocked_reason` | `str | NoneType` | `no` | `—` | — |
| `channel` | `polisyos.ir.observation.contracts.StrategicResponseChannel` | `yes` | `—` | `polisyos.ir.observation.contracts.StrategicResponseChannel` |
| `fallback_mode` | `str` | `no` | `''` | — |
| `intervention_kind` | `str | NoneType` | `no` | `—` | — |
| `performative_shift` | `float | NoneType` | `no` | `—` | — |
| `status` | `Literal[ready, blocked]` | `yes` | `—` | — |
| `strategic_response_bundle_ref` | `polisyos.ir.refs.ArtifactRefModel | NoneType` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `strategic_scm_ref` | `polisyos.ir.refs.ArtifactRefModel | NoneType` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `summary` | `dict[str, Any]` | `no` | `—` | — |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.observation.causal_readiness.TransportabilityCheckEntry` { #polisyos-ir-observation-causal-readiness-transportabilitycheckentry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:TransportabilityCheckEntry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.ObservationFamily`, `polisyos.ir.refs.ArtifactRefModel`
- Summary: Store one transportability preflight result and its blocking S-nodes.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `blocking_s_nodes` | `list[str]` | `no` | `—` | — |
| `check_id` | `str` | `yes` | `—` | — |
| `cross_regime` | `bool` | `no` | `False` | — |
| `family` | `polisyos.ir.observation.contracts.ObservationFamily | NoneType` | `no` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `identification_engine` | `str` | `no` | `''` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `normalized_reason` | `str | NoneType` | `no` | `—` | — |
| `result_ref` | `polisyos.ir.refs.ArtifactRefModel | NoneType` | `no` | `—` | `polisyos.ir.refs.ArtifactRefModel` |
| `status` | `Literal[identified, partially_identified, blocked]` | `yes` | `—` | — |
| `trace` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.observation.compiler.CalibrationSplitLabel` { #polisyos-ir-observation-compiler-calibrationsplitlabel }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:CalibrationSplitLabel`, `polisyos.ir:CalibrationSplitLabel`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Named partition used when building measurement-aware calibration targets.

| Enum values |
|-------------|
| `train` |
| `validation` |
| `test` |
| `holdout` |

### `polisyos.ir.observation.compiler.CalibrationSplitPlan` { #polisyos-ir-observation-compiler-calibrationsplitplan }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:CalibrationSplitPlan`, `polisyos.ir:CalibrationSplitPlan`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.compiler.CalibrationSplitWindow`
- Summary: Full partition plan for train, validation, test, and holdout periods.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `windows` | `list[polisyos.ir.observation.compiler.CalibrationSplitWindow]` | `no` | `—` | `polisyos.ir.observation.compiler.CalibrationSplitWindow` |

### `polisyos.ir.observation.compiler.CalibrationSplitWindow` { #polisyos-ir-observation-compiler-calibrationsplitwindow }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:CalibrationSplitWindow`, `polisyos.ir:CalibrationSplitWindow`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.compiler.CalibrationSplitLabel`
- Summary: Date window assigned to one calibration split label.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `end_date` | `date | NoneType` | `no` | `—` | — |
| `label` | `polisyos.ir.observation.compiler.CalibrationSplitLabel` | `yes` | `—` | `polisyos.ir.observation.compiler.CalibrationSplitLabel` |
| `reason` | `str` | `no` | `''` | — |
| `start_date` | `date | NoneType` | `no` | `—` | — |

### `polisyos.ir.observation.compiler.CalibrationSplitter` { #polisyos-ir-observation-compiler-calibrationsplitter }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:CalibrationSplitter`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Assign observation periods to calibration splits with boundary awareness.

### `polisyos.ir.observation.compiler.CalibrationTargetBundleCompiler` { #polisyos-ir-observation-compiler-calibrationtargetbundlecompiler }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:CalibrationTargetBundleCompiler`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compiler from observation panels to measurement-aware calibration bundles.

### `polisyos.ir.observation.compiler.NegativeControlGenerator` { #polisyos-ir-observation-compiler-negativecontrolgenerator }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:NegativeControlGenerator`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Generator for placebo targets derived from a calibration target bundle.

### `polisyos.ir.observation.compiler.NegativeControlSpec` { #polisyos-ir-observation-compiler-negativecontrolspec }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:NegativeControlSpec`, `polisyos.ir:NegativeControlSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Specification describing a generated placebo target for falsification.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `notes` | `list[str]` | `no` | `—` | — |
| `placebo_target_id` | `str` | `yes` | `—` | — |
| `placebo_time_axis` | `tuple[str]` | `no` | `—` | — |
| `shift_periods` | `int` | `yes` | `—` | — |
| `source_target_id` | `str` | `yes` | `—` | — |
| `source_time_axis` | `tuple[str]` | `no` | `—` | — |

### `polisyos.ir.observation.contract_compilers.BoundsEstimationCompileSpec` { #polisyos-ir-observation-contract-compilers-boundsestimationcompilespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:BoundsEstimationCompileSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Select outcome/treatment and optional IV/selection/proxy channels for bounds input.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `instrument_metric_id` | `str | NoneType` | `no` | `—` | — |
| `miv_proxy_metric_id` | `str | NoneType` | `no` | `—` | — |
| `outcome_metric_id` | `str` | `yes` | `—` | — |
| `selected_metric_id` | `str | NoneType` | `no` | `—` | — |
| `spec_id` | `str` | `yes` | `—` | — |
| `treatment_metric_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.BoundsEstimationInput` { #polisyos-ir-observation-contract-compilers-boundsestimationinput }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:BoundsEstimationInput`, `polisyos.ir:BoundsEstimationInput`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Dense payload consumed by partial-identification and bounds estimators.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `instrument` | `list[float] | NoneType` | `no` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `miv_proxy` | `list[float] | NoneType` | `no` | `—` | — |
| `outcome` | `list[float]` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `selected` | `list[float] | NoneType` | `no` | `—` | — |
| `treatment` | `list[float]` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.BoundsInputCompiler` { #polisyos-ir-observation-contract-compilers-boundsinputcompiler }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:BoundsInputCompiler`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compile a panel slice into dense arrays for partial-identification estimators.

### `polisyos.ir.observation.contract_compilers.CompiledObservationArtifact` { #polisyos-ir-observation-contract-compilers-compiledobservationartifact }

- Kind: `dataclass`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:CompiledObservationArtifact`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Bundle one compiler output contract together with its persisted manifest.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `compiler_id` | `str` | `yes` | `—` | — |
| `artifact_key` | `str` | `yes` | `—` | — |
| `contract` | `Any` | `yes` | `—` | — |
| `bundle` | `KernelModel` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.DynamicTreatmentCompileSpec` { #polisyos-ir-observation-contract-compilers-dynamictreatmentcompilespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:DynamicTreatmentCompileSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Select metrics required to compile sequential treatment trajectories.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `behavior_policy_prob_metric_id` | `str | NoneType` | `no` | `—` | — |
| `covariate_metric_ids` | `list[str]` | `yes` | `—` | — |
| `outcome_metric_id` | `str` | `yes` | `—` | — |
| `spec_id` | `str` | `yes` | `—` | — |
| `treatment_metric_id` | `str` | `yes` | `—` | — |
| `treatment_threshold` | `float` | `no` | `0.5` | — |

### `polisyos.ir.observation.contract_compilers.DynamicTreatmentCompiler` { #polisyos-ir-observation-contract-compilers-dynamictreatmentcompiler }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:DynamicTreatmentCompiler`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compile sequential treatment trajectories for dynamic-regime execution.

### `polisyos.ir.observation.contract_compilers.FirmEventRecord` { #polisyos-ir-observation-contract-compilers-firmeventrecord }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:FirmEventRecord`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Store one firm entry/exit or censoring event used by survival compilers.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `censor_date` | `date | NoneType` | `no` | `—` | — |
| `entry_date` | `date` | `yes` | `—` | — |
| `event_type` | `str` | `no` | `'exit'` | — |
| `exit_date` | `date | NoneType` | `no` | `—` | — |
| `firm_id` | `str` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |

### `polisyos.ir.observation.contract_compilers.FirmEvents` { #polisyos-ir-observation-contract-compilers-firmevents }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:FirmEvents`, `polisyos.ir:FirmEvents`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contract_compilers.FirmEventRecord`
- Summary: Observed firm lifecycle events used by survival compilers.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `event_set_id` | `str` | `yes` | `—` | — |
| `records` | `list[polisyos.ir.observation.contract_compilers.FirmEventRecord]` | `yes` | `—` | `polisyos.ir.observation.contract_compilers.FirmEventRecord` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.contract_compilers.FirmPanelRow` { #polisyos-ir-observation-contract-compilers-firmpanelrow }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:FirmPanelRow`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Store one firm-period metric row for panel and econometric compilers.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `firm_id` | `str` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `metrics` | `dict[str, float]` | `no` | `—` | — |
| `period_end` | `date` | `yes` | `—` | — |
| `period_start` | `date` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.FirmPanels` { #polisyos-ir-observation-contract-compilers-firmpanels }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:FirmPanels`, `polisyos.ir:FirmPanels`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contract_compilers.FirmPanelRow`
- Summary: Panel of firm-level metrics aligned by period.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `panel_id` | `str` | `yes` | `—` | — |
| `rows` | `list[polisyos.ir.observation.contract_compilers.FirmPanelRow]` | `yes` | `—` | `polisyos.ir.observation.contract_compilers.FirmPanelRow` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.contract_compilers.GraphArtifacts` { #polisyos-ir-observation-contract-compilers-graphartifacts }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:GraphArtifacts`, `polisyos.ir:GraphArtifacts`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contract_compilers.GraphBipartiteEdge`, `polisyos.ir.observation.contract_compilers.GraphEdge`, `polisyos.ir.observation.contracts.MultiplexGraphLayerId`
- Summary: Canonical multiplex graph payload used by network-oriented compilers.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `str` | `yes` | `—` | — |
| `bipartite_edges` | `list[polisyos.ir.observation.contract_compilers.GraphBipartiteEdge]` | `no` | `—` | `polisyos.ir.observation.contract_compilers.GraphBipartiteEdge` |
| `cluster_ids` | `dict[str, int]` | `no` | `—` | — |
| `coordinates` | `dict[str, tuple[float]]` | `no` | `—` | — |
| `index_map` | `dict[str, int]` | `no` | `—` | — |
| `layer_edges` | `dict[polisyos.ir.observation.contracts.MultiplexGraphLayerId, list[polisyos.ir.observation.contract_compilers.GraphEdge]]` | `no` | `—` | `polisyos.ir.observation.contract_compilers.GraphEdge`, `polisyos.ir.observation.contracts.MultiplexGraphLayerId` |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `node_features` | `dict[str, dict[str, float]]` | `no` | `—` | — |
| `node_ids` | `list[str]` | `yes` | `—` | — |
| `node_states` | `dict[str, float]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.contract_compilers.GraphBipartiteEdge` { #polisyos-ir-observation-contract-compilers-graphbipartiteedge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:GraphBipartiteEdge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Represent one treatment-to-outcome edge for bipartite exposure graphs.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `outcome_node_id` | `str` | `yes` | `—` | — |
| `treatment_node_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.GraphEdge` { #polisyos-ir-observation-contract-compilers-graphedge }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:GraphEdge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Represent one directed weighted edge in a network contract payload.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `dst_id` | `str` | `yes` | `—` | — |
| `src_id` | `str` | `yes` | `—` | — |
| `weight` | `float` | `no` | `1.0` | — |

### `polisyos.ir.observation.contract_compilers.HistoricalValidationCompilation` { #polisyos-ir-observation-contract-compilers-historicalvalidationcompilation }

- Kind: `dataclass`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:HistoricalValidationCompilation`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Pair a generated backtest plan with the payload snapshot used to run it.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `plans` | `list[HistoricalValidationPlan]` | `yes` | `—` | — |
| `historical_payloads` | `dict[str, dict[str, Any]]` | `yes` | `—` | — |
| `bundle` | `BacktestPlanBundle` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.HistoricalValidationCompileSpec` { #polisyos-ir-observation-contract-compilers-historicalvalidationcompilespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:HistoricalValidationCompileSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Specify holdout horizons and metric ids for backtest-plan compilation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `historical_data_path` | `str | NoneType` | `no` | `—` | — |
| `historical_data_ref` | `str | NoneType` | `no` | `—` | — |
| `intervention_date` | `str` | `yes` | `—` | — |
| `jurisdiction` | `str` | `no` | `''` | — |
| `metric_ids` | `list[str]` | `yes` | `—` | — |
| `post_intervention_periods` | `int` | `yes` | `—` | — |
| `pre_intervention_periods` | `int` | `yes` | `—` | — |
| `prediction_source` | `PredictionSource` | `no` | `<PredictionSource.NAIVE: 'naive'>` | — |
| `spec_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.HistoricalValidationPlanCompiler` { #polisyos-ir-observation-contract-compilers-historicalvalidationplancompiler }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:HistoricalValidationPlanCompiler`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compile panel history into backtest plans for Scientist validation runners.

### `polisyos.ir.observation.contract_compilers.LeontiefIOCompileSpec` { #polisyos-ir-observation-contract-compilers-leontiefiocompilespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:LeontiefIOCompileSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Tag a region-sector panel compilation request for Leontief IO output.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `reference_period` | `date | NoneType` | `no` | `—` | — |
| `spec_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.LeontiefIOCompiler` { #polisyos-ir-observation-contract-compilers-leontiefiocompiler }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:LeontiefIOCompiler`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compile region-sector flow panels into Leontief IO bundles for downstream solvers.

### `polisyos.ir.observation.contract_compilers.LeontiefIOInput` { #polisyos-ir-observation-contract-compilers-leontiefioinput }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:LeontiefIOInput`, `polisyos.ir:LeontiefIOInput`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Carry dense IO tables and axis labels into Leontief bundle compilation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `final_demand` | `list[float]` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `region_index_map` | `dict[str, int]` | `no` | `—` | — |
| `regions` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `sector_index_map` | `dict[str, int]` | `no` | `—` | — |
| `sector_names` | `list[str]` | `yes` | `—` | — |
| `technical_coefficients` | `list[list[float]]` | `yes` | `—` | — |
| `value_added` | `list[float]` | `no` | `—` | — |

### `polisyos.ir.observation.contract_compilers.NetworkCausalCompileSpec` { #polisyos-ir-observation-contract-compilers-networkcausalcompilespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:NetworkCausalCompileSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.MultiplexGraphLayerId`
- Summary: Select outcome/treatment/covariate metrics for interference-aware network causal data.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `covariate_metric_ids` | `list[str]` | `no` | `—` | — |
| `outcome_metric_id` | `str` | `yes` | `—` | — |
| `reference_period` | `date | NoneType` | `no` | `—` | — |
| `spec_id` | `str` | `yes` | `—` | — |
| `structure_layer` | `polisyos.ir.observation.contracts.MultiplexGraphLayerId | NoneType` | `no` | `—` | `polisyos.ir.observation.contracts.MultiplexGraphLayerId` |
| `treatment_metric_id` | `str` | `yes` | `—` | — |
| `treatment_threshold` | `float` | `no` | `0.5` | — |

### `polisyos.ir.observation.contract_compilers.NetworkCausalDataCompiler` { #polisyos-ir-observation-contract-compilers-networkcausaldatacompiler }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:NetworkCausalDataCompiler`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compile a panel plus graph into ``NetworkCausalData`` for interference-aware estimators.

### `polisyos.ir.observation.contract_compilers.NetworkContractCompileSpec` { #polisyos-ir-observation-contract-compilers-networkcontractcompilespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:NetworkContractCompileSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.MultiplexGraphLayerId`
- Summary: Configure graph-layer ordering and dense/sparse materialization for network bundles.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `dense_max_bytes` | `int` | `no` | `32000000` | — |
| `layer_order` | `list[polisyos.ir.observation.contracts.MultiplexGraphLayerId]` | `no` | `—` | `polisyos.ir.observation.contracts.MultiplexGraphLayerId` |
| `low_rank_rank` | `int | NoneType` | `no` | `—` | — |
| `materialize_node_ids` | `list[str]` | `no` | `—` | — |
| `node_feature_names` | `list[str]` | `no` | `—` | — |
| `primary_layer` | `polisyos.ir.observation.contracts.MultiplexGraphLayerId | NoneType` | `no` | `—` | `polisyos.ir.observation.contracts.MultiplexGraphLayerId` |
| `spec_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.NetworkContractCompiler` { #polisyos-ir-observation-contract-compilers-networkcontractcompiler }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:NetworkContractCompiler`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compile ``GraphArtifacts`` into network-analysis bundles for Foundry methods.

### `polisyos.ir.observation.contract_compilers.ObservationCompilerContext` { #polisyos-ir-observation-contract-compilers-observationcompilercontext }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:ObservationCompilerContext`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Shared registries and utilities used by observation contract compilers.

### `polisyos.ir.observation.contract_compilers.ObservationContractCompileError` { #polisyos-ir-observation-contract-compilers-observationcontractcompileerror }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:ObservationContractCompileError`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Validation error raised while compiling observation contracts.

### `polisyos.ir.observation.contract_compilers.ObservationContractCompilerSuite` { #polisyos-ir-observation-contract-compilers-observationcontractcompilersuite }

- Kind: `class`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:ObservationContractCompilerSuite`, `polisyos.ir:ObservationContractCompilerSuite`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Facade that compiles observation evidence into all supported contracts.

### `polisyos.ir.observation.contract_compilers.ObservationContractLoadError` { #polisyos-ir-observation-contract-compilers-observationcontractloaderror }

- Kind: `class`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Load/parse error raised while reading serialized observation artifacts.

### `polisyos.ir.observation.contract_compilers.ObservationContractSuiteResult` { #polisyos-ir-observation-contract-compilers-observationcontractsuiteresult }

- Kind: `dataclass`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:ObservationContractSuiteResult`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Collect all compiled artifacts plus the observation-to-contract manifest.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifacts` | `dict[str, CompiledObservationArtifact]` | `yes` | `—` | — |
| `backtest` | `HistoricalValidationCompilation | None` | `yes` | `—` | — |
| `manifest` | `ObservationToContractManifest` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.PanelEconometricCompileSpec` { #polisyos-ir-observation-contract-compilers-paneleconometriccompilespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:PanelEconometricCompileSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Select dependent, exogenous, and instrument columns for econometric panels.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `dependent_metric_id` | `str` | `yes` | `—` | — |
| `exog_metric_ids` | `list[str]` | `yes` | `—` | — |
| `instrument_metric_ids` | `list[str]` | `no` | `—` | — |
| `spec_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.PanelEconometricCompiler` { #polisyos-ir-observation-contract-compilers-paneleconometriccompiler }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:PanelEconometricCompiler`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compile firm-period panels into econometric tables for regression or IV methods.

### `polisyos.ir.observation.contract_compilers.PanelObservationalCompileSpec` { #polisyos-ir-observation-contract-compilers-panelobservationalcompilespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:PanelObservationalCompileSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Select panel outcome/treatment/covariate metrics for causal panel compilation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `covariate_metric_ids` | `list[str]` | `no` | `—` | — |
| `explicit_time_treatment` | `int | NoneType` | `no` | `—` | — |
| `outcome_metric_id` | `str` | `yes` | `—` | — |
| `spec_id` | `str` | `yes` | `—` | — |
| `treatment_metric_id` | `str` | `yes` | `—` | — |
| `treatment_threshold` | `float` | `no` | `0.5` | — |

### `polisyos.ir.observation.contract_compilers.PanelObservationalCompiler` { #polisyos-ir-observation-contract-compilers-panelobservationalcompiler }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:PanelObservationalCompiler`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compile longitudinal panels into ``PanelObservationalData`` for causal panel methods.

### `polisyos.ir.observation.contract_compilers.ProxyMap` { #polisyos-ir-observation-contract-compilers-proxymap }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:ProxyMap`, `polisyos.ir:ProxyMap`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.causal_graph.CausalGraphModel`
- Summary: Mapping from latent treatment concepts to observed proxy variables.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `graph` | `polisyos.ir.analytics.causal_graph.CausalGraphModel | NoneType` | `no` | `—` | `polisyos.ir.analytics.causal_graph.CausalGraphModel` |
| `mapping` | `dict[str, str]` | `yes` | `—` | — |
| `measurement_model` | `Literal[known, estimated, unknown]` | `no` | `'unknown'` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `proxy_map_id` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.contract_compilers.ProxyMeasurementCompileSpec` { #polisyos-ir-observation-contract-compilers-proxymeasurementcompilespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:ProxyMeasurementCompileSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Declare proxy and validation metrics for latent-treatment measurement bundles.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `covariate_metric_ids` | `list[str]` | `no` | `—` | — |
| `error_rate_bound` | `float | NoneType` | `no` | `—` | — |
| `error_variance` | `float | NoneType` | `no` | `—` | — |
| `outcome_metric_id` | `str` | `yes` | `—` | — |
| `spec_id` | `str` | `yes` | `—` | — |
| `treatment_proxy_metric_id` | `str` | `yes` | `—` | — |
| `validation_proxy_metric_id` | `str | NoneType` | `no` | `—` | — |
| `validation_true_treatment_metric_id` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.observation.contract_compilers.ProxyMeasurementCompiler` { #polisyos-ir-observation-contract-compilers-proxymeasurementcompiler }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:ProxyMeasurementCompiler`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compile proxy-treatment evidence into proxy-identification bundles.

### `polisyos.ir.observation.contract_compilers.RegionSectorFlowRow` { #polisyos-ir-observation-contract-compilers-regionsectorflowrow }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:RegionSectorFlowRow`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Store one inter-region/inter-sector flow used to assemble Leontief matrices.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `final_demand` | `float` | `no` | `0.0` | — |
| `from_region_code` | `str` | `yes` | `—` | — |
| `from_sector_id` | `str` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `period_start` | `date | NoneType` | `no` | `—` | — |
| `technical_coefficient` | `float` | `no` | `0.0` | — |
| `to_region_code` | `str` | `yes` | `—` | — |
| `to_sector_id` | `str` | `yes` | `—` | — |
| `value_added` | `float` | `no` | `0.0` | — |

### `polisyos.ir.observation.contract_compilers.RegionSectorPanels` { #polisyos-ir-observation-contract-compilers-regionsectorpanels }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:RegionSectorPanels`, `polisyos.ir:RegionSectorPanels`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contract_compilers.RegionSectorFlowRow`
- Summary: Region-sector flow panel used to build Leontief IO bundles.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `panel_id` | `str` | `yes` | `—` | — |
| `rows` | `list[polisyos.ir.observation.contract_compilers.RegionSectorFlowRow]` | `yes` | `—` | `polisyos.ir.observation.contract_compilers.RegionSectorFlowRow` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.contract_compilers.SparseDenseBridge` { #polisyos-ir-observation-contract-compilers-sparsedensebridge }

- Kind: `class`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:SparseDenseBridge`, `polisyos.ir:SparseDenseBridge`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Utility for converting sparse multiplex graphs into dense tensors.

### `polisyos.ir.observation.contract_compilers.SpecificationCurveCompileSpec` { #polisyos-ir-observation-contract-compilers-specificationcurvecompilespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:SpecificationCurveCompileSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contract_compilers.SpecificationCurveSourceSpec`
- Summary: Wrap the source combinations used to compile specification-curve inputs.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `source_specifications` | `list[polisyos.ir.observation.contract_compilers.SpecificationCurveSourceSpec]` | `yes` | `—` | `polisyos.ir.observation.contract_compilers.SpecificationCurveSourceSpec` |
| `spec_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.SpecificationCurveCompiler` { #polisyos-ir-observation-contract-compilers-specificationcurvecompiler }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:SpecificationCurveCompiler`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compile robustness specifications into a specification-curve input bundle.

### `polisyos.ir.observation.contract_compilers.SpecificationCurveInput` { #polisyos-ir-observation-contract-compilers-specificationcurveinput }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:SpecificationCurveInput`, `polisyos.ir:SpecificationCurveInput`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Ordered estimates used to construct a specification curve.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `estimates` | `list[float]` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `specification_ids` | `list[str]` | `yes` | `—` | — |
| `standard_errors` | `list[float]` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.SpecificationCurveSourceSpec` { #polisyos-ir-observation-contract-compilers-specificationcurvesourcespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:SpecificationCurveSourceSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: Describe one source/family combination to include in a specification curve.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `included_families` | `list[polisyos.ir.observation.contracts.ObservationFamily]` | `no` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `included_metric_ids` | `list[str]` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `sensitivity_axes` | `list[str]` | `no` | `—` | — |
| `source_combination_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.SurveyMicroDataCompileSpec` { #polisyos-ir-observation-contract-compilers-surveymicrodatacompilespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:SurveyMicroDataCompileSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.EntityScope`
- Summary: Declare which household metrics become survey-microdata fields.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `entity_scope` | `polisyos.ir.observation.contracts.EntityScope` | `no` | `<EntityScope.HOUSEHOLD: 'household'>` | `polisyos.ir.observation.contracts.EntityScope` |
| `feature_metric_ids` | `list[str]` | `no` | `—` | — |
| `income_metric_id` | `str` | `yes` | `—` | — |
| `reference_period` | `date | NoneType` | `no` | `—` | — |
| `spec_id` | `str` | `yes` | `—` | — |
| `weight_metric_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.SurveyMicroDataCompiler` { #polisyos-ir-observation-contract-compilers-surveymicrodatacompiler }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:SurveyMicroDataCompiler`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compile household survey panels into ``SurveyMicroData`` and a microsim-ready bundle.

### `polisyos.ir.observation.contract_compilers.SurvivalCompileSpec` { #polisyos-ir-observation-contract-compilers-survivalcompilespec }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:SurvivalCompileSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Select feature metrics used to compile survival-analysis tables.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `feature_metric_ids` | `list[str]` | `yes` | `—` | — |
| `spec_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.contract_compilers.SurvivalDataCompiler` { #polisyos-ir-observation-contract-compilers-survivaldatacompiler }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:SurvivalDataCompiler`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compile firm event logs and baseline panels into survival-analysis bundles.

### `polisyos.ir.observation.contracts.EntityScope` { #polisyos-ir-observation-contracts-entityscope }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:EntityScope`, `polisyos.ir:EntityScope`
- ABI snapshot: `entity_scope` / `schemas/snapshots/ir/entity_scope.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Granularity at which an observation is measured.

| Enum values |
|-------------|
| `global` |
| `agent` |
| `firm` |
| `household` |
| `cell` |
| `household_cell` |
| `region` |
| `sector` |

### `polisyos.ir.observation.contracts.IdentificationMode` { #polisyos-ir-observation-contracts-identificationmode }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:IdentificationMode`, `polisyos.ir:IdentificationMode`
- ABI snapshot: `identification_mode` / `schemas/snapshots/ir/identification_mode.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Declare the causal identification contract assumed by records and bundles.

| Enum values |
|-------------|
| `point_identified` |
| `partially_identified` |
| `bounds_only` |
| `proxy_identified` |
| `interference_aware` |
| `sequential` |

### `polisyos.ir.observation.contracts.MultiplexGraphLayerId` { #polisyos-ir-observation-contracts-multiplexgraphlayerid }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:MultiplexGraphLayerId`, `polisyos.ir:MultiplexGraphLayerId`
- ABI snapshot: `multiplex_graph_layer_id` / `schemas/snapshots/ir/multiplex_graph_layer_id.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Select the graph layer consumed by network compilers and interference checks.

| Enum values |
|-------------|
| `budget` |
| `procurement` |
| `trade` |
| `distress` |
| `public_service` |

### `polisyos.ir.observation.contracts.ObservationFamily` { #polisyos-ir-observation-contracts-observationfamily }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:ObservationFamily`, `polisyos.ir:ObservationFamily`
- ABI snapshot: `observation_family` / `schemas/snapshots/ir/observation_family.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Classify raw evidence into stable observation families for routing.

| Enum values |
|-------------|
| `budget_flows` |
| `procurement_flows` |
| `macro_state` |
| `firm_fundamentals` |
| `trade_exposure` |
| `labor_market` |
| `household_distribution` |
| `distress_enforcement` |
| `spatial_raster_exogenous` |
| `public_service_domain_flows` |
| `education_human_capital_supply` |
| `construction_capital_formation` |
| `logistics_friction` |

### `polisyos.ir.observation.contracts.ObservationPanel` { #polisyos-ir-observation-contracts-observationpanel }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:ObservationPanel`, `polisyos.ir:ObservationPanel`
- ABI snapshot: `observation_panel` / `schemas/snapshots/ir/observation_panel.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.ObservationFamily`, `polisyos.ir.observation.contracts.ObservationRecord`, `polisyos.ir.types.TimeFrequency`
- Summary: Group homogeneous raw observations before compiler and readiness stages.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `family` | `polisyos.ir.observation.contracts.ObservationFamily` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `notes` | `list[str]` | `no` | `—` | — |
| `panel_id` | `str` | `yes` | `—` | — |
| `records` | `list[polisyos.ir.observation.contracts.ObservationRecord]` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationRecord` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `time_grain` | `polisyos.ir.types.TimeFrequency` | `yes` | `—` | `polisyos.ir.types.TimeFrequency` |

### `polisyos.ir.observation.contracts.ObservationRecord` { #polisyos-ir-observation-contracts-observationrecord }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:ObservationRecord`, `polisyos.ir:ObservationRecord`
- ABI snapshot: `observation_record` / `schemas/snapshots/ir/observation_record.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.EntityScope`, `polisyos.ir.observation.contracts.IdentificationMode`, `polisyos.ir.observation.contracts.ObservationFamily`, `polisyos.ir.observation.contracts.SourceConfidenceTier`, `polisyos.ir.types.TimeFrequency`
- Summary: Store one raw normalized measurement and the metadata needed for routing.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `cell_id` | `str | NoneType` | `no` | `—` | — |
| `censoring_mask` | `bool` | `no` | `False` | — |
| `coverage_estimate` | `float` | `yes` | `—` | — |
| `entity_id` | `str | NoneType` | `no` | `—` | — |
| `entity_scope` | `polisyos.ir.observation.contracts.EntityScope` | `yes` | `—` | `polisyos.ir.observation.contracts.EntityScope` |
| `family` | `polisyos.ir.observation.contracts.ObservationFamily` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `identification_mode` | `polisyos.ir.observation.contracts.IdentificationMode` | `yes` | `—` | `polisyos.ir.observation.contracts.IdentificationMode` |
| `lag_days_estimate` | `int` | `no` | `0` | — |
| `measurement_bias_flag` | `bool` | `no` | `False` | — |
| `metric_id` | `str` | `yes` | `—` | — |
| `notes_json` | `dict[str, Any]` | `no` | `—` | — |
| `observation_id` | `str` | `yes` | `—` | — |
| `observed_value` | `float` | `yes` | `—` | — |
| `period_end` | `date` | `yes` | `—` | — |
| `period_start` | `date` | `yes` | `—` | — |
| `proxy_source_id` | `str | NoneType` | `no` | `—` | — |
| `regime_id` | `str` | `yes` | `—` | — |
| `region_code` | `str | NoneType` | `no` | `—` | — |
| `schema_regime_id` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `sector_id` | `str | NoneType` | `no` | `—` | — |
| `shock_mask` | `bool` | `no` | `False` | — |
| `source_confidence_tier` | `polisyos.ir.observation.contracts.SourceConfidenceTier` | `no` | `<SourceConfidenceTier.VALIDATED: 'validated'>` | `polisyos.ir.observation.contracts.SourceConfidenceTier` |
| `source_id` | `str` | `yes` | `—` | — |
| `source_version` | `str` | `yes` | `—` | — |
| `time_grain` | `polisyos.ir.types.TimeFrequency` | `yes` | `—` | `polisyos.ir.types.TimeFrequency` |
| `trust_weight` | `float` | `yes` | `—` | — |
| `unit` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.contracts.SourceConfidenceTier` { #polisyos-ir-observation-contracts-sourceconfidencetier }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:SourceConfidenceTier`, `polisyos.ir:SourceConfidenceTier`
- ABI snapshot: `source_confidence_tier` / `schemas/snapshots/ir/source_confidence_tier.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Declare the raw provenance tier consumed by measurement trust normalization.

| Enum values |
|-------------|
| `core` |
| `validated` |
| `exploratory` |

### `polisyos.ir.observation.contracts.StrategicResponseChannel` { #polisyos-ir-observation-contracts-strategicresponsechannel }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:StrategicResponseChannel`, `polisyos.ir:StrategicResponseChannel`
- ABI snapshot: `strategic_response_channel` / `schemas/snapshots/ir/strategic_response_channel.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Identify the adaptation channel that should trigger strategic-response checks.

| Enum values |
|-------------|
| `budget_channel` |
| `procurement_channel` |
| `labor_channel` |
| `trade_channel` |
| `household_income_channel` |
| `compliance_channel` |

### `polisyos.ir.observation.governance.GovernancePassAlias` { #polisyos-ir-observation-governance-governancepassalias }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:GovernancePassAlias`, `polisyos.ir:GovernancePassAlias`
- ABI snapshot: `governance_pass_alias` / `schemas/snapshots/ir/governance_pass_alias.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.governance.GovernancePassAliasStatus`
- Summary: Map a stable IR pass id to the runtime-specific governance pass id.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `canonical_pass_id` | `str` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `runtime_pass_id` | `str | NoneType` | `no` | `—` | — |
| `status` | `polisyos.ir.observation.governance.GovernancePassAliasStatus` | `yes` | `—` | `polisyos.ir.observation.governance.GovernancePassAliasStatus` |

### `polisyos.ir.observation.governance.GovernancePassAliasRegistry` { #polisyos-ir-observation-governance-governancepassaliasregistry }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:GovernancePassAliasRegistry`, `polisyos.ir:GovernancePassAliasRegistry`
- ABI snapshot: `governance_pass_alias_registry` / `schemas/snapshots/ir/governance_pass_alias_registry.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.governance.GovernancePassAlias`
- Summary: Store the pass-alias catalog used when emitting bundle-friendly mappings.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `aliases` | `dict[str, polisyos.ir.observation.governance.GovernancePassAlias]` | `no` | `—` | `polisyos.ir.observation.governance.GovernancePassAlias` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.governance.GovernancePassAliasStatus` { #polisyos-ir-observation-governance-governancepassaliasstatus }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:GovernancePassAliasStatus`, `polisyos.ir:GovernancePassAliasStatus`
- ABI snapshot: `governance_pass_alias_status` / `schemas/snapshots/ir/governance_pass_alias_status.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Declare whether a canonical pass can execute in the current Scientist runtime.

| Enum values |
|-------------|
| `runtime` |
| `deferred` |

### `polisyos.ir.observation.governance.GovernancePassMappingRegistry` { #polisyos-ir-observation-governance-governancepassmappingregistry }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:GovernancePassMappingRegistry`, `polisyos.ir:GovernancePassMappingRegistry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Materialize family-to-pass routing for readiness and execution manifests.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `family_passes` | `dict[str, list[str]]` | `no` | `—` | — |
| `global_mandatory_passes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.governance.ObservationFamilyPolicy` { #polisyos-ir-observation-governance-observationfamilypolicy }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:ObservationFamilyPolicy`, `polisyos.ir:ObservationFamilyPolicy`
- ABI snapshot: `observation_family_policy` / `schemas/snapshots/ir/observation_family_policy.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.IdentificationMode`, `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: Declare default identification semantics and mandatory passes for one family.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `fallback_identification_mode` | `polisyos.ir.observation.contracts.IdentificationMode | NoneType` | `no` | `—` | `polisyos.ir.observation.contracts.IdentificationMode` |
| `fallback_mode_annotation` | `str | NoneType` | `no` | `—` | — |
| `family` | `polisyos.ir.observation.contracts.ObservationFamily` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `mandatory_governance_passes` | `list[str]` | `no` | `—` | — |
| `primary_identification_mode` | `polisyos.ir.observation.contracts.IdentificationMode` | `yes` | `—` | `polisyos.ir.observation.contracts.IdentificationMode` |
| `requires_bounds_bundle` | `bool` | `no` | `False` | — |
| `requires_interference_contract` | `bool` | `no` | `False` | — |
| `requires_proxy_check` | `bool` | `no` | `False` | — |
| `requires_strategic_response_check` | `bool` | `no` | `False` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.governance.ObservationFamilyPolicyRegistry` { #polisyos-ir-observation-governance-observationfamilypolicyregistry }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:ObservationFamilyPolicyRegistry`, `polisyos.ir:ObservationFamilyPolicyRegistry`
- ABI snapshot: `observation_family_policy_registry` / `schemas/snapshots/ir/observation_family_policy_registry.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.governance.ObservationFamilyPolicy`
- Summary: Provide total family coverage for observation governance defaults.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `policies` | `dict[str, polisyos.ir.observation.governance.ObservationFamilyPolicy]` | `no` | `—` | `polisyos.ir.observation.governance.ObservationFamilyPolicy` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.measurement.IdentificationModeRouter` { #polisyos-ir-observation-measurement-identificationmoderouter }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:IdentificationModeRouter`, `polisyos.ir:IdentificationModeRouter`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.governance.ObservationFamilyPolicyRegistry`, `polisyos.ir.observation.measurement.MeasurementRegistry`
- Summary: Router that chooses the effective identification mode for observations.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `family_policy_registry` | `polisyos.ir.observation.governance.ObservationFamilyPolicyRegistry` | `no` | `—` | `polisyos.ir.observation.governance.ObservationFamilyPolicyRegistry` |
| `measurement_registry` | `polisyos.ir.observation.measurement.MeasurementRegistry` | `no` | `—` | `polisyos.ir.observation.measurement.MeasurementRegistry` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.measurement.IdentificationRoute` { #polisyos-ir-observation-measurement-identificationroute }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:IdentificationRoute`, `polisyos.ir:IdentificationRoute`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.IdentificationMode`, `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: Return the effective identification mode selected for one family/record.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `explicit_mode` | `polisyos.ir.observation.contracts.IdentificationMode | NoneType` | `no` | `—` | `polisyos.ir.observation.contracts.IdentificationMode` |
| `fallback_mode` | `polisyos.ir.observation.contracts.IdentificationMode | NoneType` | `no` | `—` | `polisyos.ir.observation.contracts.IdentificationMode` |
| `fallback_triggered` | `bool` | `no` | `False` | — |
| `family` | `polisyos.ir.observation.contracts.ObservationFamily` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `primary_mode` | `polisyos.ir.observation.contracts.IdentificationMode` | `yes` | `—` | `polisyos.ir.observation.contracts.IdentificationMode` |
| `reason` | `str` | `yes` | `—` | — |
| `selected_mode` | `polisyos.ir.observation.contracts.IdentificationMode` | `yes` | `—` | `polisyos.ir.observation.contracts.IdentificationMode` |

### `polisyos.ir.observation.measurement.MeasurementRegistry` { #polisyos-ir-observation-measurement-measurementregistry }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:MeasurementRegistry`, `polisyos.ir:MeasurementRegistry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.measurement.MeasurementTierRule`, `polisyos.ir.observation.measurement.ProxyMappingRule`
- Summary: Normalize raw observation trust, coverage thresholds, and proxy defaults.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `coverage_rules` | `dict[str, float]` | `no` | `—` | — |
| `proxy_mappings` | `dict[str, polisyos.ir.observation.measurement.ProxyMappingRule]` | `no` | `—` | `polisyos.ir.observation.measurement.ProxyMappingRule` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `trust_tiers` | `dict[str, polisyos.ir.observation.measurement.MeasurementTierRule]` | `no` | `—` | `polisyos.ir.observation.measurement.MeasurementTierRule` |

### `polisyos.ir.observation.measurement.MeasurementTierRule` { #polisyos-ir-observation-measurement-measurementtierrule }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:MeasurementTierRule`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.measurement.MeasurementTrustTier`
- Summary: Parameterize trust-weight normalization for one ``MeasurementTrustTier``.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `max_coverage` | `float` | `no` | `1.0` | — |
| `min_coverage` | `float` | `no` | `0.0` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `tier` | `polisyos.ir.observation.measurement.MeasurementTrustTier` | `yes` | `—` | `polisyos.ir.observation.measurement.MeasurementTrustTier` |
| `trust_cap` | `float` | `yes` | `—` | — |
| `trust_multiplier` | `float` | `no` | `1.0` | — |

### `polisyos.ir.observation.measurement.MeasurementTrustTier` { #polisyos-ir-observation-measurement-measurementtrusttier }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:MeasurementTrustTier`, `polisyos.ir:MeasurementTrustTier`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Represent the normalized trust bucket consumed by calibration and routing.

| Enum values |
|-------------|
| `authoritative_high_coverage` |
| `authoritative_partial_coverage` |
| `administrative_noisy` |
| `derived_proxy` |
| `weak_anchor` |

### `polisyos.ir.observation.measurement.ProxyMappingRule` { #polisyos-ir-observation-measurement-proxymappingrule }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:ProxyMappingRule`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.contracts.ObservationFamily`
- Summary: Declare the default proxy source/metric for one latent family pathway.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `family` | `polisyos.ir.observation.contracts.ObservationFamily` | `yes` | `—` | `polisyos.ir.observation.contracts.ObservationFamily` |
| `notes` | `list[str]` | `no` | `—` | — |
| `proxy_metric_id` | `str | NoneType` | `no` | `—` | — |
| `proxy_source_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.measurement.RegimeCalendar` { #polisyos-ir-observation-measurement-regimecalendar }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:RegimeCalendar`, `polisyos.ir:RegimeCalendar`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.measurement.RegimeCalendarEntry`
- Summary: Calendar of policy or reporting regimes relevant to observations.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `boundary_buffer_periods` | `int` | `no` | `1` | — |
| `entries` | `list[polisyos.ir.observation.measurement.RegimeCalendarEntry]` | `no` | `—` | `polisyos.ir.observation.measurement.RegimeCalendarEntry` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.measurement.RegimeCalendarEntry` { #polisyos-ir-observation-measurement-regimecalendarentry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:RegimeCalendarEntry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Inclusive time window for a real-world policy or publication regime.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `end_date` | `date` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `regime_id` | `str` | `yes` | `—` | — |
| `start_date` | `date` | `yes` | `—` | — |

### `polisyos.ir.observation.measurement.SchemaChangepoint` { #polisyos-ir-observation-measurement-schemachangepoint }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:SchemaChangepoint`, `polisyos.ir:SchemaChangepoint`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Mark a schema or publication-regime boundary that should trigger holdouts.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `changepoint_id` | `str` | `yes` | `—` | — |
| `effective_date` | `date` | `yes` | `—` | — |
| `from_schema_regime_id` | `str | NoneType` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `source_id` | `str | NoneType` | `no` | `—` | — |
| `source_version` | `str | NoneType` | `no` | `—` | — |
| `to_schema_regime_id` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.observation.measurement.SchemaRegimeRegistry` { #polisyos-ir-observation-measurement-schemaregimeregistry }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:SchemaRegimeRegistry`, `polisyos.ir:SchemaRegimeRegistry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.measurement.SchemaChangepoint`, `polisyos.ir.observation.measurement.SchemaRegimeSpec`
- Summary: Index schema regimes and changepoints for boundary-aware observation checks.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `changepoints` | `list[polisyos.ir.observation.measurement.SchemaChangepoint]` | `no` | `—` | `polisyos.ir.observation.measurement.SchemaChangepoint` |
| `regimes` | `dict[str, polisyos.ir.observation.measurement.SchemaRegimeSpec]` | `no` | `—` | `polisyos.ir.observation.measurement.SchemaRegimeSpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.measurement.SchemaRegimeSpec` { #polisyos-ir-observation-measurement-schemaregimespec }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:SchemaRegimeSpec`, `polisyos.ir:SchemaRegimeSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Describe the validity window and boundary buffer for one schema regime.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `boundary_buffer_periods` | `int` | `no` | `1` | — |
| `effective_end` | `date | NoneType` | `no` | `—` | — |
| `effective_start` | `date` | `yes` | `—` | — |
| `publication_regime_notes` | `list[str]` | `no` | `—` | — |
| `regime_id` | `str | NoneType` | `no` | `—` | — |
| `schema_regime_id` | `str` | `yes` | `—` | — |
| `source_id` | `str | NoneType` | `no` | `—` | — |
| `source_version` | `str` | `yes` | `—` | — |

### `polisyos.ir.observation.measurement.ShockCalendar` { #polisyos-ir-observation-measurement-shockcalendar }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.observation:ShockCalendar`, `polisyos.ir:ShockCalendar`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.observation.measurement.ShockCalendarEntry`
- Summary: Track exogenous shock windows that can force fallback identification modes.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `boundary_buffer_periods` | `int` | `no` | `1` | — |
| `entries` | `list[polisyos.ir.observation.measurement.ShockCalendarEntry]` | `no` | `—` | `polisyos.ir.observation.measurement.ShockCalendarEntry` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.observation.measurement.ShockCalendarEntry` { #polisyos-ir-observation-measurement-shockcalendarentry }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.observation:ShockCalendarEntry`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Inclusive time window for an exogenous shock that can trigger fallback logic.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `affected_regime_ids` | `list[str]` | `no` | `—` | — |
| `end_date` | `date` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `shock_id` | `str` | `yes` | `—` | — |
| `start_date` | `date` | `yes` | `—` | — |

## Trinity

### `polisyos.ir.trinity.TrinityBundle` { #polisyos-ir-trinity-trinitybundle }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.trinity:TrinityBundle`
- ABI snapshot: `trinity_bundle` / `schemas/snapshots/ir/trinity_bundle.schema.json`
- Compatibility mode: `full`
- References: `polisyos.ir.governance.policy_spec.PolicySpec`, `polisyos.ir.governance.problem_frame.ProblemFrame`, `polisyos.ir.model_spec.ModelSpec`
- Summary: Validate and transport the ``ProblemFrame`` / ``PolicySpec`` / ``ModelSpec`` triple.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `model_spec` | `polisyos.ir.model_spec.ModelSpec` | `yes` | `—` | `polisyos.ir.model_spec.ModelSpec` |
| `policy_spec` | `polisyos.ir.governance.policy_spec.PolicySpec` | `yes` | `—` | `polisyos.ir.governance.policy_spec.PolicySpec` |
| `problem_frame` | `polisyos.ir.governance.problem_frame.ProblemFrame` | `yes` | `—` | `polisyos.ir.governance.problem_frame.ProblemFrame` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.trinity.loaders.TrinityLoadError` { #polisyos-ir-trinity-loaders-trinityloaderror }

- Kind: `class`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Trinity load error exception.

## World

### `polisyos.ir.world.abi.EdgeKind` { #polisyos-ir-world-abi-edgekind }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:EdgeKind`
- ABI snapshot: `edge_kind` / `schemas/snapshots/fabric/edge_kind.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Edge kind public type.

| Enum values |
|-------------|
| `doc.has_version` |
| `doc.has_fragment` |
| `claim.cites` |
| `claim.derived_from` |
| `claim.in_conflict_set` |
| `conflict.resolves_to` |
| `claim.supports` |
| `claim.contradicts` |
| `report.about` |
| `prov.used` |
| `prov.was_generated_by` |
| `prov.was_derived_from` |
| `prov.was_associated_with` |
| `prov.was_attributed_to` |

### `polisyos.ir.world.abi.NodeKind` { #polisyos-ir-world-abi-nodekind }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:NodeKind`
- ABI snapshot: `node_kind` / `schemas/snapshots/fabric/node_kind.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Node kind public type.

| Enum values |
|-------------|
| `artifact` |
| `doc.source` |
| `doc.version` |
| `doc.fragment` |
| `claim` |
| `conflict_set` |
| `trust.assessment` |
| `quality.report` |
| `world.event` |
| `prov.agent` |
| `prov.activity` |

### `polisyos.ir.world.claim.Claim` { #polisyos-ir-world-claim-claim }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.world:Claim`
- ABI snapshot: `claim` / `schemas/snapshots/ir/claim.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.citations.CitationRef`, `polisyos.ir.world.claim.ClaimSourceKind`
- Summary: Claim public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `citations` | `list[polisyos.ir.citations.CitationRef]` | `no` | `—` | `polisyos.ir.citations.CitationRef` |
| `claim_id` | `str` | `yes` | `—` | — |
| `confidence` | `Decimal` | `yes` | `—` | — |
| `domain` | `str | NoneType` | `no` | `—` | — |
| `jurisdiction` | `str | NoneType` | `no` | `—` | — |
| `predicate_id` | `str` | `yes` | `—` | — |
| `props` | `dict[str, Any]` | `no` | `—` | — |
| `qualifiers` | `dict[str, str | int | bool]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `source_artifacts` | `list[str]` | `no` | `—` | — |
| `source_kind` | `polisyos.ir.world.claim.ClaimSourceKind` | `yes` | `—` | `polisyos.ir.world.claim.ClaimSourceKind` |
| `subject_id` | `str | NoneType` | `no` | `—` | — |
| `subject_text` | `str | NoneType` | `no` | `—` | — |
| `unit_id` | `str | NoneType` | `no` | `—` | — |
| `valid_from` | `datetime | NoneType` | `no` | `—` | — |
| `valid_to` | `datetime | NoneType` | `no` | `—` | — |
| `value_decimal` | `Decimal | NoneType` | `no` | `—` | — |
| `value_text` | `str` | `yes` | `—` | — |

### `polisyos.ir.world.claim.ClaimSourceKind` { #polisyos-ir-world-claim-claimsourcekind }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ClaimSourceKind`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Claim source kind public type.

| Enum values |
|-------------|
| `doc` |
| `dataset` |
| `simulation` |
| `expert` |
| `derived` |

### `polisyos.ir.world.conflict.ConflictKind` { #polisyos-ir-world-conflict-conflictkind }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ConflictKind`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Conflict kind public type.

| Enum values |
|-------------|
| `value_mismatch` |
| `unit_mismatch` |
| `definition_mismatch` |
| `temporal_mismatch` |
| `duplicate` |

### `polisyos.ir.world.conflict.ConflictResolution` { #polisyos-ir-world-conflict-conflictresolution }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.world:ConflictResolution`
- ABI snapshot: `conflict_resolution` / `schemas/snapshots/ir/conflict_resolution.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.world.conflict.ConflictResolutionCandidate`, `polisyos.ir.world.conflict.ConflictResolutionInputs`
- Summary: Conflict resolution public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `algorithm_version` | `str` | `yes` | `—` | — |
| `candidates` | `list[polisyos.ir.world.conflict.ConflictResolutionCandidate]` | `yes` | `—` | `polisyos.ir.world.conflict.ConflictResolutionCandidate` |
| `conflict_set_id` | `str` | `yes` | `—` | — |
| `inputs` | `polisyos.ir.world.conflict.ConflictResolutionInputs` | `yes` | `—` | `polisyos.ir.world.conflict.ConflictResolutionInputs` |
| `notes` | `list[str]` | `no` | `—` | — |
| `policy_id` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `tie_break_rule` | `Literal[lexicographic_claim_id]` | `no` | `'lexicographic_claim_id'` | — |
| `winner_claim_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.world.conflict.ConflictResolutionCandidate` { #polisyos-ir-world-conflict-conflictresolutioncandidate }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ConflictResolutionCandidate`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Conflict resolution candidate public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `claim_id` | `str` | `yes` | `—` | — |
| `score_breakdown` | `dict[str, str]` | `no` | `—` | — |
| `score_total` | `str` | `yes` | `—` | — |

### `polisyos.ir.world.conflict.ConflictResolutionInputs` { #polisyos-ir-world-conflict-conflictresolutioninputs }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ConflictResolutionInputs`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Conflict resolution inputs public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `claim_ids` | `list[str]` | `no` | `—` | — |
| `doc_version_ids` | `list[str]` | `no` | `—` | — |
| `trust_assessment_ids` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.world.conflict.ConflictSet` { #polisyos-ir-world-conflict-conflictset }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.world:ConflictSet`
- ABI snapshot: `conflict_set` / `schemas/snapshots/ir/conflict_set.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.world.conflict.ConflictKind`, `polisyos.ir.world.conflict.ConflictSetResolution`
- Summary: Conflict set public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `conflict_key` | `str` | `yes` | `—` | — |
| `conflict_kind` | `polisyos.ir.world.conflict.ConflictKind` | `yes` | `—` | `polisyos.ir.world.conflict.ConflictKind` |
| `conflict_set_id` | `str` | `yes` | `—` | — |
| `member_claim_ids` | `list[str]` | `yes` | `—` | — |
| `props` | `dict[str, Any]` | `no` | `—` | — |
| `resolution` | `polisyos.ir.world.conflict.ConflictSetResolution | NoneType` | `no` | `—` | `polisyos.ir.world.conflict.ConflictSetResolution` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.world.conflict.ConflictSetResolution` { #polisyos-ir-world-conflict-conflictsetresolution }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ConflictSetResolution`
- ABI snapshot: `conflict_set_resolution` / `schemas/snapshots/ir/conflict_set_resolution.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Conflict set resolution public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `confidence` | `Decimal` | `yes` | `—` | — |
| `policy_id` | `str` | `yes` | `—` | — |
| `rationale` | `str` | `yes` | `—` | — |
| `resolution_artifact_id` | `str` | `yes` | `—` | — |
| `winner_claim_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.world.doc.DocFragment` { #polisyos-ir-world-doc-docfragment }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.world:DocFragment`
- ABI snapshot: `doc_fragment` / `schemas/snapshots/ir/doc_fragment.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.citations.FragmentLocator`
- Summary: Doc fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `doc_version_id` | `str` | `yes` | `—` | — |
| `fragment_id` | `str` | `yes` | `—` | — |
| `locator` | `polisyos.ir.citations.FragmentLocator` | `yes` | `—` | `polisyos.ir.citations.FragmentLocator` |
| `props` | `dict[str, Any]` | `no` | `—` | — |
| `quote_preview` | `str | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `text_hash` | `str` | `yes` | `—` | — |

### `polisyos.ir.world.doc.DocMeta` { #polisyos-ir-world-doc-docmeta }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.world:DocMeta`
- ABI snapshot: `doc_meta` / `schemas/snapshots/ir/doc_meta.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Doc meta public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `canonical_url` | `str | NoneType` | `no` | `—` | — |
| `chunks_ref` | `str | NoneType` | `no` | `—` | — |
| `doc_source_id` | `str` | `yes` | `—` | — |
| `doc_version_id` | `str` | `yes` | `—` | — |
| `jurisdiction` | `str | NoneType` | `no` | `—` | — |
| `language` | `str | NoneType` | `no` | `—` | — |
| `license` | `str` | `yes` | `—` | — |
| `mime` | `str` | `yes` | `—` | — |
| `normalized_ref` | `str | NoneType` | `no` | `—` | — |
| `official_id` | `str | NoneType` | `no` | `—` | — |
| `props` | `dict[str, Any]` | `no` | `—` | — |
| `raw_ref` | `str` | `yes` | `—` | — |
| `retrieved_at` | `datetime` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `structure_ref` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.world.event.EventKind` { #polisyos-ir-world-event-eventkind }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:EventKind`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Event kind public type.

| Enum values |
|-------------|
| `fetch_doc` |
| `normalize_doc` |
| `structure_doc` |
| `chunk_doc` |
| `extract_claims` |
| `normalize_claims` |
| `detect_conflicts` |
| `resolve_conflicts` |
| `assemble_norm_pack` |
| `evaluate_legality` |
| `ingest_dataset` |
| `query_world` |
| `simulate` |
| `validate` |
| `knowledge_bundle_build` |

### `polisyos.ir.world.event.ProvActivity` { #polisyos-ir-world-event-provactivity }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ProvActivity`
- ABI snapshot: `prov_activity` / `schemas/snapshots/ir/prov_activity.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.world.event.ProvActivityType`
- Summary: Prov activity public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `activity_id` | `str` | `yes` | `—` | — |
| `activity_type` | `polisyos.ir.world.event.ProvActivityType` | `yes` | `—` | `polisyos.ir.world.event.ProvActivityType` |
| `ended_at` | `datetime | NoneType` | `no` | `—` | — |
| `label` | `str` | `yes` | `—` | — |
| `parameters` | `dict[str, Any]` | `no` | `—` | — |
| `started_at` | `datetime` | `yes` | `—` | — |

### `polisyos.ir.world.event.ProvActivityType` { #polisyos-ir-world-event-provactivitytype }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ProvActivityType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Prov activity type public type.

| Enum values |
|-------------|
| `fetch_doc` |
| `normalize_doc` |
| `structure_doc` |
| `chunk_doc` |
| `extract_claims` |
| `normalize_claims` |
| `detect_conflicts` |
| `resolve_conflicts` |
| `assemble_norm_pack` |
| `evaluate_legality` |
| `ingest_dataset` |
| `query_world` |
| `simulate` |
| `validate` |
| `knowledge_bundle_build` |

### `polisyos.ir.world.event.ProvAgent` { #polisyos-ir-world-event-provagent }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ProvAgent`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.world.event.ProvAgentType`
- Summary: Prov agent public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `agent_id` | `str` | `yes` | `—` | — |
| `agent_type` | `polisyos.ir.world.event.ProvAgentType` | `yes` | `—` | `polisyos.ir.world.event.ProvAgentType` |
| `component_id` | `str | NoneType` | `no` | `—` | — |
| `label` | `str` | `yes` | `—` | — |
| `metadata` | `dict[str, str]` | `no` | `—` | — |
| `model_id` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.world.event.ProvAgentType` { #polisyos-ir-world-event-provagenttype }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ProvAgentType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Prov agent type public type.

| Enum values |
|-------------|
| `system` |
| `user` |
| `model` |
| `connector` |
| `extractor` |
| `scheduler` |
| `human_reviewer` |

### `polisyos.ir.world.event.WorldEvent` { #polisyos-ir-world-event-worldevent }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.world:WorldEvent`
- ABI snapshot: `world_event` / `schemas/snapshots/ir/world_event.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.world.event.EventKind`, `polisyos.ir.world.event.ProvActivity`, `polisyos.ir.world.event.ProvAgent`, `polisyos.ir.world.event.WorldObjectRef`
- Summary: Capture one immutable pipeline event after its ids, inputs, and outputs are stable enough to persist.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `activity` | `polisyos.ir.world.event.ProvActivity` | `yes` | `—` | `polisyos.ir.world.event.ProvActivity` |
| `agent` | `polisyos.ir.world.event.ProvAgent` | `yes` | `—` | `polisyos.ir.world.event.ProvAgent` |
| `event_id` | `str` | `yes` | `—` | — |
| `event_kind` | `polisyos.ir.world.event.EventKind` | `yes` | `—` | `polisyos.ir.world.event.EventKind` |
| `evidence_ref` | `str | NoneType` | `no` | `—` | — |
| `inputs` | `list[polisyos.ir.world.event.WorldObjectRef]` | `no` | `—` | `polisyos.ir.world.event.WorldObjectRef` |
| `outputs` | `list[polisyos.ir.world.event.WorldObjectRef]` | `no` | `—` | `polisyos.ir.world.event.WorldObjectRef` |
| `props` | `dict[str, Any]` | `no` | `—` | — |
| `provenance_ref` | `str | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.world.event.WorldObjectRef` { #polisyos-ir-world-event-worldobjectref }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:WorldObjectRef`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Point a provenance edge at either a world object id or the artifact that produced it.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `str | NoneType` | `no` | `—` | — |
| `world_id` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.world.prov_o.ProvOActivityRecord` { #polisyos-ir-world-prov-o-provoactivityrecord }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ProvOActivityRecord`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.world.prov_o.ProvORecordType`
- Summary: PROV-O view of one activity with deterministic duration metadata.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `activity_type` | `str` | `yes` | `—` | — |
| `attributes` | `dict[str, Any]` | `no` | `—` | — |
| `duration_seconds` | `float | NoneType` | `no` | `—` | — |
| `ended_at` | `str | NoneType` | `no` | `—` | — |
| `iri` | `str` | `yes` | `—` | — |
| `label` | `str` | `yes` | `—` | — |
| `started_at` | `str` | `yes` | `—` | — |
| `type` | `polisyos.ir.world.prov_o.ProvORecordType` | `no` | `<ProvORecordType.ACTIVITY: 'prov:Activity'>` | `polisyos.ir.world.prov_o.ProvORecordType` |

### `polisyos.ir.world.prov_o.ProvOAgent` { #polisyos-ir-world-prov-o-provoagent }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ProvOAgent`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.world.prov_o.ProvORecordType`
- Summary: PROV-O view of one world agent.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `agent_type` | `str` | `yes` | `—` | — |
| `attributes` | `dict[str, Any]` | `no` | `—` | — |
| `iri` | `str` | `yes` | `—` | — |
| `label` | `str` | `yes` | `—` | — |
| `type` | `polisyos.ir.world.prov_o.ProvORecordType` | `no` | `<ProvORecordType.AGENT: 'prov:Agent'>` | `polisyos.ir.world.prov_o.ProvORecordType` |

### `polisyos.ir.world.prov_o.ProvODocument` { #polisyos-ir-world-prov-o-provodocument }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ProvODocument`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.world.prov_o.ProvOActivityRecord`, `polisyos.ir.world.prov_o.ProvOAgent`, `polisyos.ir.world.prov_o.ProvOEntity`, `polisyos.ir.world.prov_o.ProvORelation`
- Summary: JSON-LD-friendly PROV-O bundle derived from one world event.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `activities` | `list[polisyos.ir.world.prov_o.ProvOActivityRecord]` | `no` | `—` | `polisyos.ir.world.prov_o.ProvOActivityRecord` |
| `agents` | `list[polisyos.ir.world.prov_o.ProvOAgent]` | `no` | `—` | `polisyos.ir.world.prov_o.ProvOAgent` |
| `context` | `str` | `no` | `'https://www.w3.org/ns/prov#'` | — |
| `entities` | `list[polisyos.ir.world.prov_o.ProvOEntity]` | `no` | `—` | `polisyos.ir.world.prov_o.ProvOEntity` |
| `event_id` | `str` | `yes` | `—` | — |
| `relations` | `list[polisyos.ir.world.prov_o.ProvORelation]` | `no` | `—` | `polisyos.ir.world.prov_o.ProvORelation` |

### `polisyos.ir.world.prov_o.ProvOEntity` { #polisyos-ir-world-prov-o-provoentity }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ProvOEntity`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.world.prov_o.ProvORecordType`
- Summary: PROV-O entity representing a world object or artifact boundary.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `str | NoneType` | `no` | `—` | — |
| `attributes` | `dict[str, Any]` | `no` | `—` | — |
| `iri` | `str` | `yes` | `—` | — |
| `label` | `str` | `yes` | `—` | — |
| `type` | `polisyos.ir.world.prov_o.ProvORecordType` | `no` | `<ProvORecordType.ENTITY: 'prov:Entity'>` | `polisyos.ir.world.prov_o.ProvORecordType` |
| `world_id` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.world.prov_o.ProvORecordType` { #polisyos-ir-world-prov-o-provorecordtype }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ProvORecordType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Subset of PROV-O classes used by the IR bridge.

| Enum values |
|-------------|
| `prov:Entity` |
| `prov:Activity` |
| `prov:Agent` |

### `polisyos.ir.world.prov_o.ProvORelation` { #polisyos-ir-world-prov-o-provorelation }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ProvORelation`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.world.prov_o.ProvORelationType`
- Summary: Typed PROV-O edge emitted from an immutable world event.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `attributes` | `dict[str, Any]` | `no` | `—` | — |
| `object` | `str` | `yes` | `—` | — |
| `relation` | `polisyos.ir.world.prov_o.ProvORelationType` | `yes` | `—` | `polisyos.ir.world.prov_o.ProvORelationType` |
| `subject` | `str` | `yes` | `—` | — |

### `polisyos.ir.world.prov_o.ProvORelationType` { #polisyos-ir-world-prov-o-provorelationtype }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:ProvORelationType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Subset of PROV-O properties emitted from world events.

| Enum values |
|-------------|
| `prov:used` |
| `prov:wasGeneratedBy` |
| `prov:wasAssociatedWith` |
| `prov:wasDerivedFrom` |
| `prov:wasAttributedTo` |

### `polisyos.ir.world.quality.QualityIssue` { #polisyos-ir-world-quality-qualityissue }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:QualityIssue`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.world.quality.QualityIssueSeverity`
- Summary: Represent one deterministic quality finding attached to a world quality report.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `code` | `str` | `yes` | `—` | — |
| `context_json` | `dict[str, Any] | list[Any]` | `no` | `—` | — |
| `msg` | `str` | `yes` | `—` | — |
| `severity` | `polisyos.ir.world.quality.QualityIssueSeverity` | `yes` | `—` | `polisyos.ir.world.quality.QualityIssueSeverity` |

### `polisyos.ir.world.quality.QualityIssueSeverity` { #polisyos-ir-world-quality-qualityissueseverity }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:QualityIssueSeverity`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Quality issue severity public type.

| Enum values |
|-------------|
| `info` |
| `warn` |
| `error` |

### `polisyos.ir.world.quality.QualityReport` { #polisyos-ir-world-quality-qualityreport }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.world:QualityReport`
- ABI snapshot: `quality_report` / `schemas/snapshots/ir/quality_report.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.world.quality.QualityIssue`, `polisyos.ir.world.quality.QualityScope`
- Summary: Persist the sorted quality findings for one pipeline run and give them a stable world id.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `algorithm_version` | `str` | `yes` | `—` | — |
| `issues` | `list[polisyos.ir.world.quality.QualityIssue]` | `no` | `—` | `polisyos.ir.world.quality.QualityIssue` |
| `metrics` | `dict[str, str | int | bool]` | `no` | `—` | — |
| `policy_id` | `str` | `yes` | `—` | — |
| `props` | `dict[str, Any]` | `no` | `—` | — |
| `quality_report_id` | `str` | `yes` | `—` | — |
| `run_event_id` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `scope` | `polisyos.ir.world.quality.QualityScope` | `yes` | `—` | `polisyos.ir.world.quality.QualityScope` |

### `polisyos.ir.world.quality.QualityScope` { #polisyos-ir-world-quality-qualityscope }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:QualityScope`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Quality scope public type.

| Enum values |
|-------------|
| `docs_pipeline` |
| `claims_pipeline` |
| `conflict_resolution` |

### `polisyos.ir.world.trust.TrustAssessment` { #polisyos-ir-world-trust-trustassessment }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.world:TrustAssessment`
- ABI snapshot: `trust_assessment` / `schemas/snapshots/ir/trust_assessment.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.world.trust.TrustTier`
- Summary: Trust assessment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `algorithm_version` | `str` | `yes` | `—` | — |
| `features` | `dict[str, str | int | bool]` | `no` | `—` | — |
| `policy_id` | `str` | `yes` | `—` | — |
| `props` | `dict[str, Any]` | `no` | `—` | — |
| `rationale` | `dict[str, Any] | list[Any]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `score` | `Decimal` | `yes` | `—` | — |
| `target_world_id` | `str` | `yes` | `—` | — |
| `tier` | `polisyos.ir.world.trust.TrustTier` | `yes` | `—` | `polisyos.ir.world.trust.TrustTier` |
| `trust_assessment_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.world.trust.TrustTier` { #polisyos-ir-world-trust-trusttier }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.world:TrustTier`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Trust tier public type.

| Enum values |
|-------------|
| `high` |
| `medium` |
| `low` |

## Canon

### `polisyos.ir.canon.CanonSpec` { #polisyos-ir-canon-canonspec }

- Kind: `dataclass`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Canon spec data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `name` | `str` | `no` | `'polisyos.canon.json'` | — |
| `version` | `str` | `no` | `'0.2.0'` | — |
| `forbid_floats` | `bool` | `no` | `True` | — |
| `forbid_nan_inf` | `bool` | `no` | `True` | — |
| `exclude_none` | `bool` | `no` | `True` | — |
| `max_depth` | `int` | `no` | `128` | — |
| `sort_keys` | `bool` | `no` | `True` | — |
| `separators` | `tuple[str, str]` | `no` | `(',', ':')` | — |
| `ensure_ascii` | `bool` | `no` | `False` | — |

### `polisyos.ir.canon.CanonViolation` { #polisyos-ir-canon-canonviolation }

- Kind: `class`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Canon violation public type.

## Citations

### `polisyos.ir.citations.AnchorKind` { #polisyos-ir-citations-anchorkind }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Anchor kind public type.

| Enum values |
|-------------|
| `article` |
| `section` |
| `clause` |
| `paragraph` |
| `page` |
| `table` |
| `figure` |
| `heading` |
| `chunk` |
| `other` |

### `polisyos.ir.citations.CitationRef` { #polisyos-ir-citations-citationref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.citations.DocumentRef`, `polisyos.ir.citations.FragmentLocator`
- Summary: Citation-grade reference to a specific document fragment.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `doc` | `polisyos.ir.citations.DocumentRef` | `yes` | `—` | `polisyos.ir.citations.DocumentRef` |
| `evidence_ref` | `str | NoneType` | `no` | `—` | — |
| `fragment_id` | `str | NoneType` | `no` | `—` | — |
| `locator` | `polisyos.ir.citations.FragmentLocator | NoneType` | `no` | `—` | `polisyos.ir.citations.FragmentLocator` |
| `notes` | `list[str]` | `no` | `—` | — |
| `props` | `dict[str, Any]` | `no` | `—` | — |
| `provenance_ref` | `str | NoneType` | `no` | `—` | — |
| `quote_hash` | `str | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `text_hash` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.citations.DocumentRef` { #polisyos-ir-citations-documentref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Document identity with optional version binding.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `doc_id` | `str` | `yes` | `—` | — |
| `doc_version_id` | `str | NoneType` | `no` | `—` | — |
| `doc_version_ref` | `str | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.citations.FragmentLocator` { #polisyos-ir-citations-fragmentlocator }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.citations.AnchorKind`
- Summary: Declarative locator within a specific document version.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `anchor_kind` | `polisyos.ir.citations.AnchorKind` | `yes` | `—` | `polisyos.ir.citations.AnchorKind` |
| `anchor_path` | `str | NoneType` | `no` | `—` | — |
| `offset_end` | `int | NoneType` | `no` | `—` | — |
| `offset_start` | `int | NoneType` | `no` | `—` | — |
| `page_end` | `int | NoneType` | `no` | `—` | — |
| `page_start` | `int | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

## Connectors

### `polisyos.ir.connectors.ConnectorCapability` { #polisyos-ir-connectors-connectorcapability }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:ConnectorCapability`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Advertise which fetch, filtering, metadata, and resilience behaviors exist.

| Enum values |
|-------------|
| `1` |
| `2` |
| `4` |
| `8` |
| `16` |
| `32` |
| `64` |
| `128` |
| `256` |
| `512` |
| `1024` |
| `2048` |
| `4096` |
| `8192` |

### `polisyos.ir.connectors.ConnectorDocumentationSpec` { #polisyos-ir-connectors-connectordocumentationspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Documentation boundary for connector discoverability.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `description` | `str` | `yes` | `—` | — |
| `documentation_url` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.connectors.ConnectorGovernanceProfile` { #polisyos-ir-connectors-connectorgovernanceprofile }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.connectors.QualityTier`, `polisyos.ir.connectors.TrustLevel`
- Summary: Trust/quality/capability profile advertised by a connector.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `capabilities` | `int` | `yes` | `—` | — |
| `quality_tier` | `polisyos.ir.connectors.QualityTier` | `yes` | `—` | `polisyos.ir.connectors.QualityTier` |
| `trust_level` | `polisyos.ir.connectors.TrustLevel` | `yes` | `—` | `polisyos.ir.connectors.TrustLevel` |

### `polisyos.ir.connectors.ConnectorIdentitySpec` { #polisyos-ir-connectors-connectoridentityspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Stable connector identity tuple.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `connector_id` | `str` | `yes` | `—` | — |
| `namespace` | `str` | `yes` | `—` | — |
| `version` | `str` | `yes` | `—` | — |

### `polisyos.ir.connectors.ConnectorMetadataSpec` { #polisyos-ir-connectors-connectormetadataspec }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:ConnectorMetadataSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.connectors.QualityTier`, `polisyos.ir.connectors.TrustLevel`
- Summary: Define the immutable IR contract that registers one external data connector.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `capabilities` | `int` | `no` | `0` | — |
| `column_classification` | `dict[str, str]` | `no` | `—` | — |
| `connector_id` | `str` | `yes` | `—` | — |
| `data_classification` | `str` | `no` | `'public'` | — |
| `description` | `str` | `no` | `''` | — |
| `documentation_url` | `str | NoneType` | `no` | `—` | — |
| `last_updated` | `datetime | NoneType` | `no` | `—` | — |
| `namespace` | `str` | `yes` | `—` | — |
| `observed_latency_ms` | `float | NoneType` | `no` | `—` | — |
| `quality_tier` | `polisyos.ir.connectors.QualityTier` | `no` | `<QualityTier.UNVERIFIED: 0>` | `polisyos.ir.connectors.QualityTier` |
| `resilience_config` | `dict[str, Any] | NoneType` | `no` | `—` | — |
| `source_name` | `str` | `yes` | `—` | — |
| `source_organization` | `str` | `yes` | `—` | — |
| `source_url` | `str | NoneType` | `no` | `—` | — |
| `trust_level` | `polisyos.ir.connectors.TrustLevel` | `no` | `<TrustLevel.UNVERIFIED: 0>` | `polisyos.ir.connectors.TrustLevel` |
| `version` | `str` | `yes` | `—` | — |

### `polisyos.ir.connectors.ConnectorOperationalProfile` { #polisyos-ir-connectors-connectoroperationalprofile }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Operational and freshness metadata for a connector.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `last_updated` | `datetime | NoneType` | `no` | `—` | — |
| `observed_latency_ms` | `float | NoneType` | `no` | `—` | — |
| `resilience_config` | `dict[str, Any] | NoneType` | `no` | `—` | — |

### `polisyos.ir.connectors.ConnectorSourceSpec` { #polisyos-ir-connectors-connectorsourcespec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Human-readable source provenance for a connector.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `source_name` | `str` | `yes` | `—` | — |
| `source_organization` | `str` | `yes` | `—` | — |
| `source_url` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.connectors.DataVersion` { #polisyos-ir-connectors-dataversion }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.connectors.VersionStrategy`
- Summary: Version identifier for cached data.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `content_hash` | `str | NoneType` | `no` | `—` | — |
| `strategy` | `polisyos.ir.connectors.VersionStrategy` | `yes` | `—` | `polisyos.ir.connectors.VersionStrategy` |
| `timestamp` | `datetime` | `yes` | `—` | — |
| `value` | `str` | `yes` | `—` | — |

### `polisyos.ir.connectors.FetchPaginationEnvelope` { #polisyos-ir-connectors-fetchpaginationenvelope }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Pagination boundary for chunked fetch operations.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `has_more` | `bool` | `no` | `False` | — |
| `next_page_token` | `str | NoneType` | `no` | `—` | — |
| `total_count` | `int | NoneType` | `no` | `—` | — |

### `polisyos.ir.connectors.FetchProvenanceEnvelope` { #polisyos-ir-connectors-fetchprovenanceenvelope }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.connectors.DataVersion`, `polisyos.ir.refs.EvidenceBundleRef`
- Summary: Versioning and evidence metadata attached to a fetch payload.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `evidence_ref` | `polisyos.ir.refs.EvidenceBundleRef | NoneType` | `no` | `—` | `polisyos.ir.refs.EvidenceBundleRef` |
| `fetched_at` | `datetime` | `yes` | `—` | — |
| `source_updated_at` | `datetime | NoneType` | `no` | `—` | — |
| `version` | `polisyos.ir.connectors.DataVersion` | `yes` | `—` | `polisyos.ir.connectors.DataVersion` |

### `polisyos.ir.connectors.FetchQualityEnvelope` { #polisyos-ir-connectors-fetchqualityenvelope }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.connectors.QualityTier`
- Summary: Quality assessment boundary for a fetch payload.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `completeness` | `float` | `yes` | `—` | — |
| `quality_flags` | `frozenset[str]` | `no` | `frozenset()` | — |
| `quality_tier` | `polisyos.ir.connectors.QualityTier` | `yes` | `—` | `polisyos.ir.connectors.QualityTier` |

### `polisyos.ir.connectors.FetchRequest` { #polisyos-ir-connectors-fetchrequest }

- Kind: `dataclass`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Immutable, hashable fetch request specification.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `dataset_id` | `str` | `yes` | `—` | — |
| `date_start` | `datetime | None` | `no` | `None` | — |
| `date_end` | `datetime | None` | `no` | `None` | — |
| `as_of` | `datetime | None` | `no` | `None` | — |
| `filters` | `tuple[tuple[str, tuple[str, ...]], ...]` | `no` | `()` | — |
| `incremental_since` | `DataVersion | None` | `no` | `None` | — |
| `include_metadata` | `bool` | `no` | `True` | — |
| `include_schema` | `bool` | `no` | `True` | — |
| `page_size` | `int | None` | `no` | `None` | — |
| `page_token` | `str | None` | `no` | `None` | — |
| `min_quality_tier` | `QualityTier` | `no` | `<QualityTier.UNVERIFIED: 0>` | — |
| `retryable` | `bool | None` | `no` | `None` | — |
| `_query_key` | `str` | `yes` | `—` | — |
| `_request_key` | `str` | `yes` | `—` | — |

### `polisyos.ir.connectors.FetchResult` { #polisyos-ir-connectors-fetchresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `PydanticUndefined`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.connectors.DataVersion`, `polisyos.ir.connectors.PIIScanSummary`, `polisyos.ir.connectors.QualityTier`, `polisyos.ir.connectors.ResilienceInfo`, `polisyos.ir.refs.EvidenceBundleRef`
- Summary: Immutable result of a fetch operation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bytes_transferred` | `int` | `no` | `0` | — |
| `completeness` | `float` | `yes` | `—` | — |
| `data` | `~DataT` | `yes` | `—` | — |
| `evidence_ref` | `polisyos.ir.refs.EvidenceBundleRef | NoneType` | `no` | `—` | `polisyos.ir.refs.EvidenceBundleRef` |
| `fetch_duration_ms` | `float` | `no` | `0.0` | — |
| `fetched_at` | `datetime` | `yes` | `—` | — |
| `has_more` | `bool` | `no` | `False` | — |
| `next_page_token` | `str | NoneType` | `no` | `—` | — |
| `not_modified` | `bool` | `no` | `False` | — |
| `pii_scan` | `polisyos.ir.connectors.PIIScanSummary | NoneType` | `no` | `—` | `polisyos.ir.connectors.PIIScanSummary` |
| `quality_flags` | `frozenset[str]` | `no` | `frozenset()` | — |
| `quality_tier` | `polisyos.ir.connectors.QualityTier` | `no` | `<QualityTier.UNVERIFIED: 0>` | `polisyos.ir.connectors.QualityTier` |
| `resilience` | `polisyos.ir.connectors.ResilienceInfo | NoneType` | `no` | `—` | `polisyos.ir.connectors.ResilienceInfo` |
| `row_count` | `int` | `yes` | `—` | — |
| `schema_id` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `yes` | `—` | — |
| `source_updated_at` | `datetime | NoneType` | `no` | `—` | — |
| `total_count` | `int | NoneType` | `no` | `—` | — |
| `version` | `polisyos.ir.connectors.DataVersion` | `yes` | `—` | `polisyos.ir.connectors.DataVersion` |

### `polisyos.ir.connectors.FetchSchemaDescriptor` { #polisyos-ir-connectors-fetchschemadescriptor }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `PydanticUndefined`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Schema boundary for a fetch payload.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `schema_id` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `yes` | `—` | — |

### `polisyos.ir.connectors.FetchTransferEnvelope` { #polisyos-ir-connectors-fetchtransferenvelope }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.connectors.PIIScanSummary`, `polisyos.ir.connectors.ResilienceInfo`
- Summary: Transport/runtime metrics for one fetch invocation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `bytes_transferred` | `int` | `no` | `0` | — |
| `fetch_duration_ms` | `float` | `no` | `0.0` | — |
| `not_modified` | `bool` | `no` | `False` | — |
| `pii_scan` | `polisyos.ir.connectors.PIIScanSummary | NoneType` | `no` | `—` | `polisyos.ir.connectors.PIIScanSummary` |
| `resilience` | `polisyos.ir.connectors.ResilienceInfo | NoneType` | `no` | `—` | `polisyos.ir.connectors.ResilienceInfo` |

### `polisyos.ir.connectors.PIIDetectedEntity` { #polisyos-ir-connectors-piidetectedentity }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Single redacted PII detection result.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `column` | `str` | `no` | `''` | — |
| `end` | `int` | `no` | `0` | — |
| `entity_type` | `str` | `yes` | `—` | — |
| `redacted_text` | `str` | `no` | `'***'` | — |
| `score` | `float` | `yes` | `—` | — |
| `severity` | `str` | `yes` | `—` | — |
| `start` | `int` | `no` | `0` | — |

### `polisyos.ir.connectors.PIIScanSummary` { #polisyos-ir-connectors-piiscansummary }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.connectors.PIIDetectedEntity`
- Summary: Aggregated PII scan summary attached to connector fetch results.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `entities` | `list[polisyos.ir.connectors.PIIDetectedEntity]` | `no` | `—` | `polisyos.ir.connectors.PIIDetectedEntity` |
| `entities_by_severity` | `dict[str, int]` | `no` | `—` | — |
| `entities_by_type` | `dict[str, int]` | `no` | `—` | — |
| `max_severity` | `str` | `no` | `'none'` | — |
| `sample_rate` | `float` | `no` | `1.0` | — |
| `sampled` | `bool` | `no` | `False` | — |
| `scan_duration_ms` | `float` | `no` | `0.0` | — |
| `total_entities_found` | `int` | `no` | `0` | — |
| `total_records_scanned` | `int` | `no` | `0` | — |

### `polisyos.ir.connectors.QualityTier` { #polisyos-ir-connectors-qualitytier }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:QualityTier`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Data quality classification aligned with existing QualityIndicators.

| Enum values |
|-------------|
| `0` |
| `1` |
| `2` |
| `3` |
| `4` |

### `polisyos.ir.connectors.ResilienceInfo` { #polisyos-ir-connectors-resilienceinfo }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Metadata describing resilience behavior applied to a fetch result.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `circuit_state` | `str | NoneType` | `no` | `—` | — |
| `fallback_strategy` | `str | NoneType` | `no` | `—` | — |
| `fallback_used` | `bool` | `no` | `False` | — |
| `rate_limited` | `bool | NoneType` | `no` | `—` | — |
| `retry_attempts` | `int | NoneType` | `no` | `—` | — |

### `polisyos.ir.connectors.TrustLevel` { #polisyos-ir-connectors-trustlevel }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:TrustLevel`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Rank source provenance for connector admission and downstream governance.

| Enum values |
|-------------|
| `0` |
| `1` |
| `2` |
| `3` |
| `4` |

### `polisyos.ir.connectors.VersionStrategy` { #polisyos-ir-connectors-versionstrategy }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Versioning strategies for cached data.

| Enum values |
|-------------|
| `etag` |
| `timestamp` |
| `revision` |
| `content_hash` |

## Data

### `polisyos.ir.data.harmonizer.DomainHarmonizer` { #polisyos-ir-data-harmonizer-domainharmonizer }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.data:DomainHarmonizer`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Align a source DataFrame to a target variable schema.

### `polisyos.ir.data.harmonizer.HarmonizationReport` { #polisyos-ir-data-harmonizer-harmonizationreport }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.data:HarmonizationReport`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.data.harmonizer.MissingVariableRecord`, `polisyos.ir.data.harmonizer.ResolvedMapping`, `polisyos.ir.data.harmonizer.TypeMismatch`
- Summary: Frozen audit record produced by :meth:`DomainHarmonizer.align`.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `errors` | `tuple[str]` | `no` | `()` | — |
| `excluded_variables` | `tuple[str]` | `no` | `()` | — |
| `harmonized_variables` | `tuple[str]` | `yes` | `—` | — |
| `missing_variables` | `tuple[polisyos.ir.data.harmonizer.MissingVariableRecord]` | `yes` | `—` | `polisyos.ir.data.harmonizer.MissingVariableRecord` |
| `n_source_obs` | `int | NoneType` | `no` | `—` | — |
| `n_target_obs` | `int | NoneType` | `no` | `—` | — |
| `resolved_mappings` | `tuple[polisyos.ir.data.harmonizer.ResolvedMapping]` | `yes` | `—` | `polisyos.ir.data.harmonizer.ResolvedMapping` |
| `source_dataset_ref` | `str` | `yes` | `—` | — |
| `target_dataset_ref` | `str` | `yes` | `—` | — |
| `type_mismatches` | `tuple[polisyos.ir.data.harmonizer.TypeMismatch]` | `yes` | `—` | `polisyos.ir.data.harmonizer.TypeMismatch` |
| `warnings` | `tuple[str]` | `no` | `()` | — |

### `polisyos.ir.data.harmonizer.MissingVariableRecord` { #polisyos-ir-data-harmonizer-missingvariablerecord }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.data:MissingVariableRecord`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.data.harmonizer.MissingVariableStrategy`
- Summary: A target variable absent from the source dataset, with its resolution.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `imputed_value` | `float | NoneType` | `no` | `—` | — |
| `strategy_applied` | `polisyos.ir.data.harmonizer.MissingVariableStrategy` | `yes` | `—` | `polisyos.ir.data.harmonizer.MissingVariableStrategy` |
| `target_variable` | `str` | `yes` | `—` | — |

### `polisyos.ir.data.harmonizer.MissingVariableStrategy` { #polisyos-ir-data-harmonizer-missingvariablestrategy }

- Kind: `enum`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.data:MissingVariableStrategy`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Strategy applied when a target variable is absent from the source dataset.

| Enum values |
|-------------|
| `impute_mean` |
| `impute_model` |
| `exclude_unit` |
| `raise_error` |

### `polisyos.ir.data.harmonizer.ResolvedMapping` { #polisyos-ir-data-harmonizer-resolvedmapping }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.data:ResolvedMapping`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: A source column successfully mapped to a target variable.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `source_column` | `str` | `yes` | `—` | — |
| `source_dtype` | `str` | `yes` | `—` | — |
| `target_dtype` | `str` | `yes` | `—` | — |
| `target_variable` | `str` | `yes` | `—` | — |
| `type_coercion` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.data.harmonizer.TypeMismatch` { #polisyos-ir-data-harmonizer-typemismatch }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.data:TypeMismatch`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: A type incompatibility detected between source and target.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `coercion_applied` | `str | NoneType` | `no` | `—` | — |
| `is_coercible` | `bool` | `yes` | `—` | — |
| `source_dtype` | `str` | `yes` | `—` | — |
| `target_dtype` | `str` | `yes` | `—` | — |
| `target_variable` | `str` | `yes` | `—` | — |

### `polisyos.ir.data.versioning.DatasetVersion` { #polisyos-ir-data-versioning-datasetversion }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.data:DatasetVersion`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Reproducibility snapshot for a single dataset / DataFrame.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `columns` | `tuple[str]` | `yes` | `—` | — |
| `content_hash` | `str` | `yes` | `—` | — |
| `created_at` | `str` | `yes` | `—` | — |
| `dataset_ref` | `str` | `yes` | `—` | — |
| `n_obs` | `int` | `yes` | `—` | — |
| `schema_hash` | `str` | `yes` | `—` | — |
| `version_tag` | `str | NoneType` | `no` | `—` | — |

## Fact_Log

### `polisyos.ir.fact_log.Fact` { #polisyos-ir-fact-log-fact }

- Kind: `pydantic_model`
- Public status: `snapshot_only`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `fact` / `schemas/snapshots/ir/fact.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.fact_log.FactLegal`, `polisyos.ir.fact_log.FactProvenance`, `polisyos.ir.fact_log.FactTrust`
- Summary: Fact public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `fact_id` | `str` | `yes` | `—` | — |
| `legal` | `polisyos.ir.fact_log.FactLegal | NoneType` | `no` | `—` | `polisyos.ir.fact_log.FactLegal` |
| `object_value` | `str | int | bool | Decimal | NoneType` | `no` | `—` | — |
| `predicate_id` | `str` | `yes` | `—` | — |
| `provenance` | `polisyos.ir.fact_log.FactProvenance` | `yes` | `—` | `polisyos.ir.fact_log.FactProvenance` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `subject_id` | `str` | `yes` | `—` | — |
| `target_id` | `str | NoneType` | `no` | `—` | — |
| `trust` | `polisyos.ir.fact_log.FactTrust | NoneType` | `no` | `—` | `polisyos.ir.fact_log.FactTrust` |
| `tx_time` | `str` | `yes` | `—` | — |
| `valid_time` | `str | int | NoneType` | `no` | `—` | — |

### `polisyos.ir.fact_log.FactBatch` { #polisyos-ir-fact-log-factbatch }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.fact_log.Fact`
- Summary: Fact batch public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `facts` | `list[polisyos.ir.fact_log.Fact]` | `no` | `—` | `polisyos.ir.fact_log.Fact` |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.fact_log.FactLegal` { #polisyos-ir-fact-log-factlegal }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.fact_log.FactPIIEntity`
- Summary: Fact legal public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `access_tier` | `str | NoneType` | `no` | `—` | — |
| `basis` | `str | NoneType` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `pii_class` | `str | NoneType` | `no` | `—` | — |
| `pii_detected` | `list[polisyos.ir.fact_log.FactPIIEntity]` | `no` | `—` | `polisyos.ir.fact_log.FactPIIEntity` |
| `pii_max_severity` | `str | NoneType` | `no` | `—` | — |
| `pii_scan_timestamp` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.fact_log.FactPIIEntity` { #polisyos-ir-fact-log-factpiientity }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Fact PII entity public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `column` | `str | NoneType` | `no` | `—` | — |
| `end` | `int | NoneType` | `no` | `—` | — |
| `entity_type` | `str` | `yes` | `—` | — |
| `redacted_text` | `str` | `no` | `'***'` | — |
| `score` | `float | NoneType` | `no` | `—` | — |
| `severity` | `str` | `yes` | `—` | — |
| `start` | `int | NoneType` | `no` | `—` | — |

### `polisyos.ir.fact_log.FactProvenance` { #polisyos-ir-fact-log-factprovenance }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Fact provenance public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `ingestion_run_id` | `str | NoneType` | `no` | `—` | — |
| `license` | `str` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `raw_hash` | `str` | `yes` | `—` | — |
| `script_hash` | `str | NoneType` | `no` | `—` | — |
| `source_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.fact_log.FactSegmentManifest` { #polisyos-ir-fact-log-factsegmentmanifest }

- Kind: `pydantic_model`
- Public status: `snapshot_only`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `fact_segment_manifest` / `schemas/snapshots/ir/fact_segment_manifest.schema.json`
- Compatibility mode: `—`
- References: —
- Summary: Fact segment manifest data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `duplicate_count` | `int | NoneType` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `null_count` | `int | NoneType` | `no` | `—` | — |
| `path` | `str` | `yes` | `—` | — |
| `row_count` | `int` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `segment_id` | `str` | `yes` | `—` | — |
| `sha256` | `str` | `yes` | `—` | — |
| `stats` | `dict[str, int | float | str]` | `no` | `—` | — |
| `time_end` | `str | int | NoneType` | `no` | `—` | — |
| `time_start` | `str | int | NoneType` | `no` | `—` | — |

### `polisyos.ir.fact_log.FactTrust` { #polisyos-ir-fact-log-facttrust }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Fact trust public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `confidence` | `float | NoneType` | `no` | `—` | — |
| `method` | `str | NoneType` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `policy_id` | `str | NoneType` | `no` | `—` | — |

## Loaders

### `polisyos.ir.loaders.PolicyLoadError` { #polisyos-ir-loaders-policyloaderror }

- Kind: `class`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Raise when a payload cannot be parsed or validated as a Trinity bundle.

## Migration_Report

### `polisyos.ir.migration_report.MigrationAction` { #polisyos-ir-migration-report-migrationaction }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Migration action public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `from_path` | `str | NoneType` | `no` | `—` | — |
| `kind` | `Literal[copy, default, drop, transform, split, merge]` | `yes` | `—` | — |
| `lossy` | `bool` | `no` | `False` | — |
| `note` | `str | NoneType` | `no` | `—` | — |
| `to_path` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.migration_report.MigrationReport` { #polisyos-ir-migration-report-migrationreport }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.migration_report.MigrationAction`, `polisyos.ir.migration_report.MigrationWarning`
- Summary: Migration report data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `actions` | `list[polisyos.ir.migration_report.MigrationAction]` | `no` | `—` | `polisyos.ir.migration_report.MigrationAction` |
| `migration_id` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `source_format` | `str` | `yes` | `—` | — |
| `source_ref` | `str` | `yes` | `—` | — |
| `source_schema_version` | `str` | `yes` | `—` | — |
| `target_format` | `str` | `yes` | `—` | — |
| `target_schema_version` | `str` | `yes` | `—` | — |
| `warnings` | `list[polisyos.ir.migration_report.MigrationWarning]` | `no` | `—` | `polisyos.ir.migration_report.MigrationWarning` |

### `polisyos.ir.migration_report.MigrationWarning` { #polisyos-ir-migration-report-migrationwarning }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Migration warning public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `code` | `str` | `yes` | `—` | — |
| `message` | `str` | `yes` | `—` | — |
| `path` | `str | NoneType` | `no` | `—` | — |

## Model_Spec

### `polisyos.ir.model_spec.AgentConfig` { #polisyos-ir-model-spec-agentconfig }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:AgentConfig`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.model_spec.AgentTypeConfig`
- Summary: Bundle all agent populations and interaction topology for a world model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `agent_types` | `list[polisyos.ir.model_spec.AgentTypeConfig]` | `no` | `—` | `polisyos.ir.model_spec.AgentTypeConfig` |
| `interaction_topology` | `Literal[random, lattice, network, spatial] | NoneType` | `no` | `—` | — |
| `max_agents` | `int | NoneType` | `no` | `—` | — |
| `network_graph_ref` | `str | NoneType` | `no` | `—` | — |
| `total_agents` | `int | NoneType` | `no` | `—` | — |

### `polisyos.ir.model_spec.AgentTypeConfig` { #polisyos-ir-model-spec-agenttypeconfig }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:AgentTypeConfig`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.types.EntityType`, `polisyos.ir.types.TranslatableString`
- Summary: Describe one simulated agent population and its behavioral heterogeneity.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `adaptive` | `bool` | `no` | `False` | — |
| `agent_type_id` | `str` | `yes` | `—` | — |
| `attribute_distributions` | `dict[str, Any]` | `no` | `—` | — |
| `discount_rate` | `Decimal | NoneType` | `no` | `—` | — |
| `entity_type` | `polisyos.ir.types.EntityType` | `yes` | `—` | `polisyos.ir.types.EntityType` |
| `max_population` | `int | NoneType` | `no` | `—` | — |
| `name` | `polisyos.ir.types.TranslatableString | NoneType` | `no` | `—` | `polisyos.ir.types.TranslatableString` |
| `notes` | `list[str]` | `no` | `—` | — |
| `policy_model` | `str | NoneType` | `no` | `—` | — |
| `population_count` | `int | NoneType` | `no` | `—` | — |
| `population_share` | `Decimal | NoneType` | `no` | `—` | — |
| `risk_aversion` | `Decimal | NoneType` | `no` | `—` | — |
| `utility_function` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.model_spec.AssumptionSpec` { #polisyos-ir-model-spec-assumptionspec }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:AssumptionSpec`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.model_spec.AssumptionType`
- Summary: Record one explicit world-model assumption for governance and sensitivity.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `assumption_id` | `str` | `yes` | `—` | — |
| `assumption_type` | `polisyos.ir.model_spec.AssumptionType` | `yes` | `—` | `polisyos.ir.model_spec.AssumptionType` |
| `confidence` | `Decimal | NoneType` | `no` | `—` | — |
| `description` | `str` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `sensitivity_flag` | `bool` | `no` | `False` | — |
| `source` | `str | NoneType` | `no` | `—` | — |
| `value` | `Decimal | str | bool | NoneType` | `no` | `—` | — |

### `polisyos.ir.model_spec.AssumptionType` { #polisyos-ir-model-spec-assumptiontype }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:AssumptionType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Classify which downstream mechanism or uncertainty layer an assumption affects.

| Enum values |
|-------------|
| `behavioral` |
| `structural` |
| `parametric` |
| `distributional` |
| `temporal` |
| `boundary` |

### `polisyos.ir.model_spec.EnvironmentConfig` { #polisyos-ir-model-spec-environmentconfig }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:EnvironmentConfig`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.model_spec.EnvironmentParam`
- Summary: Collect exogenous parameters and stochastic execution controls.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `parallel_worlds` | `int` | `no` | `1` | — |
| `params` | `list[polisyos.ir.model_spec.EnvironmentParam]` | `no` | `—` | `polisyos.ir.model_spec.EnvironmentParam` |
| `random_seed` | `int | NoneType` | `no` | `—` | — |
| `stochastic` | `bool` | `no` | `True` | — |

### `polisyos.ir.model_spec.EnvironmentParam` { #polisyos-ir-model-spec-environmentparam }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:EnvironmentParam`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Declare one exogenous world parameter or time-varying external driver.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `description` | `str | NoneType` | `no` | `—` | — |
| `param_id` | `str` | `yes` | `—` | — |
| `time_series_ref` | `str | NoneType` | `no` | `—` | — |
| `time_varying` | `bool` | `no` | `False` | — |
| `unit_id` | `str | NoneType` | `no` | `—` | — |
| `value` | `Decimal | str | bool` | `yes` | `—` | — |

### `polisyos.ir.model_spec.FidelityLevel` { #polisyos-ir-model-spec-fidelitylevel }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:FidelityLevel`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Select the execution fidelity expected by simulation and calibration runners.

| Enum values |
|-------------|
| `surrogate_fluid` |
| `surrogate_discrete` |
| `hybrid` |
| `full_discrete` |

### `polisyos.ir.model_spec.ModelSpec` { #polisyos-ir-model-spec-modelspec }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.trinity:ModelSpec`, `polisyos.ir:ModelSpec`
- ABI snapshot: `model_spec` / `schemas/snapshots/ir/model_spec.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.time_semantics.TimeSemantics`, `polisyos.ir.model_spec.AgentConfig`, `polisyos.ir.model_spec.AssumptionSpec`, `polisyos.ir.model_spec.EnvironmentConfig`, `polisyos.ir.model_spec.FidelityLevel`, `polisyos.ir.types.TranslatableString`
- Summary: Define the Trinity ``how`` contract for simulation assumptions and state.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `agent_config` | `polisyos.ir.model_spec.AgentConfig` | `no` | `—` | `polisyos.ir.model_spec.AgentConfig` |
| `assumptions` | `list[polisyos.ir.model_spec.AssumptionSpec]` | `no` | `—` | `polisyos.ir.model_spec.AssumptionSpec` |
| `calibrated` | `bool` | `no` | `False` | — |
| `calibration_ref` | `str | NoneType` | `no` | `—` | — |
| `data_snapshot_ref` | `str` | `yes` | `—` | — |
| `description` | `str | NoneType` | `no` | `—` | — |
| `environment_config` | `polisyos.ir.model_spec.EnvironmentConfig` | `no` | `—` | `polisyos.ir.model_spec.EnvironmentConfig` |
| `fidelity_level` | `polisyos.ir.model_spec.FidelityLevel` | `no` | `<FidelityLevel.HYBRID: 'hybrid'>` | `polisyos.ir.model_spec.FidelityLevel` |
| `labels` | `list[str]` | `no` | `—` | — |
| `model_id` | `str` | `yes` | `—` | — |
| `name` | `polisyos.ir.types.TranslatableString | NoneType` | `no` | `—` | `polisyos.ir.types.TranslatableString` |
| `notes` | `list[str]` | `no` | `—` | — |
| `registry_bundle_ref` | `str | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `time_semantics` | `polisyos.ir.kernel.time_semantics.TimeSemantics | NoneType` | `no` | `—` | `polisyos.ir.kernel.time_semantics.TimeSemantics` |
| `version_tag` | `str | NoneType` | `no` | `—` | — |

## Norm_Pack

### `polisyos.ir.norm_pack.BackendExpr` { #polisyos-ir-norm-pack-backendexpr }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Backend-specific expression payload.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `backend` | `str` | `yes` | `—` | — |
| `expr` | `str` | `yes` | `—` | — |
| `language` | `str | NoneType` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.norm_pack.NormPack` { #polisyos-ir-norm-pack-normpack }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir:NormPack`
- ABI snapshot: `norm_pack` / `schemas/snapshots/ir/norm_pack.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.norm_pack.NormRule`
- Summary: Package of applicable norms for policy evaluation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `effective_date` | `str | NoneType` | `no` | `—` | — |
| `jurisdiction` | `str` | `yes` | `—` | — |
| `metadata` | `dict[str, Any]` | `no` | `—` | — |
| `norms` | `list[polisyos.ir.norm_pack.NormRule]` | `no` | `—` | `polisyos.ir.norm_pack.NormRule` |
| `pack_id` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.norm_pack.NormRef` { #polisyos-ir-norm-pack-normref }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir:NormRef`
- ABI snapshot: `norm_ref` / `schemas/snapshots/ir/norm_ref.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.citations.CitationRef`
- Summary: Reference a source provision that grounds one normative rule.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `citations` | `list[polisyos.ir.citations.CitationRef]` | `no` | `—` | `polisyos.ir.citations.CitationRef` |
| `provision_id` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `source_document` | `str | NoneType` | `no` | `—` | — |
| `version` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.norm_pack.NormRule` { #polisyos-ir-norm-pack-normrule }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir:NormRule`
- ABI snapshot: `norm_rule` / `schemas/snapshots/ir/norm_rule.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.analytics.applicability.NormApplicability`, `polisyos.ir.norm_pack.BackendExpr`, `polisyos.ir.norm_pack.NormRef`, `polisyos.ir.norm_pack.RuleType`
- Summary: Declare one machine-readable norm and its source-backed applicability scope.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `applicability` | `polisyos.ir.analytics.applicability.NormApplicability` | `no` | `—` | `polisyos.ir.analytics.applicability.NormApplicability` |
| `backend_exprs` | `list[polisyos.ir.norm_pack.BackendExpr]` | `no` | `—` | `polisyos.ir.norm_pack.BackendExpr` |
| `backend_metadata` | `dict[str, Any]` | `no` | `—` | — |
| `backend_refs` | `list[str]` | `no` | `—` | — |
| `description` | `str` | `yes` | `—` | — |
| `norm_id` | `str` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `provision_refs` | `list[polisyos.ir.norm_pack.NormRef]` | `no` | `—` | `polisyos.ir.norm_pack.NormRef` |
| `rule_type` | `polisyos.ir.norm_pack.RuleType` | `yes` | `—` | `polisyos.ir.norm_pack.RuleType` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.norm_pack.RuleType` { #polisyos-ir-norm-pack-ruletype }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:RuleType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Classify how a provision constrains policy actions in a norm pack.

| Enum values |
|-------------|
| `obligation` |
| `prohibition` |
| `permission` |

## Passes

### `polisyos.ir.passes.base.IRAnalysis` { #polisyos-ir-passes-base-iranalysis }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.passes:IRAnalysis`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Read-only pass whose outputs can be cached by dependency fingerprint.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `writes` | `tuple[str, ...]` | `yes` | `—` | — |

### `polisyos.ir.passes.base.IRPass` { #polisyos-ir-passes-base-irpass }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.passes:IRPass`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Base class for deterministic IR passes.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `str` | `yes` | `—` | — |
| `name` | `str` | `yes` | `—` | — |
| `reads` | `tuple[str, ...]` | `yes` | `—` | — |
| `writes` | `tuple[str, ...]` | `yes` | `—` | — |

### `polisyos.ir.passes.base.InvalidationSet` { #polisyos-ir-passes-base-invalidationset }

- Kind: `dataclass`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.passes:InvalidationSet`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Describe which named surfaces invalidate cached analyses.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `keys` | `frozenset[str]` | `no` | `frozenset()` | — |
| `invalidate_all` | `bool` | `no` | `False` | — |

### `polisyos.ir.passes.base.PassContext` { #polisyos-ir-passes-base-passcontext }

- Kind: `dataclass`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.passes:PassContext`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Immutable bundle of surfaces, analysis outputs, and diagnostics.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `surfaces` | `Mapping[str, Any]` | `no` | `dict()` | — |
| `analyses` | `Mapping[str, Any]` | `no` | `dict()` | — |
| `diagnostics` | `tuple[PassDiagnostic, ...]` | `no` | `()` | — |
| `_surface_fingerprints` | `Mapping[str, str]` | `no` | `dict()` | — |
| `_analysis_fingerprints` | `Mapping[str, str]` | `no` | `dict()` | — |

### `polisyos.ir.passes.base.PassDiagnostic` { #polisyos-ir-passes-base-passdiagnostic }

- Kind: `dataclass`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.passes:PassDiagnostic`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Structured compiler-style diagnostic emitted by a pass.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `code` | `str` | `yes` | `—` | — |
| `message` | `str` | `yes` | `—` | — |
| `severity` | `str` | `no` | `'info'` | — |
| `path` | `tuple[str | int, ...]` | `no` | `()` | — |
| `data` | `Mapping[str, Any]` | `no` | `dict()` | — |

### `polisyos.ir.passes.base.PassPipeline` { #polisyos-ir-passes-base-passpipeline }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.passes:PassPipeline`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Run IR passes in order with deterministic analysis caching.

### `polisyos.ir.passes.base.PassResult` { #polisyos-ir-passes-base-passresult }

- Kind: `dataclass`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.passes:PassResult`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: The output of one pass application.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `surface_updates` | `Mapping[str, Any]` | `no` | `dict()` | — |
| `analysis_updates` | `Mapping[str, Any]` | `no` | `dict()` | — |
| `diagnostics` | `tuple[PassDiagnostic, ...]` | `no` | `()` | — |
| `invalidation` | `InvalidationSet` | `no` | `none()` | — |

### `polisyos.ir.passes.core.ArtifactRefTypeCheckResult` { #polisyos-ir-passes-core-artifactreftypecheckresult }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.passes:ArtifactRefTypeCheckResult`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Summarize artifact-ref validation across IR surfaces.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `checked_ref_count` | `int` | `no` | `0` | — |
| `mismatched_ref_count` | `int` | `no` | `0` | — |
| `missing_ref_count` | `int` | `no` | `0` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.passes.core.CrossModelTypeCheckPass` { #polisyos-ir-passes-core-crossmodeltypecheckpass }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.passes:CrossModelTypeCheckPass`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Validate artifact-ref compatibility and cross-surface invariants.

### `polisyos.ir.passes.core.EstimandNormalizationPass` { #polisyos-ir-passes-core-estimandnormalizationpass }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.passes:EstimandNormalizationPass`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Normalize estimand ASTs for semantic dedupe and CAS stability.

### `polisyos.ir.passes.core.RegistryDependencyPass` { #polisyos-ir-passes-core-registrydependencypass }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.passes:RegistryDependencyPass`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compose registry fragments through the shared pass pipeline.

### `polisyos.ir.passes.core.SlotMechanismReachability` { #polisyos-ir-passes-core-slotmechanismreachability }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.passes:SlotMechanismReachability`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Describe the slot/mechanism dependency graph induced by linked Trinity policies.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `orphan_mechanisms` | `list[str]` | `no` | `—` | — |
| `reachable_mechanisms` | `list[str]` | `no` | `—` | — |
| `reachable_slots` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `terminal_slots` | `list[str]` | `no` | `—` | — |
| `unused_registry_slots` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.passes.core.SlotMechanismReachabilityPass` { #polisyos-ir-passes-core-slotmechanismreachabilitypass }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.passes:SlotMechanismReachabilityPass`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compute reachability between linked mechanisms and runtime slots.

### `polisyos.ir.passes.core.TrinityLinkAnalysisPass` { #polisyos-ir-passes-core-trinitylinkanalysispass }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.passes:TrinityLinkAnalysisPass`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Run the Trinity linker through the shared pipeline and cache its result.

### `polisyos.ir.passes.core.UnusedArtifactAnalysisPass` { #polisyos-ir-passes-core-unusedartifactanalysispass }

- Kind: `class`
- Public status: `package_facade`
- Current version: `—`
- Exported from: `polisyos.ir.passes:UnusedArtifactAnalysisPass`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Build the artifact lineage graph and report artifacts unreachable from roots.

### `polisyos.ir.passes.core.UnusedArtifactAnalysisResult` { #polisyos-ir-passes-core-unusedartifactanalysisresult }

- Kind: `pydantic_model`
- Public status: `package_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir.passes:UnusedArtifactAnalysisResult`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Summarize which artifacts are reachable from the declared roots.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `root_artifact_ids` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `unused_artifact_ids` | `list[str]` | `no` | `—` | — |
| `used_artifact_ids` | `list[str]` | `no` | `—` | — |

## Portfolio

### `polisyos.ir.portfolio.InteractionMatrix` { #polisyos-ir-portfolio-interactionmatrix }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:InteractionMatrix`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.portfolio.InteractionType`, `polisyos.ir.portfolio.PolicyInteraction`
- Summary: Matrix-like interaction layer with clamped additive pairwise effects.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `default_coefficient` | `float` | `no` | `1.0` | — |
| `default_interaction` | `polisyos.ir.portfolio.InteractionType` | `no` | `<InteractionType.NEUTRAL: 'neutral'>` | `polisyos.ir.portfolio.InteractionType` |
| `interactions` | `list[polisyos.ir.portfolio.PolicyInteraction]` | `no` | `—` | `polisyos.ir.portfolio.PolicyInteraction` |
| `legacy_max_multiplier` | `float` | `no` | `2.0` | — |
| `legacy_min_multiplier` | `float` | `no` | `0.25` | — |
| `max_pairwise_relative_effect` | `float` | `no` | `0.5` | — |

### `polisyos.ir.portfolio.InteractionMode` { #polisyos-ir-portfolio-interactionmode }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Interaction aggregation mode for portfolio scoring.

| Enum values |
|-------------|
| `pairwise_additive` |
| `multiplicative` |

### `polisyos.ir.portfolio.InteractionType` { #polisyos-ir-portfolio-interactiontype }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:InteractionType`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Qualitative label for how two policies interact in a portfolio.

| Enum values |
|-------------|
| `synergy` |
| `neutral` |
| `cannibalization` |
| `substitution` |
| `conflict` |

### `polisyos.ir.portfolio.PolicyInteraction` { #polisyos-ir-portfolio-policyinteraction }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:PolicyInteraction`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.portfolio.InteractionType`
- Summary: Pairwise interaction metadata between two portfolio policies.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `coefficient` | `float` | `no` | `1.0` | — |
| `evidence_ref` | `str | NoneType` | `no` | `—` | — |
| `interaction_type` | `polisyos.ir.portfolio.InteractionType` | `no` | `<InteractionType.NEUTRAL: 'neutral'>` | `polisyos.ir.portfolio.InteractionType` |
| `notes` | `list[str]` | `no` | `—` | — |
| `policy_a_id` | `str` | `yes` | `—` | — |
| `policy_b_id` | `str` | `yes` | `—` | — |
| `symmetric` | `bool` | `no` | `True` | — |

### `polisyos.ir.portfolio.PolicyPortfolio` { #polisyos-ir-portfolio-policyportfolio }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `1.0`
- Exported from: `polisyos.ir:PolicyPortfolio`
- ABI snapshot: `policy_portfolio` / `schemas/snapshots/ir/policy_portfolio.schema.json`
- Compatibility mode: `—`
- References: `polisyos.ir.governance.policy_spec.PolicySpec`, `polisyos.ir.portfolio.InteractionMatrix`, `polisyos.ir.types.TranslatableString`
- Summary: Bundle a feasible policy set plus pairwise interaction rules for portfolio search.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `description` | `str | NoneType` | `no` | `—` | — |
| `excluded_pairs` | `list[tuple[str, str]]` | `no` | `—` | — |
| `interaction_matrix` | `polisyos.ir.portfolio.InteractionMatrix` | `no` | `—` | `polisyos.ir.portfolio.InteractionMatrix` |
| `labels` | `list[str]` | `no` | `—` | — |
| `max_active_policies` | `int | NoneType` | `no` | `—` | — |
| `name` | `polisyos.ir.types.TranslatableString | NoneType` | `no` | `—` | `polisyos.ir.types.TranslatableString` |
| `notes` | `list[str]` | `no` | `—` | — |
| `policies` | `list[polisyos.ir.governance.policy_spec.PolicySpec]` | `no` | `—` | `polisyos.ir.governance.policy_spec.PolicySpec` |
| `policy_refs` | `list[str]` | `no` | `—` | — |
| `portfolio_id` | `str` | `yes` | `—` | — |
| `problem_frame_ref` | `str | NoneType` | `no` | `—` | — |
| `required_policies` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `total_budget_constraint` | `float | NoneType` | `no` | `—` | — |

## Predicate

### `polisyos.ir.predicate.EdgePredicateSpec` { #polisyos-ir-predicate-edgepredicatespec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Edge predicate spec data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `cardinality` | `str | NoneType` | `no` | `—` | — |
| `dst_entity_type` | `str` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `predicate_id` | `str` | `yes` | `—` | — |
| `src_entity_type` | `str` | `yes` | `—` | — |
| `temporal_validity` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.predicate.PredicateRegistry` { #polisyos-ir-predicate-predicateregistry }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.predicate.EdgePredicateSpec`, `polisyos.ir.predicate.ScalarPredicateSpec`
- Summary: Predicate registry implementation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `edges` | `dict[str, polisyos.ir.predicate.EdgePredicateSpec]` | `no` | `—` | `polisyos.ir.predicate.EdgePredicateSpec` |
| `notes` | `list[str]` | `no` | `—` | — |
| `scalars` | `dict[str, polisyos.ir.predicate.ScalarPredicateSpec]` | `no` | `—` | `polisyos.ir.predicate.ScalarPredicateSpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.predicate.PrivacyPolicyRegistry` { #polisyos-ir-predicate-privacypolicyregistry }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.predicate.PrivacyPolicySpec`
- Summary: Privacy policy registry implementation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `notes` | `list[str]` | `no` | `—` | — |
| `policies` | `dict[str, polisyos.ir.predicate.PrivacyPolicySpec]` | `no` | `—` | `polisyos.ir.predicate.PrivacyPolicySpec` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.predicate.PrivacyPolicySpec` { #polisyos-ir-predicate-privacypolicyspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Privacy policy spec data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `description` | `str | NoneType` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `policy_id` | `str` | `yes` | `—` | — |

### `polisyos.ir.predicate.ScalarPredicateSpec` { #polisyos-ir-predicate-scalarpredicatespec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.units.UnitRef`
- Summary: Scalar predicate spec data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `default_agg` | `str | NoneType` | `no` | `—` | — |
| `default_resample` | `str | NoneType` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `predicate_id` | `str` | `yes` | `—` | — |
| `slot_id` | `str` | `yes` | `—` | — |
| `unit` | `polisyos.ir.kernel.units.UnitRef | NoneType` | `no` | `—` | `polisyos.ir.kernel.units.UnitRef` |
| `value_type` | `str` | `yes` | `—` | — |

## Queries

### `polisyos.ir.queries.ClaimQuery` { #polisyos-ir-queries-claimquery }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.queries.Pagination`, `polisyos.ir.queries.QualityThresholds`, `polisyos.ir.queries.QueryScope`
- Summary: Claim query public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `domain` | `str | NoneType` | `no` | `—` | — |
| `pagination` | `polisyos.ir.queries.Pagination` | `no` | `—` | `polisyos.ir.queries.Pagination` |
| `predicate_id` | `str | NoneType` | `no` | `—` | — |
| `quality` | `polisyos.ir.queries.QualityThresholds` | `no` | `—` | `polisyos.ir.queries.QualityThresholds` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `scope` | `polisyos.ir.queries.QueryScope` | `no` | `—` | `polisyos.ir.queries.QueryScope` |
| `subject_id` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.queries.DataFilter` { #polisyos-ir-queries-datafilter }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Data filter public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `column` | `str` | `yes` | `—` | — |
| `op` | `Literal[==, !=, >, <, >=, <=, in, not_in]` | `yes` | `—` | — |
| `value` | `str | int | bool | Decimal` | `yes` | `—` | — |

### `polisyos.ir.queries.DataViewRequest` { #polisyos-ir-queries-dataviewrequest }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.queries.DataFilter`, `polisyos.ir.queries.Pagination`, `polisyos.ir.queries.QueryScope`
- Summary: Data view request data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `access_tier` | `str | NoneType` | `no` | `—` | — |
| `aggregation` | `str | NoneType` | `no` | `—` | — |
| `filters` | `list[polisyos.ir.queries.DataFilter]` | `no` | `—` | `polisyos.ir.queries.DataFilter` |
| `metrics` | `list[str]` | `yes` | `—` | — |
| `pagination` | `polisyos.ir.queries.Pagination` | `no` | `—` | `polisyos.ir.queries.Pagination` |
| `request_id` | `str` | `yes` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `scope` | `polisyos.ir.queries.QueryScope` | `no` | `—` | `polisyos.ir.queries.QueryScope` |
| `view_type` | `str` | `yes` | `—` | — |

### `polisyos.ir.queries.DocQuery` { #polisyos-ir-queries-docquery }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.queries.Pagination`, `polisyos.ir.queries.QualityThresholds`, `polisyos.ir.queries.QueryScope`
- Summary: Doc query public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `doc_type` | `str | NoneType` | `no` | `—` | — |
| `language` | `str | NoneType` | `no` | `—` | — |
| `pagination` | `polisyos.ir.queries.Pagination` | `no` | `—` | `polisyos.ir.queries.Pagination` |
| `publisher` | `str | NoneType` | `no` | `—` | — |
| `quality` | `polisyos.ir.queries.QualityThresholds` | `no` | `—` | `polisyos.ir.queries.QualityThresholds` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `scope` | `polisyos.ir.queries.QueryScope` | `no` | `—` | `polisyos.ir.queries.QueryScope` |
| `source_types` | `list[str] | NoneType` | `no` | `—` | — |
| `text_contains` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.queries.NormQuery` { #polisyos-ir-queries-normquery }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.queries.Pagination`
- Summary: Norm query public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `effective_at` | `str | NoneType` | `no` | `—` | — |
| `jurisdiction` | `str | NoneType` | `no` | `—` | — |
| `norm_pack_ids` | `list[str] | NoneType` | `no` | `—` | — |
| `pagination` | `polisyos.ir.queries.Pagination` | `no` | `—` | `polisyos.ir.queries.Pagination` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.queries.Pagination` { #polisyos-ir-queries-pagination }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Pagination public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `cursor` | `str | NoneType` | `no` | `—` | — |
| `limit` | `int` | `no` | `100` | — |

### `polisyos.ir.queries.QualityThresholds` { #polisyos-ir-queries-qualitythresholds }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.connectors.QualityTier`, `polisyos.ir.connectors.TrustLevel`
- Summary: Quality thresholds public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `min_confidence` | `Decimal | NoneType` | `no` | `—` | — |
| `min_quality_tier` | `polisyos.ir.connectors.QualityTier | NoneType` | `no` | `—` | `polisyos.ir.connectors.QualityTier` |
| `min_trust_level` | `polisyos.ir.connectors.TrustLevel | NoneType` | `no` | `—` | `polisyos.ir.connectors.TrustLevel` |

### `polisyos.ir.queries.QueryScope` { #polisyos-ir-queries-queryscope }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.queries.ValidTimeRange`
- Summary: Query scope public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `as_of` | `str | NoneType` | `no` | `—` | — |
| `jurisdiction` | `str | NoneType` | `no` | `—` | — |
| `valid_time` | `polisyos.ir.queries.ValidTimeRange | NoneType` | `no` | `—` | `polisyos.ir.queries.ValidTimeRange` |

### `polisyos.ir.queries.ValidTimeRange` { #polisyos-ir-queries-validtimerange }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Valid time range public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `from_` | `str | NoneType` | `no` | `—` | — |
| `to` | `str | NoneType` | `no` | `—` | — |

## Refs

### `polisyos.ir.refs.ABMAlignmentReportRef` { #polisyos-ir-refs-abmalignmentreportref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted ABM-alignment diagnostics consumed during model-selection review.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.abm_alignment_report]` | `no` | `'ir.abm_alignment_report'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.AbstractionCertificateRef` { #polisyos-ir-refs-abstractioncertificateref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted abstraction certificates that justify reduced-state execution.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.abstraction_certificate]` | `no` | `'ir.abstraction_certificate'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.AlignmentReportRef` { #polisyos-ir-refs-alignmentreportref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted alignment reports reviewed by governance and composition passes.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.alignment_report]` | `no` | `'ir.alignment_report'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.ArtifactRefModel` { #polisyos-ir-refs-artifactrefmodel }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Provide the common mapping-compatible base contract for artifact refs.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `str` | `yes` | `—` | — |
| `media_type` | `str` | `yes` | `—` | — |

### `polisyos.ir.refs.BacktestReportRef` { #polisyos-ir-refs-backtestreportref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted backtest reports consumed by Scientist governance and readiness review.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.backtest_report]` | `no` | `'ir.backtest_report'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.BoundsBundleRef` { #polisyos-ir-refs-boundsbundleref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted partial-identification outputs consumed by readiness checks and reporting.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.bounds_bundle]` | `no` | `'ir.bounds_bundle'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.CausalCapabilityContractRef` { #polisyos-ir-refs-causalcapabilitycontractref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for a persisted causal-capability contract emitted by readiness compilation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.causal_capability_contract]` | `no` | `'ir.causal_capability_contract'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.CausalDiscoveryReportRef` { #polisyos-ir-refs-causaldiscoveryreportref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted discovery diagnostics used when selecting or auditing graph structure.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.causal_discovery_report]` | `no` | `'ir.causal_discovery_report'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.CausalEffectReportRef` { #polisyos-ir-refs-causaleffectreportref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted causal-effect estimates consumed by governance, briefs, and downstream runners.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.causal_effect_report]` | `no` | `'ir.causal_effect_report'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.CausalExecutionBundleRef` { #polisyos-ir-refs-causalexecutionbundleref }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:CausalExecutionBundleRef`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Reference a persisted ``CausalExecutionBundle`` produced by Scientist runners.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.causal_execution_bundle]` | `no` | `'ir.causal_execution_bundle'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.CausalGraphModelRef` { #polisyos-ir-refs-causalgraphmodelref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for a persisted causal graph model once discovery or linking has frozen the structure.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.causal_graph_model]` | `no` | `'ir.causal_graph_model'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.CausalModelEnsembleRef` { #polisyos-ir-refs-causalmodelensembleref }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:CausalModelEnsembleRef`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Reference a persisted ``CausalModelEnsemble`` used for structural uncertainty.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.causal_model_ensemble]` | `no` | `'ir.causal_model_ensemble'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.CausalQueryResultRef` { #polisyos-ir-refs-causalqueryresultref }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:CausalQueryResultRef`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Reference a persisted ``CausalQueryResult`` produced by query execution.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.causal_query_result]` | `no` | `'ir.causal_query_result'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.CausalReadinessBundleRef` { #polisyos-ir-refs-causalreadinessbundleref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Reference a persisted ``CausalReadinessBundle`` consumed before execution.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.causal_readiness_bundle]` | `no` | `'ir.causal_readiness_bundle'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.CausalSensitivityResultRef` { #polisyos-ir-refs-causalsensitivityresultref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted sensitivity-analysis output consumed by robustness and governance checks.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.sensitivity_result]` | `no` | `'ir.sensitivity_result'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.CompositionCertificateRef` { #polisyos-ir-refs-compositioncertificateref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted composition certificates once interface checks have succeeded.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.composition_certificate]` | `no` | `'ir.composition_certificate'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.CompositionFailureCardBundleRef` { #polisyos-ir-refs-compositionfailurecardbundleref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted composition failure cards returned to authoring and governance loops.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.composition_failure_card_bundle]` | `no` | `'ir.composition_failure_card_bundle'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.ContextAdaptiveParameterBundleRef` { #polisyos-ir-refs-contextadaptiveparameterbundleref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted context-adapted parameter bundles used by transport and calibration stages.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.context_adaptive_parameter_bundle]` | `no` | `'ir.context_adaptive_parameter_bundle'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.ContinuousTimeQueryRef` { #polisyos-ir-refs-continuoustimequeryref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for a persisted continuous-time causal query prepared for temporal solvers.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.continuous_time_query]` | `no` | `'ir.continuous_time_query'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.CounterfactualResultRef` { #polisyos-ir-refs-counterfactualresultref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Reference to a persisted counterfactual query result artifact.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.counterfactual_result]` | `no` | `'ir.counterfactual_result'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.CrossGraphEvidenceProfileRef` { #polisyos-ir-refs-crossgraphevidenceprofileref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted cross-graph evidence profiles used during graph arbitration.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.cross_graph_evidence_profile]` | `no` | `'ir.cross_graph_evidence_profile'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.DataReadinessReportRef` { #polisyos-ir-refs-datareadinessreportref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted data-readiness reports emitted before execution is allowed to proceed.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.data_readiness_report]` | `no` | `'ir.data_readiness_report'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.DistributionalEffectBundleRef` { #polisyos-ir-refs-distributionaleffectbundleref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted subgroup-effect bundles that feed distributional reporting.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.distributional_effect_bundle]` | `no` | `'ir.distributional_effect_bundle'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.DistributionalReportRef` { #polisyos-ir-refs-distributionalreportref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted distributional-impact reports read by equity and policy-governance workflows.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.distributional_report]` | `no` | `'ir.distributional_report'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.DynamicTreatmentRegimeRef` { #polisyos-ir-refs-dynamictreatmentregimeref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted dynamic treatment regimes consumed by DTR execution workflows.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.dynamic_treatment_regime]` | `no` | `'ir.dynamic_treatment_regime'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.EffectTrajectoryBundleRef` { #polisyos-ir-refs-effecttrajectorybundleref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted effect trajectories used by forecasting and temporal reporting.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.effect_trajectory_bundle]` | `no` | `'ir.effect_trajectory_bundle'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.EstimandASTRef` { #polisyos-ir-refs-estimandastref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for a persisted normalized estimand AST.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.estimand_ast]` | `no` | `'ir.estimand_ast'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.EvidenceBundleRef` { #polisyos-ir-refs-evidencebundleref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: IR-level reference to a fabric evidence bundle artifact.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[fabric.evidence_bundle]` | `no` | `'fabric.evidence_bundle'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.FiniteStateAbstractionMapRef` { #polisyos-ir-refs-finitestateabstractionmapref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted abstraction maps consumed by reduced-state planners.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.finite_state_abstraction_map]` | `no` | `'ir.finite_state_abstraction_map'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.HTEResultRef` { #polisyos-ir-refs-hteresultref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted heterogeneous-treatment-effect results used by subgroup and equity analyses.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.hte_result]` | `no` | `'ir.hte_result'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.InteractionComplexRef` { #polisyos-ir-refs-interactioncomplexref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted interaction-complex artifacts used by interference-aware analysis.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.interaction_complex]` | `no` | `'ir.interaction_complex'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.InterfaceMappingRef` { #polisyos-ir-refs-interfacemappingref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted interface mappings that bridge artifacts across package boundaries.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.interface_mapping]` | `no` | `'ir.interface_mapping'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.InterferenceCertificateRef` { #polisyos-ir-refs-interferencecertificateref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted interference certificates consumed by readiness gates.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.interference_certificate]` | `no` | `'ir.interference_certificate'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.LiteratureCausalPriorRef` { #polisyos-ir-refs-literaturecausalpriorref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted literature priors produced by academic synthesis and consumed by calibration.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.literature_causal_prior]` | `no` | `'ir.literature_causal_prior'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.NCMSpecRef` { #polisyos-ir-refs-ncmspecref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Reference to a persisted NCMSpec artifact.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.ncm_spec]` | `no` | `'ir.ncm_spec'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.NegativeCertificateRef` { #polisyos-ir-refs-negativecertificateref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted negative-control certificates that can block unsafe execution.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.negative_certificate]` | `no` | `'ir.negative_certificate'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.NormativeArbitrationResultRef` { #polisyos-ir-refs-normativearbitrationresultref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted normative-arbitration output consumed by decision synthesis.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.normative_arbitration_result]` | `no` | `'ir.normative_arbitration_result'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.PolicyRecommendationRef` { #polisyos-ir-refs-policyrecommendationref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for a persisted policy recommendation once decision synthesis has frozen the artifact.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.policy_recommendation]` | `no` | `'ir.policy_recommendation'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.ProofBundleRef` { #polisyos-ir-refs-proofbundleref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted identification or proof bundles reviewed by governance and auditors.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.proof_bundle]` | `no` | `'ir.proof_bundle'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.SCMFragmentRef` { #polisyos-ir-refs-scmfragmentref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted SCM fragments produced before composition into a full causal model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.scm_fragment]` | `no` | `'ir.scm_fragment'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.StrategicPayoffTableRef` { #polisyos-ir-refs-strategicpayofftableref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted payoff tables consumed by strategic-response analyzers.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.strategic_payoff_table]` | `no` | `'ir.strategic_payoff_table'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.StrategicResponseBundleRef` { #polisyos-ir-refs-strategicresponsebundleref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted strategic-response bundles reviewed by governance.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.strategic_response_bundle]` | `no` | `'ir.strategic_response_bundle'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.StrategicSCMRef` { #polisyos-ir-refs-strategicscmref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted strategic SCMs consumed by strategic-response execution.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.strategic_scm]` | `no` | `'ir.strategic_scm'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.StructuralCausalModelSpecRef` { #polisyos-ir-refs-structuralcausalmodelspecref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for a persisted structural causal model spec consumed by query planning and execution.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.structural_causal_model_spec]` | `no` | `'ir.structural_causal_model_spec'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.TemporalInterventionTrajectoryRef` { #polisyos-ir-refs-temporalinterventiontrajectoryref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted intervention trajectories consumed by temporal execution runners.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.temporal_intervention_trajectory]` | `no` | `'ir.temporal_intervention_trajectory'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.TransportabilityResultRef` { #polisyos-ir-refs-transportabilityresultref }

- Kind: `pydantic_model`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:TransportabilityResultRef`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Reference a persisted ``TransportabilityResult`` consumed by readiness gates.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.transportability_result]` | `no` | `'ir.transportability_result'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.TwinNetworkResultRef` { #polisyos-ir-refs-twinnetworkresultref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted twin-network results used in counterfactual analysis.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.twin_network_result]` | `no` | `'ir.twin_network_result'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.UncertaintyEnvelopeRef` { #polisyos-ir-refs-uncertaintyenveloperef }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for a persisted uncertainty envelope produced by estimators and read by reporting layers.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.uncertainty_envelope]` | `no` | `'ir.uncertainty_envelope'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

### `polisyos.ir.refs.VariableAlignmentCertificateRef` { #polisyos-ir-refs-variablealignmentcertificateref }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.artifacts.contracts.ArtifactID`
- Summary: Stable handle for persisted variable-alignment certificates consumed by merge and reuse pipelines.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `artifact_id` | `polisyos.ir.artifacts.contracts.ArtifactID` | `yes` | `—` | `polisyos.ir.artifacts.contracts.ArtifactID` |
| `kind` | `Literal[ir.variable_alignment_certificate]` | `no` | `'ir.variable_alignment_certificate'` | — |
| `media_type` | `Literal[application/json]` | `no` | `'application/json'` | — |

## Registry_Fragments

### `polisyos.ir.registry_fragments.ActorRegistry` { #polisyos-ir-registry-fragments-actorregistry }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.registry_fragments.ActorTypeSpec`
- Summary: Actor registry implementation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `actor_types` | `dict[str, polisyos.ir.registry_fragments.ActorTypeSpec]` | `no` | `—` | `polisyos.ir.registry_fragments.ActorTypeSpec` |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.registry_fragments.ActorTypeSpec` { #polisyos-ir-registry-fragments-actortypespec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Actor type spec data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `actor_type_id` | `str` | `yes` | `—` | — |
| `description` | `str | NoneType` | `no` | `—` | — |
| `name` | `str | NoneType` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.registry_fragments.ActorsFragment` { #polisyos-ir-registry-fragments-actorsfragment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.registry_fragments.ActorRegistry`, `polisyos.ir.registry_fragments.RegistryFragmentMeta`
- Summary: Actors fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[actors]` | `no` | `'actors'` | — |
| `meta` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` | `yes` | `—` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` |
| `payload` | `polisyos.ir.registry_fragments.ActorRegistry` | `yes` | `—` | `polisyos.ir.registry_fragments.ActorRegistry` |

### `polisyos.ir.registry_fragments.ComposePolicy` { #polisyos-ir-registry-fragments-composepolicy }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Compose policy data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `mode` | `Literal[error_on_conflict, prefer_higher_priority]` | `no` | `'error_on_conflict'` | — |

### `polisyos.ir.registry_fragments.ConceptRegistry` { #polisyos-ir-registry-fragments-conceptregistry }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.registry_fragments.ConceptSpec`
- Summary: Concept registry implementation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `concepts` | `dict[str, polisyos.ir.registry_fragments.ConceptSpec]` | `no` | `—` | `polisyos.ir.registry_fragments.ConceptSpec` |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.registry_fragments.ConceptSpec` { #polisyos-ir-registry-fragments-conceptspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Concept spec data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `concept_id` | `str` | `yes` | `—` | — |
| `description` | `str | NoneType` | `no` | `—` | — |
| `name` | `str | NoneType` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.registry_fragments.ConceptsFragment` { #polisyos-ir-registry-fragments-conceptsfragment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.registry_fragments.ConceptRegistry`, `polisyos.ir.registry_fragments.RegistryFragmentMeta`
- Summary: Concepts fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[concepts]` | `no` | `'concepts'` | — |
| `meta` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` | `yes` | `—` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` |
| `payload` | `polisyos.ir.registry_fragments.ConceptRegistry` | `yes` | `—` | `polisyos.ir.registry_fragments.ConceptRegistry` |

### `polisyos.ir.registry_fragments.ConstraintsFragment` { #polisyos-ir-registry-fragments-constraintsfragment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.constraints.ConstraintRegistry`, `polisyos.ir.registry_fragments.RegistryFragmentMeta`
- Summary: Constraints fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[constraints]` | `no` | `'constraints'` | — |
| `meta` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` | `yes` | `—` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` |
| `payload` | `polisyos.ir.kernel.constraints.ConstraintRegistry` | `yes` | `—` | `polisyos.ir.kernel.constraints.ConstraintRegistry` |

### `polisyos.ir.registry_fragments.GeoAreaSpec` { #polisyos-ir-registry-fragments-geoareaspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Geo area spec data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `geo_id` | `str` | `yes` | `—` | — |
| `kind` | `str | NoneType` | `no` | `—` | — |
| `name` | `str | NoneType` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.registry_fragments.GeoFragment` { #polisyos-ir-registry-fragments-geofragment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.registry_fragments.GeoRegistry`, `polisyos.ir.registry_fragments.RegistryFragmentMeta`
- Summary: Geo fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[geo]` | `no` | `'geo'` | — |
| `meta` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` | `yes` | `—` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` |
| `payload` | `polisyos.ir.registry_fragments.GeoRegistry` | `yes` | `—` | `polisyos.ir.registry_fragments.GeoRegistry` |

### `polisyos.ir.registry_fragments.GeoRegistry` { #polisyos-ir-registry-fragments-georegistry }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.registry_fragments.GeoAreaSpec`
- Summary: Geo registry implementation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `areas` | `dict[str, polisyos.ir.registry_fragments.GeoAreaSpec]` | `no` | `—` | `polisyos.ir.registry_fragments.GeoAreaSpec` |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.registry_fragments.MechanismsFragment` { #polisyos-ir-registry-fragments-mechanismsfragment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.mechanisms.MechanismTypeRegistry`, `polisyos.ir.registry_fragments.RegistryFragmentMeta`
- Summary: Mechanisms fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[mechanisms]` | `no` | `'mechanisms'` | — |
| `meta` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` | `yes` | `—` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` |
| `payload` | `polisyos.ir.kernel.mechanisms.MechanismTypeRegistry` | `yes` | `—` | `polisyos.ir.kernel.mechanisms.MechanismTypeRegistry` |

### `polisyos.ir.registry_fragments.MergeRulesFragment` { #polisyos-ir-registry-fragments-mergerulesfragment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.merge_rules.MergeRuleRegistry`, `polisyos.ir.registry_fragments.RegistryFragmentMeta`
- Summary: Merge rules fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[merge_rules]` | `no` | `'merge_rules'` | — |
| `meta` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` | `yes` | `—` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` |
| `payload` | `polisyos.ir.kernel.merge_rules.MergeRuleRegistry` | `yes` | `—` | `polisyos.ir.kernel.merge_rules.MergeRuleRegistry` |

### `polisyos.ir.registry_fragments.MetricsFragment` { #polisyos-ir-registry-fragments-metricsfragment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.metrics.MetricRegistry`, `polisyos.ir.registry_fragments.RegistryFragmentMeta`
- Summary: Metrics fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[metrics]` | `no` | `'metrics'` | — |
| `meta` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` | `yes` | `—` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` |
| `payload` | `polisyos.ir.kernel.metrics.MetricRegistry` | `yes` | `—` | `polisyos.ir.kernel.metrics.MetricRegistry` |

### `polisyos.ir.registry_fragments.PredicatesFragment` { #polisyos-ir-registry-fragments-predicatesfragment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.predicate.PredicateRegistry`, `polisyos.ir.registry_fragments.RegistryFragmentMeta`
- Summary: Predicates fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[predicates]` | `no` | `'predicates'` | — |
| `meta` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` | `yes` | `—` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` |
| `payload` | `polisyos.ir.predicate.PredicateRegistry` | `yes` | `—` | `polisyos.ir.predicate.PredicateRegistry` |

### `polisyos.ir.registry_fragments.PrivacyFragment` { #polisyos-ir-registry-fragments-privacyfragment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.predicate.PrivacyPolicyRegistry`, `polisyos.ir.registry_fragments.RegistryFragmentMeta`
- Summary: Privacy fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[privacy]` | `no` | `'privacy'` | — |
| `meta` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` | `yes` | `—` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` |
| `payload` | `polisyos.ir.predicate.PrivacyPolicyRegistry` | `yes` | `—` | `polisyos.ir.predicate.PrivacyPolicyRegistry` |

### `polisyos.ir.registry_fragments.RegistryBundle` { #polisyos-ir-registry-fragments-registrybundle }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.constraints.ConstraintRegistry`, `polisyos.ir.kernel.mechanisms.MechanismTypeRegistry`, `polisyos.ir.kernel.merge_rules.MergeRuleRegistry`, `polisyos.ir.kernel.metrics.MetricRegistry`, `polisyos.ir.kernel.selector_fields.SelectorFieldRegistry`, `polisyos.ir.kernel.slots.SlotRegistry`, `polisyos.ir.kernel.trust.TrustRegistry`, `polisyos.ir.kernel.units.UnitsRegistry`, `polisyos.ir.predicate.PredicateRegistry`, `polisyos.ir.predicate.PrivacyPolicyRegistry`, `polisyos.ir.registry_fragments.ActorRegistry`, `polisyos.ir.registry_fragments.ConceptRegistry`, `polisyos.ir.registry_fragments.GeoRegistry`, `polisyos.ir.registry_fragments.TimeAxisRegistry`
- Summary: Registry bundle data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `actors` | `polisyos.ir.registry_fragments.ActorRegistry | NoneType` | `no` | `—` | `polisyos.ir.registry_fragments.ActorRegistry` |
| `concepts` | `polisyos.ir.registry_fragments.ConceptRegistry | NoneType` | `no` | `—` | `polisyos.ir.registry_fragments.ConceptRegistry` |
| `constraints` | `polisyos.ir.kernel.constraints.ConstraintRegistry | NoneType` | `no` | `—` | `polisyos.ir.kernel.constraints.ConstraintRegistry` |
| `geo` | `polisyos.ir.registry_fragments.GeoRegistry | NoneType` | `no` | `—` | `polisyos.ir.registry_fragments.GeoRegistry` |
| `mechanisms` | `polisyos.ir.kernel.mechanisms.MechanismTypeRegistry | NoneType` | `no` | `—` | `polisyos.ir.kernel.mechanisms.MechanismTypeRegistry` |
| `merge_rules` | `polisyos.ir.kernel.merge_rules.MergeRuleRegistry | NoneType` | `no` | `—` | `polisyos.ir.kernel.merge_rules.MergeRuleRegistry` |
| `metrics` | `polisyos.ir.kernel.metrics.MetricRegistry | NoneType` | `no` | `—` | `polisyos.ir.kernel.metrics.MetricRegistry` |
| `notes` | `list[str]` | `no` | `—` | — |
| `predicates` | `polisyos.ir.predicate.PredicateRegistry | NoneType` | `no` | `—` | `polisyos.ir.predicate.PredicateRegistry` |
| `privacy` | `polisyos.ir.predicate.PrivacyPolicyRegistry | NoneType` | `no` | `—` | `polisyos.ir.predicate.PrivacyPolicyRegistry` |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `selector_fields` | `polisyos.ir.kernel.selector_fields.SelectorFieldRegistry | NoneType` | `no` | `—` | `polisyos.ir.kernel.selector_fields.SelectorFieldRegistry` |
| `slots` | `polisyos.ir.kernel.slots.SlotRegistry | NoneType` | `no` | `—` | `polisyos.ir.kernel.slots.SlotRegistry` |
| `time` | `polisyos.ir.registry_fragments.TimeAxisRegistry | NoneType` | `no` | `—` | `polisyos.ir.registry_fragments.TimeAxisRegistry` |
| `trust` | `polisyos.ir.kernel.trust.TrustRegistry | NoneType` | `no` | `—` | `polisyos.ir.kernel.trust.TrustRegistry` |
| `units` | `polisyos.ir.kernel.units.UnitsRegistry | NoneType` | `no` | `—` | `polisyos.ir.kernel.units.UnitsRegistry` |

### `polisyos.ir.registry_fragments.RegistryComposeRequest` { #polisyos-ir-registry-fragments-registrycomposerequest }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.registry_fragments.ActorsFragment`, `polisyos.ir.registry_fragments.ComposePolicy`, `polisyos.ir.registry_fragments.ConceptsFragment`, `polisyos.ir.registry_fragments.ConstraintsFragment`, `polisyos.ir.registry_fragments.GeoFragment`, `polisyos.ir.registry_fragments.MechanismsFragment`, `polisyos.ir.registry_fragments.MergeRulesFragment`, `polisyos.ir.registry_fragments.MetricsFragment`, `polisyos.ir.registry_fragments.PredicatesFragment`, `polisyos.ir.registry_fragments.PrivacyFragment`, `polisyos.ir.registry_fragments.RegistryBundle`, `polisyos.ir.registry_fragments.SelectorFieldsFragment`, `polisyos.ir.registry_fragments.SlotsFragment`, `polisyos.ir.registry_fragments.TimeFragment`, `polisyos.ir.registry_fragments.TrustFragment`, `polisyos.ir.registry_fragments.UnitsFragment`
- Summary: Registry compose request data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `base_registries` | `polisyos.ir.registry_fragments.RegistryBundle | NoneType` | `no` | `—` | `polisyos.ir.registry_fragments.RegistryBundle` |
| `fragments` | `list[polisyos.ir.registry_fragments.UnitsFragment | polisyos.ir.registry_fragments.TrustFragment | polisyos.ir.registry_fragments.PredicatesFragment | polisyos.ir.registry_fragments.PrivacyFragment | polisyos.ir.registry_fragments.MetricsFragment | polisyos.ir.registry_fragments.MechanismsFragment | polisyos.ir.registry_fragments.SlotsFragment | polisyos.ir.registry_fragments.SelectorFieldsFragment | polisyos.ir.registry_fragments.MergeRulesFragment | polisyos.ir.registry_fragments.ConstraintsFragment | polisyos.ir.registry_fragments.TimeFragment | polisyos.ir.registry_fragments.GeoFragment | polisyos.ir.registry_fragments.ActorsFragment | polisyos.ir.registry_fragments.ConceptsFragment]` | `yes` | `—` | `polisyos.ir.registry_fragments.ActorsFragment`, `polisyos.ir.registry_fragments.ConceptsFragment`, `polisyos.ir.registry_fragments.ConstraintsFragment`, `polisyos.ir.registry_fragments.GeoFragment`, `polisyos.ir.registry_fragments.MechanismsFragment`, `polisyos.ir.registry_fragments.MergeRulesFragment`, `polisyos.ir.registry_fragments.MetricsFragment`, `polisyos.ir.registry_fragments.PredicatesFragment`, `polisyos.ir.registry_fragments.PrivacyFragment`, `polisyos.ir.registry_fragments.SelectorFieldsFragment`, `polisyos.ir.registry_fragments.SlotsFragment`, `polisyos.ir.registry_fragments.TimeFragment`, `polisyos.ir.registry_fragments.TrustFragment`, `polisyos.ir.registry_fragments.UnitsFragment` |
| `policy` | `polisyos.ir.registry_fragments.ComposePolicy` | `no` | `—` | `polisyos.ir.registry_fragments.ComposePolicy` |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.registry_fragments.RegistryComposeResult` { #polisyos-ir-registry-fragments-registrycomposeresult }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.registry_fragments.RegistryBundle`, `polisyos.ir.registry_fragments.RegistryConflict`
- Summary: Registry compose result data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `applied_fragments` | `list[str]` | `no` | `—` | — |
| `composed` | `polisyos.ir.registry_fragments.RegistryBundle | NoneType` | `no` | `—` | `polisyos.ir.registry_fragments.RegistryBundle` |
| `conflicts` | `list[polisyos.ir.registry_fragments.RegistryConflict]` | `no` | `—` | `polisyos.ir.registry_fragments.RegistryConflict` |
| `deterministic_hash` | `str | NoneType` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |
| `warnings` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.registry_fragments.RegistryConflict` { #polisyos-ir-registry-fragments-registryconflict }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Registry conflict public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `conflict_kind` | `Literal[duplicate_identical, duplicate_different, invalid_item, reserved_prefix, dependency_missing, dependency_cycle, dependency_unresolved]` | `yes` | `—` | — |
| `item_key` | `str` | `yes` | `—` | — |
| `left_fragment_id` | `str | NoneType` | `no` | `—` | — |
| `left_value_hash` | `str | NoneType` | `no` | `—` | — |
| `message` | `str | NoneType` | `no` | `—` | — |
| `registry_kind` | `str` | `yes` | `—` | — |
| `resolution` | `Literal[none, chose_left, chose_right, merged]` | `no` | `'none'` | — |
| `right_fragment_id` | `str | NoneType` | `no` | `—` | — |
| `right_value_hash` | `str | NoneType` | `no` | `—` | — |

### `polisyos.ir.registry_fragments.RegistryFragmentMeta` { #polisyos-ir-registry-fragments-registryfragmentmeta }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Registry fragment meta public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `depends_on` | `list[str]` | `no` | `—` | — |
| `fragment_id` | `str` | `yes` | `—` | — |
| `namespace` | `str` | `yes` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |
| `priority` | `int` | `no` | `0` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.registry_fragments.SelectorFieldsFragment` { #polisyos-ir-registry-fragments-selectorfieldsfragment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.selector_fields.SelectorFieldRegistry`, `polisyos.ir.registry_fragments.RegistryFragmentMeta`
- Summary: Selector fields fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[selector_fields]` | `no` | `'selector_fields'` | — |
| `meta` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` | `yes` | `—` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` |
| `payload` | `polisyos.ir.kernel.selector_fields.SelectorFieldRegistry` | `yes` | `—` | `polisyos.ir.kernel.selector_fields.SelectorFieldRegistry` |

### `polisyos.ir.registry_fragments.SlotsFragment` { #polisyos-ir-registry-fragments-slotsfragment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.slots.SlotRegistry`, `polisyos.ir.registry_fragments.RegistryFragmentMeta`
- Summary: Slots fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[slots]` | `no` | `'slots'` | — |
| `meta` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` | `yes` | `—` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` |
| `payload` | `polisyos.ir.kernel.slots.SlotRegistry` | `yes` | `—` | `polisyos.ir.kernel.slots.SlotRegistry` |

### `polisyos.ir.registry_fragments.TimeAxisRegistry` { #polisyos-ir-registry-fragments-timeaxisregistry }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `1.0`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.registry_fragments.TimeAxisSpec`
- Summary: Time axis registry implementation.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `axes` | `dict[str, polisyos.ir.registry_fragments.TimeAxisSpec]` | `no` | `—` | `polisyos.ir.registry_fragments.TimeAxisSpec` |
| `notes` | `list[str]` | `no` | `—` | — |
| `schema_version` | `str` | `no` | `'1.0'` | — |

### `polisyos.ir.registry_fragments.TimeAxisSpec` { #polisyos-ir-registry-fragments-timeaxisspec }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Time axis spec data model.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `axis_id` | `str` | `yes` | `—` | — |
| `description` | `str | NoneType` | `no` | `—` | — |
| `notes` | `list[str]` | `no` | `—` | — |

### `polisyos.ir.registry_fragments.TimeFragment` { #polisyos-ir-registry-fragments-timefragment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.registry_fragments.RegistryFragmentMeta`, `polisyos.ir.registry_fragments.TimeAxisRegistry`
- Summary: Time fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[time]` | `no` | `'time'` | — |
| `meta` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` | `yes` | `—` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` |
| `payload` | `polisyos.ir.registry_fragments.TimeAxisRegistry` | `yes` | `—` | `polisyos.ir.registry_fragments.TimeAxisRegistry` |

### `polisyos.ir.registry_fragments.TrustFragment` { #polisyos-ir-registry-fragments-trustfragment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.trust.TrustRegistry`, `polisyos.ir.registry_fragments.RegistryFragmentMeta`
- Summary: Trust fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[trust]` | `no` | `'trust'` | — |
| `meta` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` | `yes` | `—` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` |
| `payload` | `polisyos.ir.kernel.trust.TrustRegistry` | `yes` | `—` | `polisyos.ir.kernel.trust.TrustRegistry` |

### `polisyos.ir.registry_fragments.UnitsFragment` { #polisyos-ir-registry-fragments-unitsfragment }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: `polisyos.ir.kernel.units.UnitsRegistry`, `polisyos.ir.registry_fragments.RegistryFragmentMeta`
- Summary: Units fragment public type.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `kind` | `Literal[units]` | `no` | `'units'` | — |
| `meta` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` | `yes` | `—` | `polisyos.ir.registry_fragments.RegistryFragmentMeta` |
| `payload` | `polisyos.ir.kernel.units.UnitsRegistry` | `yes` | `—` | `polisyos.ir.kernel.units.UnitsRegistry` |

## Schema_Catalog

### `polisyos.ir.schema_catalog.IRExportInfo` { #polisyos-ir-schema-catalog-irexportinfo }

- Kind: `dataclass`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:IRExportInfo`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: One exported symbol from a package facade.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `package` | `str` | `yes` | `—` | — |
| `export_name` | `str` | `yes` | `—` | — |
| `target_fqn` | `str` | `yes` | `—` | — |

### `polisyos.ir.schema_catalog.IRFieldInfo` { #polisyos-ir-schema-catalog-irfieldinfo }

- Kind: `dataclass`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:IRFieldInfo`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Structured field metadata exposed by the reflection catalog.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `name` | `str` | `yes` | `—` | — |
| `annotation` | `str` | `yes` | `—` | — |
| `required` | `bool` | `yes` | `—` | — |
| `default` | `str | None` | `yes` | `—` | — |
| `references` | `tuple[str, ...]` | `no` | `()` | — |

### `polisyos.ir.schema_catalog.IRPublicStatus` { #polisyos-ir-schema-catalog-irpublicstatus }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:IRPublicStatus`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Describe how a symbol becomes part of the supported IR surface.

| Enum values |
|-------------|
| `root_facade` |
| `package_facade` |
| `snapshot_only` |
| `internal` |

### `polisyos.ir.schema_catalog.IRSchemaCatalog` { #polisyos-ir-schema-catalog-irschemacatalog }

- Kind: `dataclass`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:IRSchemaCatalog`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Snapshot of the current importable IR type surface.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `types` | `tuple[IRTypeInfo, ...]` | `yes` | `—` | — |
| `exports` | `tuple[IRExportInfo, ...]` | `yes` | `—` | — |

### `polisyos.ir.schema_catalog.IRTypeInfo` { #polisyos-ir-schema-catalog-irtypeinfo }

- Kind: `dataclass`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:IRTypeInfo`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Catalog entry for one IR class or enum.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `name` | `str` | `yes` | `—` | — |
| `qualname` | `str` | `yes` | `—` | — |
| `fqn` | `str` | `yes` | `—` | — |
| `module` | `str` | `yes` | `—` | — |
| `kind` | `IRTypeKind` | `yes` | `—` | — |
| `schema_version` | `str | None` | `yes` | `—` | — |
| `public_status` | `IRPublicStatus` | `yes` | `—` | — |
| `exported_from` | `tuple[str, ...]` | `yes` | `—` | — |
| `docs_link` | `str` | `yes` | `—` | — |
| `summary` | `str | None` | `yes` | `—` | — |
| `fields` | `tuple[IRFieldInfo, ...]` | `no` | `()` | — |
| `refs` | `tuple[str, ...]` | `no` | `()` | — |
| `enum_values` | `tuple[str, ...]` | `no` | `()` | — |
| `abi_key` | `str | None` | `no` | `None` | — |
| `abi_schema_file` | `str | None` | `no` | `None` | — |
| `abi_priority` | `str | None` | `no` | `None` | — |
| `compat_mode` | `CompatibilityMode | None` | `no` | `None` | — |
| `compat_readable_versions` | `tuple[str, ...]` | `no` | `()` | — |
| `compat_writable_versions` | `tuple[str, ...]` | `no` | `()` | — |

### `polisyos.ir.schema_catalog.IRTypeKind` { #polisyos-ir-schema-catalog-irtypekind }

- Kind: `enum`
- Public status: `root_facade`
- Current version: `—`
- Exported from: `polisyos.ir:IRTypeKind`
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Classify the structural shape of one IR symbol.

| Enum values |
|-------------|
| `pydantic_model` |
| `root_model` |
| `enum` |
| `dataclass` |
| `protocol` |
| `class` |

## Types

### `polisyos.ir.types.EntityType` { #polisyos-ir-types-entitytype }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Типы агентов и объектов в системе.

| Enum values |
|-------------|
| `agent` |
| `resource` |
| `infrastructure` |
| `environment` |

### `polisyos.ir.types.OptimizationDirection` { #polisyos-ir-types-optimizationdirection }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Куда двигать метрику.

| Enum values |
|-------------|
| `maximize` |
| `minimize` |
| `maintain_range` |

### `polisyos.ir.types.SelectorOperator` { #polisyos-ir-types-selectoroperator }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Разрешенные операторы для TargetSelector (AST).

| Enum values |
|-------------|
| `==` |
| `!=` |
| `>` |
| `<` |
| `>=` |
| `<=` |
| `in` |
| `not_in` |
| `between` |
| `contains` |

### `polisyos.ir.types.TimeFrequency` { #polisyos-ir-types-timefrequency }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Единицы времени для симуляции.

| Enum values |
|-------------|
| `M` |
| `Q` |
| `Y` |

### `polisyos.ir.types.TimeUnit` { #polisyos-ir-types-timeunit }

- Kind: `enum`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Единицы времени в IR (человеческий формат).

| Enum values |
|-------------|
| `month` |
| `quarter` |
| `year` |

### `polisyos.ir.types.TranslatableString` { #polisyos-ir-types-translatablestring }

- Kind: `pydantic_model`
- Public status: `internal`
- Current version: `—`
- Exported from: —
- ABI snapshot: `—` / `—`
- Compatibility mode: `—`
- References: —
- Summary: Мультиязычная строка.

| Field | Type | Required | Default | IR refs |
|-------|------|----------|---------|---------|
| `en` | `str` | `yes` | `—` | — |
| `ru` | `str | NoneType` | `no` | `—` | — |
| `ua` | `str` | `yes` | `—` | — |
