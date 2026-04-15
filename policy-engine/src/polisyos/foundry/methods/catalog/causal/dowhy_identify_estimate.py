"""Public causal dowhy identify estimate module API."""
from __future__ import annotations

import json
from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.common.logger import get_logger
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
from polisyos.foundry.methods.catalog.causal._common import (
    build_failure_report,
    build_success_report,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal.protocols import GraphCausalData, GraphCausalDataV1
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus

logger = get_logger(__name__)


def _load_dowhy_dependencies() -> tuple[Any, Any]:
    import dowhy
    import pandas as pd


    return dowhy, pd


def _to_float_scalar(value: Any) -> float:
    array = np.asarray(value, dtype=float)
    if array.size != 1:
        raise ValueError(f"expected scalar value, got shape={array.shape}")
    scalar = float(array.reshape(-1)[0])
    if not np.isfinite(scalar):
        raise ValueError("scalar value is non-finite")
    return scalar


def _extract_standard_error(estimate: Any) -> float | None:
    if not hasattr(estimate, "get_standard_error"):
        return None
    try:
        value = estimate.get_standard_error()
        if value is None:
            return None
        scalar = _to_float_scalar(value)
    except (TypeError, ValueError) as exc:
        logger.debug(
            "Failed to extract standard error from estimate: %s", exc,
        )
        return None
    if scalar < 0:
        return None
    return scalar


def _extract_confidence_interval(estimate: Any) -> tuple[float, float] | None:
    if not hasattr(estimate, "get_confidence_intervals"):
        return None
    try:
        interval = estimate.get_confidence_intervals()
    except (TypeError, ValueError) as exc:
        logger.debug(
            "Failed to extract confidence intervals from estimate: %s", exc,
        )
        return None
    if interval is None:
        return None

    if hasattr(interval, "to_numpy"):
        raw = np.asarray(interval.to_numpy(), dtype=float)
    else:
        raw = np.asarray(interval, dtype=float)
    flat = raw.reshape(-1)
    if flat.size < 2:
        return None
    lower = float(flat[0])
    upper = float(flat[1])
    if not np.isfinite(lower) or not np.isfinite(upper):
        return None
    if lower > upper:
        lower, upper = upper, lower
    return lower, upper


def _json_serializable(value: Any) -> bool:
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return False
    return True


def _sanitize_method_params(params: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in params.items():
        if key in {"__rng__", "__seed__"}:
            continue
        if _json_serializable(value):
            result[str(key)] = value
    return result


_METHOD_MAP: dict[str, CausalMethod] = {
    "backdoor.linear_regression": CausalMethod.DOWHY_BACKDOOR,
    "backdoor.propensity_score_matching": CausalMethod.DOWHY_BACKDOOR,
    "backdoor.propensity_score_weighting": CausalMethod.DOWHY_BACKDOOR,
    "backdoor.econml.dml": CausalMethod.DOWHY_BACKDOOR,
    "iv.instrumental_variable": CausalMethod.DOWHY_IV,
    "frontdoor.two_stage_regression": CausalMethod.DOWHY_FRONTDOOR,
}


def _base_signature() -> MethodSignature:
    return MethodSignature(
        name="dowhy_identify_estimate",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="graph_causal_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("observations", "rows"),
                    shape=("n_obs", "n_features"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="causal_effect_report",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="estimand_type", default="nonparametric-ate"),
            ParameterSpec(name="method_name", default="backdoor.linear_regression"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )


_BASE_METADATA = MethodMetadata(
    description="DoWhy causal identification and estimation in a single pure step.",
    tags=frozenset({"causal", "dowhy", "identify", "estimate"}),
    citations=(
        "Sharma, A., Kiciman, E. (2020). DoWhy: An End-to-End Library "
        "for Causal Inference.",
    ),
    assumptions={
        "graph_correctness": "Causal graph is correctly specified.",
        "identifiability": "Target estimand is identifiable under graph assumptions.",
    },
    when_to_use="Systematic identification and estimation of causal effect given causal DAG; use DoWhy framework",
    when_not_to_use="No causal graph available; outcome is not identified from observed data",
    typical_min_obs=100,
    output_interpretation="Identified estimand (expression of ATE in terms of observables) + numeric estimate with confidence interval.",
)


def _run_dowhy(
    *,
    data: GraphCausalData | GraphCausalDataV1,
    params: Mapping[str, Any],
    graph_text: str | None,
    graph_field: str,
    assumptions: Mapping[str, str],
) -> dict[str, Any]:
    method_name = str(params.get("method_name", "backdoor.linear_regression"))
    estimand_type = str(params.get("estimand_type", "nonparametric-ate"))
    causal_method = _METHOD_MAP.get(method_name, CausalMethod.DOWHY_BACKDOOR)
    method_params = _sanitize_method_params(params)
    sample_size = data.sample_size
    treatment_idx = data.column_names.index(data.treatment)
    treatment_values = np.asarray(data.data[:, treatment_idx], dtype=float)
    n_treated = int(np.sum(treatment_values != 0))
    n_control = int(sample_size - n_treated)

    try:
        dowhy, pd = _load_dowhy_dependencies()
    except ModuleNotFoundError as exc:
        report = build_failure_report(
            method=causal_method,
            status=EstimationStatus.NUMERICAL_FAILURE,
            reason=f"DoWhy backend unavailable: {exc}",
            estimand=estimand_type,
            sample_size=sample_size,
            n_treated=n_treated,
            n_control=n_control,
            pre_periods=0,
            post_periods=0,
            assumptions=dict(assumptions),
            method_params=method_params,
            estimand_type=estimand_type,
            graph_ref=data.graph_ref,
        )
        return wrap_causal_output(
            report,
            warnings=[report.status_reason or "backend unavailable"],
        )

    df = pd.DataFrame(data.data, columns=data.column_names)
    try:
        model = dowhy.CausalModel(
            data=df,
            treatment=data.treatment,
            outcome=data.outcome,
            graph=graph_text,
        )
        identified = model.identify_effect(proceed_when_unidentifiable=False)
    except Exception as exc:
        report = build_failure_report(
            method=causal_method,
            status=EstimationStatus.ASSUMPTION_FAILED,
            reason=f"DoWhy identification failed: {exc}",
            estimand=estimand_type,
            sample_size=sample_size,
            n_treated=n_treated,
            n_control=n_control,
            pre_periods=0,
            post_periods=0,
            assumptions=dict(assumptions),
            method_params=method_params,
            estimand_type=estimand_type,
            graph_ref=data.graph_ref,
        )
        return wrap_causal_output(
            report,
            warnings=[report.status_reason or "identification failed"],
        )

    try:
        estimate = model.estimate_effect(identified, method_name=method_name)
        point_estimate = _to_float_scalar(estimate.value)
    except Exception as exc:
        report = build_failure_report(
            method=causal_method,
            status=EstimationStatus.NUMERICAL_FAILURE,
            reason=f"DoWhy estimation failed: {exc}",
            estimand=estimand_type,
            sample_size=sample_size,
            n_treated=n_treated,
            n_control=n_control,
            pre_periods=0,
            post_periods=0,
            assumptions=dict(assumptions),
            method_params=method_params,
            identified_estimand=str(identified),
            estimand_type=estimand_type,
            graph_ref=data.graph_ref,
        )
        return wrap_causal_output(
            report,
            warnings=[report.status_reason or "estimation failed"],
        )

    ci = _extract_confidence_interval(estimate)
    if ci is None:
        epsilon = max(abs(point_estimate) * 1e-9, 1e-9)
        ci = (point_estimate - epsilon, point_estimate + epsilon)

    report = build_success_report(
        method=causal_method,
        estimand=estimand_type,
        point_estimate=point_estimate,
        confidence_interval=ci,
        inference_method=method_name,
        sample_size=sample_size,
        n_treated=n_treated,
        n_control=n_control,
        pre_periods=0,
        post_periods=0,
        assumptions=dict(assumptions),
        standard_error=_extract_standard_error(estimate),
        method_params=method_params,
        identified_estimand=str(identified),
        estimand_type=estimand_type,
        graph_ref=data.graph_ref,
        metadata={
            "treatment": data.treatment,
            "outcome": data.outcome,
            "graph_supplied": graph_text is not None,
            "graph_field": graph_field,
        },
    )
    return wrap_causal_output(report)


@foundry_method(
    namespace="causal.inference",
    version="1.0.0",
    tags={"causal", "dowhy", "identification", "estimation", "legacy"},
)
class DoWhyIdentifyEstimateV1:
    """Legacy DoWhy identify/estimate contract using `graph_gml`."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    signature: ClassVar[MethodSignature] = _base_signature()
    metadata: ClassVar[MethodMetadata] = _BASE_METADATA

    @staticmethod
    def pure_step(state: GraphCausalDataV1, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, GraphCausalDataV1)
            else GraphCausalDataV1.model_validate(state)
        )
        return _run_dowhy(
            data=data,
            params=params,
            graph_text=data.graph_gml,
            graph_field="graph_gml",
            assumptions=DoWhyIdentifyEstimateV1.metadata.assumptions,
        )


@foundry_method(
    namespace="causal.inference",
    version="2.0.0",
    tags={"causal", "dowhy", "identification", "estimation"},
)
class DoWhyIdentifyEstimate:
    """Primary DoWhy identify/estimate contract using `graph_dot`."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    signature: ClassVar[MethodSignature] = _base_signature()
    metadata: ClassVar[MethodMetadata] = _BASE_METADATA

    @staticmethod
    def pure_step(state: GraphCausalData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, GraphCausalData)
            else GraphCausalData.model_validate(state)
        )
        return _run_dowhy(
            data=data,
            params=params,
            graph_text=data.graph_dot,
            graph_field="graph_dot",
            assumptions=DoWhyIdentifyEstimate.metadata.assumptions,
        )


__all__ = [
    "DoWhyIdentifyEstimate",
    "DoWhyIdentifyEstimateV1",
    "_load_dowhy_dependencies",
]
