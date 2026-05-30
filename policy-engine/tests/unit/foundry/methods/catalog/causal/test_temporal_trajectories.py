from __future__ import annotations

import numpy as np
from polisyos.foundry.methods.catalog.causal.dtr import estimate_dtr_trajectory
from polisyos.foundry.methods.catalog.causal.event_process_weighting import (
    estimate_event_process_weighting_trajectory,
)
from polisyos.foundry.methods.catalog.causal.g_computation import (
    estimate_g_computation_trajectory,
)
from polisyos.foundry.methods.catalog.causal.protocols import (
    DynamicTreatmentData,
    EventProcessObservationalData,
    PanelObservationalData,
)
from polisyos.foundry.methods.catalog.causal.structural_time_series import (
    estimate_structural_time_series_trajectory,
    solve_temporal_effect_path,
)
from polisyos.foundry.methods.catalog.causal.temporal_estimand_compiler import (
    compile_temporal_estimand,
)
from polisyos.ir.analytics.dynamic_regime import (
    CausalTranslationCertificateStatus,
    ContinuousTimeQuery,
    DynamicTreatmentRegime,
    InterventionInterpolationPolicy,
    RegimeRule,
    TemporalIdentificationCertificate,
    TemporalIdentificationTheoremFamily,
    TemporalInterventionSemantics,
    TemporalInterventionTrajectory,
    TemporalLawObject,
    TemporalObservabilityRegime,
    TemporalSamplingScheme,
    TemporalTargetFunctional,
)
from polisyos.ir.analytics.rough_path_semantics import (
    PathLiftMethod,
    RoughPathGraphCriterion,
    RoughPathIdentificationStatus,
    RoughPathIdentificationStrategy,
    RoughPathInterventionCertificate,
    RoughPathInterventionType,
    RoughPathModelFamily,
    RoughPathTopology,
    TemporalPathSemanticsAttachment,
    TemporalPathSemanticsScope,
)
from polisyos.ir.registry.refs import ArtifactRefModel, RoughPathInterventionCertificateRef


def _artifact_id(ch: str) -> str:
    return f"sha256:{ch * 64}"


def _artifact_ref(ch: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=_artifact_id(ch),
        kind=kind,
        media_type="application/json",
    )


def _rough_path_certificate_ref(ch: str = "a") -> RoughPathInterventionCertificateRef:
    return RoughPathInterventionCertificateRef(artifact_id=_artifact_id(ch))


def _query(
    *,
    outcome_process: str,
    horizon_end: float,
    preferred_backend: str = "linear_sde",
) -> ContinuousTimeQuery:
    return ContinuousTimeQuery(
        intervention_trajectory_ref=_artifact_ref("a", kind="test.intervention_trajectory"),
        outcome_process=outcome_process,
        horizon_start=0.0,
        horizon_end=horizon_end,
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        metadata={"preferred_backend": preferred_backend},
    )


def _intervention(
    *,
    horizon_end: float,
    values: tuple[float, ...] | None = None,
) -> TemporalInterventionTrajectory:
    n_points = int(horizon_end) + 1
    return TemporalInterventionTrajectory(
        time_points=tuple(float(index) for index in range(n_points)),
        values=values or tuple(1.0 for _ in range(n_points)),
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
    )


def _panel_data() -> PanelObservationalData:
    rng = np.random.default_rng(11)
    n_donors, n_periods, t0 = 4, 6, 4
    donors = np.cumsum(rng.normal(0.0, 0.15, size=(n_donors, n_periods)), axis=1)
    treated = donors.mean(axis=0).copy()
    treated[t0:] += np.array([1.2, 1.5], dtype=float)
    return PanelObservationalData(
        outcome=np.vstack([treated, donors]),
        treatment=np.array([1] + [0] * n_donors, dtype=int),
        time_treatment=t0,
        time_index=np.arange(n_periods, dtype=float),
    )


