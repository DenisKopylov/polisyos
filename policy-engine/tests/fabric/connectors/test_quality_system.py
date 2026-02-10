"""Tests for the Phase 2.6 quality system."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

from polisyos.fabric.connectors.base import FetchResult
from polisyos.fabric.connectors.quality import (
    CompletenessAnalyzer,
    ConsistencyChecker,
    DataQualityReport,
    DataQualityValidator,
    FreshnessChecker,
    FreshnessLevel,
    FreshnessPolicy,
)
from polisyos.fabric.connectors.contracts.schema import (
    DataSchema,
    FieldSpec,
    SchemaType,
    SchemaVersion,
    SemanticType,
    TimeGranularity,
)
from polisyos.ir.connectors import DataVersion, QualityTier, VersionStrategy


def make_schema(
    fields: list[FieldSpec],
    *,
    time_dimension: str | None = None,
    time_granularity: TimeGranularity | None = None,
) -> DataSchema:
    return DataSchema(
        schema_id="test.schema",
        version=SchemaVersion.parse("1.0.0"),
        fields=tuple(fields),
        time_dimension=time_dimension,
        time_granularity=time_granularity,
    )


def make_fetch_result(
    data,
    *,
    fetched_at: datetime | None = None,
    source_updated_at: datetime | None = None,
) -> FetchResult:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    version = DataVersion(
        strategy=VersionStrategy.TIMESTAMP,
        value=fetched_at.isoformat(),
        timestamp=fetched_at,
    )
    if isinstance(data, pd.DataFrame):
        row_count = len(data)
    elif isinstance(data, list):
        row_count = len(data)
    else:
        row_count = 0
    return FetchResult(
        data=data,
        row_count=row_count,
        schema_id="test.dataset",
        schema_version="1.0.0",
        version=version,
        fetched_at=fetched_at,
        source_updated_at=source_updated_at,
        completeness=1.0,
        quality_tier=QualityTier.UNVERIFIED,
    )


class TestFreshnessChecker:
    def test_fresh_real_time_data(self):
        checker = FreshnessChecker()
        metadata = SimpleNamespace(schedule="real-time", capabilities=0)
        status = checker.check_freshness(
            dataset_id="stock_prices",
            metadata=metadata,
            fetched_at=datetime.now(timezone.utc) - timedelta(minutes=2),
            last_updated=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        assert status.level == FreshnessLevel.FRESH
        assert status.is_fresh

    def test_schedule_inference_ignores_unknown(self):
        checker = FreshnessChecker()
        metadata = SimpleNamespace(schedule="unknown", capabilities=0)
        status = checker.check_freshness(
            dataset_id="census_monthly_2024",
            metadata=metadata,
            fetched_at=datetime.now(timezone.utc) - timedelta(days=20),
        )
        assert status.schedule == "monthly"

    def test_adaptive_requires_update_interval(self):
        policy = FreshnessPolicy(
            ttl=timedelta(minutes=5),
            schedule="real-time",
            adaptive=True,
        )
        checker = FreshnessChecker({"market_data": policy})
        metadata = SimpleNamespace(schedule="real-time", capabilities=0)
        status = checker.check_freshness(
            dataset_id="market_data",
            metadata=metadata,
            fetched_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert status.ttl_seconds == 300


class TestCompletenessAnalyzer:
    def test_missing_required_field_hard_fail(self):
        df = pd.DataFrame({"value": [1, 2, 3]})
        schema = make_schema(
            [
                FieldSpec(
                    name="required_field",
                    data_type=SchemaType.INT32,
                    expected_completeness=1.0,
                )
            ]
        )
        analyzer = CompletenessAnalyzer()
        result = analyzer.analyze(df, schema)
        assert result.hard_fail
        assert result.score == 0.0

    def test_gap_detection_uses_time_dimension(self):
        dates = pd.date_range("2024-01-01", "2024-01-10", freq="D")
        dates_with_gap = dates.delete([3, 4])
        df = pd.DataFrame({"date": dates_with_gap, "value": range(len(dates_with_gap))})
        schema = make_schema(
            [
                FieldSpec(
                    name="date",
                    data_type=SchemaType.DATETIME,
                    semantic_type=SemanticType.TEMPORAL,
                ),
                FieldSpec(name="value", data_type=SchemaType.INT32),
            ],
            time_dimension="date",
            time_granularity=TimeGranularity.DAILY,
        )
        analyzer = CompletenessAnalyzer()
        result = analyzer.analyze(df, schema)
        assert result.gaps_detected > 0


class TestConsistencyChecker:
    def test_bounds_violation(self):
        df = pd.DataFrame({"age": [25, 30, -5, 150, 40]})
        schema = make_schema(
            [FieldSpec(name="age", data_type=SchemaType.INT32, bounds=(0, 120))]
        )
        checker = ConsistencyChecker()
        result = checker.check_consistency(df, schema)
        assert any("below minimum" in v.message for v in result.violations)
        assert any("above maximum" in v.message for v in result.violations)

    def test_categorical_validation(self):
        df = pd.DataFrame({"country": ["USA", "CAN", "UK", "MEX", "FR"]})
        schema = make_schema(
            [
                FieldSpec(
                    name="country",
                    data_type=SchemaType.CATEGORY,
                    allowed_values=frozenset(["USA", "CAN", "MEX"]),
                )
            ]
        )
        checker = ConsistencyChecker()
        result = checker.check_consistency(df, schema)
        assert len(result.violations) == 1


class TestDataQualityValidator:
    def test_high_quality_data_platinum(self):
        df = pd.DataFrame({"value": range(100)})
        fetch_result = make_fetch_result(
            data=df,
            fetched_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            source_updated_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        )
        schema = make_schema(
            [
                FieldSpec(
                    name="value",
                    data_type=SchemaType.INT32,
                    expected_completeness=1.0,
                    bounds=(0, 1000),
                )
            ]
        )
        validator = DataQualityValidator()
        report = validator.validate(fetch_result, schema)
        assert report.tier == QualityTier.PLATINUM
        assert report.is_acceptable

    def test_low_quality_data_bronze(self):
        df = pd.DataFrame({"value": [1, None, 3, None, 5, None, 200, None]})
        fetch_result = make_fetch_result(
            data=df,
            fetched_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        schema = make_schema(
            [
                FieldSpec(
                    name="value",
                    data_type=SchemaType.INT32,
                    expected_completeness=0.95,
                    bounds=(0, 100),
                )
            ]
        )
        validator = DataQualityValidator()
        report = validator.validate(fetch_result, schema)
        assert report.tier == QualityTier.BRONZE
        assert report.needs_attention

    def test_sampling_preserves_gap_detection(self):
        dates = pd.date_range("2024-01-01", "2024-03-01", freq="D")
        dates_with_gap = dates.delete([10, 11, 12])
        df = pd.DataFrame({"date": dates_with_gap, "value": range(len(dates_with_gap))})
        fetch_result = make_fetch_result(data=df)
        schema = make_schema(
            [
                FieldSpec(
                    name="date",
                    data_type=SchemaType.DATETIME,
                    semantic_type=SemanticType.TEMPORAL,
                ),
                FieldSpec(name="value", data_type=SchemaType.INT32),
            ],
            time_dimension="date",
            time_granularity=TimeGranularity.DAILY,
        )
        validator = DataQualityValidator(sampling_threshold=10)
        report = validator.validate(fetch_result, schema)
        assert any("gaps detected" in warning for warning in report.warnings)

    def test_sampling_preserves_categorical_checks(self):
        df = pd.DataFrame({
            "category": ["A"] * 200 + ["B"] * 200 + ["X"]
        })
        fetch_result = make_fetch_result(data=df)
        schema = make_schema(
            [
                FieldSpec(
                    name="category",
                    data_type=SchemaType.CATEGORY,
                    allowed_values=frozenset(["A", "B"]),
                )
            ]
        )
        validator = DataQualityValidator(sampling_threshold=50)
        report = validator.validate(fetch_result, schema)
        assert any(v.field_name == "category" for v in report.violations)


class TestQualityGateIntegration:
    def test_quality_gate_blocks_bronze_in_strict(self):
        try:
            from polisyos.scientist.governance.passes.quality_gate_pass import (
                QualityGatePass,
            )
            from polisyos.core.governance.passes.base import PassContext
            from polisyos.core.governance.profiles import ValidationProfile
        except ModuleNotFoundError as exc:
            pytest.skip(f"Governance dependencies unavailable: {exc}")

        freshness_status = SimpleNamespace(
            level=FreshnessLevel.STALE,
            is_fresh=False,
            cache_age_seconds=0,
            data_age_seconds=None,
            ttl_seconds=0,
            schedule="daily",
            last_updated=None,
            fetched_at=datetime.now(timezone.utc),
            message="stale",
        )
        report = DataQualityReport(
            dataset_id="test.dataset",
            schema_id="test.schema",
            validated_at=datetime.now(timezone.utc),
            score=0.65,
            tier=QualityTier.BRONZE,
            grade="D",
            freshness_status=freshness_status,
            completeness_score=0.6,
            consistency_score=0.6,
            violations=[],
            warnings=[],
            quality_indicators=None,
            row_count=100,
        )

        ctx = PassContext(
            ir=None,
            state={"data_quality_report": report},
            registry_bundle=None,
            profile=ValidationProfile.strict(),
            run_id="test",
        )

        gate = QualityGatePass()
        issues = gate.validate(ctx)
        assert any(issue.severity.value == "blocker" for issue in issues)
