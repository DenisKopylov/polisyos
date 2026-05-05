from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.dynamic_regime import (
    CausalTranslationCertificate,
    CausalTranslationCertificateStatus,
    ContinuousTimeQuery,
    DynamicTreatmentRegime,
    EffectTrajectoryBundle,
    InterventionInterpolationPolicy,
    RegimeRule,
    RuntimeSupportStatus,
    StrategicAdaptationMode,
    TemporalIdentificationCertificate,
    TemporalIdentificationTheoremFamily,
    TemporalInterventionSemantics,
    TemporalInterventionTrajectory,
    TemporalLawObject,
    TemporalObservabilityRegime,
    TemporalPathRepresentation,
    TemporalQueryMode,
    TemporalSamplingScheme,
    TemporalTargetFunctional,
    load_continuous_time_query,
    load_dynamic_treatment_regime,
    load_effect_trajectory_bundle,
    load_temporal_identification_certificate,
    load_temporal_intervention_trajectory,
    persist_continuous_time_query,
    persist_dynamic_treatment_regime,
    persist_effect_trajectory_bundle,
    persist_temporal_identification_certificate,
    persist_temporal_intervention_trajectory,
)
from polisyos.ir.analytics.rough_path_semantics import (
    RoughPathGraphCriterion,
    RoughPathInterventionType,
    RoughPathTopology,
    TemporalPathSemanticsScope,
)
from polisyos.ir.refs import (
    ArtifactRefModel,
    ContinuousTimeQueryRef,
    DynamicTreatmentRegimeRef,
    EffectTrajectoryBundleRef,
    RoughPathInterventionCertificateRef,
    TemporalIdentificationCertificateRef,
    TemporalInterventionTrajectoryRef,
)
from pydantic import ValidationError


def _artifact_id(ch: str) -> str:
    return f"sha256:{ch * 64}"


def _artifact_ref(ch: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=_artifact_id(ch),
        kind=kind,
        media_type="application/json",
    )


def _rough_path_certificate_ref(ch: str = "f") -> RoughPathInterventionCertificateRef:
    return RoughPathInterventionCertificateRef(artifact_id=_artifact_id(ch))


def _query(
    *,
    sampling_scheme: TemporalSamplingScheme = TemporalSamplingScheme.REGULAR_GRID,
    time_scale: str = "days",
    horizon_start: float = 0.0,
    horizon_end: float = 30.0,
    target_functional: TemporalTargetFunctional = TemporalTargetFunctional.EFFECT_PATH,
    metadata: dict[str, object] | None = None,
) -> ContinuousTimeQuery:
    return ContinuousTimeQuery(
        intervention_trajectory_ref=_artifact_ref("a", kind="test.intervention_trajectory"),
        outcome_process="employment_rate",
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        target_functional=target_functional,
        sampling_scheme=sampling_scheme,
        time_scale=time_scale,
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        metadata=dict(metadata or {}),
    )


def _bundle(
    *,
    query_ref: ContinuousTimeQueryRef | None = None,
    path_representation: TemporalPathRepresentation = TemporalPathRepresentation.LINEAR_SDE,
    identification_certificate_ref: TemporalIdentificationCertificateRef | None = None,
    discretization_error: float | None = 0.05,
    discretization_note: str | None = None,
    continuous_time_degraded: bool = False,
    metadata: dict[str, object] | None = None,
) -> EffectTrajectoryBundle:
    return EffectTrajectoryBundle(
        query_ref=query_ref or ContinuousTimeQueryRef(artifact_id=_artifact_id("b")),
        trajectory_ref=_artifact_ref("c", kind="test.trajectory"),
        confidence_band_ref=_artifact_ref("d", kind="test.confidence_band"),
        solver_diagnostics_ref=_artifact_ref("e", kind="test.solver_diagnostics"),
        identification_certificate_ref=identification_certificate_ref,
        discretization_error=discretization_error,
        discretization_note=discretization_note,
        path_representation=path_representation,
        solver_family="euler_maruyama",
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        strategic_adaptation_mode=StrategicAdaptationMode.ABSENT,
        continuous_time_degraded=continuous_time_degraded,
        metadata=dict(metadata or {}),
    )


