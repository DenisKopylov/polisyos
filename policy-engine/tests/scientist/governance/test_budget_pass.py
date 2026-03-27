from __future__ import annotations

from unittest.mock import MagicMock

from polisyos.core.governance.passes.base import IssueSeverity
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.scientist.governance.passes.budget_pass import BudgetPass


def _make_ir_mock(*, num_interventions: int = 3, step_count: int | None = None):
    """Create a minimal IR mock with policy_spec.interventions and model_spec.time_semantics."""
    ir = MagicMock()
    ir.policy_spec.interventions = [MagicMock() for _ in range(num_interventions)]

    if step_count is not None:
        ir.model_spec.time_semantics.step_count = step_count
    else:
        ir.model_spec.time_semantics = None

    return ir


class TestBudgetPassSimAndLLM:
    """Budget exhaustion checks for sim runs and LLM calls."""

    def test_sim_runs_exhausted_is_blocker(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(
            state={
                "budget": {"max_sim_runs": 10},
                "budget_usage": {"sim_runs": 10},
            },
            profile=strict_profile,
        )
        issues = BudgetPass().validate(ctx)
        assert len(issues) == 1
        assert issues[0].code == "BUDGET_EXHAUSTED_SIM"
        assert issues[0].severity is IssueSeverity.BLOCKER

    def test_llm_calls_exhausted_is_blocker(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(
            state={
                "budget": {"max_llm_calls": 5},
                "budget_usage": {"llm_calls": 5},
            },
            profile=strict_profile,
        )
        issues = BudgetPass().validate(ctx)
        assert len(issues) == 1
        assert issues[0].code == "BUDGET_EXHAUSTED_LLM"
        assert issues[0].severity is IssueSeverity.BLOCKER

    def test_both_within_limits_no_issues(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(
            state={
                "budget": {"max_sim_runs": 10, "max_llm_calls": 20},
                "budget_usage": {"sim_runs": 5, "llm_calls": 10},
            },
            profile=strict_profile,
        )
        issues = BudgetPass().validate(ctx)
        assert issues == []

    def test_both_exhausted_two_blockers(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(
            state={
                "budget": {"max_sim_runs": 3, "max_llm_calls": 7},
                "budget_usage": {"sim_runs": 3, "llm_calls": 7},
            },
            profile=strict_profile,
        )
        issues = BudgetPass().validate(ctx)
        codes = {i.code for i in issues}
        assert codes == {"BUDGET_EXHAUSTED_SIM", "BUDGET_EXHAUSTED_LLM"}
        assert all(i.severity is IssueSeverity.BLOCKER for i in issues)

    def test_missing_budget_keys_defaults_to_inf(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(state={}, profile=strict_profile)
        issues = BudgetPass().validate(ctx)
        assert issues == []


class TestBudgetPassIR:
    """IR-based complexity and graph cost checks."""

    def test_too_many_interventions_blocker(self, pass_context_factory, strict_profile):
        ir = _make_ir_mock(num_interventions=20)
        ctx = pass_context_factory(
            state={},
            profile=strict_profile,
            ir=ir,
        )
        issues = BudgetPass().validate(ctx)
        codes = {i.code for i in issues}
        assert "COMPLEXITY_EXCEEDED" in codes
        issue = next(i for i in issues if i.code == "COMPLEXITY_EXCEEDED")
        assert issue.severity is IssueSeverity.BLOCKER

    def test_high_graph_cost_warning(self, pass_context_factory, strict_profile):
        # strict profile max_graph_cost defaults to 10000
        # 5 interventions * 5000 steps = 25000 > 10000
        ir = _make_ir_mock(num_interventions=5, step_count=5000)
        ctx = pass_context_factory(
            state={},
            profile=strict_profile,
            ir=ir,
        )
        issues = BudgetPass().validate(ctx)
        codes = {i.code for i in issues}
        assert "GRAPH_COST_HIGH" in codes
        issue = next(i for i in issues if i.code == "GRAPH_COST_HIGH")
        assert issue.severity is IssueSeverity.WARNING

    def test_ir_within_limits_no_issues(self, pass_context_factory, strict_profile):
        ir = _make_ir_mock(num_interventions=3, step_count=10)
        ctx = pass_context_factory(
            state={
                "budget": {"max_sim_runs": 100, "max_llm_calls": 100},
                "budget_usage": {"sim_runs": 0, "llm_calls": 0},
            },
            profile=strict_profile,
            ir=ir,
        )
        issues = BudgetPass().validate(ctx)
        assert issues == []
