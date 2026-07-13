from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.core.observability.truthfulness import (
    TruthfulnessReceipt,
    TruthfulnessScope,
    TruthfulnessTier,
)
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodTiming,
    ReproducibilityInfo,
)
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.catalog.bayesian.protocols import PosteriorResult
from polisyos.foundry.methods.catalog.bayesian.regression import (
    BayesianLinearRegressionEstimator,
)
from polisyos.foundry.methods.catalog.econometrics.protocols import EconometricResult
from polisyos.foundry.methods.catalog.econometrics.timeseries import TimeSeriesEstimator
from polisyos.foundry.methods.components.consensus import EstimandSpec
from polisyos.foundry.methods.components.value_evidence import (
    MethodValueEvidence,
    MethodValueRefusal,
    project_method_value_evidence,
)
from polisyos.ir.analytics.distributional import (
    DistributionalBoundsBundle,
    DistributionalFunctional,
    FunctionalBounds,
    GridAxis,
)
from polisyos.ir.analytics.forecasting_uncertainty import (
    FanChartSpec,
    ForecastCalibrationMethod,
    ForecastCoverageDiagnostic,
    ForecastingUncertaintyBundle,
    ForecastIntervalSemantics,
    HorizonInterval,
    HorizonPolicySpec,
)
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    BoundsBundle,
    PartialIdentificationResult,
)
from polisyos.ir.analytics.transportability import (
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
)


def _method_result(report: object) -> MethodResult:
    return MethodResult(
        output={"result": report},
        slot_outputs={"result": report},
        timing=MethodTiming(wall_time_ms=1.0),
        reproducibility=ReproducibilityInfo(
            backend=ComputeBackend.BAYESIAN,
            determinism_tier=DeterminismTier.STATISTICAL,
            seed=42,
        ),
    )


def _estimand(parameter: str = "coefficients_0") -> EstimandSpec:
    return EstimandSpec(
        query_id="foundry-value-evidence-probe",
        estimand_id=parameter,
        outcome="avg_income",
        treatment_or_exposure="candidate:treatment",
        population="owner_resolved_rows",
        time_horizon="2017/2020",
        unit="avg_income",
        target_role="causal",
    )


def _signature(*, contract_id: str, family: str) -> MethodSignature:
    return MethodSignature(
        name="value_projection_probe",
        namespace=family,
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("value", "json"),
                    contract_id=contract_id,
                )
            }
        ),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_1,
        family=family,
    )


def _posterior(*, verified: bool) -> PosteriorResult:
    if not verified:
        return PosteriorResult(
            method_name="bayesian_linear_regression",
            posterior_means={"coefficients_0": 1.5},
            posterior_stds={"coefficients_0": 0.8},
            credible_intervals={"coefficients_0": (-2.0, 5.0)},
            diagnostics={"credible_mass": 0.9, "num_samples": 128},
            truthfulness_receipt=TruthfulnessReceipt(
                runtime_truthfulness_tier=TruthfulnessTier.UNVERIFIED,
                truthfulness_scope=TruthfulnessScope.POSTERIOR,
                degradation_reasons=("runtime_calibration_evidence_missing",),
            ),
        )
    return PosteriorResult(
        method_name="bayesian_linear_regression",
        posterior_means={"coefficients_0": 1.5},
        posterior_stds={"coefficients_0": 0.8},
        credible_intervals={"coefficients_0": (-2.0, 5.0)},
        sampler_family="mcmc",
        diagnostics={
            "credible_mass": 0.9,
            "num_samples": 128,
            "rhat_max": 1.01,
            "ess_bulk_min": 128.0,
            "ess_tail_min": 64.0,
            "quantile_mcse_relative_max": 0.05,
            "divergences": 0.0,
        },
    )