def _intervention() -> TemporalInterventionTrajectory:
    return TemporalInterventionTrajectory(
        time_points=(0.0, 10.0, 20.0, 30.0),
        values=(0.0, 1.0, 1.0, 1.0),
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
    )


def _identification_certificate(
    *,
    theorem_family: TemporalIdentificationTheoremFamily = (
        TemporalIdentificationTheoremFamily.NSDE_FIXED_OBSERVED_CHANNEL_V1
    ),
) -> TemporalIdentificationCertificate:
    if theorem_family is TemporalIdentificationTheoremFamily.LOCAL_INDEPENDENCE_WEIGHTING_V1:
        return TemporalIdentificationCertificate(
            theorem_family=theorem_family,
            identified_functionals=(
                TemporalTargetFunctional.CUMULATIVE_INCIDENCE,
                TemporalTargetFunctional.SURVIVAL_CURVE,
            ),
            intervention_semantics=TemporalInterventionSemantics.INTENSITY_REPLACEMENT,
            observability_regime=TemporalObservabilityRegime.OBSERVED_FILTRATION,
            law_object=TemporalLawObject.INTENSITY_COMPENSATOR,
            assumptions=("causal_validity_intensity_replacement", "independent_censoring_local"),
        )
    if theorem_family is TemporalIdentificationTheoremFamily.NCDE_FIXED_OBSERVED_CHANNEL_V1:
        return TemporalIdentificationCertificate(
            theorem_family=theorem_family,
            identified_functionals=(
                TemporalTargetFunctional.EFFECT_PATH,
                TemporalTargetFunctional.INTEGRAL_EFFECT,
            ),
            intervention_semantics=TemporalInterventionSemantics.SURGICAL_REPLACEMENT,
            observability_regime=TemporalObservabilityRegime.FULL_STATE,
            law_object=TemporalLawObject.CANONICAL_CONTROL_PATH,
            canonical_control_required=True,
            control_canonicalization=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
            assumptions=("full_state_observability", "canonical_control_path"),
        )
    return TemporalIdentificationCertificate(
        theorem_family=theorem_family,
        identified_functionals=(
            TemporalTargetFunctional.EFFECT_PATH,
            TemporalTargetFunctional.INTEGRAL_EFFECT,
        ),
        intervention_semantics=TemporalInterventionSemantics.SURGICAL_REPLACEMENT,
        observability_regime=TemporalObservabilityRegime.FULL_STATE,
        law_object=TemporalLawObject.SEMIMARTINGALE_CHARACTERISTICS,
        assumptions=("full_state_observability", "weak_uniqueness_after_intervention"),
    )


