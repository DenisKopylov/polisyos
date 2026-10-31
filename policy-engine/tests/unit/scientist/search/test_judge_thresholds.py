from __future__ import annotations

import json
import math

import pytest

from polisyos.foundry.methods.catalog.causal.algebraic_calibration import (
    tetrad_threshold_recommendations,
)
from polisyos.scientist.methods.search.judge_stack import (
    JudgeName,
    JudgeStack,
    JudgeThresholdEntry,
    JudgeThresholdRegistry,
    _check_threshold_violation,
)
from polisyos.scientist.methods.search.judge_thresholds import JudgeThresholdSnapshot


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


def test_threshold_registry_exposes_tiered_tetrad_defaults(tmp_path) -> None:
    registry = JudgeThresholdRegistry(tmp_path / "judge_thresholds")
    resolved = registry.resolve(JudgeName.STATISTICAL.value, family="algebraic_tetrad")
    recommendations = {
        (item.metric_name, item.threshold_tier): item for item in tetrad_threshold_recommendations()
    }

    assert resolved.threshold_value(
        "algebraic_tetrad_min_q",
        threshold_tier="warning",
    ) == pytest.approx(recommendations[("algebraic_tetrad_min_q", "warning")].threshold_value)
    assert resolved.threshold_value("algebraic_tetrad_min_q") == pytest.approx(
        recommendations[("algebraic_tetrad_min_q", "blocker")].threshold_value
    )
    assert resolved.threshold_value(
        "algebraic_tetrad_max_abs_z",
        threshold_tier="warning",
    ) == pytest.approx(recommendations[("algebraic_tetrad_max_abs_z", "warning")].threshold_value)
    assert resolved.threshold_value("algebraic_tetrad_max_abs_z") == pytest.approx(
        recommendations[("algebraic_tetrad_max_abs_z", "blocker")].threshold_value
    )

    warn_violation = _check_threshold_violation(
        resolved,
        metric_name="algebraic_tetrad_min_q",
        observed_value=0.05,
        threshold_tier="warning",
    )
    blocker_violation = _check_threshold_violation(
        resolved,
        metric_name="algebraic_tetrad_min_q",
        observed_value=0.05,
    )

    assert warn_violation is not None
    assert blocker_violation is None


def test_threshold_registry_prefers_dp_specific_scope(tmp_path) -> None:
    registry = JudgeThresholdRegistry(tmp_path / "judge_thresholds")
    registry.record(
        JudgeThresholdEntry(
            judge_name="ci_tests",
            metric_name="mc_bootstrap_B",
            threshold_value=250,
            direction="min",
            rationale="generic categorical CI setting",
            benchmark_source="unit_test",
            scope_family="categorical_ci",
            scope_query_type="g2",
            scope_estimator="stratified_counts",
        ),
        change_reason="seed generic categorical CI policy",
        approved_by="tests",
    )
    registry.record(
        JudgeThresholdEntry(
            judge_name="ci_tests",
            metric_name="mc_bootstrap_B",
            threshold_value=1000,
            direction="min",
            rationale="DP-specific categorical CI setting",
            benchmark_source="unit_test",
            scope_family="categorical_ci",
            scope_query_type="g2",
            scope_estimator="stratified_counts",
            scope_dp_mechanism="laplace_counts",
            scope_dp_epsilon_bucket="0.5_to_1.0",
            scope_dp_delta_bucket="zero",
        ),
        change_reason="seed DP categorical CI policy",
        approved_by="tests",
    )

    resolved = registry.resolve(
        "ci_tests",
        family="categorical_ci",
        query_type="g2",
        estimator="stratified_counts",
        dp_mechanism="laplace_counts",
        dp_epsilon=0.7,
        dp_delta=0.0,
    )

    assert resolved.threshold_value("mc_bootstrap_B") == pytest.approx(1000.0)
    assert resolved.scope["dp_epsilon_bucket"] == "0.5_to_1.0"


def test_threshold_registry_resolves_typed_foundry_ci_policy(tmp_path) -> None:
    registry = JudgeThresholdRegistry(tmp_path / "judge_thresholds")
    registry.record(
        JudgeThresholdEntry(
            judge_name="ci_tests",
            metric_name="mc_bootstrap_B",
            threshold_value=1234,
            direction="min",
            rationale="DP-scoped test policy",
            benchmark_source="unit_test",
            scope_family="categorical_ci",
            scope_query_type="g2",
            scope_estimator="stratified_counts",
            scope_readiness_target="diagnostic",
            scope_dp_mechanism="laplace_counts",
            scope_dp_epsilon_bucket="0.5_to_1.0",
            scope_dp_delta_bucket="zero",
        ),
        change_reason="test Scientist-to-Foundry resolution",
        approved_by="tests",
    )

    policy = registry.resolve_ci_test_policy(
        family="categorical_ci",
        query_type="g2",
        estimator="stratified_counts",
        dp_context={"mechanism": "laplace_counts", "epsilon": 0.7, "delta": 0.0},
        n_bootstrap=2000,
        readiness_target="diagnostic",
    )

    assert policy.mc_bootstrap_B == 1234
    assert policy.threshold_scope == {
        "family": "categorical_ci",
        "query_type": "g2",
        "estimator": "stratified_counts",
        "readiness_target": "diagnostic",
        "dp_mechanism": "laplace_counts",
        "dp_epsilon_bucket": "0.5_to_1.0",
        "dp_delta_bucket": "zero",
    }


