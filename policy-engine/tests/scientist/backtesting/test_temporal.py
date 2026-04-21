from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.foundry.methods.catalog.causal.structural_time_series import solve_temporal_effect_path
from polisyos.foundry.methods.catalog.causal.temporal_estimand_compiler import (
    TemporalCompileError,
    compile_temporal_estimand,
)
from polisyos.ir.analytics.dynamic_regime import (
    ContinuousTimeQuery,
    EffectTrajectoryBundle,
    InterventionInterpolationPolicy,
    StrategicAdaptationMode,
    TemporalIdentificationCertificate,
    TemporalIdentificationTheoremFamily,
    TemporalPathRepresentation,
    TemporalSamplingScheme,
    TemporalInterventionTrajectory,
    TemporalInterventionSemantics,
    TemporalLawObject,
    TemporalObservabilityRegime,
)
from polisyos.ir.refs import (
    ArtifactRefModel,
    ContinuousTimeQueryRef,
    RoughPathInterventionCertificateRef,
)
from polisyos.scientist.backtesting.temporal import (
    TemporalThresholds,
    evaluate_temporal_safe_rejection,
    evaluate_temporal_trajectory,
)


def _artifact_ref() -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=f"sha256:{'a' * 64}",
        kind="test.intervention_trajectory",
        media_type="application/json",
    )


def _json_ref(ch: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=f"sha256:{ch * 64}",
        kind=kind,
        media_type="application/json",
    )


def _rough_path_certificate_ref() -> RoughPathInterventionCertificateRef:
    return RoughPathInterventionCertificateRef(artifact_id=f"sha256:{'b' * 64}")


def _query(
    *,
    horizon_end: float,
    preferred_backend: str = "linear_sde",
    sampling_scheme: TemporalSamplingScheme = TemporalSamplingScheme.REGULAR_GRID,
) -> ContinuousTimeQuery:
    return ContinuousTimeQuery(
        intervention_trajectory_ref=_artifact_ref(),
        outcome_process="synthetic_state",
        horizon_start=0.0,
        horizon_end=horizon_end,
        sampling_scheme=sampling_scheme,
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
        values=values or tuple(0.0 if index == 0 else 1.0 for index in range(n_points)),
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
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
            identified_functionals=("effect_path", "integral_effect"),
            intervention_semantics=TemporalInterventionSemantics.SURGICAL_REPLACEMENT,
            observability_regime=TemporalObservabilityRegime.FULL_STATE,
            law_object=TemporalLawObject.CANONICAL_CONTROL_PATH,
            canonical_control_required=True,
            control_canonicalization=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        )
    return TemporalIdentificationCertificate(
        theorem_family=theorem_family,
        identified_functionals=("effect_path", "integral_effect"),
        intervention_semantics=TemporalInterventionSemantics.SURGICAL_REPLACEMENT,
        observability_regime=TemporalObservabilityRegime.FULL_STATE,
        law_object=TemporalLawObject.SEMIMARTINGALE_CHARACTERISTICS,
    )


def _plan(horizon_end: float = 3.0, *, preferred_backend: str = "linear_sde"):
    panel = PanelObservationalData(
        outcome=np.vstack([np.linspace(0.0, horizon_end, int(horizon_end) + 1), np.zeros(int(horizon_end) + 1), np.zeros(int(horizon_end) + 1)]),
        treatment=np.array([1, 0, 0], dtype=int),
        time_treatment=1,
        time_index=np.arange(int(horizon_end) + 1, dtype=float),
    )
    return compile_temporal_estimand(
        _query(horizon_end=horizon_end, preferred_backend=preferred_backend),
        data=panel,
        resolved_intervention=_intervention(
            horizon_end=horizon_end,
            values=tuple(0.0 if index < 1 else 1.0 for index in range(int(horizon_end) + 1)),
        ),
    )


def _trajectory(
    effect_path: list[float],
    *,
    effect_samples: np.ndarray | None = None,
):
    plan = _plan(float(len(effect_path) - 1))
    controls = {"counterfactual_series": np.zeros(len(effect_path), dtype=float)}
    if effect_samples is not None:
        controls["effect_samples"] = effect_samples
    return solve_temporal_effect_path(
        plan,
        observed_series=np.asarray(effect_path, dtype=float),
        controls=controls,
    )


