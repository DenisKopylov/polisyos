"""Capture thresholds the real judges actually ask their registry to resolve."""

from __future__ import annotations

from polisyos.core.artifacts import FileSystemCAS
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.search.judge_stack import (
    JudgeInputBundle,
    JudgeStack,
    _hidden_holdout_degradation_card_with_threshold,
    capture_judge_validation_profiles,
)
from polisyos.scientist.methods.search.judge_thresholds import (
    JudgeThresholdEntry,
    JudgeThresholdRegistry,
    capture_judge_threshold_requirements,
)
from polisyos.scientist.policy_design.schema import persist_policy_candidate_schema
from tests.unit.scientist.search.test_phase_b_policy_runtime import _benchmark, _candidate


def _registry_without(tmp_path, metric_name: str) -> JudgeThresholdRegistry:
    registry = JudgeThresholdRegistry(root=tmp_path / "registry")
    current = registry.snapshot()
    registry._write_snapshot(
        current.model_copy(
            update={
                "entries": [entry for entry in current.entries if entry.metric_name != metric_name]
            }
        )
    )
    return registry


def test_real_judges_record_missing_selected_threshold_without_promoting(tmp_path) -> None:
    registry = _registry_without(tmp_path, "statistical_uncertainty_level")
    store = FileSystemCAS(tmp_path / "cas")
    bundle = JudgeInputBundle(
        candidate=_candidate(),
        governance_report=GovernanceReport(verdict="human_gate"),
        compute_cost_usd=1,
        timeout_risk=0.2,
        evaluation_promotable_source=False,
        run_id="synthetic-threshold-requirements",
    )
    with capture_judge_threshold_requirements() as required:
        verdict = JudgeStack(
            threshold_registry=registry.frozen_view(), store=store
        ).evaluate_phase5_preflight(bundle)
    assert len(verdict.per_judge) == 6 and verdict.composite_decision == "defer_to_human"
    statistical = [item for item in required if item.metric_name == "statistical_uncertainty_level"]
    assert len(statistical) == 1
    assert statistical[0].judge_name == "statistical"
    assert statistical[0].source == "missing"
    assert statistical[0].fallback_rule is None
    assert statistical[0].fallback_value is None
    compute = [item for item in required if item.metric_name == "timeout_risk"]
    assert len(compute) == 1 and compute[0].source == "registry"


def test_real_holdout_rule_records_its_existing_fallback_when_registry_entry_missing(
    tmp_path,
) -> None:
    registry = _registry_without(tmp_path, "hidden_holdout_degradation")
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    selection, holdout = _benchmark(candidate_ref, holdout_score=0.70)
    bundle = JudgeInputBundle(
        candidate=candidate,
        benchmark_evaluation=selection,
        hidden_holdout_evaluation=holdout,
    )
    with capture_judge_threshold_requirements() as required:
        card = _hidden_holdout_degradation_card_with_threshold(
            bundle, registry.resolve("robustness", family="causal_core")
        )
    assert card is not None and card.failure_type == "hidden_holdout_degradation"
    assert len(required) == 1
    assert required[0].metric_name == "hidden_holdout_degradation"
    assert required[0].source == "fallback"
    assert required[0].fallback_rule == "hidden_holdout_degradation_max_0.10"
    assert required[0].fallback_value == 0.10


def test_holdout_records_registry_and_existing_stricter_fallback_together(tmp_path) -> None:
    registry = _registry_without(tmp_path, "hidden_holdout_degradation")
    registry.record(
        JudgeThresholdEntry(
            judge_name="robustness",
            metric_name="hidden_holdout_degradation",
            threshold_value=0.20,
            direction="max",
            rationale="synthetic test",
            benchmark_source="test_only",
        )
    )
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    selection, holdout = _benchmark(candidate_ref, holdout_score=0.80)
    bundle = JudgeInputBundle(
        candidate=candidate,
        benchmark_evaluation=selection,
        hidden_holdout_evaluation=holdout,
    )
    with capture_judge_threshold_requirements() as required:
        card = _hidden_holdout_degradation_card_with_threshold(
            bundle, registry.resolve("robustness", family="causal_core")
        )
    assert card is not None and card.failure_type == "hidden_holdout_degradation"
    assert len(required) == 1 and required[0].source == "registry"
    assert required[0].selected_entry is not None
    assert required[0].selected_entry.threshold_value == 0.20
    assert required[0].fallback_rule == "hidden_holdout_degradation_max_0.10"
    assert required[0].fallback_value == 0.10


def test_real_judge_records_the_profile_actually_given_to_governance_passes(
    tmp_path, monkeypatch
) -> None:
    import polisyos.scientist.methods.search.judge_stack as owner

    registry = _registry_without(tmp_path, "unused_synthetic_metric")
    store = FileSystemCAS(tmp_path / "cas")
    bundle = JudgeInputBundle(
        candidate=_candidate(), governance_report=GovernanceReport(verdict="human_gate")
    )
    stack = JudgeStack(threshold_registry=registry.frozen_view(), store=store)
    with capture_judge_validation_profiles() as profiles:
        stack.evaluate_phase5_preflight(bundle)
    governance = next(
        profile
        for profile in profiles
        if set(profile.pass_ids)
        == {"budget", "equity", "privacy", "pii_check", "human_review_required", "legal"}
    )
    assert governance.level == "strict"
    assert governance.short_circuit_on_blocker is False
    original = dict(governance.thresholds)["budget_ratio"]
    monkeypatch.setitem(owner._STRICT_PROFILE.thresholds, "budget_ratio", original + 0.01)
    with capture_judge_validation_profiles() as changed_profiles:
        stack.evaluate_phase5_preflight(bundle)
    changed = next(
        profile for profile in changed_profiles if profile.pass_ids == governance.pass_ids
    )
    assert dict(changed.thresholds)["budget_ratio"] == original + 0.01
    assert dict(governance.thresholds)["budget_ratio"] == original
