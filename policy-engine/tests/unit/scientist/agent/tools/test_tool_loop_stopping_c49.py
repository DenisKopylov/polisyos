"""The real tool-loop consumer distinguishes resource halt from convergence."""

from __future__ import annotations

import pytest

from polisyos.scientist.agent.tools.tool_loop import run_tool_loop
from polisyos.scientist.orchestration.engine.convergence import ConvergenceConfig
from tests.unit.scientist.agent.tools.test_tool_loop import (
    MockResponse,
    MockToolCallAttr,
    _make_registry_with_echo,
)


@pytest.mark.asyncio
async def test_actual_tool_loop_resource_cap_does_not_return_converged():
    class Wire:
        def __init__(self):
            self.calls = 0

        async def generate(self, **kwargs):
            self.calls += 1
            return MockResponse(
                content="candidate tool work",
                tool_calls=[
                    MockToolCallAttr(
                        id=f"call-{self.calls}", name="echo", arguments={"text": "fixture"}
                    ),
                ],
            )

    client = Wire()
    result = await run_tool_loop(
        client=client,
        system="fixture",
        user="bounded tool work",
        tool_registry=_make_registry_with_echo(),
        max_iterations=4,
        convergence_config=ConvergenceConfig(min_iterations=1, max_iterations=1),
    )
    assert client.calls == 1 and len(result.tool_calls_made) == 1
    assert result.convergence_reason == "max_iterations"
    assert result.stop_kind == "resource_limit"
    assert not result.converged and not result.scientific_converged
