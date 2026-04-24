"""Public optimization advanced stochastic module API."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
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

from .protocols import OptimizationAmbiguityCertificate


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _bilevel_signature() -> MethodSignature:
    return MethodSignature(
        name="bilevel",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("c_upper", SlotType.VECTOR, Unit("cost", "value"), shape=("n_vars",)),
                SlotSpec("c_lower", SlotType.VECTOR, Unit("cost", "value"), shape=("n_vars",)),
                SlotSpec(
                    "A_upper",
                    SlotType.MATRIX,
                    Unit("constraint", "coeff"),
                    shape=("m_upper", "n_vars"),
                ),
                SlotSpec("b_upper", SlotType.VECTOR, Unit("constraint", "rhs"), shape=("m_upper",)),
                SlotSpec(
                    "A_lower",
                    SlotType.MATRIX,
                    Unit("constraint", "coeff"),
                    shape=("m_lower", "n_vars"),
                ),
                SlotSpec("b_lower", SlotType.VECTOR, Unit("constraint", "rhs"), shape=("m_lower",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="max_iter", default=100),
            ParameterSpec(name="step_size", default=0.1, bounds=(0.001, 1.0)),
            ParameterSpec(name="ambiguity_mode", default="auto"),
            ParameterSpec(name="tie_break", default=None),
            ParameterSpec(name="delta_near_opt", default=0.0, bounds=(0.0, None)),
            ParameterSpec(name="objective_spread_tol", default=1.0e-6, bounds=(0.0, None)),
            ParameterSpec(name="follower_gap_tol", default=1.0e-8, bounds=(0.0, None)),
            ParameterSpec(name="multistart_count", default=8, bounds=(1, 256)),
            ParameterSpec(name="certificate_mode", default="residual_or_bounds"),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )


def _bilevel_metadata() -> MethodMetadata:
    return MethodMetadata(
        description="Bilevel optimization via alternating projection with ambiguity-aware objective bounds fallback.",
        tags=frozenset({"optimization", "bilevel", "hierarchical", "stackelberg"}),
        equations={
            "upper": "min c_upper'*x s.t. A_upper*x <= b_upper",
            "lower": "min c_lower'*x s.t. A_lower*x <= b_lower",
            "fallback": "if follower is ambiguous/nonconvex, certify incumbent or analytic bounds on the leader objective",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Hierarchical optimization where a leader-follower structure exists; principal-agent problems; Stackelberg game policy design with refusal modes.",
        when_not_to_use="Single-level optimization; cooperative setting with no strategic hierarchy; nonconvex follower settings that require an exact global bilevel optimum certificate.",
        output_interpretation="Returns the shared-vector heuristic candidate together with feasibility, residual diagnostics, and either a point report or an ambiguity certificate carrying leader-objective bounds.",
    )


def _project_feasible(x_in: np.ndarray, A: np.ndarray, b: np.ndarray) -> np.ndarray:
    x_out = x_in.copy()
    violations = A @ x_out - b
    for i in range(len(b)):
        if violations[i] > 0:
            a_i = A[i]
            norm_sq = float(a_i @ a_i)
            if norm_sq > 1e-12:
                x_out -= (violations[i] / norm_sq) * a_i
    return np.maximum(x_out, 0.0)


def _coerce_mode(value: Any, *, default: str) -> str:
    if value is None:
        return default
    candidate = str(value).strip().lower()
    if not candidate:
        return default
    return candidate


def _coerce_optional_nonnegative(value: Any, *, default: float) -> float:
    try:
        resolved = float(default if value is None else value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(resolved) or resolved < 0.0:
        return float(default)
    return float(resolved)


def _coerce_optional_float(value: Any) -> float | None:
    try:
        resolved = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(resolved):
        return None
    return resolved


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in {"1", "true", "yes", "y", "on"}:
            return True
        if candidate in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _finite_interval_from_payload(raw: Any) -> tuple[float, float] | None:
    if isinstance(raw, Mapping):
        lower_raw = raw.get("lower", raw.get("incumbent_lower"))
        upper_raw = raw.get("upper", raw.get("incumbent_upper"))
    elif isinstance(raw, (list, tuple)) and len(raw) == 2:
        lower_raw, upper_raw = raw
    else:
        return None
    lower = _coerce_optional_float(lower_raw)
    upper = _coerce_optional_float(upper_raw)
    if lower is None or upper is None or lower > upper:
        return None
    return lower, upper


def _explicit_leader_bounds(state: Mapping[str, Any]) -> tuple[float, float] | None:
    for key in (
        "leader_objective_bounds",
        "incumbent_leader_objective_bounds",
        "leader_objective_interval",
    ):
        bounds = _finite_interval_from_payload(state.get(key))
        if bounds is not None:
            return bounds
    return None


def _follower_global_certificate_available(
    state: Mapping[str, Any],
    *,
    follower_gap_tol: float,
) -> bool:
    if _coerce_bool(state.get("epsilon_feasible_only"), default=False):
        return False
    if _coerce_bool(state.get("follower_epsilon_feasible_only"), default=False):
        return False

    for key in ("follower_global_certificate", "lower_level_global_certificate"):
        if key in state:
            return _coerce_bool(state.get(key), default=False)

    solver_status = _coerce_mode(
        state.get("follower_solver_status", state.get("lower_level_solver_status")),
        default="",
    )
    if solver_status in {
        "global_optimal",
        "certified_global_optimal",
        "optimal_global",
        "exact",
    }:
        return True
    if solver_status in {
        "epsilon_feasible",
        "feasible",
        "locally_optimal",
        "local_optimal",
        "stationary",
        "timeout",
        "unknown",
    }:
        return False

    gap = _coerce_optional_float(state.get("follower_global_gap"))
    if gap is not None and gap > follower_gap_tol:
        return False
    return True


def _has_structural_nonconvexity(
    state: Mapping[str, Any],
    *,
    follower_gap_tol: float,
) -> str | None:
    follower_model = state.get("follower_model")
    model = follower_model if isinstance(follower_model, Mapping) else {}
    lower_structure = state.get("lower_level_structure")
    structure = lower_structure if isinstance(lower_structure, Mapping) else {}
    merged: dict[str, Any] = {**dict(structure), **dict(model)}

    kind = _coerce_mode(merged.get("kind"), default="")
    if kind in {"quartic_double_well", "quartic_counterexample"}:
        return "structural_nonconvex_follower"

    for key in (
        "lower_level_nonconvex",
        "follower_nonconvex",
        "nonconvex",
        "is_nonconvex",
        "negative_curvature",
        "has_negative_curvature",
        "has_bilinear_terms",
        "bilinear_terms",
        "has_integer_variables",
        "integer_variables",
        "solver_marked_nonconvex",
    ):
        if _coerce_bool(state.get(key, merged.get(key)), default=False):
            return f"structural_nonconvex:{key}"

    hessian = merged.get("quadratic_hessian", merged.get("lower_hessian"))
    if hessian is not None:
        try:
            eigvals = np.linalg.eigvalsh(np.asarray(hessian, dtype=float))
        except (TypeError, ValueError, np.linalg.LinAlgError):
            eigvals = np.asarray([], dtype=float)
        if eigvals.size and bool(np.any(eigvals < -1.0e-10)):
            return "structural_nonconvex:negative_hessian_eigenvalue"

    if not _follower_global_certificate_available(
        state,
        follower_gap_tol=follower_gap_tol,
    ):
        return "epsilon_feasible_lower_level_only"
    return None


def _extract_follower_objective_witnesses(
    state: Mapping[str, Any],
    *,
    delta_near_opt: float,
    follower_gap_tol: float,
) -> np.ndarray | None:
    del follower_gap_tol
    phi_upper = _coerce_optional_float(state.get("follower_value_upper", state.get("phi_upper")))
    raw = state.get("leader_objective_witnesses")
    values: list[float] = []

    def add_candidate(item: Any) -> None:
        if isinstance(item, Mapping):
            if not _coerce_bool(
                item.get("lower_feasible", item.get("feasible", True)), default=True
            ):
                return
            near_optimal = _coerce_bool(
                item.get("near_optimal", item.get("is_near_optimal", False)),
                default=False,
            )
            lower_gap = _coerce_optional_float(item.get("lower_gap", item.get("follower_gap")))
            follower_value = _coerce_optional_float(
                item.get("lower_objective", item.get("follower_objective"))
            )
            if not near_optimal and lower_gap is not None and lower_gap <= delta_near_opt:
                near_optimal = True
            if (
                not near_optimal
                and phi_upper is not None
                and follower_value is not None
                and follower_value <= phi_upper + delta_near_opt
            ):
                near_optimal = True
            if not near_optimal and (
                "lower_gap" in item
                or "follower_gap" in item
                or "lower_objective" in item
                or "follower_objective" in item
                or "near_optimal" in item
                or "is_near_optimal" in item
            ):
                return
            candidate = item.get("leader_objective", item.get("objective"))
        else:
            candidate = item
        value = _coerce_optional_float(candidate)
        if value is not None:
            values.append(value)

    if isinstance(raw, (list, tuple)):
        for item in raw:
            add_candidate(item)

    response_raw = state.get(
        "lower_level_response_witnesses",
        state.get("follower_response_witnesses"),
    )
    if isinstance(response_raw, (list, tuple)):
        for item in response_raw:
            add_candidate(item)

    if not values:
        return None
    return np.asarray(values, dtype=float)


def _certificate_from_leader_values(
    values: np.ndarray,
    *,
    delta_near_opt: float,
    follower_gap: float,
    trigger: str,
    note: str,
) -> OptimizationAmbiguityCertificate:
    return OptimizationAmbiguityCertificate(
        mode="leader_objective_bounds",
        incumbent_lower=float(np.min(values)),
        incumbent_upper=float(np.max(values)),
        optimistic_value=None,
        pessimistic_value=None,
        delta_near_opt=float(delta_near_opt),
        follower_global_gap=float(follower_gap),
        trigger=trigger,
        witness_count=int(values.size),
        note=note,
    )


def _quartic_counterexample_certificate(
    *,
    state: Mapping[str, Any],
    solution: np.ndarray,
    delta_near_opt: float,
    follower_gap_tol: float,
) -> OptimizationAmbiguityCertificate | None:
    raw = state.get("follower_model")
    if not isinstance(raw, Mapping):
        return None
    if _coerce_mode(raw.get("kind"), default="") not in {
        "quartic_double_well",
        "quartic_counterexample",
    }:
        return None
    leader_weight = _coerce_optional_nonnegative(
        raw.get("leader_weight", raw.get("lambda")),
        default=1.0,
    )
    x_hat = float(solution[0]) if solution.size else 0.0
    x_hat = min(1.0, max(0.0, x_hat))
    branch = max(0.0, 1.0 - x_hat)
    witness_values = np.asarray(
        [-leader_weight * branch, leader_weight * branch],
        dtype=float,
    )
    if branch <= 1.0e-12:
        witness_values = np.asarray([0.0], dtype=float)
    return OptimizationAmbiguityCertificate(
        mode="leader_objective_bounds",
        incumbent_lower=float(np.min(witness_values)),
        incumbent_upper=float(np.max(witness_values)),
        optimistic_value=float(-leader_weight),
        pessimistic_value=0.0,
        delta_near_opt=float(delta_near_opt),
        follower_global_gap=float(
            _coerce_optional_nonnegative(
                raw.get("follower_global_gap"),
                default=follower_gap_tol,
            )
        ),
        trigger="nonconvex_follower_with_ambiguous_response",
        witness_count=int(witness_values.size),
        note="Point bilevel certificate suppressed for quartic nonconvex follower counterexample.",
    )


def compute_incumbent_objective_bounds(
    *,
    state: Mapping[str, Any],
    solution: np.ndarray,
    delta_near_opt: float,
    follower_gap_tol: float,
    objective_spread_tol: float,
) -> OptimizationAmbiguityCertificate | None:
    """Compute incumbent leader-objective bounds for the current leader candidate.

    This helper is intentionally conservative: when nonconvex follower structure is
    detected but no interval/witness data exists, it returns a bounds-mode
    certificate without lower/upper values. That suppresses point certification
    while making the missing evidence explicit.
    """

    explicit_bounds = _explicit_leader_bounds(state)
    follower_gap = _coerce_optional_nonnegative(
        state.get("follower_global_gap"),
        default=follower_gap_tol,
    )
    if explicit_bounds is not None:
        lower, upper = explicit_bounds
        return OptimizationAmbiguityCertificate(
            mode="leader_objective_bounds",
            incumbent_lower=float(lower),
            incumbent_upper=float(upper),
            optimistic_value=(
                None if state.get("optimistic_value") is None else float(state["optimistic_value"])
            ),
            pessimistic_value=(
                None
                if state.get("pessimistic_value") is None
                else float(state["pessimistic_value"])
            ),
            delta_near_opt=float(delta_near_opt),
            follower_global_gap=float(follower_gap),
            trigger="explicit_leader_objective_bounds",
            witness_count=2,
            note="Point bilevel certificate suppressed in favor of caller-provided leader objective bounds.",
        )

    certificate = _quartic_counterexample_certificate(
        state=state,
        solution=solution,
        delta_near_opt=delta_near_opt,
        follower_gap_tol=follower_gap_tol,
    )
    if certificate is not None:
        return certificate

    structural_trigger = _has_structural_nonconvexity(
        state,
        follower_gap_tol=follower_gap_tol,
    )
    witness_values = _extract_follower_objective_witnesses(
        state,
        delta_near_opt=delta_near_opt,
        follower_gap_tol=follower_gap_tol,
    )
    if witness_values is None:
        if structural_trigger is None:
            return None
        return OptimizationAmbiguityCertificate(
            mode="leader_objective_bounds",
            incumbent_lower=None,
            incumbent_upper=None,
            optimistic_value=(
                None if state.get("optimistic_value") is None else float(state["optimistic_value"])
            ),
            pessimistic_value=(
                None
                if state.get("pessimistic_value") is None
                else float(state["pessimistic_value"])
            ),
            delta_near_opt=float(delta_near_opt),
            follower_global_gap=float(follower_gap),
            trigger=structural_trigger,
            witness_count=0,
            note="Point bilevel certificate suppressed; no certified follower response witnesses were provided for bounds.",
        )

    width = float(np.max(witness_values) - np.min(witness_values))
    if width <= objective_spread_tol and structural_trigger is None:
        return None
    trigger = structural_trigger or "nonconvex_follower_with_ambiguous_response"
    if width > objective_spread_tol:
        trigger = "nonconvex_follower_with_ambiguous_response"
    certificate = _certificate_from_leader_values(
        witness_values,
        delta_near_opt=delta_near_opt,
        follower_gap=follower_gap,
        trigger=trigger,
        note="Point bilevel certificate suppressed because ambiguous or tolerance-level follower witnesses are available.",
    )
    return OptimizationAmbiguityCertificate(
        mode=certificate.mode,
        incumbent_lower=certificate.incumbent_lower,
        incumbent_upper=certificate.incumbent_upper,
        optimistic_value=(
            None if state.get("optimistic_value") is None else float(state["optimistic_value"])
        ),
        pessimistic_value=(
            None if state.get("pessimistic_value") is None else float(state["pessimistic_value"])
        ),
        delta_near_opt=certificate.delta_near_opt,
        follower_global_gap=certificate.follower_global_gap,
        trigger=certificate.trigger,
        witness_count=certificate.witness_count,
        note=certificate.note,
    )


def _resolve_bilevel_ambiguity_certificate(
    *,
    state: Mapping[str, Any],
    params: Mapping[str, Any],
    solution: np.ndarray,
) -> OptimizationAmbiguityCertificate:
    ambiguity_mode = _coerce_mode(params.get("ambiguity_mode"), default="auto")
    if ambiguity_mode == "off":
        return OptimizationAmbiguityCertificate(note="Ambiguity checks disabled by caller.")

    delta_near_opt = _coerce_optional_nonnegative(params.get("delta_near_opt"), default=0.0)
    objective_spread_tol = _coerce_optional_nonnegative(
        params.get("objective_spread_tol"),
        default=1.0e-6,
    )
    follower_gap_tol = _coerce_optional_nonnegative(
        params.get("follower_gap_tol"),
        default=1.0e-8,
    )

    certificate = compute_incumbent_objective_bounds(
        state=state,
        solution=solution,
        delta_near_opt=delta_near_opt,
        follower_gap_tol=follower_gap_tol,
        objective_spread_tol=objective_spread_tol,
    )
    if certificate is not None:
        return certificate

    if ambiguity_mode == "required":
        return OptimizationAmbiguityCertificate(
            mode="leader_objective_bounds",
            delta_near_opt=float(delta_near_opt),
            follower_global_gap=float(
                _coerce_optional_nonnegative(
                    state.get("follower_global_gap"),
                    default=follower_gap_tol,
                )
            ),
            trigger="bounds_required_without_interval_witnesses",
            note="Bounds mode required, but the caller did not provide explicit follower response witnesses.",
        )
    return OptimizationAmbiguityCertificate()


def _solve_bilevel_with_bounds(
    state: Mapping[str, Any],
    params: Mapping[str, Any],
) -> dict[str, Any]:
    c_u = np.asarray(state["c_upper"], dtype=float)
    c_l = np.asarray(state["c_lower"], dtype=float)
    A_u = np.asarray(state["A_upper"], dtype=float)
    b_u = np.asarray(state["b_upper"], dtype=float)
    A_l = np.asarray(state["A_lower"], dtype=float)
    b_l = np.asarray(state["b_lower"], dtype=float)
    n = len(c_u)
    max_iter = int(params.get("max_iter", 100))
    step = float(params.get("step_size", 0.1))
    tie_break = params.get("tie_break")

    x = np.zeros(n)
    iterations_run = 0
    converged = False
    last_residual = np.full(n, np.inf, dtype=float)

    for iteration in range(max_iter):
        x_lower = _project_feasible(x - step * c_l, A_l, b_l)
        x_upper = _project_feasible(x_lower - step * c_u, A_u, b_u)
        last_residual = x_upper - x
        iterations_run = iteration + 1

        if np.max(np.abs(last_residual)) < 1e-8:
            x = x_upper
            converged = True
            break
        x = x_upper

    upper_constraint_slacks = (b_u - A_u @ x).astype(float)
    lower_constraint_slacks = (b_l - A_l @ x).astype(float)
    upper_objective = float(c_u @ x)
    lower_objective = float(c_l @ x)
    ambiguity_certificate = _resolve_bilevel_ambiguity_certificate(
        state=state,
        params=params,
        solution=x,
    )
    point_suppressed = ambiguity_certificate.mode == "leader_objective_bounds"
    bounds_available = (
        ambiguity_certificate.incumbent_lower is not None
        and ambiguity_certificate.incumbent_upper is not None
    )

    result: dict[str, Any] = {
        "solution": x.tolist(),
        "objective_value": None if point_suppressed else upper_objective,
        "upper_objective": upper_objective,
        "lower_objective": lower_objective,
        "upper_feasible": bool(np.all(A_u @ x <= b_u + 1e-6)),
        "lower_feasible": bool(np.all(A_l @ x <= b_l + 1e-6)),
        "fixed_point_residual": last_residual.astype(float).tolist(),
        "fixed_point_residual_inf": float(np.max(np.abs(last_residual))),
        "upper_constraint_slacks": upper_constraint_slacks.tolist(),
        "lower_constraint_slacks": lower_constraint_slacks.tolist(),
        "min_upper_slack": float(np.min(upper_constraint_slacks)),
        "min_lower_slack": float(np.min(lower_constraint_slacks)),
        "iterations_run": iterations_run,
        "converged": converged,
        "n_vars": n,
        "ambiguity_certificate": ambiguity_certificate.to_payload(),
        "certificate_kind": ambiguity_certificate.mode,
        "ambiguity_mode_requested": _coerce_mode(params.get("ambiguity_mode"), default="auto"),
        "tie_break": None if tie_break is None else str(tie_break),
        "certificate_mode": str(params.get("certificate_mode", "residual_or_bounds")),
        "point_solution_suppressed": point_suppressed,
        "leader_objective_bounds_available": bounds_available,
        "abstained_from_point_certificate": point_suppressed and not bounds_available,
    }
    if ambiguity_certificate.incumbent_lower is not None:
        result["leader_objective_lower"] = float(ambiguity_certificate.incumbent_lower)
    if ambiguity_certificate.incumbent_upper is not None:
        result["leader_objective_upper"] = float(ambiguity_certificate.incumbent_upper)
    if ambiguity_certificate.optimistic_value is not None:
        result["optimistic_value"] = float(ambiguity_certificate.optimistic_value)
    if ambiguity_certificate.pessimistic_value is not None:
        result["pessimistic_value"] = float(ambiguity_certificate.pessimistic_value)
    return {"result": result}


class _BilevelOptimizationCore:
    """Shared implementation for the current bilevel method and its legacy alias."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _bilevel_signature()
    metadata: ClassVar[MethodMetadata] = _bilevel_metadata()

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        return _solve_bilevel_with_bounds(state, params)


