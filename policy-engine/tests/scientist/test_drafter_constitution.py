from __future__ import annotations

import asyncio
from datetime import datetime

from polisyos.scientist.agent.drafter import MultiPassConfig, MultiPassLLMDrafter, MockDrafterAgent
from polisyos.scientist.agent.protocols import ProblemFrame


def run(coro):
    return asyncio.run(coro)


class RecordingDrafter(MockDrafterAgent):
    def __init__(self) -> None:
        super().__init__()
        self.last_context: dict[str, object] = {}

    async def draft_policy(
        self,
        problem_frame: ProblemFrame,
        *,
        data_context: dict[str, object] | None = None,
        hints: list[str] | None = None,
        prior_drafts=None,
    ):
        self.last_context = dict(problem_frame.context)
        return await super().draft_policy(
            problem_frame,
            data_context=data_context,
            hints=hints,
            prior_drafts=prior_drafts,
        )


def test_multipass_injects_constitution_into_problem_frame_context() -> None:
    inner = RecordingDrafter()
    agent = MultiPassLLMDrafter(
        inner,
        config=MultiPassConfig(max_passes=1, constitution_enabled=True),
    )
    problem_frame = ProblemFrame(
        frame_id="pf_constitution_injection",
        domain="fiscal",
        problem_statement="Reduce poverty under budget",
        goals=("reduce poverty",),
        constraints=("Budget <= 1000",),
        created_at=datetime.utcnow(),
    )

    _ = run(agent.draft_policy(problem_frame))

    assert "policy_constitution" in inner.last_context
    assert "POLICY CONSTITUTION" in str(inner.last_context["policy_constitution"])
    assert "policy_constitution_hash" in inner.last_context
    assert agent.last_constitution_hash is not None
