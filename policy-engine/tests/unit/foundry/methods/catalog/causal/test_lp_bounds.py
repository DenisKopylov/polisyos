from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.catalog.causal.bounds import BalkePearlBoundsEstimator
from polisyos.foundry.methods.catalog.causal.lp_bounds import auto_bounds, auto_bounds_with_metadata
from polisyos.ir.analytics.dual_certificate import (
    BoundsDualCertificateBundle,
    validate_dual_certificate_bundle,
)
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    PartialIdentificationResult,
    compute_manski_bounds,
)


def _binary_iv_state(n: int = 600, seed: int = 7) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    z = rng.integers(0, 2, size=n).astype(float)
    t = (rng.random(size=n) < (0.15 + 0.55 * z)).astype(float)
    y = (rng.random(size=n) < (0.10 + 0.15 * z + 0.50 * t)).astype(float)
    return {"outcome": y, "treatment": t, "instrument": z}


def test_lp_bounds_binary_iv_matches_balke_pearl() -> None:
    state = _binary_iv_state()
    auto = auto_bounds(
        outcome=state["outcome"],
        treatment=state["treatment"],
        instrument=state["instrument"],
    )
    bp_raw = BalkePearlBoundsEstimator.pure_step(state, {"clip_probs": True})
    bp = PartialIdentificationResult.model_validate(bp_raw["result"]["partial_id_result"])

    assert auto.bounds_type == "sharp_lp"
    assert auto.method == bp.method
    assert auto.lower_bound == pytest.approx(bp.lower_bound, abs=1e-6)
    assert auto.upper_bound == pytest.approx(bp.upper_bound, abs=1e-6)
    assert auto.discretization_method == "instrument_exact"


def test_binary_iv_exact_lp_emits_valid_dual_certificate_payload() -> None:
    state = _binary_iv_state()

    result, metadata = auto_bounds_with_metadata(
        outcome=state["outcome"],
        treatment=state["treatment"],
        instrument=state["instrument"],
    )

    assert result.method == BoundMethod.LP_BALKE_PEARL
    assert result.bounds_type == "sharp_lp"
    assert "dual_certificate_payload" in metadata
    cert = BoundsDualCertificateBundle.model_validate(metadata["dual_certificate_payload"])
    validation = validate_dual_certificate_bundle(cert)
    assert validation.ok, validation.errors


def test_lp_bounds_with_monotonicity_tightens_unconstrained_and_manski() -> None:
    rng = np.random.default_rng(11)
    n = 800
    treatment = rng.integers(0, 2, size=n).astype(float)
    outcome = (rng.random(size=n) < (0.08 + 0.62 * treatment)).astype(float)

    unconstrained = auto_bounds(outcome=outcome, treatment=treatment)
    monotone = auto_bounds(
        outcome=outcome,
        treatment=treatment,
        constraints={"monotone": True},
    )
    manski = compute_manski_bounds(
        outcome_conditioned=np.array(
            [
                float(np.mean(outcome[treatment < 0.5])),
                float(np.mean(outcome[treatment > 0.5])),
            ]
        ),
        treatment_probs=np.array(
            [
                float(np.mean(treatment < 0.5)),
                float(np.mean(treatment > 0.5)),
            ]
        ),
        outcome_support=(0.0, 1.0),
    )

    assert monotone.bounds_type == "sharp_lp"
    assert monotone.lower_bound >= unconstrained.lower_bound - 1e-9
    assert monotone.upper_bound <= unconstrained.upper_bound + 1e-9
    assert monotone.lower_bound >= manski.lower_bound - 1e-9
    assert monotone.upper_bound <= manski.upper_bound + 1e-9
    assert "monotone_treatment_response" in monotone.assumptions_used


def test_small_multivalued_discrete_uses_exact_lp() -> None:
    rng = np.random.default_rng(23)
    n = 500
    treatment = rng.integers(0, 2, size=n).astype(float)
    outcome = np.where(
        treatment > 0.5,
        rng.choice(np.array([0.0, 1.0, 2.0, 3.0]), size=n, replace=True, p=[0.1, 0.2, 0.3, 0.4]),
        rng.choice(np.array([0.0, 1.0, 2.0, 3.0]), size=n, replace=True, p=[0.4, 0.3, 0.2, 0.1]),
    )

    result = auto_bounds(outcome=outcome, treatment=treatment)

    assert result.method == BoundMethod.GENERAL_LP_BOUNDS
    assert result.bounds_type == "sharp_lp"
    assert result.discretization_method == "exact"
    assert result.relaxation_gap == 0.0
    assert "exact_discrete_support" in result.assumptions_used


def test_exact_lp_emits_valid_dual_certificate_payload() -> None:
    rng = np.random.default_rng(31)
    n = 450
    treatment = rng.integers(0, 3, size=n).astype(float)
    outcome = np.where(
        treatment < 0.5,
        rng.choice(np.array([0.0, 1.0, 2.0]), size=n, replace=True, p=[0.55, 0.30, 0.15]),
        np.where(
            treatment < 1.5,
            rng.choice(np.array([0.0, 1.0, 2.0]), size=n, replace=True, p=[0.25, 0.40, 0.35]),
            rng.choice(np.array([0.0, 1.0, 2.0]), size=n, replace=True, p=[0.10, 0.30, 0.60]),
        ),
    )

    result, metadata = auto_bounds_with_metadata(outcome=outcome, treatment=treatment)

    assert result.bounds_type == "sharp_lp"
    assert "dual_certificate_payload" in metadata
    cert = BoundsDualCertificateBundle.model_validate(metadata["dual_certificate_payload"])
    validation = validate_dual_certificate_bundle(cert)
    assert validation.ok, validation.errors


def test_high_cardinality_discrete_uses_relaxed_outer_approximation() -> None:
    rng = np.random.default_rng(29)
    n = 700
    treatment = rng.integers(0, 2, size=n).astype(float)
    outcome = np.where(
        treatment > 0.5,
        rng.integers(4, 16, size=n),
        rng.integers(0, 12, size=n),
    ).astype(float)

    result = auto_bounds(
        outcome=outcome,
        treatment=treatment,
        max_cardinality=3,
        initial_bins=4,
        max_bins=16,
        convergence_tol=0.05,
    )

    assert result.bounds_type == "relaxed_polynomial"
    assert result.discretization_method == "adaptive"
    assert "response_function_outer_relaxation" in result.assumptions_used
    assert result.n_bins_final is not None
    assert result.n_refinement_steps >= 1


def test_continuous_bounds_converge_with_refinement() -> None:
    rng = np.random.default_rng(41)
    n = 600
    treatment = rng.integers(0, 2, size=n).astype(float)
    outcome = np.clip(0.1 + 0.35 * treatment + rng.normal(0.0, 0.03, size=n), 0.0, 1.0)

    coarse = auto_bounds(
        outcome=outcome,
        treatment=treatment,
        initial_bins=5,
        max_bins=20,
        convergence_tol=0.05,
    )
    refined = auto_bounds(
        outcome=outcome,
        treatment=treatment,
        initial_bins=10,
        max_bins=20,
        convergence_tol=0.05,
    )

    assert coarse.bounds_type == "relaxed_polynomial"
    assert coarse.discretization_method == "adaptive"
    assert coarse.n_refinement_steps >= 1
    assert coarse.n_bins_final is not None
    assert coarse.lower_bound <= refined.upper_bound
    assert refined.lower_bound <= coarse.upper_bound
    assert abs(coarse.bound_width - refined.bound_width) < 0.15
