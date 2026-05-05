from __future__ import annotations

from polisyos.scientist.agent.runtime_capabilities import (
    AgentCapabilityId,
    assert_agent_capability_registry_complete,
    get_agent_capability,
    list_agent_capabilities,
)
from polisyos.scientist.engine.frontier_runtime import FrontierCapabilityStatus


def test_agent_capability_registry_lists_every_known_id_once() -> None:
    assert_agent_capability_registry_complete()

    capabilities = list_agent_capabilities()

    assert [item.capability_id for item in capabilities] == list(AgentCapabilityId)
    assert len({item.capability_id for item in capabilities}) == len(AgentCapabilityId)
    assert all(isinstance(item.frontier_status, FrontierCapabilityStatus) for item in capabilities)


def test_agent_capability_registry_exposes_default_rules() -> None:
    supervisor = get_agent_capability("supervisor_worker")

    assert supervisor.capability_id == AgentCapabilityId.SUPERVISOR_WORKER
    assert "offline validated" in supervisor.default_rule
    assert "handoff eval" in supervisor.required_evidence
