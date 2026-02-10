from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from polisyos.fabric.quality import (
    QualityIndicators,
    QualityLevel,
    QualityThresholds,
    compute_quality_indicators,
)
from polisyos.fabric.fitness_report import DataFitnessReport, MetricFitness


class TestQualityIndicatorsCalculation:
    """Test accuracy of quality indicator calculations."""

    def test_missingness_calculation_no_nulls(self) -> None:
        df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": ["x", "y", "z", "w", "v"]})
        indicators = compute_quality_indicators(df, metric_id="test_metric")
        assert indicators.missingness == 0.0
        assert indicators.row_count == 5

    def test_missingness_calculation_half_nulls(self) -> None:
        df = pd.DataFrame(
            {"a": [1, None, 3, None, 5], "b": [None, "y", None, "w", None]}
        )
        indicators = compute_quality_indicators(df, metric_id="test_metric")
        assert indicators.missingness == 0.5

    def test_missingness_calculation_all_nulls(self) -> None:
        df = pd.DataFrame({"a": [None, None, None], "b": [None, None, None]})
        indicators = compute_quality_indicators(df, metric_id="test_metric")
        assert indicators.missingness == 1.0

    def test_staleness_calculation(self) -> None:
        df = pd.DataFrame({"a": [1, 2, 3]})
        last_updated = datetime.utcnow() - timedelta(days=30)
        indicators = compute_quality_indicators(
            df, metric_id="test_metric", last_updated=last_updated
        )
        assert indicators.staleness_days == 30

    def test_coverage_calculation(self) -> None:
        df = pd.DataFrame({"a": [1, 2, 3, 4, 5]})
        indicators = compute_quality_indicators(
            df, metric_id="test_metric", expected_row_count=10
        )
        assert indicators.coverage == 0.5

    def test_coverage_exceeds_expected(self) -> None:
        df = pd.DataFrame({"a": range(20)})
        indicators = compute_quality_indicators(
            df, metric_id="test_metric", expected_row_count=10
        )
        assert indicators.coverage == 1.0

    def test_schema_drift_detection(self) -> None:
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
        baseline_columns = {"a", "b"}
        indicators = compute_quality_indicators(
            df, metric_id="test_metric", baseline_columns=baseline_columns
        )
        assert indicators.schema_drift is True

    def test_outlier_ratio_calculation(self) -> None:
        normal_values = list(range(10, 20))
        outliers = [100, 200]
        df = pd.DataFrame({"values": normal_values + outliers})
        indicators = compute_quality_indicators(df, metric_id="test_metric")
        assert indicators.outlier_ratio > 0.1


class TestQualityLevelScoring:
    """Test quality level determination logic."""

    def test_excellent_quality(self) -> None:
        indicators = QualityIndicators(
            metric_id="test",
            missingness=0.005,
            staleness_days=3,
            coverage=0.995,
            row_count=1000,
        )
        level = indicators.overall_level()
        assert level == QualityLevel.EXCELLENT

    def test_poor_quality_high_missingness(self) -> None:
        indicators = QualityIndicators(
            metric_id="test",
            missingness=0.25,
            staleness_days=5,
            coverage=0.95,
            row_count=1000,
        )
        level = indicators.overall_level()
        assert level in {QualityLevel.POOR, QualityLevel.ACCEPTABLE}

    def test_unusable_quality_insufficient_rows(self) -> None:
        indicators = QualityIndicators(
            metric_id="test",
            missingness=0.0,
            staleness_days=1,
            coverage=1.0,
            row_count=5,
        )
        level = indicators.overall_level()
        assert level == QualityLevel.UNUSABLE

    def test_schema_drift_penalty(self) -> None:
        base_indicators = QualityIndicators(
            metric_id="test",
            missingness=0.02,
            staleness_days=10,
            coverage=0.97,
            row_count=1000,
            schema_drift=False,
        )
        drift_indicators = QualityIndicators(
            metric_id="test",
            missingness=0.02,
            staleness_days=10,
            coverage=0.97,
            row_count=1000,
            schema_drift=True,
        )
        base_level = base_indicators.overall_level()
        drift_level = drift_indicators.overall_level()
        assert drift_level <= base_level

    def test_custom_thresholds(self) -> None:
        indicators = QualityIndicators(
            metric_id="test",
            missingness=0.15,
            staleness_days=50,
            coverage=0.80,
            row_count=100,
        )
        loose = QualityThresholds(
            missingness_acceptable=0.20,
            staleness_acceptable=90,
            coverage_acceptable=0.70,
        )
        level = indicators.overall_level(thresholds=loose)
        assert level.is_passing()


