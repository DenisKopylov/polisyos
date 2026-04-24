"""Public causal transport bounds module API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from polisyos.foundry.methods.catalog.causal.lp_bounds import auto_bounds
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    PartialIdentificationResult,
    compute_manski_bounds,
)
from polisyos.ir.analytics.transportability import SelectionDiagram


def _extract_arrays(data: Mapping[str, Any] | None) -> tuple[np.ndarray, np.ndarray] | None:
    if data is None:
        return None
    outcome = data.get("outcome")
    treatment = data.get("treatment")
    if outcome is None or treatment is None:
        return None
    y = np.asarray(outcome, dtype=float).reshape(-1)
    t = np.asarray(treatment, dtype=float).reshape(-1)
    if y.size == 0 or t.size == 0 or y.size != t.size:
        return None
    finite = np.isfinite(y) & np.isfinite(t)
    if not np.any(finite):
        return None
    y = y[finite]
    t = t[finite]
    if y.size == 0 or t.size == 0:
        return None
    return y, t


def _resolved_count(
    selection_diagram: SelectionDiagram, constraints: Mapping[str, Any] | None
) -> int:
    if not constraints:
        return 0
    resolved = constraints.get("resolved_s_nodes") or constraints.get("eliminated_s_nodes")
    if resolved is None:
        return 0
    if isinstance(resolved, int):
        return max(0, resolved)
    if isinstance(resolved, (list, tuple, set, frozenset)):
        return len(resolved)
    return 0


def _manski_like_pid(data: Mapping[str, Any] | None) -> PartialIdentificationResult:
    arrays = _extract_arrays(data)
    if arrays is None:
        return PartialIdentificationResult(
            method=BoundMethod.MANSKI,
            lower_bound=-1.0,
            upper_bound=1.0,
            confidence=0.05,
            assumptions_used=["worst_case_transport_ignorance"],
            bounds_type="manski",
            display_label="Worst-case transport ignorance bounds",
        )
    outcome, treatment = arrays
    treated = treatment > 0.5
    if not np.any(treated) or not np.any(~treated):
        support = float(np.max(outcome) - np.min(outcome)) if outcome.size else 1.0
        support = max(support, 1.0)
        return PartialIdentificationResult(
            method=BoundMethod.MANSKI,
            lower_bound=-support,
            upper_bound=support,
            confidence=0.05,
            assumptions_used=["worst_case_transport_ignorance", "degenerate_treatment_support"],
            bounds_type="manski",
            display_label="Worst-case transport ignorance bounds",
        )
    pid = compute_manski_bounds(
        outcome_conditioned=np.array(
            [
                float(np.mean(outcome[~treated])),
                float(np.mean(outcome[treated])),
            ]
        ),
        treatment_probs=np.array(
            [
                float(np.mean(~treated)),
                float(np.mean(treated)),
            ]
        ),
        outcome_support=(float(np.min(outcome)), float(np.max(outcome))),
    )
    return pid.model_copy(
        update={
            "assumptions_used": ["worst_case_transport_ignorance", *pid.assumptions_used],
            "display_label": "Worst-case transport ignorance bounds",
        }
    )


def _component_bounds(
    data: Mapping[str, Any] | None,
    *,
    constraints: Mapping[str, Any] | None,
) -> PartialIdentificationResult | None:
    arrays = _extract_arrays(data)
    if arrays is None:
        return None
    outcome, treatment = arrays
    return auto_bounds(
        outcome=outcome,
        treatment=treatment,
        constraints=constraints,
    )


def _convex_relaxation(
    informative: PartialIdentificationResult,
    ignorance: PartialIdentificationResult,
    *,
    informative_weight: float,
) -> tuple[float, float]:
    w = float(np.clip(informative_weight, 0.0, 1.0))
    lower = w * informative.lower_bound + (1.0 - w) * ignorance.lower_bound
    upper = w * informative.upper_bound + (1.0 - w) * ignorance.upper_bound
    return float(lower), float(upper)


def _intersect_or_envelope(
    base_interval: tuple[float, float],
    other: PartialIdentificationResult | None,
) -> tuple[tuple[float, float], bool]:
    if other is None:
        return base_interval, False
    lower = max(base_interval[0], other.lower_bound)
    upper = min(base_interval[1], other.upper_bound)
    if lower <= upper:
        return (float(lower), float(upper)), False
    return (
        (
            float(min(base_interval[0], other.lower_bound)),
            float(max(base_interval[1], other.upper_bound)),
        ),
        True,
    )


def _combine_methods(*results: PartialIdentificationResult | None) -> str:
    labels = []
    for idx, result in enumerate(results):
        if result is None:
            continue
        labels.append(f"p{idx + 1}:{result.discretization_method or result.method.value}")
    return "|".join(labels) if labels else "transport_relaxation"


def transport_bounds(
    *,
    selection_diagram: SelectionDiagram,
    data_source: Mapping[str, Any] | None = None,
    data_target: Mapping[str, Any] | None = None,
    constraints: Mapping[str, Any] | None = None,
) -> PartialIdentificationResult:
    """Selection-aware transport bounds built from valid partial-ID components.

    This routine deliberately avoids claiming an exact transport formula unless
    the selection diagram is fully resolved and every underlying component bound
    is itself exact.  With unresolved S-nodes it returns a convex relaxation
    between source-domain bounds and worst-case target ignorance, optionally
    intersected with target-domain partial identification when target data exist.
    """

    resolved = _resolved_count(selection_diagram, constraints)
    total_s = len(selection_diagram.s_nodes)
    unresolved = max(total_s - resolved, 0)
    informative_weight = 1.0 if total_s == 0 else float(resolved) / float(total_s)

    source_pid = _component_bounds(data_source, constraints=constraints)
    target_pid = _component_bounds(data_target, constraints=constraints)
    ignorance_pid = _manski_like_pid(data_target if data_target is not None else data_source)

    if source_pid is not None:
        relaxed_interval = _convex_relaxation(
            source_pid,
            ignorance_pid,
            informative_weight=informative_weight,
        )
    elif target_pid is not None:
        relaxed_interval = (target_pid.lower_bound, target_pid.upper_bound)
    else:
        relaxed_interval = (ignorance_pid.lower_bound, ignorance_pid.upper_bound)

    combined_interval, inconsistent_components = _intersect_or_envelope(
        relaxed_interval, target_pid
    )
    lower, upper = combined_interval

    assumptions_used = [
        "selection_diagram_constraints",
        "transport_selection_relaxation",
        f"resolved_s_nodes={resolved}/{total_s}" if total_s else "resolved_s_nodes=0/0",
    ]
    if source_pid is not None:
        assumptions_used.append("source_partial_identification")
    if target_pid is not None:
        assumptions_used.append("target_partial_identification")
    if unresolved:
        assumptions_used.append("unresolved_selection_bias")
    if inconsistent_components:
        assumptions_used.append("non_nested_component_bounds")

    component_results = [result for result in (source_pid, target_pid) if result is not None]
    if informative_weight < 1.0 or not component_results:
        component_results.append(ignorance_pid)
    all_sharp = bool(component_results) and all(
        result.bounds_type == "sharp_lp" for result in component_results
    )
    exact_transport = unresolved == 0 and all_sharp and not inconsistent_components

    relaxation_gap_candidates = [
        result.relaxation_gap for result in component_results if result.relaxation_gap is not None
    ]
    ignorance_width = ignorance_pid.bound_width
    final_width = upper - lower
    if exact_transport:
        relaxation_gap = 0.0
    else:
        relaxation_gap = float(
            max([0.0, ignorance_width - final_width, *relaxation_gap_candidates])
        )

    min_conf = min((result.confidence for result in component_results), default=0.05)
    if exact_transport:
        confidence = min(0.95, max(0.75, min_conf))
    elif unresolved == 0:
        confidence = max(0.35, min(0.8, min_conf))
    else:
        confidence = max(0.15, min(0.65, min_conf * max(informative_weight, 0.5)))

    return PartialIdentificationResult(
        method=BoundMethod.TRANSPORT_BOUNDS,
        lower_bound=lower,
        upper_bound=upper,
        confidence=float(confidence),
        assumptions_used=assumptions_used,
        display_label="Selection-aware transport bounds",
        bounds_type="sharp_lp" if exact_transport else "relaxed_polynomial",
        relaxation_gap=relaxation_gap,
        discretization_method=_combine_methods(source_pid, target_pid, ignorance_pid),
        n_bins_final=max(
            (result.n_bins_final or 0 for result in component_results),
            default=None,
        )
        or None,
        discretization_converged=(
            None
            if not component_results
            else all(result.discretization_converged is not False for result in component_results)
        ),
        n_refinement_steps=sum(result.n_refinement_steps for result in component_results),
    )


__all__ = ["transport_bounds"]
