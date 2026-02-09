"""Agent factory utilities for legacy workflow/orchestrator entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Mapping

from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.norm_pack import NormPack
from polisyos.scientist.agent.critic import MockCriticAgent, create_critic_agent
from polisyos.scientist.agent.drafter import MockDrafterAgent, MultiPassConfig, create_drafter_agent
from polisyos.scientist.agent.feasibility import FeasibilityProbe
from polisyos.scientist.agent.formalizer import LLMFormalizerAgent, MockFormalizerAgent
from polisyos.scientist.agent.informed_critic import InformedCriticConfig
from polisyos.scientist.agent.knowledge_base import CriticKnowledgeBase
from polisyos.scientist.agent.memory import ShortTermMemory
from polisyos.scientist.agent.norm_loader import NormPackLoader
from polisyos.scientist.agent.pi import LLMPIAgent, MockPIAgent
from polisyos.scientist.agent.protocols import CriticAgent, DrafterAgent, FormalizerAgent, PIAgent


@dataclass(frozen=True, slots=True)
class AgentStack:
    """Resolved multi-agent stack for orchestrator usage."""

    pi: PIAgent
    drafter: DrafterAgent
    formalizer: FormalizerAgent
    critic: CriticAgent


def _as_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def resolve_critic_agent(
    state: Mapping[str, Any],
    *,
    llm_client: Any | None,
    model_name: str | None = None,
    informed_config: InformedCriticConfig | None = None,
    norm_loader: NormPackLoader | None = None,
    feasibility_probe: FeasibilityProbe | None = None,
    knowledge_base: CriticKnowledgeBase | None = None,
) -> CriticAgent:
    """Resolve critic from workflow state or construct default via feature-flag factory."""
    existing = state.get("critic_agent")
    if isinstance(existing, CriticAgent):
        return existing

    return create_critic_agent(
        llm_client,
        model_name=model_name,
        informed_config=informed_config,
        norm_loader=norm_loader,
        feasibility_probe=feasibility_probe,
        knowledge_base=knowledge_base,
    )


def build_agent_stack(
    *,
    llm_client: Any | None,
    model_name: str | None = None,
    use_mocks: bool | None = None,
    memory: ShortTermMemory | None = None,
    drafter_config: MultiPassConfig | None = None,
    informed_config: InformedCriticConfig | None = None,
    norm_loader: NormPackLoader | None = None,
    feasibility_probe: FeasibilityProbe | None = None,
    knowledge_base: CriticKnowledgeBase | None = None,
    constitution_norm_pack: NormPack | None = None,
    constitution_model_spec: ModelSpec | None = None,
) -> AgentStack:
    """Build PI/Drafter/Formalizer/Critic stack with feature-flag-aware critic factory."""
    if use_mocks is None:
        use_mocks = _as_bool(
            os.getenv("POLISYOS_AGENT_FACTORY_USE_MOCKS"),
            default=llm_client is None,
        )

    if use_mocks:
        drafter: DrafterAgent = MockDrafterAgent()
        formalizer: FormalizerAgent = MockFormalizerAgent()
        critic = create_critic_agent(
            llm_client,
            model_name=model_name,
            inner=MockCriticAgent(),
            informed_config=informed_config,
            norm_loader=norm_loader,
            feasibility_probe=feasibility_probe,
            knowledge_base=knowledge_base,
        )
        pi: PIAgent = MockPIAgent()
        return AgentStack(pi=pi, drafter=drafter, formalizer=formalizer, critic=critic)

    if llm_client is None:
        raise ValueError("llm_client is required when use_mocks=False")

    drafter = create_drafter_agent(
        llm_client,
        model_name=model_name,
        memory=memory,
        config=drafter_config,
        knowledge_base=knowledge_base,
        constitution_norm_pack=constitution_norm_pack,
        constitution_model_spec=constitution_model_spec,
    )
    formalizer = LLMFormalizerAgent(llm_client, model_name=model_name)
    critic = create_critic_agent(
        llm_client,
        model_name=model_name,
        informed_config=informed_config,
        norm_loader=norm_loader,
        feasibility_probe=feasibility_probe,
        knowledge_base=knowledge_base,
    )
    pi = LLMPIAgent(
        llm_client,
        drafter=drafter,
        formalizer=formalizer,
        critic=critic,
        model_name=model_name,
    )
    return AgentStack(pi=pi, drafter=drafter, formalizer=formalizer, critic=critic)


__all__ = [
    "AgentStack",
    "build_agent_stack",
    "resolve_critic_agent",
]
