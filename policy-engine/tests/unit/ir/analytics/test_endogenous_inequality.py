from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.distributional import (
    CausalAssumptionCard,
    DistributionalBoundsBundle,
    DistributionalBoundsMethodSummary,
    DistributionalFunctional,
    DistributionalFunctionalParameters,
    FunctionalBounds,
    GridAxis,
)
from polisyos.ir.analytics.endogenous_inequality import (
    CounterfactualLawEstimate,
    CounterfactualLawLabel,
    EndogenousGroupDecompositionStatus,
    EndogenousGroupInequalityDecompositionResult,
    ScalarEstimandEstimate,
    load_endogenous_group_inequality_decomposition_result,
    persist_endogenous_group_inequality_decomposition_result,
)
from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate
from polisyos.ir.analytics.partial_identification import BoundMethod, PartialIdentificationResult
from polisyos.ir.refs import EndogenousGroupInequalityDecompositionRef


def _law(label: CounterfactualLawLabel, value: float) -> CounterfactualLawEstimate:
    return CounterfactualLawEstimate(
        law=label,
        structure_from=int(label.value[2]),
        composition_from=int(label.value[3]),
        mean_estimate=10.0 + value,
        transformed_moment_estimate=15.0 + value,
        inequality_estimate=value,
        standard_error=0.05,
        confidence_interval=(value - 0.1, value + 0.1),
    )


def _effect(value: float, formula: str) -> ScalarEstimandEstimate:
    return ScalarEstimandEstimate(
        point_estimate=value,
        standard_error=0.1,
        confidence_interval=(value - 0.2, value + 0.2),
        estimand_formula=formula,
    )


def test_identified_endogenous_group_decomposition_result_validates() -> None:
    result = EndogenousGroupInequalityDecompositionResult(
        functional=DistributionalFunctional.THEIL_T,
        status=EndogenousGroupDecompositionStatus.IDENTIFIED,
        laws=(
            _law(CounterfactualLawLabel.F_00, 0.10),
            _law(CounterfactualLawLabel.F_10, 0.18),
            _law(CounterfactualLawLabel.F_11, 0.24),
            _law(CounterfactualLawLabel.F_01, 0.14),
        ),
        total_effect=_effect(0.14, "T(F_11) - T(F_00)"),
        compositional_effect=_effect(0.06, "T(F_11) - T(F_10)"),
        structural_effect=_effect(0.08, "T(F_10) - T(F_00)"),
        shapley_compositional_effect=_effect(0.05, "shapley comp"),
        shapley_structural_effect=_effect(0.09, "shapley str"),
        overlap_fraction=0.97,
        retained_fraction=1.0,
        assumption_cards=(
            CausalAssumptionCard(
                scope="estimation",
                status="identified_needed",
                theorem_family="interventional_endogenous_group_decomposition_v1",
                assumption_type="positivity",
                description="All required cells lie on common support.",
                testable=True,
            ),
        ),
    )

    assert result.status is EndogenousGroupDecompositionStatus.IDENTIFIED
    assert result.total_effect is not None
    assert result.compositional_effect is not None
    assert result.structural_effect is not None
    assert {law.law for law in result.laws} == {
        CounterfactualLawLabel.F_00,
        CounterfactualLawLabel.F_10,
        CounterfactualLawLabel.F_11,
        CounterfactualLawLabel.F_01,
    }


def test_generalized_entropy_requires_alpha() -> None:
    with pytest.raises(ValueError, match="generalized_entropy_alpha"):
        EndogenousGroupInequalityDecompositionResult(
            functional=DistributionalFunctional.GENERALIZED_ENTROPY,
            status=EndogenousGroupDecompositionStatus.BLOCKED,
            negative_certificate=NegativeCertificate(
                blocking_type=BlockingType.COUPLING_NOT_IDENTIFIED,
                blocking_description="Missing mediator exchangeability assumptions.",
                partial_bounds=PartialIdentificationResult(
                    method=BoundMethod.TRANSPORT_BOUNDS,
                    lower_bound=-1.0,
                    upper_bound=1.0,
                    confidence=1.0,
                ),
            ),
        )


