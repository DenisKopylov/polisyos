"""Build policy-level diffs between two runtime runs."""

from __future__ import annotations

from math import isfinite
from typing import TYPE_CHECKING

from polisyos.core.contracts.runtime import (
    ComparabilityReport,
    CompareCandidate,
    CompareCandidateRelation,
    ComparisonFrame,
    DeltaDistribution,
    DeltaQuantity,
    LineageCompactSummaryItem,
    LineageDelta,
    LineageRef,
    QuantityUncertainty,
    QuantityValue,
    TemporalRef,
    TemporalScope,
    UnitRef,
)

if TYPE_CHECKING:
    from datetime import datetime

    from polisyos.runtime.http.services.lineage import LineageService
    from polisyos.runtime.http.services.run_index import IndexedRunRecord
    from polisyos.runtime.http.services.temporal import TemporalService


class CompareService:
    """Normalize quantities, run comparability checks, and compute typed deltas."""

    def __init__(
        self,
        *,
        lineage_service: LineageService,
        temporal_service: TemporalService,
    ) -> None:
        self._lineage = lineage_service
        self._temporal = temporal_service

    def build_compare(
        self,
        *,
        run_a: IndexedRunRecord,
        run_b: IndexedRunRecord,
        temporal_scope: TemporalScope | None,
    ) -> tuple[ComparisonFrame, ComparabilityReport, list[DeltaQuantity]]:
        """Return a comparison frame, report, and quantity-law deltas."""
        quantities_a = self._decision_quantities(run_a, temporal_scope)
        quantities_b = self._decision_quantities(run_b, temporal_scope)
        by_metric_a = _quantity_map(quantities_a)
        by_metric_b = _quantity_map(quantities_b)
        common_metric_ids = sorted(set(by_metric_a).intersection(by_metric_b))

        report = _comparability_report(
            run_a=run_a,
            run_b=run_b,
            metric_ids=common_metric_ids,
            by_metric_a=by_metric_a,
            by_metric_b=by_metric_b,
        )
        frame = ComparisonFrame(
            run_a=run_a.run_id,
            run_b=run_b.run_id,
            metric_set=common_metric_ids,
            population=_population_label(run_a, run_b),
            unit_policy="canonical",
            temporal_scope=temporal_scope,
            scenario_scope=_scenario_scope(temporal_scope),
            assumption_set=_assumption_set(run_a, run_b),
        )
        if report.status == "blocked":
            return frame, report, []

        deltas = [
            _delta_for_metric(
                metric_id=metric_id,
                a=by_metric_a[metric_id],
                b=by_metric_b[metric_id],
                temporal_scope=temporal_scope,
            )
            for metric_id in common_metric_ids
            if _units_compatible(by_metric_a[metric_id], by_metric_b[metric_id])
        ]
        deltas.sort(key=lambda item: (-item.decision_salience, item.metric_id))
        return frame, report, deltas

    def candidate_for(
        self,
        *,
        run: IndexedRunRecord,
        candidate: IndexedRunRecord,
        temporal_scope: TemporalScope | None,
        relation: CompareCandidateRelation | None = None,
    ) -> CompareCandidate:
        """Return one comparator candidate with pre-flight comparability."""
        frame, report, deltas = self.build_compare(
            run_a=run,
            run_b=candidate,
            temporal_scope=temporal_scope,
        )
        return CompareCandidate(
            run_id=candidate.run_id,
            label=_candidate_label(candidate, frame=frame, delta_count=len(deltas)),
            relation=relation or self.relation_for(run=run, candidate=candidate),
            status=candidate.details.status,
            started_at=candidate.details.started_at,
            finished_at=candidate.details.finished_at,
            comparability=report,
        )

    def relation_for(
        self,
        *,
        run: IndexedRunRecord,
        candidate: IndexedRunRecord,
    ) -> CompareCandidateRelation:
        """Classify why a candidate is a useful comparator."""
        if _looks_like_baseline(candidate):
            return "baseline"
        if _started_before(candidate, run):
            return "previous"
        return "recommended"

    def _decision_quantities(
        self,
        run: IndexedRunRecord,
        temporal_scope: TemporalScope | None,
    ) -> list[QuantityValue]:
        quantities, _coverage, entries = self._lineage.build_quantity_inventory_for_run(run)
        projected, _projected_coverage, _projected_entries = self._temporal.project_quantities(
            quantities,
            entries,
            temporal_scope,
        )
        return [quantity for quantity in projected if quantity.quantity_class == "decision"]


