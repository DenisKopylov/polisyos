"""
Mock Principal Investigator (PI) Agent.

Implements the PIAgent protocol with deterministic outputs suitable for tests.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from polisyos.scientist.agent.prompts import get_pi_prompt
from polisyos.scientist.agent.protocols import (
    AgentRole,
    DelegationResult,
    PIAgent,
    ProblemFrame,
    SubTask,
    TaskPriority,
    TaskStatus,
)
from polisyos.scientist.llm import TracedLLMClient

if TYPE_CHECKING:
    from polisyos.scientist.agent.protocols import CriticAgent, DrafterAgent, FormalizerAgent


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
                description="Convert draft to TrinityBundle (PolicySpec + ModelSpec)",
                target_agent=AgentRole.FORMALIZER,
                priority=TaskPriority.HIGH,
                status=TaskStatus.PENDING,
                dependencies=(f"task_{base_hash}_draft",),
                inputs={},
                expected_output="Valid TrinityBundle object",
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


class LLMPIAgent:
    """
    LLM-powered Principal Investigator agent.

    Uses chain-of-thought prompting for task decomposition.
    """

    def __init__(
        self,
        llm_client: Any,
        drafter: "DrafterAgent | None" = None,
        formalizer: "FormalizerAgent | None" = None,
        critic: "CriticAgent | None" = None,
        model_name: str | None = None,
    ) -> None:
        if llm_client is not None and not isinstance(llm_client, TracedLLMClient):
            self._llm = TracedLLMClient(llm_client, model_name=model_name)
        else:
            self._llm = llm_client
        self._drafter = drafter
        self._formalizer = formalizer
        self._critic = critic
        self._current_problem_frame: ProblemFrame | None = None

    async def create_problem_frame(
        self,
        request: str,
        *,
        domain_hint: str | None = None,
    ) -> ProblemFrame:
        """Create a ProblemFrame from a user request using LLM."""
        if not request or not request.strip():
            raise ValueError("Request cannot be empty")

        prompt = get_pi_prompt()
        user_message = f"USER REQUEST: {request}"
        if domain_hint:
            user_message += f"\nDOMAIN HINT: {domain_hint}"

        response = await self._llm.generate(
            system=prompt,
            user=user_message,
            response_format={"type": "json_object"},
        )

        content = response.content if hasattr(response, "content") else str(response)
        try:
            data = json.loads(content)
            pf_data = data.get("problem_frame", data)
            return ProblemFrame(
                frame_id=pf_data.get("frame_id", str(uuid.uuid4())),
                domain=pf_data.get("domain", domain_hint or "economic"),
                problem_statement=pf_data["problem_statement"],
                actors=tuple(pf_data.get("actors", [])),
                goals=tuple(pf_data.get("goals", [])),
                constraints=tuple(pf_data.get("constraints", [])),
                success_criteria=pf_data.get("success_criteria", {}),
                assumptions=tuple(pf_data.get("assumptions", [])),
                created_at=datetime.utcnow(),
            )
        except (json.JSONDecodeError, KeyError):
            return ProblemFrame(
                frame_id=str(uuid.uuid4()),
                domain=domain_hint or "economic",
                problem_statement=request[:500],
                goals=(request[:200],),
                created_at=datetime.utcnow(),
            )

    async def decompose_task(
        self,
        request: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> list[SubTask]:
        """Decompose a high-level request into sub-tasks using LLM."""
        if not request or not request.strip():
            raise ValueError("Request cannot be empty")

        prompt = get_pi_prompt()
        context_str = ""
        if context:
            context_str = f"\nCONTEXT: {json.dumps(context, ensure_ascii=True)}"
        user_message = f"USER REQUEST: {request}{context_str}"

        response = await self._llm.generate(
            system=prompt,
            user=user_message,
            response_format={"type": "json_object"},
        )

        content = response.content if hasattr(response, "content") else str(response)
        try:
            data = json.loads(content)
            tasks_data = data.get("sub_tasks", [])
            tasks: list[SubTask] = []
            for idx, task in enumerate(tasks_data):
                target_agent = task.get("target_agent", "DRAFTER")
                priority = task.get("priority", "medium")
                try:
                    agent_role = AgentRole(target_agent.lower())
                except ValueError:
                    agent_role = AgentRole.DRAFTER
                try:
                    priority_enum = TaskPriority(priority.lower())
                except ValueError:
                    priority_enum = TaskPriority.MEDIUM
                tasks.append(
                    SubTask(
                        task_id=task.get("task_id", f"task_{idx}"),
                        description=task["description"],
                        target_agent=agent_role,
                        priority=priority_enum,
                        status=TaskStatus.PENDING,
                        dependencies=tuple(task.get("dependencies", [])),
                        expected_output=task.get("expected_output", ""),
                    )
                )
            return tasks
        except (json.JSONDecodeError, KeyError, ValueError):
            return [
                SubTask(
                    task_id="task_0",
                    description=request[:500],
                    target_agent=AgentRole.DRAFTER,
                    priority=TaskPriority.HIGH,
                    status=TaskStatus.PENDING,
                )
            ]

    async def delegate(
        self,
        task: SubTask,
        agent_role: AgentRole,
    ) -> DelegationResult:
        """Delegate a sub-task to a specialized agent."""
        agent_map = {
            AgentRole.DRAFTER: self._drafter,
            AgentRole.FORMALIZER: self._formalizer,
            AgentRole.CRITIC: self._critic,
        }
        agent = agent_map.get(agent_role)
        if agent is None:
            return DelegationResult(
                task_id=task.task_id,
                agent_role=agent_role,
                success=False,
                error=f"No {agent_role.value} agent registered",
            )

        start_time = datetime.utcnow()
        try:
            if agent_role == AgentRole.DRAFTER:
                result = await agent.draft_policy(
                    self._current_problem_frame,
                    hints=task.inputs.get("hints"),
                )
            elif agent_role == AgentRole.FORMALIZER:
                result = await agent.formalize(task.inputs.get("draft"))
            elif agent_role == AgentRole.CRITIC:
                result = await agent.critique(task.inputs.get("ir"), self._current_problem_frame)
            else:
                raise ValueError(f"Unknown agent role: {agent_role}")

            duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            return DelegationResult(
                task_id=task.task_id,
                agent_role=agent_role,
                success=True,
                output=result,
                duration_ms=int(duration),
            )
        except Exception as exc:
            return DelegationResult(
                task_id=task.task_id,
                agent_role=agent_role,
                success=False,
                error=str(exc),
            )

    async def hold_problem_frame(self, problem_frame: ProblemFrame) -> None:
        """Set the current ProblemFrame for the session."""
        self._current_problem_frame = problem_frame

    @property
    def current_problem_frame(self) -> ProblemFrame | None:
        """Get the currently held ProblemFrame."""
        return self._current_problem_frame


def _verify_protocol() -> None:
    agent = MockPIAgent()
    if not isinstance(agent, PIAgent):
        raise TypeError("MockPIAgent does not implement PIAgent protocol")


_verify_protocol()
