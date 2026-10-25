"""Transport-bounds projections require the owner-declared status and mode."""

from __future__ import annotations

from itertools import product

import pytest

from polisyos.foundry.methods.components.consensus import EstimandSpec
from polisyos.ir.analytics.partial_identification import (
    PartialIdentificationResult,
    compute_manski_bounds,
)
from polisyos.ir.analytics.transportability import (
    TransportabilityResult,
    TransportabilityStatus,
    TransportFormula,
    TransportMode,
)
from polisyos.ir.analytics.uncertainty import (
    IntervalSemantics,
    NativeValueEstimandBinding,
    UncertaintyEnvelope,
)


def _estimand() -> EstimandSpec:
    return EstimandSpec(
        query_id="transport-bounds-projection-probe",
        estimand_id="transported_ate",
        outcome="avg_income",
        treatment_or_exposure="policy",
        population="declared-target-moment-fixture",
        unit="income_index",
        target_role="candidate",
    )


def _bounds() -> PartialIdentificationResult:
    # These are explicit utility inputs only; the fixture does not claim they
    # were empirically observed or admitted by a production producer.
    return compute_manski_bounds(
        outcome_conditioned=(0.45, 0.55),
        treatment_probs=(0.5, 0.5),
        outcome_support=(0.4, 0.6),
    )


def _projection_binding(estimand: EstimandSpec) -> NativeValueEstimandBinding:
    return NativeValueEstimandBinding.from_estimand(
        estimand=estimand,
        native_contract_id=TransportabilityResult.contract_id,
        producer_method_fqn="causal.transport_bounds.explicit_moments@candidate",
        projection_input_content_hash="sha256:" + "a" * 64,
    )


def _bounded_result(
    bounds: PartialIdentificationResult | None = None,
) -> TransportabilityResult:
    return TransportabilityResult(
        query="transported_ate",
        status=TransportabilityStatus.BOUNDED_NON_IDENTIFIED,
        transport_mode=TransportMode.BOUNDS_ONLY,
        partial_identification_result=bounds or _bounds(),
    )


def _project(result: TransportabilityResult) -> UncertaintyEnvelope | None:
    estimand = _estimand()
    return result.to_value_uncertainty(
        estimand=estimand,
        projection_binding=_projection_binding(estimand),
    )


def test_explicit_moment_manski_math_remains_available_as_a_candidate() -> None:
    bounds = _bounds()

    assert bounds.lower_bound == pytest.approx(-0.05)
    assert bounds.upper_bound == pytest.approx(0.15)
    assert bounds.is_informative is True
    assert bounds.assumptions_used


def test_only_owner_declared_bounded_bounds_only_tuple_projects_partial_bounds() -> None:
    canonical = _bounded_result()

    # Enumerate the owner's complete status/mode product. The IR contract
    # declares BOUNDED_NON_IDENTIFIED as the bounds-bearing status and requires
    # BOUNDS_ONLY; attached bounds on every other tuple are opaque history.
    for status, mode in product(TransportabilityStatus, TransportMode):
        candidate = canonical.model_copy(update={"status": status, "transport_mode": mode})
        projected = _project(candidate)
        expected = (
            status is TransportabilityStatus.BOUNDED_NON_IDENTIFIED
            and mode is TransportMode.BOUNDS_ONLY
            and candidate.transport_formula is None
        )
        assert (projected is not None) is expected, (status, mode)


def test_bounds_tuple_with_transport_formula_is_not_projected() -> None:
    inconsistent = _bounded_result().model_copy(
        update={
            "transport_formula": TransportFormula(
                formula_str="P*(avg_income|do(policy)) = P(avg_income|policy)",
            )
        }
    )

    assert inconsistent.partial_identification_result is not None
    assert _project(inconsistent) is None


def test_unsupported_history_with_attached_bounds_is_preserved_but_not_projected() -> None:
    bounds = _bounds()
    unsupported = TransportabilityResult(
        query="transported_ate",
        status=TransportabilityStatus.UNSUPPORTED,
        transport_mode=TransportMode.NONE,
        feasible=False,
        unsupported_reason="basis_not_transportable",
        unsupported_cases=["manski_target_basis_missing"],
        warnings=["partial_identification_unavailable:manski_target_basis_missing"],
        partial_identification_result=bounds,
    )

    projected = _project(unsupported)

    assert unsupported.partial_identification_result is bounds
    assert unsupported.unsupported_cases == ["manski_target_basis_missing"]
    assert unsupported.warnings == [
        "partial_identification_unavailable:manski_target_basis_missing"
    ]
    assert unsupported.status is TransportabilityStatus.UNSUPPORTED
    assert unsupported.transport_mode is TransportMode.NONE
    assert projected is None


def test_canonical_bounds_projection_keeps_typed_interval_semantics() -> None:
    result = _bounded_result()
    projected = _project(result)

    assert projected is not None
    assert projected.point_estimate == pytest.approx(0.05)
    assert projected.confidence_interval == pytest.approx((-0.05, 0.15))
    assert projected.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS
    assert projected.gate_eligible is True
    assert _projection_binding(_estimand()).production_value_eligible is False