def test_frozen_threshold_view_preserves_real_scoped_snapshot(tmp_path, monkeypatch) -> None:
    registry = JudgeThresholdRegistry(tmp_path / "judge_thresholds")
    generic = JudgeThresholdEntry(
        judge_name="ci_tests",
        metric_name="mc_bootstrap_B",
        threshold_value=5000,
        direction="min",
        rationale="generic CI policy",
        benchmark_source="unit_test",
        scope_family="categorical_ci",
    )
    scoped = generic.model_copy(
        update={
            "threshold_value": 6000,
            "scope_query_type": "g2",
            "scope_estimator": "stratified_counts",
            "scope_readiness_target": "diagnostic",
            "scope_dp_mechanism": "laplace_counts",
            "scope_dp_epsilon_bucket": "0.5_to_1.0",
            "scope_dp_delta_bucket": "zero",
        }
    )
    registry.record(generic)
    registry.record(scoped)
    with pytest.raises(TypeError):
        registry.frozen_view(JudgeThresholdSnapshot(entries=[]))  # type: ignore[call-arg]
    frozen = registry.frozen_view()
    scope = {
        "family": "categorical_ci",
        "query_type": "g2",
        "estimator": "stratified_counts",
        "readiness_target": "diagnostic",
        "dp_mechanism": "laplace_counts",
        "dp_epsilon": 0.7,
        "dp_delta": 0.0,
    }
    before = registry.resolve("ci_tests", **scope)
    assert before.threshold_value("mc_bootstrap_B") == pytest.approx(6000)
    assert frozen.resolve("ci_tests", **scope) == before
    assert frozen.snapshot() == registry.snapshot()
    assert isinstance(JudgeStack(threshold_registry=frozen), JudgeStack)

    detached_snapshot = frozen.snapshot()
    detached_snapshot.entries.clear()
    assert frozen.snapshot().entries
    assert frozen.resolve("ci_tests", **scope) == before

    registry.record(scoped.model_copy(update={"threshold_value": 7000}))
    assert registry.resolve("ci_tests", **scope).threshold_value("mc_bootstrap_B") == pytest.approx(
        7000
    )
    for _ in range(2):
        assert frozen.resolve("ci_tests", **scope) == before
    with pytest.raises(AttributeError, match="read-only"):
        frozen._captured_snapshot_json = registry.snapshot().model_dump_json()  # type: ignore[attr-defined]
    assert frozen.resolve("ci_tests", **scope) == before
    with pytest.raises(AttributeError, match="read-only"):
        del frozen._captured_snapshot_json  # type: ignore[attr-defined]
    assert frozen.resolve("ci_tests", **scope) == before
    assert (
        frozen.resolve_ci_test_policy(
            family="categorical_ci",
            query_type="g2",
            estimator="stratified_counts",
            dp_context={"mechanism": "laplace_counts", "epsilon": 0.7, "delta": 0.0},
        ).mc_bootstrap_B
        == 6000
    )
    with pytest.raises(RuntimeError, match="read-only"):
        frozen.record(scoped)
    with pytest.raises(RuntimeError, match="read-only"):
        frozen._write_snapshot(frozen.snapshot())
    assert frozen.resolve("ci_tests", **scope) == before
    assert registry.resolve("ci_tests", **scope).threshold_value("mc_bootstrap_B") == pytest.approx(
        7000
    )

    # Removal control: reconnect the view's intake to the live registry.
    monkeypatch.setattr(type(frozen), "_load_snapshot", lambda _self: registry.snapshot())
    assert frozen.resolve("ci_tests", **scope).threshold_value("mc_bootstrap_B") == pytest.approx(
        7000
    )


def test_frozen_empty_threshold_view_cannot_seed_live_registry(tmp_path) -> None:
    registry = JudgeThresholdRegistry(tmp_path / "judge_thresholds")
    registry._write_snapshot(JudgeThresholdSnapshot(entries=[]))
    registry_path = tmp_path / "judge_thresholds" / "judge_threshold_registry.json"
    before = registry_path.read_bytes()
    frozen = registry.frozen_view()

    with pytest.raises(RuntimeError, match="read-only"):
        frozen.seed_defaults()

    assert not frozen.snapshot().entries
    assert registry_path.read_bytes() == before


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_frozen_view_preserves_values_accepted_by_live_reader(tmp_path, value: float) -> None:
    registry = JudgeThresholdRegistry(tmp_path / "judge_thresholds")
    registry.record(
        JudgeThresholdEntry(
            judge_name="compatibility_probe",
            metric_name="threshold",
            threshold_value=1,
            direction="max",
            rationale="live reader compatibility",
            benchmark_source="unit_test",
        )
    )
    registry_path = tmp_path / "judge_thresholds" / "judge_threshold_registry.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    for entry in payload["entries"]:
        if entry["judge_name"] == "compatibility_probe":
            entry["threshold_value"] = value
    registry_path.write_text(json.dumps(payload), encoding="utf-8")

    live_value = registry.resolve("compatibility_probe").threshold_value("threshold")
    frozen_value = (
        registry.frozen_view().resolve("compatibility_probe").threshold_value("threshold")
    )
    assert live_value is not None and frozen_value is not None
    if math.isnan(value):
        assert math.isnan(live_value) and math.isnan(frozen_value)
    else:
        assert live_value == frozen_value == value
