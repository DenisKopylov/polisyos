"""Public policy mcda module API."""
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


# ---------------------------------------------------------------------------
# TOPSIS
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="policy.mcda",
    version="1.0.0",
    tags={"policy", "mcda", "topsis", "multi-criteria", "structural"},
)
class TOPSISEstimator:
    """Rank policy options by distance to ideal and anti-ideal outcomes."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="topsis",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "decision_matrix", SlotType.MATRIX, Unit("score", "value"),
                    shape=("n_alternatives", "n_criteria"),
                ),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "value"), shape=("n_criteria",)),
                SlotSpec("is_benefit", SlotType.VECTOR, Unit("flag", "bool"), shape=("n_criteria",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="TOPSIS multi-criteria decision analysis: ranking by similarity to ideal solution.",
        tags=frozenset({"policy", "mcda", "topsis", "multi-criteria", "structural"}),
        citations=(
            "Hwang, C.L. & Yoon, K. (1981). Multiple Attribute Decision Making.",
        ),
        equations={
            "closeness": "C_i = D_i^- / (D_i^+ + D_i^-)",
        },
        assumptions={
            "cardinal": "Criteria values are on ratio or interval scale",
            "independence": "Criteria are preferentially independent",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Multi-criteria decision analysis; comparing policy alternatives on multiple dimensions",
        output_interpretation="Ranking of alternatives. TOPSIS: higher closeness-to-ideal = better. AHP: higher priority weight = better.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        dm = np.asarray(state["decision_matrix"], dtype=float)
        weights = np.asarray(state["weights"], dtype=float)
        is_benefit = np.asarray(state["is_benefit"], dtype=bool)

        if dm.ndim != 2:
            raise ValueError("decision_matrix must be 2D")
        n_alt, n_crit = dm.shape
        if weights.shape != (n_crit,) or is_benefit.shape != (n_crit,):
            raise ValueError("weights and is_benefit must match number of criteria")

        # Normalize
        norms = np.sqrt(np.sum(dm ** 2, axis=0))
        norms = np.where(norms > 0, norms, 1.0)
        normalized = dm / norms

        # Weighted normalized
        weighted = normalized * weights

        # Ideal and anti-ideal
        ideal = np.where(is_benefit, np.max(weighted, axis=0), np.min(weighted, axis=0))
        anti_ideal = np.where(is_benefit, np.min(weighted, axis=0), np.max(weighted, axis=0))

        # Distances
        d_plus = np.sqrt(np.sum((weighted - ideal) ** 2, axis=1))
        d_minus = np.sqrt(np.sum((weighted - anti_ideal) ** 2, axis=1))

        # Closeness coefficient
        denom = d_plus + d_minus
        closeness = np.where(denom > 0, d_minus / denom, 0.0)

        ranking = np.argsort(-closeness)

        return {
            "result": {
                "closeness_coefficients": closeness.tolist(),
                "ranking": ranking.tolist(),
                "best_alternative": int(ranking[0]),
                "d_plus": d_plus.tolist(),
                "d_minus": d_minus.tolist(),
            }
        }


# ---------------------------------------------------------------------------
# AHP
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="policy.mcda",
    version="1.0.0",
    tags={"policy", "mcda", "ahp", "multi-criteria", "structural"},
)
class AHPEstimator:
    """Rank policy options with analytic hierarchy process judgments."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ahp",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "pairwise_matrix", SlotType.MATRIX, Unit("comparison", "ratio"),
                    shape=("n_criteria", "n_criteria"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="cr_threshold", default=0.1, bounds=(0.0, 1.0)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Analytic Hierarchy Process: derive priority weights from pairwise comparisons.",
        tags=frozenset({"policy", "mcda", "ahp", "multi-criteria", "structural"}),
        citations=(
            "Saaty, T.L. (1980). The Analytic Hierarchy Process.",
        ),
        equations={
            "priority": "w = principal_eigenvector(A) / sum(principal_eigenvector(A))",
            "cr": "CR = CI / RI, CI = (lambda_max - n) / (n - 1)",
        },
        assumptions={
            "reciprocal": "Pairwise comparison matrix must be positive reciprocal: a_ij = 1/a_ji",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Multi-criteria decision analysis; comparing policy alternatives on multiple dimensions",
        output_interpretation="Ranking of alternatives. TOPSIS: higher closeness-to-ideal = better. AHP: higher priority weight = better.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        matrix = np.asarray(state["pairwise_matrix"], dtype=float)
        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
            raise ValueError("pairwise_matrix must be square")
        n = matrix.shape[0]
        if n < 2:
            raise ValueError("need at least 2 criteria")

        cr_threshold = float(params.get("cr_threshold", 0.1))

        # Priority vector via geometric mean (row-wise)
        geo_means = np.prod(matrix, axis=1) ** (1.0 / n)
        weights = geo_means / np.sum(geo_means)

        # Consistency check
        weighted_sum = matrix @ weights
        lambdas = weighted_sum / np.maximum(weights, 1e-12)
        lambda_max = float(np.mean(lambdas))
        ci = (lambda_max - n) / max(n - 1, 1)

        # Random Index (Saaty)
        ri_table = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24,
                    7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}
        ri = ri_table.get(n, 1.49)
        cr = ci / ri if ri > 0 else 0.0

        return {
            "result": {
                "priority_weights": weights.tolist(),
                "lambda_max": lambda_max,
                "consistency_index": float(ci),
                "consistency_ratio": float(cr),
                "is_consistent": bool(cr <= cr_threshold),
                "cr_threshold": cr_threshold,
            }
        }


# ---------------------------------------------------------------------------
# ELECTRE I
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="policy.mcda",
    version="1.0.0",
    tags={"policy", "mcda", "electre", "multi-criteria", "structural"},
)
class ELECTREEstimator:
    """Rank policy options with ELECTRE-style outranking comparisons."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="electre",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "decision_matrix", SlotType.MATRIX, Unit("score", "value"),
                    shape=("n_alternatives", "n_criteria"),
                ),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "value"), shape=("n_criteria",)),
                SlotSpec("is_benefit", SlotType.VECTOR, Unit("flag", "bool"), shape=("n_criteria",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="concordance_threshold", default=0.65, bounds=(0.0, 1.0)),
            ParameterSpec(name="discordance_threshold", default=0.35, bounds=(0.0, 1.0)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="ELECTRE I outranking method for multi-criteria decision analysis.",
        tags=frozenset({"policy", "mcda", "electre", "outranking", "multi-criteria", "structural"}),
        citations=(
            "Roy, B. (1968). Classement et choix en presence de points de vue multiples.",
        ),
        equations={
            "concordance": "c(a,b) = sum w_j for j where a_j >= b_j",
            "discordance": "d(a,b) = max (b_j - a_j) / range_j for j where b_j > a_j",
        },
        assumptions={"ordinal_or_cardinal": "Criteria on at least ordinal scale"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Multi-criteria decision analysis; comparing policy alternatives on multiple dimensions",
        output_interpretation="Ranking of alternatives. TOPSIS: higher closeness-to-ideal = better. AHP: higher priority weight = better.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        dm = np.asarray(state["decision_matrix"], dtype=float)
        weights = np.asarray(state["weights"], dtype=float)
        is_benefit = np.asarray(state["is_benefit"], dtype=bool)

        if dm.ndim != 2:
            raise ValueError("decision_matrix must be 2D")
        n_alt, n_crit = dm.shape

        c_thresh = float(params.get("concordance_threshold", 0.65))
        d_thresh = float(params.get("discordance_threshold", 0.35))

        # Normalize weights
        w = weights / np.sum(weights)

        # Normalize decision matrix
        ranges = np.ptp(dm, axis=0)
        ranges = np.where(ranges > 0, ranges, 1.0)

        # Concordance and discordance matrices
        concordance = np.zeros((n_alt, n_alt))
        discordance = np.zeros((n_alt, n_alt))

        for i in range(n_alt):
            for j in range(n_alt):
                if i == j:
                    continue
                # Concordance: sum of weights where i is at least as good as j
                if is_benefit.any():
                    better_or_eq = np.where(is_benefit, dm[i] >= dm[j], dm[i] <= dm[j])
                else:
                    better_or_eq = dm[i] <= dm[j]
                concordance[i, j] = float(np.sum(w[better_or_eq]))

                # Discordance: max normalized disadvantage
                if is_benefit.any():
                    disadvantage = np.where(is_benefit, dm[j] - dm[i], dm[i] - dm[j])
                else:
                    disadvantage = dm[i] - dm[j]
                disadvantage = np.maximum(disadvantage, 0.0) / ranges
                discordance[i, j] = float(np.max(disadvantage))

        # Outranking relation
        outranks = (concordance >= c_thresh) & (discordance <= d_thresh)
        np.fill_diagonal(outranks, False)

        # Net flow scores
        net_concordance = np.sum(concordance, axis=1) - np.sum(concordance, axis=0)
        net_discordance = np.sum(discordance, axis=1) - np.sum(discordance, axis=0)

        # Kernel: alternatives not outranked by any kernel member
        dominated = np.any(outranks, axis=0)
        kernel = [int(i) for i in range(n_alt) if not dominated[i]]

        return {
            "result": {
                "concordance_matrix": concordance.tolist(),
                "discordance_matrix": discordance.tolist(),
                "outranking_matrix": outranks.tolist(),
                "kernel": kernel,
                "net_concordance": net_concordance.tolist(),
                "net_discordance": net_discordance.tolist(),
            }
        }


__all__ = [
    "AHPEstimator",
    "ELECTREEstimator",
    "TOPSISEstimator",
]
