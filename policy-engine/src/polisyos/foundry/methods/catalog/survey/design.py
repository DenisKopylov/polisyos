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
    namespace="survey.design",
    version="1.0.0",
    tags={"survey", "design", "complex-survey"},
)
class ComplexSurveyDesignEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="complex_survey",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("y", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "value"), shape=("n_obs",)),
                SlotSpec("strata", SlotType.VECTOR, Unit("stratum", "id"), shape=("n_obs",)),
                SlotSpec("clusters", SlotType.VECTOR, Unit("cluster", "id"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Complex survey estimator with stratification, clustering, and design effects.",
        tags=frozenset({"survey", "design", "complex-survey", "design-effect", "linearization"}),
        citations=("Kish, L. (1965). Survey Sampling. Wiley.",),
        equations={
            "weighted_mean": "y_bar = sum(w*y) / sum(w)",
            "deff": "DEFF = V_complex / V_srs",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Stratified, clustered, or weighted probability surveys; needs design-consistent standard errors",
        when_not_to_use="Simple random sample where SRS SE applies; administrative data covering full population",
        output_interpretation="Survey-weighted point estimates + SE accounting for design effect. DEFF = complex_SE²/SRS_SE².",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        y = np.asarray(state["y"], dtype=float)
        w = np.asarray(state["weights"], dtype=float)
        strata = np.asarray(state["strata"])
        clusters = np.asarray(state["clusters"])
        n = len(y)

        # Weighted mean
        w_sum = float(np.sum(w))
        y_bar = float(np.sum(w * y) / max(w_sum, 1e-12))

        # Linearization variance (Taylor series)
        unique_strata = np.unique(strata)
        var_total = 0.0
        n_strata = len(unique_strata)

        for h in unique_strata:
            in_h = strata == h
            clusters_h = np.unique(clusters[in_h])
            n_h = len(clusters_h)

            if n_h < 2:
                continue

            # Cluster totals
            z_hi = []
            for c in clusters_h:
                in_hc = in_h & (clusters == c)
                z_hi.append(float(np.sum(w[in_hc] * (y[in_hc] - y_bar))))
            z_hi = np.array(z_hi)
            z_bar = float(np.mean(z_hi))

            var_h = float(n_h / (n_h - 1) * np.sum((z_hi - z_bar) ** 2))
            var_total += var_h

        var_complex = var_total / max(w_sum**2, 1e-12)

        # SRS variance for DEFF
        var_srs = float(np.sum(w * (y - y_bar) ** 2) / max(w_sum**2, 1e-12)) * n / max(n - 1, 1)
        deff = var_complex / max(var_srs, 1e-12)

        se = float(np.sqrt(max(var_complex, 0.0)))

        return {
            "result": {
                "weighted_mean": y_bar,
                "standard_error": se,
                "design_effect": max(deff, 0.0),
                "effective_sample_size": n / max(deff, 1e-6),
                "n_strata": n_strata,
                "n_clusters": len(np.unique(clusters)),
                "n_obs": n,
            }
        }


__all__ = [
    "ComplexSurveyDesignEstimator",
]
