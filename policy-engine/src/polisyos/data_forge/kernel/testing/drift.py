"""Distribution drift helpers for Data Forge migration gates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel

if TYPE_CHECKING:
    from collections.abc import Mapping


class DriftThreshold(DataForgeModel):
    """Allowed numeric drift for one metric."""

    metric: str = Field(min_length=1)
    max_absolute_delta: float = Field(ge=0)
    max_relative_delta: float | None = Field(default=None, ge=0)


class DriftMetric(DataForgeModel):
    """Observed drift for one numeric metric."""

    metric: str = Field(min_length=1)
    baseline: float
    candidate: float
    absolute_delta: float = Field(ge=0)
    relative_delta: float | None = Field(default=None, ge=0)
    threshold: DriftThreshold
    passed: bool


class DomainDriftReport(DataForgeModel):
    """Drift report for one Data Forge domain."""

    domain: str = Field(pattern=r"^(academic|catalog|legal|ukraine)$")
    metrics: tuple[DriftMetric, ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        """Return whether every compared metric is within threshold."""
        return not self.warnings and all(metric.passed for metric in self.metrics)

    def metric_by_name(self, metric_name: str) -> DriftMetric:
        """Return one metric by name."""
        for metric in self.metrics:
            if metric.metric == metric_name:
                return metric
        raise KeyError(metric_name)


def compare_domain_metrics(
    *,
    domain: str,
    baseline: Mapping[str, float | int],
    candidate: Mapping[str, float | int],
    thresholds: Mapping[str, DriftThreshold | float | int],
    required_metrics: tuple[str, ...] = (),
) -> DomainDriftReport:
    """Compare domain metrics against absolute or explicit drift thresholds."""
    warnings: list[str] = []
    metrics: list[DriftMetric] = []
    metric_names = sorted(
        (set(baseline) & set(candidate)) | set(thresholds) | set(required_metrics)
    )

    for metric_name in metric_names:
        if metric_name not in baseline:
            warnings.append(f"baseline metric missing: {metric_name}")
            continue
        if metric_name not in candidate:
            warnings.append(f"candidate metric missing: {metric_name}")
            continue

        threshold = _threshold(metric_name, thresholds.get(metric_name, 0.0))
        baseline_value = float(baseline[metric_name])
        candidate_value = float(candidate[metric_name])
        absolute_delta = abs(candidate_value - baseline_value)
        relative_delta = absolute_delta / abs(baseline_value) if baseline_value != 0.0 else None
        relative_passed = (
            True
            if threshold.max_relative_delta is None or relative_delta is None
            else relative_delta <= threshold.max_relative_delta
        )
        metrics.append(
            DriftMetric(
                metric=metric_name,
                baseline=baseline_value,
                candidate=candidate_value,
                absolute_delta=absolute_delta,
                relative_delta=relative_delta,
                threshold=threshold,
                passed=absolute_delta <= threshold.max_absolute_delta and relative_passed,
            )
        )

    return DomainDriftReport(domain=domain, metrics=tuple(metrics), warnings=tuple(warnings))


def compare_domain_drift_suite(
    suites: Mapping[str, tuple[Mapping[str, float | int], Mapping[str, float | int]]],
    *,
    thresholds: Mapping[str, Mapping[str, DriftThreshold | float | int]],
) -> tuple[DomainDriftReport, ...]:
    """Run drift checks for multiple Data Forge domains."""
    return tuple(
        compare_domain_metrics(
            domain=domain,
            baseline=baseline,
            candidate=candidate,
            thresholds=thresholds.get(domain, {}),
        )
        for domain, (baseline, candidate) in sorted(suites.items())
    )


def _threshold(metric_name: str, threshold: DriftThreshold | float | int) -> DriftThreshold:
    if isinstance(threshold, DriftThreshold):
        return threshold
    return DriftThreshold(metric=metric_name, max_absolute_delta=float(threshold))


__all__ = [
    "DomainDriftReport",
    "DriftMetric",
    "DriftThreshold",
    "compare_domain_drift_suite",
    "compare_domain_metrics",
]
