"""Public causal dowhy refute module API."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any, ClassVar

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
from polisyos.foundry.methods.catalog.causal.protocols import GraphCausalData
from polisyos.ir.analytics.causal import (
    CausalMethod,
    DiagnosticTest,
    EstimationStatus,
    RefutationResult,
    RefutationTestType,
)

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


def _to_safe_details(payload: Mapping[str, Any]) -> dict[str, Any]:
    details: dict[str, Any] = {}
    for key, value in payload.items():
        if _json_serializable(value):
            details[str(key)] = value
        else:
            details[str(key)] = str(value)
    return details


def _extract_p_value(refutation: Any) -> float | None:
    raw = getattr(refutation, "p_value", None)
    if isinstance(raw, dict):
        raw = raw.get("p_value")
    if raw is None:
        return None
    try:
        value = _to_float_scalar(raw)
    except (TypeError, ValueError) as exc:
        logger.debug(
            "Failed to parse p-value from refutation result: %s",
            exc,
        )
        return None
    if 0.0 <= value <= 1.0:
        return value
    return None


def _extract_refuted_estimate(refutation: Any, *, fallback: float) -> float:
    for attr in ("new_effect", "new_effect_estimate", "refuted_effect"):
        if hasattr(refutation, attr):
            candidate = getattr(refutation, attr)
            if candidate is None:
                continue
            try:
                return _to_float_scalar(candidate)
            except (TypeError, ValueError) as exc:
                logger.debug(
                    "Failed to convert refuted estimate attr %r: %s",
                    attr,
                    exc,
                )
                continue

    if hasattr(refutation, "new_effect_array"):
        try:
            values = np.asarray(refutation.new_effect_array, dtype=float).reshape(-1)
            values = values[np.isfinite(values)]
            if values.size > 0:
                return float(np.mean(values))
        except Exception as exc:
            logger.debug("Ignored exception: %s", exc)

    raw_result = getattr(refutation, "refutation_result", None)
    if isinstance(raw_result, Mapping):
        for key in ("new_effect", "refuted_effect", "effect"):
            if key not in raw_result:
                continue
            try:
                return _to_float_scalar(raw_result[key])
            except (TypeError, ValueError) as exc:
                logger.debug(
                    "Failed to convert refutation_result[%r]: %s",
                    key,
                    exc,
                )
                continue

    return fallback


def _compute_effect_ratio(*, original: float, refuted: float) -> float:
    if abs(original) <= 1.0e-12:
        if abs(refuted) <= 1.0e-12:
            return 1.0
        return math.copysign(float("inf"), refuted)
    return float(refuted / original)


@foundry_method(
    namespace="causal.refutation",
    version="1.0.0",
    tags={"causal", "refutation", "robustness"},
)
class DoWhyRefute:
    """Run DoWhy refutation tests for graph-based observational estimates."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="dowhy_refute",
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
            ParameterSpec(name="p_value_threshold", default=0.05),
            ParameterSpec(name="effect_ratio_tolerance", default=0.20),
            ParameterSpec(name="data_subset_fraction", default=0.80),
            ParameterSpec(name="bootstrap_num_simulations", default=100),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "DoWhy estimate refutation with placebo, random common cause, "
            "data subset, and bootstrap tests."
        ),
        tags=frozenset({"causal", "dowhy", "refutation", "robustness"}),
        citations=(
            "Sharma, A., Kiciman, E. (2020). DoWhy: An End-to-End Library for Causal Inference.",
        ),
        assumptions={
            "graph_correctness": "Causal graph is correctly specified.",
            "identifiability": "Target estimand is identifiable under graph assumptions.",
            "robustness_rule": "Refutation passes when effect ratio remains near 1.0.",
        },
        when_to_use="Validate causal estimate robustness via placebo treatment, random common cause, data subset refuters",
        when_not_to_use="No prior causal estimate to validate; purely exploratory analysis",
        output_interpretation="Refutation test statistics. Estimate should be stable under placebo/random cause. Large deviation = suspect.",
    )

    _METHOD_MAP: ClassVar[dict[str, CausalMethod]] = {
        "backdoor.linear_regression": CausalMethod.DOWHY_BACKDOOR,
        "backdoor.propensity_score_matching": CausalMethod.DOWHY_BACKDOOR,
        "backdoor.propensity_score_weighting": CausalMethod.DOWHY_BACKDOOR,
        "backdoor.econml.dml": CausalMethod.DOWHY_BACKDOOR,
        "iv.instrumental_variable": CausalMethod.DOWHY_IV,
        "frontdoor.two_stage_regression": CausalMethod.DOWHY_FRONTDOOR,
    }

    _REFUTER_METHODS: ClassVar[tuple[tuple[RefutationTestType, str], ...]] = (
        (RefutationTestType.PLACEBO_TREATMENT, "placebo_treatment_refuter"),
        (RefutationTestType.RANDOM_COMMON_CAUSE, "random_common_cause"),
        (RefutationTestType.DATA_SUBSET, "data_subset_refuter"),
        (RefutationTestType.BOOTSTRAP, "bootstrap_refuter"),
    )

    @staticmethod
    def pure_step(state: GraphCausalData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state if isinstance(state, GraphCausalData) else GraphCausalData.model_validate(state)
        )
        method_name = str(params.get("method_name", "backdoor.linear_regression"))
        estimand_type = str(params.get("estimand_type", "nonparametric-ate"))
        p_value_threshold = float(params.get("p_value_threshold", 0.05))
        effect_ratio_tolerance = float(params.get("effect_ratio_tolerance", 0.20))
        subset_fraction = float(params.get("data_subset_fraction", 0.80))
        bootstrap_num_simulations = int(params.get("bootstrap_num_simulations", 100))
        seed = int(params.get("__seed__", 0) or 0)
        np.random.seed(seed)

        causal_method = DoWhyRefute._METHOD_MAP.get(method_name, CausalMethod.DOWHY_BACKDOOR)
        method_params = _sanitize_method_params(params)
        assumptions = dict(DoWhyRefute.metadata.assumptions)
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
                assumptions=assumptions,
                method_params=method_params,
                estimand_type=estimand_type,
                graph_ref=data.graph_ref,
            )
            return wrap_causal_output(
                report, warnings=[report.status_reason or "backend unavailable"]
            )

        df = pd.DataFrame(data.data, columns=data.column_names)
        try:
            model = dowhy.CausalModel(
                data=df,
                treatment=data.treatment,
                outcome=data.outcome,
                graph=data.graph_dot,
            )
            identified = model.identify_effect(proceed_when_unidentifiable=False)
            estimate = model.estimate_effect(identified, method_name=method_name)
            original_estimate = _to_float_scalar(estimate.value)
        except Exception as exc:
            report = build_failure_report(
                method=causal_method,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=f"DoWhy estimate bootstrap for refutation failed: {exc}",
                estimand=estimand_type,
                sample_size=sample_size,
                n_treated=n_treated,
                n_control=n_control,
                pre_periods=0,
                post_periods=0,
                assumptions=assumptions,
                method_params=method_params,
                estimand_type=estimand_type,
                graph_ref=data.graph_ref,
            )
            return wrap_causal_output(
                report, warnings=[report.status_reason or "estimation failed"]
            )

        ci = _extract_confidence_interval(estimate)
        if ci is None:
            epsilon = max(abs(original_estimate) * 1e-9, 1e-9)
            ci = (original_estimate - epsilon, original_estimate + epsilon)

        refutation_results: list[RefutationResult] = []
        diagnostics: list[DiagnosticTest] = []
        for test_type, refuter_method in DoWhyRefute._REFUTER_METHODS:
            refuter_kwargs: dict[str, Any] = {}
            if test_type is RefutationTestType.DATA_SUBSET:
                refuter_kwargs["subset_fraction"] = subset_fraction
            elif test_type is RefutationTestType.BOOTSTRAP:
                refuter_kwargs["num_simulations"] = bootstrap_num_simulations

            refuted_estimate = original_estimate
            p_value: float | None = None
            passed = False
            run_error: Exception | None = None
            call_kwargs = dict(refuter_kwargs)
            try:
                call_kwargs["random_state"] = seed
                refutation = model.refute_estimate(
                    identified,
                    estimate,
                    method_name=refuter_method,
                    **call_kwargs,
                )
            except TypeError:
                call_kwargs = dict(refuter_kwargs)
                try:
                    refutation = model.refute_estimate(
                        identified,
                        estimate,
                        method_name=refuter_method,
                        **call_kwargs,
                    )
                except Exception as exc:
                    run_error = exc
                    refutation = None
            except Exception as exc:
                run_error = exc
                refutation = None

            details: dict[str, Any]
            if run_error is None and refutation is not None:
                refuted_estimate = _extract_refuted_estimate(
                    refutation,
                    fallback=original_estimate,
                )
                p_value = _extract_p_value(refutation)
                effect_ratio = _compute_effect_ratio(
                    original=original_estimate,
                    refuted=refuted_estimate,
                )
                passed = (
                    np.isfinite(effect_ratio)
                    and abs(effect_ratio - 1.0) <= effect_ratio_tolerance
                    and (p_value is None or p_value >= p_value_threshold)
                )
                details = _to_safe_details(
                    {
                        "refuter_method": refuter_method,
                        "kwargs": call_kwargs,
                        "seed": seed,
                        "result": str(refutation),
                    }
                )
            else:
                effect_ratio = _compute_effect_ratio(
                    original=original_estimate,
                    refuted=refuted_estimate,
                )
                details = _to_safe_details(
                    {
                        "refuter_method": refuter_method,
                        "kwargs": call_kwargs,
                        "seed": seed,
                        "error": str(run_error),
                    }
                )

            result_item = RefutationResult(
                test_type=test_type,
                original_estimate=original_estimate,
                refuted_estimate=refuted_estimate,
                p_value=p_value,
                passed=passed,
                effect_ratio=effect_ratio,
                details=details,
            )
            refutation_results.append(result_item)
            diagnostics.append(
                DiagnosticTest(
                    test_name=f"refutation.{test_type.value}",
                    statistic=effect_ratio if np.isfinite(effect_ratio) else None,
                    p_value=p_value,
                    passed=passed,
                    details=dict(details),
                )
            )

        report = build_success_report(
            method=causal_method,
            estimand=estimand_type,
            point_estimate=original_estimate,
            confidence_interval=ci,
            inference_method=method_name,
            sample_size=sample_size,
            n_treated=n_treated,
            n_control=n_control,
            pre_periods=0,
            post_periods=0,
            assumptions=assumptions,
            diagnostics=diagnostics,
            standard_error=_extract_standard_error(estimate),
            method_params=method_params,
            identified_estimand=str(identified),
            estimand_type=estimand_type,
            graph_ref=data.graph_ref,
            refutation_results=refutation_results,
            metadata={
                "treatment": data.treatment,
                "outcome": data.outcome,
                "graph_supplied": data.graph_dot is not None,
                "refutation_tests": len(refutation_results),
                "refutation_seed": seed,
            },
        )
        return wrap_causal_output(report)


__all__ = ["DoWhyRefute", "_load_dowhy_dependencies"]
