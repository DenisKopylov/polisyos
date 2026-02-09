from __future__ import annotations

from polisyos.scientist.agent.critic import LLMCriticAgent, MockCriticAgent, create_critic_agent
from polisyos.scientist.agent.informed_critic import InformedCriticAgent


class StubLLM:
    async def generate(self, **kwargs):
        del kwargs
        return type("Resp", (), {"content": "{}"})()


def test_create_critic_agent_returns_base_llm_critic_when_flag_off(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_INFORMED_CRITIC_ENABLED", "false")

    critic = create_critic_agent(StubLLM())

    assert isinstance(critic, LLMCriticAgent)


def test_create_critic_agent_wraps_informed_critic_when_flag_on(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_INFORMED_CRITIC_ENABLED", "true")

    critic = create_critic_agent(StubLLM())

    assert isinstance(critic, InformedCriticAgent)


def test_create_critic_agent_honors_mock_mode(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_INFORMED_CRITIC_ENABLED", "false")
    monkeypatch.setenv("POLISYOS_CRITIC_MODE", "mock")

    critic = create_critic_agent(StubLLM())

    assert isinstance(critic, MockCriticAgent)