class TestQualityGatePassIntegration:
    """Test QualityGatePass integration with validation pipeline."""

    def test_strict_profile_blocks_on_poor_quality(self) -> None:
        from polisyos.scientist.governance.passes.quality_gate_pass import QualityGatePass
        from polisyos.core.governance.passes.base import PassContext, IssueSeverity
        from polisyos.core.governance.profiles import ValidationProfile

        quality_pass = QualityGatePass(force_run=True, critical_metrics=["test_metric"])

        profile = ValidationProfile.strict()
        ctx = PassContext(
            ir=None,
            state={
                "evidence_bundle": _mock_evidence_bundle(),
                "catalog_registry": _mock_catalog_with_poor_quality(),
            },
            registry_bundle=None,
            profile=profile,
            run_id="test_run",
        )

        issues = quality_pass.validate(ctx)
        blockers = [issue for issue in issues if issue.severity == IssueSeverity.BLOCKER]
        assert len(blockers) > 0

    def test_fast_profile_allows_poor_quality(self) -> None:
        from polisyos.core.governance.profiles import ValidationProfile

        profile = ValidationProfile.fast()
        assert "quality" not in profile.pass_ids

    def test_fitness_report_attached_to_state(self) -> None:
        from polisyos.scientist.governance.passes.quality_gate_pass import QualityGatePass
        from polisyos.core.governance.passes.base import PassContext
        from polisyos.core.governance.profiles import ValidationProfile

        quality_pass = QualityGatePass(force_run=True)

        profile = ValidationProfile.strict()
        ctx = PassContext(
            ir=None,
            state={
                "evidence_bundle": _mock_evidence_bundle(),
                "catalog_registry": _mock_catalog_with_good_quality(),
            },
            registry_bundle=None,
            profile=profile,
            run_id="test_run",
        )

        quality_pass.validate(ctx)
        assert "data_fitness_report" in ctx.state
        report = ctx.state["data_fitness_report"]
        assert isinstance(report, DataFitnessReport)


class TestDataFitnessReport:
    """Test fitness report generation."""

    def test_generate_summary_format(self) -> None:
        report = DataFitnessReport(run_id="test_001", profile="mvp")
        indicators = QualityIndicators(
            metric_id="revenue_quarterly",
            missingness=0.02,
            staleness_days=5,
            coverage=0.98,
            row_count=500,
        )
        fitness = MetricFitness.from_indicators(indicators, profile="mvp")
        report.add_metric(fitness)

        summary = report.generate_summary()
        assert "test_001" in summary
        assert "revenue_quarterly" in summary
        assert "PASSED" in summary or "FAILED" in summary

    def test_overall_passed_calculation(self) -> None:
        report = DataFitnessReport(run_id="test", profile="strict")

        good_indicators = QualityIndicators(
            metric_id="good_metric",
            missingness=0.01,
            staleness_days=5,
            coverage=0.99,
            row_count=1000,
        )
        bad_indicators = QualityIndicators(
            metric_id="bad_metric",
            missingness=0.50,
            staleness_days=200,
            coverage=0.30,
            row_count=5,
        )

        report.add_metric(MetricFitness.from_indicators(good_indicators))
        report.add_metric(MetricFitness.from_indicators(bad_indicators))

        assert report.overall_passed is False
        assert report.passed_metrics == 1
        assert report.failed_metrics == 1


def _mock_evidence_bundle():
    from dataclasses import dataclass

    @dataclass
    class MockEvidenceBundle:
        sources: list | None = None

        def __post_init__(self) -> None:
            self.sources = self.sources or []

    return MockEvidenceBundle()


def _mock_catalog_with_poor_quality():
    class MockRegistry:
        def get_contract(self, metric_id):
            return type(
                "Contract",
                (),
                {
                    "metadata": {
                        "quality_indicators": {
                            "metric_id": metric_id,
                            "missingness": 0.30,
                            "staleness_days": 120,
                            "coverage": 0.50,
                            "row_count": 50,
                            "computed_at": datetime.utcnow().isoformat(),
                        }
                    }
                },
            )()

    return MockRegistry()


def _mock_catalog_with_good_quality():
    class MockRegistry:
        def get_contract(self, metric_id):
            return type(
                "Contract",
                (),
                {
                    "metadata": {
                        "quality_indicators": {
                            "metric_id": metric_id,
                            "missingness": 0.01,
                            "staleness_days": 5,
                            "coverage": 0.99,
                            "row_count": 1000,
                            "computed_at": datetime.utcnow().isoformat(),
                        }
                    }
                },
            )()

    return MockRegistry()
