"""Public optimization convex module API."""

from __future__ import annotations

import time
from collections.abc import Mapping
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
from polisyos.ir.analytics.uncertainty import RobustSetFamily, RobustSetSpec

from .protocols import AmbiguityCertificate, DiagnosticResult, OptimizationResult


def _mapping_payload(state: Any) -> dict[str, Any]:
    if isinstance(state, Mapping):
        return dict(state)
    raise TypeError("state must be a mapping")


def _solver_status(status: str) -> SolverStatus:
    normalized = str(status).lower()
    if "optimal" in normalized:
        return SolverStatus.OPTIMAL
    if "infeasible" in normalized:
        return SolverStatus.INFEASIBLE
    if "unbounded" in normalized:
        return SolverStatus.UNBOUNDED
    if "limit" in normalized or "timeout" in normalized:
        return SolverStatus.TIMEOUT
    if "error" in normalized:
        return SolverStatus.ERROR
    return SolverStatus.UNKNOWN


def _serialize_result(result: OptimizationResult) -> dict[str, Any]:
    payload = result.to_payload()
    payload["contract_id"] = OptimizationResult.contract_id
    return payload


def _vector(value: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D array")
    return arr


def _matrix(value: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"{name} must be a 2D array")
    return arr


def _extract_bounds(payload: Mapping[str, Any], n_vars: int) -> tuple[np.ndarray, np.ndarray]:
    bounds = payload.get("bounds")
    if bounds is None:
        return np.zeros(n_vars, dtype=float), np.full(n_vars, np.inf, dtype=float)
    arr = np.asarray(bounds, dtype=float)
    if arr.ndim != 2 or arr.shape[0] != n_vars or arr.shape[1] != 2:
        raise ValueError("bounds must have shape (n_vars, 2)")
    return arr[:, 0], arr[:, 1]


def _pick_solver(cp: Any, requested: str, *fallbacks: str) -> Any:
    installed = {str(name).upper() for name in cp.installed_solvers()}
    candidates = (requested, *fallbacks)
    for candidate in candidates:
        candidate_name = str(candidate).upper()
        if candidate_name in installed and hasattr(cp, candidate_name):
            return getattr(cp, candidate_name)
    return None


def _matrix_square_root(covariance: np.ndarray) -> np.ndarray:
    symmetric = 0.5 * (covariance + covariance.T)
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    clipped = np.clip(eigenvalues, a_min=0.0, a_max=None)
    return (eigenvectors * np.sqrt(clipped)) @ eigenvectors.T


def _coerce_robust_set_spec(
    value: Any,
    *,
    expected_dim: int,
    objective_center: np.ndarray,
) -> RobustSetSpec:
    spec = RobustSetSpec.model_validate(value)
    if spec.dimension != expected_dim:
        raise ValueError("robust_set_spec dimension must match objective_vector length")
    if not np.allclose(
        np.asarray(spec.center, dtype=float), objective_center, atol=1e-8, rtol=1e-6
    ):
        raise ValueError("robust_set_spec.center must match objective_vector")
    if spec.family not in {RobustSetFamily.BOX, RobustSetFamily.ELLIPSOID}:
        raise ValueError(
            "set-based robust optimization currently supports only box and ellipsoid families"
        )
    return spec


def _box_support_penalty_value(
    vector: np.ndarray,
    *,
    rho: float,
    scale_diag: np.ndarray,
) -> float:
    return float(max(rho, 0.0) * np.linalg.norm(scale_diag * vector, ord=1))


def _ellipsoid_support_penalty_value(
    vector: np.ndarray,
    *,
    rho: float,
    covariance: np.ndarray,
) -> float:
    sqrt_cov = _matrix_square_root(covariance)
    return float(max(rho, 0.0) * np.linalg.norm(sqrt_cov @ vector, ord=2))


def _support_penalty_value(vector: np.ndarray, spec: RobustSetSpec) -> float:
    arr = np.asarray(vector, dtype=float)
    if spec.family is RobustSetFamily.BOX:
        scale_diag = np.asarray(spec.scale_diag, dtype=float)
        return _box_support_penalty_value(arr, rho=spec.size_parameter, scale_diag=scale_diag)
    covariance = np.asarray(spec.covariance, dtype=float)
    return _ellipsoid_support_penalty_value(arr, rho=spec.size_parameter, covariance=covariance)


def _support_penalty_expression(cp: Any, x: Any, spec: RobustSetSpec) -> Any:
    if spec.family is RobustSetFamily.BOX:
        scale_diag = np.asarray(spec.scale_diag, dtype=float)
        return spec.size_parameter * cp.norm1(cp.multiply(scale_diag, x))
    covariance = np.asarray(spec.covariance, dtype=float)
    sqrt_cov = _matrix_square_root(covariance)
    return spec.size_parameter * cp.norm(sqrt_cov @ x, 2)


def _coverage_confidence(spec: RobustSetSpec) -> float:
    if spec.coverage_target is None or spec.coverage_target <= 0.0:
        return 1.0
    return float(min(spec.coverage_target, 1.0))


def _support_description(spec: RobustSetSpec) -> str:
    if spec.family is RobustSetFamily.BOX:
        return "box objective-coefficient set: {center + diag(scale_diag) z: ||z||_inf <= rho}"
    return "ellipsoid objective-coefficient set: {center + covariance^{1/2} z: ||z||_2 <= rho}"


def _set_based_ambiguity_certificate(
    *,
    spec: RobustSetSpec,
    status: SolverStatus,
    support_penalty: float,
    solver_name: str,
    elapsed_seconds: float,
) -> AmbiguityCertificate:
    """Build the Phase 3 ambiguity certificate for an explicit robust set."""

    is_solved = status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}
    coverage_declared = spec.coverage_target is not None and spec.coverage_target > 0.0
    diagnostic_status = "pass" if is_solved and coverage_declared else "warn"
    ambiguity_set_type = "robust_box" if spec.family is RobustSetFamily.BOX else "robust_ellipsoid"
    return AmbiguityCertificate(
        ambiguity_set_type=ambiguity_set_type,  # type: ignore[arg-type]
        confidence_level=_coverage_confidence(spec),
        overall_status="pass" if diagnostic_status == "pass" else "warn",
        support_description=_support_description(spec),
        price_of_robustness=float(support_penalty),
        solver_runtime_ms=float(elapsed_seconds * 1000.0),
        solver_backend=solver_name,
        diagnostics=(
            DiagnosticResult(
                test_name="robust_set_geometry",
                status=diagnostic_status,  # type: ignore[arg-type]
                message=(
                    "Explicit robust uncertainty set applied through its support function."
                    if is_solved
                    else "Solver did not return a solved robust counterpart status."
                ),
                statistic=float(spec.size_parameter),
                metadata={
                    "family": spec.family.value,
                    "coverage_target": spec.coverage_target,
                    "calibration_method": spec.calibration_method.value,
                },
            ),
            DiagnosticResult(
                test_name="deadweight_conservatism_premium",
                status="pass",
                message="Support-function premium at the returned decision.",
                statistic=float(support_penalty),
                metadata={
                    "interpretation": "rho * h_U(x)",
                    "theorem_scope": "affine_objective_uncertainty",
                },
            ),
        ),
        metadata={
            "model_semantics": "set_based_robust_counterpart",
            "uncertainty_enters": "objective_coefficients",
            "robust_set_spec": spec.model_dump(mode="python", exclude_none=True),
        },
    )


