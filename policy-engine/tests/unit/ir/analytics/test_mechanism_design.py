from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.mechanism_design import (
    IncentiveCertificateStatus,
    MechanismFamily,
    MechanismFamilySpec,
    build_reserve_auction_welfare_loss_bound,
    certify_affine_tax,
    certify_license_scoring_auction,
    certify_piecewise_linear_tax,
    load_incentive_compatibility_certificate,
    load_mechanism_family_spec,
    load_mechanism_welfare_loss_bound,
    persist_incentive_compatibility_certificate,
    persist_mechanism_family_spec,
    persist_mechanism_welfare_loss_bound,
)


def test_piecewise_linear_tax_certificate_and_bound_are_constructive() -> None:
    certificate, bound = certify_piecewise_linear_tax(
        mechanism_id="bayes_tax_pl_v1",
        type_grid=(1.0, 1.5, 2.0),
        earnings_schedule=(0.8, 1.2, 1.6),
        prior_weights=(1.0, 1.0, 1.0),
        revenue_floor=-1.0,
    )

    assert certificate.status is IncentiveCertificateStatus.CERTIFIED
    assert certificate.family is MechanismFamily.TAX_PIECEWISE_LINEAR
    assert certificate.monotonicity_passed is True
    assert certificate.interim_ir_passed is True
    assert certificate.profitable_deviation_max == pytest.approx(0.0, abs=1e-9)
    assert certificate.revenue_value == pytest.approx(0.56, abs=1e-9)
    assert bound.upper_bound == pytest.approx(0.08, abs=1e-9)
    assert bound.observed_gap == pytest.approx(0.03, abs=1e-9)


def test_affine_tax_wrapper_relabels_family_and_keeps_bound_math() -> None:
    certificate, bound = certify_affine_tax(
        mechanism_id="bayes_tax_affine_v1",
        type_grid=(1.0, 1.5, 2.0),
        gamma=0.8,
        prior_weights=(1.0, 1.0, 1.0),
    )

    assert certificate.family is MechanismFamily.TAX_AFFINE
    assert certificate.status is IncentiveCertificateStatus.CERTIFIED
    assert certificate.metadata["gamma"] == pytest.approx(0.8)
    assert bound.family is MechanismFamily.TAX_AFFINE
    assert bound.observed_gap == pytest.approx(0.03, abs=1e-9)


def test_license_scoring_certificate_detects_monotone_threshold_payments() -> None:
    certificate = certify_license_scoring_auction(
        mechanism_id="license_scoring_reserve_v1",
        bid_grid=(0.0, 0.2, 0.3, 0.4, 0.6),
        allocation_rule=(0.0, 0.0, 1.0, 1.0, 1.0),
        payments=(0.0, 0.0, 0.3, 0.3, 0.3),
        reserve_price=0.3,
    )

    assert certificate.status is IncentiveCertificateStatus.CERTIFIED
    assert certificate.family is MechanismFamily.LICENSE_SCORING_RESERVE
    assert certificate.monotonicity_passed is True
    assert certificate.payment_residual_max == pytest.approx(0.0, abs=1e-9)
    assert certificate.profitable_deviation_max == pytest.approx(0.0, abs=1e-9)
    assert certificate.interim_ir_passed is True
    assert certificate.budget_feasible is True


def test_reserve_auction_welfare_bound_matches_binomial_formula() -> None:
    bound = build_reserve_auction_welfare_loss_bound(
        mechanism_id="license_scoring_reserve_v1",
        n_bidders=5,
        k_units=2,
        reserve_price=0.3,
        cdf_at_reserve=0.3,
    )

    assert bound.family is MechanismFamily.LICENSE_SCORING_RESERVE
    assert bound.upper_bound == pytest.approx(0.009963, abs=1e-12)
    assert bound.metadata["tail_terms"] == pytest.approx([0.00243, 0.03078], abs=1e-12)


def test_mechanism_design_artifacts_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    spec = MechanismFamilySpec(
        mechanism_id="bayes_tax_pl_v1",
        family=MechanismFamily.TAX_PIECEWISE_LINEAR,
        verification_mode="monotonicity_envelope",
        parameterization="monotone_piecewise_linear_earnings",
        tunable_parameters=("type_grid", "earnings_schedule"),
        assumptions=("single_dimensional_private_type",),
    )
    certificate, bound = certify_piecewise_linear_tax(
        mechanism_id="bayes_tax_pl_v1",
        type_grid=(1.0, 1.5, 2.0),
        earnings_schedule=(0.8, 1.2, 1.6),
        prior_weights=(1.0, 1.0, 1.0),
    )

    spec_ref = persist_mechanism_family_spec(store, spec)
    certificate_ref = persist_incentive_compatibility_certificate(store, certificate)
    bound_ref = persist_mechanism_welfare_loss_bound(store, bound)

    assert load_mechanism_family_spec(store, spec_ref) == spec
    assert load_incentive_compatibility_certificate(store, certificate_ref) == certificate
    assert load_mechanism_welfare_loss_bound(store, bound_ref) == bound
