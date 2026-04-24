"""Public econometrics panel module API."""

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

from .dependence import route_cross_sectional_dependence
from .protocols import EconometricResult, PanelData

logger = get_logger(__name__)


def _panel_input_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=PanelData,
        nested_keys=("panel_data",),
    )


def _materialize_panel_data(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
    payload = _panel_input_payload(fallback_state)
    payload.update(bound_inputs)
    return PanelData.model_validate(payload)


def _panel_output_slots() -> frozenset[SlotSpec]:
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


def _explicit_panel_input_slots() -> frozenset[SlotSpec]:
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
        }
    )


def _feature_names(state: PanelData) -> list[str]:
    if state.feature_names:
        return list(state.feature_names)
    return [f"x{i}" for i in range(state.n_features)]


def _drop_time_invariant_exog(
    exog: np.ndarray,
    entity_ids: np.ndarray,
    names: list[str],
) -> tuple[np.ndarray, list[str], list[str]]:
    dropped: list[str] = []
    keep_idx: list[int] = []

    unique_entities = np.unique(entity_ids)
    for idx, name in enumerate(names):
        column = exog[:, idx]
        invariant_within_entities = True
        for entity in unique_entities:
            entity_values = column[entity_ids == entity]
            if entity_values.size <= 1:
                continue
            if float(np.max(entity_values) - np.min(entity_values)) > 1e-12:
                invariant_within_entities = False
                break
        if invariant_within_entities:
            dropped.append(name)
        else:
            keep_idx.append(idx)

    if not keep_idx:
        raise ValueError("Fixed Effects dropped all regressors as time-invariant within entities")

    reduced = exog[:, keep_idx]
    kept_names = [names[i] for i in keep_idx]
    return reduced, kept_names, dropped


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
        except Exception:
            try:
                row = conf_int_obj[name]
                values = np.asarray(row)
                if values.size >= 2:
                    lo = _safe_float(values[0])
                    hi = _safe_float(values[1])
            except Exception as exc:
                logger.debug("Ignored exception: %s", exc)

        if lo is not None and hi is not None:
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
    n_entities: int,
    n_periods: int,
    diagnostics: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    cross_sectional_dependence_diagnostic: Any = None,
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

    f_stat = None
    f_pvalue = None
    f_stat_obj = getattr(fit_result, "f_statistic", None)
    if f_stat_obj is not None:
        f_stat = _safe_float(getattr(f_stat_obj, "stat", None))
        f_pvalue = _safe_float(getattr(f_stat_obj, "pval", None))

    return EconometricResult(
        method_name=method_name,
        params=params_dict,
        std_errors=std_errors,
        t_stats=t_stats,
        p_values=p_values,
        confidence_intervals=intervals,
        confidence_level=confidence_level,
        r_squared=_safe_float(getattr(fit_result, "rsquared", None)),
        adj_r_squared=_safe_float(getattr(fit_result, "rsquared_adj", None)),
        f_statistic=f_stat,
        f_pvalue=f_pvalue,
        n_obs=int(getattr(fit_result, "nobs", 0) or 0),
        n_entities=n_entities,
        n_periods=n_periods,
        diagnostics=diagnostics or {},
        model_info={
            "library": "linearmodels",
            "estimator": type(fit_result).__name__,
        },
        metadata=metadata or {},
        cross_sectional_dependence_diagnostic=cross_sectional_dependence_diagnostic,
    )


