from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.catalog.econometrics.protocols import (
    ConfidenceSetSegment,
    CrossSectionalDependenceDiagnostic,
    EconometricDiagnosticResult,
    EconometricResult,
    IdentificationDiagnostic,
    IntervalDisagreementDiagnostic,
    NonstationaryVolatilitySummary,
    OrthogonalityNuisanceDiagnostic,
    PanelData,
    PostSelectionCoverageDiagnostic,
    PostSelectionInterval,
    SparsityComplexityDiagnostic,
    ThresholdEffectModel,
    ThresholdIdentificationMode,
    ThresholdRegressionData,
    ThresholdScoreSummary,
    ThresholdStateField,
    ThresholdSurfaceMode,
    TimeSeriesData,
    VolatilityBreak,
    VolatilityBreakDetectionMethod,
    VolatilityCoverageSummary,
    VolatilityLossFamily,
    VolatilityRegimeSegment,
)


def test_panel_data_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="exog row count"):
        PanelData(
            dependent=np.ones(10),
            exog=np.ones((9, 2)),
            entity_ids=np.repeat(np.arange(5), 2),
            time_ids=np.tile(np.arange(2), 5),
        )


def test_panel_data_rejects_repeated_cross_section_metadata() -> None:
    with pytest.raises(ValueError, match="repeated cross-section/survey data"):
        PanelData(
            dependent=np.ones(10),
            exog=np.ones((10, 2)),
            entity_ids=np.repeat(np.arange(5), 2),
            time_ids=np.tile(np.arange(2), 5),
            metadata={"data_shape": "survey_repeated_cross_section"},
        )


def test_time_series_data_rejects_short_series() -> None:
    with pytest.raises(ValueError, match="at least 8"):
        TimeSeriesData(endog=np.arange(4, dtype=float))


def test_threshold_regression_data_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="running_variable length must match dependent length"):
        ThresholdRegressionData(
            dependent=np.ones(20),
            exog=np.ones((20, 2)),
            running_variable=np.ones(19),
        )


def test_threshold_regression_data_accepts_local_design_fields() -> None:
    data = ThresholdRegressionData(
        dependent=np.ones(24),
        exog=np.ones((24, 2)),
        running_variable=np.linspace(-1.0, 1.0, 24),
        treatment=np.linspace(0.0, 1.0, 24),
        policy_variable=np.linspace(-0.5, 0.5, 24),
        cluster_ids=np.repeat(np.arange(6), 4),
    )

    assert data.treatment is not None
    assert data.policy_variable is not None
    assert data.n_clusters == 6


def test_econometric_result_to_uncertainty_envelope() -> None:
    result = EconometricResult(
        method_name="test",
        params={"beta": 1.2},
        std_errors={"beta": 0.1},
        confidence_intervals={"beta": (1.0, 1.4)},
        p_values={"beta": 0.01},
        n_obs=100,
    )

    envelope = result.to_uncertainty_envelope("beta")
    assert envelope is not None
    assert envelope.point_estimate == 1.2
    assert envelope.confidence_interval == (1.0, 1.4)


def test_econometric_result_weak_iv_set_envelope_uses_robust_hull() -> None:
    result = EconometricResult(
        method_name="test",
        params={"beta": 1.2},
        std_errors={"beta": 0.1},
        coverage_guarantee_tier="WEAK_IV_ROBUST_SET",
        post_selection_ci={
            "beta": PostSelectionInterval(
                parameter="beta",
                method_family="orthogonal_score_wald",
                confidence_level=0.95,
                point_estimate=1.2,
                segments=(ConfidenceSetSegment(lower=1.0, upper=1.4),),
            )
        },
        weak_iv_robust_ci={
            "beta": PostSelectionInterval(
                parameter="beta",
                method_family="anderson_rubin_hc1",
                confidence_level=0.95,
                semantics="confidence_set",
                point_estimate=1.2,
                segments=(
                    ConfidenceSetSegment(lower=0.4, upper=0.9),
                    ConfidenceSetSegment(lower=1.1, upper=2.3),
                ),
            )
        },
        n_obs=100,
    )

    envelope = result.to_uncertainty_envelope("beta")
    assert envelope is not None
    assert envelope.confidence_interval == (0.4, 2.3)
    assert envelope.metadata["interval_source"] == "weak_iv_robust_ci"
    assert envelope.metadata["interval_hull_only"] is True


def test_econometric_result_none_tier_without_explicit_interval_returns_no_envelope() -> None:
    result = EconometricResult(
        method_name="test",
        params={"beta": 1.2},
        std_errors={"beta": 0.1},
        coverage_guarantee_tier="NONE",
        n_obs=100,
    )

    assert result.to_uncertainty_envelope("beta") is None