def _legacy_penalized_nominal_certificate(
    *,
    rho: float,
    solution: np.ndarray,
    solver_name: str,
    elapsed_seconds: float,
) -> AmbiguityCertificate:
    premium = float(max(rho, 0.0) * np.linalg.norm(np.asarray(solution, dtype=float), ord=1))
    return AmbiguityCertificate(
        ambiguity_set_type="hybrid",
        confidence_level=1.0,
        overall_status="warn",
        support_description="legacy penalized nominal objective c'x - rho||x||_1; no calibrated robust set",
        price_of_robustness=premium,
        solver_runtime_ms=float(elapsed_seconds * 1000.0),
        solver_backend=solver_name,
        diagnostics=(
            DiagnosticResult(
                test_name="robust_set_semantics",
                status="warn",
                message=(
                    "Legacy robust_optimization uses an L1 penalty and does not certify "
                    "coverage or set adequacy."
                ),
                statistic=float(rho),
                metadata={"model_semantics": "penalized_nominal"},
            ),
        ),
        metadata={
            "model_semantics": "penalized_nominal",
            "coverage_certified": False,
        },
    )


@foundry_method(
    namespace="optimization.convex",
    version="1.0.0",
    tags={"optimization", "convex", "quadratic-program"},
)
class QuadraticProgramEstimator:
    """Solve quadratic programs for allocation or control problems with smooth objectives."""

    runtime_stack: ClassVar[tuple[str, ...]] = ("cvxpy", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="quadratic_program",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "objective_vector",
                    SlotType.VECTOR,
                    Unit("objective", "value"),
                    shape=("n_vars",),
                ),
                SlotSpec(
                    "quadratic_matrix",
                    SlotType.MATRIX,
                    Unit("quadratic", "value"),
                    shape=("n_vars", "n_vars"),
                ),
                SlotSpec(
                    "constraint_matrix",
                    SlotType.MATRIX,
                    Unit("constraint", "value"),
                    shape=("n_constraints", "n_vars"),
                ),
                SlotSpec(
                    "constraint_rhs",
                    SlotType.VECTOR,
                    Unit("constraint", "value"),
                    shape=("n_constraints",),
                ),
                SlotSpec("bounds", SlotType.MATRIX, Unit("bound", "value"), shape=("n_vars", 2)),
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
            ParameterSpec(name="objective", default="maximize"),
            ParameterSpec(name="solver", default="OSQP"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.SOLVER,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Quadratic program with explicit vectors, matrices, and bounds.",
        tags=frozenset({"optimization", "convex", "quadratic-program"}),
        when_to_use="Convex objective + constraints; portfolio optimization, signal processing, regression variants",
        citations=(
            "Boyd, S. & Vandenberghe, L. (2004). Convex Optimization. Cambridge University Press.",
        ),
        when_not_to_use="Non-convex quadratic objective (indefinite Q); integer variables required",
        output_interpretation="Globally optimal solution (convex guarantees). KKT conditions hold at optimum.",
    )

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any], fallback_state: Any
    ) -> Mapping[str, Any]:
        payload = _mapping_payload(fallback_state) if isinstance(fallback_state, Mapping) else {}
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(
        state: Mapping[str, Any], params: Mapping[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        import cvxpy as cp

        payload = _mapping_payload(state)
        c = _vector(payload["objective_vector"], name="objective_vector")
        q = _matrix(payload["quadratic_matrix"], name="quadratic_matrix")
        a = _matrix(payload["constraint_matrix"], name="constraint_matrix")
        b = _vector(payload["constraint_rhs"], name="constraint_rhs")
        if (
            a.shape[0] != b.shape[0]
            or a.shape[1] != c.shape[0]
            or q.shape != (c.shape[0], c.shape[0])
        ):
            raise ValueError("objective/constraint/quadratic dimensions are inconsistent")
        lb, ub = _extract_bounds(payload, c.shape[0])

        x = cp.Variable(c.shape[0])
        q_psd = 0.5 * (q + q.T) + 1e-8 * np.eye(q.shape[0], dtype=float)
        objective_name = str(params.get("objective", "maximize")).lower()
        expr = cp.sum(cp.multiply(c, x)) - 0.5 * cp.quad_form(x, q_psd)
        objective = cp.Maximize(expr) if objective_name == "maximize" else cp.Minimize(-expr)
        constraints = [a @ x <= b, x >= lb]
        finite_ub = np.isfinite(ub)
        if finite_ub.any():
            constraints.append(x[finite_ub] <= ub[finite_ub])
        problem = cp.Problem(objective, constraints)

        started = time.perf_counter()
        solver_name = str(params.get("solver", "OSQP")).upper()
        solver = _pick_solver(cp, solver_name, "OSQP", "CLARABEL", "SCS")
        problem.solve(solver=solver, verbose=False)
        elapsed = time.perf_counter() - started

        status = _solver_status(problem.status)
        solution = (
            np.zeros(c.shape[0], dtype=float)
            if x.value is None
            else np.asarray(x.value, dtype=float)
        )
        lhs = a @ solution
        constraints_ok = {
            f"constraint_{idx}": bool(lhs[idx] <= b[idx] + 1e-6) for idx in range(a.shape[0])
        }
        constraints_ok["lower_bounds"] = bool(np.all(solution >= lb - 1e-6))
        constraints_ok["upper_bounds"] = bool(np.all(solution[finite_ub] <= ub[finite_ub] + 1e-6))

        result = OptimizationResult(
            status=status,
            objective_value=(None if problem.value is None else float(problem.value)),
            variables={f"x_{idx}": float(solution[idx]) for idx in range(solution.shape[0])},
            constraints_satisfied=constraints_ok,
            solver_iterations=int(getattr(problem.solver_stats, "num_iters", 0) or 0),
            solver_gap=None,
            solver_time_seconds=float(
                getattr(problem.solver_stats, "solve_time", elapsed) or elapsed
            ),
            metadata={"solver": solver_name, "objective": objective_name},
        )
        solver_info = {
            "status": status.value,
            "gap": None,
            "iterations": result.solver_iterations,
            "objective_value": result.objective_value,
            "solver": solver_name,
        }
        return _serialize_result(result), solver_info


@foundry_method(
    namespace="optimization.convex",
    version="1.0.0",
    tags={"optimization", "convex", "robust-optimization"},
)
class RobustOptimizationEstimator:
    """Solve the legacy L1-penalized nominal proxy that predates set-based robust optimization."""

    runtime_stack: ClassVar[tuple[str, ...]] = ("cvxpy", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="robust_optimization",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "objective_vector",
                    SlotType.VECTOR,
                    Unit("objective", "value"),
                    shape=("n_vars",),
                ),
                SlotSpec(
                    "constraint_matrix",
                    SlotType.MATRIX,
                    Unit("constraint", "value"),
                    shape=("n_constraints", "n_vars"),
                ),
                SlotSpec(
                    "constraint_rhs",
                    SlotType.VECTOR,
                    Unit("constraint", "value"),
                    shape=("n_constraints",),
                ),
                SlotSpec("bounds", SlotType.MATRIX, Unit("bound", "value"), shape=("n_vars", 2)),
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
            ParameterSpec(name="uncertainty_radius", default=0.1),
            ParameterSpec(name="solver", default="ECOS"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.SOLVER,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Legacy robust proxy: nominal linear allocation with an L1 penalty on decision magnitude. "
            "This is not an explicit set-based robust counterpart."
        ),
        tags=frozenset({"optimization", "convex", "robust-optimization"}),
        when_to_use=(
            "Backward-compatible regularized allocation problems where the legacy "
            "uncertainty_radius * ||x||_1 penalty is still the desired behavior"
        ),
        citations=(
            "Ben-Tal, A., El Ghaoui, L. & Nemirovski, A. (2009). Robust Optimization. Princeton University Press.",
        ),
        when_not_to_use=(
            "When you need a calibrated box/ellipsoid uncertainty set or an explicit "
            "robust counterpart for uncertain coefficients"
        ),
        output_interpretation=(
            "Optimal solution to a penalized nominal problem. The objective is c'x - rho||x||_1, "
            "not a general robust counterpart."
        ),
    )

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any], fallback_state: Any
    ) -> Mapping[str, Any]:
        payload = _mapping_payload(fallback_state) if isinstance(fallback_state, Mapping) else {}
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(
        state: Mapping[str, Any], params: Mapping[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        import cvxpy as cp

        payload = _mapping_payload(state)
        c = _vector(payload["objective_vector"], name="objective_vector")
        a = _matrix(payload["constraint_matrix"], name="constraint_matrix")
        b = _vector(payload["constraint_rhs"], name="constraint_rhs")
        if a.shape[0] != b.shape[0] or a.shape[1] != c.shape[0]:
            raise ValueError("objective/constraint dimensions are inconsistent")
        lb, ub = _extract_bounds(payload, c.shape[0])
        rho = max(0.0, float(params.get("uncertainty_radius", 0.1)))

        x = cp.Variable(c.shape[0])
        objective = cp.Maximize(cp.sum(cp.multiply(c, x)) - rho * cp.norm1(x))
        constraints = [a @ x <= b, x >= lb]
        finite_ub = np.isfinite(ub)
        if finite_ub.any():
            constraints.append(x[finite_ub] <= ub[finite_ub])
        problem = cp.Problem(objective, constraints)

        started = time.perf_counter()
        solver_name = str(params.get("solver", "ECOS")).upper()
        solver = _pick_solver(cp, solver_name, "SCS", "CLARABEL", "OSQP")
        problem.solve(solver=solver, verbose=False)
        elapsed = time.perf_counter() - started

        status = _solver_status(problem.status)
        solution = (
            np.zeros(c.shape[0], dtype=float)
            if x.value is None
            else np.asarray(x.value, dtype=float)
        )
        lhs = a @ solution
        constraints_ok = {
            f"constraint_{idx}": bool(lhs[idx] <= b[idx] + 1e-6) for idx in range(a.shape[0])
        }
        result = OptimizationResult(
            status=status,
            objective_value=(None if problem.value is None else float(problem.value)),
            variables={f"x_{idx}": float(solution[idx]) for idx in range(solution.shape[0])},
            constraints_satisfied=constraints_ok,
            solver_iterations=int(getattr(problem.solver_stats, "num_iters", 0) or 0),
            solver_gap=None,
            solver_time_seconds=float(
                getattr(problem.solver_stats, "solve_time", elapsed) or elapsed
            ),
            ambiguity_certificate=_legacy_penalized_nominal_certificate(
                rho=rho,
                solution=solution,
                solver_name=solver_name,
                elapsed_seconds=elapsed,
            ),
            metadata={
                "solver": solver_name,
                "uncertainty_radius": rho,
                "model_semantics": "penalized_nominal",
                "legacy_warning": (
                    "This estimator applies an L1 regularization penalty rather than an explicit "
                    "box or ellipsoid uncertainty set."
                ),
            },
        )
        solver_info = {
            "status": status.value,
            "gap": None,
            "iterations": result.solver_iterations,
            "objective_value": result.objective_value,
            "solver": solver_name,
        }
        return _serialize_result(result), solver_info


@foundry_method(
    namespace="optimization.convex",
    version="1.0.0",
    tags={"optimization", "convex", "robust-optimization", "set-based-robust"},
)
class SetBasedRobustLinearEstimator:
    """Solve a linear objective with an explicit box or ellipsoid uncertainty set."""

    runtime_stack: ClassVar[tuple[str, ...]] = ("cvxpy", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="set_based_robust_linear",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "objective_vector",
                    SlotType.VECTOR,
                    Unit("objective", "value"),
                    shape=("n_vars",),
                ),
                SlotSpec(
                    "constraint_matrix",
                    SlotType.MATRIX,
                    Unit("constraint", "value"),
                    shape=("n_constraints", "n_vars"),
                ),
                SlotSpec(
                    "constraint_rhs",
                    SlotType.VECTOR,
                    Unit("constraint", "value"),
                    shape=("n_constraints",),
                ),
                SlotSpec("bounds", SlotType.MATRIX, Unit("bound", "value"), shape=("n_vars", 2)),
                SlotSpec(
                    "robust_set_spec",
                    SlotType.SCALAR,
                    Unit("uncertainty", "json"),
                    contract_id=RobustSetSpec.contract_id,
                ),
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
        parameters=(ParameterSpec(name="solver", default="CLARABEL"),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.SOLVER,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Set-based robust linear optimization for uncertain objective coefficients. "
            "Supports weighted box and ellipsoid uncertainty sets via support-function penalties."
        ),
        tags=frozenset({"optimization", "convex", "robust-optimization", "set-based-robust"}),
        when_to_use=(
            "Objective coefficients are uncertain and you want an explicit robust counterpart "
            "with a calibrated box or ellipsoid uncertainty set"
        ),
        citations=(
            "Ben-Tal, A., El Ghaoui, L. & Nemirovski, A. (2009). Robust Optimization. Princeton University Press.",
            "Bertsimas, D. & Sim, M. (2004). The Price of Robustness. Operations Research.",
        ),
        when_not_to_use=(
            "Uncertainty primarily enters nonlinear constraints or requires scenario-based "
            "chance constraints instead of a support-function reformulation"
        ),
        output_interpretation=(
            "Optimal solution to max c'x - rho h_U(x), where h_U is the support function of "
            "the selected uncertainty-set family."
        ),
    )

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any], fallback_state: Any
    ) -> Mapping[str, Any]:
        payload = _mapping_payload(fallback_state) if isinstance(fallback_state, Mapping) else {}
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(
        state: Mapping[str, Any], params: Mapping[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        import cvxpy as cp

        payload = _mapping_payload(state)
        c = _vector(payload["objective_vector"], name="objective_vector")
        a = _matrix(payload["constraint_matrix"], name="constraint_matrix")
        b = _vector(payload["constraint_rhs"], name="constraint_rhs")
        if a.shape[0] != b.shape[0] or a.shape[1] != c.shape[0]:
            raise ValueError("objective/constraint dimensions are inconsistent")
        lb, ub = _extract_bounds(payload, c.shape[0])
        spec = _coerce_robust_set_spec(
            payload["robust_set_spec"],
            expected_dim=c.shape[0],
            objective_center=c,
        )

        x = cp.Variable(c.shape[0])
        penalty = _support_penalty_expression(cp, x, spec)
        objective = cp.Maximize(cp.sum(cp.multiply(c, x)) - penalty)
        constraints = [a @ x <= b, x >= lb]
        finite_ub = np.isfinite(ub)
        if finite_ub.any():
            constraints.append(x[finite_ub] <= ub[finite_ub])
        problem = cp.Problem(objective, constraints)

        started = time.perf_counter()
        solver_name = str(params.get("solver", "CLARABEL")).upper()
        solver = _pick_solver(cp, solver_name, "CLARABEL", "SCS", "OSQP")
        problem.solve(solver=solver, verbose=False)
        elapsed = time.perf_counter() - started

        status = _solver_status(problem.status)
        solution = (
            np.zeros(c.shape[0], dtype=float)
            if x.value is None
            else np.asarray(x.value, dtype=float)
        )
        lhs = a @ solution
        constraints_ok = {
            f"constraint_{idx}": bool(lhs[idx] <= b[idx] + 1e-6) for idx in range(a.shape[0])
        }
        constraints_ok["lower_bounds"] = bool(np.all(solution >= lb - 1e-6))
        constraints_ok["upper_bounds"] = bool(np.all(solution[finite_ub] <= ub[finite_ub] + 1e-6))

        support_penalty = _support_penalty_value(solution, spec)
        result = OptimizationResult(
            status=status,
            objective_value=(None if problem.value is None else float(problem.value)),
            variables={f"x_{idx}": float(solution[idx]) for idx in range(solution.shape[0])},
            constraints_satisfied=constraints_ok,
            solver_iterations=int(getattr(problem.solver_stats, "num_iters", 0) or 0),
            solver_gap=None,
            solver_time_seconds=float(
                getattr(problem.solver_stats, "solve_time", elapsed) or elapsed
            ),
            ambiguity_certificate=_set_based_ambiguity_certificate(
                spec=spec,
                status=status,
                support_penalty=support_penalty,
                solver_name=solver_name,
                elapsed_seconds=elapsed,
            ),
            metadata={
                "solver": solver_name,
                "model_semantics": "set_based_robust_counterpart",
                "robust_set_family": spec.family.value,
                "size_parameter": float(spec.size_parameter),
                "coverage_target": spec.coverage_target,
                "calibration_method": spec.calibration_method.value,
                "support_penalty_at_solution": support_penalty,
                "robust_set_spec": spec.model_dump(mode="python", exclude_none=True),
            },
        )
        solver_info = {
            "status": status.value,
            "gap": None,
            "iterations": result.solver_iterations,
            "objective_value": result.objective_value,
            "solver": solver_name,
            "support_penalty_at_solution": support_penalty,
        }
        return _serialize_result(result), solver_info


__all__ = [
    "QuadraticProgramEstimator",
    "RobustOptimizationEstimator",
    "SetBasedRobustLinearEstimator",
]
