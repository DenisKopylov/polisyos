"""Phase 3 mechanism-family catalog and certificate helpers."""

from __future__ import annotations

from polisyos.ir.analytics.mechanism_design import (
    ICVerificationMode,
    MechanismFamily,
    MechanismFamilySpec,
    build_reserve_auction_welfare_loss_bound,
    certify_affine_tax,
    certify_license_scoring_auction,
    certify_piecewise_linear_tax,
)

_MECHANISM_FAMILY_SPECS: dict[str, MechanismFamilySpec] = {
    "bayes_tax_pl_v1": MechanismFamilySpec(
        mechanism_id="bayes_tax_pl_v1",
        family=MechanismFamily.TAX_PIECEWISE_LINEAR,
        verification_mode=ICVerificationMode.MONOTONICITY_ENVELOPE,
        parameterization="monotone_piecewise_linear_earnings",
        tunable_parameters=("type_grid", "earnings_schedule", "u0", "revenue_floor"),
        assumptions=(
            "single_dimensional_private_type",
            "quasi_linear_utility",
            "mirrlees_quadratic_effort",
        ),
        solver_config={"recommended_solver": "convex_or_projected_gradient"},
    ),
    "bayes_tax_affine_v1": MechanismFamilySpec(
        mechanism_id="bayes_tax_affine_v1",
        family=MechanismFamily.TAX_AFFINE,
        verification_mode=ICVerificationMode.MONOTONICITY_ENVELOPE,
        parameterization="affine_earnings_schedule",
        tunable_parameters=("type_grid", "gamma", "u0", "revenue_floor"),
        assumptions=(
            "single_dimensional_private_type",
            "quasi_linear_utility",
            "mirrlees_quadratic_effort",
        ),
        solver_config={"recommended_solver": "one_dimensional_search_or_convex_scan"},
    ),
    "license_scoring_reserve_v1": MechanismFamilySpec(
        mechanism_id="license_scoring_reserve_v1",
        family=MechanismFamily.LICENSE_SCORING_RESERVE,
        verification_mode=ICVerificationMode.MONOTONE_THRESHOLD,
        parameterization="single_parameter_scoring_with_reserve",
        tunable_parameters=("bid_grid", "allocation_rule", "payments", "reserve_price"),
        assumptions=(
            "single_parameter_environment",
            "independent_private_values",
            "regular_priors_or_grid_audit",
        ),
        solver_config={"recommended_solver": "top_k_or_matroid_optimizer"},
    ),
    "license_myerson_score_v1": MechanismFamilySpec(
        mechanism_id="license_myerson_score_v1",
        family=MechanismFamily.LICENSE_MYERSON_SCORE,
        verification_mode=ICVerificationMode.MONOTONE_THRESHOLD,
        parameterization="virtual_value_plus_public_score",
        tunable_parameters=("bid_grid", "allocation_rule", "payments", "reserve_price"),
        assumptions=(
            "single_parameter_environment",
            "independent_private_values",
            "regular_virtual_values",
        ),
        solver_config={"recommended_solver": "top_k_or_matroid_optimizer"},
    ),
}


def get_mechanism_family_spec(mechanism_id: str) -> MechanismFamilySpec:
    """Return one registered mechanism-family specification."""

    if mechanism_id not in _MECHANISM_FAMILY_SPECS:
        raise ValueError(
            "Unknown mechanism family: "
            f"'{mechanism_id}'. Available: {sorted(_MECHANISM_FAMILY_SPECS)}"
        )
    return _MECHANISM_FAMILY_SPECS[mechanism_id]


def mechanism_family_catalog() -> list[dict[str, object]]:
    """Return a compact catalog view for Phase 3 mechanism families."""

    catalog: list[dict[str, object]] = []
    for mechanism_id, spec in sorted(_MECHANISM_FAMILY_SPECS.items()):
        catalog.append(
            {
                "mechanism_id": mechanism_id,
                "family": spec.family.value,
                "verification_mode": spec.verification_mode.value,
                "parameterization": spec.parameterization,
                "tunable_parameters": list(spec.tunable_parameters),
                "assumptions": list(spec.assumptions),
            }
        )
    return catalog


__all__ = [
    "build_reserve_auction_welfare_loss_bound",
    "certify_affine_tax",
    "certify_license_scoring_auction",
    "certify_piecewise_linear_tax",
    "get_mechanism_family_spec",
    "mechanism_family_catalog",
]
