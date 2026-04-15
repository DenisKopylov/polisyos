from __future__ import annotations

import pytest

from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.portfolio import InteractionMatrix, PolicyInteraction, PolicyPortfolio


def _portfolio_three() -> PolicyPortfolio:
    return PolicyPortfolio(
        portfolio_id="poverty_portfolio",
        policies=[
            PolicySpec(policy_id="tax_credit"),
            PolicySpec(policy_id="cash_transfer"),
            PolicySpec(policy_id="job_training"),
        ],
        interaction_matrix=InteractionMatrix(
            interactions=[
                PolicyInteraction(
                    policy_a_id="tax_credit",
                    policy_b_id="cash_transfer",
                    coefficient=0.7,
                ),
                PolicyInteraction(
                    policy_a_id="tax_credit",
                    policy_b_id="job_training",
                    coefficient=1.2,
                ),
                PolicyInteraction(
                    policy_a_id="cash_transfer",
                    policy_b_id="job_training",
                    coefficient=1.1,
                ),
            ],
            max_pairwise_relative_effect=0.5,
        ),
        required_policies=["tax_credit"],
        excluded_pairs=[("cash_transfer", "job_training")],
        max_active_policies=2,
    )


def test_policy_portfolio_validation_rejects_unknown_required() -> None:
    with pytest.raises(ValueError, match="required_policy"):
        PolicyPortfolio(
            portfolio_id="bad_portfolio",
            policies=[PolicySpec(policy_id="a")],
            required_policies=["missing"],
        )


def test_total_benefit_uses_additive_pairwise_effects() -> None:
    portfolio = PolicyPortfolio(
        portfolio_id="benefit_demo",
        policies=[PolicySpec(policy_id="a"), PolicySpec(policy_id="b"), PolicySpec(policy_id="c")],
        interaction_matrix=InteractionMatrix(
            interactions=[
                PolicyInteraction(policy_a_id="a", policy_b_id="b", coefficient=1.2),
                PolicyInteraction(policy_a_id="a", policy_b_id="c", coefficient=1.2),
                PolicyInteraction(policy_a_id="b", policy_b_id="c", coefficient=1.2),
            ],
            max_pairwise_relative_effect=0.5,
        ),
    )

    base = {"a": 100.0, "b": 100.0, "c": 100.0}
    total = portfolio.total_benefit(base)

    # Additive model: 300 base + (20 + 20 + 20) interaction deltas = 360
    assert abs(total - 360.0) < 1e-9


def test_total_benefit_supports_legacy_multiplicative_with_clamp() -> None:
    portfolio = PolicyPortfolio(
        portfolio_id="legacy_mode",
        policies=[PolicySpec(policy_id="a"), PolicySpec(policy_id="b"), PolicySpec(policy_id="c")],
        interaction_matrix=InteractionMatrix(
            interactions=[
                PolicyInteraction(policy_a_id="a", policy_b_id="b", coefficient=1.4),
                PolicyInteraction(policy_a_id="a", policy_b_id="c", coefficient=1.4),
                PolicyInteraction(policy_a_id="b", policy_b_id="c", coefficient=1.4),
            ],
            legacy_min_multiplier=0.5,
            legacy_max_multiplier=1.5,
        ),
    )
    total = portfolio.total_benefit(
        {"a": 100.0, "b": 100.0, "c": 100.0},
        interaction_mode="multiplicative",
    )
    # unclamped per-policy multiplier would be 1.4*1.4=1.96, clamped to 1.5
    assert abs(total - 450.0) < 1e-9


def test_total_benefit_rejects_unknown_interaction_mode() -> None:
    portfolio = PolicyPortfolio(
        portfolio_id="mode_guard",
        policies=[PolicySpec(policy_id="a")],
    )

    with pytest.raises(ValueError, match="interaction_mode"):
        portfolio.total_benefit({"a": 1.0}, interaction_mode="unknown")


def test_matrix_completeness_warning_when_density_low() -> None:
    portfolio = PolicyPortfolio(
        portfolio_id="sparse",
        policies=[
            PolicySpec(policy_id="p1"),
            PolicySpec(policy_id="p2"),
            PolicySpec(policy_id="p3"),
            PolicySpec(policy_id="p4"),
        ],
        interaction_matrix=InteractionMatrix(interactions=[]),
    )
    warnings = portfolio.completeness_warnings(min_non_neutral_density=0.1)
    assert warnings


def test_portfolio_combination_validation() -> None:
    portfolio = _portfolio_three()
    assert portfolio.is_valid_combination({"tax_credit"})
    assert not portfolio.is_valid_combination({"cash_transfer"})
    assert not portfolio.is_valid_combination({"tax_credit", "cash_transfer", "job_training"})
    assert not portfolio.is_valid_combination({"tax_credit", "cash_transfer", "job_training"})