def _rough_path_effect_bundle(*, semantics_scope: str = "represented_path") -> EffectTrajectoryBundle:
    return EffectTrajectoryBundle(
        query_ref=ContinuousTimeQueryRef(artifact_id=f"sha256:{'c' * 64}"),
        trajectory_ref=_json_ref("d", kind="test.trajectory"),
        confidence_band_ref=_json_ref("e", kind="test.confidence_band"),
        solver_diagnostics_ref=_json_ref("f", kind="test.solver_diagnostics"),
        discretization_error=0.05,
        path_representation=TemporalPathRepresentation.GEOMETRIC_ROUGH_PATH,
        solver_family="rough_solver",
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        strategic_adaptation_mode=StrategicAdaptationMode.ABSENT,
        metadata={
            "path_semantics": {
                "semantics_scope": semantics_scope,
                "lift_method": "lead_lag",
                "topology": "p_variation",
                "p_variation_order": 2.0,
                "interpolation_is_adapted": True,
                "future_leakage_ruled_out": True,
                "intervention_type": "policy_override",
                "graph_criterion": "delta_sep",
                "proof_artifact_ref": _rough_path_certificate_ref().model_dump(mode="json"),
                "sampling_ignorability_checked": True,
                "lift_faithfulness_checked": semantics_scope == "latent_path",
            }
        },
    )


def test_temporal_evaluator_reports_pointwise_functional_and_band_metrics() -> None:
    rng = np.random.default_rng(101)
    expected = [0.0, 0.2, 0.4, 0.6]
    effect_samples = np.asarray(
        [np.asarray(expected, dtype=float) + rng.normal(0.0, 0.05, size=len(expected)) for _ in range(256)],
        dtype=float,
    )
    trajectory = _trajectory(expected, effect_samples=effect_samples)

    result = evaluate_temporal_trajectory(
        scenario_id="temporal_metrics",
        scenario_label="Temporal metric evaluation",
        trajectory=trajectory,
        expected_effect_path=expected,
        thresholds=TemporalThresholds(
            max_path_rmse=0.1,
            max_integral_effect_abs_error=0.1,
            min_band_coverage=0.95,
        ),
    )

    assert result.pointwise_metrics["path_rmse"] == pytest.approx(0.0)
    assert result.functional_metrics["integral_effect_abs_error"] == pytest.approx(0.0)
    assert result.uncertainty_metrics["band_coverage"] >= 0.95
    assert result.acceptance_checks["diagnostics_complete"] is True
    assert result.actual_outcome == "pass"


def test_temporal_evaluator_flags_missing_diagnostics_disclosure() -> None:
    trajectory = _trajectory([0.0, 0.1, 0.2, 0.3])
    malformed = trajectory.model_copy(update={"diagnostics": {"solver_family": trajectory.solver_family}})

    result = evaluate_temporal_trajectory(
        scenario_id="temporal_missing_diagnostics",
        scenario_label="Temporal diagnostics omission",
        trajectory=malformed,
        expected_effect_path=[0.0, 0.1, 0.2, 0.3],
        thresholds=TemporalThresholds(max_path_rmse=0.1),
        expected_outcome="diagnostic_failure",
    )

    assert result.diagnostics_checks["complete"] is False
    assert "dt" in result.diagnostics_checks["missing_fields"]
    assert result.actual_outcome == "diagnostic_failure"
    assert result.matches_expected_outcome is True


def test_temporal_evaluator_requires_causal_translation_certificate_for_numeric_discretization() -> None:
    trajectory = _trajectory([0.0, 0.1, 0.2, 0.3])
    diagnostics = dict(trajectory.diagnostics)
    diagnostics.pop("causal_translation_certificate", None)
    malformed = trajectory.model_copy(
        update={
            "causal_translation_certificate": None,
            "diagnostics": diagnostics,
        }
    )

    result = evaluate_temporal_trajectory(
        scenario_id="temporal_missing_causal_translation_certificate",
        scenario_label="Temporal causal translation omission",
        trajectory=malformed,
        expected_effect_path=[0.0, 0.1, 0.2, 0.3],
        thresholds=TemporalThresholds(max_path_rmse=0.1),
        expected_outcome="diagnostic_failure",
    )

    assert result.diagnostics_checks["complete"] is False
    assert "causal_translation_certificate" in result.diagnostics_checks["missing_fields"]
    assert result.actual_outcome == "diagnostic_failure"
    assert result.matches_expected_outcome is True