def _dynamic_g_data() -> DynamicTreatmentData:
    rng = np.random.default_rng(21)
    n_units, n_periods = 220, 4
    state = np.zeros((n_units, n_periods), dtype=float)
    treatment = np.zeros((n_units, n_periods), dtype=int)
    state[:, 0] = rng.normal(size=n_units)

    def sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-x))

    for t in range(n_periods):
        treatment[:, t] = rng.binomial(1, sigmoid(0.5 * state[:, t]))
        if t < n_periods - 1:
            state[:, t + 1] = (
                0.5 * treatment[:, t]
                + 0.3 * state[:, t]
                + rng.normal(
                    0.0,
                    0.35,
                    size=n_units,
                )
            )

    outcome = treatment.sum(axis=1).astype(float) + state[:, 0] + rng.normal(0.0, 0.8, size=n_units)
    return DynamicTreatmentData(
        outcome=outcome,
        treatment_sequence=treatment,
        covariate_sequence=state[:, :, np.newaxis],
        time_ids=np.arange(n_periods, dtype=float),
        variable_names=["state"],
    )


def _irregular_dynamic_g_data() -> DynamicTreatmentData:
    return _dynamic_g_data().model_copy(
        update={"time_ids": np.array([0.0, 1.0, 2.5, 4.0], dtype=float)}
    )


def _rough_path_certificate() -> RoughPathInterventionCertificate:
    return RoughPathInterventionCertificate(
        semantics_scope=TemporalPathSemanticsScope.REPRESENTED_PATH,
        model_family=RoughPathModelFamily.HYBRID_RDE,
        topology=RoughPathTopology.P_VARIATION,
        graph_criterion=RoughPathGraphCriterion.DELTA_SEP,
        observation_operator_ref=_artifact_ref("b", kind="test.observation_operator"),
        lift_operator_ref=_artifact_ref("c", kind="test.lift_operator"),
        interpolation_is_adapted=True,
        future_leakage_ruled_out=True,
        intervention_type=RoughPathInterventionType.POLICY_OVERRIDE,
        intervention_operator_ref=_artifact_ref("d", kind="test.intervention_operator"),
        actuatable_component="state",
        filtration_ref=_artifact_ref("e", kind="test.filtration"),
        well_posedness_ref=_artifact_ref("f", kind="test.well_posedness"),
        identification_strategy=RoughPathIdentificationStrategy.CONTINUOUS_TIME_G_FORMULA,
        positivity_ref=_artifact_ref("1", kind="test.positivity"),
        sampling_ignorability_ref=_artifact_ref("2", kind="test.sampling_ignorability"),
        target_functional_ref=_artifact_ref("3", kind="test.target_functional"),
        proof_trace_ref=_artifact_ref("4", kind="test.proof_trace"),
        status=RoughPathIdentificationStatus.IDENTIFIED_REPRESENTATION_ONLY,
    )


def _rough_path_attachment() -> TemporalPathSemanticsAttachment:
    return TemporalPathSemanticsAttachment(
        semantics_scope=TemporalPathSemanticsScope.REPRESENTED_PATH,
        lift_method=PathLiftMethod.LEAD_LAG,
        topology=RoughPathTopology.P_VARIATION,
        p_variation_order=2.0,
        interpolation_is_adapted=True,
        future_leakage_ruled_out=True,
        intervention_type=RoughPathInterventionType.POLICY_OVERRIDE,
        graph_criterion=RoughPathGraphCriterion.DELTA_SEP,
        proof_artifact_ref=_rough_path_certificate_ref(),
        sampling_ignorability_checked=True,
        lift_faithfulness_checked=False,
    )


