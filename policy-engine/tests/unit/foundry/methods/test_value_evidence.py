from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from polisyos.core.observability.determinism import DeterminismTier
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
    resolve_method_value_projection_capabilities,
)
from polisyos.ir.analytics import (
    TruthfulnessReceipt,
    TruthfulnessScope,
    TruthfulnessTier,
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
from polisyos.ir.analytics.uncertainty import (
    NativeValueEstimandBinding,
    OutputContractCapability,
    ValueUncertaintyProjectionKind,
    value_uncertainty_output_contract,
)


class _ForgedNativeOutputOwner:
    contract_id = "test.value.forged_native_output.v1"


class _DeclaredNativeOutput:
    contract_id = _ForgedNativeOutputOwner.contract_id
    output_contract_declaration = value_uncertainty_output_contract(
        contract_id,
        projection_kind=ValueUncertaintyProjectionKind.POSTERIOR,
    )

    def to_value_uncertainty(
        self,
        *,
        estimand: object,
        projection_binding: NativeValueEstimandBinding,
    ) -> None:
        del estimand, projection_binding
        return None


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


def _projection_binding(
    report: object,
    *,
    estimand: EstimandSpec,
    signature: MethodSignature,
) -> NativeValueEstimandBinding:
    return NativeValueEstimandBinding.from_estimand(
        estimand=estimand,
        native_contract_id=str(type(report).contract_id),
        producer_method_fqn=signature.fqn,
        projection_input_content_hash="sha256:" + "a" * 64,
    )


def test_projection_binding_is_intrinsically_nonproduction() -> None:
    estimand = _estimand()
    report = _posterior(verified=True)
    binding = _projection_binding(
        report,
        estimand=estimand,
        signature=BayesianLinearRegressionEstimator.signature,
    )

    assert binding.authority_scope == "contract_only_nonproduction"
    assert binding.production_value_eligible is False

    forged_payload = binding.model_dump(mode="python")
    forged_payload["production_value_eligible"] = True
    with pytest.raises(ValidationError):
        NativeValueEstimandBinding.model_validate(forged_payload)


def _signature(*, output_contract: type[object], family: str) -> MethodSignature:
    return MethodSignature(
        name="value_projection_probe",
        namespace=family,
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {
                SlotSpec.for_output_contract(
                    "result",
                    SlotType.SCALAR,
                    Unit("value", "json"),
                    output_contract=output_contract,
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
    forecast_signature = _signature(
        output_contract=ForecastingUncertaintyBundle,
        family="forecasting",
    )
    forecast_estimand = replace(
        _estimand("avg_income"),
        time_horizon="1",
        target_role="prediction",
    )
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
    posterior_estimand = _estimand()
    posterior = _posterior(verified=True)
    econometric_estimand = _estimand()
    distributional_signature = _signature(
        output_contract=DistributionalBoundsBundle,
        family="distributional",
    )
    distributional_estimand = _estimand("quantile_shift")
    partial_signature = _signature(
        output_contract=BoundsBundle,
        family="partial_identification",
    )
    partial_estimand = _estimand("ate")
    transport_signature = _signature(
        output_contract=TransportabilityResult,
        family="transport",
    )
    transport_estimand = _estimand("transported_ate")
    return (
        (
            "posterior",
            posterior,
            BayesianLinearRegressionEstimator.signature,
            posterior_estimand,
            (-2.0, 5.0),
        ),
        (
            "econometric",
            econometric,
            TimeSeriesEstimator.signature,
            econometric_estimand,
            (1.1, 2.9),
        ),
        (
            "forecasting",
            forecast,
            forecast_signature,
            forecast_estimand,
            (8.0, 13.0),
        ),
        (
            "distributional",
            distributional,
            distributional_signature,
            distributional_estimand,
            (-2.0, 4.0),
        ),
        (
            "partial_identification",
            partial,
            partial_signature,
            partial_estimand,
            (-0.5, 1.25),
        ),
        (
            "transport",
            transport,
            transport_signature,
            transport_estimand,
            (-1.0, 2.0),
        ),
    )


def test_unverified_native_truthfulness_refuses_value_projection() -> None:
    estimand = _estimand()
    posterior = _posterior(verified=False)
    binding = _projection_binding(
        posterior,
        estimand=estimand,
        signature=BayesianLinearRegressionEstimator.signature,
    )
    refusal = project_method_value_evidence(
        method_signature=BayesianLinearRegressionEstimator.signature,
        method_result=_method_result(posterior),
        estimand=estimand,
        selected_output_slot="result",
        projection_binding=binding,
    )

    assert isinstance(refusal, MethodValueRefusal)
    assert refusal.reason_code == "method_truthfulness_unverified"


def test_native_declaration_without_slot_witness_is_not_projection_authority() -> None:
    signature = MethodSignature(
        name="unwitnessed_posterior",
        namespace="test.value",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("value", "json"),
                    contract_id=PosteriorResult.contract_id,
                )
            }
        ),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_1,
    )

    refusal = project_method_value_evidence(
        method_signature=signature,
        method_result=_method_result(_posterior(verified=True)),
        estimand=_estimand(),
        selected_output_slot="result",
    )

    assert isinstance(refusal, MethodValueRefusal)
    assert refusal.reason_code == "method_value_projection_capability_undeclared"


def test_forged_slot_capability_without_matching_owner_refuses() -> None:
    signature = MethodSignature(
        name="forged_slot_capability",
        namespace="test.value",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("value", "json"),
                    contract_id=_DeclaredNativeOutput.contract_id,
                    contract_capabilities=frozenset(
                        {OutputContractCapability.VALUE_UNCERTAINTY_PROJECTION}
                    ),
                    contract_owner=f"{__name__}:_ForgedNativeOutputOwner",
                )
            }
        ),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_1,
    )

    refusal = project_method_value_evidence(
        method_signature=signature,
        method_result=_method_result(_DeclaredNativeOutput()),
        estimand=_estimand(),
        selected_output_slot="result",
    )

    assert isinstance(refusal, MethodValueRefusal)
    assert refusal.reason_code == "method_value_projection_owner_mismatch"


