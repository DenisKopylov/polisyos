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

# =============================================================================
# MOCK IMPLEMENTATIONS (Testing)
# =============================================================================

from polisyos.scientist.agent.critic import LLMCriticAgent, MockCriticAgent, create_mock_problem_frame
from polisyos.scientist.agent.drafter import LLMDrafterAgent, MockDrafterAgent, MockLLM
from polisyos.scientist.agent.formalizer import LLMFormalizerAgent, MockFormalizerAgent, create_mock_draft
from polisyos.scientist.agent.memory import ShortTermMemory, TurnRole
from polisyos.scientist.agent.pi import LLMPIAgent, MockPIAgent

# =============================================================================
# LEGACY SUPPORT (Backward Compatibility)
# =============================================================================

from polisyos.scientist.agent.base import BaseAgent, MockAgent
from polisyos.scientist.agent.drafter import drafter_node

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