def _identification_scope(
    *,
    theorem_family: TemporalIdentificationTheoremFamily = (
        TemporalIdentificationTheoremFamily.NSDE_FIXED_OBSERVED_CHANNEL_V1
    ),
) -> dict[str, object]:
    if theorem_family is TemporalIdentificationTheoremFamily.NCDE_FIXED_OBSERVED_CHANNEL_V1:
        return {
            "theorem_family": theorem_family.value,
            "identified_functionals": [
                TemporalTargetFunctional.EFFECT_PATH.value,
                TemporalTargetFunctional.INTEGRAL_EFFECT.value,
            ],
            "intervention_semantics": TemporalInterventionSemantics.SURGICAL_REPLACEMENT.value,
            "observability_regime": TemporalObservabilityRegime.FULL_STATE.value,
            "law_object": TemporalLawObject.CANONICAL_CONTROL_PATH.value,
            "law_invariant": True,
            "canonical_control_required": True,
            "control_canonicalization": InterventionInterpolationPolicy.PIECEWISE_CONSTANT.value,
            "support_status": "on_support",
            "query_mode": TemporalQueryMode.FIXED_INTERVENTION.value,
            "sampling_scheme": TemporalSamplingScheme.REGULAR_GRID.value,
            "target_functional": TemporalTargetFunctional.EFFECT_PATH.value,
            "interpolation_policy": InterventionInterpolationPolicy.PIECEWISE_CONSTANT.value,
            "strategic_adaptation_mode": StrategicAdaptationMode.ABSENT.value,
            "scope_covered": True,
            "tree_like_invariant_estimand": False,
        }
    return {
        "theorem_family": theorem_family.value,
        "identified_functionals": [
            TemporalTargetFunctional.EFFECT_PATH.value,
            TemporalTargetFunctional.INTEGRAL_EFFECT.value,
        ],
        "intervention_semantics": TemporalInterventionSemantics.SURGICAL_REPLACEMENT.value,
        "observability_regime": TemporalObservabilityRegime.FULL_STATE.value,
        "law_object": TemporalLawObject.SEMIMARTINGALE_CHARACTERISTICS.value,
        "law_invariant": True,
        "canonical_control_required": False,
        "control_canonicalization": None,
        "support_status": "on_support",
        "query_mode": TemporalQueryMode.FIXED_INTERVENTION.value,
        "sampling_scheme": TemporalSamplingScheme.REGULAR_GRID.value,
        "target_functional": TemporalTargetFunctional.EFFECT_PATH.value,
        "interpolation_policy": InterventionInterpolationPolicy.PIECEWISE_CONSTANT.value,
        "strategic_adaptation_mode": StrategicAdaptationMode.ABSENT.value,
        "scope_covered": True,
        "tree_like_invariant_estimand": False,
    }


def test_continuous_time_query_accepts_regular_grid_contract() -> None:
    query = _query()

    assert query.target_functional is TemporalTargetFunctional.EFFECT_PATH
    assert query.interpolation_policy is InterventionInterpolationPolicy.PIECEWISE_CONSTANT
    assert query.is_research_gated is False
    assert query.runtime_eligible is True
    assert query.runtime_support_status is RuntimeSupportStatus.SUPPORTED


def test_event_process_query_supports_irregular_grid_weighting_backend() -> None:
    query = _query(
        sampling_scheme=TemporalSamplingScheme.IRREGULAR_GRID,
        horizon_end=4.0,
        target_functional=TemporalTargetFunctional.CUMULATIVE_INCIDENCE,
        metadata={
            "preferred_backend": "event_process_weighting",
            "process_family": "event_log",
        },
    )

    assert query.is_research_gated is False
    assert query.runtime_eligible is True
    assert query.runtime_support_status is RuntimeSupportStatus.SUPPORTED


def test_continuous_time_query_rejects_invalid_horizon_and_blank_time_scale() -> None:
    with pytest.raises(
        ValidationError, match="horizon_start must be strictly less than horizon_end"
    ):
        _query(horizon_start=5.0, horizon_end=5.0)

    with pytest.raises(ValidationError, match="string fields must be non-empty"):
        _query(time_scale="   ")

    with pytest.raises(ValidationError, match="intervention_trajectory_ref is required"):
        ContinuousTimeQuery(
            outcome_process="employment_rate",
            horizon_start=0.0,
            horizon_end=30.0,
            time_scale="days",
            interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        )


def test_optimal_policy_query_mode_does_not_require_fixed_intervention_ref() -> None:
    query = ContinuousTimeQuery(
        query_mode=TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY,
        outcome_process="employment_rate",
        horizon_start=0.0,
        horizon_end=30.0,
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
    )

    assert query.intervention_trajectory_ref is None
    assert query.query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY


def test_effect_trajectory_bundle_requires_band_and_finite_diagnostics_surface() -> None:
    with pytest.raises(ValidationError, match="confidence_band_ref"):
        EffectTrajectoryBundle(
            query_ref=ContinuousTimeQueryRef(artifact_id=_artifact_id("b")),
            trajectory_ref=_artifact_ref("c", kind="test.trajectory"),
            solver_diagnostics_ref=_artifact_ref("e", kind="test.solver_diagnostics"),
            discretization_error=0.05,
            path_representation=TemporalPathRepresentation.LINEAR_SDE,
            solver_family="rk4",
            time_scale="days",
            interpolation_policy=InterventionInterpolationPolicy.LINEAR,
            strategic_adaptation_mode=StrategicAdaptationMode.ABSENT,
        )

    with pytest.raises(ValidationError, match="discretization_error"):
        _bundle(discretization_error=float("inf"))