def test_same_fqn_stale_signature_cannot_supply_projection_capability() -> None:
    live_signature = MethodSignature(
        name="stale_signature",
        namespace="test.value",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("value", "json"),
                    contract_id=_DeclaredNativeOutput.contract_id,
                )
            }
        ),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_1,
    )
    stale_signature = _signature(
        output_contract=_DeclaredNativeOutput,
        family="test.value",
    )
    stale_signature = replace(
        stale_signature,
        name=live_signature.name,
        namespace=live_signature.namespace,
        version=live_signature.version,
    )

    class _LiveMethod:
        signature = live_signature

    assert (
        resolve_method_value_projection_capabilities(
            method_cls=_LiveMethod,
            method_signature=stale_signature,
        )
        == ()
    )


def test_native_output_subclass_cannot_inherit_projection_authority() -> None:
    class _ShapedPosterior(PosteriorResult):
        pass

    shaped = _ShapedPosterior.model_validate(_posterior(verified=True).model_dump())
    refusal = project_method_value_evidence(
        method_signature=BayesianLinearRegressionEstimator.signature,
        method_result=_method_result(shaped),
        estimand=_estimand(),
        selected_output_slot="result",
    )

    assert isinstance(refusal, MethodValueRefusal)
    assert refusal.reason_code == "method_value_projection_owner_mismatch"


def test_missing_native_estimand_binding_refuses_projection() -> None:
    refusal = project_method_value_evidence(
        method_signature=BayesianLinearRegressionEstimator.signature,
        method_result=_method_result(_posterior(verified=True)),
        estimand=_estimand(),
        selected_output_slot="result",
    )

    assert isinstance(refusal, MethodValueRefusal)
    assert refusal.reason_code == "method_estimand_binding_mismatch"


def test_same_coefficient_cannot_launder_different_treatment_identity() -> None:
    real_estimand = _estimand()
    posterior = _posterior(verified=True)
    binding = _projection_binding(
        posterior,
        estimand=real_estimand,
        signature=BayesianLinearRegressionEstimator.signature,
    )
    wrong_treatment = replace(
        real_estimand,
        treatment_or_exposure="candidate:unrelated_fabricated_treatment",
    )
    refusal = project_method_value_evidence(
        method_signature=BayesianLinearRegressionEstimator.signature,
        method_result=_method_result(posterior),
        estimand=wrong_treatment,
        selected_output_slot="result",
        projection_binding=binding,
    )

    assert isinstance(refusal, MethodValueRefusal)
    assert refusal.reason_code == "method_estimand_binding_mismatch"


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
    binding = _projection_binding(
        report,
        estimand=estimand,
        signature=signature,
    )
    evidence = project_method_value_evidence(
        method_signature=signature,
        method_result=_method_result(report),
        estimand=estimand,
        selected_output_slot="result",
        projection_binding=binding,
    )

    assert isinstance(evidence, MethodValueEvidence), family
    assert evidence.status == "contract_projection_ready"
    assert evidence.authority_scope == "contract_only_nonproduction"
    assert evidence.production_value_eligible is False
    assert evidence.envelope.confidence_interval == expected_interval
    assert evidence.method_signature_digest == signature.stable_digest()
    assert evidence.projection_binding == binding
    assert evidence.estimand_binding_content_hash == binding.content_hash
    assert evidence.native_projection_capability.projection_kind.value == family
    assert evidence.native_projection_capability.contract_id == type(report).contract_id
    assert evidence.native_projection_capability.output_slot == "result"

    forged_payload = evidence.model_dump(mode="python")
    forged_payload["production_value_eligible"] = True
    with pytest.raises(ValidationError):
        MethodValueEvidence.model_validate(forged_payload)


def test_method_value_evidence_rejects_projection_kind_not_owned_by_contract() -> None:
    report = _posterior(verified=True)
    estimand = _estimand()
    signature = BayesianLinearRegressionEstimator.signature
    binding = _projection_binding(report, estimand=estimand, signature=signature)
    evidence = project_method_value_evidence(
        method_signature=signature,
        method_result=_method_result(report),
        estimand=estimand,
        selected_output_slot="result",
        projection_binding=binding,
    )
    assert isinstance(evidence, MethodValueEvidence)

    forged = evidence.model_dump(mode="python")
    forged["native_projection_capability"]["projection_kind"] = "econometric"
    forged_without_hash = {
        key: value for key, value in forged.items() if key != "content_hash"
    }
    from polisyos.foundry.methods.components.value_evidence import _content_hash

    forged["content_hash"] = _content_hash(forged_without_hash)
    with pytest.raises(
        ValidationError,
        match="method_value_evidence_projection_owner_mismatch",
    ):
        MethodValueEvidence.model_validate(forged)
