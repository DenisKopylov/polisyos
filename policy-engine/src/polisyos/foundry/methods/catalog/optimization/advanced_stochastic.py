"""Public optimization advanced stochastic module API."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

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


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


@foundry_method(
    namespace="optimization.bilevel",
    version="1.0.0",
    tags={"optimization", "bilevel"},
)
class BilevelOptimizationEstimator:
    """Solve bilevel policy design problems with nested leader-follower objectives."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="bilevel",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("c_upper", SlotType.VECTOR, Unit("cost", "value"), shape=("n_vars",)),
                SlotSpec("c_lower", SlotType.VECTOR, Unit("cost", "value"), shape=("n_vars",)),
                SlotSpec("A_upper", SlotType.MATRIX, Unit("constraint", "coeff"), shape=("m_upper", "n_vars")),
                SlotSpec("b_upper", SlotType.VECTOR, Unit("constraint", "rhs"), shape=("m_upper",)),
                SlotSpec("A_lower", SlotType.MATRIX, Unit("constraint", "coeff"), shape=("m_lower", "n_vars")),
                SlotSpec("b_lower", SlotType.VECTOR, Unit("constraint", "rhs"), shape=("m_lower",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="max_iter", default=100),
            ParameterSpec(name="step_size", default=0.1, bounds=(0.001, 1.0)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Bilevel optimization via alternating projection for hierarchical policy decisions.",
        tags=frozenset({"optimization", "bilevel", "hierarchical", "stackelberg"}),
        equations={
            "upper": "min c_upper'*x s.t. A_upper*x <= b_upper",
            "lower": "min c_lower'*x s.t. A_lower*x <= b_lower",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Hierarchical optimization where a leader-follower structure exists; principal-agent problems; Stackelberg game policy design",
        when_not_to_use="Single-level optimization; cooperative setting with no strategic hierarchy",
        output_interpretation="Upper-level (leader) solution + lower-level (follower) response. Check both feasibility flags for a valid bilevel solution.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        c_u = np.asarray(state["c_upper"], dtype=float)
        c_l = np.asarray(state["c_lower"], dtype=float)
        A_u = np.asarray(state["A_upper"], dtype=float)
        b_u = np.asarray(state["b_upper"], dtype=float)
        A_l = np.asarray(state["A_lower"], dtype=float)
        b_l = np.asarray(state["b_lower"], dtype=float)
        n = len(c_u)
        max_iter = int(params.get("max_iter", 100))
        step = float(params.get("step_size", 0.1))

        x = np.zeros(n)
        iterations_run = 0
        converged = False
        last_residual = np.full(n, np.inf, dtype=float)

        def project_feasible(x_in: np.ndarray, A: np.ndarray, b: np.ndarray) -> np.ndarray:
            x_out = x_in.copy()
            violations = A @ x_out - b
            for i in range(len(b)):
                if violations[i] > 0:
                    a_i = A[i]
                    norm_sq = float(a_i @ a_i)
                    if norm_sq > 1e-12:
                        x_out -= (violations[i] / norm_sq) * a_i
            return np.maximum(x_out, 0.0)

        for iteration in range(max_iter):
            # Lower level: gradient step on c_lower, project onto lower feasible
            x_lower = project_feasible(x - step * c_l, A_l, b_l)
            # Upper level: gradient step on c_upper, project onto upper feasible
            x_upper = project_feasible(x_lower - step * c_u, A_u, b_u)
            last_residual = x_upper - x
            iterations_run = iteration + 1

            if np.max(np.abs(last_residual)) < 1e-8:
                x = x_upper
                converged = True
                break
            x = x_upper

        upper_constraint_slacks = (b_u - A_u @ x).astype(float)
        lower_constraint_slacks = (b_l - A_l @ x).astype(float)

        return {
            "result": {
                "solution": x.tolist(),
                "upper_objective": float(c_u @ x),
                "lower_objective": float(c_l @ x),
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
            }
        }


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
                SlotSpec("A_mean", SlotType.MATRIX, Unit("constraint", "coeff"), shape=("m_constraints", "n_vars")),
                SlotSpec("b", SlotType.VECTOR, Unit("constraint", "rhs"), shape=("m_constraints",)),
                SlotSpec("A_std", SlotType.MATRIX, Unit("constraint", "std"), shape=("m_constraints", "n_vars")),
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
        citations=("Charnes, A. & Cooper, W.W. (1959). Chance-Constrained Programming. Management Science.",),
        equations={"cc": "min c'x s.t. P(A*x <= b) >= alpha → A_mean*x + Phi^-1(alpha)*||A_std*x|| <= b"},
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
]