def _dynamic_dtr_data() -> DynamicTreatmentData:
    rng = np.random.default_rng(31)
    n_units, n_periods = 260, 3
    state = np.zeros((n_units, n_periods), dtype=float)
    treatment = np.zeros((n_units, n_periods), dtype=int)
    state[:, 0] = rng.normal(size=n_units)

    for t in range(n_periods):
        treatment[:, t] = rng.integers(0, 2, size=n_units)
        if t < n_periods - 1:
            state[:, t + 1] = (
                0.45 * treatment[:, t]
                + 0.25 * state[:, t]
                + rng.normal(
                    0.0,
                    0.3,
                    size=n_units,
                )
            )

    outcome = (
        1.8 * treatment.sum(axis=1).astype(float)
        + state[:, 0]
        + rng.normal(
            0.0,
            0.5,
            size=n_units,
        )
    )
    return DynamicTreatmentData(
        outcome=outcome,
        treatment_sequence=treatment,
        covariate_sequence=state[:, :, np.newaxis],
        time_ids=np.arange(n_periods, dtype=float),
        variable_names=["state"],
    )


def _event_process_data() -> EventProcessObservationalData:
    outcome_events = np.array(
        [
            [0, 0, 1, 0],
            [0, 1, 0, 0],
            [0, 0, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 1],
        ],
        dtype=int,
    )
    return EventProcessObservationalData(
        outcome_events=outcome_events,
        censoring_events=np.zeros_like(outcome_events, dtype=int),
        policy_weights=np.array(
            [
                [1.0, 1.0, 1.8, 1.8],
                [1.0, 1.2, 1.2, 1.2],
                [1.0, 1.0, 1.0, 1.7],
                [1.0, 1.0, 1.5, 1.5],
                [1.0, 1.0, 1.0, 1.0],
                [1.0, 1.0, 1.0, 1.6],
            ],
            dtype=float,
        ),
        baseline_weights=np.ones_like(outcome_events, dtype=float),
        time_index=np.array([0.0, 1.0, 2.5, 4.0], dtype=float),
        metadata={"time_scale": "days", "process_family": "event_log"},
    )


def _certificate(
    *,
    theorem_family: TemporalIdentificationTheoremFamily = (
        TemporalIdentificationTheoremFamily.NSDE_FIXED_OBSERVED_CHANNEL_V1
    ),
) -> TemporalIdentificationCertificate:
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
        law_object=TemporalLawObject.GENERATOR,
        assumptions=("fixed_intervention_query", "observed_channel_generator"),
    )


def test_ode_and_linear_sde_match_when_diffusion_is_zero() -> None:
    panel = PanelObservationalData(
        outcome=np.vstack([np.linspace(0.0, 4.0, 5), np.zeros(5), np.zeros(5)]),
        treatment=np.array([1, 0, 0], dtype=int),
        time_treatment=3,
        time_index=np.arange(5, dtype=float),
    )
    linear_plan = compile_temporal_estimand(
        _query(outcome_process="panel_state", horizon_end=4.0, preferred_backend="linear_sde"),
        data=panel,
        resolved_intervention=_intervention(horizon_end=4.0, values=(0.0, 0.0, 0.0, 1.0, 1.0)),
    )
    ode_plan = compile_temporal_estimand(
        _query(outcome_process="panel_state", horizon_end=4.0, preferred_backend="ode"),
        data=panel,
        resolved_intervention=_intervention(horizon_end=4.0, values=(0.0, 0.0, 0.0, 1.0, 1.0)),
    )
    observed = np.linspace(0.0, 4.0, 5)
    baseline = np.zeros(5)

    linear = solve_temporal_effect_path(
        linear_plan,
        observed_series=observed,
        controls={"counterfactual_series": baseline},
    )
    ode = solve_temporal_effect_path(
        ode_plan,
        observed_series=observed,
        controls={"counterfactual_series": baseline},
    )

    assert linear.solver_mean_path == ode.solver_mean_path
    assert linear.discretization_error == ode.discretization_error


