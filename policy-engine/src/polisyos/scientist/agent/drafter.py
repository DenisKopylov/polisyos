"""Public drafter API facade.

The implementation is split across dedicated modules to keep responsibilities
separate and reduce the size of this entrypoint.
"""

from polisyos.scientist.agent.drafter_clients import LLMDrafterAgent, MockDrafterAgent, MockLLM
from polisyos.scientist.agent.drafter_factory import create_drafter_agent, drafter_node
from polisyos.scientist.agent.drafter_models import (
    FindingCategory,
    FindingSeverity,
    MultiPassConfig,
    PassExecution,
    PassFinding,
)
from polisyos.scientist.agent.drafter_multipass import MultiPassLLMDrafter

__all__ = [
    "FindingCategory",
    "FindingSeverity",
    "LLMDrafterAgent",
    "MockDrafterAgent",
    "MockLLM",
    "MultiPassConfig",
    "MultiPassLLMDrafter",
    "PassExecution",
    "PassFinding",
    "create_drafter_agent",
    "drafter_node",
]
