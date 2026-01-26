"""
Mock Principal Investigator (PI) Agent.

Implements the PIAgent protocol with deterministic outputs suitable for tests.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any

from polisyos.scientist.agent.protocols import (
    AgentRole,
    DelegationResult,
    PIAgent,
    ProblemFrame,
    SubTask,
    TaskPriority,
    TaskStatus,
)


class MockPIAgent:
    """Mock implementation of PIAgent for testing."""

    def __init__(self) -> None:
        self._problem_frame: ProblemFrame | None = None
        self._delegation_count: int = 0

    async def decompose_task(
        self,
        request: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> list[SubTask]:
        if not request or not request.strip():
            raise ValueError("Request cannot be empty")

        base_hash = hashlib.sha256(request.encode()).hexdigest()[:8]

        return [
            SubTask(
                task_id=f"task_{base_hash}_draft",
                description=f"Generate policy draft for: {request[:50]}...",
                target_agent=AgentRole.DRAFTER,
                priority=TaskPriority.HIGH,
                status=TaskStatus.PENDING,
                dependencies=(),
                inputs={"request": request, "context": context or {}},
                expected_output="DraftResult with policy narrative",
            ),
            SubTask(
                task_id=f"task_{base_hash}_formalize",
                description="Convert draft to PolicySurfaceIR",
                target_agent=AgentRole.FORMALIZER,
                priority=TaskPriority.HIGH,
                status=TaskStatus.PENDING,
                dependencies=(f"task_{base_hash}_draft",),
                inputs={},
                expected_output="Valid PolicySurfaceIR object",
            ),
            SubTask(
                task_id=f"task_{base_hash}_critique",
                description="Review IR against ProblemFrame",
                target_agent=AgentRole.CRITIC,
                priority=TaskPriority.MEDIUM,
                status=TaskStatus.PENDING,
                dependencies=(f"task_{base_hash}_formalize",),
                inputs={},
                expected_output="CritiqueReport with verdict",
            ),
        ]

    async def create_problem_frame(
        self,
        request: str,
        *,
        domain_hint: str | None = None,
    ) -> ProblemFrame:
        if not request or not request.strip():
            raise ValueError("Request cannot be empty")

        frame_id = f"pf_{hashlib.sha256(request.encode()).hexdigest()[:16]}"

        domain = domain_hint or "economic"
        lowered = request.lower()
        if any(word in lowered for word in ["health", "medical", "disease"]):
            domain = "healthcare"
        elif any(word in lowered for word in ["education", "school", "learning"]):
            domain = "education"
        elif any(word in lowered for word in ["poverty", "income", "tax", "subsidy"]):
            domain = "economic"

        goals = (f"Address: {request[:100]}",)
        constraints = (
            "Budget deficit must not exceed 3%",
            "Policy must be politically feasible",
        )

        actors_map = {
            "economic": ("government", "citizens", "businesses"),
            "healthcare": ("ministry_of_health", "patients", "providers"),
            "education": ("ministry_of_education", "students", "teachers"),
        }
        actors = actors_map.get(domain, ("government", "citizens"))

        return ProblemFrame(
            frame_id=frame_id,
            domain=domain,
            problem_statement=request,
            actors=actors,
            goals=goals,
            constraints=constraints,
            success_criteria={
                "primary_metric": "improvement_rate",
                "threshold": 0.1,
                "timeframe_months": 12,
            },
            assumptions=(
                "Current economic conditions remain stable",
                "No major external shocks occur",
            ),
            context={"source": "mock_pi", "original_request": request},
            created_at=datetime.utcnow(),
        )

    async def delegate(
        self,
        task: SubTask,
        agent_role: AgentRole,
    ) -> DelegationResult:
        if agent_role not in (AgentRole.DRAFTER, AgentRole.FORMALIZER, AgentRole.CRITIC):
            raise ValueError(f"Cannot delegate to {agent_role}")

        self._delegation_count += 1

        output_map: dict[AgentRole, dict[str, str]] = {
            AgentRole.DRAFTER: {"draft_id": f"draft_{uuid.uuid4().hex[:8]}"},
            AgentRole.FORMALIZER: {"ir_ref": f"ir_{uuid.uuid4().hex[:8]}"},
            AgentRole.CRITIC: {"verdict": "APPROVE"},
        }

        return DelegationResult(
            task_id=task.task_id,
            agent_role=agent_role,
            success=True,
            output=output_map.get(agent_role, {}),
            duration_ms=100,
            token_usage={"input": 0, "output": 0},
        )

    async def hold_problem_frame(self, problem_frame: ProblemFrame) -> None:
        if not problem_frame.frame_id:
            raise ValueError("ProblemFrame must have a valid frame_id")
        self._problem_frame = problem_frame

    @property
    def current_problem_frame(self) -> ProblemFrame | None:
        return self._problem_frame

    @property
    def delegation_count(self) -> int:
        return self._delegation_count

    def reset(self) -> None:
        self._problem_frame = None
        self._delegation_count = 0


def _verify_protocol() -> None:
    agent = MockPIAgent()
    if not isinstance(agent, PIAgent):
        raise TypeError("MockPIAgent does not implement PIAgent protocol")


_verify_protocol()