def test_phase_c_contracts_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    query = _query()
    intervention = _intervention()
    certificate = _identification_certificate()
    regime = DynamicTreatmentRegime(
        time_points=(0, 1, 2),
        treatment_variables=("A_0", "A_1", "A_2"),
        time_varying_covariates=("state",),
        outcome="Y",
        rule=RegimeRule.THRESHOLD,
        threshold_value=0.2,
    )

    intervention_ref = persist_temporal_intervention_trajectory(store, intervention)
    certificate_ref = persist_temporal_identification_certificate(store, certificate)
    query_ref = persist_continuous_time_query(store, query)
    regime_ref = persist_dynamic_treatment_regime(store, regime)
    bundle = _bundle(query_ref=query_ref, identification_certificate_ref=certificate_ref)
    bundle_ref = persist_effect_trajectory_bundle(store, bundle)

    assert isinstance(intervention_ref, TemporalInterventionTrajectoryRef)
    assert isinstance(certificate_ref, TemporalIdentificationCertificateRef)
    assert isinstance(query_ref, ContinuousTimeQueryRef)
    assert isinstance(regime_ref, DynamicTreatmentRegimeRef)
    assert isinstance(bundle_ref, EffectTrajectoryBundleRef)
    assert load_temporal_intervention_trajectory(store, intervention_ref) == intervention
    assert load_temporal_identification_certificate(store, certificate_ref) == certificate
    assert load_continuous_time_query(store, query_ref) == query
    assert load_dynamic_treatment_regime(store, regime_ref) == regime
    assert load_effect_trajectory_bundle(store, bundle_ref) == bundle


def test_local_independence_temporal_identification_certificate_validates() -> None:
    certificate = _identification_certificate(
        theorem_family=TemporalIdentificationTheoremFamily.LOCAL_INDEPENDENCE_WEIGHTING_V1
    )

    assert (
        certificate.theorem_family
        is TemporalIdentificationTheoremFamily.LOCAL_INDEPENDENCE_WEIGHTING_V1
    )
    assert certificate.intervention_semantics is TemporalInterventionSemantics.INTENSITY_REPLACEMENT
    assert certificate.observability_regime is TemporalObservabilityRegime.OBSERVED_FILTRATION
    assert certificate.law_object is TemporalLawObject.INTENSITY_COMPENSATOR


def test_causal_translation_certificate_validates_stage_4_3_schema() -> None:
    certificate = CausalTranslationCertificate.model_validate(
        {
            "schema_name": "ir.causal_translation_certificate",
            "schema_version": "1.0",
            "status": "certified_restricted",
            "abstraction_family": "exact_tau_transformation",
            "scope": {
                "query_functionals_covered": ["effect_path", "integral_effect"],
                "time_grid_covered": [0.0, 1.0, 2.0],
                "variables_covered": ["effect_path", "counterfactual_path", "solver_mean_path"],
            },
            "tau_mapping": {
                "type": "time_sampling",
                "sampling_times": [0.0, 1.0, 2.0],
                "value_quantization": {"enabled": False, "bin_edges": None},
            },
            "omega_mapping": {
                "type": "intervention_lift",
                "interpolation_policy": "piecewise_constant",
                "hold_semantics": "zoh",
                "knot_times": [0.0, 1.0, 2.0],
                "knot_values": [0.0, 1.0, 1.0],
            },
            "sufficient_conditions": {
                "time_scale_matches": True,
                "interpolation_policy_matches_contract": True,
                "grid_regular": True,
                "horizon_aligned": True,
                "backend_exact_discretization": False,
                "allowed_interventions_restricted_to_omega_image": True,
                "unique_solution_assumed": True,
            },
            "assumptions_introduced": [
                "Interventions are interpreted via zoh between knots.",
                "Causal claims only about variables in tau_mapping.",
            ],
            "failure_reasons": [],
            "evidence": {
                "plan_metadata": {"preferred_backend": "linear_sde"},
                "theory_refs": [
                    "Rubenstein et al. 2017 (exact transformations)",
                    "Boeken & Mooij 2024 (subsampled DSCM semantics)",
                ],
            },
        }
    )

    assert certificate.status is CausalTranslationCertificateStatus.CERTIFIED_RESTRICTED
    assert certificate.is_certified is True
    assert certificate.omega_mapping.hold_semantics == "zoh"
    assert certificate.scope.query_functionals_covered == ("effect_path", "integral_effect")


