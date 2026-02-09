"""
Scientist Agent Layer
=====================

Exports protocol interfaces, mock implementations, and legacy helpers.
"""

from __future__ import annotations

# =============================================================================
# PROTOCOLS (Type Interfaces)
# =============================================================================

from polisyos.scientist.agent.protocols import (
    AGENT_PROTOCOLS,
    AgentRole,
    CriticAgent,
    CritiqueCategory,
    CritiqueIssue,
    CritiqueReport,
    CritiqueSeverity,
    DelegationResult,
    DrafterAgent,
    DraftResult,
    FormalizerAgent,
    PIAgent,
    ProblemFrame,
    SubTask,
    TaskPriority,
    TaskStatus,
    get_protocol_for_role,
    is_valid_agent,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Optional exports (loaded lazily at runtime to avoid circular imports).
    from polisyos.scientist.agent.base import BaseAgent, MockAgent
    from polisyos.scientist.agent.critic import LLMCriticAgent, MockCriticAgent
    from polisyos.scientist.agent.drafter import (
        LLMDrafterAgent,
        MockDrafterAgent,
        MockLLM,
        MultiPassConfig,
        MultiPassLLMDrafter,
        create_drafter_agent,
    )
    from polisyos.scientist.agent.rag import CASRAGIndex, RAGConfig
    from polisyos.scientist.agent.code_verifier import CodeVerificationSandbox, SandboxConfig
    from polisyos.scientist.agent.formalizer import LLMFormalizerAgent, MockFormalizerAgent
    from polisyos.scientist.agent.memory import ShortTermMemory, TurnRole
    from polisyos.scientist.agent.pi import LLMPIAgent, MockPIAgent

__all__ = [
    "PIAgent",
    "DrafterAgent",
    "FormalizerAgent",
    "CriticAgent",
    "MockPIAgent",
    "LLMPIAgent",
    "MockDrafterAgent",
    "LLMDrafterAgent",
    "MockFormalizerAgent",
    "LLMFormalizerAgent",
    "MockCriticAgent",
    "LLMCriticAgent",
    "MockLLM",
    "MultiPassLLMDrafter",
    "MultiPassConfig",
    "create_drafter_agent",
    "CASRAGIndex",
    "RAGConfig",
    "CodeVerificationSandbox",
    "SandboxConfig",
    "ProblemFrame",
    "SubTask",
    "DraftResult",
    "CritiqueReport",
    "CritiqueIssue",
    "DelegationResult",
    "AgentRole",
    "TaskPriority",
    "TaskStatus",
    "CritiqueSeverity",
    "CritiqueCategory",
    "AGENT_PROTOCOLS",
    "get_protocol_for_role",
    "is_valid_agent",
    "create_mock_draft",
    "create_mock_problem_frame",
    "ShortTermMemory",
    "TurnRole",
    "BaseAgent",
    "MockAgent",
    "drafter_node",
]

__version__ = "2.0.0"


def __getattr__(name: str):
    """
    Lazy export resolver.

    This package historically re-exported many implementations (LLM agents, mocks, legacy nodes).
    Importing them eagerly creates circular imports with orchestrator/state. We resolve them on
    demand instead.
    """
    import importlib

    mapping = {
        # critic
        "LLMCriticAgent": ("polisyos.scientist.agent.critic", "LLMCriticAgent"),
        "MockCriticAgent": ("polisyos.scientist.agent.critic", "MockCriticAgent"),
        "create_mock_problem_frame": ("polisyos.scientist.agent.critic", "create_mock_problem_frame"),
        # drafter
        "LLMDrafterAgent": ("polisyos.scientist.agent.drafter", "LLMDrafterAgent"),
        "MockDrafterAgent": ("polisyos.scientist.agent.drafter", "MockDrafterAgent"),
        "MockLLM": ("polisyos.scientist.agent.drafter", "MockLLM"),
        "MultiPassLLMDrafter": ("polisyos.scientist.agent.drafter", "MultiPassLLMDrafter"),
        "MultiPassConfig": ("polisyos.scientist.agent.drafter", "MultiPassConfig"),
        "create_drafter_agent": ("polisyos.scientist.agent.drafter", "create_drafter_agent"),
        "drafter_node": ("polisyos.scientist.agent.drafter", "drafter_node"),
        "CASRAGIndex": ("polisyos.scientist.agent.rag", "CASRAGIndex"),
        "RAGConfig": ("polisyos.scientist.agent.rag", "RAGConfig"),
        "CodeVerificationSandbox": (
            "polisyos.scientist.agent.code_verifier",
            "CodeVerificationSandbox",
        ),
        "SandboxConfig": ("polisyos.scientist.agent.code_verifier", "SandboxConfig"),
        # formalizer
        "LLMFormalizerAgent": ("polisyos.scientist.agent.formalizer", "LLMFormalizerAgent"),
        "MockFormalizerAgent": ("polisyos.scientist.agent.formalizer", "MockFormalizerAgent"),
        "create_mock_draft": ("polisyos.scientist.agent.formalizer", "create_mock_draft"),
        # memory
        "ShortTermMemory": ("polisyos.scientist.agent.memory", "ShortTermMemory"),
        "TurnRole": ("polisyos.scientist.agent.memory", "TurnRole"),
        # pi
        "LLMPIAgent": ("polisyos.scientist.agent.pi", "LLMPIAgent"),
        "MockPIAgent": ("polisyos.scientist.agent.pi", "MockPIAgent"),
        # base
        "BaseAgent": ("polisyos.scientist.agent.base", "BaseAgent"),
        "MockAgent": ("polisyos.scientist.agent.base", "MockAgent"),
    }

    if name in mapping:
        module_name, attr = mapping[name]
        module = importlib.import_module(module_name)
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(name)
