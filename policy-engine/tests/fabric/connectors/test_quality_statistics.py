from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from polisyos.fabric.connectors.base import FetchResult
from polisyos.fabric.connectors.contracts.schema import (
    DataSchema,
    FieldSpec,
    SchemaType,
    SchemaVersion,
    SemanticType,
    TimeGranularity,
)
from polisyos.fabric.connectors.quality import (
    DataQualityValidator,
    detect_drift,
)
from polisyos.ir.connectors import DataVersion, QualityTier, VersionStrategy


def _schema() -> DataSchema:
    return DataSchema(
        schema_id="test.schema",
        version=SchemaVersion.parse("1.0.0"),
        fields=(
            FieldSpec(
                name="date",
                data_type=SchemaType.DATETIME,
                semantic_type=SemanticType.TEMPORAL,
            ),
            FieldSpec(
                name="value",
                data_type=SchemaType.FLOAT64,
                expected_completeness=1.0,
                bounds=(0, 10_000),
            ),
            FieldSpec(
                name="category",
                data_type=SchemaType.CATEGORY,
                allowed_values=frozenset({"A", "B", "C"}),
            ),
        ),
        time_dimension="date",
        time_granularity=TimeGranularity.DAILY,
    )


def _fetch_result(data: pd.DataFrame, *, fetched_at: datetime | None = None) -> FetchResult:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    version = DataVersion(
        strategy=VersionStrategy.TIMESTAMP,
        value=fetched_at.isoformat(),
        timestamp=fetched_at,
    )
    return FetchResult(
        data=data,
        row_count=len(data),
        schema_id="test.dataset",
        schema_version="1.0.0",
        version=version,
        fetched_at=fetched_at,
        source_updated_at=fetched_at - timedelta(hours=1),
        completeness=1.0,
        quality_tier=QualityTier.UNVERIFIED,
    )


def test_validator_emits_profiles_anomalies_drift_and_trends() -> None:
    baseline = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=30, freq="D"),
            "value": [10.0 + index for index in range(30)],
            "category": ["A"] * 20 + ["B"] * 10,
        }
    )
    current = pd.DataFrame(
        {
            "date": pd.date_range("2024-02-01", periods=30, freq="D"),
            "value": [100.0 + index for index in range(28)] + [2_000.0, 2_500.0],
            "category": ["C"] * 30,
        }
    )
    history = [
        {
            "dataset_id": "test.dataset",
            "schema_id": "test.schema",
            "validated_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "score": 0.96,
            "row_count": 30,
            "completeness_score": 1.0,
            "consistency_score": 1.0,
            "tier": "platinum",
        }
    ]

    report = DataQualityValidator().validate(
        _fetch_result(current),
        _schema(),
        baseline_data=baseline,
        trend_history=history,
    )

    assert report.dataset_profile is not None
    assert "value" in report.dataset_profile.column_profiles
    assert report.dataset_profile.column_profiles["value"].quantiles["p50"] > 100.0

    assert report.anomaly_report is not None
    assert report.anomaly_report.findings
    assert any(finding.column_name == "value" for finding in report.anomaly_report.findings)

    assert report.drift_report is not None
    assert report.drift_report.findings
    assert any(finding.detected for finding in report.drift_report.findings)

    assert report.trend_report is not None
    assert report.trend_report.score_delta is not None
    assert report.trend_report.score_delta < 0


def test_inline_yaml_quality_contract_can_gate_validation() -> None:
    data = pd.DataFrame(
        {
            "date": pd.date_range("2024-03-01", periods=10, freq="D"),
            "value": [10.0, 11.0, None, 12.0, 13.0, 14.0, 15.0, 16.0, 5_000.0, 6_000.0],
            "category": ["A"] * 10,
        }
    )
    contract_yaml = """
name: gated_quality
rules:
  - expect_column_null_rate_to_be_between:
      column: value
      max: 0.0
      severity: error
  - expect_column_anomaly_rate_to_be_below:
      column: value
      max: 0.01
      severity: warning
  - expect_dataset_score_to_be_at_least:
      value: 0.8
      severity: error
"""

    report = DataQualityValidator().validate(
        _fetch_result(data),
        _schema(),
        quality_contract=contract_yaml,
    )

    assert report.quality_contract_result is not None
    assert report.quality_contract_result.passed is False
    assert report.quality_contract_result.failed_rules >= 1
    assert any(
        violation.rule_type.startswith("quality_contract:")
        for violation in report.violations
    )
    assert report.score <= 0.69


def test_detect_drift_reports_numeric_and_categorical_findings() -> None:
    baseline = pd.DataFrame(
        {
            "value": [10.0 + index for index in range(50)],
            "category": ["A"] * 40 + ["B"] * 10,
        }
    )
    current = pd.DataFrame(
        {
            "value": [200.0 + index for index in range(50)],
            "category": ["C"] * 50,
        }
    )

    report = detect_drift(
        current,
        baseline,
        schema=_schema(),
        baseline_dataset_id="baseline.dataset",
    )

    tests = {(finding.column_name, finding.test) for finding in report.findings}
    assert ("value", "ks") in tests
    assert ("value", "psi") in tests
    assert ("category", "chi_squared") in tests
    assert any(finding.detected for finding in report.findings)
