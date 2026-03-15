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
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)

from .protocols import SurvivalData, SurvivalResult


def _survival_payload(state: Any) -> dict[str, Any]:
    if isinstance(state, SurvivalData):
        return state.model_dump(mode="python")
    if isinstance(state, Mapping):
        nested = state.get("survival_data")
        if isinstance(nested, SurvivalData):
            return nested.model_dump(mode="python")
        if isinstance(nested, Mapping):
            payload = dict(nested)
            payload.update({k: v for k, v in state.items() if k not in {"survival_data"}})
            return payload
        return dict(state)
    raise TypeError("state must be SurvivalData or mapping")


@foundry_method(
    namespace="ml.survival",
    version="1.0.0",
    tags={"ml", "survival", "cox"},
)
class SurvivalAnalysisEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("lifelines", "pandas", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="survival_analysis",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "features",
                    SlotType.MATRIX,
                    Unit("feature", "value"),
                    shape=("n_obs", "n_features"),
                ),
                SlotSpec("durations", SlotType.VECTOR, Unit("duration", "time"), shape=("n_obs",)),
                SlotSpec("events", SlotType.VECTOR, Unit("event", "flag"), shape=("n_obs",)),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("survival", "json"),
                    contract_id=SurvivalResult.contract_id,
                )
            }
        ),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Cox proportional hazards survival analysis for time-to-event outcomes.",
        tags=frozenset({"ml", "survival", "cox"}),
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> SurvivalData:
        payload = _survival_payload(fallback_state)
        payload.update(bound_inputs)
        return SurvivalData.model_validate(payload)

    @staticmethod
    def pure_step(state: SurvivalData, params: Mapping[str, Any]) -> dict[str, Any]:
        import pandas as pd
        from lifelines import CoxPHFitter

        del params
        data = state if isinstance(state, SurvivalData) else SurvivalData.model_validate(state)
        feature_names = list(data.feature_names or [f"x{i}" for i in range(data.features.shape[1])])
        frame = pd.DataFrame(np.asarray(data.features, dtype=float), columns=feature_names)
        frame["duration"] = np.asarray(data.durations, dtype=float)
        frame["event"] = np.asarray(data.events, dtype=int)
        fitter = CoxPHFitter()
        fitter.fit(frame, duration_col="duration", event_col="event")
        risk_scores = np.asarray(fitter.predict_partial_hazard(frame)).reshape(-1)
        coefficients = {
            str(name): float(value) for name, value in fitter.params_.to_dict().items()
        }
        return {
            "result": SurvivalResult(
                method_name="survival_analysis",
                risk_scores=risk_scores,
                concordance_index=float(getattr(fitter, "concordance_index_", np.nan)),
                coefficients=coefficients,
                metadata={"library": "lifelines", "estimator": "CoxPHFitter"},
            )
        }


__all__ = ["SurvivalAnalysisEstimator"]
