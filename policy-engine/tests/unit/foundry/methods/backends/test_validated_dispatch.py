from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends import MethodDispatcher
from polisyos.foundry.methods.backends.validated import ValidatedStatus
from polisyos.foundry.methods.catalog.policy import ensure_policy_methods_registered
from polisyos.foundry.methods.microsim import (
    SurveyMicroData,
    ensure_microsim_methods_registered,
)
from polisyos.foundry.methods.optimization import ensure_optimization_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_registry_and_dispatcher() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _passing_microsim_gate() -> dict[str, object]:
    return {
        "decision": "pass",
        "can_run_microsim": True,
        "compatibility_status": "compatible",
        "blocking_reasons": [],
    }


def _make_state(
    income: np.ndarray | list[float], *, certified_for_microsim: bool = False
) -> SurveyMicroData:
    return SurveyMicroData(
        market_income=np.asarray(income, dtype=float),
        weights=np.ones(len(income), dtype=float),
        microsim_calibration_report=_passing_microsim_gate() if certified_for_microsim else None,
    )


def test_tax_benefit_required_mode_emits_rigorous_boundary_enclosure() -> None:
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("microsim.policy.tax_benefit_calculator@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_state([10000.0, 20000.0, 80000.0]),
        params={"validated_mode": "required"},
        seed=17,
    )

    assert result.validated_bound is not None
    assert result.validated_bound.status is ValidatedStatus.RIGOROUS_ENCLOSURE
    assert result.validated_bound.quantity == "marginal_tax_rate"
    assert result.validated_bound.lower == (0.0, 0.1, 0.32)
    assert result.validated_bound.upper == (0.1, 0.1, 0.32)
    assert result.validated_bound.contains_point_estimate is True
    assert result.artifacts["validated_bound_certificate"]["status"] == "rigorous_enclosure"
    assert result.artifacts["validated_bound_certificate"]["witness"]["ambiguous_count"] == 1
    assert len(result.artifacts["validated_uncertainty_envelopes"]) == 3
    assert (
        result.artifacts["validated_uncertainty_envelopes"][0]["interval_semantics"]
        == "deterministic_bounds"
    )


def test_tax_benefit_auto_mode_skips_certification_away_from_thresholds() -> None:
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("microsim.policy.tax_benefit_calculator@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_state([5000.0, 20000.0, 50000.0, 70000.0]),
        params={"validated_mode": "auto"},
        seed=19,
    )

    assert result.validated_bound is None
    assert "validated_bound_certificate" not in result.artifacts


def test_required_mode_marks_methods_without_registered_certifier() -> None:
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("microsim.static.static_microsim@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_state([4000.0, 12000.0, 22000.0], certified_for_microsim=True),
        params={"validated_mode": "required"},
        seed=23,
    )

    assert result.validated_bound is not None
    assert result.validated_bound.status is ValidatedStatus.NOT_APPLICABLE
    assert result.validated_bound.quantity == "microsim.static.static_microsim@1.0.0"
    assert "validated_bound_not_applicable:microsim.static.static_microsim@1.0.0" in result.warnings
    assert result.artifacts["validated_bound_certificate"]["status"] == "not_applicable"


def test_bilevel_required_mode_emits_certified_residual_bound() -> None:
    ensure_optimization_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("optimization.bilevel.bilevel@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state={
            "c_upper": np.zeros(2, dtype=float),
            "c_lower": np.zeros(2, dtype=float),
            "A_upper": np.eye(2, dtype=float),
            "b_upper": np.ones(2, dtype=float) * 5.0,
            "A_lower": np.eye(2, dtype=float),
            "b_lower": np.ones(2, dtype=float) * 5.0,
        },
        params={"validated_mode": "required"},
        seed=29,
    )

    assert result.validated_bound is not None
    assert result.validated_bound.status is ValidatedStatus.RIGOROUS_ENCLOSURE
    assert result.validated_bound.quantity == "bilevel_fixed_point_residual_inf"
    assert float(result.validated_bound.upper) <= 1e-8
    assert (
        result.artifacts["validated_uncertainty_envelope"]["interval_semantics"]
        == "deterministic_bounds"
    )
    assert result.output["result"]["converged"] is True


def test_bilevel_required_mode_emits_leader_objective_interval_when_bounds_active() -> None:
    ensure_optimization_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("optimization.bilevel.bilevel@1.1.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state={
            "c_upper": np.array([1.0], dtype=float),
            "c_lower": np.array([0.5], dtype=float),
            "A_upper": np.array([[1.0]], dtype=float),
            "b_upper": np.array([1.0], dtype=float),
            "A_lower": np.array([[1.0]], dtype=float),
            "b_lower": np.array([1.0], dtype=float),
            "follower_model": {
                "kind": "quartic_counterexample",
                "lambda": 10.0,
            },
        },
        params={"validated_mode": "required", "ambiguity_mode": "auto"},
        seed=37,
    )

    assert result.validated_bound is not None
    assert result.validated_bound.status is ValidatedStatus.RIGOROUS_ENCLOSURE
    assert result.validated_bound.quantity == "leader_objective_interval"
    assert float(result.validated_bound.lower) <= -10.0
    assert float(result.validated_bound.upper) >= 10.0
    assert result.output["result"]["ambiguity_certificate"]["mode"] == "leader_objective_bounds"
    assert (
        result.artifacts["validated_uncertainty_envelope"]["interval_semantics"]
        == "deterministic_bounds"
    )


def test_welfare_required_mode_emits_discounted_bound_and_irr_witness() -> None:
    ensure_policy_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("policy.welfare.cost_benefit_analysis@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state={
            "benefits": np.array([0.0, 200.0, 200.0], dtype=float),
            "costs": np.array([300.0, 0.0, 0.0], dtype=float),
        },
        params={"validated_mode": "required", "discount_rate": 0.05},
        seed=31,
    )

    assert result.validated_bound is not None
    assert result.validated_bound.status is ValidatedStatus.RIGOROUS_ENCLOSURE
    assert result.validated_bound.quantity == "net_present_value"
    assert float(result.validated_bound.lower) <= float(result.output["result"]["npv"])
    assert float(result.validated_bound.upper) >= float(result.output["result"]["npv"])
    irr_certificate = result.validated_bound.witness["irr_certificate"]
    assert irr_certificate is not None
    assert irr_certificate["status"] == "rigorous_unique_root"
    assert (
        result.artifacts["validated_uncertainty_envelope"]["interval_semantics"]
        == "deterministic_bounds"
    )
