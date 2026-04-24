"""Tests for FunnelOrchestrator."""

from __future__ import annotations

from unittest.mock import MagicMock

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.autotune.models import BenchmarkEvaluation, BenchmarkSplit
from polisyos.scientist.doe.stress_report import StressTestReport
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.search.funnel.level5_refutation_governance import (
    Level5RefutationGovernanceStage,
)
from polisyos.scientist.search.funnel.level6_promotion import Level6PromotionStage
from polisyos.scientist.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.search.funnel.types import (
    CheapSignalVector,
    FunnelStage,
    FunnelStageResult,
    TypedFailureCard,
    UncertaintyEnvelope,
)
from polisyos.scientist.search.lessons import LessonRegistry
from polisyos.scientist.search.voi_scheduler import PredictiveVOIScheduler


def _artifact_ref(seed: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{seed * 64}"[:71],
        kind="scientist.test",
        media_type="application/json",
    )


def _make_stage(
    level: int,
    name: str,
    is_promising: bool = True,
    has_blockers: bool = False,
    cheap_signal: CheapSignalVector | None = None,
    objective_value: float = 0.0,
) -> FunnelStage:
    """Create a mock FunnelStage."""
    stage = MagicMock(spec=FunnelStage)
    stage.fidelity_level = level
    stage.stage_name = name
    stage.estimated_cost_usd = 0.0

    cards = []
    if has_blockers:
        cards.append(
            TypedFailureCard(
                judge_name=name,
                failure_type="test_blocker",
                severity="blocker",
                description="test blocker",
            )
        )

    result = FunnelStageResult(
        policy_candidate={},
        objective_value=objective_value,
        is_promising=is_promising,
        stage_name=name,
        uncertainty_envelope=UncertaintyEnvelope.deterministic(),
        cheap_signal=cheap_signal,
        failure_cards=cards,
        fidelity_level=level,
    )
    stage.evaluate.return_value = result
    return stage