@pytest.mark.parametrize(
    ("sampling_scheme", "preferred_backend", "expected_reason"),
    [
        (TemporalSamplingScheme.IRREGULAR_GRID, "linear_sde", "research_gated_sampling_scheme"),
        (TemporalSamplingScheme.REGULAR_GRID, "neural_cde", "research_gated_backend"),
        (TemporalSamplingScheme.REGULAR_GRID, "neural_sde", "research_gated_backend"),
    ],
)
def test_temporal_evaluator_marks_safe_rejections_machine_readably(
    sampling_scheme: TemporalSamplingScheme,
    preferred_backend: str,
    expected_reason: str,
) -> None:
    panel = PanelObservationalData(
        outcome=np.vstack([np.linspace(0.0, 3.0, 4), np.zeros(4), np.zeros(4)]),
        treatment=np.array([1, 0, 0], dtype=int),
        time_treatment=1,
        time_index=np.arange(4, dtype=float),
    )
    with pytest.raises(TemporalCompileError) as exc_info:
        compile_temporal_estimand(
            _query(
                horizon_end=3.0,
                preferred_backend=preferred_backend,
                sampling_scheme=sampling_scheme,
            ),
            data=panel,
            resolved_intervention=_intervention(horizon_end=3.0),
        )

    result = evaluate_temporal_safe_rejection(
        scenario_id="temporal_safe_rejection",
        scenario_label="Temporal safe rejection",
        error=exc_info.value,
        expected_reason_code=expected_reason,
    )

    assert result.actual_outcome == "safe_rejection"
    assert result.matches_expected_outcome is True
    assert result.reason_code == expected_reason


def test_temporal_evaluator_reports_unsupported_identification_scope() -> None:
    panel = PanelObservationalData(
        outcome=np.vstack([np.linspace(0.0, 3.0, 4), np.zeros(4), np.zeros(4)]),
        treatment=np.array([1, 0, 0], dtype=int),
        time_treatment=1,
        time_index=np.arange(4, dtype=float),
    )
    with pytest.raises(TemporalCompileError) as exc_info:
        compile_temporal_estimand(
            _query(horizon_end=3.0, preferred_backend="neural_sde"),
            data=panel,
            resolved_intervention=_intervention(horizon_end=3.0),
            identification_certificate=_certificate(
                theorem_family=TemporalIdentificationTheoremFamily.NCDE_FIXED_OBSERVED_CHANNEL_V1
            ),
        )

    result = evaluate_temporal_safe_rejection(
        scenario_id="temporal_identification_scope_rejection",
        scenario_label="Temporal identification scope rejection",
        error=exc_info.value,
        expected_reason_code="unsupported_identification_scope",
    )

    assert result.actual_outcome == "safe_rejection"
    assert result.matches_expected_outcome is True
    assert result.reason_code == "unsupported_identification_scope"


def test_temporal_evaluator_marks_rough_path_without_bundle_as_research_blocked() -> None:
    trajectory = _trajectory([0.0, 0.1, 0.2, 0.3]).model_copy(
        update={"path_representation": TemporalPathRepresentation.GEOMETRIC_ROUGH_PATH}
    )

    result = evaluate_temporal_trajectory(
        scenario_id="temporal_rough_path_research_blocked",
        scenario_label="Temporal rough-path gating without bundle semantics",
        trajectory=trajectory,
        expected_effect_path=[0.0, 0.1, 0.2, 0.3],
        thresholds=TemporalThresholds(max_path_rmse=0.1),
    )

    assert result.gating_checks["runtime_eligible"] is False
    assert result.gating_checks["runtime_support_status"] == "blocked_research"
    assert result.gating_checks["path_semantics_present"] is False
    assert result.gating_checks["path_semantics_scope"] is None
    assert result.gating_checks["path_semantics_disclosure_notes"] == []


def test_temporal_evaluator_discloses_representation_only_scope_for_rough_path_bundle() -> None:
    trajectory = _trajectory([0.0, 0.1, 0.2, 0.3]).model_copy(
        update={
            "path_representation": TemporalPathRepresentation.GEOMETRIC_ROUGH_PATH,
            "effect_bundle": _rough_path_effect_bundle(),
        }
    )

    result = evaluate_temporal_trajectory(
        scenario_id="temporal_rough_path_scope_disclosure",
        scenario_label="Temporal rough-path scope disclosure",
        trajectory=trajectory,
        expected_effect_path=[0.0, 0.1, 0.2, 0.3],
        thresholds=TemporalThresholds(max_path_rmse=0.1),
    )

    assert result.gating_checks["runtime_eligible"] is True
    assert result.gating_checks["runtime_support_status"] == "supported"
    assert result.gating_checks["path_semantics_present"] is True
    assert result.gating_checks["path_semantics_scope"] == "represented_path"
    assert result.gating_checks["path_semantics_disclosure_notes"] == [
        "claim_scope_limited_to_represented_path"
    ]
