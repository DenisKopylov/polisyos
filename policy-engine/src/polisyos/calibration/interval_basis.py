"""Internal reconciliation of a scenario's declared interval evidence.

This numerical completeness check supplies no scientific or Runtime authority.
Point-only reports remain point-only; conditional coverage is descriptive when
the requested interval roster is incomplete or its projections contradict rows.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

from polisyos.ir.analytics.backtest import BacktestScenario


def _read_interval(value: object) -> tuple[tuple[float, float] | None, str | None]:
    """Read a finite ordered numeric pair without repairing its contents."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None, "invalid_interval_shape"
    if any(isinstance(bound, bool) or not isinstance(bound, numbers.Real) for bound in value):
        return None, "non_numeric_interval"
    try:
        lower, upper = float(value[0]), float(value[1])
    except (TypeError, ValueError, OverflowError):
        return None, "non_finite_interval"
    if not math.isfinite(lower) or not math.isfinite(upper):
        return None, "non_finite_interval"
    if lower > upper:
        return None, "reversed_interval"
    return (lower, upper), None


@dataclass(frozen=True)
class _IntervalBasis:
    requested: bool
    requested_count: int
    evaluated_count: int
    hit_count: int
    issues: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.issues


def _reconcile_interval_basis(scenario: BacktestScenario) -> _IntervalBasis:
    """Derive completeness from actual bounds, observations and typed counts.

    An absent metadata marker does not invalidate a reconcilable legacy report.
    A positive marker never overrides a missing row, a wrong count or a retained
    producer limitation (including extra metric/time axes not present in rows).
    """
    rows = scenario.outcome_comparisons
    admission = scenario.metadata.get("interval_admission")
    requested = bool(
        scenario.interval_requested_count
        or scenario.interval_available_count
        or scenario.interval_evaluated_count
        or scenario.interval_hit_count
        or scenario.interval_availability is not None
        or scenario.interval_hit_rate is not None
        or scenario.coverage_probability is not None
        or any(
            row.ci_lower is not None or row.ci_upper is not None or row.within_ci is not None
            for row in rows
        )
        or admission is not None
    )
    if not requested:
        return _IntervalBasis(False, 0, 0, 0, ())

    issues: list[str] = []
    expected = max(scenario.interval_requested_count, scenario.requested_count, len(rows))
    if expected == 0 or scenario.interval_requested_count != expected:
        issues.append("interval_requested_roster_mismatch")
    if len(rows) != expected:
        issues.append("interval_point_roster_incomplete")
    if scenario.requested_count and scenario.compared_count != len(rows):
        issues.append("interval_point_projection_mismatch")

    evaluated = 0
    hits = 0
    for row in rows:
        bounds, reason = _read_interval((row.ci_lower, row.ci_upper))
        if bounds is None:
            issues.append("interval_bounds_unavailable:" + str(reason))
            continue
        evaluated += 1
        hit = bounds[0] <= row.y_true <= bounds[1]
        hits += int(hit)
        if row.within_ci is not hit:
            issues.append("interval_hit_projection_mismatch")

    if evaluated != expected:
        issues.append("interval_evaluated_roster_incomplete")
    if scenario.interval_available_count != evaluated:
        issues.append("interval_available_projection_mismatch")
    if scenario.interval_evaluated_count != evaluated:
        issues.append("interval_evaluated_projection_mismatch")
    if scenario.interval_hit_count != hits:
        issues.append("interval_hits_projection_mismatch")
    availability = evaluated / expected if expected else None
    rate = hits / evaluated if evaluated else None
    for actual, derived in (
        (scenario.interval_availability, availability),
        (scenario.interval_hit_rate, rate),
    ):
        if actual != derived:
            issues.append("interval_rate_projection_mismatch")
    # Legacy interval_hit_rate is the measured projection; the optional
    # coverage alias need not exist, but it cannot contradict actual rows.
    if scenario.coverage_probability is not None and scenario.coverage_probability != rate:
        issues.append("interval_rate_projection_mismatch")

    if isinstance(admission, dict):
        if (
            admission.get("status") == "limited"
            or admission.get("limitations")
            or admission.get("reconciled_issues")
        ):
            issues.append("producer_interval_limitations")
        if (
            admission.get("requested_count", expected) != expected
            or admission.get("evaluated_count", evaluated) != evaluated
        ):
            issues.append("interval_metadata_projection_mismatch")
    elif admission is not None:
        issues.append("interval_metadata_malformed")
    return _IntervalBasis(requested, expected, evaluated, hits, tuple(dict.fromkeys(issues)))


__all__: list[str] = []
