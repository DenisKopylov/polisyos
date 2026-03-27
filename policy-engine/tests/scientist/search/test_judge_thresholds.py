from __future__ import annotations

import pytest

from polisyos.scientist.search.judge_stack import (
    JudgeName,
    JudgeThresholdEntry,
    JudgeThresholdRegistry,
)


def test_threshold_registry_prefers_more_specific_scope(tmp_path) -> None:
    registry = JudgeThresholdRegistry(tmp_path / "judge_thresholds")
    registry.record(
        JudgeThresholdEntry(
            judge_name=JudgeName.STATISTICAL.value,
            metric_name="statistical_uncertainty_level",
            threshold_value=0.30,
            direction="max",
            rationale="scoped threshold",
            benchmark_source="unit_test",
            scope_family="causal_core",
            scope_query_type="policy",
            scope_estimator="cf",
            scope_readiness_target="deployment_ready",
        ),
        change_reason="seed scoped override",
        approved_by="tests",
    )

    resolved = registry.resolve(
        JudgeName.STATISTICAL.value,
        family="causal_core",
        query_type="policy",
        estimator="cf",
        readiness_target="deployment_ready",
    )

    assert resolved.threshold_value("statistical_uncertainty_level") == pytest.approx(0.30)


def test_threshold_registry_rejects_loosen_without_override(tmp_path) -> None:
    registry = JudgeThresholdRegistry(tmp_path / "judge_thresholds")

    with pytest.raises(ValueError, match="refuses to loosen"):
        registry.record(
            JudgeThresholdEntry(
                judge_name=JudgeName.COMPUTE.value,
                metric_name="timeout_risk",
                threshold_value=0.90,
                direction="max",
                rationale="too loose",
                benchmark_source="unit_test",
            ),
            change_reason="attempted loosening",
            approved_by="tests",
        )
