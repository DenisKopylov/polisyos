"""Tests for optional GonkaGate response-healing in JSON-only agent paths."""

from __future__ import annotations

import json

import pytest
from polisyos.scientist.agent.formalizer import (
    LLMFormalizerAgent,
    MockFormalizerAgent,
    create_mock_draft,
)
from polisyos.scientist.agent.pi import LLMPIAgent
from polisyos.scientist.llm.gateway_client import GatewayLLMResponse, GatewayUsage


class _FakeJSONLLMClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    async def generate(self, **kwargs):
        self.calls.append(dict(kwargs))
        return GatewayLLMResponse(
            content=json.dumps(self.payload),
            usage=GatewayUsage(),
            raw={},
        )


@pytest.mark.asyncio
async def test_pi_agent_can_attach_response_healing_plugin():
    client = _FakeJSONLLMClient(
        {
            "problem_frame": {
                "frame_id": "pf_test",
                "domain": "economic",
                "problem_statement": "Reduce poverty",
                "actors": ["government"],
                "goals": ["Improve welfare"],
                "constraints": ["Budget cap"],
                "success_criteria": {"metric": "income"},
                "assumptions": ["Stable macro conditions"],
            }
        }
    )

    agent = LLMPIAgent(client, enable_response_healing=True)
    frame = await agent.create_problem_frame("Reduce poverty")

    assert frame.frame_id == "pf_test"
    assert client.calls[0]["plugins"] == [{"id": "response-healing"}]
    assert client.calls[0]["response_format"] == {"type": "json_object"}
    assert "tools" not in client.calls[0]


@pytest.mark.asyncio
async def test_formalizer_agent_can_attach_response_healing_plugin():
    draft = create_mock_draft(draft_id="draft_test")
    bundle = await MockFormalizerAgent().formalize(draft)
    client = _FakeJSONLLMClient(bundle.model_dump(mode="json"))

    agent = LLMFormalizerAgent(client, enable_response_healing=True)
    formalized = await agent.formalize(draft)

    assert formalized.schema_version == bundle.schema_version
    assert client.calls[0]["plugins"] == [{"id": "response-healing"}]
    assert client.calls[0]["response_format"] == {"type": "json_object"}
    assert "tools" not in client.calls[0]
