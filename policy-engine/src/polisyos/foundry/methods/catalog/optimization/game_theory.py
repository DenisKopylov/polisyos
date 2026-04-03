"""Public optimization game theory module API."""
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
    namespace="optimization.game_theory",
    version="1.0.0",
    tags={"optimization", "game-theory", "nash-equilibrium"},
)
class NashEquilibriumEstimator:
    """Nash equilibrium estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="nash_equilibrium",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("payoff_A", SlotType.MATRIX, Unit("payoff", "value"), shape=("n_strategies_A", "n_strategies_B")),
                SlotSpec("payoff_B", SlotType.MATRIX, Unit("payoff", "value"), shape=("n_strategies_A", "n_strategies_B")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="max_iter", default=1000),
            ParameterSpec(name="learning_rate", default=0.01, bounds=(0.001, 1.0)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Nash equilibrium finder for two-player normal-form games via support enumeration and gradient.",
        tags=frozenset({"optimization", "game-theory", "nash-equilibrium", "two-player"}),
        citations=("Nash, J. (1950). Equilibrium Points in N-Person Games. PNAS.",),
        equations={"nash": "sigma_A = argmax E[u_A(a, sigma_B)]; sigma_B = argmax E[u_B(sigma_A, b)]"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Strategic interaction between agents; mechanism design; market competition analysis",
        when_not_to_use="Cooperative game; single-agent optimization",
        output_interpretation="Nash equilibrium strategies + payoffs. Multiple NE possible — check for coordination games.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        A = np.asarray(state["payoff_A"], dtype=float)
        B = np.asarray(state["payoff_B"], dtype=float)
        m, n_s = A.shape
        max_iter = int(params.get("max_iter", 1000))
        lr = float(params.get("learning_rate", 0.01))

        # Check for pure strategy Nash equilibria
        pure_nash = []
        for i in range(m):
            for j in range(n_s):
                if A[i, j] == np.max(A[:, j]) and B[i, j] == np.max(B[i, :]):
                    pure_nash.append({"player_A_strategy": i, "player_B_strategy": j,
                                      "payoff_A": float(A[i, j]), "payoff_B": float(B[i, j])})

        # Mixed strategy via multiplicative weights update
        p = np.ones(m) / m
        q = np.ones(n_s) / n_s

        for _ in range(max_iter):
            # Expected payoffs
            eu_A = A @ q  # (m,)
            eu_B = B.T @ p  # (n,)

            # Multiplicative weights
            p_new = p * np.exp(lr * eu_A)
            p_new /= np.sum(p_new)
            q_new = q * np.exp(lr * eu_B)
            q_new /= np.sum(q_new)

            if np.max(np.abs(p_new - p)) + np.max(np.abs(q_new - q)) < 1e-10:
                p, q = p_new, q_new
                break
            p, q = p_new, q_new

        expected_payoff_A = float(p @ A @ q)
        expected_payoff_B = float(p @ B @ q)

        return {
            "result": {
                "mixed_strategy_A": p.tolist(),
                "mixed_strategy_B": q.tolist(),
                "expected_payoff_A": expected_payoff_A,
                "expected_payoff_B": expected_payoff_B,
                "pure_nash_equilibria": pure_nash,
                "n_pure_nash": len(pure_nash),
                "n_strategies_A": m,
                "n_strategies_B": n_s,
            }
        }


__all__ = [
    "NashEquilibriumEstimator",
]