def _resolve_dependence_metadata(state: PanelData, params: Mapping[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if isinstance(state.metadata.get("dependence_metadata"), Mapping):
        metadata.update(dict(state.metadata["dependence_metadata"]))
    for key in ("cluster_ids", "coords", "W", "graph"):
        if key in state.metadata:
            metadata[key] = state.metadata[key]
    param_metadata = params.get("dependence_metadata")
    if isinstance(param_metadata, Mapping):
        metadata.update(dict(param_metadata))
    return metadata


def _maybe_build_dependence_diagnostic(
    *,
    fit_result: Any,
    state: PanelData,
    params: Mapping[str, Any],
    used_time_dummies: bool,
) -> Any | None:
    dependence_mode = str(params.get("dependence_mode", "off")).strip().lower()
    if dependence_mode in {"", "off", "none", "false"}:
        return None

    residuals = getattr(fit_result, "resids", None)
    if residuals is None:
        return None

    return route_cross_sectional_dependence(
        np.asarray(residuals, dtype=float),
        entity_ids=state.entity_ids,
        time_ids=state.time_ids,
        dependence_metadata=_resolve_dependence_metadata(state, params),
        used_time_dummies=used_time_dummies,
        dependence_covariance=params.get("dependence_covariance", "auto"),
        dependence_fallback=str(params.get("dependence_fallback", "conservative")).strip().lower(),
        covariance_applied=False,
    )


def _apply_dependence_posture(
    result: EconometricResult,
    *,
    params: Mapping[str, Any],
) -> EconometricResult:
    diagnostic = result.cross_sectional_dependence_diagnostic
    if diagnostic is None:
        return result

    metadata = dict(result.metadata)
    warnings = list(metadata.get("warnings", []))
    warnings.append(
        "Cross-sectional dependence router classified residual dependence as "
        f"'{diagnostic.class_label}' with status '{diagnostic.estimator_status}'."
    )
    metadata["warnings"] = warnings
    metadata["dependence_posture"] = {
        "class_label": diagnostic.class_label,
        "strength": diagnostic.strength,
        "estimator_status": diagnostic.estimator_status,
        "recommended_covariance": diagnostic.recommended_covariance,
    }

    fallback = str(params.get("dependence_fallback", "conservative")).strip().lower()
    if diagnostic.estimator_status == "ok_conservative":
        metadata["exploratory_only"] = True

    if fallback == "suppress_inference" and diagnostic.estimator_status in {
        "reroute_required",
        "unsafe_for_default_inference",
    }:
        metadata["inference_suppressed"] = True
        metadata["exploratory_only"] = True
        return result.model_copy(
            update={
                "std_errors": {},
                "t_stats": {},
                "p_values": {},
                "confidence_intervals": {},
                "metadata": metadata,
            }
        )

    return result.model_copy(update={"metadata": metadata})


def _run_fixed_effects(state: PanelData, params: Mapping[str, Any]) -> EconometricResult:
    import pandas as pd
    from linearmodels.panel import PanelOLS

    names = _feature_names(state)
    reduced_exog, reduced_names, dropped = _drop_time_invariant_exog(
        state.exog,
        state.entity_ids,
        names,
    )

    frame = pd.DataFrame(reduced_exog, columns=reduced_names)
    frame["y"] = state.dependent
    frame["entity"] = state.entity_ids
    frame["time"] = _coerce_panel_time_ids(state.time_ids, pd=pd)
    frame = frame.set_index(["entity", "time"])

    include_time_effects = bool(params.get("include_time_effects", False))
    cov_type = str(params.get("cov_type", "robust"))

    rhs = " + ".join(reduced_names)
    if include_time_effects:
        formula = f"y ~ {rhs} + EntityEffects + TimeEffects"
    else:
        formula = f"y ~ {rhs} + EntityEffects"

    model = PanelOLS.from_formula(formula, data=frame)
    fit_result = model.fit(cov_type=cov_type)

    warnings: list[str] = []
    for name in dropped:
        warnings.append(f"Dropped time-invariant variable '{name}' for Fixed Effects")

    dependence_diagnostic = _maybe_build_dependence_diagnostic(
        fit_result=fit_result,
        state=state,
        params=params,
        used_time_dummies=include_time_effects,
    )

    result = _build_result(
        method_name="fixed_effects",
        fit_result=fit_result,
        confidence_level=float(params.get("confidence_level", 0.95)),
        n_entities=state.n_entities,
        n_periods=state.n_periods,
        diagnostics={
            "cov_type": cov_type,
            "include_time_effects": include_time_effects,
            "dropped_time_invariant": dropped,
        },
        metadata={"warnings": warnings},
        cross_sectional_dependence_diagnostic=dependence_diagnostic,
    )
    return _apply_dependence_posture(result, params=params)


def _run_random_effects(state: PanelData, params: Mapping[str, Any]) -> EconometricResult:
    import pandas as pd
    from linearmodels.panel import RandomEffects

    names = _feature_names(state)
    frame = pd.DataFrame(state.exog, columns=names)
    frame["y"] = state.dependent
    frame["entity"] = state.entity_ids
    frame["time"] = _coerce_panel_time_ids(state.time_ids, pd=pd)
    frame = frame.set_index(["entity", "time"])

    cov_type = str(params.get("cov_type", "robust"))
    formula = "y ~ 1 + " + " + ".join(names)
    model = RandomEffects.from_formula(formula, data=frame)
    fit_result = model.fit(cov_type=cov_type)

    dependence_diagnostic = _maybe_build_dependence_diagnostic(
        fit_result=fit_result,
        state=state,
        params=params,
        used_time_dummies=False,
    )

    result = _build_result(
        method_name="random_effects",
        fit_result=fit_result,
        confidence_level=float(params.get("confidence_level", 0.95)),
        n_entities=state.n_entities,
        n_periods=state.n_periods,
        diagnostics={"cov_type": cov_type},
        cross_sectional_dependence_diagnostic=dependence_diagnostic,
    )
    return _apply_dependence_posture(result, params=params)


def _coerce_panel_time_ids(time_ids: np.ndarray, *, pd: Any) -> np.ndarray:
    """Normalize panel time ids so linearmodels receives numeric or date-like values."""

    index = pd.Index(time_ids)
    if pd.api.types.is_numeric_dtype(index.dtype) or pd.api.types.is_datetime64_any_dtype(
        index.dtype
    ):
        return time_ids

    coerced = pd.to_datetime(time_ids, errors="coerce")
    if not coerced.isna().any():
        return coerced.to_numpy()

    return time_ids


@foundry_method(
    namespace="econometrics.panel",
    version="1.0.0",
    tags={
        "econometrics",
        "panel-data",
        "fixed-effects",
        "random-effects",
        "deprecated:aggregate-wrapper",
    },
)
class PanelDataEstimator:
    """Panel-data estimators via linearmodels."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("linearmodels", "pandas", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="panel_data",
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
        output_slots=_panel_output_slots(),
        parameters=(
            ParameterSpec(name="model", default="fixed_effects"),
            ParameterSpec(name="cov_type", default="robust"),
            ParameterSpec(name="include_time_effects", default=False),
            ParameterSpec(name="dependence_mode", default="off"),
            ParameterSpec(name="dependence_covariance", default="auto"),
            ParameterSpec(name="dependence_fallback", default="conservative"),
            ParameterSpec(name="dependence_metadata", default=None),
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
        description="Panel-data estimation using Fixed Effects and Random Effects models.",
        tags=frozenset({"econometrics", "panel-data"}),
        citations=(
            "Wooldridge, J. (2010). Econometric Analysis of Cross Section and Panel Data.",
            "Baltagi, B. (2021). Econometric Analysis of Panel Data.",
        ),
        equations={
            "fixed_effects": "y_it = alpha_i + X_it * beta + epsilon_it",
            "random_effects": "y_it = alpha + X_it * beta + u_i + epsilon_it",
        },
        assumptions={
            "fixed_effects": "Entity-specific effects may correlate with regressors.",
            "random_effects": "Entity-specific effects are uncorrelated with regressors.",
            "strict_exogeneity": "E[epsilon_it | X_i1 ... X_iT, alpha_i] = 0",
        },
    )

    @staticmethod
    def pure_step(state: PanelData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, PanelData) else PanelData.model_validate(state)

        model = str(params.get("model", "fixed_effects")).lower()
        if model == "random_effects":
            result = _run_random_effects(data, params)
        else:
            result = _run_fixed_effects(data, params)

        envelope = result.to_uncertainty_envelope(param_name=params.get("envelope_param"))
        return {
            "result": result,
            "uncertainty_envelope": envelope,
        }

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
        return _materialize_panel_data(bound_inputs, fallback_state)


@foundry_method(
    namespace="econometrics.panel",
    version="1.0.0",
    tags={"econometrics", "fixed-effects"},
)
class FixedEffectsEstimator:
    """Dedicated Fixed Effects estimator with explicit panel slots."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("linearmodels", "pandas", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="fixed_effects",
        namespace="",
        version="0.0.0",
        input_slots=_explicit_panel_input_slots(),
        output_slots=_panel_output_slots(),
        parameters=(
            ParameterSpec(name="cov_type", default="robust"),
            ParameterSpec(name="include_time_effects", default=False),
            ParameterSpec(name="dependence_mode", default="off"),
            ParameterSpec(name="dependence_covariance", default="auto"),
            ParameterSpec(name="dependence_fallback", default="conservative"),
            ParameterSpec(name="dependence_metadata", default=None),
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
        description="Dedicated Fixed Effects panel estimator.",
        tags=frozenset({"econometrics", "fixed-effects"}),
        citations=PanelDataEstimator.metadata.citations,
        equations={"fixed_effects": PanelDataEstimator.metadata.equations["fixed_effects"]},
        assumptions=PanelDataEstimator.metadata.assumptions,
        when_to_use="Panel data; want to control for time-invariant unobserved heterogeneity; treatment varies within unit over time",
        when_not_to_use="Cross-sectional only; time-invariant treatment; interest in between-unit effects",
        typical_min_obs=50,
        output_interpretation="Within-estimator coefficient: effect of X on Y controlling for unit FE. Hausman test to choose between FE/RE.",
    )

    @staticmethod
    def pure_step(state: PanelData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, PanelData) else PanelData.model_validate(state)
        result = _run_fixed_effects(data, params)
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
        return _materialize_panel_data(bound_inputs, fallback_state)


@foundry_method(
    namespace="econometrics.panel",
    version="1.0.0",
    tags={"econometrics", "random-effects"},
)
class RandomEffectsEstimator:
    """Dedicated Random Effects estimator with explicit panel slots."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("linearmodels", "pandas", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="random_effects",
        namespace="",
        version="0.0.0",
        input_slots=_explicit_panel_input_slots(),
        output_slots=_panel_output_slots(),
        parameters=(
            ParameterSpec(name="cov_type", default="robust"),
            ParameterSpec(name="dependence_mode", default="off"),
            ParameterSpec(name="dependence_covariance", default="auto"),
            ParameterSpec(name="dependence_fallback", default="conservative"),
            ParameterSpec(name="dependence_metadata", default=None),
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
        description="Dedicated Random Effects panel estimator.",
        tags=frozenset({"econometrics", "random-effects"}),
        citations=PanelDataEstimator.metadata.citations,
        equations={"random_effects": PanelDataEstimator.metadata.equations["random_effects"]},
        assumptions=PanelDataEstimator.metadata.assumptions,
        when_to_use="Panel data; individual effects uncorrelated with regressors; want to estimate between-unit effects",
        when_not_to_use="Correlated random effects (use FE or Mundlak); unbalanced panel with few periods per unit",
        typical_min_obs=50,
        output_interpretation="GLS estimator. More efficient than FE if RE assumption holds. Compare with FE via Hausman test.",
    )

    @staticmethod
    def pure_step(state: PanelData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, PanelData) else PanelData.model_validate(state)
        result = _run_random_effects(data, params)
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
        return _materialize_panel_data(bound_inputs, fallback_state)


__all__ = [
    "FixedEffectsEstimator",
    "PanelDataEstimator",
    "RandomEffectsEstimator",
]
