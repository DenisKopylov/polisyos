"""Validate run budgets and graph complexity before expensive execution stages."""

from __future__ import annotations

from polisyos.core.governance.passes.base import (
    ComplianceIssue,
    IssueSeverity,
    PassContext,
    ValidatorPass,
)
from polisyos.scientist.kernel.budgets import ComplexityBudget, ComputeBudget, EvidenceBudget


class BudgetPass(ValidatorPass):
    """Block exhausted simulation/LLM budgets and over-large intervention graphs.

    The pass reads budget/usage counters from `PassContext`, inspects `ctx.ir`
    for intervention count and time-step complexity, and applies profile
    thresholds `max_interventions` and `max_graph_cost`. Simulation and LLM
    exhaustion plus intervention overflow are blockers; high estimated graph cost
    is emitted as `GRAPH_COST_HIGH` warning.
    """

    @property
    def pass_id(self) -> str:
        return "budget"

    @property
    def estimated_cost_ms(self) -> int:
        return 5

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        issues: list[ComplianceIssue] = []
        ir = ctx.ir

        max_sim_runs = ctx.get_budget("max_sim_runs", float("inf"))
        sim_runs_used = ctx.get_usage("sim_runs", 0.0)

        if max_sim_runs - sim_runs_used < 1:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["budget", "max_sim_runs"],
                    message=f"No simulation runs remaining (used {sim_runs_used}/{max_sim_runs})",
                    severity=IssueSeverity.BLOCKER,
                    code="BUDGET_EXHAUSTED_SIM",
                    suggestion="Increase max_sim_runs or reduce experiment scope",
                )
            )

        max_llm_calls = ctx.get_budget("max_llm_calls", float("inf"))
        llm_calls_used = ctx.get_usage("llm_calls", 0.0)

        if max_llm_calls - llm_calls_used < 1:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["budget", "max_llm_calls"],
                    message=f"No LLM calls remaining (used {llm_calls_used}/{max_llm_calls})",
                    severity=IssueSeverity.BLOCKER,
                    code="BUDGET_EXHAUSTED_LLM",
                )
            )

        if ir is not None:
            num_interventions = len(ir.policy_spec.interventions)
            max_interventions = int(ctx.profile.thresholds.get("max_interventions", 10))

            if num_interventions > max_interventions:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["semantic", "interventions"],
                        message=f"Too many interventions: {num_interventions} > {max_interventions}",
                        severity=IssueSeverity.BLOCKER,
                        code="COMPLEXITY_EXCEEDED",
                        input_value=str(num_interventions),
                    )
                )

            time_steps = 1
            if ir.model_spec.time_semantics is not None:
                if ir.model_spec.time_semantics.step_count is not None:
                    time_steps = ir.model_spec.time_semantics.step_count

            estimated_cost = num_interventions * max(1, time_steps)
            max_graph_cost = int(ctx.profile.thresholds.get("max_graph_cost", 10000))

            if estimated_cost > max_graph_cost:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["model_spec", "time_semantics"],
                        message=f"Estimated graph cost {estimated_cost} exceeds limit {max_graph_cost}",
                        severity=IssueSeverity.WARNING,
                        code="GRAPH_COST_HIGH",
                        suggestion="Reduce step_count or intervention count",
                    )
                )

        return issues


__all__ = ["BudgetPass", "ComplexityBudget", "ComputeBudget", "EvidenceBudget"]