def _quantity_map(quantities: list[QuantityValue]) -> dict[str, QuantityValue]:
    by_metric: dict[str, QuantityValue] = {}
    for quantity in quantities:
        metric_id = quantity.metric_id or quantity.label
        if not metric_id:
            continue
        existing = by_metric.get(metric_id)
        if existing is None or _trace_rank(quantity) > _trace_rank(existing):
            by_metric[metric_id] = quantity
    return by_metric


def _trace_rank(quantity: QuantityValue) -> int:
    if quantity.lineage.status == "verified":
        return 3
    if quantity.lineage.status == "pending":
        return 2
    if quantity.lineage.status == "disputed":
        return 1
    return 0


def _comparability_report(
    *,
    run_a: IndexedRunRecord,
    run_b: IndexedRunRecord,
    metric_ids: list[str],
    by_metric_a: dict[str, QuantityValue],
    by_metric_b: dict[str, QuantityValue],
) -> ComparabilityReport:
    warnings: list[str] = []
    blocked_reasons: list[str] = []
    if run_a.run_id == run_b.run_id:
        blocked_reasons.append("same_run")
    if not metric_ids:
        blocked_reasons.append("no_overlapping_decision_metrics")

    incompatible_units = [
        metric_id
        for metric_id in metric_ids
        if not _units_compatible(by_metric_a[metric_id], by_metric_b[metric_id])
    ]
    if incompatible_units and len(incompatible_units) == len(metric_ids):
        blocked_reasons.append("no_compatible_metric_units")
    elif incompatible_units:
        warnings.append(f"incompatible_units:{','.join(incompatible_units[:5])}")

    if (
        run_a.details.cell_id
        and run_b.details.cell_id
        and run_a.details.cell_id != run_b.details.cell_id
    ):
        warnings.append("different_cell_population")
    if (
        run_a.details.execution_profile
        and run_b.details.execution_profile
        and run_a.details.execution_profile != run_b.details.execution_profile
    ):
        warnings.append("different_execution_profile")

    if blocked_reasons:
        return ComparabilityReport(
            status="blocked",
            warnings=warnings,
            blocked_reasons=blocked_reasons,
        )
    return ComparabilityReport(
        status="warning" if warnings else "compatible",
        warnings=warnings,
        blocked_reasons=[],
    )


def _units_compatible(a: QuantityValue, b: QuantityValue) -> bool:
    return a.unit.code == b.unit.code and a.unit.system == b.unit.system


def _delta_for_metric(
    *,
    metric_id: str,
    a: QuantityValue,
    b: QuantityValue,
    temporal_scope: TemporalScope | None,
) -> DeltaQuantity:
    label = b.label or a.label or metric_id
    delta_point = _numeric_delta(a.point, b.point)
    delta_absolute = (
        _delta_quantity(
            metric_id=f"{metric_id}.delta_absolute",
            label=f"{label} absolute delta",
            point=delta_point,
            unit=a.unit,
            a=a,
            b=b,
            temporal_scope=temporal_scope,
            uncertainty=_delta_uncertainty(a, b),
        )
        if delta_point is not None
        else None
    )
    relative_point = _relative_delta(a.point, b.point)
    delta_relative = (
        _delta_quantity(
            metric_id=f"{metric_id}.delta_relative",
            label=f"{label} relative delta",
            point=relative_point,
            unit=UnitRef(code="1", system="ucum", display="ratio"),
            a=a,
            b=b,
            temporal_scope=temporal_scope,
            uncertainty=None,
        )
        if relative_point is not None
        else None
    )
    distribution = _delta_distribution(a, b, delta_point)
    significance = _significance(
        metric_id=metric_id,
        delta_point=delta_point,
        distribution=distribution,
    )
    return DeltaQuantity(
        metric_id=metric_id,
        label=label,
        a=a,
        b=b,
        delta_absolute=delta_absolute,
        delta_relative=delta_relative,
        delta_distribution=distribution,
        significance=significance,
        dominance=_dominance(significance),
        decision_salience=_decision_salience(
            delta_point=delta_point,
            relative_point=relative_point,
            lineage_delta=_lineage_delta(a, b),
        ),
        lineage_delta=_lineage_delta(a, b),
    )


def _delta_quantity(
    *,
    metric_id: str,
    label: str,
    point: float,
    unit: UnitRef,
    a: QuantityValue,
    b: QuantityValue,
    temporal_scope: TemporalScope | None,
    uncertainty: QuantityUncertainty | None,
) -> QuantityValue:
    return QuantityValue(
        point=point,
        unit=unit,
        metric_id=metric_id,
        label=label,
        lineage=_delta_lineage(metric_id=metric_id, a=a, b=b),
        uncertainty=uncertainty,
        time=_temporal_ref_from_scope(temporal_scope) or b.time or a.time,
        quantity_class="decision",
    )