def test_econometric_result_v2_accepts_cross_sectional_dependence_diagnostic() -> None:
    dependence = CrossSectionalDependenceDiagnostic(
        detected=True,
        class_label="factor",
        strength="strong",
        estimator_status="unsafe_for_default_inference",
        recommended_covariance="cce_reroute",
        tests=[
            EconometricDiagnosticResult(
                test_name="latent_factor_screen",
                statistic=0.61,
                passed=False,
            )
        ],
        factor_count=1,
        used_time_dummies=False,
        dependence_removed_by_time_effects=False,
        evidence={"router_version": "phase1"},
    )

    result = EconometricResult(
        method_name="test",
        params={"beta": 0.8},
        std_errors={"beta": 0.2},
        cross_sectional_dependence_diagnostic=dependence,
    )

    assert EconometricResult.contract_id == "foundry.econometrics.result.v2"
    assert result.cross_sectional_dependence_diagnostic is not None
    assert result.cross_sectional_dependence_diagnostic.class_label == "factor"


def test_econometric_result_accepts_threshold_state_field() -> None:
    threshold_state_field = ThresholdStateField(
        regime_model=ThresholdEffectModel.THRESHOLD,
        identification_mode=ThresholdIdentificationMode.GLOBAL_PROFILE,
        threshold_surface_mode=ThresholdSurfaceMode.AFFINE_STATE_FIXED,
        continuity_imposed=False,
        threshold_shift=0.25,
        state_weights=(0.5,),
        state_variable_names=("eligibility_score",),
        candidate_count=31,
        objective_value=12.4,
        regime_counts={"below_threshold": 48, "at_or_above_threshold": 52},
        normalized_score=ThresholdScoreSummary(
            min_score=-2.0,
            max_score=2.2,
            mean_score=0.03,
            std_score=0.84,
            positive_share=0.52,
            support_within_window=17,
            window_half_width=0.2,
        ),
        metadata={"surface_family": "affine"},
    )

    result = EconometricResult(
        method_name="test",
        params={"beta": 0.9},
        std_errors={"beta": 0.2},
        threshold_state_field=threshold_state_field,
    )

    assert result.threshold_state_field is not None
    assert result.threshold_state_field.regime_model is ThresholdEffectModel.THRESHOLD
    assert result.threshold_state_field.normalized_score.support_within_window == 17


def test_econometric_result_accepts_nonstationary_volatility_summary() -> None:
    summary = NonstationaryVolatilitySummary(
        grouping_strategy="metadata_mapping",
        break_detection_method=VolatilityBreakDetectionMethod.BINSEG_LOG_VARIANCE,
        loss_family=VolatilityLossFamily.GAUSSIAN_QML,
        distribution="normal",
        n_groups=1,
        n_regimes=1,
        breaks=(
            VolatilityBreak(
                group_label="pooled",
                breakpoint_index=8,
                breakpoint_time_id=8,
            ),
        ),
        segments=(
            VolatilityRegimeSegment(
                group_label="pooled",
                segment_index=0,
                start_index=0,
                end_index=7,
                start_time_id=0,
                end_time_id=7,
                n_entities=2,
                n_obs=16,
                params={"omega": 0.1, "alpha[1]": 0.08, "beta[1]": 0.86},
                persistence=0.94,
                mean_conditional_volatility=0.32,
                diagnostics={"empirical_coverage_primary": 0.88},
            ),
        ),
        coverage=VolatilityCoverageSummary(
            primary_nominal_coverage=0.9,
            empirical_coverage=0.88,
            ece=0.03,
            max_calibration_error=0.05,
            sample_count=16,
            diagnostic_levels=(0.5, 0.8, 0.9, 0.95),
        ),
    )

    result = EconometricResult(
        method_name="nonstationary_garch",
        params={"pooled.seg0.omega": 0.1},
        std_errors={"pooled.seg0.omega": 0.02},
        nonstationary_volatility=summary,
    )

    assert result.nonstationary_volatility is not None
    assert result.nonstationary_volatility.breaks[0].breakpoint_index == 8
    assert result.nonstationary_volatility.segments[0].persistence == pytest.approx(0.94)