def test_causal_translation_certificate_rejects_quantization_edges_when_disabled() -> None:
    with pytest.raises(ValidationError, match="bin_edges require enabled=true"):
        CausalTranslationCertificate.model_validate(
            {
                "status": "not_certified",
                "scope": {
                    "query_functionals_covered": ["effect_path"],
                    "time_grid_covered": [0.0, 1.0],
                    "variables_covered": ["effect_path"],
                },
                "tau_mapping": {
                    "sampling_times": [0.0, 1.0],
                    "value_quantization": {
                        "enabled": False,
                        "bin_edges": [0.0, 1.0],
                    },
                },
                "omega_mapping": {
                    "interpolation_policy": "linear",
                    "hold_semantics": "foh",
                    "knot_times": [0.0, 1.0],
                    "knot_values": [0.0, 1.0],
                },
                "sufficient_conditions": {
                    "time_scale_matches": True,
                    "interpolation_policy_matches_contract": True,
                    "grid_regular": True,
                    "horizon_aligned": True,
                    "backend_exact_discretization": False,
                    "allowed_interventions_restricted_to_omega_image": True,
                    "unique_solution_assumed": True,
                },
            }
        )


def test_phase_c_research_gating_is_machine_readable() -> None:
    irregular_query = _query(sampling_scheme=TemporalSamplingScheme.IRREGULAR_GRID)
    neural_query = _query(
        metadata={
            "preferred_backend": "neural_sde",
            "temporal_identification_certificate": _identification_certificate().model_dump(
                mode="json"
            ),
        }
    )
    neural_bundle = _bundle(path_representation=TemporalPathRepresentation.NEURAL_SDE)
    certified_neural_bundle = _bundle(
        path_representation=TemporalPathRepresentation.NEURAL_SDE,
        identification_certificate_ref=TemporalIdentificationCertificateRef(
            artifact_id=_artifact_id("f"),
        ),
    )
    scoped_neural_bundle = _bundle(
        path_representation=TemporalPathRepresentation.NEURAL_SDE,
        identification_certificate_ref=TemporalIdentificationCertificateRef(
            artifact_id=_artifact_id("f"),
        ),
        metadata={"identification_scope": _identification_scope()},
    )
    rough_bundle_without_semantics = _bundle(
        path_representation=TemporalPathRepresentation.GEOMETRIC_ROUGH_PATH
    )

    assert irregular_query.is_research_gated is True
    assert irregular_query.runtime_eligible is False
    assert neural_query.is_research_gated is False
    assert neural_query.runtime_eligible is False
    assert neural_query.runtime_support_status is RuntimeSupportStatus.BLOCKED_UNSUPPORTED
    assert neural_query.runtime_blockers == ("unsupported_backend_target",)
    assert neural_bundle.is_research_gated is True
    assert neural_bundle.runtime_eligible is False
    assert neural_bundle.runtime_blockers == ("missing_identification_certificate",)
    assert certified_neural_bundle.is_research_gated is True
    assert certified_neural_bundle.runtime_eligible is False
    assert certified_neural_bundle.runtime_support_status is RuntimeSupportStatus.BLOCKED_RESEARCH
    assert certified_neural_bundle.runtime_blockers == ("unsupported_identification_scope",)
    assert scoped_neural_bundle.is_research_gated is False
    assert scoped_neural_bundle.runtime_eligible is True
    assert scoped_neural_bundle.runtime_support_status is RuntimeSupportStatus.SUPPORTED
    assert rough_bundle_without_semantics.is_research_gated is True
    assert rough_bundle_without_semantics.runtime_eligible is False
    assert rough_bundle_without_semantics.runtime_blockers == (
        "research_gated_path_semantics_missing",
    )


