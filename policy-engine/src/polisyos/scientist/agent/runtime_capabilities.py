"""Canonical inventory of agentic Scientist runtime capabilities.

This module is intentionally static: it describes what can be promoted, not
whether a feature flag currently enables that capability in production.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.frontier_runtime import FrontierCapabilityStatus

__all__ = [
    "AGENT_CAPABILITY_REGISTRY",
    "AgentCapabilityFamily",
    "AgentCapabilityId",
    "assert_agent_capability_registry_complete",
    "get_agent_capability",
    "list_agent_capabilities",
]


class AgentCapabilityId(StrEnum):
    """Stable identifiers for Phase 1.4 agent promotion decisions."""

    TOOL_LOOP = "tool_loop"
    SUPERVISOR_WORKER = "supervisor_worker"
    DEEP_RESEARCH_SUBGRAPH = "deep_research_subgraph"
    TREE_OF_THOUGHT = "tree_of_thought"
    LATS_MCTS = "lats_mcts"
    LEARNED_ROUTING = "learned_routing"
    LEARNED_VOI = "learned_voi"
    SAME_MODEL_FANOUT = "same_model_fanout"


class AgentCapabilityFamily(BaseModel):
    """One promotion-controlled agent capability family."""

    model_config = ConfigDict(extra="forbid")

    capability_id: AgentCapabilityId
    display_name: str = Field(min_length=1)
    family: str = Field(min_length=1)
    default_rule: str = Field(min_length=1)
    frontier_status: FrontierCapabilityStatus
    feature_flag: str = Field(min_length=1)
    owner_module: str = Field(min_length=1)
    required_evidence: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


AGENT_CAPABILITY_REGISTRY: tuple[AgentCapabilityFamily, ...] = (
    AgentCapabilityFamily(
        capability_id=AgentCapabilityId.TOOL_LOOP,
        display_name="Tool loop",
        family="tools",
        default_rule="default only with transcript/order/schema tests",
        frontier_status=FrontierCapabilityStatus.OFFLINE_GATED,
        feature_flag="scientist.agent.tool_loop",
        owner_module="polisyos.scientist.agent.tools.tool_loop",
        required_evidence=[
            "tool schema validation",
            "response caps",
            "structured error taxonomy",
            "transcript/order tests",
        ],
    ),
    AgentCapabilityFamily(
        capability_id=AgentCapabilityId.SUPERVISOR_WORKER,
        display_name="Supervisor-worker",
        family="supervisor",
        default_rule="shadow first, then offline validated",
        frontier_status=FrontierCapabilityStatus.OFFLINE_GATED,
        feature_flag="scientist.agent.supervisor_worker",
        owner_module="polisyos.scientist.agent.supervisor",
        required_evidence=[
            "handoff eval",
            "delegation success metrics",
            "quorum consistency metrics",
        ],
    ),
    AgentCapabilityFamily(
        capability_id=AgentCapabilityId.DEEP_RESEARCH_SUBGRAPH,
        display_name="Deep research subgraph",
        family="research",
        default_rule="non-default until citation/faithfulness evals pass",
        frontier_status=FrontierCapabilityStatus.OFFLINE_GATED,
        feature_flag="scientist.agent.deep_research_subgraph",
        owner_module="polisyos.scientist.evidence",
        required_evidence=[
            "deep research eval",
            "citation faithfulness eval",
            "public/private data separation",
        ],
    ),
    AgentCapabilityFamily(
        capability_id=AgentCapabilityId.TREE_OF_THOUGHT,
        display_name="Tree-of-thought",
        family="reasoning",
        default_rule="offline-gated until lift beats baseline",
        frontier_status=FrontierCapabilityStatus.OFFLINE_GATED,
        feature_flag="scientist.agent.reasoning.tree_of_thought",
        owner_module="polisyos.scientist.agent.reasoning",
        required_evidence=[
            "reasoning gate",
            "comparative eval versus Reflexion baseline",
        ],
    ),
    AgentCapabilityFamily(
        capability_id=AgentCapabilityId.LATS_MCTS,
        display_name="LATS / MCTS",
        family="reasoning",
        default_rule="offline-gated until lift beats baseline",
        frontier_status=FrontierCapabilityStatus.OFFLINE_GATED,
        feature_flag="scientist.agent.reasoning.lats_mcts",
        owner_module="polisyos.scientist.agent.reasoning",
        required_evidence=[
            "reasoning gate",
            "comparative eval versus Reflexion baseline",
        ],
    ),
    AgentCapabilityFamily(
        capability_id=AgentCapabilityId.LEARNED_ROUTING,
        display_name="Learned routing",
        family="search",
        default_rule="shadow only until calibration and regret tests pass",
        frontier_status=FrontierCapabilityStatus.EXPERIMENTAL_NOT_WIRED,
        feature_flag="scientist.search.learned_routing",
        owner_module="polisyos.scientist.search.strategies.advanced_policy",
        required_evidence=[
            "offline validation",
            "calibration tests",
            "regret tests",
        ],
    ),
    AgentCapabilityFamily(
        capability_id=AgentCapabilityId.LEARNED_VOI,
        display_name="Learned VOI",
        family="search",
        default_rule="shadow only until calibration and regret tests pass",
        frontier_status=FrontierCapabilityStatus.EXPERIMENTAL_NOT_WIRED,
        feature_flag="scientist.search.learned_voi",
        owner_module="polisyos.scientist.search.strategies.advanced_policy",
        required_evidence=[
            "offline validation",
            "calibration tests",
            "regret tests",
        ],
    ),
    AgentCapabilityFamily(
        capability_id=AgentCapabilityId.SAME_MODEL_FANOUT,
        display_name="Same-model fan-out / voting",
        family="supervisor",
        default_rule="allowed only with budget + citation + consistency checks",
        frontier_status=FrontierCapabilityStatus.OFFLINE_GATED,
        feature_flag="scientist.agent.same_model_fanout",
        owner_module="polisyos.scientist.agent.supervisor",
        required_evidence=[
            "budget cap eval",
            "citation consistency eval",
            "comparative eval versus baseline",
        ],
    ),
)


def list_agent_capabilities() -> list[AgentCapabilityFamily]:
    """Return the static Phase 1.4 capability inventory."""

    assert_agent_capability_registry_complete()
    return list(AGENT_CAPABILITY_REGISTRY)


def get_agent_capability(capability_id: AgentCapabilityId | str) -> AgentCapabilityFamily:
    """Look up one capability family by stable id."""

    resolved = AgentCapabilityId(capability_id)
    for capability in AGENT_CAPABILITY_REGISTRY:
        if capability.capability_id == resolved:
            return capability
    raise KeyError(resolved.value)


def assert_agent_capability_registry_complete() -> None:
    """Fail if the registry is missing or duplicating a known capability id."""

    expected = {item.value for item in AgentCapabilityId}
    observed = [item.capability_id.value for item in AGENT_CAPABILITY_REGISTRY]
    duplicate_ids = sorted({item for item in observed if observed.count(item) > 1})
    if duplicate_ids:
        raise ValueError(f"duplicate agent capability ids: {', '.join(duplicate_ids)}")
    missing = sorted(expected.difference(observed))
    extra = sorted(set(observed).difference(expected))
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing={missing}")
        if extra:
            details.append(f"extra={extra}")
        raise ValueError("agent capability registry mismatch: " + "; ".join(details))