def test_econometric_result_post_selection_bundle_supports_weak_iv_comparator() -> None:
    result = EconometricResult(
        method_name="iv_high_dimensional_post_selection",
        params={"x_endog": 1.4},
        std_errors={"x_endog": 0.2},
        coverage_guarantee_tier="ORTHOGONAL_CROSSFIT",
        coverage_diagnostic=PostSelectionCoverageDiagnostic(
            sample_size_requirement="s_x log(max(p_x,n_train))/n_train=0.08; s_z log(max(p_z,n_train))/n_train=0.04",
            sparsity=SparsityComplexityDiagnostic(
                selected_controls_union=3,
                selected_instruments_union=2,
                complexity_ratio_controls=0.08,
                complexity_ratio_instruments=0.04,
                support_stability_controls=0.7,
                support_stability_instruments=0.8,
                passed=True,
            ),
            orthogonality=OrthogonalityNuisanceDiagnostic(
                score_type="partial_linear_iv_orthogonal",
                cross_fitted=True,
                n_folds=3,
                orthogonality_score=0.9,
                nuisance_rmse_y=0.4,
                nuisance_rmse_d=0.3,
                nuisance_rmse_z=0.2,
                product_rate_proxy=0.01,
                passed=True,
            ),
            identification=IdentificationDiagnostic(
                weak_iv_test_family="montiel_olea_pflueger_proxy",
                weak_iv_stat=14.0,
                critical_value=10.0,
                passed=True,
            ),
            interval_disagreement=IntervalDisagreementDiagnostic(
                wald_ci=PostSelectionInterval(
                    parameter="x_endog",
                    method_family="orthogonal_score_wald",
                    confidence_level=0.95,
                    point_estimate=1.4,
                    segments=(ConfidenceSetSegment(lower=1.0, upper=1.8),),
                ),
                set_inversion_used=False,
            ),
            overall_gate_passed=True,
        ),
        post_selection_ci={
            "x_endog": PostSelectionInterval(
                parameter="x_endog",
                method_family="orthogonal_score_wald",
                confidence_level=0.95,
                point_estimate=1.4,
                segments=(ConfidenceSetSegment(lower=1.0, upper=1.8),),
            )
        },
    )

    assert result.coverage_diagnostic is not None
    assert result.coverage_diagnostic.sparsity is not None
    assert result.post_selection_ci["x_endog"].method_family == "orthogonal_score_wald"


def test_econometric_result_supports_post_selection_coverage_bundle() -> None:
    post_selection_ci = PostSelectionInterval(
        parameter="beta",
        confidence_level=0.95,
        method_family="orthogonal_score_wald",
        segments=(ConfidenceSetSegment(lower=0.9, upper=1.3),),
        point_estimate=1.1,
    )
    weak_iv_ci = PostSelectionInterval(
        parameter="beta",
        confidence_level=0.95,
        method_family="anderson_rubin_hc1",
        semantics="confidence_set",
        segments=(
            ConfidenceSetSegment(lower=0.7, upper=1.4),
            ConfidenceSetSegment(lower=1.8, upper=2.1),
        ),
        point_estimate=1.1,
    )
    coverage = PostSelectionCoverageDiagnostic(
        sample_size_requirement="s_x log p_x / n is small",
        sparsity=SparsityComplexityDiagnostic(
            selected_controls_union=3,
            selected_instruments_union=2,
            complexity_ratio_controls=0.08,
            complexity_ratio_instruments=0.05,
            support_stability_controls=0.7,
            support_stability_instruments=0.6,
            passed=True,
        ),
        orthogonality=OrthogonalityNuisanceDiagnostic(
            score_type="partial_linear_iv_orthogonal",
            cross_fitted=True,
            n_folds=3,
            orthogonality_score=1.2,
            nuisance_rmse_y=0.4,
            nuisance_rmse_d=0.3,
            nuisance_rmse_z=0.2,
            product_rate_proxy=0.01,
            passed=True,
        ),
        identification=IdentificationDiagnostic(
            weak_iv_test_family="robust_f_proxy",
            weak_iv_stat=12.5,
            critical_value=10.0,
            passed=True,
        ),
        interval_disagreement=IntervalDisagreementDiagnostic(
            wald_ci=post_selection_ci,
            weak_iv_robust_ci=weak_iv_ci,
            ci_disagreement_ratio=1.6,
            set_inversion_used=True,
            materially_different=True,
        ),
        overall_gate_passed=True,
        warnings=("proxy effective F",),
        decision_notes=("orthogonal gate passed",),
    )

    result = EconometricResult(
        method_name="hd_iv",
        params={"beta": 1.1},
        std_errors={"beta": 0.1},
        confidence_intervals={"beta": (0.9, 1.3)},
        coverage_guarantee_tier="WEAK_IV_ROBUST_SET",
        coverage_diagnostic=coverage,
        post_selection_ci={"beta": post_selection_ci},
        weak_iv_robust_ci={"beta": weak_iv_ci},
        n_obs=240,
    )

    envelope = result.to_uncertainty_envelope("beta")
    assert envelope is not None
    assert envelope.confidence_interval == (0.7, 2.1)
    assert envelope.metadata["interval_source"] == "weak_iv_robust_ci"
    assert envelope.metadata["interval_hull_only"] is True
    assert envelope.gate_eligible is True
