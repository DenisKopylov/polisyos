"""Distributional-bounds request preparation, evaluation, and admission summaries."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import InputRef
from polisyos.foundry.methods.catalog.causal.distributional_bounds import (
    POINTWISE_NON_UNIFORM_WARNING,
    DistributionalBoundsEngineMethod,
)
from polisyos.ir.analytics.distributional import (
    DistributionalBoundsBundle,
    DistributionalBoundUniformity,
    DistributionalDualCertificate,
    DistributionalFunctional,
    DistributionalProofTarget,
    attach_distributional_dual_certificate_ref,
    persist_distributional_bounds_bundle,
    persist_distributional_dual_certificate,
)
from polisyos.ir.registry.refs import (
    DistributionalBoundsBundleRef,
    DistributionalDualCertificateRef,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

_DISTRIBUTIONAL_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_DISTRIBUTIONAL_LOAD_ERRORS = (OSError, RuntimeError, TypeError, ValueError, ValidationError)
_DISTRIBUTIONAL_EXECUTION_ERRORS = (RuntimeError, TypeError, ValueError, ValidationError)


@dataclass(frozen=True)
class _DistributionalBoundsResolution:
    refs: list[DistributionalBoundsBundleRef]
    assumptions: list[str]
    metadata: dict[str, Any]
    theorem_families: list[str]
    functionals: list[str]
    bound_uniformity: DistributionalBoundUniformity
    proof_target: DistributionalProofTarget


@dataclass(frozen=True)
class _DistributionalBoundsRequestPreparation:
    family: str
    assumptions: list[str]
    state_payload: dict[str, Any] | None
    skip_reason: str | None = None


def _prepare_distributional_bounds_request(
    request: dict[str, Any],
    *,
    config: dict[str, Any],
    state: ExperimentState,
    baseline_values: np.ndarray,
    counterfactual_values: np.ndarray,
) -> _DistributionalBoundsRequestPreparation:
    family = str(request.get("theorem_family", request.get("method_family", ""))).strip()
    if family not in {
        "lee_trimming_distributional",
        "makarov_pointwise",
        "mtr_headcount",
        "mtr_theil",
        "mtr_atkinson",
        "mtr_gini_lorenz",
        "sd_headcount",
        "sd_theil",
        "sd_atkinson",
        "sd_gini_lorenz",
    }:
        return _DistributionalBoundsRequestPreparation(
            family=family,
            assumptions=[],
            state_payload=None,
            skip_reason="unsupported_theorem_family",
        )

    assumptions = _string_list(
        request.get("assumptions")
        or config.get("assumptions")
        or state.params.get("distributional_bound_assumptions")
    )
    state_payload = _distributional_bounds_state_payload(
        request,
        family=family,
        baseline_values=baseline_values,
        counterfactual_values=counterfactual_values,
    )
    if state_payload is None:
        return _DistributionalBoundsRequestPreparation(
            family=family,
            assumptions=assumptions,
            state_payload=None,
            skip_reason="missing_required_data",
        )
    if family == "lee_trimming_distributional" and "monotone_selection_S1_ge_S0" not in assumptions:
        return _DistributionalBoundsRequestPreparation(
            family=family,
            assumptions=assumptions,
            state_payload=state_payload,
            skip_reason="missing_monotone_selection_assumption",
        )
    if family in {"mtr_headcount", "mtr_theil", "mtr_atkinson", "mtr_gini_lorenz"} and (
        "monotone_treatment_response_y1_ge_y0" not in assumptions
    ):
        return _DistributionalBoundsRequestPreparation(
            family=family,
            assumptions=assumptions,
            state_payload=state_payload,
            skip_reason="missing_mtr_assumption",
        )
    if family in {"sd_headcount", "sd_theil", "sd_atkinson", "sd_gini_lorenz"} and (
        "first_order_stochastic_dominance_y1_ge_y0" not in assumptions
    ):
        return _DistributionalBoundsRequestPreparation(
            family=family,
            assumptions=assumptions,
            state_payload=state_payload,
            skip_reason="missing_fosd_assumption",
        )
    if family == "makarov_pointwise" and not _makarov_marginals_licensed(request, config):
        return _DistributionalBoundsRequestPreparation(
            family=family,
            assumptions=assumptions,
            state_payload=state_payload,
            skip_reason="marginal_laws_not_licensed",
        )
    return _DistributionalBoundsRequestPreparation(
        family=family,
        assumptions=assumptions,
        state_payload=state_payload,
    )


def _resolve_distributional_bounds(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    baseline_values: np.ndarray,
    counterfactual_values: np.ndarray,
    inputs: list[InputRef],
) -> _DistributionalBoundsResolution:
    config = _distributional_bounds_config(state)
    if config is None:
        return _empty_distributional_bounds_resolution({"status": "not_requested"})

    refs: list[DistributionalBoundsBundleRef] = []
    theorem_families: list[str] = []
    functionals: list[str] = []
    assumptions: list[str] = []
    skipped: list[str] = []
    bundle_summaries: list[dict[str, Any]] = []

    for index, request in enumerate(_distributional_bounds_requests(config)):
        preparation = _prepare_distributional_bounds_request(
            request,
            config=config,
            state=state,
            baseline_values=baseline_values,
            counterfactual_values=counterfactual_values,
        )
        if preparation.skip_reason is not None:
            skipped.append(f"request_{index}:{preparation.skip_reason}")
            continue
        family = preparation.family
        request_assumptions = preparation.assumptions
        state_payload = preparation.state_payload
        if state_payload is None:
            skipped.append(f"request_{index}:missing_required_data")
            continue

        for functional, axis_values in _distributional_bounds_functional_axes(
            request,
            family=family,
            baseline_values=baseline_values,
            counterfactual_values=counterfactual_values,
        ):
            try:
                output = DistributionalBoundsEngineMethod.pure_step(
                    state_payload,
                    {
                        "theorem_family": family,
                        "functional": functional.value,
                        "axis_values": axis_values,
                        "target_potential_outcome": request.get("target_potential_outcome", "y1"),
                        "support_floor": request.get("support_floor"),
                        "support_ceiling": request.get("support_ceiling"),
                        "mean_floor": request.get("mean_floor"),
                        "outcome_unit": request.get("outcome_unit", "income"),
                    },
                )
                bundle_payload = output["result"]["distributional_bounds_bundle"]
                bundle = DistributionalBoundsBundle.model_validate(bundle_payload)
                dual_certificate_ref: DistributionalDualCertificateRef | None = None
                dual_certificate_payload = output["result"].get(
                    "distributional_dual_certificate_payload"
                )
                if isinstance(dual_certificate_payload, dict):
                    certificate = DistributionalDualCertificate.model_validate(
                        dual_certificate_payload
                    )
                    dual_certificate_ref = persist_distributional_dual_certificate(
                        _ensure_ir_artifact_store(ctx.store),
                        certificate,
                        inputs=inputs,
                    )
                    bundle = attach_distributional_dual_certificate_ref(
                        bundle, dual_certificate_ref
                    )
                ref = persist_distributional_bounds_bundle(
                    _ensure_ir_artifact_store(ctx.store),
                    bundle,
                    inputs=[
                        *inputs,
                        *(
                            [
                                InputRef(
                                    artifact_id=str(dual_certificate_ref.artifact_id),
                                    role="distributional_dual_certificate",
                                )
                            ]
                            if dual_certificate_ref is not None
                            else []
                        ),
                    ],
                )
            except _DISTRIBUTIONAL_EXECUTION_ERRORS as exc:
                skipped.append(f"request_{index}:{functional.value}:{exc.__class__.__name__}")
                continue
            refs.append(ref)
            theorem_families.append(str(bundle.metadata.get("theorem_family") or family))
            functionals.append(bundle.functional.value)
            assumptions.extend(request_assumptions)
            if bundle.method_summaries:
                assumptions.extend(
                    str(item) for item in bundle.method_summaries[0].assumptions_used
                )
            bundle_summaries.append(
                {
                    "ref": ref.model_dump(mode="json"),
                    "functional": bundle.functional.value,
                    "estimand_type": bundle.estimand_type,
                    "theorem_family": bundle.metadata.get("theorem_family") or family,
                    "sharpness_status": bundle.sharpness_status,
                    "warnings": list(bundle.warnings),
                    "pointwise_not_uniform": bool(bundle.metadata.get("pointwise_not_uniform")),
                    "dual_certificate_ref": (
                        bundle.dual_certificate_ref.model_dump(mode="json")
                        if bundle.dual_certificate_ref is not None
                        else None
                    ),
                }
            )

    if not refs:
        return _empty_distributional_bounds_resolution(
            {
                "status": "requested_but_not_applicable",
                "skipped_reasons": skipped,
            }
        )

    unique_theorems = _stable_unique(theorem_families)
    unique_functionals = _stable_unique(functionals)
    uniformity = _distributional_bounds_uniformity(bundle_summaries)
    return _DistributionalBoundsResolution(
        refs=refs,
        assumptions=_stable_unique(
            [
                *assumptions,
                "distributional_bounds_theorem_family",
                "bounded_distributional_functional",
            ]
        ),
        metadata={
            "status": "bounded",
            "primary_theorem_family": unique_theorems[0]
            if unique_theorems
            else "distributional_bounds",
            "theorem_families": unique_theorems,
            "functionals": unique_functionals,
            "bound_uniformity": uniformity.value,
            "bounds": bundle_summaries,
            "skipped_reasons": skipped,
            "pointwise_warning": any(
                POINTWISE_NON_UNIFORM_WARNING in summary.get("warnings", ())
                for summary in bundle_summaries
            ),
        },
        theorem_families=unique_theorems,
        functionals=unique_functionals,
        bound_uniformity=uniformity,
        proof_target=(
            DistributionalProofTarget.MARGINAL_PAIR
            if "makarov_pointwise" in unique_theorems
            else DistributionalProofTarget.CDF
        ),
    )


def _empty_distributional_bounds_resolution(
    metadata: dict[str, Any] | None = None,
) -> _DistributionalBoundsResolution:
    return _DistributionalBoundsResolution(
        refs=[],
        assumptions=[],
        metadata=dict(metadata or {}),
        theorem_families=[],
        functionals=[],
        bound_uniformity=DistributionalBoundUniformity.NOT_APPLICABLE,
        proof_target=DistributionalProofTarget.CDF,
    )


def _distributional_bounds_config(state: ExperimentState) -> dict[str, Any] | None:
    raw = state.params.get("distributional_bounds")
    if raw is None:
        raw = state.params.get("distributional_bounds_config")
    if not isinstance(raw, dict):
        return None
    if raw.get("enabled") is False:
        return None
    return dict(raw)


def _distributional_bounds_requests(config: dict[str, Any]) -> list[dict[str, Any]]:
    requests = config.get("requests")
    if isinstance(requests, list):
        return [dict(item) for item in requests if isinstance(item, dict)]
    return [dict(config)]


def _distributional_bounds_state_payload(
    request: dict[str, Any],
    *,
    family: str,
    baseline_values: np.ndarray,
    counterfactual_values: np.ndarray,
) -> dict[str, Any] | None:
    data = request.get("data") if isinstance(request.get("data"), dict) else request
    if family == "lee_trimming_distributional":
        outcome = _numeric_array(data.get("outcome"))
        treatment = _numeric_array(data.get("treatment"))
        selected = _numeric_array(data.get("selected"))
        if outcome is None or treatment is None or selected is None:
            return None
        return {"outcome": outcome, "treatment": treatment, "selected": selected}
    if family in {
        "mtr_headcount",
        "mtr_theil",
        "mtr_atkinson",
        "mtr_gini_lorenz",
        "sd_headcount",
        "sd_theil",
        "sd_atkinson",
        "sd_gini_lorenz",
    }:
        outcome = _numeric_array(data.get("outcome"))
        treatment = _numeric_array(data.get("treatment"))
        if outcome is None or treatment is None:
            return None
        return {"outcome": outcome, "treatment": treatment}

    treated = _numeric_array(data.get("treated_outcome"))
    control = _numeric_array(data.get("control_outcome"))
    if treated is None and bool(request.get("use_distributional_samples_as_marginals")):
        treated = np.asarray(counterfactual_values, dtype=float)
    if control is None and bool(request.get("use_distributional_samples_as_marginals")):
        control = np.asarray(baseline_values, dtype=float)
    if treated is None or control is None:
        return None
    return {"treated_outcome": treated, "control_outcome": control}


def _distributional_bounds_functional_axes(
    request: dict[str, Any],
    *,
    family: str,
    baseline_values: np.ndarray,
    counterfactual_values: np.ndarray,
) -> list[tuple[DistributionalFunctional, tuple[float, ...]]]:
    if family == "lee_trimming_distributional":
        return [
            (
                DistributionalFunctional.TAIL_DELTA,
                _axis_values_from_request(
                    request,
                    keys=("tail_thresholds", "thresholds"),
                    default=(float(np.median(baseline_values)),),
                ),
            ),
            (
                DistributionalFunctional.QUANTILE_SHIFT,
                _axis_values_from_request(
                    request,
                    keys=("quantiles",),
                    default=(0.25, 0.5, 0.75),
                ),
            ),
        ]
    if family in {"mtr_headcount", "sd_headcount"}:
        return [
            (
                DistributionalFunctional.POVERTY_HEADCOUNT,
                _axis_values_from_request(
                    request,
                    keys=("poverty_lines", "poverty_line", "thresholds"),
                    default=(float(np.median(baseline_values)),),
                ),
            ),
        ]
    if family in {"mtr_theil", "sd_theil"}:
        return [
            (
                DistributionalFunctional.THEIL_T,
                (1.0,),
            ),
        ]
    if family in {"mtr_atkinson", "sd_atkinson"}:
        return [
            (DistributionalFunctional.ATKINSON, (epsilon,))
            for epsilon in _axis_values_from_request(
                request,
                keys=("atkinson_epsilons", "atkinson_epsilon", "epsilons", "epsilon"),
                default=(0.5,),
            )
        ]
    if family in {"mtr_gini_lorenz", "sd_gini_lorenz"}:
        return [
            (
                DistributionalFunctional.GINI,
                (1.0,),
            ),
        ]
    return [
        (
            DistributionalFunctional.ITE_TAIL_RISK,
            _axis_values_from_request(
                request,
                keys=("harm_thresholds", "thresholds"),
                default=(0.0,),
            ),
        ),
        (
            DistributionalFunctional.QUANTILE,
            _axis_values_from_request(
                request,
                keys=("quantiles",),
                default=(0.25, 0.5, 0.75),
            ),
        ),
    ]


def _axis_values_from_request(
    request: dict[str, Any],
    *,
    keys: tuple[str, ...],
    default: tuple[float, ...],
) -> tuple[float, ...]:
    axis_payload = request.get("axis_values")
    if isinstance(axis_payload, dict):
        for key in keys:
            values = _float_tuple(axis_payload.get(key))
            if values:
                return values
    for key in keys:
        values = _float_tuple(request.get(key))
        if values:
            return values
    return default


def _makarov_marginals_licensed(
    request: dict[str, Any],
    config: dict[str, Any],
) -> bool:
    status = (
        str(request.get("marginal_law_status") or config.get("marginal_law_status") or "")
        .strip()
        .lower()
    )
    if status in {"identified", "bounded", "licensed"}:
        return True
    return bool(request.get("marginal_laws_licensed") or config.get("marginal_laws_licensed"))


def _distributional_bounds_uniformity(
    summaries: list[dict[str, Any]],
) -> DistributionalBoundUniformity:
    if any(summary.get("pointwise_not_uniform") for summary in summaries):
        return DistributionalBoundUniformity.POINTWISE_ONLY
    if any(POINTWISE_NON_UNIFORM_WARNING in summary.get("warnings", ()) for summary in summaries):
        return DistributionalBoundUniformity.POINTWISE_ONLY
    statuses = {str(summary.get("sharpness_status", "")) for summary in summaries}
    if statuses == {"sharp"}:
        return DistributionalBoundUniformity.UNIFORM_SHARP
    return DistributionalBoundUniformity.UNIFORM_OUTER


def _numeric_array(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError):
        return None
    if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
        return None
    return array


def _float_tuple(value: Any) -> tuple[float, ...]:
    if value is None:
        return ()
    if isinstance(value, (int, float)):
        return (float(value),)
    if not isinstance(value, (list, tuple)):
        return ()
    output: list[float] = []
    for item in value:
        try:
            number = float(item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            output.append(number)
    return tuple(output)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, (list, tuple, set, frozenset)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _stable_unique(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = str(value).strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            output.append(candidate)
    return output