def test_bounded_result_accepts_negative_certificate() -> None:
    cert = NegativeCertificate(
        blocking_type=BlockingType.POSITIVITY_VIOLATION,
        blocking_description="Estimated overlap floor failed.",
        partial_bounds=PartialIdentificationResult(
            method=BoundMethod.TRANSPORT_BOUNDS,
            lower_bound=-0.5,
            upper_bound=0.9,
            confidence=1.0,
        ),
    )
    result = EndogenousGroupInequalityDecompositionResult(
        functional=DistributionalFunctional.GENERALIZED_ENTROPY,
        functional_parameters=DistributionalFunctionalParameters(
            generalized_entropy_alpha=2.0,
        ),
        status=EndogenousGroupDecompositionStatus.BOUNDED,
        negative_certificate=cert,
        bounds_bundle=cert.bounds_bundle,
        overlap_fraction=0.71,
        retained_fraction=0.71,
    )

    assert result.status is EndogenousGroupDecompositionStatus.BOUNDED
    assert result.bounds_bundle is not None
    assert result.negative_certificate is cert


def test_bounded_result_accepts_distributional_bounds_bundle() -> None:
    axis = GridAxis(axis_name="decomposition_effect", values=(0.0,), unit="effect_index")
    distributional_bounds = DistributionalBoundsBundle(
        estimand_type="endogenous_group_inequality_decomposition",
        functional=DistributionalFunctional.THEIL_T,
        axis=axis,
        method_summaries=[
            DistributionalBoundsMethodSummary(
                method="support_interval_arithmetic",
                functional=DistributionalFunctional.THEIL_T,
                axis=axis,
                bounds=FunctionalBounds(lower=(-0.2,), upper=(0.4,)),
                sharpness="outer_approx",
            )
        ],
    )

    result = EndogenousGroupInequalityDecompositionResult(
        functional=DistributionalFunctional.THEIL_T,
        status=EndogenousGroupDecompositionStatus.BOUNDED,
        distributional_bounds_bundle=distributional_bounds,
    )

    assert result.distributional_bounds_bundle is not None
    assert result.bounds_bundle is None
    assert result.negative_certificate is None


def test_endogenous_group_decomposition_persists_round_trip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    result = EndogenousGroupInequalityDecompositionResult(
        functional=DistributionalFunctional.THEIL_T,
        status=EndogenousGroupDecompositionStatus.IDENTIFIED,
        laws=(
            _law(CounterfactualLawLabel.F_00, 0.10),
            _law(CounterfactualLawLabel.F_10, 0.18),
            _law(CounterfactualLawLabel.F_11, 0.24),
            _law(CounterfactualLawLabel.F_01, 0.14),
        ),
        total_effect=_effect(0.14, "T(F_11) - T(F_00)"),
        compositional_effect=_effect(0.06, "T(F_11) - T(F_10)"),
        structural_effect=_effect(0.08, "T(F_10) - T(F_00)"),
        shapley_compositional_effect=_effect(0.05, "shapley comp"),
        shapley_structural_effect=_effect(0.09, "shapley str"),
    )

    ref = persist_endogenous_group_inequality_decomposition_result(store, result)
    loaded = load_endogenous_group_inequality_decomposition_result(store, ref)

    assert isinstance(ref, EndogenousGroupInequalityDecompositionRef)
    assert ref.kind == "ir.endogenous_group_inequality_decomposition"
    assert loaded == result


def test_endogenous_group_decomposition_is_on_analytics_facade() -> None:
    from polisyos.ir import analytics

    assert (
        analytics.EndogenousGroupInequalityDecompositionResult
        is EndogenousGroupInequalityDecompositionResult
    )
    assert (
        analytics.EndogenousGroupInequalityDecompositionRef
        is EndogenousGroupInequalityDecompositionRef
    )
