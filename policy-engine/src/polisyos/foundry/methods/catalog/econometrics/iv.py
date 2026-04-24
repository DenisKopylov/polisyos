"""Public econometrics iv module API."""

from __future__ import annotations

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
from polisyos.foundry.methods.catalog._payloads import extract_model_payload

from .protocols import EconometricResult, PanelData

logger = get_logger(__name__)


def _iv_input_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=PanelData,
        nested_keys=("panel_data",),
    )


def _materialize_iv_data(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
    payload = _iv_input_payload(fallback_state)
    payload.update(bound_inputs)
    return PanelData.model_validate(payload)


def _iv_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                name="result",
                slot_type=SlotType.SCALAR,
                unit=Unit("result", "json"),
                contract_id=EconometricResult.contract_id,
            ),
            SlotSpec(
                name="uncertainty_envelope",
                slot_type=SlotType.SCALAR,
                unit=Unit("uncertainty", "json"),
            ),
        }
    )


def _iv_input_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                name="dependent",
                slot_type=SlotType.VECTOR,
                unit=Unit("outcome", "value"),
                shape=("n_obs",),
            ),
            SlotSpec(
                name="exog",
                slot_type=SlotType.MATRIX,
                unit=Unit("feature", "value"),
                shape=("n_obs", "n_features"),
            ),
            SlotSpec(
                name="entity_ids",
                slot_type=SlotType.VECTOR,
                unit=Unit("entity", "id"),
                shape=("n_obs",),
            ),
            SlotSpec(
                name="time_ids",
                slot_type=SlotType.VECTOR,
                unit=Unit("time", "index"),
                shape=("n_obs",),
            ),
            SlotSpec(
                name="instrument_ids",
                slot_type=SlotType.MATRIX,
                unit=Unit("instrument", "value"),
                shape=("n_obs", "n_instruments"),
            ),
        }
    )


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except Exception:
        return None
    if not np.isfinite(result):
        return None
    return result


def _extract_confidence_intervals(
    conf_int_obj: Any,
    *,
    param_names: list[str],
) -> dict[str, tuple[float, float]]:
    intervals: dict[str, tuple[float, float]] = {}
    for name in param_names:
        lo: float | None = None
        hi: float | None = None
        try:
            row = conf_int_obj.loc[name]
            if hasattr(row, "iloc"):
                lo = _safe_float(row.iloc[0])
                hi = _safe_float(row.iloc[1])
            else:
                values = np.asarray(row)
                if values.size >= 2:
                    lo = _safe_float(values[0])
                    hi = _safe_float(values[1])
        except Exception as exc:
            logger.debug("Ignored exception: %s", exc)
        if lo is None or hi is None:
            continue
        if lo > hi:
            lo, hi = hi, lo
        intervals[name] = (lo, hi)
    return intervals


def _call_conf_int(fit_result: Any, *, confidence_level: float) -> Any:
    conf_int_fn = getattr(fit_result, "conf_int", None)
    if conf_int_fn is None:
        return None
    try:
        return conf_int_fn(level=confidence_level)
    except TypeError:
        pass
    try:
        return conf_int_fn(alpha=1.0 - confidence_level)
    except TypeError:
        pass
    try:
        return conf_int_fn()
    except Exception:
        return None


def _build_result(
    *,
    method_name: str,
    fit_result: Any,
    confidence_level: float,
    diagnostics: dict[str, Any] | None = None,
) -> EconometricResult:
    params = fit_result.params
    param_names = [str(name) for name in getattr(params, "index", range(len(params)))]

    params_dict = {name: float(params[name]) for name in param_names}
    std_errors = {name: float(fit_result.std_errors[name]) for name in param_names}

    t_stats = {}
    p_values = {}
    for name in param_names:
        t_value = _safe_float(getattr(fit_result, "tstats", {}).get(name))
        p_value = _safe_float(getattr(fit_result, "pvalues", {}).get(name))
        if t_value is not None:
            t_stats[name] = t_value
        if p_value is not None:
            p_values[name] = p_value

    conf_int_obj = _call_conf_int(fit_result, confidence_level=confidence_level)
    intervals = (
        _extract_confidence_intervals(conf_int_obj, param_names=param_names)
        if conf_int_obj is not None
        else {}
    )

    return EconometricResult(
        method_name=method_name,
        params=params_dict,
        std_errors=std_errors,
        t_stats=t_stats,
        p_values=p_values,
        confidence_intervals=intervals,
        confidence_level=confidence_level,
        r_squared=_safe_float(getattr(fit_result, "rsquared", None)),
        n_obs=int(getattr(fit_result, "nobs", 0) or 0),
        diagnostics=diagnostics or {},
        model_info={
            "library": "linearmodels",
            "estimator": type(fit_result).__name__,
        },
    )


