from __future__ import annotations

import asyncio
from contextlib import nullcontext

from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain
from polisyos.ir.governance.problem_frame import ProblemFrame as IRProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.agent.critic import MockCriticAgent
from polisyos.scientist.agent.feasibility import BudgetImpactResult, PopulationQueryResult
from polisyos.scientist.agent.informed_critic import InformedCriticAgent
from polisyos.scientist.agent.protocols import CritiqueCategory, ProblemFrame


def run(coro):
    return asyncio.run(coro)


def _bundle_with_selector(value: str, amount: str = "100") -> TrinityBundle:
    problem_frame = IRProblemFrame(
        problem_id="pf_informed",
        domain=ProblemDomain.FISCAL,
        narrative="Reduce poverty",
    )
    policy_spec = PolicySpec(
        policy_id="policy_informed",
        interventions=[
            InterventionSpec(
                intervention_id="intv_1",
                kind="tax_subsidy",
                target={
                    "kind": "predicate",
                    "field": "income",
                    "operator": "<",
                    "value": value,
                },
                schedule={"start_step": 0, "duration_steps": 12},
                params={"amount": amount},
            )
        ],
    )
    model_spec = ModelSpec(
        model_id="model_informed",
        data_snapshot_ref="sha256:" + ("0" * 64),
    )
    return TrinityBundle(
        problem_frame=problem_frame,
        policy_spec=policy_spec,
        model_spec=model_spec,
    )


def _agent_problem_frame() -> ProblemFrame:
    return ProblemFrame(
        frame_id="pf_agent_informed",
        domain="fiscal",
        problem_statement="Reduce poverty",
        goals=("reduce poverty",),
        constraints=("Budget <= 1000",),
    )


class ZeroMatchProbe:
    async def count_matching_agents(self, **kwargs):
        return PopulationQueryResult(
            matching_count=0,
            total_count=1000,
            match_ratio=0.0,
            snapshot_ref=kwargs["data_snapshot_ref"],
            query_description="0/1000",
        )

    async def check_attribute_exists(self, **kwargs):
        return True

    async def estimate_budget_impact(self, **kwargs):
        return BudgetImpactResult(
            estimated_total_cost=0.0,
            matching_count=0,
            total_count=1000,
            budget_limit=kwargs.get("budget_limit"),
            feasible=True,
            snapshot_ref=kwargs["data_snapshot_ref"],
            query_description="0",
        )


class BudgetOverflowProbe:
    async def count_matching_agents(self, **kwargs):
        return PopulationQueryResult(
            matching_count=5,
            total_count=10,
            match_ratio=0.5,
            snapshot_ref=kwargs["data_snapshot_ref"],
            query_description="5/10",
        )

    async def check_attribute_exists(self, **kwargs):
        return True

    async def estimate_budget_impact(self, **kwargs):
        return BudgetImpactResult(
            estimated_total_cost=2500.0,
            matching_count=5,
            total_count=10,
            budget_limit=kwargs.get("budget_limit"),
            feasible=False,
            snapshot_ref=kwargs["data_snapshot_ref"],
            query_description="2500>1000",
        )


class _FakeSpan:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}

    def __enter__(self) -> _FakeSpan:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


class _FakeTracer:
    def __init__(self) -> None:
        self.last_span: _FakeSpan | None = None

    def start_as_current_span(self, name: str, attributes: dict[str, object]) -> _FakeSpan:
        del name, attributes
        self.last_span = _FakeSpan()
        return self.last_span


class _FakeMetrics:
    def __init__(self) -> None:
        self.preemptive_catches: list[str] = []
        self.feasibility_statuses: list[str] = []

    def time_informed_critic(self, attrs: dict[str, str]):
        del attrs
        return nullcontext()

    def record_critic_preemptive_catch(self, *, catch_type: str) -> None:
        self.preemptive_catches.append(catch_type)

    def record_feasibility_query(self, *, duration_seconds: float, status: str) -> None:
        del duration_seconds
        self.feasibility_statuses.append(status)

    def set_failure_pattern_index_size(self, size: int) -> None:
        del size


def test_informed_critic_catches_zero_target_before_inner_critic() -> None:
    inner = MockCriticAgent(default_verdict="APPROVE")
    critic = InformedCriticAgent(inner=inner, feasibility_probe=ZeroMatchProbe())

    report = run(critic.critique(_bundle_with_selector("100"), _agent_problem_frame()))

    assert report.verdict == "REJECT"
    feasibility_issues = [
        issue for issue in report.issues if issue.category == CritiqueCategory.FEASIBILITY
    ]
    assert feasibility_issues
    assert any("matches 0" in issue.message for issue in feasibility_issues)


def test_informed_critic_catches_budget_overflow() -> None:
    inner = MockCriticAgent(default_verdict="APPROVE")
    critic = InformedCriticAgent(inner=inner, feasibility_probe=BudgetOverflowProbe())

    report = run(
        critic.critique(_bundle_with_selector("1000", amount="500"), _agent_problem_frame())
    )

    assert report.verdict == "REJECT"
    assert any("exceeds budget limit" in issue.message for issue in report.issues)


def test_informed_critic_accepts_injected_observability(monkeypatch) -> None:
    def _fail_get_tracer():
        raise AssertionError("global tracer lookup should not be used")

    def _fail_get_metrics():
        raise AssertionError("global metrics lookup should not be used")

    monkeypatch.setattr(
        "polisyos.scientist.agent.informed_critic.get_tracer",
        _fail_get_tracer,
    )
    monkeypatch.setattr(
        "polisyos.scientist.agent.informed_critic.get_metrics",
        _fail_get_metrics,
    )

    tracer = _FakeTracer()
    metrics = _FakeMetrics()
    critic = InformedCriticAgent(
        inner=MockCriticAgent(default_verdict="APPROVE"),
        feasibility_probe=BudgetOverflowProbe(),
        tracer=tracer,
        metrics=metrics,
    )

    report = run(
        critic.critique(_bundle_with_selector("1000", amount="500"), _agent_problem_frame())
    )

    assert report.verdict == "REJECT"
    assert "budget_exhausted" in metrics.preemptive_catches
    assert "ok" in metrics.feasibility_statuses
    assert "budget" in metrics.feasibility_statuses
    assert tracer.last_span is not None
    assert tracer.last_span.attributes["polisyos.critic.verdict"] == "REJECT"
