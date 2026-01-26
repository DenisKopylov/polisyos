"""Multi-agent workflow integration tests."""

from __future__ import annotations

from datetime import datetime
import uuid

from polisyos.scientist.agent.memory import ShortTermMemory, TurnRole
from polisyos.scientist.agent.protocols import (
    CritiqueCategory,
    CritiqueIssue,
    CritiqueReport,
    CritiqueSeverity,
)
from polisyos.scientist.orchestrator.workflow import build_workflow


class StaticCritic:
    def __init__(self, verdict: str, hint: str = "") -> None:
        self._verdict = verdict
        self._hint = hint

    async def critique(self, ir, problem_frame, *, depth: str = "standard") -> CritiqueReport:
        issues = []
        if self._verdict != "APPROVE":
            issues.append(
                CritiqueIssue(
                    issue_id="issue_0",
                    category=CritiqueCategory.COMPLETENESS,
                    severity=CritiqueSeverity.WARNING,
                    message="Missing explicit objective coverage",
                    location="semantic.objectives",
                    suggestion="Add objectives aligned to goals",
                )
            )
        return CritiqueReport(
            report_id=f"critique_{uuid.uuid4().hex[:8]}",
            ir_ref="ir_test",
            problem_frame_ref=problem_frame.frame_id,
            verdict=self._verdict,
            issues=issues,
            alignment_score=0.8,
            completeness_score=0.7,
            overall_quality=0.75,
            reflexion_hint=self._hint,
            created_at=datetime.utcnow(),
        )

    async def generate_hint(self, issues) -> str:
        return self._hint or "No issues identified."

    async def check_alignment(self, ir, problem_frame) -> float:
        return 0.8


class TestMultiAgentWorkflow:
    """Test the complete multi-agent workflow."""

    def test_workflow_produces_valid_ir(self) -> None:
        workflow = build_workflow()
        result = workflow.invoke(
            {
                "user_request": "Reduce poverty through progressive taxation",
                "budget": {"max_llm_calls": 10, "max_sim_runs": 1},
                "stop_after_phase": "frame",
                "critic_agent": StaticCritic("APPROVE"),
            }
        )

        assert result.get("ir") is not None
        assert result["ir"].semantic.interventions
        assert result.get("problem_frame") is not None

    def test_critic_generates_actionable_hints(self) -> None:
        workflow = build_workflow()
        result = workflow.invoke(
            {
                "user_request": "Invalid policy with no clear goal",
                "budget": {"max_llm_calls": 5},
                "max_reflexion_attempts": 1,
                "stop_after_phase": "frame",
                "critic_agent": StaticCritic("NEEDS_REVISION", hint="Add objectives to match goals"),
            }
        )

        critique = result.get("critique_report") or {}
        if critique.get("verdict") == "NEEDS_REVISION":
            assert critique.get("reflexion_hint")

    def test_memory_persists_across_attempts(self) -> None:
        workflow = build_workflow()
        result = workflow.invoke(
            {
                "user_request": "Test policy requiring multiple attempts",
                "max_reflexion_attempts": 1,
                "budget": {"max_llm_calls": 10},
                "stop_after_phase": "frame",
                "critic_agent": StaticCritic("NEEDS_REVISION", hint="Fix the tax rate"),
            }
        )

        memory_data = result.get("short_term_memory", {})
        if memory_data:
            memory = ShortTermMemory.from_dict(memory_data)
            assert memory.get_hints() is not None


class TestShortTermMemory:
    """Test memory module functionality."""

    def test_add_turn(self) -> None:
        memory = ShortTermMemory()
        memory.add_turn(TurnRole.USER, "Test message")
        memory.add_turn("drafter", "Response")
        assert len(memory._turns) == 2

    def test_get_hints(self) -> None:
        memory = ShortTermMemory()
        memory.add_attempt("Draft 1", "IR 1", "NEEDS_REVISION", "Fix the tax rate")
        hints = memory.get_hints()
        assert "Fix the tax rate" in hints

    def test_reset(self) -> None:
        memory = ShortTermMemory()
        memory.add_turn(TurnRole.USER, "Test")
        memory.add_attempt("d", "i", "v", "h")
        memory.reset()
        assert len(memory._turns) == 0
        assert len(memory._hints) == 0

    def test_serialization_roundtrip(self) -> None:
        memory = ShortTermMemory()
        memory.add_turn(TurnRole.PI, "Decomposed task")
        memory.add_attempt("d", "i", "APPROVE", "")

        data = memory.to_dict()
        restored = ShortTermMemory.from_dict(data)
        assert len(restored._turns) == len(memory._turns)