class TestFunnelOrchestrator:
    def test_runs_all_stages_on_passing_candidate(self):
        stages = [
            _make_stage(0, "L0"),
            _make_stage(1, "L1"),
            _make_stage(2, "L2"),
        ]
        orch = FunnelOrchestrator(stages)
        result = orch.evaluate({}, {})

        assert result.stage_name == "L2"
        for s in stages:
            s.evaluate.assert_called_once()

    def test_stops_on_blocker(self):
        stages = [
            _make_stage(0, "L0", has_blockers=True, is_promising=False),
            _make_stage(1, "L1"),
        ]
        orch = FunnelOrchestrator(stages)
        result = orch.evaluate({}, {})

        assert result.stage_name == "L0"
        assert result.has_blockers
        stages[1].evaluate.assert_not_called()

    def test_stops_on_not_promising(self):
        stages = [
            _make_stage(0, "L0"),
            _make_stage(1, "L1", is_promising=False),
            _make_stage(2, "L2"),
        ]
        orch = FunnelOrchestrator(stages)
        result = orch.evaluate({}, {})

        assert result.stage_name == "L1"
        stages[2].evaluate.assert_not_called()

    def test_respects_max_level(self):
        stages = [
            _make_stage(0, "L0"),
            _make_stage(1, "L1"),
            _make_stage(2, "L2"),
            _make_stage(3, "L3"),
        ]
        orch = FunnelOrchestrator(stages, max_level=1)
        result = orch.evaluate({}, {})

        assert result.stage_name == "L1"
        stages[2].evaluate.assert_not_called()
        stages[3].evaluate.assert_not_called()

    def test_fast_track_skips_to_final(self):
        fast_signal = CheapSignalVector(
            structural_validity=1.0,
            causal_identifiability=1.0,
            expected_value_proxy=0.95,
            feasibility=0.9,
            expected_harm_proxy=0.05,
            positivity_risk=0.1,
            uncertainty_prior=0.2,
        )
        assert fast_signal.routing_decision() == "fast_track"

        stages = [
            _make_stage(0, "L0"),
            _make_stage(1, "L1", cheap_signal=fast_signal),
            _make_stage(2, "L2"),  # should be skipped
            _make_stage(3, "L3"),  # final — should be executed
        ]
        orch = FunnelOrchestrator(stages)
        result = orch.evaluate({}, {})

        # L2 should be skipped, L3 should be executed.
        stages[2].evaluate.assert_not_called()
        stages[3].evaluate.assert_called_once()

    def test_reject_routing_stops_funnel(self):
        reject_signal = CheapSignalVector(
            structural_validity=0.3,  # triggers reject
        )
        stages = [
            _make_stage(0, "L0"),
            _make_stage(1, "L1", cheap_signal=reject_signal),
            _make_stage(2, "L2"),
        ]
        orch = FunnelOrchestrator(stages)
        result = orch.evaluate({}, {})

        assert result.is_promising is False
        stages[2].evaluate.assert_not_called()

    def test_stages_sorted_by_fidelity(self):
        """Stages should be sorted regardless of input order."""
        stages = [
            _make_stage(2, "L2"),
            _make_stage(0, "L0"),
            _make_stage(1, "L1"),
        ]
        orch = FunnelOrchestrator(stages)
        assert [s.fidelity_level for s in orch.stages] == [0, 1, 2]

    def test_empty_stages_returns_passing_result(self):
        orch = FunnelOrchestrator([])
        result = orch.evaluate({}, {})
        assert result.is_promising is True

    def test_context_enriched_with_level_results(self):
        """Each stage should receive previous stage results in context."""
        l0 = _make_stage(0, "L0")
        l1 = _make_stage(1, "L1")

        orch = FunnelOrchestrator([l0, l1])
        orch.evaluate({"key": "val"}, {})

        # L1 should have received _funnel_L0_result in context.
        l1_call_ctx = l1.evaluate.call_args[0][1]
        assert "_funnel_L0_result" in l1_call_ctx

    # ------------------------------------------------------------------
    # Adapter tests
    # ------------------------------------------------------------------

    def test_as_stage_a_callable(self):
        stages = [_make_stage(0, "L0", objective_value=0.42)]
        orch = FunnelOrchestrator(stages)
        fn = orch.as_stage_a_callable()

        score, passed = fn({}, {})
        assert score == 0.42
        assert passed is True

    def test_as_stage_b_callable(self):
        stages = [_make_stage(0, "L0")]
        orch = FunnelOrchestrator(stages)
        fn = orch.as_stage_b_callable()

        result = fn({}, {})
        assert "objective_value" in result
        assert "is_promising" in result

    def test_stage_b_reuses_cached_stage_a_progress(self):
        stages = [
            _make_stage(0, "L0"),
            _make_stage(1, "L1"),
            _make_stage(2, "L2"),
            _make_stage(3, "L3"),
        ]
        orch = FunnelOrchestrator(stages)
        stage_a = orch.as_stage_a_callable()
        stage_b = orch.as_stage_b_callable()

        score, passed = stage_a({"candidate": 1}, {})
        assert passed is True
        assert score == 0.0
        assert stages[0].evaluate.call_count == 1
        assert stages[1].evaluate.call_count == 1
        assert stages[2].evaluate.call_count == 1
        assert stages[3].evaluate.call_count == 0

        result = stage_b({"candidate": 1}, {})
        assert result["feedback"]["funnel_cache"] == "hit"
        assert stages[0].evaluate.call_count == 1
        assert stages[1].evaluate.call_count == 1
        assert stages[2].evaluate.call_count == 1
        assert stages[3].evaluate.call_count == 1

    def test_stage_b_cache_miss_falls_back_to_full_execution(self):
        stages = [
            _make_stage(0, "L0"),
            _make_stage(1, "L1"),
            _make_stage(2, "L2"),
            _make_stage(3, "L3"),
        ]
        orch = FunnelOrchestrator(stages)
        stage_b = orch.as_stage_b_callable()

        result = stage_b({"candidate": 99}, {})
        assert result["feedback"]["funnel_cache"] == "miss"
        for stage in stages:
            stage.evaluate.assert_called_once()

    def test_burn_in_policy_bypasses_cheap_rejection_until_level4(self):
        reject_signal = CheapSignalVector(structural_validity=0.3)
        stages = [
            _make_stage(0, "L0"),
            _make_stage(1, "L1", is_promising=False, cheap_signal=reject_signal),
            _make_stage(2, "L2"),
            _make_stage(4, "L4"),
        ]
        orch = FunnelOrchestrator(stages)
        ticket = orch.submit(
            {"semantic": {"interventions": [], "objectives": []}}, {"burn_in_cohort": "calibration"}
        )
        result = orch.advance(ticket, policy="burn_in")

        assert result.final_result is not None
        assert result.final_result.stage_name == "L4"
        stages[3].evaluate.assert_called_once()

    def test_records_failure_lessons_on_terminal_reject(self, tmp_path):
        store = FileSystemCAS(tmp_path / ".polisyos")
        lesson_registry = LessonRegistry(root=tmp_path / "registry" / "lessons", store=store)
        stages = [_make_stage(0, "L0", has_blockers=True, is_promising=False)]
        orch = FunnelOrchestrator(stages, lesson_registry=lesson_registry)

        outcome = orch.advance(
            orch.submit(
                {"semantic": {"interventions": [], "objectives": []}}, {"source_run_id": "run-1"}
            ),
            policy="full",
        )
        assert outcome.lesson_refs
        assert lesson_registry.top_patterns(limit=5)

    def test_records_success_lesson_on_level4_success(self, tmp_path):
        store = FileSystemCAS(tmp_path / ".polisyos")
        lesson_registry = LessonRegistry(root=tmp_path / "registry" / "lessons", store=store)
        stages = [
            _make_stage(0, "L0"),
            _make_stage(1, "L1"),
            _make_stage(2, "L2"),
            _make_stage(4, "L4"),
        ]
        orch = FunnelOrchestrator(stages, lesson_registry=lesson_registry)

        outcome = orch.advance(
            orch.submit(
                {
                    "semantic": {
                        "interventions": [{"type": "tax_reform"}],
                        "objectives": [{"name": "gdp_growth"}],
                    }
                },
                {"source_run_id": "run-1"},
            ),
            policy="full",
        )
        assert outcome.lesson_refs
        assert lesson_registry.top_patterns(limit=5)[0].kind.value == "success"

    def test_predictive_scheduler_receives_stage_observations(self):
        stages = [
            _make_stage(0, "L0"),
            _make_stage(1, "L1"),
            _make_stage(
                2,
                "L2",
                cheap_signal=CheapSignalVector(
                    expected_value_proxy=0.7,
                    expected_information_gain=0.4,
                ),
            ),
            _make_stage(4, "L4"),
        ]
        scheduler = PredictiveVOIScheduler()
        orch = FunnelOrchestrator(stages, voi_scheduler=scheduler)

        orch.evaluate({}, {"run_id": "run-1", "task_family": "policy", "domain": "fiscal"})

        snapshot = scheduler.snapshot()
        assert snapshot.observations
        assert snapshot.observations[-1].candidate_id

    def test_level5_and_level6_runtime_generalization_collects_audit_refs(self, tmp_path):
        store = FileSystemCAS(tmp_path / ".polisyos")
        stages = [
            _make_stage(0, "L0"),
            _make_stage(1, "L1"),
            _make_stage(
                2,
                "L2",
                cheap_signal=CheapSignalVector(
                    expected_value_proxy=0.8,
                    expected_information_gain=0.3,
                ),
            ),
            _make_stage(4, "L4", objective_value=0.8),
            Level5RefutationGovernanceStage(
                require_hidden_holdout=True,
            ),
            Level6PromotionStage(
                promotion_runner=lambda candidate, context: {
                    "decision": "complete",
                    "reason": "promoted_for_test",
                },
            ),
        ]
        orch = FunnelOrchestrator(stages)
        selection = BenchmarkEvaluation(
            loop_id="loop",
            suite_id="selection",
            candidate_ref=_artifact_ref("a"),
            selection_metrics={"score": 1.0},
            holdout_metrics={"score": 1.0},
            promotable=True,
            runtime_split_type=BenchmarkSplit.SELECTION,
        )
        hidden_holdout = BenchmarkEvaluation(
            loop_id="loop",
            suite_id="policy_hidden_holdout",
            candidate_ref=_artifact_ref("b"),
            selection_metrics={"score": 1.0},
            holdout_metrics={"score": 0.96},
            promotable=True,
            runtime_split_type=BenchmarkSplit.HIDDEN_HOLDOUT,
        )
        stress_report = StressTestReport(
            report_id="stress_ok",
            total_scenarios_evaluated=3,
            robustness_score=0.9,
        )
        governance_report = GovernanceReport(verdict="approve")

        outcome = orch.advance(
            orch.submit(
                {"candidate_id": "cand-1", "semantic": {"interventions": [], "objectives": []}},
                {
                    "store": store,
                    "selection_evaluation": selection,
                    "hidden_holdout_evaluation": hidden_holdout,
                    "stress_test_report": stress_report,
                    "governance_report": governance_report,
                },
            ),
            policy="full",
        )

        assert outcome.completed is True
        assert outcome.final_action == "complete"
        assert outcome.final_result is not None
        assert outcome.final_result.stage_name == "funnel_L6_promotion"
        assert outcome.audit_refs
        assert outcome.actionable_side_information_refs

    def test_level6_respects_no_promotion_degraded_mode(self, tmp_path):
        store = FileSystemCAS(tmp_path / ".polisyos")

        class _Tracker:
            def routing_mode(self) -> str:
                return "no_promotion"

            def compute_metrics(self) -> dict[str, object]:
                return {"routing_mode": "no_promotion", "promotion_ban_active": True}

        stages = [
            _make_stage(0, "L0"),
            _make_stage(1, "L1"),
            _make_stage(
                2,
                "L2",
                cheap_signal=CheapSignalVector(
                    expected_value_proxy=0.9,
                    expected_information_gain=0.2,
                ),
            ),
            _make_stage(4, "L4", objective_value=0.7),
            Level5RefutationGovernanceStage(require_hidden_holdout=False),
            Level6PromotionStage(allow_noop_complete=True),
        ]
        orch = FunnelOrchestrator(stages, correlation_tracker=_Tracker())

        outcome = orch.advance(
            orch.submit({"candidate_id": "cand-2"}, {"store": store}),
            policy="full",
        )

        assert outcome.completed is True
        assert outcome.final_action == "defer_to_human"
        assert outcome.final_result is not None
        assert outcome.final_result.feedback["funnel_action"] == "defer_to_human"

    def test_level5_blocks_runtime_split_type_mismatch(self, tmp_path):
        store = FileSystemCAS(tmp_path / ".polisyos")
        stages = [
            _make_stage(0, "L0"),
            _make_stage(1, "L1"),
            _make_stage(2, "L2"),
            _make_stage(4, "L4", objective_value=0.6),
            Level5RefutationGovernanceStage(require_hidden_holdout=True),
        ]
        orch = FunnelOrchestrator(stages)
        selection = BenchmarkEvaluation(
            loop_id="loop",
            suite_id="selection",
            candidate_ref=_artifact_ref("c"),
            selection_metrics={"score": 1.0},
            holdout_metrics={"score": 1.0},
            promotable=True,
            runtime_split_type=BenchmarkSplit.SELECTION,
        )
        hidden_holdout = BenchmarkEvaluation(
            loop_id="loop",
            suite_id="rotation_suite",
            candidate_ref=_artifact_ref("d"),
            selection_metrics={"score": 1.0},
            holdout_metrics={"score": 0.98},
            promotable=True,
            runtime_split_type=BenchmarkSplit.ROTATING_CHALLENGE,
        )

        outcome = orch.advance(
            orch.submit(
                {"candidate_id": "cand-3", "semantic": {"interventions": [], "objectives": []}},
                {
                    "store": store,
                    "selection_evaluation": selection,
                    "hidden_holdout_evaluation": hidden_holdout,
                },
            ),
            policy="full",
        )

        assert outcome.final_result is not None
        assert outcome.final_result.stage_name == "funnel_L5_refutation_governance"
        assert any(
            card.failure_type == "benchmark_split_type_mismatch" for card in outcome.failure_cards
        )
