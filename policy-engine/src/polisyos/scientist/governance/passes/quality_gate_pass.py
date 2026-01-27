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

from .base import ValidatorPass, PassContext, ComplianceIssue, IssueSeverity


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
