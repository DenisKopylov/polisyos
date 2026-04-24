"""Public auction optimization module API."""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np

from polisyos.foundry.methods.backends.protocol import SolverStatus
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.ir.analytics.uncertainty import (
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

from .protocols import (
    AmbiguityCertificate,
    AuctionFormatRecommendation,
    AuctionReserveProblem,
    ConstraintCertificate,
    DiagnosticResult,
    MomentBound,
    OptimizationResult,
    emit_optimization_metrics,
    parse_auction_reserve_problem,
)


def _serialize_result(result: OptimizationResult) -> dict[str, Any]:
    payload = result.to_payload()
    payload["contract_id"] = OptimizationResult.contract_id
    return payload


def _format_weight_key(index: int, reserve: float) -> str:
    return f"reserve_weight[{index}]::{reserve:.12g}"


def _solve_mixed_policy(revenue_matrix: np.ndarray) -> tuple[np.ndarray, float, str] | None:
    try:
        from scipy.optimize import linprog
    except Exception:
        return None

    n_scenarios, n_reserves = revenue_matrix.shape
    c = np.zeros(n_reserves + 1, dtype=float)
    c[-1] = -1.0

    a_ub = np.zeros((n_scenarios, n_reserves + 1), dtype=float)
    a_ub[:, :n_reserves] = -revenue_matrix
    a_ub[:, -1] = 1.0
    b_ub = np.zeros(n_scenarios, dtype=float)

    a_eq = np.zeros((1, n_reserves + 1), dtype=float)
    a_eq[0, :n_reserves] = 1.0
    b_eq = np.array([1.0], dtype=float)
    bounds = [(0.0, None)] * n_reserves + [(None, None)]

    result = linprog(
        c,
        A_ub=a_ub,
        b_ub=b_ub,
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )
    if not bool(result.success) or result.x is None:
        return None

    weights = np.asarray(result.x[:n_reserves], dtype=float)
    weights = np.maximum(weights, 0.0)
    total = float(np.sum(weights))
    if total <= 0.0:
        return None
    weights = weights / total
    guarantee = float(result.x[-1])
    message = str(getattr(result, "message", "scipy.optimize.linprog"))
    return weights, guarantee, message


def _build_revenue_matrix(
    problem: AuctionReserveProblem,
    *,
    include_seller_value_when_unsold: bool,
) -> tuple[np.ndarray, int]:
    if problem.scenario_revenues is not None:
        matrix = np.asarray(problem.scenario_revenues, dtype=float)
        return matrix, int(matrix.shape[0])

    assert problem.valuation_scenarios is not None
    reserve_grid = np.asarray(problem.reserve_grid, dtype=float)
    n_scenarios = len(problem.valuation_scenarios)
    matrix = np.zeros((n_scenarios, reserve_grid.size), dtype=float)
    total_profiles = 0

    for scenario_idx, scenario in enumerate(problem.valuation_scenarios):
        values = np.asarray(scenario, dtype=float)
        total_profiles += int(values.shape[0])
        if values.shape[1] == 1:
            top = values[:, 0]
            second = np.full_like(top, float(problem.seller_value))
        else:
            ordered = np.sort(values, axis=1)
            top = ordered[:, -1]
            second = ordered[:, -2]

        for reserve_idx, reserve in enumerate(reserve_grid):
            sold = top >= reserve
            realized = np.where(sold, np.maximum(reserve, second), 0.0)
            if include_seller_value_when_unsold:
                realized = np.where(sold, realized, float(problem.seller_value))
            matrix[scenario_idx, reserve_idx] = float(np.mean(realized))

    return matrix, total_profiles


def _normalize_probabilities(problem: AuctionReserveProblem, n_scenarios: int) -> np.ndarray:
    if problem.scenario_probabilities is None:
        return np.full(n_scenarios, 1.0 / max(n_scenarios, 1), dtype=float)
    probs = np.asarray(problem.scenario_probabilities, dtype=float)
    total = float(np.sum(probs))
    if total <= 0.0:
        raise ValueError("scenario probabilities must have positive total mass")
    return probs / total


def _recommended_format(problem: AuctionReserveProblem) -> str:
    if "second_price" in problem.supported_formats:
        return "second_price"
    if "english" in problem.supported_formats:
        return "english"
    if problem.supported_formats:
        return problem.supported_formats[0]
    return "second_price"


@dataclass(frozen=True, slots=True)
class RevenueEquivalenceAssessment:
    status: str
    holds: bool
    reason: str
    recommended_format: str
    compared_formats: tuple[str, ...]
    blockers: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "holds": self.holds,
            "reason": self.reason,
            "recommended_format": self.recommended_format,
            "compared_formats": list(self.compared_formats),
            "blockers": list(self.blockers),
        }


