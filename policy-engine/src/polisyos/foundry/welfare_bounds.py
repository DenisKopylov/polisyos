"""Mechanism welfare-loss sidecars relative to planner first-best benchmarks."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.foundry import (
    ObservedRange,
    ObservedRangeBundle,
    ObservedRangeBundleRef,
    WelfareBoundReport,
    WelfareBoundReportRef,
)

_SUPPORTED_MECHANISMS = frozenset({"income_tax", "tax_subsidy", "labor_market"})
_REQUIRED_OBSERVABLES: dict[str, tuple[str, ...]] = {
    "income_tax": ("income_tax.eti_effective",),
    "tax_subsidy": (
        "tax_subsidy.first_best_transfer",
        "tax_subsidy.curvature",
    ),
    "labor_market": (),
}


def persist_observed_range_bundle(
    store: FileSystemCAS,
    bundle: ObservedRangeBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> ObservedRangeBundleRef:
    """Persist an observed/calibrated range bundle."""
    artifact = store.put_json(
        bundle,
        PutOptions(
            kind="foundry.observed_range_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.ObservedRangeBundle", version=bundle.schema_version
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ObservedRangeBundleRef.model_validate(artifact.model_dump())


def load_observed_range_bundle(
    store: FileSystemCAS,
    ref: ArtifactRef | ObservedRangeBundleRef,
) -> ObservedRangeBundle:
    """Load an observed/calibrated range bundle."""
    return ObservedRangeBundle.model_validate(
        from_canonical_bytes(store.get_bytes(ref.artifact_id))
    )


def persist_welfare_bound_report(
    store: FileSystemCAS,
    report: WelfareBoundReport,
    *,
    inputs: list[InputRef] | None = None,
) -> WelfareBoundReportRef:
    """Persist a mechanism-level welfare-bound report."""
    artifact = store.put_json(
        report,
        PutOptions(
            kind="foundry.welfare_bound_report",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.WelfareBoundReport", version=report.schema_version
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return WelfareBoundReportRef.model_validate(artifact.model_dump())


def load_welfare_bound_report(
    store: FileSystemCAS,
    ref: ArtifactRef | WelfareBoundReportRef,
) -> WelfareBoundReport:
    """Load a persisted welfare-bound report."""
    return WelfareBoundReport.model_validate(from_canonical_bytes(store.get_bytes(ref.artifact_id)))


def safe_compute_mechanism_welfare_bound_report(
    mechanism_type: str,
    mechanism: Any,
    state_before: Any,
    observed_ranges: ObservedRangeBundle | None,
    state_after: Any | None = None,
    *,
    node_id: str | None = None,
    target_mask: Any = None,
    mode: str = "ex_ante",
) -> WelfareBoundReport | None:
    """Compute a welfare-bound report without letting sidecar failures abort execution."""
    if mechanism_type not in _SUPPORTED_MECHANISMS:
        return None
    try:
        return compute_mechanism_welfare_bound_report(
            mechanism_type,
            mechanism,
            state_before,
            observed_ranges,
            state_after=state_after,
            node_id=node_id,
            target_mask=target_mask,
            mode=mode,
        )
    except Exception as exc:  # pragma: no cover - defensive envelope
        return WelfareBoundReport(
            mechanism_type=mechanism_type,
            node_id=node_id,
            mode=_coerce_mode(mode),
            required_observables=_REQUIRED_OBSERVABLES.get(mechanism_type, ()),
            status="warning",
            notes=[
                "welfare_bound_provider_error",
                f"{type(exc).__name__}: {exc}",
            ],
        )


def compute_mechanism_welfare_bound_report(
    mechanism_type: str,
    mechanism: Any,
    state_before: Any,
    observed_ranges: ObservedRangeBundle | None,
    state_after: Any | None = None,
    *,
    node_id: str | None = None,
    target_mask: Any = None,
    mode: str = "ex_ante",
) -> WelfareBoundReport | None:
    """Compute a mechanism-family-specific welfare-loss report."""
    normalized_mode = _coerce_mode(mode)
    if mechanism_type == "labor_market":
        return _compute_labor_market_report(
            mechanism,
            state_before,
            state_after=state_after,
            node_id=node_id,
            target_mask=target_mask,
            mode=normalized_mode,
        )
    if mechanism_type == "income_tax":
        return _compute_income_tax_report(
            mechanism,
            state_before,
            observed_ranges,
            node_id=node_id,
            target_mask=target_mask,
            mode=normalized_mode,
        )
    if mechanism_type == "tax_subsidy":
        return _compute_tax_subsidy_report(
            mechanism,
            state_before,
            observed_ranges,
            node_id=node_id,
            target_mask=target_mask,
            mode=normalized_mode,
        )
    return None


def _compute_labor_market_report(
    mechanism: Any,
    state_before: Any,
    state_after: Any | None,
    *,
    node_id: str | None,
    target_mask: Any,
    mode: str,
) -> WelfareBoundReport:
    report = _base_report("labor_market", node_id=node_id, mode=mode)
    wages = np.asarray(state_before.firms.wage_offer, dtype=np.float64)
    if wages.size == 0:
        return report.model_copy(
            update={
                "status": "invalid_input",
                "notes": ["labor_market_missing_firms"],
            }
        )

    effective_mask = _effective_agent_mask(state_before, target_mask)
    skills = np.asarray(state_before.agents.skill_level, dtype=np.float64)
    total_skill = float(np.sum(skills[effective_mask]))
    threshold = _coerce_probability(getattr(mechanism, "employment_threshold", 0.5))
    if threshold is None:
        return report.model_copy(
            update={
                "status": "invalid_input",
                "notes": ["labor_market_invalid_threshold"],
            }
        )

    wage_max = float(np.max(wages))
    wage_mean = float(np.mean(wages))
    ex_ante_mechanism_value = total_skill * threshold * wage_mean
    ex_ante_first_best = total_skill * wage_max
    ex_ante_welfare_loss = max(0.0, ex_ante_first_best - ex_ante_mechanism_value)

    if mode == "ex_ante":
        return report.model_copy(
            update={
                "status": "ok",
                "mechanism_value": ex_ante_mechanism_value,
                "welfare_loss_lower": ex_ante_welfare_loss,
                "welfare_loss_upper": ex_ante_welfare_loss,
                "first_best_lower": ex_ante_first_best,
                "first_best_upper": ex_ante_first_best,
                "notes": [
                    "exact_ex_ante_bound",
                    "benchmark:planner_assignment_without_capacities",
                ],
            }
        )

    if state_after is None:
        return report.model_copy(
            update={
                "status": "warning",
                "mechanism_value": ex_ante_mechanism_value,
                "welfare_loss_lower": ex_ante_welfare_loss,
                "welfare_loss_upper": ex_ante_welfare_loss,
                "first_best_lower": ex_ante_first_best,
                "first_best_upper": ex_ante_first_best,
                "notes": [
                    "ex_post_state_unavailable",
                    "returned_ex_ante_bound",
                    "benchmark:planner_assignment_without_capacities",
                ],
            }
        )

    income_after = np.asarray(state_after.agents.income, dtype=np.float64)
    if income_after.shape != skills.shape:
        return report.model_copy(
            update={
                "status": "invalid_input",
                "notes": ["labor_market_state_after_income_shape_mismatch"],
            }
        )

    ex_post_mechanism_value = float(np.sum(income_after[effective_mask]))
    ex_post_first_best = ex_ante_first_best
    ex_post_welfare_loss = max(0.0, ex_post_first_best - ex_post_mechanism_value)
    notes = [
        "exact_ex_post_bound",
        "benchmark:planner_assignment_without_capacities",
    ]
    if mode == "both":
        notes.extend(
            [
                f"ex_ante_mechanism_value:{ex_ante_mechanism_value}",
                f"ex_ante_welfare_loss:{ex_ante_welfare_loss}",
            ]
        )
    return report.model_copy(
        update={
            "status": "ok",
            "mechanism_value": ex_post_mechanism_value,
            "welfare_loss_lower": ex_post_welfare_loss,
            "welfare_loss_upper": ex_post_welfare_loss,
            "first_best_lower": ex_post_first_best,
            "first_best_upper": ex_post_first_best,
            "notes": notes,
        }
    )


def _compute_income_tax_report(
    mechanism: Any,
    state_before: Any,
    observed_ranges: ObservedRangeBundle | None,
    *,
    node_id: str | None,
    target_mask: Any,
    mode: str,
) -> WelfareBoundReport:
    report = _base_report("income_tax", node_id=node_id, mode=mode)
    rate = _coerce_rate(getattr(mechanism, "rate", None))
    if rate is None or rate < 0.0 or rate >= 1.0:
        return report.model_copy(
            update={
                "status": "invalid_input",
                "notes": ["income_tax_rate_must_lie_in_[0,1)"],
            }
        )

    effective_mask = _effective_agent_mask(state_before, target_mask)
    agent_count = int(np.asarray(effective_mask).shape[0])
    reported_income = np.asarray(state_before.agents.reported_income, dtype=np.float64)
    if reported_income.shape[0] != agent_count:
        return report.model_copy(
            update={
                "status": "invalid_input",
                "notes": ["income_tax_reported_income_shape_mismatch"],
            }
        )

    eti_range = _get_range(observed_ranges, "income_tax.eti_effective")
    if eti_range is None:
        return report.model_copy(
            update={
                "status": "insufficient_observables",
                "notes": ["missing_observable:income_tax.eti_effective"],
            }
        )

    phi = -math.log1p(-rate) - rate
    aggregate_taxable_range = _get_range(
        observed_ranges,
        "income_tax.aggregate_taxable_income",
        "income_tax.aggregate_reported_income",
    )
    if aggregate_taxable_range is not None:
        eti_scalar_lower, eti_scalar_upper = _coerce_scalar_interval(eti_range)
        tax_scalar_lower, tax_scalar_upper = _coerce_scalar_interval(aggregate_taxable_range)
        if (
            eti_scalar_lower is None
            or eti_scalar_upper is None
            or tax_scalar_lower is None
            or tax_scalar_upper is None
        ):
            return report.model_copy(
                update={
                    "status": "invalid_input",
                    "notes": ["income_tax_aggregate_range_requires_scalar_bounds"],
                }
            )
        lower = phi * eti_scalar_lower * tax_scalar_lower
        upper = phi * eti_scalar_upper * tax_scalar_upper
        status = "ok" if mode == "ex_ante" else "warning"
        notes = [
            "eti_envelope_bound",
            "aggregate_taxable_income_path",
            "benchmark:lump_sum_first_best_with_equal_revenue",
        ]
        if mode != "ex_ante":
            notes.extend(["ex_post_not_supported_for_family", "returned_ex_ante_envelope"])
        return report.model_copy(
            update={
                "status": status,
                "welfare_loss_lower": lower,
                "welfare_loss_upper": upper,
                "notes": notes,
            }
        )

    taxable_range = _get_range(
        observed_ranges,
        "income_tax.taxable_income",
        "income_tax.reported_income",
    )
    if taxable_range is None:
        z_lower = reported_income
        z_upper = reported_income
    else:
        z_lower, z_upper = _materialize_range(
            taxable_range,
            size=agent_count,
            broadcast_scalar=True,
        )
        if z_lower is None or z_upper is None:
            return report.model_copy(
                update={
                    "status": "invalid_input",
                    "notes": ["income_tax_taxable_income_range_shape_mismatch"],
                }
            )

    eti_lower, eti_upper = _materialize_range(
        eti_range,
        size=agent_count,
        broadcast_scalar=True,
    )
    if eti_lower is None or eti_upper is None:
        return report.model_copy(
            update={
                "status": "invalid_input",
                "notes": ["income_tax_eti_range_shape_mismatch"],
            }
        )
    if np.any(~np.isfinite(eti_lower)) or np.any(~np.isfinite(eti_upper)):
        return report.model_copy(
            update={
                "status": "invalid_input",
                "notes": ["income_tax_eti_range_non_finite"],
            }
        )
    if np.any(eti_upper < eti_lower):
        return report.model_copy(
            update={
                "status": "invalid_input",
                "notes": ["income_tax_eti_range_inverted"],
            }
        )

    lower = phi * float(np.sum((eti_lower * z_lower)[effective_mask]))
    upper = phi * float(np.sum((eti_upper * z_upper)[effective_mask]))
    status = "ok" if mode == "ex_ante" else "warning"
    notes = [
        "eti_envelope_bound",
        "benchmark:lump_sum_first_best_with_equal_revenue",
    ]
    if mode != "ex_ante":
        notes.extend(["ex_post_not_supported_for_family", "returned_ex_ante_envelope"])
    return report.model_copy(
        update={
            "status": status,
            "welfare_loss_lower": lower,
            "welfare_loss_upper": upper,
            "notes": notes,
        }
    )


def _compute_tax_subsidy_report(
    mechanism: Any,
    state_before: Any,
    observed_ranges: ObservedRangeBundle | None,
    *,
    node_id: str | None,
    target_mask: Any,
    mode: str,
) -> WelfareBoundReport:
    report = _base_report("tax_subsidy", node_id=node_id, mode=mode)
    xstar_range = _get_range(observed_ranges, "tax_subsidy.first_best_transfer")
    curvature_range = _get_range(observed_ranges, "tax_subsidy.curvature")
    if xstar_range is None or curvature_range is None:
        missing = []
        if xstar_range is None:
            missing.append("missing_observable:tax_subsidy.first_best_transfer")
        if curvature_range is None:
            missing.append("missing_observable:tax_subsidy.curvature")
        return report.model_copy(
            update={
                "status": "insufficient_observables",
                "notes": missing,
            }
        )

    effective_mask = _effective_agent_mask(state_before, target_mask)
    income = np.asarray(state_before.agents.income, dtype=np.float64)
    rate = _coerce_rate(getattr(mechanism, "rate", None))
    if rate is None:
        return report.model_copy(
            update={
                "status": "invalid_input",
                "notes": ["tax_subsidy_invalid_rate"],
            }
        )

    transfers = income * rate
    agent_count = int(income.shape[0])
    xstar_lower, xstar_upper = _materialize_range(
        xstar_range,
        size=agent_count,
        broadcast_scalar=True,
    )
    curvature_lower, curvature_upper = _materialize_range(
        curvature_range,
        size=agent_count,
        broadcast_scalar=True,
    )
    if (
        xstar_lower is None
        or xstar_upper is None
        or curvature_lower is None
        or curvature_upper is None
    ):
        return report.model_copy(
            update={
                "status": "invalid_input",
                "notes": ["tax_subsidy_range_shape_mismatch"],
            }
        )
    if np.any(xstar_upper < xstar_lower):
        return report.model_copy(
            update={
                "status": "invalid_input",
                "notes": ["tax_subsidy_first_best_transfer_range_inverted"],
            }
        )
    if (
        np.any(curvature_lower <= 0.0)
        or np.any(curvature_upper <= 0.0)
        or np.any(curvature_upper < curvature_lower)
    ):
        return report.model_copy(
            update={
                "status": "invalid_input",
                "notes": ["tax_subsidy_curvature_range_invalid"],
            }
        )

    active_transfers = transfers[effective_mask]
    active_xstar_lower = xstar_lower[effective_mask]
    active_xstar_upper = xstar_upper[effective_mask]
    active_curvature_lower = curvature_lower[effective_mask]
    active_curvature_upper = curvature_upper[effective_mask]
    dist_lower = np.where(
        active_transfers < active_xstar_lower,
        active_xstar_lower - active_transfers,
        np.where(active_transfers > active_xstar_upper, active_transfers - active_xstar_upper, 0.0),
    )
    dist_upper = np.maximum(
        np.abs(active_transfers - active_xstar_lower),
        np.abs(active_transfers - active_xstar_upper),
    )
    lower = 0.5 * float(np.sum(active_curvature_lower * np.square(dist_lower)))
    upper = 0.5 * float(np.sum(active_curvature_upper * np.square(dist_upper)))
    status = "ok" if mode == "ex_ante" else "warning"
    notes = [
        "curvature_envelope_bound",
        "benchmark:personalized_transfer_first_best_with_equal_budget",
    ]
    if mode != "ex_ante":
        notes.extend(["ex_post_not_supported_for_family", "returned_ex_ante_envelope"])
    return report.model_copy(
        update={
            "status": status,
            "welfare_loss_lower": lower,
            "welfare_loss_upper": upper,
            "notes": notes,
        }
    )


def _base_report(mechanism_type: str, *, node_id: str | None, mode: str) -> WelfareBoundReport:
    return WelfareBoundReport(
        mechanism_type=mechanism_type,
        node_id=node_id,
        mode=mode,
        required_observables=_REQUIRED_OBSERVABLES.get(mechanism_type, ()),
    )


def _coerce_mode(value: str) -> str:
    if value in {"ex_ante", "ex_post", "both"}:
        return value
    return "ex_ante"


def _get_range(
    bundle: ObservedRangeBundle | None,
    *names: str,
) -> ObservedRange | None:
    if bundle is None:
        return None
    for name in names:
        item = bundle.ranges.get(name)
        if item is not None:
            return item
    return None


def _effective_agent_mask(state_before: Any, target_mask: Any) -> np.ndarray:
    active = getattr(state_before.agents, "active", None)
    if active is None:
        base = np.ones(int(np.asarray(state_before.agents.income).shape[0]), dtype=bool)
    else:
        base = np.asarray(active, dtype=bool)
    if target_mask is None:
        return base
    target = np.asarray(target_mask, dtype=bool)
    if target.shape != base.shape:
        raise ValueError("target mask shape mismatch")
    return base & target


def _coerce_probability(value: Any) -> float | None:
    if value is None:
        return None
    numeric = np.asarray(value, dtype=np.float64)
    if numeric.size != 1 or not np.isfinite(numeric).all():
        return None
    return float(np.clip(numeric.reshape(()), 0.0, 1.0))


def _coerce_rate(value: Any) -> float | None:
    if value is None:
        return None
    numeric = np.asarray(value, dtype=np.float64)
    if numeric.size != 1 or not np.isfinite(numeric).all():
        return None
    return float(numeric.reshape(()))


def _materialize_range(
    observed_range: ObservedRange,
    *,
    size: int,
    broadcast_scalar: bool,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    lower = _materialize_values(observed_range.lower, size=size, broadcast_scalar=broadcast_scalar)
    upper = _materialize_values(observed_range.upper, size=size, broadcast_scalar=broadcast_scalar)
    return lower, upper


def _materialize_values(
    payload: float | list[float] | None,
    *,
    size: int,
    broadcast_scalar: bool,
) -> np.ndarray | None:
    if payload is None:
        return None
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        array = np.asarray(payload, dtype=np.float64)
        if array.shape != (size,):
            return None
        return array
    scalar = float(payload)
    if not broadcast_scalar and size != 1:
        return None
    return np.full((size,), scalar, dtype=np.float64)


def _coerce_scalar_interval(
    observed_range: ObservedRange,
) -> tuple[float | None, float | None]:
    lower = _coerce_optional_scalar(observed_range.lower)
    upper = _coerce_optional_scalar(observed_range.upper)
    if lower is None or upper is None:
        return None, None
    if not math.isfinite(lower) or not math.isfinite(upper) or upper < lower:
        return None, None
    return lower, upper


def _coerce_optional_scalar(value: float | list[float] | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return None
    return float(value)


__all__ = [
    "compute_mechanism_welfare_bound_report",
    "load_observed_range_bundle",
    "load_welfare_bound_report",
    "persist_observed_range_bundle",
    "persist_welfare_bound_report",
    "safe_compute_mechanism_welfare_bound_report",
]
