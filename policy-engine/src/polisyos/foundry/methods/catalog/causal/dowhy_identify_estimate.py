"""Public causal dowhy identify estimate module API."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

from polisyos.common.logger import get_logger
from polisyos.core.observability import DeterminismTier
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
            "Failed to extract standard error from estimate: %s",
            exc,
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
            "Failed to extract confidence intervals from estimate: %s",
            exc,
        )
        return None
    if interval is None:
        return None

    if hasattr(interval, "to_numpy"):
        raw = np.asarray(interval.to_numpy(), dtype=float)
    else:
        raw = np.asarray(interval, dtype=float)
    if raw.shape not in {(2,), (1, 2)}:
        return None
    lower, upper = (float(x) for x in raw.reshape(2))
    if not np.isfinite(lower) or not np.isfinite(upper):
        return None
    if lower > upper:
        return None
    return lower, upper


def _extract_identified_estimand_type(identified: Any) -> str | None:
    """Read the backend's declared estimand type when its DTO exposes one."""
    value = getattr(identified, "estimand_type", None)
    if value is None:
        return None
    return str(getattr(value, "value", value))


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

# These are the estimand profiles exposed by DoWhy 0.13's AutoIdentifier.
# Keep this adapter-side allowlist explicit so an unknown request cannot be
# relabelled as the backend's default ATE.
_SUPPORTED_ESTIMAND_TYPES = frozenset(
    {
        "nonparametric-ate",
        "nonparametric-cde",
        "nonparametric-nde",
        "nonparametric-nie",
    }
)


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
            ParameterSpec(name="execution_profile", default="dowhy-014"),
            ParameterSpec(name="control_value", default=0),
            ParameterSpec(name="treatment_value", default=1),
            ParameterSpec(name="target_units", default="ate"),
            ParameterSpec(name="confidence_level", default=0.95),
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
        "Sharma, A., Kiciman, E. (2020). DoWhy: An End-to-End Library for Causal Inference.",
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


def _run_legacy_dowhy(
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

    if estimand_type not in _SUPPORTED_ESTIMAND_TYPES:
        reason = f"unsupported_estimand_type: {estimand_type}"
        report = build_failure_report(
            method=causal_method,
            status=EstimationStatus.INPUT_INVALID,
            reason=reason,
            estimand=estimand_type,
            sample_size=sample_size,
            n_treated=n_treated,
            n_control=n_control,
            pre_periods=0,
            post_periods=0,
            assumptions=dict(assumptions),
            confidence_level=None,
            method_params=method_params,
            estimand_type=estimand_type,
            graph_ref=data.graph_ref,
            metadata={
                "capability": "unsupported_estimand_type",
                "requested_estimand_type": estimand_type,
                "supported_estimand_types": sorted(_SUPPORTED_ESTIMAND_TYPES),
            },
        )
        return wrap_causal_output(report, warnings=[reason])

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
            estimand_type=estimand_type,
        )
        identified = model.identify_effect(
            estimand_type=estimand_type,
            proceed_when_unidentifiable=False,
        )

        identified_type = _extract_identified_estimand_type(identified)
        if identified_type is not None and identified_type != estimand_type:
            reason = (
                "DoWhy returned a different estimand type: "
                f"requested={estimand_type!r}, identified={identified_type!r}"
            )
            report = build_failure_report(
                method=causal_method,
                status=EstimationStatus.ASSUMPTION_FAILED,
                reason=reason,
                estimand=estimand_type,
                sample_size=sample_size,
                n_treated=n_treated,
                n_control=n_control,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(assumptions),
                confidence_level=None,
                method_params=method_params,
                identified_estimand=str(identified),
                estimand_type=estimand_type,
                graph_ref=data.graph_ref,
                metadata={
                    "capability": "estimand_binding_mismatch",
                    "requested_estimand_type": estimand_type,
                    "identified_estimand_type": identified_type,
                },
            )
            return wrap_causal_output(report, warnings=[reason])
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
        estimate = model.estimate_effect(
            identified,
            method_name=method_name,
            confidence_intervals=True,
        )
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

    standard_error = _extract_standard_error(estimate)
    ci = _extract_confidence_interval(estimate)
    if ci is None:
        reason = (
            "DoWhy estimate did not provide a supported confidence interval; "
            "point estimate retained as point-only"
        )
        report = build_failure_report(
            method=causal_method,
            status=EstimationStatus.NUMERICAL_FAILURE,
            reason=reason,
            estimand=estimand_type,
            sample_size=sample_size,
            n_treated=n_treated,
            n_control=n_control,
            pre_periods=0,
            post_periods=0,
            assumptions=dict(assumptions),
            confidence_level=None,
            point_estimate=point_estimate,
            standard_error=standard_error,
            method_params=method_params,
            identified_estimand=str(identified),
            estimand_type=estimand_type,
            graph_ref=data.graph_ref,
            metadata={
                "treatment": data.treatment,
                "outcome": data.outcome,
                "graph_supplied": graph_text is not None,
                "graph_field": graph_field,
                "inference_status": "point_only",
                "confidence_interval_available": False,
            },
        )
        return wrap_causal_output(report, warnings=[reason])

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
        standard_error=standard_error,
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


