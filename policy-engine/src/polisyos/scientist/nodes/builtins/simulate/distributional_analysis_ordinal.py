"""Ordinal-poverty calculation and report construction for the distributional node."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import InputRef
from polisyos.foundry.methods.catalog.distributional.poverty_advanced import (
    OrdinalMultidimensionalPovertyEstimator,
)
from polisyos.ir.analytics.distributional import (
    OrdinalPovertyEstimate,
    OrdinalPovertyReport,
    persist_ordinal_poverty_report,
)
from polisyos.ir.registry.refs import (
    OrdinalPovertyReportRef,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    NodeEvent,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState

_DISTRIBUTIONAL_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)


@dataclass(frozen=True)
class _OrdinalPovertyResolution:
    ref: OrdinalPovertyReportRef | None
    summary: dict[str, Any]
    events: tuple[NodeEvent, ...]
    metadata: dict[str, Any]


def _coerce_optional_bool(raw_value: Any, *, name: str, default: bool) -> bool:
    if raw_value is None:
        return default
    if isinstance(raw_value, bool):
        return raw_value
    raise TypeError(f"{name} must be True/False when provided")


def _coerce_ordinal_category_matrix(
    raw_matrix: Any,
    *,
    name: str,
    expected_agents: int | None = None,
) -> np.ndarray:
    matrix = np.asarray(raw_matrix, dtype=object)
    if matrix.ndim != 2:
        raise ValueError(f"{name} must be a 2D matrix")
    if matrix.shape[0] == 0:
        raise ValueError(f"{name} must not be empty")
    if expected_agents is not None and matrix.shape[0] != expected_agents:
        raise ValueError(
            f"{name} row count must match agent count {expected_agents}, got {matrix.shape[0]}"
        )
    return matrix


def _coerce_ordinal_weights(raw_weights: Any, *, n_dimensions: int) -> np.ndarray:
    if raw_weights is None:
        return np.full(n_dimensions, 1.0 / n_dimensions, dtype=np.float64)
    weights = np.asarray(raw_weights, dtype=np.float64)
    if weights.ndim != 1:
        raise ValueError("ordinal_poverty weights must be a 1D vector")
    if weights.shape[0] != n_dimensions:
        raise ValueError("ordinal_poverty weights length must match the number of dimensions")
    if np.any(~np.isfinite(weights)):
        raise ValueError("ordinal_poverty weights must be finite")
    if np.any(weights < 0.0):
        raise ValueError("ordinal_poverty weights must be non-negative")
    if float(np.sum(weights)) <= 0.0:
        raise ValueError("ordinal_poverty weights must sum to a positive value")
    return weights


def _ordinal_estimate_summary(estimate: OrdinalPovertyEstimate) -> dict[str, Any]:
    cutoff_diagnostics = dict(estimate.cutoff_diagnostics)
    cutoff_excerpt = (
        {
            "current_cutoffs": cutoff_diagnostics.get("current_cutoffs", []),
            "local_slopes": cutoff_diagnostics.get("local_slopes", {}),
            "flip_shares": cutoff_diagnostics.get("flip_shares", {}),
            "preferred_cutoff_plateau": cutoff_diagnostics.get("preferred_cutoff_plateau", []),
            "recoding_invariance_bound": cutoff_diagnostics.get("recoding_invariance_bound", 0.0),
        }
        if cutoff_diagnostics
        else {}
    )
    return {
        "headcount_h": estimate.headcount_h,
        "ordinal_intensity_a": estimate.ordinal_intensity_a,
        "ordinal_adjusted_headcount_q": estimate.ordinal_adjusted_headcount_q,
        "af_m0_baseline": estimate.af_m0_baseline,
        "beta": estimate.beta,
        "k_threshold": estimate.k_threshold,
        "n_agents": estimate.n_agents,
        "n_dimensions": estimate.n_dimensions,
        "n_poor": estimate.n_poor,
        "dimension_names": list(estimate.dimension_names),
        "deprivation_cutoffs": list(estimate.deprivation_cutoffs),
        "dimension_weights": list(estimate.dimension_weights),
        "threshold_weights_basis": estimate.threshold_weights_basis,
        "dimension_contributions": dict(estimate.dimension_contributions),
        "cutoff_sensitivity": cutoff_excerpt,
        "legacy_gap_envelope": dict(estimate.legacy_gap_envelope),
    }


def _ordinal_poverty_summary_from_report(
    report: OrdinalPovertyReport,
    *,
    ref: OrdinalPovertyReportRef,
) -> dict[str, Any]:
    summary = {
        "status": "included" if report.counterfactual is not None else "baseline_only",
        "methodology": report.methodology,
        "ordinal_poverty_ref": str(ref.artifact_id),
        "baseline": _ordinal_estimate_summary(report.baseline),
        "deltas": dict(report.deltas),
    }
    if report.counterfactual is not None:
        summary["counterfactual"] = _ordinal_estimate_summary(report.counterfactual)
    return summary


def _run_ordinal_poverty_estimate(
    config: Mapping[str, Any],
    *,
    category_matrix: np.ndarray,
    label: str,
) -> OrdinalPovertyEstimate:
    n_dimensions = int(category_matrix.shape[1])
    weights = _coerce_ordinal_weights(
        config.get("dimension_weights", config.get("weights")),
        n_dimensions=n_dimensions,
    )
    params = {
        "category_orders": config.get("category_orders"),
        "deprivation_cutoffs": config.get("deprivation_cutoffs"),
        "k_threshold": config.get("poverty_cutoff_K", config.get("k_threshold", 0.33)),
        "beta": config.get("beta", 1.0),
        "threshold_weights": config.get("threshold_weights", "equal"),
        "dimension_names": config.get("dimension_names"),
        "return_censored_scores": _coerce_optional_bool(
            config.get("return_censored_scores"),
            name="ordinal_poverty.return_censored_scores",
            default=True,
        ),
        "return_dimension_contributions": _coerce_optional_bool(
            config.get("return_dimension_contributions"),
            name="ordinal_poverty.return_dimension_contributions",
            default=True,
        ),
        "return_cutoff_diagnostics": _coerce_optional_bool(
            config.get("return_cutoff_diagnostics"),
            name="ordinal_poverty.return_cutoff_diagnostics",
            default=True,
        ),
        "cutoff_grid": config.get("cutoff_grid"),
        "max_cutoff_grid_size": int(config.get("max_cutoff_grid_size", 256)),
        "comparator_recodings": config.get("comparator_recodings"),
    }
    payload = OrdinalMultidimensionalPovertyEstimator.pure_step(
        {
            "category_matrix": category_matrix,
            "weights": weights,
        },
        params,
    )
    estimate = OrdinalPovertyEstimate.model_validate(
        {
            **payload["result"],
            "metadata": {
                "population_label": label,
                **dict(payload["result"].get("metadata", {})),
            },
        }
    )
    return estimate


def _maybe_build_ordinal_poverty_report(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    artifact_inputs: list[InputRef],
    sim_result_ref: Any,
    baseline_agent_count: int,
    counterfactual_agent_count: int,
) -> _OrdinalPovertyResolution:
    raw_config = state.params.get("ordinal_poverty")
    if raw_config is None:
        return _OrdinalPovertyResolution(
            ref=None,
            summary={},
            events=(),
            metadata={"ordinal_poverty_status": "not_requested"},
        )
    if not isinstance(raw_config, Mapping):
        message = "ordinal_poverty config must be a mapping; skipping ordinal poverty integration"
        return _OrdinalPovertyResolution(
            ref=None,
            summary={"status": "skipped", "reason": message},
            events=(NodeEvent(level="warn", message=message),),
            metadata={
                "ordinal_poverty_status": "skipped",
                "ordinal_poverty_reason": message,
            },
        )

    try:
        enabled = _coerce_optional_bool(
            raw_config.get("enabled"),
            name="ordinal_poverty.enabled",
            default=True,
        )
    except _DISTRIBUTIONAL_VALIDATION_ERRORS as exc:
        message = f"Ordinal poverty config invalid: {exc}"
        return _OrdinalPovertyResolution(
            ref=None,
            summary={"status": "skipped", "reason": str(exc)},
            events=(NodeEvent(level="warn", message=message),),
            metadata={
                "ordinal_poverty_status": "skipped",
                "ordinal_poverty_reason": str(exc),
            },
        )

    if not enabled:
        return _OrdinalPovertyResolution(
            ref=None,
            summary={"status": "disabled"},
            events=(),
            metadata={"ordinal_poverty_status": "disabled"},
        )

    try:
        baseline_raw = raw_config.get("baseline_category_matrix", raw_config.get("category_matrix"))
        baseline_matrix = _coerce_ordinal_category_matrix(
            baseline_raw,
            name="ordinal_poverty.baseline_category_matrix",
            expected_agents=baseline_agent_count,
        )
        counterfactual_raw = raw_config.get(
            "counterfactual_category_matrix",
            raw_config.get("simulated_category_matrix"),
        )
        counterfactual_matrix = (
            _coerce_ordinal_category_matrix(
                counterfactual_raw,
                name="ordinal_poverty.counterfactual_category_matrix",
                expected_agents=counterfactual_agent_count,
            )
            if counterfactual_raw is not None
            else None
        )
        baseline = _run_ordinal_poverty_estimate(
            raw_config,
            category_matrix=baseline_matrix,
            label="baseline",
        )
        counterfactual = (
            _run_ordinal_poverty_estimate(
                raw_config,
                category_matrix=counterfactual_matrix,
                label="counterfactual",
            )
            if counterfactual_matrix is not None
            else None
        )
        report = OrdinalPovertyReport(
            methodology=str(raw_config.get("methodology", "oraf_phase2")),
            baseline=baseline,
            counterfactual=counterfactual,
            source_simulation_ref=str(sim_result_ref.artifact_id),
            metadata={
                "run_id": state.run_id,
                "baseline_agent_count": baseline_agent_count,
                "counterfactual_agent_count": counterfactual_agent_count,
            },
        )
        ref = persist_ordinal_poverty_report(
            _ensure_ir_artifact_store(ctx.store), report, inputs=artifact_inputs
        )
        summary = _ordinal_poverty_summary_from_report(report, ref=ref)
        event_message = (
            "Ordinal multidimensional poverty report generated"
            if counterfactual is not None
            else "Ordinal multidimensional poverty baseline report generated"
        )
        return _OrdinalPovertyResolution(
            ref=ref,
            summary=summary,
            events=(NodeEvent(level="info", message=event_message),),
            metadata={
                "ordinal_poverty_status": summary["status"],
                "ordinal_poverty_ref": str(ref.artifact_id),
                "ordinal_poverty_methodology": report.methodology,
            },
        )
    except _DISTRIBUTIONAL_VALIDATION_ERRORS as exc:
        message = f"Ordinal poverty analysis skipped: {exc}"
        return _OrdinalPovertyResolution(
            ref=None,
            summary={"status": "skipped", "reason": str(exc)},
            events=(NodeEvent(level="warn", message=message),),
            metadata={
                "ordinal_poverty_status": "skipped",
                "ordinal_poverty_reason": str(exc),
            },
        )