def test_rough_path_plan_maps_to_rough_representation_and_degraded_disclosure() -> None:
    plan = compile_temporal_estimand(
        ContinuousTimeQuery(
            intervention_trajectory_ref=_artifact_ref("a", kind="test.intervention_trajectory"),
            outcome_process="state",
            horizon_start=0.0,
            horizon_end=4.0,
            time_scale="days",
            sampling_scheme=TemporalSamplingScheme.IRREGULAR_GRID,
            interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
            metadata={
                "preferred_backend": "geometric_rough_path",
                "path_semantics": _rough_path_attachment().model_dump(mode="json"),
                "rough_path_certificate": _rough_path_certificate().model_dump(mode="json"),
            },
        ),
        data=_irregular_dynamic_g_data(),
        resolved_intervention=_intervention(
            horizon_end=4.0,
            values=(0.0, 0.0, 0.0, 1.0, 1.0),
        ),
    )

    trajectory = solve_temporal_effect_path(
        plan,
        observed_series=np.array([0.0, 0.1, 0.5, 1.2], dtype=float),
        controls={"counterfactual_series": np.zeros(4, dtype=float)},
    )

    assert trajectory.path_representation.value == "geometric_rough_path"
    assert trajectory.continuous_time_degraded is True
    assert trajectory.metadata["path_semantics"]["semantics_scope"] == "represented_path"
    assert trajectory.metadata["rough_path_identification_status"] == (
        RoughPathIdentificationStatus.IDENTIFIED_REPRESENTATION_ONLY.value
    )


def test_structural_time_series_temporal_path_returns_positive_effect() -> None:
    trajectory = estimate_structural_time_series_trajectory(
        _panel_data(),
        _query(outcome_process="treated_outcome", horizon_end=5.0),
    )

    assert np.isfinite(trajectory.integral_effect)
    assert trajectory.effect_path[-1] > 0.5
    assert len(trajectory.counterfactual_path) == 6
    assert trajectory.diagnostics["comparator_semantics"] == "untreated_counterfactual"


def test_non_fallback_temporal_path_emits_restricted_causal_translation_certificate() -> None:
    trajectory = estimate_structural_time_series_trajectory(
        _panel_data(),
        _query(outcome_process="treated_outcome", horizon_end=5.0),
    )

    assert trajectory.causal_translation_certificate is not None
    assert (
        trajectory.causal_translation_certificate.status
        is CausalTranslationCertificateStatus.CERTIFIED_RESTRICTED
    )
    assert (
        trajectory.diagnostics["causal_translation_certificate"]["status"] == "certified_restricted"
    )
    assert trajectory.causal_equivalence_note is not None
    assert "time grid" in trajectory.causal_equivalence_note


def test_exact_zoh_solver_promotes_causal_translation_certificate_to_exact() -> None:
    panel = PanelObservationalData(
        outcome=np.vstack([np.linspace(0.0, 4.0, 5), np.zeros(5), np.zeros(5)]),
        treatment=np.array([1, 0, 0], dtype=int),
        time_treatment=2,
        time_index=np.arange(5, dtype=float),
    )
    plan = compile_temporal_estimand(
        _query(outcome_process="panel_state", horizon_end=4.0, preferred_backend="ode"),
        data=panel,
        resolved_intervention=_intervention(horizon_end=4.0, values=(0.0, 0.0, 1.0, 1.0, 1.0)),
    ).model_copy(
        update={
            "solver_config": {
                "solver_family": "exact_flow",
                "exact_discretization": True,
            }
        }
    )

    trajectory = solve_temporal_effect_path(
        plan,
        observed_series=np.linspace(0.0, 4.0, 5),
        controls={"counterfactual_series": np.zeros(5, dtype=float)},
    )

    assert trajectory.causal_translation_certificate is not None
    assert (
        trajectory.causal_translation_certificate.status
        is CausalTranslationCertificateStatus.CERTIFIED_EXACT
    )
    assert trajectory.diagnostics["causal_translation_certificate"]["status"] == "certified_exact"
    assert (
        trajectory.diagnostics["causal_translation_certificate"]["omega_mapping"]["hold_semantics"]
        == "zoh"
    )
    assert (
        "Pechlivanidou"
        in trajectory.diagnostics["causal_translation_certificate"]["evidence"]["theory_refs"][2]
    )
    assert trajectory.causal_equivalence_note is not None
    assert "exact" in trajectory.causal_equivalence_note


