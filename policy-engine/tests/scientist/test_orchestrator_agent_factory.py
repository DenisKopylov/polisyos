from __future__ import annotations

from datetime import datetime

from polisyos.scientist.agent.informed_critic import InformedCriticAgent
from polisyos.scientist.agent.protocols import (
    CritiqueReport,
    ProblemFrame,
)
from polisyos.scientist.orchestrator.agent_factory import build_agent_stack, resolve_critic_agent


class StaticCritic:
    async def critique(self, ir, problem_frame, *, depth: str = "standard") -> CritiqueReport:
        del ir, depth
        return CritiqueReport(
            report_id="rep",
            ir_ref="ir",
            problem_frame_ref=problem_frame.frame_id,
            verdict="APPROVE",
            created_at=datetime.utcnow(),
        )

    async def generate_hint(self, issues):
        del issues
        return ""

    async def check_alignment(self, ir, problem_frame):
        del ir, problem_frame
        return 1.0


class StubLLM:
    async def generate(self, **kwargs):
        del kwargs
        return type("Resp", (), {"content": "{}"})()


def test_resolve_critic_agent_reuses_state_override(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_INFORMED_CRITIC_ENABLED", "true")
    custom = StaticCritic()

    resolved = resolve_critic_agent({"critic_agent": custom}, llm_client=StubLLM())

    assert resolved is custom


def test_resolve_critic_agent_uses_factory_with_feature_flag(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_INFORMED_CRITIC_ENABLED", "true")

    resolved = resolve_critic_agent({}, llm_client=StubLLM())

    assert isinstance(resolved, InformedCriticAgent)


def test_build_agent_stack_wires_informed_critic(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_INFORMED_CRITIC_ENABLED", "true")

    stack = build_agent_stack(llm_client=StubLLM(), use_mocks=True)

    assert isinstance(stack.critic, InformedCriticAgent)
    assert isinstance(stack.pi.current_problem_frame, type(None))
