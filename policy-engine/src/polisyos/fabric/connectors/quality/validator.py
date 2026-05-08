"""
Data Quality Validator - main orchestrator for quality validation.

Coordinates freshness, completeness, and consistency checks to produce
comprehensive quality reports.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd

from polisyos.common.logger import get_logger
from polisyos.core.evaluation import ThresholdBand, ThresholdMapper, WeightedScorer
from polisyos.fabric.numerics.finite import ensure_non_negative_finite, ensure_probability
from polisyos.fabric.data_plane.tabular import require_dataframe
from polisyos.ir.connectors import QualityTier

from .completeness import CompletenessAnalyzer, SamplingStrategy
from .consistency import ConsistencyChecker
from .freshness import FreshnessChecker, FreshnessPolicy
from .report import DataQualityReport
from .statistics import (
    QualityTrendPoint,
    build_quality_trend_report,
    detect_anomalies,
    detect_drift,
    evaluate_quality_contract,
    load_quality_contract,
    profile_dataframe,
)

logger = get_logger(__name__)


class QualityScorer:
    """
    Aggregate component scores into overall quality score and tier.

    score = (
        w_freshness * freshness_score +
        w_completeness * completeness_score +
        w_consistency * consistency_score
    )
    """

    _tier_mapper = ThresholdMapper[QualityTier](
        [
            ThresholdBand(0.95, QualityTier.PLATINUM),
            ThresholdBand(0.85, QualityTier.GOLD),
            ThresholdBand(0.70, QualityTier.SILVER),
            ThresholdBand(0.0, QualityTier.BRONZE),
        ],
        default=QualityTier.BRONZE,
    )
    _grade_mapper = ThresholdMapper[str](
        [
            ThresholdBand(0.97, "A+"),
            ThresholdBand(0.93, "A"),
            ThresholdBand(0.90, "A-"),
            ThresholdBand(0.87, "B+"),
            ThresholdBand(0.83, "B"),
            ThresholdBand(0.80, "B-"),
            ThresholdBand(0.77, "C+"),
            ThresholdBand(0.73, "C"),
            ThresholdBand(0.70, "C-"),
            ThresholdBand(0.60, "D"),
            ThresholdBand(0.0, "F"),
        ],
        default="F",
    )

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        defaults = {
            "freshness": 0.25,
            "completeness": 0.3,
            "consistency": 0.25,
            "profile": 0.08,
            "anomaly": 0.06,
            "drift": 0.04,
            "contract": 0.02,
        }
        if weights:
            for key, value in weights.items():
                if key in defaults and isinstance(value, (int, float)):
                    defaults[key] = ensure_non_negative_finite(
                        value,
                        what=f"quality weight {key}",
                    )
        if sum(max(value, 0.0) for value in defaults.values()) <= 0:
            defaults = {"freshness": 0.3, "completeness": 0.4, "consistency": 0.3}
        self._scorer = WeightedScorer(defaults)
        self.weights = self._scorer.weights

    def compute_breakdown(
        self,
        freshness_status: Any,
        completeness_score: float,
        consistency_score: float,
        *,
        profile_score: float | None = None,
        anomaly_score: float | None = None,
        drift_score: float | None = None,
        contract_score: float | None = None,
    ) -> Any:
        from .report import FreshnessLevel

        freshness_scores = {
            FreshnessLevel.FRESH: 1.0,
            FreshnessLevel.HEALTHY: 0.8,
            FreshnessLevel.STALE: 0.5,
            FreshnessLevel.EXPIRED: 0.0,
        }
        freshness_score = freshness_scores.get(freshness_status.level, 0.5)

        return self._scorer.score(
            {
                "freshness": freshness_score,
                "completeness": ensure_probability(
                    completeness_score,
                    what="quality completeness_score",
                ),
                "consistency": ensure_probability(
                    consistency_score,
                    what="quality consistency_score",
                ),
                "profile": (
                    ensure_probability(profile_score, what="quality profile_score")
                    if profile_score is not None
                    else None
                ),
                "anomaly": (
                    ensure_probability(anomaly_score, what="quality anomaly_score")
                    if anomaly_score is not None
                    else None
                ),
                "drift": (
                    ensure_probability(drift_score, what="quality drift_score")
                    if drift_score is not None
                    else None
                ),
                "contract": (
                    ensure_probability(contract_score, what="quality contract_score")
                    if contract_score is not None
                    else None
                ),
            }
        )

    def compute_score(
        self,
        freshness_status: Any,
        completeness_score: float,
        consistency_score: float,
        *,
        profile_score: float | None = None,
        anomaly_score: float | None = None,
        drift_score: float | None = None,
        contract_score: float | None = None,
    ) -> float:
        breakdown = self.compute_breakdown(
            freshness_status=freshness_status,
            completeness_score=completeness_score,
            consistency_score=consistency_score,
            profile_score=profile_score,
            anomaly_score=anomaly_score,
            drift_score=drift_score,
            contract_score=contract_score,
        )
        return ensure_probability(breakdown.score, what="quality aggregate score", clamp=True)

    def assign_tier(self, score: float) -> QualityTier:
        return self._tier_mapper.map(score)

    def assign_grade(self, score: float) -> str:
        return self._grade_mapper.map(score)


class DataQualityValidator:
    """Main orchestrator for quality validation."""

    def __init__(
        self,
        freshness_policies: dict[str, FreshnessPolicy] | None = None,
        quality_weights: dict[str, float] | None = None,
        sampling_threshold: int = 100_000,
    ) -> None:
        self.freshness_checker = FreshnessChecker(freshness_policies or {})
        self.completeness_analyzer = CompletenessAnalyzer()
        self.consistency_checker = ConsistencyChecker()
        self.scorer = QualityScorer(quality_weights)
        self.sampling_threshold = sampling_threshold

    def validate(
        self,
        fetch_result: Any,
        schema: Any,
        *,
        baseline_data: Any | None = None,
        quality_contract: str | Path | dict[str, Any] | None = None,
        trend_history: list[Any] | tuple[Any, ...] | None = None,
        enable_isolation_forest: bool = False,
    ) -> DataQualityReport:
        try:
            data = self._extract_dataframe(fetch_result)
            sampled_data, was_sampled = self._maybe_sample(data)

            freshness_status = self._check_freshness(fetch_result, schema)

            time_series = self._extract_time_series(data, schema)
            completeness_result = self._check_completeness(
                sampled_data,
                schema,
                time_series=time_series,
            )

            consistency_result = self._check_consistency(
                sampled_data,
                schema,
                full_data=data if was_sampled else None,
            )

            profiled_data = sampled_data if was_sampled else data
            dataset_profile = profile_dataframe(profiled_data, schema=schema)
            anomaly_report = detect_anomalies(
                profiled_data,
                enable_isolation_forest=enable_isolation_forest,
            )
            drift_report = (
                detect_drift(
                    current_data=profiled_data,
                    baseline_data=baseline_data,
                    schema=schema,
                    baseline_dataset_id=getattr(fetch_result, "schema_id", None),
                )
                if baseline_data is not None
                else None
            )

            base_breakdown = self.scorer.compute_breakdown(
                freshness_status=freshness_status,
                completeness_score=completeness_result.score,
                consistency_score=consistency_result.score,
                profile_score=dataset_profile.profile_score,
                anomaly_score=anomaly_report.score,
                drift_score=drift_report.score if drift_report is not None else None,
            )
            score = ensure_probability(base_breakdown.score, what="quality score", clamp=True)
            final_breakdown = base_breakdown

            contract_result = None
            contract_violations = []
            contract_warnings = []
            if quality_contract is not None:
                contract = load_quality_contract(quality_contract)
                contract_result = evaluate_quality_contract(
                    contract,
                    dataset_id=fetch_result.schema_id,
                    schema_id=schema.schema_id,
                    source_id=self._resolve_source_id(fetch_result),
                    score=score,
                    completeness_score=completeness_result.score,
                    consistency_score=consistency_result.score,
                    row_count=len(data),
                    dataset_profile=dataset_profile,
                    anomaly_report=anomaly_report,
                    drift_report=drift_report,
                )
                final_breakdown = self.scorer.compute_breakdown(
                    freshness_status=freshness_status,
                    completeness_score=completeness_result.score,
                    consistency_score=consistency_result.score,
                    profile_score=dataset_profile.profile_score,
                    anomaly_score=anomaly_report.score,
                    drift_score=drift_report.score if drift_report is not None else None,
                    contract_score=contract_result.score,
                )
                score = ensure_probability(
                    final_breakdown.score,
                    what="quality score",
                    clamp=True,
                )
                for failure in contract_result.failures:
                    message = failure.message
                    if failure.severity == "error":
                        contract_violations.append(self._contract_failure_to_violation(failure))
                    else:
                        contract_warnings.append(message)

            if (
                completeness_result.hard_fail
                or consistency_result.hard_fail
                or (contract_result is not None and contract_result.blocking_rules > 0)
            ):
                score = min(score, 0.69)

            tier = self.scorer.assign_tier(score)
            grade = self.scorer.assign_grade(score)

            violations = (
                completeness_result.violations + consistency_result.violations + contract_violations
            )
            warnings = self._generate_warnings(
                freshness_status,
                completeness_result,
                consistency_result,
                anomaly_report=anomaly_report,
                drift_report=drift_report,
                contract_result=contract_result,
            )
            warnings.extend(contract_warnings)

            quality_indicators = self._compute_quality_indicators(
                data=sampled_data if was_sampled else data,
                dataset_id=fetch_result.schema_id,
                fetch_result=fetch_result,
            )

            source_id = self._resolve_source_id(fetch_result)
            current_trend_point = QualityTrendPoint(
                dataset_id=fetch_result.schema_id,
                schema_id=schema.schema_id,
                source_id=source_id,
                validated_at=datetime.now(UTC),
                score=score,
                row_count=len(data),
                completeness_score=completeness_result.score,
                consistency_score=consistency_result.score,
                tier=tier.value,
            )
            trend_report = build_quality_trend_report(
                dataset_id=fetch_result.schema_id,
                schema_id=schema.schema_id,
                source_id=source_id,
                current_point=current_trend_point,
                history=trend_history,
            )

            return DataQualityReport(
                dataset_id=fetch_result.schema_id,
                schema_id=schema.schema_id,
                validated_at=current_trend_point.validated_at,
                score=score,
                tier=tier,
                grade=grade,
                freshness_status=freshness_status,
                completeness_score=completeness_result.score,
                consistency_score=consistency_result.score,
                violations=violations,
                warnings=warnings,
                quality_indicators=quality_indicators,
                row_count=len(data),
                sampled=was_sampled,
                sample_size=len(sampled_data) if was_sampled else None,
                source_id=source_id,
                component_scores=dict(final_breakdown.components),
                dataset_profile=dataset_profile,
                anomaly_report=anomaly_report,
                drift_report=drift_report,
                quality_contract_result=contract_result,
                trend_report=trend_report,
            )

        except Exception as exc:
            logger.exception("Quality validation failed: %s", exc)
            return self._create_error_report(fetch_result, schema, str(exc))

    def _extract_dataframe(self, fetch_result: Any) -> pd.DataFrame:
        return require_dataframe(
            fetch_result.data,
            allow_dict=True,
            label="fetch_result.data",
        )

    def _maybe_sample(self, data: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
        if not SamplingStrategy.should_sample(len(data), self.sampling_threshold):
            return data, False

        sample_size = SamplingStrategy.compute_sample_size(len(data))
        sampled_data, was_sampled = SamplingStrategy.sample_data(
            data, strategy="random", sample_size=sample_size
        )

        if was_sampled:
            logger.info(
                "Sampled %s/%s rows for quality validation",
                sample_size,
                len(data),
            )

        return sampled_data, was_sampled

    def _check_freshness(self, fetch_result: Any, schema: Any) -> Any:
        try:
            metadata = getattr(fetch_result, "metadata", None)
            if metadata is None:
                schedule_hint = self._schedule_hint_from_schema(schema)
                if schedule_hint:
                    metadata = SimpleNamespace(schedule=schedule_hint, capabilities=0)

            last_updated = getattr(fetch_result, "source_updated_at", None)
            if last_updated is None:
                last_updated = getattr(fetch_result.version, "timestamp", None)

            return self.freshness_checker.check_freshness(
                dataset_id=fetch_result.schema_id,
                metadata=metadata,
                fetched_at=fetch_result.fetched_at,
                last_updated=last_updated,
            )
        except Exception as exc:
            logger.warning("Freshness check failed: %s", exc)
            from .report import FreshnessLevel, FreshnessStatus

            return FreshnessStatus(
                level=FreshnessLevel.STALE,
                cache_age_seconds=0,
                data_age_seconds=None,
                ttl_seconds=86400,
                schedule="unknown",
                last_updated=None,
                fetched_at=fetch_result.fetched_at,
                message=f"Freshness check error: {exc}",
            )

    def _check_completeness(
        self,
        data: pd.DataFrame,
        schema: Any,
        *,
        time_series: pd.Series | None,
    ) -> Any:
        try:
            return self.completeness_analyzer.analyze(
                data=data,
                schema=schema,
                expected_row_count=None,
                time_series=time_series,
            )
        except Exception as exc:
            logger.warning("Completeness check failed: %s", exc)
            from .report import CompletenessResult

            return CompletenessResult(
                score=0.5,
                field_completeness={},
                violations=[],
                gaps_detected=0,
                penalty=0.0,
                hard_fail=False,
            )

    def _check_consistency(
        self,
        data: pd.DataFrame,
        schema: Any,
        *,
        full_data: pd.DataFrame | None,
    ) -> Any:
        try:
            return self.consistency_checker.check_consistency(
                data=data,
                schema=schema,
                full_data=full_data,
            )
        except Exception as exc:
            logger.warning("Consistency check failed: %s", exc)
            from .report import ConsistencyResult

            return ConsistencyResult(score=0.5, violations=[], penalty=0.0)

    def _compute_quality_indicators(
        self,
        data: pd.DataFrame,
        dataset_id: str,
        fetch_result: Any,
    ) -> Any:
        try:
            from polisyos.fabric.quality.quality import compute_quality_indicators

            last_updated = getattr(fetch_result, "source_updated_at", None)
            if last_updated is None:
                last_updated = getattr(fetch_result.version, "timestamp", None)

            return compute_quality_indicators(
                df=data,
                metric_id=dataset_id,
                last_updated=last_updated,
            )
        except Exception as exc:
            logger.warning("Failed to compute quality indicators: %s", exc)
            return None

    def _generate_warnings(
        self,
        freshness_status: Any,
        completeness_result: Any,
        consistency_result: Any,
        *,
        anomaly_report: Any | None = None,
        drift_report: Any | None = None,
        contract_result: Any | None = None,
    ) -> list[str]:
        warnings: list[str] = []

        if not freshness_status.is_fresh:
            warnings.append(freshness_status.message)

        if getattr(completeness_result, "applicable", True) and completeness_result.score < 0.9:
            warnings.append(f"Completeness score {completeness_result.score:.1%} below 90%")

        if completeness_result.gaps_detected > 0:
            warnings.append(f"{completeness_result.gaps_detected} gaps detected in time series")

        if consistency_result.score < 0.9:
            warnings.append(f"Consistency score {consistency_result.score:.1%} below 90%")

        if anomaly_report is not None and anomaly_report.findings:
            warnings.append(f"Detected {len(anomaly_report.findings)} statistical anomaly findings")

        if drift_report is not None and drift_report.findings:
            detected = sum(1 for finding in drift_report.findings if finding.detected)
            warnings.append(f"Detected {detected}/{len(drift_report.findings)} drift findings")

        if contract_result is not None and not contract_result.passed:
            warnings.append(
                f"Quality contract {contract_result.contract_name} failed "
                f"{contract_result.failed_rules}/{contract_result.evaluated_rules} rules"
            )

        return warnings

    def _create_error_report(
        self,
        fetch_result: Any,
        schema: Any,
        error_message: str,
    ) -> DataQualityReport:
        from .report import FreshnessLevel, FreshnessStatus

        return DataQualityReport(
            dataset_id=fetch_result.schema_id,
            schema_id=schema.schema_id,
            validated_at=datetime.now(UTC),
            score=0.0,
            tier=QualityTier.BRONZE,
            grade="F",
            freshness_status=FreshnessStatus(
                level=FreshnessLevel.EXPIRED,
                cache_age_seconds=0,
                data_age_seconds=None,
                ttl_seconds=0,
                schedule="unknown",
                last_updated=None,
                fetched_at=fetch_result.fetched_at,
                message="Validation error",
            ),
            completeness_score=0.0,
            consistency_score=0.0,
            violations=[],
            warnings=[f"Validation error: {error_message}"],
            quality_indicators=None,
            row_count=0,
            sampled=False,
        )

    @staticmethod
    def _resolve_source_id(fetch_result: Any) -> str | None:
        metadata = getattr(fetch_result, "metadata", None)
        if metadata is not None:
            for attr_name in ("source_id", "source", "connector_id"):
                value = getattr(metadata, attr_name, None)
                if isinstance(value, str) and value:
                    return value
        for attr_name in ("source_id", "source", "connector_id"):
            value = getattr(fetch_result, attr_name, None)
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _contract_failure_to_violation(failure: Any) -> Any:
        from .report import RuleViolation

        return RuleViolation(
            rule_type=f"quality_contract:{failure.rule_id}",
            field_name=failure.field_name,
            severity=failure.severity,
            message=failure.message,
            expected=failure.expected,
            actual=failure.actual,
            sample_values=None,
        )

    @staticmethod
    def _schedule_hint_from_schema(schema: Any) -> str | None:
        granularity = getattr(schema, "time_granularity", None)
        if granularity is None:
            return None
        mapping = {
            "second": "real-time",
            "minute": "real-time",
            "hourly": "hourly",
            "daily": "daily",
            "weekly": "weekly",
            "monthly": "monthly",
            "quarterly": "quarterly",
            "annual": "annual",
            "fiscal_year": "annual",
        }
        value = getattr(granularity, "value", None)
        if value is None:
            value = str(granularity)
        return mapping.get(str(value).lower())

    @staticmethod
    def _extract_time_series(data: pd.DataFrame, schema: Any) -> pd.Series | None:
        time_dimension = getattr(schema, "time_dimension", None)
        if time_dimension and time_dimension in data.columns:
            return data[time_dimension]

        for field in schema.fields:
            if hasattr(field, "semantic_type"):
                from polisyos.fabric.connectors.contracts.schema import SemanticType

                if field.semantic_type == SemanticType.TEMPORAL:
                    if field.name in data.columns:
                        return data[field.name]
            if hasattr(field, "data_type") and field.data_type.is_temporal():
                if field.name in data.columns:
                    return data[field.name]
        return None