def test_exact_solver_does_not_claim_exact_translation_under_linear_hold() -> None:
    panel = PanelObservationalData(
        outcome=np.vstack([np.linspace(0.0, 3.0, 4), np.zeros(4), np.zeros(4)]),
        treatment=np.array([1, 0, 0], dtype=int),
        time_treatment=1,
        time_index=np.arange(4, dtype=float),
    )
    query = ContinuousTimeQuery(
        intervention_trajectory_ref=_artifact_ref("a", kind="test.intervention_trajectory"),
        outcome_process="panel_state",
        horizon_start=0.0,
        horizon_end=3.0,
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.LINEAR,
        metadata={"preferred_backend": "ode"},
    )
    intervention = TemporalInterventionTrajectory(
        time_points=(0.0, 1.0, 2.0, 3.0),
        values=(0.0, 1.0, 1.0, 1.0),
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.LINEAR,
    )
    plan = compile_temporal_estimand(
        query,
        data=panel,
        resolved_intervention=intervention,
    ).model_copy(
        update={
            "solver_config": {
                "solver_family": "exact_flow",
                "exact_discretization": True,
            }
        }
    )

    trajectory = solve_temporal_effect_path(
        plan,
        observed_series=np.linspace(0.0, 3.0, 4),
        controls={"counterfactual_series": np.zeros(4, dtype=float)},
    )

    assert trajectory.causal_translation_certificate is not None
    assert (
        trajectory.causal_translation_certificate.status
        is CausalTranslationCertificateStatus.CERTIFIED_RESTRICTED
    )
    assert (
        trajectory.causal_translation_certificate.sufficient_conditions.backend_exact_discretization
        is False
    )
    assert (
        trajectory.diagnostics["causal_translation_certificate"]["omega_mapping"]["hold_semantics"]
        == "foh"
    )


def test_neural_temporal_path_emits_neural_sde_representation_and_scope() -> None:
    plan = compile_temporal_estimand(
        _query(outcome_process="panel_state", horizon_end=5.0, preferred_backend="neural_sde"),
        data=_panel_data(),
        resolved_intervention=_intervention(
            horizon_end=5.0,
            values=(0.0, 0.0, 0.0, 0.0, 1.0, 1.0),
        ),
        identification_certificate=_certificate(),
    )

    trajectory = solve_temporal_effect_path(
        plan,
        observed_series=np.linspace(0.0, 5.0, 6),
        controls={"counterfactual_series": np.zeros(6, dtype=float)},
    )

    assert trajectory.path_representation.value == "neural_sde"
    assert trajectory.solver_family == "law_invariant_nsde"
    assert trajectory.metadata["identification_scope"]["theorem_family"] == (
        TemporalIdentificationTheoremFamily.NSDE_FIXED_OBSERVED_CHANNEL_V1.value
    )
    assert trajectory.diagnostics["causal_translation_certificate"]["status"] == (
        "certified_restricted"
    )


def test_neural_cde_temporal_path_is_deterministic_on_canonical_control_grid() -> None:
    plan = compile_temporal_estimand(
        _query(outcome_process="panel_state", horizon_end=5.0, preferred_backend="neural_cde"),
        data=_panel_data(),
        resolved_intervention=_intervention(
            horizon_end=5.0,
            values=(0.0, 0.0, 0.0, 0.0, 1.0, 1.0),
        ),
        identification_certificate=_certificate(
            theorem_family=TemporalIdentificationTheoremFamily.NCDE_FIXED_OBSERVED_CHANNEL_V1
        ),
    )

    trajectory = solve_temporal_effect_path(
        plan,
        observed_series=np.linspace(0.0, 5.0, 6),
        controls={"counterfactual_series": np.zeros(6, dtype=float)},
    )

    assert trajectory.path_representation.value == "neural_cde"
    assert trajectory.solver_family == "canonical_control_ncde"
    assert trajectory.diagnostics["diffusion_norm"] == 0.0