def test_neural_bundle_with_certificate_still_blocks_out_of_scope_adaptation() -> None:
    bundle = _bundle(
        path_representation=TemporalPathRepresentation.NEURAL_CDE,
        identification_certificate_ref=TemporalIdentificationCertificateRef(
            artifact_id=_artifact_id("f"),
        ),
    ).model_copy(
        update={
            "strategic_adaptation_mode": StrategicAdaptationMode.MODELED_SEPARATELY,
        }
    )

    assert bundle.is_research_gated is True
    assert bundle.runtime_support_status is RuntimeSupportStatus.BLOCKED_RESEARCH
    assert bundle.runtime_blockers == ("unsupported_identification_scope",)


def test_rough_path_bundle_is_supported_only_with_semantic_attachment() -> None:
    bundle = _bundle(
        path_representation=TemporalPathRepresentation.GEOMETRIC_ROUGH_PATH,
        metadata={
            "path_semantics": {
                "semantics_scope": TemporalPathSemanticsScope.REPRESENTED_PATH.value,
                "lift_method": "lead_lag",
                "topology": RoughPathTopology.P_VARIATION.value,
                "p_variation_order": 2.0,
                "interpolation_is_adapted": True,
                "future_leakage_ruled_out": True,
                "intervention_type": RoughPathInterventionType.POLICY_OVERRIDE.value,
                "graph_criterion": RoughPathGraphCriterion.DELTA_SEP.value,
                "proof_artifact_ref": _rough_path_certificate_ref().model_dump(mode="json"),
                "sampling_ignorability_checked": True,
                "lift_faithfulness_checked": False,
            }
        },
    )

    assert bundle.runtime_support_status is RuntimeSupportStatus.SUPPORTED
    assert bundle.runtime_eligible is True
    assert bundle.path_semantics_attachment is not None
    assert bundle.path_semantics_scope is TemporalPathSemanticsScope.REPRESENTED_PATH
    assert bundle.path_semantics_disclosure_notes == ("claim_scope_limited_to_represented_path",)


def test_truncated_signature_bundle_requires_logsignature_attachment() -> None:
    with pytest.raises(ValidationError, match="lift_method=logsignature"):
        _bundle(
            path_representation=TemporalPathRepresentation.TRUNCATED_SIGNATURE,
            metadata={
                "path_semantics": {
                    "semantics_scope": TemporalPathSemanticsScope.SIGNATURE_EQUIVALENCE_CLASS.value,
                    "lift_method": "lead_lag",
                    "topology": RoughPathTopology.P_VARIATION.value,
                    "p_variation_order": 2.0,
                    "signature_level": 4,
                    "interpolation_is_adapted": True,
                    "future_leakage_ruled_out": True,
                    "intervention_type": RoughPathInterventionType.POLICY_OVERRIDE.value,
                    "graph_criterion": RoughPathGraphCriterion.NONE.value,
                    "proof_artifact_ref": _rough_path_certificate_ref("1").model_dump(mode="json"),
                    "sampling_ignorability_checked": True,
                    "lift_faithfulness_checked": False,
                }
            },
        )


def test_discrete_fallback_bundle_requires_truthful_disclosure() -> None:
    bundle = _bundle(
        path_representation=TemporalPathRepresentation.DISCRETE_REPLAY,
        discretization_error=None,
        discretization_note="unavailable_under_discrete_fallback",
        continuous_time_degraded=True,
    )

    assert bundle.runtime_support_status is RuntimeSupportStatus.DEGRADED
    assert bundle.runtime_eligible is True

    with pytest.raises(ValidationError, match="must not claim a numeric discretization_error"):
        _bundle(
            path_representation=TemporalPathRepresentation.DISCRETE_REPLAY,
            discretization_error=0.0,
            discretization_note="unavailable_under_discrete_fallback",
            continuous_time_degraded=True,
        )