def _supported_native_cases() -> tuple[
    tuple[str, object, MethodSignature, EstimandSpec, tuple[float, float]], ...
]:
    generated_at = datetime(2026, 7, 13, tzinfo=UTC)
    forecast = ForecastingUncertaintyBundle(
        method_fqn="forecasting.probe@1.0.0",
        target_id="avg_income",
        generated_at=generated_at,
        prediction_interval=(
            HorizonInterval(
                horizon=1,
                point=10.0,
                lower=8.0,
                upper=13.0,
                coverage_target=0.9,
                constructor=ForecastCalibrationMethod.CONFORMAL,
                sample_count=64,
            ),
        ),
        fan_chart=FanChartSpec(quantile_levels=(), horizons=()),
        coverage_diagnostic=ForecastCoverageDiagnostic(
            nominal_coverage=0.9,
            empirical_coverage_by_horizon={1: 0.91},
            sample_count_by_horizon={1: 64},
            last_recalibrated_at=generated_at,
        ),
        horizon_policy=HorizonPolicySpec(
            default_method=ForecastCalibrationMethod.CONFORMAL,
            gate_eligible=True,
        ),
        interval_semantics=ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL,
        calibration_method=ForecastCalibrationMethod.CONFORMAL,
        nominal_coverage=0.9,
        sample_size_assumption="owner calibration rows",
    )
    distributional = DistributionalBoundsBundle(
        estimand_type="quantile_shift",
        functional=DistributionalFunctional.QUANTILE_SHIFT,
        axis=GridAxis(axis_name="quantile", values=(0.25, 0.75), unit="probability"),
        consensus_bounds=FunctionalBounds(lower=(-2.0, -1.0), upper=(1.0, 4.0)),
        sharpness_status="outer_approx",
    )
    partial = BoundsBundle(
        estimand_type="ate",
        lower_bound=-0.5,
        upper_bound=1.25,
        consensus_lower=-0.5,
        consensus_upper=1.25,
        sharpness_status="sharp",
    )
    transport = TransportabilityResult(
        query="transported_ate",
        status=TransportabilityStatus.BOUNDED_NON_IDENTIFIED,
        transport_mode=TransportMode.BOUNDS_ONLY,
        partial_identification_result=PartialIdentificationResult(
            method=BoundMethod.TRANSPORT_BOUNDS,
            lower_bound=-1.0,
            upper_bound=2.0,
            confidence=0.8,
            informativeness_threshold=4.0,
        ),
    )
    econometric = EconometricResult(
        method_name="time_series_ols",
        params={"coefficients_0": 2.0},
        std_errors={"coefficients_0": 0.4},
        confidence_intervals={"coefficients_0": (1.1, 2.9)},
        n_obs=64,
    )
    return (
        (
            "posterior",
            _posterior(verified=True),
            BayesianLinearRegressionEstimator.signature,
            _estimand(),
            (-2.0, 5.0),
        ),
        (
            "econometric",
            econometric,
            TimeSeriesEstimator.signature,
            _estimand(),
            (1.1, 2.9),
        ),
        (
            "forecasting",
            forecast,
            _signature(contract_id=ForecastingUncertaintyBundle.contract_id, family="forecasting"),
            replace(_estimand("avg_income"), time_horizon="1", target_role="prediction"),
            (8.0, 13.0),
        ),
        (
            "distributional",
            distributional,
            _signature(
                contract_id=DistributionalBoundsBundle.contract_id,
                family="distributional",
            ),
            _estimand("quantile_shift"),
            (-2.0, 4.0),
        ),
        (
            "partial_identification",
            partial,
            _signature(contract_id=BoundsBundle.contract_id, family="partial_identification"),
            _estimand("ate"),
            (-0.5, 1.25),
        ),
        (
            "transport",
            transport,
            _signature(contract_id=TransportabilityResult.contract_id, family="transport"),
            _estimand("transported_ate"),
            (-1.0, 2.0),
        ),
    )


def test_unverified_native_truthfulness_refuses_value_projection() -> None:
    refusal = project_method_value_evidence(
        method_signature=BayesianLinearRegressionEstimator.signature,
        method_result=_method_result(_posterior(verified=False)),
        estimand=_estimand(),
        selected_output_slot="result",
    )

    assert isinstance(refusal, MethodValueRefusal)
    assert refusal.reason_code == "method_truthfulness_unverified"


@pytest.mark.parametrize(
    ("family", "report", "signature", "estimand", "expected_interval"),
    _supported_native_cases(),
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_verified_native_intervals_remain_projectable(
    family: str,
    report: object,
    signature: MethodSignature,
    estimand: EstimandSpec,
    expected_interval: tuple[float, float],
) -> None:
    evidence = project_method_value_evidence(
        method_signature=signature,
        method_result=_method_result(report),
        estimand=estimand,
        selected_output_slot="result",
    )

    assert isinstance(evidence, MethodValueEvidence), family
    assert evidence.envelope.confidence_interval == expected_interval