def test_event_process_weighting_temporal_path_returns_policy_curve_contrast() -> None:
    trajectory = estimate_event_process_weighting_trajectory(
        _event_process_data(),
        ContinuousTimeQuery(
            intervention_trajectory_ref=_artifact_ref("a", kind="test.intervention_trajectory"),
            outcome_process="event",
            horizon_start=0.0,
            horizon_end=4.0,
            target_functional=TemporalTargetFunctional.CUMULATIVE_INCIDENCE,
            time_scale="days",
            sampling_scheme="irregular_grid",
            interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
            metadata={
                "preferred_backend": "event_process_weighting",
                "process_family": "event_log",
            },
        ),
        resolved_intervention=TemporalInterventionTrajectory(
            time_points=(0.0, 1.0, 2.0, 3.0, 4.0),
            values=(0.0, 0.0, 1.0, 1.0, 1.0),
            time_scale="days",
            interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        ),
    )

    assert trajectory.path_representation.value == "event_process_weighting"
    assert trajectory.effect_path[-1] > 0.0
    assert trajectory.diagnostics["backend_target"] == "event_process_weighting"


def test_g_computation_temporal_path_beats_never_treat_baseline() -> None:
    regime = DynamicTreatmentRegime(
        time_points=(0, 1, 2, 3),
        treatment_variables=("A_0", "A_1", "A_2", "A_3"),
        time_varying_covariates=("state",),
        outcome="Y",
        rule=RegimeRule.ALWAYS_TREAT,
    )
    g_result, trajectory = estimate_g_computation_trajectory(
        _dynamic_g_data(),
        _query(outcome_process="state", horizon_end=3.0),
        regime=regime,
        method="parametric_g",
        method_params={"n_bootstrap": 30, "n_monte_carlo": 120},
    )

    assert g_result.counterfactual_mean > 1.0
    assert trajectory.integral_effect > 0.0
    assert trajectory.effect_path[-1] > 0.0
    assert trajectory.diagnostics["comparator_semantics"] == "never_treat_baseline"


def test_g_computation_temporal_path_accepts_neural_sde_backend() -> None:
    regime = DynamicTreatmentRegime(
        time_points=(0, 1, 2, 3),
        treatment_variables=("A_0", "A_1", "A_2", "A_3"),
        time_varying_covariates=("state",),
        outcome="Y",
        rule=RegimeRule.ALWAYS_TREAT,
    )
    _, trajectory = estimate_g_computation_trajectory(
        _dynamic_g_data(),
        _query(outcome_process="state", horizon_end=3.0, preferred_backend="neural_sde"),
        regime=regime,
        method="parametric_g",
        method_params={"n_bootstrap": 30, "n_monte_carlo": 120},
        identification_certificate=_certificate(),
    )

    assert trajectory.path_representation.value == "neural_sde"
    assert trajectory.solver_family == "law_invariant_nsde"


def test_dtr_temporal_path_uses_optimal_regime_against_baseline() -> None:
    dtr_result, trajectory = estimate_dtr_trajectory(
        _dynamic_dtr_data(),
        _query(outcome_process="state", horizon_end=2.0),
        method="q_learning",
        method_params={"n_bootstrap": 30},
    )

    assert dtr_result.value_estimate > 0.0
    assert trajectory.integral_effect > 0.0
    assert trajectory.effect_path[-1] > 0.0
    assert trajectory.diagnostics["optimal_regime_rule"] in {
        RegimeRule.ALWAYS_TREAT.value,
        RegimeRule.THRESHOLD.value,
    }