def _run_dowhy(
    *,
    data: GraphCausalData | GraphCausalDataV1,
    params: Mapping[str, Any],
    graph_text: str | None,
    graph_field: str,
    assumptions: Mapping[str, str],
) -> dict[str, Any]:
    """Route the selected production profile through the source-bound worker."""
    from ._dowhy_worker import WorkerBindingError, WorkerUnavailableError, run_worker

    profile = params.get("execution_profile", "dowhy-014")
    if profile == "legacy-inprocess":
        return _run_legacy_dowhy(
            data=data,
            params=params,
            graph_text=graph_text,
            graph_field=graph_field,
            assumptions=assumptions,
        )
    requested = {
        "estimand_type": params.get("estimand_type", "nonparametric-ate"),
        "method_name": params.get("method_name", "backdoor.linear_regression"),
        "control_value": params.get("control_value", 0),
        "treatment_value": params.get("treatment_value", 1),
        "target_units": params.get("target_units", "ate"),
        "confidence_level": params.get("confidence_level", 0.95),
    }
    treatment = data.data[:, data.column_names.index(data.treatment)]
    common = {
        "method": _METHOD_MAP.get(str(requested["method_name"]), CausalMethod.DOWHY_BACKDOOR),
        "estimand": str(requested["estimand_type"]),
        "sample_size": data.sample_size,
        "n_treated": int(np.sum(treatment == 1)),
        "n_control": int(np.sum(treatment == 0)),
        "pre_periods": 0,
        "post_periods": 0,
        "assumptions": dict(assumptions),
        "method_params": _sanitize_method_params(params),
        "estimand_type": str(requested["estimand_type"]),
        "graph_ref": data.graph_ref,
    }
    supported = {
        "estimand_type": "nonparametric-ate",
        "method_name": "backdoor.linear_regression",
        "control_value": 0,
        "treatment_value": 1,
        "target_units": "ate",
        "confidence_level": 0.95,
    }
    if profile != "dowhy-014" or requested != supported or not isinstance(data, GraphCausalData):
        reason = "unsupported selected DoWhy profile/estimand/estimator/contrast/target/level"
        report = build_failure_report(
            **common,
            status=EstimationStatus.INPUT_INVALID,
            reason=reason,
            confidence_level=None,
            metadata={
                "capability": "unsupported_worker_profile",
                "execution_profile": profile,
                "requested": requested,
            },
        )
        return wrap_causal_output(report, warnings=[reason])
    try:
        response = run_worker(
            operation="linear_ate",
            state=data,
            payload={
                **requested,
                "treatment": data.treatment,
                "outcome": data.outcome,
                "adjustment_set": data.covariates,
            },
            seed=int(params.get("__seed__", 0)),
        )
    except (WorkerUnavailableError, WorkerBindingError) as exc:
        reason = str(exc)
        status = (
            EstimationStatus.INPUT_INVALID
            if isinstance(exc, WorkerBindingError)
            else EstimationStatus.NUMERICAL_FAILURE
        )
        report = build_failure_report(
            **common,
            status=status,
            reason=reason,
            confidence_level=None,
            metadata={
                "capability": "worker_binding_refused"
                if isinstance(exc, WorkerBindingError)
                else "backend_unavailable",
                "execution_profile": profile,
            },
        )
        return wrap_causal_output(report, warnings=[reason])
    result = response["result"]
    metadata = {
        "execution_profile": profile,
        "worker": response,
        "inference_status": result["inference_status"],
        "authority": "candidate_computation_only",
        "scientific_scope": "declared graph; IID full-rank constant-effect Gaussian linear profile",
    }
    details = {
        **common,
        "point_estimate": result["point"],
        "standard_error": result["standard_error"],
        "identified_estimand": result["identified_estimand"],
        "metadata": metadata,
    }
    if result["interval"] is None:
        reason = "DoWhy point estimate retained without an available confidence interval"
        report = build_failure_report(
            **details,
            status=EstimationStatus.NUMERICAL_FAILURE,
            reason=reason,
            confidence_level=None,
        )
        return wrap_causal_output(report, warnings=[reason])
    report = build_success_report(
        **details,
        confidence_interval=tuple(result["interval"]),
        inference_method=result["method_name"],
        confidence_level=0.95,
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
            state if isinstance(state, GraphCausalData) else GraphCausalData.model_validate(state)
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
