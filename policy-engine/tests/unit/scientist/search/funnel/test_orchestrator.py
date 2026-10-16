"""Tests for FunnelOrchestrator."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation, BenchmarkSplit
from polisyos.scientist.methods.doe.designs import (
    AdversarialPlan,
    AdversarialStrategy,
    ParameterSpec,
)
from polisyos.scientist.methods.doe.stress_report import StressTestReport
from polisyos.scientist.methods.search.adversarial import run_stress_test
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
from polisyos.scientist.methods.search.objective import (
    BaseObjective,
    CompositeObjective,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.transfer_context import TransferContext
from polisyos.scientist.methods.search.voi_scheduler import PredictiveVOIScheduler
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)


def _artifact_ref(seed: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{seed * 64}"[:71],
        kind="scientist.test",
        media_type="application/json",
    )


class _L5FixtureUtilityObjective(BaseObjective):
    """Deterministic objective for a source-bound finite stress fixture."""

    @property
    def name(self) -> str:
        return "utility"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MINIMIZE

    def _extract_value(self, results: dict[str, object]) -> float:
        raw_value = results["utility"]
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise TypeError("utility must be a numeric fixture result")
        return float(raw_value)


def _persist_l5_l6_candidate(store: FileSystemCAS) -> ArtifactRef:
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_funnel_l5_l6", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(policy_id="policy_funnel_l5_l6"),
        model_spec=ModelSpec(model_id="model_funnel_l5_l6", data_snapshot_ref="sha256:" + "3" * 64),
    )
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        bundle, candidate_id="candidate_funnel_l5_l6"
    )
    return persist_policy_candidate_schema(store, candidate, return_selected_profile=True)


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
    def test_unknown_stage_cost_stays_unknown_in_trace_and_outcome(self):
        stage = _make_stage(0, "L0")
        orchestrator = FunnelOrchestrator([stage])

        ticket = orchestrator.submit({}, {})
        outcome = orchestrator.advance(ticket, target_level=0)

        assert outcome.trace[0].compute_cost_usd is None
        assert outcome.trace[0].compute_cost_origin == "unknown"
        assert outcome.compute_cost_usd is None
        assert outcome.compute_cost_origin == "unknown"
        assert outcome.stage_results[0].compute_cost_usd is None

    def test_unknown_cost_status_survives_policy_runtime_serialization(self):
        from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
            _serialize_funnel_outcome,
        )

        orchestrator = FunnelOrchestrator([_make_stage(0, "L0")])
        outcome = orchestrator.advance(orchestrator.submit({}, {}), target_level=0)

        payload = _serialize_funnel_outcome(outcome)

        assert payload["compute_cost_usd"] is None
        assert payload["compute_cost_origin"] == "unknown"
        assert payload["trace"][0]["compute_cost_usd"] is None
        assert payload["trace"][0]["compute_cost_origin"] == "unknown"
        assert payload["stage_results"]["0"]["compute_cost_usd"] is None
        assert payload["stage_results"]["0"]["compute_cost_origin"] == "unknown"

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

    def test_freeze_mode_continuation_preserves_partial_progress(self):
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
            stage.evaluate.return_value.compute_cost_usd = cost
            stage.evaluate.return_value.compute_cost_origin = "estimated"
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
        prior_cost = sum(step.compute_cost_usd or 0.0 for step in ticket.trace)

        tracker.mode = "freeze_frontier"
        successor = orch.submit(candidate, context)

        assert successor is not ticket
        assert successor.parent_ticket_id == ticket.ticket_id
        assert successor.lineage[:-1] == ticket.lineage
        assert successor.continuation_reason is not None
        assert successor.stage_results == prior_stage_results
        assert successor.trace == prior_trace
        assert sum(step.compute_cost_usd or 0.0 for step in successor.trace) == prior_cost

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
            stage.evaluate.return_value.compute_cost_usd = cost
            stage.evaluate.return_value.compute_cost_origin = "estimated"
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
        prior_cost = sum(step.compute_cost_usd or 0.0 for step in ticket.trace)

        budget.record_spend("run", Decimal("0.01"))
        successor = orch.submit(candidate, context)

        assert successor is not ticket
        assert successor.parent_ticket_id == ticket.ticket_id
        assert successor.lineage[:-1] == ticket.lineage
        assert successor.continuation_reason is not None
        assert successor.stage_results == prior_stage_results
        assert successor.trace == prior_trace
        assert sum(step.compute_cost_usd or 0.0 for step in successor.trace) == prior_cost

    def test_stage_defer_continuation_without_scheduler_decision(self):
        stages = [_make_stage(0, "L0"), _make_stage(1, "L1"), _make_stage(2, "L2")]
        for stage, cost in zip(stages[:2], (0.1, 0.2), strict=True):
            stage.evaluate.return_value.compute_cost_usd = cost
            stage.evaluate.return_value.compute_cost_origin = "estimated"
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
        prior_cost = sum(step.compute_cost_usd or 0.0 for step in ticket.trace)

        budget.record_spend("run", Decimal("0.01"))
        successor = orch.submit(candidate, context)

        assert successor is not ticket
        assert successor.parent_ticket_id == ticket.ticket_id
        assert successor.lineage[:-1] == ticket.lineage
        assert successor.continuation_reason is not None
        assert successor.stage_results == prior_stage_results
        assert successor.trace == prior_trace
        assert sum(step.compute_cost_usd or 0.0 for step in successor.trace) == prior_cost

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
                compute_cost_usd=0.1 if is_context_a else 0.2,
                compute_cost_origin="estimated",
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
        prior_a_cost = sum(step.compute_cost_usd or 0.0 for step in ticket_a.trace)

        ticket_b = orch.submit(candidate, context_b)
        outcome_b = orch.advance(ticket_b, policy="full")
        assert outcome_b.final_action == "defer"
        assert ticket_b.stage_results[1].objective_value == 2.0

        budget.record_spend("run", Decimal("0.01"))
        successor_a = orch.submit(candidate, context_a)

        assert successor_a is not ticket_a
        assert successor_a.parent_ticket_id == ticket_a.ticket_id
        assert successor_a.parent_ticket_id != ticket_b.ticket_id
        assert successor_a.lineage[:-1] == ticket_a.lineage
        assert successor_a.stage_results == prior_a_results
        assert successor_a.stage_results[1].objective_value == 1.0
        assert successor_a.trace == prior_a_trace
        assert sum(step.compute_cost_usd or 0.0 for step in successor_a.trace) == prior_a_cost

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

    @pytest.mark.parametrize("prepared", [False, True])
    def test_level5_and_level6_runtime_generalization_collects_audit_refs(self, tmp_path, prepared):
        store = FileSystemCAS(tmp_path / ".polisyos")
        candidate_ref = _persist_l5_l6_candidate(store)
        candidate = {"candidate_id": "cand-1", "semantic": {"interventions": [], "objectives": []}}
        plan = AdversarialPlan(
            parameter_specs=[
                ParameterSpec(name=f"p{index}", lower_bound=-1.0, upper_bound=1.0)
                for index in range(4)
            ],
            strategy=AdversarialStrategy.GRID_EXTREME,
            max_iterations=10,
            vulnerability_threshold=0.0,
            stop_on_first_vulnerability=False,
            collect_top_k=1,
        )
        stress_report = run_stress_test(
            adversarial_plan=plan,
            base_objective=CompositeObjective([_L5FixtureUtilityObjective()]),
            stage_b_evaluator=lambda _candidate, _context: {
                "simulation_results": {"utility": -1.0}
            },
            context={"policy_candidate_ref": candidate_ref},
            cas=store,
        )
        stress_report_ref = stress_report.cas_artifact_ref
        assert stress_report_ref is not None
        assert stress_report_ref.manifest_profile_sha256 is not None
        assert stress_report.score_status == "available"
        assert stress_report.score_profile == "finite_binary_scenario_v1"
        assert stress_report.robustness_score == 1.0

        selection = BenchmarkEvaluation(
            loop_id="loop",
            suite_id="selection",
            candidate_ref=candidate_ref,
            selection_metrics={"score": 1.0},
            holdout_metrics={"score": 1.0},
            promotable=True,
            runtime_split_type=BenchmarkSplit.SELECTION,
        )
        hidden_holdout = BenchmarkEvaluation(
            loop_id="loop",
            suite_id="policy_hidden_holdout",
            candidate_ref=candidate_ref,
            selection_metrics={"score": 1.0},
            holdout_metrics={"score": 0.96},
            promotable=True,
            runtime_split_type=BenchmarkSplit.HIDDEN_HOLDOUT,
        )
        unbound_summary = Level5RefutationGovernanceStage(require_hidden_holdout=True).evaluate(
            candidate,
            {
                "store": store,
                "policy_candidate_ref": candidate_ref,
                "selection_evaluation": selection,
                "hidden_holdout_evaluation": hidden_holdout,
                "stress_test_report": StressTestReport(
                    report_id="unbound_score_only",
                    score_profile="finite_binary_scenario_v1",
                    score_status="available",
                    score_predicate_status="recomputed",
                    robustness_score=1.0,
                ),
            },
        )
        assert unbound_summary.feedback["stress_score_status"] == "unbound"
        assert unbound_summary.feedback["stress_score_value"] is None
        assert unbound_summary.terminal_action == "defer_to_human"

        runner_calls = []
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
            Level5RefutationGovernanceStage(require_hidden_holdout=True),
            Level6PromotionStage(
                promotion_runner=lambda candidate, context: runner_calls.append(candidate)
                or {
                    "decision": "complete",
                    "reason": "promoted_for_test",
                },
            ),
        ]
        orch = FunnelOrchestrator(stages)
        context = {
            "store": store,
            "policy_candidate_ref": candidate_ref,
            "selection_evaluation": selection,
            "hidden_holdout_evaluation": hidden_holdout,
            "stress_test_report_ref": stress_report_ref,
            "governance_report": GovernanceReport(verdict="approve"),
            **(
                {"promotion_result": {"decision": "complete", "reason": "already_prepared"}}
                if prepared
                else {}
            ),
        }

        outcome = orch.advance(orch.submit(candidate, context), policy="full")

        assert outcome.completed is True
        assert outcome.final_action == ("complete" if prepared else "defer_to_human")
        assert runner_calls == []
        assert outcome.final_result is not None
        assert outcome.final_result.stage_name == "funnel_L6_promotion"
        level5_result = outcome.stage_results[5]
        assert level5_result.terminal_action is None
        assert level5_result.feedback["stress_score_status"] == "available"
        assert level5_result.feedback["stress_score_profile"] == "finite_binary_scenario_v1"
        assert level5_result.feedback["stress_score_predicate_status"] == "recomputed"
        assert level5_result.feedback["stress_score_value"] == 1.0
        assert level5_result.feedback["stress_robust"] is True
        assert not any(
            card.failure_type == "stress_score_unavailable" for card in level5_result.failure_cards
        )
        if prepared:
            assert outcome.final_result.feedback["promotion_result_read_only"] is True
        else:
            assert outcome.final_result.feedback["promotion_admission_status"] == "bridge_missing"
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

    def test_ticket_fallback_does_not_override_declared_transfer_run(self) -> None:
        stage = _make_stage(0, "L0")
        orchestrator = FunnelOrchestrator([stage])
        declared = TransferContext(
            task_family="policy", domain="fiscal", run_id="source-declared-run"
        )

        ticket = orchestrator.submit(
            {"candidate_id": "candidate-a"}, {"transfer_context": declared}
        )
        orchestrator.advance(ticket, target_level=0)

        stage_context = stage.evaluate.call_args.args[1]
        assert stage_context["transfer_context"].run_id == "source-declared-run"
        assert stage_context["policy_runtime_work_identity"]["run_id"] == "source-declared-run"

    @pytest.mark.parametrize(
        "mode",
        [
            "normal",
            "conservative_routing",
            "no_promotion",
            "reduced_judge",
            "freeze_frontier",
            "prior_free",
            "auto_cap",
        ],
    )
    def test_routing_mode_accepts_supported_context_modes(self, mode: str) -> None:
        orchestrator = FunnelOrchestrator([])
        assert orchestrator._routing_mode({"funnel_degradation_mode": mode}) == mode

    @pytest.mark.parametrize("mode", [None, "future_mode"])
    def test_routing_mode_unknown_hashable_modes_keep_existing_fallback(self, mode: object) -> None:
        orchestrator = FunnelOrchestrator([])
        assert orchestrator._routing_mode({"funnel_degradation_mode": mode}) == "normal"

    @pytest.mark.parametrize("mode", [[], {}])
    def test_routing_mode_unhashable_mode_remains_malformed_input(self, mode: object) -> None:
        orchestrator = FunnelOrchestrator([])
        with pytest.raises(TypeError):
            orchestrator._routing_mode({"funnel_degradation_mode": mode})

    def test_routing_mode_validates_metrics_and_preserves_fallbacks(self) -> None:
        orchestrator = FunnelOrchestrator([])
        assert (
            orchestrator._routing_mode(
                {
                    "funnel_degradation_mode": "future_mode",
                    "correlation_metrics": {"routing_mode": "no_promotion"},
                }
            )
            == "no_promotion"
        )
        assert (
            orchestrator._routing_mode(
                {
                    "correlation_metrics": {
                        "routing_mode": "future_mode",
                        "promotion_ban_active": False,
                    }
                }
            )
            == "normal"
        )
        assert (
            orchestrator._routing_mode(
                {
                    "correlation_metrics": {
                        "routing_mode": "future_mode",
                        "promotion_ban_active": True,
                    }
                }
            )
            == "no_promotion"
        )

        class _TrackerWithFallback:
            def routing_mode(self) -> object:
                return "future_mode"

            def compute_metrics(self) -> dict[str, object]:
                return {"routing_mode": "auto_cap"}

        assert (
            FunnelOrchestrator([], correlation_tracker=_TrackerWithFallback())._routing_mode()
            == "auto_cap"
        )

        class _MetricsOnlyTracker:
            def compute_metrics(self) -> dict[str, object]:
                return {"routing_mode": "future_mode"}

        assert (
            FunnelOrchestrator([], correlation_tracker=_MetricsOnlyTracker())._routing_mode()
            == "normal"
        )
