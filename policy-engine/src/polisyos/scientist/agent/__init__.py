"""
Scientist Agent Layer
=====================

Exports protocol interfaces, mock implementations, and legacy helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# =============================================================================
# PROTOCOLS (Type Interfaces)
# =============================================================================
from polisyos.scientist.agent.protocols import (
    AGENT_PROTOCOLS,
    AgentRole,
    AgentRouter,
    CriticAgent,
    CritiqueCategory,
    CritiqueIssue,
    CritiqueReport,
    CritiqueSeverity,
    DataNeedExtractorAgent,
    DataNeedSpec,
    DelegationResult,
    DrafterAgent,
    DraftResult,
    FormalizerAgent,
    PIAgent,
    ProblemFrame,
    RoutingState,
    SubTask,
    TaskPriority,
    TaskStatus,
    get_protocol_for_role,
    is_valid_agent,
)

if TYPE_CHECKING:
    # Optional exports (loaded lazily at runtime to avoid circular imports).
    from polisyos.scientist.agent.base import BaseAgent, MockAgent
    from polisyos.scientist.agent.code_verifier import CodeVerificationSandbox, SandboxConfig
    from polisyos.scientist.agent.constitution import (
        ConstitutionGenerator,
        KnownPitfall,
        PolicyConstitution,
    )
    from polisyos.scientist.agent.critic import (
        LLMCriticAgent,
        MockCriticAgent,
        create_critic_agent,
    )
    from polisyos.scientist.agent.data_need_extractor import (
        LLMDataNeedExtractorAgent,
        MockDataNeedExtractorAgent,
    )
    from polisyos.scientist.agent.drafter import (
        LLMDrafterAgent,
        MockDrafterAgent,
        MockLLM,
        MultiPassConfig,
        MultiPassLLMDrafter,
        create_drafter_agent,
    )
    from polisyos.scientist.agent.failure_index import FailurePatternIndex
    from polisyos.scientist.agent.feasibility import (
        FeasibilityProbe,
        NullFeasibilityProbe,
        StateSnapshotFeasibilityProbe,
    )
    from polisyos.scientist.agent.feasibility_duckdb import DuckDBFeasibilityProbe
    from polisyos.scientist.agent.formalizer import LLMFormalizerAgent, MockFormalizerAgent
    from polisyos.scientist.agent.informed_critic import InformedCriticAgent, InformedCriticConfig
    from polisyos.scientist.agent.knowledge_base import CriticKnowledgeBase
    from polisyos.scientist.agent.memory import ShortTermMemory, TurnRole
    from polisyos.scientist.agent.norm_loader import (
        CASNormPackLoader,
        NormPackLoader,
        StaticNormPackLoader,
    )
    from polisyos.scientist.agent.pi import LLMPIAgent, MockPIAgent
    from polisyos.scientist.agent.rag import CASRAGIndex, RAGConfig

__all__ = [
    "PIAgent",
    "DrafterAgent",
    "FormalizerAgent",
    "CriticAgent",
    "DataNeedExtractorAgent",
    "MockPIAgent",
    "LLMPIAgent",
    "MockDataNeedExtractorAgent",
    "LLMDataNeedExtractorAgent",
    "MockDrafterAgent",
    "LLMDrafterAgent",
    "MockFormalizerAgent",
    "LLMFormalizerAgent",
    "MockCriticAgent",
    "LLMCriticAgent",
    "create_critic_agent",
    "MockLLM",
    "MultiPassLLMDrafter",
    "MultiPassConfig",
    "create_drafter_agent",
    "ConstitutionGenerator",
    "PolicyConstitution",
    "KnownPitfall",
    "InformedCriticAgent",
    "InformedCriticConfig",
    "FeasibilityProbe",
    "NullFeasibilityProbe",
    "StateSnapshotFeasibilityProbe",
    "DuckDBFeasibilityProbe",
    "NormPackLoader",
    "StaticNormPackLoader",
    "CASNormPackLoader",
    "CriticKnowledgeBase",
    "FailurePatternIndex",
    "CASRAGIndex",
    "RAGConfig",
    "CodeVerificationSandbox",
    "SandboxConfig",
    "ProblemFrame",
    "SubTask",
    "DraftResult",
    "CritiqueReport",
    "CritiqueIssue",
    "DataNeedSpec",
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
        "create_critic_agent": ("polisyos.scientist.agent.critic", "create_critic_agent"),
        "create_mock_problem_frame": ("polisyos.scientist.agent.critic", "create_mock_problem_frame"),
        # drafter
        "LLMDrafterAgent": ("polisyos.scientist.agent.drafter", "LLMDrafterAgent"),
        "MockDrafterAgent": ("polisyos.scientist.agent.drafter", "MockDrafterAgent"),
        "MockLLM": ("polisyos.scientist.agent.drafter", "MockLLM"),
        "MultiPassLLMDrafter": ("polisyos.scientist.agent.drafter", "MultiPassLLMDrafter"),
        "MultiPassConfig": ("polisyos.scientist.agent.drafter", "MultiPassConfig"),
        "create_drafter_agent": ("polisyos.scientist.agent.drafter", "create_drafter_agent"),
        "drafter_node": ("polisyos.scientist.agent.drafter", "drafter_node"),
        # constitution
        "ConstitutionGenerator": (
            "polisyos.scientist.agent.constitution",
            "ConstitutionGenerator",
        ),
        "PolicyConstitution": ("polisyos.scientist.agent.constitution", "PolicyConstitution"),
        "KnownPitfall": ("polisyos.scientist.agent.constitution", "KnownPitfall"),
        # informed critic
        "InformedCriticAgent": (
            "polisyos.scientist.agent.informed_critic",
            "InformedCriticAgent",
        ),
        "InformedCriticConfig": (
            "polisyos.scientist.agent.informed_critic",
            "InformedCriticConfig",
        ),
        "FeasibilityProbe": ("polisyos.scientist.agent.feasibility", "FeasibilityProbe"),
        "NullFeasibilityProbe": (
            "polisyos.scientist.agent.feasibility",
            "NullFeasibilityProbe",
        ),
        "StateSnapshotFeasibilityProbe": (
            "polisyos.scientist.agent.feasibility",
            "StateSnapshotFeasibilityProbe",
        ),
        "DuckDBFeasibilityProbe": (
            "polisyos.scientist.agent.feasibility_duckdb",
            "DuckDBFeasibilityProbe",
        ),
        "NormPackLoader": ("polisyos.scientist.agent.norm_loader", "NormPackLoader"),
        "StaticNormPackLoader": ("polisyos.scientist.agent.norm_loader", "StaticNormPackLoader"),
        "CASNormPackLoader": ("polisyos.scientist.agent.norm_loader", "CASNormPackLoader"),
        "CriticKnowledgeBase": ("polisyos.scientist.agent.knowledge_base", "CriticKnowledgeBase"),
        "FailurePatternIndex": ("polisyos.scientist.agent.failure_index", "FailurePatternIndex"),
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
        # data need extractor
        "LLMDataNeedExtractorAgent": (
            "polisyos.scientist.agent.data_need_extractor",
            "LLMDataNeedExtractorAgent",
        ),
        "MockDataNeedExtractorAgent": (
            "polisyos.scientist.agent.data_need_extractor",
            "MockDataNeedExtractorAgent",
        ),
        # base
        "BaseAgent": ("polisyos.scientist.agent.base", "BaseAgent"),
        "MockAgent": ("polisyos.scientist.agent.base", "MockAgent"),
        # router
        "FixedPipelineRouter": ("polisyos.scientist.agent.router", "FixedPipelineRouter"),
        "AdaptiveRouter": ("polisyos.scientist.agent.router", "AdaptiveRouter"),
        "AgentFallbackChain": ("polisyos.scientist.agent.router", "AgentFallbackChain"),
        "ParallelAgentRunner": ("polisyos.scientist.agent.router", "ParallelAgentRunner"),
    }

    if name in mapping:
        module_name, attr = mapping[name]
        module = importlib.import_module(module_name)
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(name)