def _delta_lineage(*, metric_id: str, a: QuantityValue, b: QuantityValue) -> LineageRef:
    status = _combined_lineage_status(a, b)
    freshness = "stale" if "stale" in {a.lineage.freshness, b.lineage.freshness} else "current"
    kwargs = {}
    if status == "untraced":
        kwargs = {
            "reason_code": "comparison_input_untraced",
            "tracking_issue": "policyos://policy-diff/untraced-input",
        }
        freshness = "unknown"
    return LineageRef(
        id=f"compare:{metric_id}:{a.lineage.id}:{b.lineage.id}",
        status=status,
        freshness=freshness,
        summary={
            "source": "Policy diff",
            "method": "QuantityValue delta",
            "a": a.lineage.id,
            "b": b.lineage.id,
        },
        compact_summary=[
            LineageCompactSummaryItem(kind="source", label=a.label or a.metric_id or "Run A"),
            LineageCompactSummaryItem(kind="source", label=b.label or b.metric_id or "Run B"),
            LineageCompactSummaryItem(kind="transform", label="Policy diff"),
            LineageCompactSummaryItem(kind="result", label=metric_id),
        ],
        **kwargs,
    )


def _combined_lineage_status(a: QuantityValue, b: QuantityValue) -> str:
    statuses = {a.lineage.status, b.lineage.status}
    if "disputed" in statuses:
        return "disputed"
    if "untraced" in statuses:
        return "untraced"
    if "pending" in statuses:
        return "pending"
    return "verified"


def _lineage_delta(a: QuantityValue, b: QuantityValue) -> LineageDelta:
    verification_changed = None
    if a.lineage.status != b.lineage.status:
        verification_changed = f"{a.lineage.status}_to_{b.lineage.status}"
    source_changed = a.lineage.id != b.lineage.id or _summary_labels(
        a.lineage.compact_summary
    ) != _summary_labels(b.lineage.compact_summary)
    model_changed = _summary_value(a, "method") != _summary_value(b, "method")
    notes: list[str] = []
    if source_changed:
        notes.append("source_changed")
    if model_changed:
        notes.append("method_changed")
    return LineageDelta(
        source_changed=source_changed,
        model_changed=model_changed,
        hash_changed=bool(a.lineage.hash and b.lineage.hash and a.lineage.hash != b.lineage.hash),
        freshness_changed=a.lineage.freshness != b.lineage.freshness,
        verification_changed=verification_changed,
        notes=notes,
    )


def _summary_labels(items: list[LineageCompactSummaryItem]) -> tuple[str, ...]:
    return tuple(item.label for item in items)


def _summary_value(quantity: QuantityValue, key: str) -> str | None:
    return quantity.lineage.summary.get(key)


def _numeric_delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    if not (isfinite(a) and isfinite(b)):
        return None
    return b - a


def _relative_delta(a: float | None, b: float | None) -> float | None:
    delta = _numeric_delta(a, b)
    if delta is None or a in {None, 0}:
        return None
    return delta / abs(a)


def _delta_uncertainty(a: QuantityValue, b: QuantityValue) -> QuantityUncertainty | None:
    a_ci = a.uncertainty.ci_95 if a.uncertainty else None
    b_ci = b.uncertainty.ci_95 if b.uncertainty else None
    if a_ci is None and b_ci is None:
        return None
    if a_ci is not None and b_ci is not None:
        ci_95 = (b_ci[0] - a_ci[1], b_ci[1] - a_ci[0])
    else:
        ci_95 = None
    return QuantityUncertainty(
        ci_95=ci_95,
        method="analytic",
        identifiability=_combined_identifiability(a, b),
        disputed=bool(
            (a.uncertainty.disputed if a.uncertainty else False)
            or (b.uncertainty.disputed if b.uncertainty else False)
        ),
    )


def _combined_identifiability(a: QuantityValue, b: QuantityValue) -> str:
    order = {"identified": 3, "estimated": 2, "assumed": 1, "unknown": 0}
    left = a.uncertainty.identifiability if a.uncertainty else "unknown"
    right = b.uncertainty.identifiability if b.uncertainty else "unknown"
    return left if order.get(left, 0) <= order.get(right, 0) else right


def _delta_distribution(
    a: QuantityValue,
    b: QuantityValue,
    delta_point: float | None,
) -> DeltaDistribution:
    a_quantiles = a.uncertainty.quantiles if a.uncertainty else {}
    b_quantiles = b.uncertainty.quantiles if b.uncertainty else {}
    quantiles = {
        key: b_quantiles[key] - a_quantiles[key]
        for key in sorted(set(a_quantiles).intersection(b_quantiles))
    }
    a_ci = a.uncertainty.ci_95 if a.uncertainty else None
    b_ci = b.uncertainty.ci_95 if b.uncertainty else None
    return DeltaDistribution(
        quantiles=quantiles,
        mean_shift=delta_point,
        median_shift=quantiles.get("0.5") or quantiles.get("p50"),
        ci_overlap=_ci_overlap(a_ci, b_ci),
    )