def _run_2sls(state: PanelData, params: Mapping[str, Any]) -> EconometricResult:
    import pandas as pd
    from linearmodels.iv import IV2SLS

    if state.instrument_ids is None:
        raise ValueError("2SLS requires instrument_ids in PanelData")

    n_obs, n_exog = state.exog.shape
    n_instr = state.instrument_ids.shape[1]

    n_endogenous = int(params.get("n_endogenous", 1))
    if n_endogenous <= 0 or n_endogenous >= n_exog:
        raise ValueError("n_endogenous must be in range [1, n_exog - 1]")

    feature_names = state.feature_names or [f"x{i}" for i in range(n_exog)]
    instrument_names = state.instrument_names or [f"z{j}" for j in range(n_instr)]

    frame = pd.DataFrame(state.exog, columns=feature_names)
    frame["y"] = state.dependent
    for idx, name in enumerate(instrument_names):
        frame[name] = state.instrument_ids[:, idx]

    endogenous_cols = feature_names[:n_endogenous]
    exogenous_cols = feature_names[n_endogenous:]

    dependent = frame["y"]
    endog = frame[endogenous_cols]
    exog = frame[exogenous_cols] if exogenous_cols else None
    instruments = frame[instrument_names]

    cov_type = str(params.get("cov_type", "robust"))
    fit_result = IV2SLS(dependent, exog, endog, instruments).fit(cov_type=cov_type)

    diagnostics: dict[str, Any] = {
        "method": "2sls",
        "cov_type": cov_type,
        "n_obs": n_obs,
    }
    first_stage = getattr(fit_result, "first_stage", None)
    if first_stage is not None:
        try:
            diagnostics["first_stage_summary"] = str(first_stage.summary)
        except Exception as exc:
            logger.debug("Ignored exception: %s", exc)

    return _build_result(
        method_name="iv_2sls",
        fit_result=fit_result,
        confidence_level=float(params.get("confidence_level", 0.95)),
        diagnostics=diagnostics,
    )


def _run_gmm(state: PanelData, params: Mapping[str, Any]) -> EconometricResult:
    import pandas as pd
    from linearmodels.iv import IVGMM

    if state.instrument_ids is None:
        raise ValueError("GMM requires instrument_ids in PanelData")

    n_obs, n_exog = state.exog.shape
    n_instr = state.instrument_ids.shape[1]

    n_endogenous = int(params.get("n_endogenous", 1))
    if n_endogenous <= 0 or n_endogenous >= n_exog:
        raise ValueError("n_endogenous must be in range [1, n_exog - 1]")

    feature_names = state.feature_names or [f"x{i}" for i in range(n_exog)]
    instrument_names = state.instrument_names or [f"z{j}" for j in range(n_instr)]

    frame = pd.DataFrame(state.exog, columns=feature_names)
    frame["y"] = state.dependent
    for idx, name in enumerate(instrument_names):
        frame[name] = state.instrument_ids[:, idx]

    endogenous_cols = feature_names[:n_endogenous]
    exogenous_cols = feature_names[n_endogenous:]

    dependent = frame["y"]
    endog = frame[endogenous_cols]
    exog = frame[exogenous_cols] if exogenous_cols else None
    instruments = frame[instrument_names]

    cov_type = str(params.get("cov_type", "robust"))
    weight_type = str(params.get("weight_type", "robust"))
    fit_result = IVGMM(
        dependent,
        exog,
        endog,
        instruments,
        weight_type=weight_type,
    ).fit(cov_type=cov_type)

    diagnostics: dict[str, Any] = {
        "method": "gmm",
        "cov_type": cov_type,
        "weight_type": weight_type,
        "n_obs": n_obs,
    }
    j_stat = getattr(fit_result, "j_stat", None)
    if j_stat is not None:
        stat = _safe_float(getattr(j_stat, "stat", None))
        pval = _safe_float(getattr(j_stat, "pval", None))
        if stat is not None:
            diagnostics["j_stat"] = stat
        if pval is not None:
            diagnostics["j_pvalue"] = pval

    return _build_result(
        method_name="iv_gmm",
        fit_result=fit_result,
        confidence_level=float(params.get("confidence_level", 0.95)),
        diagnostics=diagnostics,
    )


