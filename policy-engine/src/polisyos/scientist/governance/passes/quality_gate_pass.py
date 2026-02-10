from __future__ import annotations

from typing import Any, List

from polisyos.fabric.fitness_report import DataFitnessReport, MetricFitness
from polisyos.fabric.quality import (
    QualityIndicators,
    QualityLevel,
    QualityThresholds,
    compute_quality_indicators,
    get_cached_quality_indicators,
)

from polisyos.core.governance.passes.base import ValidatorPass, PassContext, ComplianceIssue, IssueSeverity


class QualityGatePass(ValidatorPass):
    """
    Validates data quality before simulation execution.

    Behavior by profile:
    - FAST: Skip entirely (not in pass_ids)
    - MVP: Skip entirely (not in pass_ids)
    - STRICT: Run and block on POOR or UNUSABLE quality
    """

    def __init__(
        self,
        *,
        force_run: bool = False,
        critical_metrics: list[str] | None = None,
    ) -> None:
        self._force_run = force_run
        self._critical_metrics = critical_metrics

    @property
    def pass_id(self) -> str:
        return "quality"

    @property
    def estimated_cost_ms(self) -> int:
        return 500

    @property
    def requires_data(self) -> bool:
        return True

    def validate(self, ctx: PassContext) -> List[ComplianceIssue]:
        issues: List[ComplianceIssue] = []

        if not self._force_run and self.pass_id not in ctx.profile.pass_ids:
            return issues

        profile_level = ctx.profile.level.value
        quality_thresholds = self._get_thresholds_from_profile(ctx.profile)

        report = DataFitnessReport(run_id=ctx.run_id, profile=profile_level)
        ctx.state["data_fitness_report"] = report

        data_quality_report = ctx.state.get("data_quality_report")
        if data_quality_report is not None:
            self._validate_from_quality_report(
                data_quality_report=data_quality_report,
                ctx=ctx,
                issues=issues,
            )
            report.generate_summary()
            return issues

        evidence_bundle = ctx.state.get("evidence_bundle")
        if evidence_bundle is None:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["state", "evidence_bundle"],
                    message="No evidence bundle found in state; cannot validate data quality",
                    severity=IssueSeverity.WARNING,
                    code="NO_EVIDENCE_BUNDLE",
                    suggestion="Ensure EvidenceBundle is attached to state before validation",
                )
            )
            report.generate_summary()
            return issues

        catalog_registry = ctx.state.get("catalog_registry")
        metrics_to_check = self._get_metrics_to_check(evidence_bundle, ctx)

        for metric_id, metric_data in metrics_to_check.items():
            indicators = self._get_or_compute_indicators(
                metric_id=metric_id,
                metric_data=metric_data,
                catalog_registry=catalog_registry,
            )

            if indicators is None:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["metrics", metric_id],
                        message=f"Could not compute quality indicators for metric '{metric_id}'",
                        severity=IssueSeverity.WARNING,
                        code="INDICATORS_UNAVAILABLE",
                    )
                )
                continue

            fitness = MetricFitness.from_indicators(
                indicators=indicators,
                thresholds=quality_thresholds,
                profile=profile_level,
            )
            report.add_metric(fitness)

            if fitness.level == QualityLevel.UNUSABLE:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["metrics", metric_id, "quality"],
                        message=f"Metric '{metric_id}' has UNUSABLE quality level",
                        severity=IssueSeverity.BLOCKER,
                        code="QUALITY_UNUSABLE",
                        suggestion="; ".join(fitness.fail_reasons[:2]),
                    )
                )
            elif fitness.level == QualityLevel.POOR:
                severity = (
                    IssueSeverity.BLOCKER
                    if profile_level == "strict"
                    else IssueSeverity.WARNING
                )
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["metrics", metric_id, "quality"],
                        message=f"Metric '{metric_id}' has POOR quality level",
                        severity=severity,
                        code="QUALITY_POOR",
                        suggestion="; ".join(fitness.fail_reasons[:2]),
                    )
                )

        report.generate_summary()
        return issues

    def _get_thresholds_from_profile(self, profile: Any) -> QualityThresholds:
        profile_thresholds = profile.thresholds or {}
        level = profile.level.value

        thresholds = QualityThresholds.for_profile(level)

        overrides: dict[str, Any] = {}
        for key, value in profile_thresholds.items():
            if key.startswith("quality_"):
                threshold_key = key[8:]
                if hasattr(thresholds, threshold_key):
                    overrides[threshold_key] = value

        if overrides:
            thresholds = thresholds.with_overrides(overrides)

        return thresholds

    def _get_metrics_to_check(
        self,
        evidence_bundle: Any,
        ctx: PassContext,
    ) -> dict[str, Any]:
        metrics: dict[str, Any] = {}

        bundle_quality = getattr(evidence_bundle, "quality_indicators", None)
        if isinstance(bundle_quality, dict):
            for metric_id, indicator_payload in bundle_quality.items():
                metrics[str(metric_id)] = {
                    "source": "evidence_bundle",
                    "indicators": indicator_payload,
                }

        if self._critical_metrics:
            for metric_id in self._critical_metrics:
                entry = metrics.get(metric_id, {})
                entry.setdefault("source", "explicit")
                metrics[metric_id] = entry
            return metrics

        for source in getattr(evidence_bundle, "sources", []) or []:
            if hasattr(source, "artifact_id"):
                metric_id = str(source.artifact_id)
                metrics.setdefault(metric_id, {"source": source})

        metric_refs = ctx.state.get("metric_refs", []) or []
        for ref in metric_refs:
            if isinstance(ref, str):
                metrics.setdefault(ref, {"source": "state"})
            elif hasattr(ref, "metric_id"):
                metrics.setdefault(ref.metric_id, {"source": ref})

        return metrics

    def _get_or_compute_indicators(
        self,
        metric_id: str,
        metric_data: dict[str, Any],
        catalog_registry: Any | None,
    ) -> QualityIndicators | None:
        indicators_payload = metric_data.get("indicators")
        if isinstance(indicators_payload, QualityIndicators):
            return indicators_payload
        if isinstance(indicators_payload, dict):
            try:
                return QualityIndicators.from_dict(indicators_payload)
            except Exception:
                return None

        if catalog_registry is not None:
            cached = get_cached_quality_indicators(metric_id, catalog_registry)
            if cached is not None:
                return cached

        source = metric_data.get("source")
        if isinstance(source, str) and source in {"explicit", "state", "evidence_bundle"}:
            return None

        if hasattr(source, "load_dataframe"):
            try:
                df = source.load_dataframe()
                return compute_quality_indicators(df=df, metric_id=metric_id)
            except Exception:
                return None

        return None

    def _validate_from_quality_report(
        self,
        data_quality_report: Any,
        ctx: PassContext,
        issues: List[ComplianceIssue],
    ) -> None:
        from polisyos.ir.connectors import QualityTier

        profile_level = ctx.profile.level.value

        if data_quality_report.tier == QualityTier.BRONZE:
            severity = (
                IssueSeverity.BLOCKER
                if profile_level == "strict"
                else IssueSeverity.WARNING
            )

            violation_summary: list[str] = []
            for violation in data_quality_report.violations[:3]:
                field = violation.field_name or "unknown"
                violation_summary.append(f"{field}: {violation.message}")

            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["data", "quality"],
                    message=(
                        f"Data quality {data_quality_report.grade} "
                        f"(score: {data_quality_report.score:.2f}) is below threshold"
                    ),
                    severity=severity,
                    code="QUALITY_BRONZE_TIER",
                    suggestion=(
                        "Address top violations: " + "; ".join(violation_summary)
                        if violation_summary
                        else "Investigate data quality violations"
                    ),
                )
            )

        if not data_quality_report.freshness_status.is_fresh:
            severity = (
                IssueSeverity.WARNING
                if profile_level in ("fast", "mvp")
                else IssueSeverity.BLOCKER
            )

            age_days = 0
            if data_quality_report.freshness_status.data_age_seconds is not None:
                age_days = data_quality_report.freshness_status.data_age_seconds // 86400

            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["data", "freshness"],
                    message=data_quality_report.freshness_status.message,
                    severity=severity,
                    code="DATA_STALENESS",
                    suggestion=f"Data last updated {age_days} days ago",
                )
            )

        critical_violations = [
            v for v in data_quality_report.violations if v.severity == "error"
        ]
        if critical_violations:
            for violation in critical_violations[:5]:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["data", "violations", violation.field_name or "unknown"],
                        message=violation.message,
                        severity=(
                            IssueSeverity.BLOCKER
                            if profile_level == "strict"
                            else IssueSeverity.WARNING
                        ),
                        code=f"QUALITY_{violation.rule_type.upper()}",
                        suggestion=(
                            f"Expected: {violation.expected}, Actual: {violation.actual}"
                        ),
                    )
                )

        try:
            indicators = QualityIndicators.from_quality_report(data_quality_report)
            fitness = MetricFitness.from_indicators(
                indicators=indicators,
                thresholds=self._get_thresholds_from_profile(ctx.profile),
                profile=profile_level,
            )
            report = ctx.state.get("data_fitness_report")
            if report:
                report.add_metric(fitness)
        except Exception:
            return None