def test_dtr_temporal_path_accepts_neural_cde_backend() -> None:
    _, trajectory = estimate_dtr_trajectory(
        _dynamic_dtr_data(),
        _query(outcome_process="state", horizon_end=2.0, preferred_backend="neural_cde"),
        method="q_learning",
        method_params={"n_bootstrap": 30},
        identification_certificate=_certificate(
            theorem_family=TemporalIdentificationTheoremFamily.NCDE_FIXED_OBSERVED_CHANNEL_V1
        ),
    )

    assert trajectory.path_representation.value == "neural_cde"
    assert trajectory.solver_family == "canonical_control_ncde"


def test_linear_interpolation_does_not_posthoc_shrink_confidence_bands() -> None:
    panel = PanelObservationalData(
        outcome=np.vstack([np.linspace(0.0, 3.0, 4), np.zeros(4), np.zeros(4)]),
        treatment=np.array([1, 0, 0], dtype=int),
        time_treatment=1,
        time_index=np.arange(4, dtype=float),
    )
    query = ContinuousTimeQuery(
        intervention_trajectory_ref=_artifact_ref("a", kind="test.intervention_trajectory"),
        outcome_process="panel_state",
        horizon_start=0.0,
        horizon_end=3.0,
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        metadata={"preferred_backend": "linear_sde"},
    )
    intervention = TemporalInterventionTrajectory(
        time_points=(0.0, 1.0, 2.0, 3.0),
        values=(0.0, 1.0, 1.0, 1.0),
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
    )
    plan = compile_temporal_estimand(
        query,
        data=panel,
        resolved_intervention=intervention,
    )
    effect_samples = np.asarray(
        [
            [0.10, 0.20, 0.30, 0.40],
            [0.15, 0.25, 0.35, 0.45],
            [0.05, 0.15, 0.25, 0.35],
        ],
        dtype=float,
    )
    trajectory = solve_temporal_effect_path(
        plan,
        observed_series=np.array([0.1, 0.2, 0.3, 0.4], dtype=float),
        controls={
            "counterfactual_series": np.zeros(4, dtype=float),
            "effect_samples": effect_samples,
        },
    )

    assert np.allclose(
        np.asarray(trajectory.confidence_band_lower, dtype=float),
        np.quantile(effect_samples, 0.025, axis=0),
    )
    assert np.allclose(
        np.asarray(trajectory.confidence_band_upper, dtype=float),
        np.quantile(effect_samples, 0.975, axis=0),
    )


def test_discrete_fallback_is_truthfully_disclosed() -> None:
    regime = DynamicTreatmentRegime(
        time_points=(0, 1, 2, 3),
        treatment_variables=("A_0", "A_1", "A_2", "A_3"),
        time_varying_covariates=("state",),
        outcome="Y",
        rule=RegimeRule.ALWAYS_TREAT,
    )
    _, trajectory = estimate_g_computation_trajectory(
        _dynamic_g_data(),
        _query(outcome_process="state", horizon_end=2.5),
        regime=regime,
        method="parametric_g",
        method_params={"n_bootstrap": 30, "n_monte_carlo": 120},
    )

    assert trajectory.path_representation.value == "discrete_replay"
    assert trajectory.discretization_error is None
    assert trajectory.discretization_note == "unavailable_under_discrete_fallback"
    assert trajectory.continuous_time_degraded is True
    assert trajectory.causal_translation_certificate is not None
    assert (
        trajectory.causal_translation_certificate.status
        is CausalTranslationCertificateStatus.NOT_CERTIFIED
    )
    assert trajectory.diagnostics["causal_translation_certificate"]["status"] == "not_certified"
    assert trajectory.causal_equivalence_note is not None
    assert "not certified" in trajectory.causal_equivalence_note
