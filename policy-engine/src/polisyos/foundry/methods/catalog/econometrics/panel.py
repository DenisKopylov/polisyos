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

from .protocols import EconometricResult, PanelData


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
        raise ValueError(
            "Fixed Effects dropped all regressors as time-invariant within entities"
        )

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
            except Exception:
                pass

        if lo is not None and hi is not None:
            if lo > hi:
                lo, hi = hi, lo
            intervals[name] = (lo, hi)

    return intervals


def _build_result(
    *,
    method_name: str,
    fit_result: Any,
    confidence_level: float,
    n_entities: int,
    n_periods: int,
    diagnostics: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
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

    alpha = 1.0 - confidence_level
    conf_int_obj = fit_result.conf_int(alpha=alpha) if hasattr(fit_result, "conf_int") else None
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
    )


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
    frame["time"] = state.time_ids
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

    return _build_result(
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
    )


def _run_random_effects(state: PanelData, params: Mapping[str, Any]) -> EconometricResult:
    import pandas as pd
    from linearmodels.panel import RandomEffects

    names = _feature_names(state)
    frame = pd.DataFrame(state.exog, columns=names)
    frame["y"] = state.dependent
    frame["entity"] = state.entity_ids
    frame["time"] = state.time_ids
    frame = frame.set_index(["entity", "time"])

    cov_type = str(params.get("cov_type", "robust"))
    formula = "y ~ 1 + " + " + ".join(names)
    model = RandomEffects.from_formula(formula, data=frame)
    fit_result = model.fit(cov_type=cov_type)

    return _build_result(
        method_name="random_effects",
        fit_result=fit_result,
        confidence_level=float(params.get("confidence_level", 0.95)),
        n_entities=state.n_entities,
        n_periods=state.n_periods,
        diagnostics={"cov_type": cov_type},
    )


@foundry_method(
    namespace="econometrics.panel",
    version="1.0.0",
    tags={"econometrics", "panel-data", "fixed-effects", "random-effects"},
)
class PanelDataEstimator:
    """Panel-data estimators via linearmodels."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="panel_data",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="panel_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("panel", "observations"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="econometric_result",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("result", "json"),
                )
            }
        ),
        parameters=(
            ParameterSpec(name="model", default="fixed_effects"),
            ParameterSpec(name="cov_type", default="robust"),
            ParameterSpec(name="include_time_effects", default=False),
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
            "envelope": envelope,
        }


__all__ = ["PanelDataEstimator"]
