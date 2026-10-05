"""Tests for FunnelOrchestrator."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation, BenchmarkSplit
from polisyos.scientist.methods.doe.stress_report import StressTestReport
from polisyos.scientist.methods.search.funnel.level5_refutation_governance import (
    Level5RefutationGovernanceStage,
)
from polisyos.scientist.methods.search.funnel.level6_promotion import Level6PromotionStage
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import (
    CheapSignalVector,
    FunnelStage,
    FunnelStageResult,
    TypedFailureCard,
    UncertaintyEnvelope,
)
from polisyos.scientist.methods.search.lessons import LessonRegistry
from polisyos.scientist.methods.search.voi_scheduler import PredictiveVOIScheduler
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState


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
    def test_spend_does_not_authorize_skipping_a_deferred_stage(self):
        stages = [_make_stage(0, "L0"), _make_stage(1, "L1"), _make_stage(2, "L2")]
        stages[1].evaluate.return_value.terminal_action = "defer"
        budget = BudgetState(spent={"run": Decimal("0")})
        orch = FunnelOrchestrator(stages, budget_state=budget)
        candidate = {"candidate_id": "deferred-owner"}
        ticket = orch.submit(candidate, {})
        orch.advance(ticket, policy="full")

        budget.record_spend("run", Decimal("0.01"))
        retried = orch.submit(candidate, {})
        outcome = orch.advance(retried, policy="full")

        assert retried is ticket
        assert outcome.final_action == "defer"
        stages[0].evaluate.assert_called_once()
        stages[1].evaluate.assert_called_once()
        stages[2].evaluate.assert_not_called()

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

    def test_empty_stages_returns_not_evaluated_result(self):
        orch = FunnelOrchestrator([])
        result = orch.evaluate({}, {})
        assert result.is_promising is False
        assert result.objective_value == float("inf")
        assert result.feedback["verdict"] == "NOT_EVALUATED"

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

    def test_submit_cache_is_scoped_to_effective_context(self):
        stage = _make_stage(0, "L0")

        def evaluate(candidate, context):
            dataset_scores = {"dataset-v1": 1.0, "dataset-v2": 2.0}
            return FunnelStageResult(
                policy_candidate=dict(candidate),
                objective_value=dataset_scores[context["dataset_version"]],
                is_promising=True,
                stage_name="L0",
                uncertainty_envelope=UncertaintyEnvelope.deterministic(),
                fidelity_level=0,
            )

        stage.evaluate.side_effect = evaluate
        orch = FunnelOrchestrator([stage])
        candidate = {"candidate_id": "same-candidate"}
        context_v1 = {
            "dataset_version": "dataset-v1",
            "model_version": "model-v1",
            "evaluation_role": "ordinary",
        }
        context_v2 = {
            "dataset_version": "dataset-v2",
            "model_version": "model-v1",
            "evaluation_role": "ordinary",
        }

        ticket_v1 = orch.submit(candidate, context_v1)
        outcome_v1 = orch.advance(ticket_v1, policy="full")
        ticket_v2 = orch.submit(candidate, context_v2)
        outcome_v2 = orch.advance(ticket_v2, policy="full")

        assert ticket_v2 is not ticket_v1
        assert outcome_v2.ticket_id != outcome_v1.ticket_id
        assert outcome_v1.final_result is not None
        assert outcome_v2.final_result is not None
        assert outcome_v1.final_result.objective_value == 1.0
        assert outcome_v2.final_result.objective_value == 2.0

        cached_ticket = orch.submit(candidate, context_v1)
        assert cached_ticket is ticket_v1
        assert cached_ticket.submitted_via_cache is True
        assert stage.evaluate.call_count == 2

    def test_budget_continuation_requires_improved_capacity_and_preserves_progress(self):
        class _Tracker:
            mode = "normal"

            def routing_mode(self) -> str:
                return self.mode

            def compute_metrics(self) -> dict[str, object]:
                return {"routing_mode": self.mode}

        stages = [
            _make_stage(0, "L0"),
            _make_stage(1, "L1"),
            _make_stage(
                2,
                "L2",
                cheap_signal=CheapSignalVector(expected_value_proxy=0.8),
            ),
            _make_stage(3, "L3"),
        ]
        for stage, cost in zip(stages[:3], (0.1, 0.2, 0.3), strict=True):
            stage.evaluate.return_value.compute_actual_usd = cost
        stages[3].estimated_cost_usd = 1.0
        tracker = _Tracker()
        budget = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("0.5"))})
        orch = FunnelOrchestrator(
            stages,
            budget_state=budget,
            correlation_tracker=tracker,
        )
        candidate = {"candidate_id": "freeze-continuation"}
        context = {"dataset_version": "dataset-v1"}

        ticket = orch.submit(candidate, context)
        outcome = orch.advance(ticket, policy="full")

        assert outcome.final_action == "defer"
        assert ticket.last_scheduling_decision is not None
        assert ticket.last_scheduling_decision.recommended_action == "defer"
        prior_stage_results = dict(ticket.stage_results)
        prior_trace = list(ticket.trace)
        prior_cost = sum(step.compute_actual_usd for step in ticket.trace)

        tracker.mode = "freeze_frontier"
        assert orch.submit(candidate, context) is ticket
        tracker.mode = "normal"
        budget.limits["run"].max_usd = Decimal("5")
        successor = orch.submit(candidate, context)

        assert successor is not ticket
        assert successor.parent_ticket_id == ticket.ticket_id
        assert successor.lineage[:-1] == ticket.lineage
        assert successor.continuation_reason is not None
        assert successor.stage_results == prior_stage_results
        assert successor.trace == prior_trace
        assert sum(step.compute_actual_usd for step in successor.trace) == prior_cost

    def test_retry_cheaper_continuation_preserves_partial_progress(self):
        stages = [
            _make_stage(0, "L0"),
            _make_stage(1, "L1"),
            _make_stage(
                2,
                "L2",
                cheap_signal=CheapSignalVector(expected_value_proxy=0.8),
            ),
            _make_stage(4, "L4"),
        ]
        for stage, cost in zip(stages[:3], (0.1, 0.2, 0.3), strict=True):
            stage.evaluate.return_value.compute_actual_usd = cost
        stages[2].evaluate.return_value.feedback["timeout_risk"] = 0.9
        budget = BudgetState(spent={"run": Decimal("0")})
        orch = FunnelOrchestrator(stages, budget_state=budget)
        candidate = {"candidate_id": "retry-continuation"}
        context = {"dataset_version": "dataset-v1"}

        ticket = orch.submit(candidate, context)
        outcome = orch.advance(ticket, policy="full")

        assert outcome.final_action == "retry_cheaper"
        assert ticket.last_scheduling_decision is not None
        assert ticket.last_scheduling_decision.recommended_action == "retry_cheaper"
        prior_stage_results = dict(ticket.stage_results)
        prior_trace = list(ticket.trace)
        prior_cost = sum(step.compute_actual_usd for step in ticket.trace)

        budget.record_spend("run", Decimal("0.01"))
        successor = orch.submit(candidate, context)

        assert successor is ticket
        assert successor.parent_ticket_id is None
        assert successor.lineage == ticket.lineage
        assert successor.continuation_reason is None
        assert successor.stage_results == prior_stage_results
        assert successor.trace == prior_trace
        assert sum(step.compute_actual_usd for step in successor.trace) == prior_cost

    def test_stage_defer_continuation_without_scheduler_decision(self):
        stages = [_make_stage(0, "L0"), _make_stage(1, "L1"), _make_stage(2, "L2")]
        for stage, cost in zip(stages[:2], (0.1, 0.2), strict=True):
            stage.evaluate.return_value.compute_actual_usd = cost
        stages[1].evaluate.return_value.terminal_action = "defer"
        budget = BudgetState(spent={"run": Decimal("0")})
        orch = FunnelOrchestrator(stages, budget_state=budget)
        candidate = {"candidate_id": "stage-defer-continuation"}
        context = {"dataset_version": "dataset-v1"}

        ticket = orch.submit(candidate, context)
        outcome = orch.advance(ticket, policy="full")

        assert outcome.final_action == "defer"
        assert ticket.last_scheduling_decision is None
        prior_stage_results = dict(ticket.stage_results)
        prior_trace = list(ticket.trace)
        prior_cost = sum(step.compute_actual_usd for step in ticket.trace)

        budget.record_spend("run", Decimal("0.01"))
        successor = orch.submit(candidate, context)

        assert successor is ticket
        assert successor.parent_ticket_id is None
        assert successor.lineage == ticket.lineage
        assert successor.continuation_reason is None
        assert successor.stage_results == prior_stage_results
        assert successor.trace == prior_trace
        assert sum(step.compute_actual_usd for step in successor.trace) == prior_cost

    def test_interleaved_context_continuation_uses_exact_context_predecessor(self):
        stages = [_make_stage(0, "L0"), _make_stage(1, "L1"), _make_stage(2, "L2")]

        def evaluate_stage(candidate, context, *, level):
            is_context_a = context["dataset_version"] == "dataset-a"
            return FunnelStageResult(
                policy_candidate=dict(candidate),
                objective_value=1.0 if is_context_a else 2.0,
                is_promising=True,
                stage_name=f"{context['dataset_version']}-L{level}",
                uncertainty_envelope=UncertaintyEnvelope.deterministic(),
                compute_actual_usd=0.1 if is_context_a else 0.2,
                fidelity_level=level,
                terminal_action="defer" if level == 1 else None,
            )

        stages[0].evaluate.side_effect = lambda candidate, context: evaluate_stage(
            candidate, context, level=0
        )
        stages[1].evaluate.side_effect = lambda candidate, context: evaluate_stage(
            candidate, context, level=1
        )
        budget = BudgetState(spent={"run": Decimal("0")})
        orch = FunnelOrchestrator(stages, budget_state=budget)
        candidate = {"candidate_id": "interleaved-continuation"}
        context_a = {"dataset_version": "dataset-a"}
        context_b = {"dataset_version": "dataset-b"}

        ticket_a = orch.submit(candidate, context_a)
        outcome_a = orch.advance(ticket_a, policy="full")
        assert outcome_a.final_action == "defer"
        prior_a_results = dict(ticket_a.stage_results)
        prior_a_trace = list(ticket_a.trace)
        prior_a_cost = sum(step.compute_actual_usd for step in ticket_a.trace)

        ticket_b = orch.submit(candidate, context_b)
        outcome_b = orch.advance(ticket_b, policy="full")
        assert outcome_b.final_action == "defer"
        assert ticket_b.stage_results[1].objective_value == 2.0

        budget.record_spend("run", Decimal("0.01"))
        successor_a = orch.submit(candidate, context_a)

        assert successor_a is ticket_a
        assert successor_a.parent_ticket_id is None
        assert successor_a is not ticket_b
        assert successor_a.lineage == ticket_a.lineage
        assert successor_a.stage_results == prior_a_results
        assert successor_a.stage_results[1].objective_value == 1.0
        assert successor_a.trace == prior_a_trace
        assert sum(step.compute_actual_usd for step in successor_a.trace) == prior_a_cost

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


def _bootstrap_workflow(observations):
    """Use the real loop engine and Foundry bootstrap on bounded synthetic data."""
    import numpy as np

    from polisyos.foundry.methods.catalog.causal.ci_backends import bootstrap_mean_interval
    from polisyos.scientist.orchestration.workflows import SimpleLoopEngine

    def estimate(state):
        data = np.asarray(state["data"], dtype=float)
        fraction = state["data_config"]["subsample_fraction"]
        sample = data[: max(2, int(len(data) * fraction))]
        draws = state["estimation_config"]["n_bootstrap"]
        low, high = bootstrap_mean_interval(sample, seed=17, draws=draws)
        observations.append((len(sample), draws, low, high))
        return {
            **state,
            "simulation_results": {
                "ate": float(sample.mean()),
                "gdp_change": float(sample.mean()),
                "gov_balance": 0.0,
                "bootstrap": {"ci_width": high - low},
            },
            "feedback": {"verdict": "APPROVE"},
        }

    return SimpleLoopEngine([("estimate", estimate)], terminal_node="estimate")


def _bootstrap_context():
    return {
        "data": list(range(1, 121)),
        "dataset_version": "bounded-synthetic-120-v1",
        "model_version": "mean-bootstrap-v1",
        "evaluation_role": "ordinary",
        "data_config": {"subsample_fraction": 1.0},
        "estimation_config": {"n_bootstrap": 120},
        "model_config": {"scm_complexity": "full"},
    }


def test_real_workflow_full_and_split_recheck_budget_before_l3():
    from polisyos.scientist.methods.search.funnel.level2_causal import Level2CausalPlausibility
    from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity
    from polisyos.scientist.methods.search.funnel.level4_full import Level4FullFidelity

    for split in (False, True):
        observations = []
        engine = _bootstrap_workflow(observations)
        budget = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("0.01"))})
        orch = FunnelOrchestrator(
            [Level2CausalPlausibility(), Level3MediumFidelity(engine), Level4FullFidelity(engine)],
            budget_state=budget,
        )
        candidate, context = {"candidate_id": "real-continuation"}, _bootstrap_context()
        ticket = orch.submit(candidate, context)
        if split:
            orch.as_stage_a_callable()(candidate, context)
            orch.as_stage_b_callable()(candidate, context)
            outcome = orch.get_outcome(ticket)
        else:
            outcome = orch.advance(ticket, policy="full")
        assert outcome.final_action == "defer"
        assert list(outcome.stage_results) == [2]
        assert observations == []
        assert outcome.last_scheduling_decision.reason == "budget_exhausted_for_next_level"
        prior_cost = outcome.compute_actual_usd

        assert orch.submit(candidate, context) is ticket
        budget.record_spend("run", Decimal("0.001"))
        assert orch.submit(candidate, context) is ticket
        assert observations == []
        budget.limits["run"].max_usd = Decimal("10")
        successor = orch.submit(candidate, context)
        assert successor is not ticket
        assert successor.parent_ticket_id == ticket.ticket_id
        assert successor.stage_results[2] is ticket.stage_results[2]
        assert orch.get_outcome(successor).compute_actual_usd == prior_cost
        resumed = orch.advance(successor, policy="full")
        assert list(resumed.stage_results) == [2, 3, 4]
        assert resumed.final_action == "complete"
        assert resumed.last_scheduling_decision.recommended_action == "advance"
        assert [(n, draws) for n, draws, _, _ in observations] == [(24, 50), (120, 120)]
        assert ticket.final_action == "defer"


def test_real_workflow_context_roles_do_not_reuse_or_mutate_ordinary_attempt():
    from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity

    observations = []
    orch = FunnelOrchestrator([Level3MediumFidelity(_bootstrap_workflow(observations))])
    candidate, context = {"candidate_id": "real-role"}, _bootstrap_context()
    ordinary = orch.submit(candidate, context)
    first = orch.advance(ordinary, policy="full")
    assert orch.submit(candidate, {**context, "request_id": "repeat"}) is ordinary
    for changed in (
        {**context, "evaluation_role": "calibration"},
        {**context, "calibration_role": "independent_control"},
        {**context, "dataset_version": "bounded-synthetic-120-v2"},
    ):
        ticket = orch.submit(candidate, changed)
        assert ticket is not ordinary
        orch.advance(ticket, policy="full")
    sentinel = orch.submit({**candidate, "__sentinel__": {"sentinel_id": "control-1"}}, context)
    orch.advance(sentinel, policy="full")
    assert len(observations) == 5
    assert not ordinary.context.get("is_sentinel")
    assert ordinary.context["evaluation_role"] == "ordinary"
    assert orch.get_outcome(ordinary).trace == first.trace


def test_real_bootstrap_l3_then_l4_matches_direct_full_config_and_audit_readback(tmp_path):
    from copy import deepcopy

    from polisyos.scientist.methods.search.actionable_side_information import (
        load_actionable_side_information,
    )
    from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity
    from polisyos.scientist.methods.search.funnel.level4_full import Level4FullFidelity

    context = _bootstrap_context()
    original = deepcopy(context)
    store = FileSystemCAS(tmp_path / "audit")
    candidate = {"candidate_id": "full-config"}
    direct_observations, chained_observations = [], []
    direct = Level4FullFidelity(_bootstrap_workflow(direct_observations)).evaluate(
        candidate, context
    )
    orch = FunnelOrchestrator(
        [
            Level3MediumFidelity(_bootstrap_workflow(chained_observations)),
            Level4FullFidelity(_bootstrap_workflow(chained_observations)),
        ]
    )
    output = orch.as_stage_b_callable()(candidate, {**context, "store": store})
    full = output["_funnel_outcome"].stage_results[4]
    medium = output["_funnel_outcome"].stage_results[3]
    assert context == original
    assert direct_observations == [chained_observations[1]]
    assert [(n, draws) for n, draws, _, _ in chained_observations] == [(24, 50), (120, 120)]
    assert medium.simulation_results != full.simulation_results
    assert full.simulation_results == direct.simulation_results
    assert output["objective_value"] == direct.objective_value
    assert output["feedback"]["verdict"] == "APPROVE"
    assert output["_funnel_outcome"].final_action == "complete"
    audit = load_actionable_side_information(store, full.actionable_side_information_ref)
    assert audit.candidate_id == candidate["candidate_id"]
    assert audit.metadata["approved"] is True


def test_real_workflow_zero_empty_and_capped_aggregate_projection():
    from polisyos.scientist.methods.search.funnel.level4_full import Level4FullFidelity

    observations = []
    stage = Level4FullFidelity(_bootstrap_workflow(observations))
    context = {**_bootstrap_context(), "data": [0.0] * 120}
    candidate = {"candidate_id": "true-zero"}
    evaluated = FunnelOrchestrator([stage]).as_stage_b_callable()(candidate, context)
    assert evaluated["objective_value"] == 0.0
    assert evaluated["feedback"]["verdict"] == "APPROVE"
    for orch in (FunnelOrchestrator([]), FunnelOrchestrator([stage], max_level=2)):
        output = orch.as_stage_b_callable()(candidate, context)
        assert output["feedback"]["verdict"] == "NOT_EVALUATED"
        assert not output["is_promising"]
        assert output["objective_value"] != 0.0
        assert output["_funnel_outcome"].stage_results == {}
        assert output["_funnel_outcome"].evaluation_status == "not_evaluated"
    assert len(observations) == 1


def test_real_workflow_ci_width_and_optional_stage_verdict_do_not_grant_promotion():
    from polisyos.ir import UncertaintyType
    from polisyos.scientist.methods.search.funnel.level4_full import Level4FullFidelity
    from polisyos.scientist.orchestration.workflows import SimpleLoopEngine

    for width, method in (
        (None, "ci_width_missing"),
        ("broken", "ci_width_invalid"),
        (0.0, "full_fidelity_bootstrap"),
        (0.4, "full_fidelity_bootstrap"),
    ):
        for supplied_verdict in (True, False):

            def estimate(state, width=width, supplied_verdict=supplied_verdict):
                feedback = {"verdict": "APPROVE"} if supplied_verdict else {}
                # ExpensiveStage itself requires APPROVE to mark a stage promising.
                # Keep the numerical evidence fixed when the optional field changes.
                return {
                    **state,
                    "simulation_results": {
                        "ate": 2.0,
                        "gdp_change": 2.0,
                        "bootstrap": {"ci_width": width},
                    },
                    "feedback": feedback,
                }

            engine = SimpleLoopEngine([("estimate", estimate)], terminal_node="estimate")
            stage = Level4FullFidelity(engine)
            result = stage.evaluate({}, {})
            estimate_value = result.uncertainty_envelope.uncertainties[UncertaintyType.STATISTICAL]
            assert estimate_value.quantification_method == method
            assert result.simulation_results["ate"] == 2.0
            assert estimate_value.level == (
                1.0 if width is None or width == "broken" else width / 4
            )


def test_real_l2_defer_projection_is_independent_of_optional_stage_verdict():
    from dataclasses import replace

    from polisyos.scientist.methods.search.funnel.level2_causal import Level2CausalPlausibility
    from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity

    projections = []
    for verdict in (None, "APPROVE"):

        class StageWithOptionalVerdict(Level2CausalPlausibility):
            def evaluate(self, candidate, context, verdict=verdict):
                result = super().evaluate(candidate, context)
                feedback = dict(result.feedback)
                if verdict is not None:
                    feedback["verdict"] = verdict
                return replace(result, feedback=feedback)

        observations = []
        budget = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("0.001"))})
        orch = FunnelOrchestrator(
            [StageWithOptionalVerdict(), Level3MediumFidelity(_bootstrap_workflow(observations))],
            budget_state=budget,
        )
        output = orch.as_stage_b_callable()(
            {"candidate_id": "optional-verdict"}, _bootstrap_context()
        )
        assert output["feedback"]["stage_verdict"] == verdict
        assert output["_funnel_result"].is_promising
        assert output["feedback"]["verdict"] == "DEFER"
        assert not output["is_promising"]
        assert output["_funnel_outcome"].final_action == "defer"
        assert observations == []
        projections.append((output["objective_value"], output["feedback"]["verdict"]))
    assert projections[0] == projections[1]


def test_semantic_rule_and_time_basis_changes_do_not_reuse_terminal_uncertainty():
    from datetime import UTC, date, datetime

    from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity

    for key in (
        "subject_id",
        "value_slot",
        "input_signature",
        "procedure_id",
        "rule_version",
        "population_scope",
        "valid_at",
        "rule_effective_at",
        "observation_timestamp",
    ):
        observations = []
        orch = FunnelOrchestrator([Level3MediumFidelity(_bootstrap_workflow(observations))])
        candidate = {"candidate_id": "scope-time-control"}
        context = {**_bootstrap_context(), key: "basis-a"}
        first = orch.submit(candidate, context)
        initial = orch.advance(first, policy="full")
        changed = orch.submit(candidate, {**context, key: "basis-b"})
        assert changed is not first, key
        assert changed.stage_results == {}, key
        orch.advance(changed, policy="full")
        assert len(observations) == 2, key
        assert orch.get_outcome(first).trace == initial.trace
    for first_time, next_time in (
        (date(2026, 10, 1), date(2026, 10, 2)),
        (datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 10, 2, tzinfo=UTC)),
        (datetime(2026, 10, 1), datetime(2026, 10, 2)),
    ):
        for nested in (False, True):
            observations = []
            orch = FunnelOrchestrator([Level3MediumFidelity(_bootstrap_workflow(observations))])
            candidate, context = {"candidate_id": "typed-time"}, _bootstrap_context()
            changed_context = dict(context)
            if nested:
                context["evaluation_config"] = {"valid_at": first_time}
                changed_context["evaluation_config"] = {"valid_at": next_time}
            else:
                context["valid_at"] = first_time
                changed_context["valid_at"] = next_time
            first = orch.submit(candidate, context)
            orch.advance(first, policy="full")
            changed = orch.submit(candidate, changed_context)
            assert changed is not first
            assert changed.stage_results == {}
            orch.advance(changed, policy="full")
            assert len(observations) == 2
            assert orch.submit(candidate, context) is first


def test_real_workflow_calibration_pairs_reopen_with_consistent_routing_and_publication_cap(
    tmp_path,
):
    from polisyos.scientist.methods.search.calibration_report import (
        FunnelCalibrationReport,
        load_funnel_calibration_report,
        persist_funnel_calibration_report,
    )
    from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity
    from polisyos.scientist.methods.search.funnel.level4_full import Level4FullFidelity
    from polisyos.scientist.methods.search.stages import CorrelationTracker
    from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
        _resolve_runtime_correlation_tracker,
    )

    for relation in ("empty", "aligned", "opposite"):
        store = FileSystemCAS(tmp_path / relation)
        tracker = CorrelationTracker()
        if relation != "empty":
            for index in range(3):
                observations = []
                engine = _bootstrap_workflow(observations)
                cheap_context = {
                    **_bootstrap_context(),
                    "data": list(range(1 + index, 121 + index)),
                }
                expensive_index = index if relation == "aligned" else 2 - index
                full_context = {
                    **_bootstrap_context(),
                    "data": list(range(1 + expensive_index, 121 + expensive_index)),
                }
                candidate = {"candidate_id": f"paired-{index}"}
                cheap = Level3MediumFidelity(engine).evaluate(candidate, cheap_context)
                full = Level4FullFidelity(engine).evaluate(candidate, full_context)
                tracker.record(cheap, full, f"paired-{index}")
        expected = tracker.compute_metrics()
        report = FunnelCalibrationReport(
            current_mode=tracker.routing_mode(),
            routing_health=expected,
            metadata={
                "correlation_tracker_snapshot": tracker.to_snapshot().model_dump(mode="json")
            },
        )
        report_ref = persist_funnel_calibration_report(store, report)
        reopened_store = FileSystemCAS(tmp_path / relation)
        restored = _resolve_runtime_correlation_tracker(
            load_funnel_calibration_report(reopened_store, report_ref)
        )
        assert restored is not None
        assert restored.compute_metrics() == expected
        assert restored.routing_mode() == expected["routing_mode"]
        assert expected["sample_count"] == (0 if relation == "empty" else 3)
        assert expected["calibration_state"] == (
            "not_established" if relation == "empty" else "observed"
        )
        assert expected["routing_mode"] == ("normal" if relation == "aligned" else "no_promotion")
        calls = []
        orch = FunnelOrchestrator(
            [
                Level6PromotionStage(
                    promotion_runner=lambda *args, calls=calls: calls.append("write")
                )
            ],
            correlation_tracker=restored,
        )
        outcome = orch.advance(orch.submit({"candidate_id": relation}, {}), policy="full")
        if relation != "aligned":
            assert calls == []
            assert outcome.final_action == "defer_to_human"


def test_datetime_input_reaches_real_workflow_instead_of_stale_terminal_score():
    from datetime import UTC, datetime

    from polisyos.scientist.methods.search.funnel.level4_full import Level4FullFidelity
    from polisyos.scientist.orchestration.workflows import SimpleLoopEngine

    observed_days = []

    def estimate(state):
        day = state["valid_at"].day
        observed_days.append(day)
        return {
            **state,
            "simulation_results": {"gdp_change": float(day)},
            "feedback": {"verdict": "APPROVE"},
        }

    orch = FunnelOrchestrator([Level4FullFidelity(SimpleLoopEngine([("estimate", estimate)]))])
    candidate = {"candidate_id": "dated-effect"}
    first_context = {"valid_at": datetime(2026, 10, 1, tzinfo=UTC)}
    first = orch.submit(candidate, first_context)
    first_outcome = orch.advance(first, policy="full")
    second = orch.submit(candidate, {"valid_at": datetime(2026, 10, 2, tzinfo=UTC)})
    second_outcome = orch.advance(second, policy="full")
    assert second is not first
    assert first_outcome.final_result.objective_value == -1.0
    assert second_outcome.final_result.objective_value == -2.0
    assert observed_days == [1, 2]
    assert orch.submit(candidate, first_context) is first


def test_routing_budget_snapshot_does_not_establish_actual_spend_bridge():
    """Bounded divergent control: reported stage cost does not charge its caller budget."""
    from polisyos.scientist.methods.search.funnel.level4_full import Level4FullFidelity

    budget = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))})
    orch = FunnelOrchestrator(
        [Level4FullFidelity(_bootstrap_workflow([]), estimated_cost_usd=1.0)],
        budget_state=budget,
    )
    outcome = orch.advance(orch.submit({"candidate_id": "spend-boundary"}, _bootstrap_context()))
    assert outcome.compute_actual_usd >= 1.0
    assert budget.remaining("run") == Decimal("5")
    assert budget.spent == {}