@foundry_method(
    namespace="econometrics.iv",
    version="1.0.0",
    tags={
        "econometrics",
        "instrumental-variables",
        "2sls",
        "gmm",
        "deprecated:aggregate-wrapper",
    },
)
class InstrumentalVariablesEstimator:
    """Instrumental Variables estimators via linearmodels."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("linearmodels", "pandas", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="instrumental_variables",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="panel_data",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("panel", "dataset"),
                    contract_id=PanelData.contract_id,
                )
            }
        ),
        output_slots=_iv_output_slots(),
        parameters=(
            ParameterSpec(name="method", default="2sls"),
            ParameterSpec(name="n_endogenous", default=1),
            ParameterSpec(name="cov_type", default="robust"),
            ParameterSpec(name="weight_type", default="robust"),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="envelope_param", default=None),
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
            "Instrumental Variables estimation with 2SLS and GMM backends "
            "for endogeneity-robust inference."
        ),
        tags=frozenset({"econometrics", "iv", "2sls", "gmm"}),
        citations=(
            "Angrist, J. & Pischke, J. (2009). Mostly Harmless Econometrics.",
            "Hansen, L. (1982). Large Sample Properties of GMM Estimators.",
        ),
        equations={
            "2sls_stage1": "X_hat = Z * pi + v",
            "2sls_stage2": "y = X_hat * beta + epsilon",
            "gmm_moment": "E[Z' * epsilon(beta)] = 0",
        },
        assumptions={
            "relevance": "Instruments must be correlated with endogenous regressors.",
            "exclusion": "Instruments affect outcome only through endogenous channel.",
            "exogeneity": "Instruments are orthogonal to structural error.",
        },
    )

    @staticmethod
    def pure_step(state: PanelData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, PanelData) else PanelData.model_validate(state)

        method = str(params.get("method", "2sls")).lower()
        if method == "gmm":
            result = _run_gmm(data, params)
        else:
            result = _run_2sls(data, params)

        envelope = result.to_uncertainty_envelope(param_name=params.get("envelope_param"))
        return {
            "result": result,
            "uncertainty_envelope": envelope,
        }

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
        return _materialize_iv_data(bound_inputs, fallback_state)


@foundry_method(
    namespace="econometrics.iv",
    version="1.0.0",
    tags={"econometrics", "instrumental-variables", "2sls"},
)
class TwoStageLeastSquaresEstimator:
    """Dedicated 2SLS estimator with explicit slots."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("linearmodels", "pandas", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="two_stage_least_squares",
        namespace="",
        version="0.0.0",
        input_slots=_iv_input_slots(),
        output_slots=_iv_output_slots(),
        parameters=(
            ParameterSpec(name="n_endogenous", default=1),
            ParameterSpec(name="cov_type", default="robust"),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="envelope_param", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Dedicated 2SLS IV estimator.",
        tags=frozenset({"econometrics", "instrumental-variables", "2sls"}),
        citations=InstrumentalVariablesEstimator.metadata.citations,
        equations={
            "2sls_stage1": InstrumentalVariablesEstimator.metadata.equations["2sls_stage1"],
            "2sls_stage2": InstrumentalVariablesEstimator.metadata.equations["2sls_stage2"],
        },
        assumptions=InstrumentalVariablesEstimator.metadata.assumptions,
        when_to_use="Endogenous regressor with valid instrument (relevance + exclusion restriction); LATE estimation",
        when_not_to_use="Weak instruments (F-stat < 10); no valid exclusion restriction; many instruments relative to obs",
        typical_min_obs=100,
        output_interpretation="LATE: Local Average Treatment Effect for compliers. First-stage F-stat should exceed 10. Sargan-Hansen for overidentification.",
    )

    @staticmethod
    def pure_step(state: PanelData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, PanelData) else PanelData.model_validate(state)
        result = _run_2sls(data, params)
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
        return _materialize_iv_data(bound_inputs, fallback_state)


@foundry_method(
    namespace="econometrics.iv",
    version="1.0.0",
    tags={"econometrics", "instrumental-variables", "gmm"},
)
class GMMEstimator:
    """Dedicated GMM IV estimator with explicit slots."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("linearmodels", "pandas", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="gmm",
        namespace="",
        version="0.0.0",
        input_slots=_iv_input_slots(),
        output_slots=_iv_output_slots(),
        parameters=(
            ParameterSpec(name="n_endogenous", default=1),
            ParameterSpec(name="cov_type", default="robust"),
            ParameterSpec(name="weight_type", default="robust"),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="envelope_param", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Dedicated IV GMM estimator.",
        tags=frozenset({"econometrics", "instrumental-variables", "gmm"}),
        citations=InstrumentalVariablesEstimator.metadata.citations,
        equations={"gmm_moment": InstrumentalVariablesEstimator.metadata.equations["gmm_moment"]},
        assumptions=InstrumentalVariablesEstimator.metadata.assumptions,
        when_to_use="Multiple instruments; heteroskedastic errors; panel IV; want efficient weighting of moments",
        when_not_to_use="Homoskedastic errors (2SLS is as efficient); few observations relative to instruments",
        typical_min_obs=150,
        output_interpretation="GMM coefficient + SE with optimal weighting matrix. J-statistic tests overidentifying restrictions (should not reject). Compare to 2SLS for efficiency gain.",
    )

    @staticmethod
    def pure_step(state: PanelData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, PanelData) else PanelData.model_validate(state)
        result = _run_gmm(data, params)
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
        return _materialize_iv_data(bound_inputs, fallback_state)


__all__ = [
    "GMMEstimator",
    "InstrumentalVariablesEstimator",
    "TwoStageLeastSquaresEstimator",
]