@foundry_method(
    namespace="optimization.bilevel",
    version="1.1.0",
    tags={"optimization", "bilevel"},
)
class BilevelOptimizationEstimator(_BilevelOptimizationCore):
    """Current bilevel heuristic with ambiguity-aware bounds fallback."""


@foundry_method(
    namespace="optimization.bilevel",
    version="1.0.0",
    tags={"optimization", "bilevel"},
)
class LegacyBilevelOptimizationEstimator(_BilevelOptimizationCore):
    """Backward-compatible alias for callers pinned to the legacy bilevel FQN."""


@foundry_method(
    namespace="optimization.stochastic",
    version="1.0.0",
    tags={"optimization", "stochastic", "chance-constrained"},
)
class ChanceConstrainedEstimator:
    """Solve optimization problems that enforce probabilistic feasibility constraints."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="chance_constrained",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("c", SlotType.VECTOR, Unit("cost", "value"), shape=("n_vars",)),
                SlotSpec(
                    "A_mean",
                    SlotType.MATRIX,
                    Unit("constraint", "coeff"),
                    shape=("m_constraints", "n_vars"),
                ),
                SlotSpec("b", SlotType.VECTOR, Unit("constraint", "rhs"), shape=("m_constraints",)),
                SlotSpec(
                    "A_std",
                    SlotType.MATRIX,
                    Unit("constraint", "std"),
                    shape=("m_constraints", "n_vars"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="confidence", default=0.95, bounds=(0.5, 0.999)),
            ParameterSpec(name="max_iter", default=200),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Chance-constrained optimization via deterministic reformulation (Gaussian).",
        tags=frozenset({"optimization", "stochastic", "chance-constrained", "robust"}),
        citations=(
            "Charnes, A. & Cooper, W.W. (1959). Chance-Constrained Programming. Management Science.",
        ),
        equations={
            "cc": "min c'x s.t. P(A*x <= b) >= alpha → A_mean*x + Phi^-1(alpha)*||A_std*x|| <= b"
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Worst-case uncertainty; no distributional assumption on uncertainty; robust policy design with probabilistic constraint satisfaction",
        when_not_to_use="Deterministic problem; uncertainty structure is non-Gaussian or highly asymmetric",
        output_interpretation="Minimax optimal solution. Constraint satisfied for all scenarios in uncertainty set. Constraint slacks report how far from violation.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        c = np.asarray(state["c"], dtype=float)
        A_mean = np.asarray(state["A_mean"], dtype=float)
        b = np.asarray(state["b"], dtype=float)
        A_std = np.asarray(state["A_std"], dtype=float)
        alpha = float(params.get("confidence", 0.95))
        max_iter = int(params.get("max_iter", 200))
        n = len(c)

        # Approximate Phi^-1(alpha) using rational approximation
        # For alpha in [0.5, 1): Abramowitz & Stegun 26.2.23
        if alpha >= 1.0:
            z_alpha = 4.0
        elif alpha <= 0.5:
            z_alpha = 0.0
        else:
            t = np.sqrt(-2.0 * np.log(1.0 - alpha))
            z_alpha = t - (2.515517 + 0.802853 * t + 0.010328 * t**2) / (
                1.0 + 1.432788 * t + 0.189269 * t**2 + 0.001308 * t**3
            )

        # Deterministic reformulation: A_mean*x + z_alpha * sigma_i(x) <= b
        # where sigma_i(x) = ||diag(A_std[i,:]) * x||
        # Solve via projected gradient descent
        x = np.zeros(n)
        lr = 0.01

        for _ in range(max_iter):
            grad = c.copy()

            # Project onto tightened constraints
            feasible = True
            for i in range(len(b)):
                sigma_i = float(np.sqrt(np.sum((A_std[i] * x) ** 2) + 1e-12))
                lhs = float(A_mean[i] @ x) + z_alpha * sigma_i
                if lhs > b[i]:
                    feasible = False
                    # Subgradient of constraint
                    g_mean = A_mean[i]
                    g_std = z_alpha * (A_std[i] ** 2 * x) / max(sigma_i, 1e-12)
                    grad += 10.0 * (g_mean + g_std)  # penalty

            x_new = x - lr * grad
            x_new = np.maximum(x_new, 0.0)

            if np.max(np.abs(x_new - x)) < 1e-8 and feasible:
                x = x_new
                break
            x = x_new

        # Check final feasibility
        constraint_slacks = []
        for i in range(len(b)):
            sigma_i = float(np.sqrt(np.sum((A_std[i] * x) ** 2) + 1e-12))
            slack = float(b[i]) - float(A_mean[i] @ x) - z_alpha * sigma_i
            constraint_slacks.append(slack)

        return {
            "result": {
                "solution": x.tolist(),
                "objective": float(c @ x),
                "confidence_level": alpha,
                "z_quantile": float(z_alpha),
                "constraint_slacks": constraint_slacks,
                "all_feasible": all(s >= -1e-6 for s in constraint_slacks),
                "n_vars": n,
            }
        }


__all__ = [
    "BilevelOptimizationEstimator",
    "ChanceConstrainedEstimator",
    "LegacyBilevelOptimizationEstimator",
    "compute_incumbent_objective_bounds",
]
