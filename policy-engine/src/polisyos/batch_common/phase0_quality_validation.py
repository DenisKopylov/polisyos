"""Phase-0 deterministic quality validation and consistency closure checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Phase0QualityThresholds:
    """Threshold configuration for phase-0 quality validation."""

    min_article_count: int = 50
    min_claims_count: int = 200
    min_parameters_count: int = 100
    min_canonical_claim_variable_pct: float = 80.0
    required_alignment_seed_parity_pct: float = 100.0
    min_dataset_coverage_pct: float = 60.0
    max_proxy_share_pct: float = 60.0
    max_temporal_extrapolation_share_pct: float = 30.0


@dataclass(frozen=True)
class Phase0QualityCheck:
    """One phase-0 quality check result."""

    name: str
    passed: bool
    severity: str = "critical"  # critical | warning
    value: float | int | str | None = None
    threshold: float | int | str | None = None
    message: str = ""


@dataclass
class Phase0QualityReport:
    """Aggregated phase-0 quality report."""

    checks: list[Phase0QualityCheck] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(check.passed or check.severity != "critical" for check in self.checks)

    @property
    def critical_failed(self) -> list[Phase0QualityCheck]:
        return [check for check in self.checks if check.severity == "critical" and not check.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "metrics": self.metrics,
            "checks": [
                {
                    "name": check.name,
                    "passed": check.passed,
                    "severity": check.severity,
                    "value": check.value,
                    "threshold": check.threshold,
                    "message": check.message,
                }
                for check in self.checks
            ],
        }


def evaluate_phase0_quality(
    *,
    article_count: int,
    claims_count: int,
    parameters_count: int,
    canonical_claim_variable_pct: float,
    alignment_seed_parity_pct: float,
    hard_constraints_present: bool = False,
    hard_constraint_block_signal: bool | None = None,
    dataset_coverage_pct: float | None = None,
    proxy_share_pct: float | None = None,
    temporal_extrapolation_share_pct: float | None = None,
    thresholds: Phase0QualityThresholds | None = None,
) -> Phase0QualityReport:
    """Evaluate deterministic phase-0 quality gates and warnings."""
    th = thresholds or Phase0QualityThresholds()
    checks: list[Phase0QualityCheck] = []

    checks.append(
        Phase0QualityCheck(
            name="article_count",
            passed=article_count >= th.min_article_count,
            value=article_count,
            threshold=th.min_article_count,
        )
    )
    checks.append(
        Phase0QualityCheck(
            name="claims_count",
            passed=claims_count >= th.min_claims_count,
            value=claims_count,
            threshold=th.min_claims_count,
        )
    )
    checks.append(
        Phase0QualityCheck(
            name="parameters_count",
            passed=parameters_count >= th.min_parameters_count,
            value=parameters_count,
            threshold=th.min_parameters_count,
        )
    )
    checks.append(
        Phase0QualityCheck(
            name="canonical_claim_variable_pct",
            passed=canonical_claim_variable_pct >= th.min_canonical_claim_variable_pct,
            value=round(float(canonical_claim_variable_pct), 3),
            threshold=th.min_canonical_claim_variable_pct,
        )
    )
    checks.append(
        Phase0QualityCheck(
            name="alignment_seed_parity_pct",
            passed=alignment_seed_parity_pct >= th.required_alignment_seed_parity_pct,
            value=round(float(alignment_seed_parity_pct), 3),
            threshold=th.required_alignment_seed_parity_pct,
        )
    )

    if hard_constraints_present:
        checks.append(
            Phase0QualityCheck(
                name="hard_constraint_block_signal",
                passed=bool(hard_constraint_block_signal),
                value=1 if hard_constraint_block_signal else 0,
                threshold=1,
                message=(
                    ""
                    if hard_constraint_block_signal
                    else "HARD constraints present without blocking signal"
                ),
            )
        )
    else:
        checks.append(
            Phase0QualityCheck(
                name="hard_constraint_block_signal",
                passed=True,
                value=0,
                threshold=0,
                message="No HARD constraints in evaluated scenario.",
            )
        )

    checks.extend(
        _warning_checks(
            dataset_coverage_pct=dataset_coverage_pct,
            proxy_share_pct=proxy_share_pct,
            temporal_extrapolation_share_pct=temporal_extrapolation_share_pct,
            thresholds=th,
        )
    )

    metrics: dict[str, Any] = {
        "article_count": article_count,
        "claims_count": claims_count,
        "parameters_count": parameters_count,
        "canonical_claim_variable_pct": round(float(canonical_claim_variable_pct), 3),
        "alignment_seed_parity_pct": round(float(alignment_seed_parity_pct), 3),
        "hard_constraints_present": bool(hard_constraints_present),
        "hard_constraint_block_signal": bool(hard_constraint_block_signal),
    }
    if dataset_coverage_pct is not None:
        metrics["dataset_coverage_pct"] = round(float(dataset_coverage_pct), 3)
    if proxy_share_pct is not None:
        metrics["proxy_share_pct"] = round(float(proxy_share_pct), 3)
    if temporal_extrapolation_share_pct is not None:
        metrics["temporal_extrapolation_share_pct"] = round(
            float(temporal_extrapolation_share_pct), 3
        )

    return Phase0QualityReport(checks=checks, metrics=metrics)


def _warning_checks(
    *,
    dataset_coverage_pct: float | None,
    proxy_share_pct: float | None,
    temporal_extrapolation_share_pct: float | None,
    thresholds: Phase0QualityThresholds,
) -> list[Phase0QualityCheck]:
    checks: list[Phase0QualityCheck] = []

    checks.append(
        Phase0QualityCheck(
            name="dataset_coverage_pct",
            passed=(
                True
                if dataset_coverage_pct is None
                else dataset_coverage_pct >= thresholds.min_dataset_coverage_pct
            ),
            severity="warning",
            value=None if dataset_coverage_pct is None else round(float(dataset_coverage_pct), 3),
            threshold=thresholds.min_dataset_coverage_pct,
            message=(
                "dataset coverage metric was not provided" if dataset_coverage_pct is None else ""
            ),
        )
    )
    checks.append(
        Phase0QualityCheck(
            name="proxy_share_pct",
            passed=(
                True
                if proxy_share_pct is None
                else proxy_share_pct <= thresholds.max_proxy_share_pct
            ),
            severity="warning",
            value=None if proxy_share_pct is None else round(float(proxy_share_pct), 3),
            threshold=thresholds.max_proxy_share_pct,
            message="proxy share metric was not provided" if proxy_share_pct is None else "",
        )
    )
    checks.append(
        Phase0QualityCheck(
            name="temporal_extrapolation_share_pct",
            passed=(
                True
                if temporal_extrapolation_share_pct is None
                else temporal_extrapolation_share_pct
                <= thresholds.max_temporal_extrapolation_share_pct
            ),
            severity="warning",
            value=(
                None
                if temporal_extrapolation_share_pct is None
                else round(float(temporal_extrapolation_share_pct), 3)
            ),
            threshold=thresholds.max_temporal_extrapolation_share_pct,
            message=(
                "temporal extrapolation metric was not provided"
                if temporal_extrapolation_share_pct is None
                else ""
            ),
        )
    )
    return checks


__all__ = [
    "Phase0QualityCheck",
    "Phase0QualityReport",
    "Phase0QualityThresholds",
    "evaluate_phase0_quality",
]
