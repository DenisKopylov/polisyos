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
from polisyos.foundry.methods.catalog._payloads import extract_model_payload

from .protocols import PanelObservationalData


def _panel_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=PanelObservationalData,
        nested_keys=("panel_data", "panel_observational_data"),
    )


@foundry_method(
    namespace="causal.diagnostics",
    version="1.0.0",
    tags={"causal", "diagnostics", "parallel-trends"},
)
class ParallelTrendsCheck:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="parallel_trends_check",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "outcome",
                    SlotType.MATRIX,
                    Unit("outcome", "value"),
                    shape=("n_units", "n_periods"),
                ),
                SlotSpec(
                    "treatment",
                    SlotType.VECTOR,
                    Unit("binary", "flag"),
                    shape=("n_units",),
                ),
                SlotSpec("time_treatment", SlotType.SCALAR, Unit("time", "index")),
            }
        ),
        output_slots=frozenset({SlotSpec("result", SlotType.SCALAR, Unit("diagnostic", "json"))}),
        parameters=(ParameterSpec(name="alpha", default=0.05),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Pre-treatment slope check for the DiD parallel trends assumption.",
        tags=frozenset({"causal", "diagnostics", "parallel-trends"}),
    )

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> PanelObservationalData:
        payload = _panel_payload(fallback_state)
        payload.update(bound_inputs)
        return PanelObservationalData.model_validate(payload)

    @staticmethod
    def pure_step(state: PanelObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        import statsmodels.api as sm

        data = (
            state
            if isinstance(state, PanelObservationalData)
            else PanelObservationalData.model_validate(state)
        )
        if data.time_treatment < 2:
            raise ValueError("parallel_trends_check requires at least 2 pre-treatment periods")

        treated_mask = np.asarray(data.treatment, dtype=int) == 1
        control_mask = ~treated_mask
        if not treated_mask.any() or not control_mask.any():
            raise ValueError("parallel_trends_check requires treated and control units")

        pre_outcome = np.asarray(data.outcome[:, : data.time_treatment], dtype=float)
        treated_mean = np.mean(pre_outcome[treated_mask], axis=0)
        control_mean = np.mean(pre_outcome[control_mask], axis=0)
        diff = treated_mean - control_mean
        trend = np.arange(diff.shape[0], dtype=float)

        x = sm.add_constant(trend, has_constant="add")
        fit = sm.OLS(diff, x).fit()
        slope = float(fit.params[1])
        p_value = float(fit.pvalues[1])
        alpha = float(params.get("alpha", 0.05))

        return {
            "result": {
                "test_name": "parallel_trends_check",
                "statistic": float(fit.tvalues[1]),
                "p_value": p_value,
                "passed": bool(p_value >= alpha),
                "critical_value": alpha,
                "metadata": {
                    "pre_periods": int(diff.shape[0]),
                    "slope": slope,
                    "intercept": float(fit.params[0]),
                    "treated_mean_pre": treated_mean.tolist(),
                    "control_mean_pre": control_mean.tolist(),
                    "difference_series": diff.tolist(),
                    "r_squared": float(getattr(fit, "rsquared", 0.0)),
                },
            }
        }


__all__ = ["ParallelTrendsCheck"]