def _assess_revenue_equivalence(problem: AuctionReserveProblem) -> RevenueEquivalenceAssessment:
    blockers: list[str] = []
    if problem.reserve_visibility != "public":
        blockers.append("reserve realization is not public")
    if problem.reserve_timing != "pre_commit":
        blockers.append("reserve can be revised after bid submission")
    if problem.value_model != "independent_private_values":
        blockers.append("values are not independent private values")
    if problem.bidder_risk != "risk_neutral":
        blockers.append("bidders are not risk neutral")
    if problem.prior_regime != "symmetric":
        blockers.append("priors are not symmetric across bidders")
    if problem.entry_regime != "fixed":
        blockers.append("entry is endogenous")

    recommended = _recommended_format(problem)
    if not blockers:
        return RevenueEquivalenceAssessment(
            status="pass",
            holds=True,
            reason=(
                "Conditional revenue equivalence applies because the reserve is public, "
                "pre-committed, and the environment matches the standard IPV benchmark."
            ),
            recommended_format=recommended,
            compared_formats=tuple(problem.supported_formats),
            blockers=(),
        )

    return RevenueEquivalenceAssessment(
        status="warn",
        holds=False,
        reason="Revenue equivalence is not portable beyond the reference SPA calculation because "
        + "; ".join(blockers)
        + ".",
        recommended_format=recommended,
        compared_formats=tuple(problem.supported_formats),
        blockers=tuple(blockers),
    )


def _format_recommendation(
    problem: AuctionReserveProblem,
    *,
    equivalence: RevenueEquivalenceAssessment,
    used_mixed_policy: bool,
    deterministic_guarantee: float,
    guarantee: float,
    nominal_expected: float,
    oracle_expected: float,
) -> AuctionFormatRecommendation:
    robustness_gap = max(0.0, oracle_expected - guarantee)
    nominal_gap = max(0.0, oracle_expected - nominal_expected)

    if not equivalence.holds:
        uncertainty_regime = "high"
        reserve_visibility = "revisable" if problem.reserve_timing != "pre_commit" else "secret"
        reserve_policy = "bilevel_or_sequential_analysis"
        rationale = (
            "Revenue equivalence is not transportable across formats in this information "
            "regime, so the format decision should be treated as a strategic mechanism "
            "design problem rather than a pure reserve-calibration problem."
        )
    elif used_mixed_policy or (
        robustness_gap > 0.25 * max(abs(oracle_expected), 1.0e-9) and nominal_gap > 0.0
    ):
        uncertainty_regime = "high"
        reserve_visibility = "public"
        reserve_policy = "public_randomized_or_maxmin"
        rationale = (
            "Worst-case revenue is materially sensitive to reserve uncertainty, so a public "
            "format should be retained while the reserve policy is optimized for robustness."
        )
    elif nominal_gap > 0.0 or abs(guarantee - deterministic_guarantee) > 1.0e-9:
        uncertainty_regime = "moderate"
        reserve_visibility = "public"
        reserve_policy = "public_downward_robustified"
        rationale = (
            "Conditional revenue equivalence still applies, but reserve miss costs are large "
            "enough to justify a robust public reserve rather than a plug-in point estimate."
        )
    else:
        uncertainty_regime = "low"
        reserve_visibility = "public"
        reserve_policy = "public_deterministic"
        rationale = (
            "Reserve uncertainty is limited, so a simple public reserve in a standard "
            "revenue-equivalent format is the preferred operating point."
        )

    return AuctionFormatRecommendation(
        uncertainty_regime=uncertainty_regime,
        recommended_format=equivalence.recommended_format,
        reserve_policy=reserve_policy,
        reserve_visibility=reserve_visibility,
        revenue_equivalence_holds=equivalence.holds,
        rationale=rationale,
        compared_formats=equivalence.compared_formats,
        blockers=equivalence.blockers,
        diagnostics={
            "deterministic_guarantee": deterministic_guarantee,
            "worst_case_guarantee": guarantee,
            "nominal_expected_revenue": nominal_expected,
            "oracle_expected_revenue": oracle_expected,
            "robustness_gap": robustness_gap,
            "policy_mode": "mixed" if used_mixed_policy else "deterministic",
        },
    )


