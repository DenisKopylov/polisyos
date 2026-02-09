from __future__ import annotations

from datetime import datetime

from polisyos.scientist.agent.informed_critic import InformedCriticAgent
from polisyos.scientist.agent.protocols import CritiqueReport
from polisyos.scientist.orchestrator.workflow import build_workflow


class StaticCritic:
    async def critique(self, ir, problem_frame, *, depth: str = "standard") -> CritiqueReport:
        del ir, depth
        return CritiqueReport(
            report_id="rep_custom",
            ir_ref="ir_custom",
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


def test_workflow_resolves_informed_critic_from_feature_flag(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_INFORMED_CRITIC_ENABLED", "true")

    app = build_workflow()
    result = app.invoke(
        {
            "user_request": "Reduce poverty through progressive taxation",
            "stop_after_phase": "frame",
        }
    )

    critic = result.get("critic_agent")
    assert isinstance(critic, InformedCriticAgent)


def test_workflow_uses_state_critic_override(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_INFORMED_CRITIC_ENABLED", "true")
    custom = StaticCritic()

    app = build_workflow()
    result = app.invoke(
        {
            "user_request": "Reduce poverty through progressive taxation",
            "stop_after_phase": "frame",
            "critic_agent": custom,
        }
    )

    assert result.get("critic_agent") is custom