def _ci_overlap(
    a_ci: tuple[float, float] | None,
    b_ci: tuple[float, float] | None,
) -> bool | None:
    if a_ci is None or b_ci is None:
        return None
    return max(a_ci[0], b_ci[0]) <= min(a_ci[1], b_ci[1])


def _significance(
    *,
    metric_id: str,
    delta_point: float | None,
    distribution: DeltaDistribution,
) -> str:
    if delta_point is None:
        return "not_comparable"
    if abs(delta_point) < 1e-9:
        return "uncertain"
    if distribution.ci_overlap is True:
        return "uncertain"
    direction = _metric_direction(metric_id)
    if direction == "unknown":
        return "mixed"
    improved = delta_point > 0 if direction == "higher_is_better" else delta_point < 0
    return "improved" if improved else "worsened"


def _metric_direction(metric_id: str) -> str:
    lowered = metric_id.lower()
    if any(
        token in lowered for token in ("cost", "budget", "risk", "blocker", "latency", "duration")
    ):
        return "lower_is_better"
    if any(
        token in lowered
        for token in ("score", "rate", "trust", "coverage", "completeness", "benefit", "effect")
    ):
        return "higher_is_better"
    return "unknown"


def _dominance(significance: str) -> str:
    if significance == "improved":
        return "b"
    if significance == "worsened":
        return "a"
    if significance == "mixed":
        return "mixed"
    if significance == "uncertain":
        return "none"
    return "unknown"


def _decision_salience(
    *,
    delta_point: float | None,
    relative_point: float | None,
    lineage_delta: LineageDelta,
) -> float:
    if delta_point is None:
        base = 0.0
    elif relative_point is not None:
        base = min(abs(relative_point), 1.0)
    else:
        base = min(abs(delta_point) / (abs(delta_point) + 1.0), 1.0)
    drift_bonus = (
        0.15
        if any(
            (
                lineage_delta.source_changed,
                lineage_delta.model_changed,
                lineage_delta.hash_changed,
                lineage_delta.freshness_changed,
                lineage_delta.verification_changed,
            )
        )
        else 0.0
    )
    return min(round(base + drift_bonus, 4), 1.0)


def _temporal_ref_from_scope(scope: TemporalScope | None) -> TemporalRef | None:
    if scope is None:
        return None
    return TemporalRef(
        valid_at=scope.valid_at,
        tx_at=scope.tx_at,
        branch=scope.branch,
        snapshot_id=scope.snapshot_id,
        scenario_id=scope.scenario_id,
    )


def _scenario_scope(scope: TemporalScope | None) -> dict[str, str]:
    if scope is None or scope.scenario_id is None:
        return {}
    return {"scenario_id": scope.scenario_id}


def _assumption_set(run_a: IndexedRunRecord, run_b: IndexedRunRecord) -> list[str]:
    assumptions = []
    for run in (run_a, run_b):
        for warning in run.details.warnings:
            if warning not in assumptions:
                assumptions.append(warning)
    return assumptions


def _population_label(run_a: IndexedRunRecord, run_b: IndexedRunRecord) -> str | None:
    if run_a.details.cell_id and run_a.details.cell_id == run_b.details.cell_id:
        return run_a.details.cell_id
    if run_a.details.tenant_id and run_a.details.tenant_id == run_b.details.tenant_id:
        return run_a.details.tenant_id
    return None


def _candidate_label(
    candidate: IndexedRunRecord,
    *,
    frame: ComparisonFrame,
    delta_count: int,
) -> str:
    started_at = _format_date(candidate.details.started_at)
    metric_text = f"{delta_count} comparable metrics" if delta_count else "no comparable metrics"
    return f"{candidate.run_id} · {candidate.details.status} · {metric_text} · {started_at}"


def _looks_like_baseline(candidate: IndexedRunRecord) -> bool:
    haystack = " ".join(
        [
            candidate.run_id,
            candidate.details.execution_profile or "",
            " ".join(candidate.details.warnings),
        ]
    ).lower()
    return "baseline" in haystack


def _started_before(candidate: IndexedRunRecord, run: IndexedRunRecord) -> bool:
    if candidate.details.started_at is None or run.details.started_at is None:
        return False
    return candidate.details.started_at < run.details.started_at


def _format_date(value: datetime | None) -> str:
    if value is None:
        return "unknown time"
    return value.isoformat()