def _overreserve_diagnostic(
    reserve_grid: np.ndarray,
    expected_by_reserve: np.ndarray,
) -> DiagnosticResult:
    best_idx = int(np.argmax(expected_by_reserve))
    if best_idx == 0 or best_idx == expected_by_reserve.size - 1:
        return DiagnosticResult(
            test_name="overreserve_asymmetry",
            status="warn",
            message="Cannot compare upward vs downward reserve miss costs at a grid boundary.",
            metadata={"best_index": best_idx},
        )

    best = float(expected_by_reserve[best_idx])
    downward_loss = best - float(expected_by_reserve[best_idx - 1])
    upward_loss = best - float(expected_by_reserve[best_idx + 1])
    return DiagnosticResult(
        test_name="overreserve_asymmetry",
        status="pass" if upward_loss >= downward_loss else "warn",
        statistic=float(upward_loss - downward_loss),
        message=(
            "Higher reserve miss is at least as costly as lower reserve miss."
            if upward_loss >= downward_loss
            else "Reserve miss asymmetry does not favor downward correction on this grid."
        ),
        metadata={
            "best_reserve": float(reserve_grid[best_idx]),
            "downward_loss": downward_loss,
            "upward_loss": upward_loss,
        },
    )


@foundry_method(
    namespace="optimization.auction",
    version="1.0.0",
    tags={"optimization", "auction", "robust", "mechanism-design"},
)
class PublicReserveAuctionEstimator:
    """Optimize a public reserve policy under scenario or valuation uncertainty."""

    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="public_reserve_auction",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "auction_reserve_problem",
                    SlotType.SCALAR,
                    Unit("problem", "json"),
                    contract_id=AuctionReserveProblem.contract_id,
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("result", "json"),
                    contract_id=OptimizationResult.contract_id,
                ),
                SlotSpec("solver_info", SlotType.SCALAR, Unit("solver", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="allow_mixed_policy", default=True),
            ParameterSpec(name="include_seller_value_when_unsold", default=False),
            ParameterSpec(name="revenue_floor", default=None),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.SOLVER,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Robust public-reserve auction optimizer over a finite reserve grid.",
        tags=frozenset({"optimization", "auction", "robust", "mechanism-design"}),
        equations={
            "scenario_maximin": "max_x eta s.t. A x >= eta 1, 1'x = 1, x >= 0",
            "spa_revenue": "rho_r(v) = 1{v_(1) >= r} max(r, v_(2))",
        },
        when_to_use=(
            "Reserve-price design under public reserve disclosure when valuation or "
            "scenario uncertainty matters more than auction-format micro-details."
        ),
        when_not_to_use=(
            "Secret/revisable reserves, common values, endogenous entry, or settings that "
            "require a full bilevel model of strategic response."
        ),
        output_interpretation=(
            "Objective value is the worst-case revenue guarantee of the chosen reserve policy. "
            "Metadata also reports nominal expected revenue and whether standard revenue "
            "equivalence assumptions hold."
        ),
    )

    @staticmethod
    def pure_step(
        state: Mapping[str, Any] | AuctionReserveProblem,
        params: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        started = time.perf_counter()
        problem = parse_auction_reserve_problem(state)
        allow_mixed_policy = bool(params.get("allow_mixed_policy", True))
        include_seller_value = bool(params.get("include_seller_value_when_unsold", False))
        revenue_floor = (
            None if params.get("revenue_floor") is None else float(params["revenue_floor"])
        )

        reserve_grid = np.asarray(problem.reserve_grid, dtype=float)
        revenue_matrix, sample_size = _build_revenue_matrix(
            problem,
            include_seller_value_when_unsold=include_seller_value,
        )
        probabilities = _normalize_probabilities(problem, revenue_matrix.shape[0])

        deterministic_min = np.min(revenue_matrix, axis=0)
        deterministic_idx = int(np.argmax(deterministic_min))
        deterministic_weights = np.zeros(reserve_grid.size, dtype=float)
        deterministic_weights[deterministic_idx] = 1.0
        deterministic_guarantee = float(deterministic_min[deterministic_idx])

        solver_backend = "deterministic_enumeration"
        solver_message = "Enumerated deterministic reserve grid."
        weights = deterministic_weights
        guarantee = deterministic_guarantee
        used_mixed_policy = False
        mixed_warning: DiagnosticResult | None = None

        if allow_mixed_policy:
            mixed = _solve_mixed_policy(revenue_matrix)
            if mixed is not None:
                mixed_weights, mixed_guarantee, mixed_message = mixed
                if mixed_guarantee > deterministic_guarantee + 1e-9:
                    weights = mixed_weights
                    guarantee = mixed_guarantee
                    solver_backend = "scipy_linprog"
                    solver_message = mixed_message
                    used_mixed_policy = True
                else:
                    solver_backend = "scipy_linprog"
                    solver_message = mixed_message
            else:
                mixed_warning = DiagnosticResult(
                    test_name="mixed_policy_solver",
                    status="warn",
                    message="SciPy LP solver unavailable; fell back to deterministic reserve search.",
                )

        realized_by_scenario = revenue_matrix @ weights
        nominal_expected = float(probabilities @ realized_by_scenario)
        expected_by_reserve = probabilities @ revenue_matrix
        oracle_idx = int(np.argmax(expected_by_reserve))
        oracle_expected = float(expected_by_reserve[oracle_idx])
        recommended_reserve = float(np.dot(weights, reserve_grid))
        support = [
            float(reserve_grid[idx]) for idx, weight in enumerate(weights) if float(weight) > 1.0e-8
        ]

        equivalence = _assess_revenue_equivalence(problem)
        format_recommendation = _format_recommendation(
            problem,
            equivalence=equivalence,
            used_mixed_policy=used_mixed_policy,
            deterministic_guarantee=deterministic_guarantee,
            guarantee=guarantee,
            nominal_expected=nominal_expected,
            oracle_expected=oracle_expected,
        )
        overreserve_diag = _overreserve_diagnostic(reserve_grid, expected_by_reserve)
        mixed_diag = DiagnosticResult(
            test_name="mixed_policy_gain",
            status="pass" if used_mixed_policy or not allow_mixed_policy else "warn",
            statistic=float(guarantee - deterministic_guarantee),
            message=(
                "Mixed reserve policy improved the worst-case guarantee."
                if used_mixed_policy
                else "Deterministic reserve search remained the active policy."
            ),
            metadata={
                "deterministic_guarantee": deterministic_guarantee,
                "active_policy": "mixed" if used_mixed_policy else "deterministic",
            },
        )

        diagnostics = [
            DiagnosticResult(
                test_name="revenue_equivalence",
                status=equivalence.status,
                message=equivalence.reason,
                metadata=equivalence.to_payload(),
            ),
            DiagnosticResult(
                test_name="auction_format_recommendation",
                status="pass" if format_recommendation.revenue_equivalence_holds else "warn",
                message=format_recommendation.rationale,
                metadata=format_recommendation.to_payload(),
            ),
            mixed_diag,
            overreserve_diag,
        ]
        if mixed_warning is not None:
            diagnostics.append(mixed_warning)

        certificate = AmbiguityCertificate(
            ambiguity_set_type="hybrid",
            confidence_level=1.0,
            overall_status="pass" if equivalence.holds and mixed_warning is None else "warn",
            support_description=(
                f"{revenue_matrix.shape[0]} scenarios over {reserve_grid.size} reserve points"
            ),
            regime_model="scenario_envelope_public_reserve",
            moment_bounds=(
                MomentBound(
                    name="scenario_expected_revenue",
                    order=1,
                    estimator="scenario_average",
                    point_estimate=tuple(float(value) for value in expected_by_reserve.tolist()),
                    confidence=1.0,
                    sample_size=sample_size,
                    metadata={"reserve_grid": [float(value) for value in reserve_grid.tolist()]},
                ),
                MomentBound(
                    name="scenario_worst_case_revenue",
                    order=1,
                    estimator="scenario_minimum",
                    point_estimate=tuple(float(value) for value in deterministic_min.tolist()),
                    confidence=1.0,
                    sample_size=int(revenue_matrix.shape[0]),
                    metadata={"reserve_grid": [float(value) for value in reserve_grid.tolist()]},
                ),
            ),
            per_constraint=(
                ConstraintCertificate(
                    name="worst_case_revenue",
                    constraint_class="revenue",
                    formulation=(
                        "scenario_maximin_lp" if allow_mixed_policy else "scenario_vertex_search"
                    ),
                    exactness="exact" if problem.scenario_revenues is not None else "approximation",
                    worst_case_bound=float(np.min(realized_by_scenario)),
                    threshold=(guarantee if revenue_floor is None else revenue_floor),
                    slack=(
                        0.0
                        if revenue_floor is None
                        else float(np.min(realized_by_scenario) - revenue_floor)
                    ),
                    solver_family="LP",
                    theorem_refs=(
                        ("conditional_revenue_equivalence_public_reserve",)
                        if equivalence.holds
                        else ()
                    ),
                    metadata={
                        "policy_mode": "mixed" if used_mixed_policy else "deterministic",
                        "policy_support": support,
                    },
                ),
            ),
            diagnostics=tuple(diagnostics),
            price_of_ambiguity=float(oracle_expected - guarantee),
            price_of_robustness=float(oracle_expected - nominal_expected),
            solver_runtime_ms=float((time.perf_counter() - started) * 1000.0),
            solver_backend=solver_backend,
            reproducibility={
                "reserve_grid": [float(value) for value in reserve_grid.tolist()],
                "policy_support": support,
            },
            metadata={
                "oracle_reserve": float(reserve_grid[oracle_idx]),
                "recommended_format": equivalence.recommended_format,
                "format_recommendation": format_recommendation.to_payload(),
                "solver_message": solver_message,
            },
        )

        status = (
            SolverStatus.OPTIMAL
            if used_mixed_policy or not allow_mixed_policy or mixed_warning is None
            else SolverStatus.FEASIBLE
        )
        result = OptimizationResult(
            status=status,
            objective_value=guarantee,
            variables={
                **{
                    _format_weight_key(idx, float(reserve_grid[idx])): float(weight)
                    for idx, weight in enumerate(weights.tolist())
                },
                "recommended_reserve": recommended_reserve,
                "nominal_expected_revenue": nominal_expected,
                "oracle_expected_revenue": oracle_expected,
            },
            constraints_satisfied={
                "simplex": bool(abs(float(np.sum(weights)) - 1.0) <= 1.0e-8),
                "nonnegative_weights": bool(np.all(weights >= -1.0e-10)),
                "revenue_floor": (
                    True if revenue_floor is None else bool(guarantee >= revenue_floor - 1.0e-9)
                ),
                "revenue_equivalence_conditions": bool(equivalence.holds),
            },
            solver_iterations=int(revenue_matrix.shape[0] * reserve_grid.size),
            solver_gap=None,
            solver_time_seconds=float(time.perf_counter() - started),
            uncertainty=UncertaintyEnvelope(
                point_estimate=guarantee,
                confidence_interval=(
                    float(np.min(realized_by_scenario)),
                    float(np.max(realized_by_scenario)),
                ),
                confidence_level=None,
                source=UncertaintySource.ENSEMBLE,
                propagation_method=PropagationMethod.ANALYTICAL,
                interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
                is_heuristic_ci=False,
                gate_eligible=True,
                metadata={
                    "nominal_expected_revenue": nominal_expected,
                    "oracle_expected_revenue": oracle_expected,
                    "policy_mode": "mixed" if used_mixed_policy else "deterministic",
                },
            ),
            ambiguity_certificate=certificate,
            format_recommendation=format_recommendation,
            metadata={
                "policy_mode": "mixed" if used_mixed_policy else "deterministic",
                "selected_support": support,
                "recommended_format": equivalence.recommended_format,
                "format_recommendation": format_recommendation.to_payload(),
                "revenue_equivalence": equivalence.to_payload(),
                "oracle_reserve": float(reserve_grid[oracle_idx]),
                "solver_backend": solver_backend,
                "solver_message": solver_message,
            },
        )
        emit_optimization_metrics(
            method="public_reserve_auction",
            status=result.status,
            duration_seconds=result.solver_time_seconds,
        )
        solver_info = {
            "status": result.status.value,
            "objective_value": result.objective_value,
            "backend": solver_backend,
            "message": solver_message,
            "recommended_reserve": recommended_reserve,
            "recommended_format": format_recommendation.recommended_format,
            "uncertainty_regime": format_recommendation.uncertainty_regime,
        }
        return _serialize_result(result), solver_info


__all__ = ["PublicReserveAuctionEstimator"]
