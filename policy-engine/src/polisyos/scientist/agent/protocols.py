"""
Agent protocols and supporting types for the Scientist module.

This module defines the protocol interfaces for the Hierarchical Agent
Orchestration pattern along with immutable/mutable artifacts used in the
pipeline.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from polisyos.ir.surface import PolicySurfaceIR


# =============================================================================
# SUPPORTING DATA TYPES
# =============================================================================


class TaskPriority(str, Enum):
    """Priority levels for sub-tasks."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, Enum):
    """Status of a sub-task in the decomposition."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class AgentRole(str, Enum):
    """Roles that can be delegated to."""

    PI = "pi"
    DRAFTER = "drafter"
    FORMALIZER = "formalizer"
    CRITIC = "critic"


class CritiqueSeverity(str, Enum):
    """Severity levels for critique issues."""

    BLOCKER = "blocker"
    WARNING = "warning"
    INFO = "info"


class CritiqueCategory(str, Enum):
    """Categories of critique issues."""

    ALIGNMENT = "alignment"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    FEASIBILITY = "feasibility"
    COMPLIANCE = "compliance"
    SCHEMA = "schema"


@dataclass(frozen=True, slots=True)
class ProblemFrame:
    """
    Formalized problem statement capturing the "what" before the "how".

    ProblemFrame is immutable within an experiment and referenced by all
    downstream artifacts.
    """

    frame_id: str
    domain: str
    problem_statement: str
    actors: tuple[str, ...] = field(default_factory=tuple)
    goals: tuple[str, ...] = field(default_factory=tuple)
    constraints: tuple[str, ...] = field(default_factory=tuple)
    success_criteria: dict[str, Any] = field(default_factory=dict)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __hash__(self) -> int:
        """Enable use as dict key based on frame_id."""
        return hash(self.frame_id)


@dataclass(frozen=True, slots=True)
class SubTask:
    """
    A decomposed sub-task from the PI agent.

    SubTasks form a DAG (Directed Acyclic Graph) of work items that can be
    delegated to specialized agents.
    """

    task_id: str
    description: str
    target_agent: AgentRole
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    inputs: dict[str, Any] = field(default_factory=dict)
    expected_output: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DraftResult:
    """
    Output from the Drafter agent - a natural language policy draft.
    """

    draft_id: str
    problem_frame_ref: str
    narrative: str
    interventions: list[dict[str, Any]] = field(default_factory=list)
    rationale: str = ""
    domain_references: list[str] = field(default_factory=list)
    confidence: float = 0.0
    alternatives_considered: list[str] = field(default_factory=list)
    raw_llm_response: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True, slots=True)
class CritiqueIssue:
    """
    A single issue identified during critique.
    """

    issue_id: str
    category: CritiqueCategory
    severity: CritiqueSeverity
    message: str
    location: str = ""
    suggestion: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CritiqueReport:
    """
    Output from the Critic agent - assessment of IR quality.
    """

    report_id: str
    ir_ref: str
    problem_frame_ref: str
    verdict: str  # "APPROVE" | "NEEDS_REVISION" | "REJECT"
    issues: list[CritiqueIssue] = field(default_factory=list)
    alignment_score: float = 0.0
    completeness_score: float = 0.0
    overall_quality: float = 0.0
    reflexion_hint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def has_blockers(self) -> bool:
        """Check if any blocker-level issues exist."""
        return any(issue.severity == CritiqueSeverity.BLOCKER for issue in self.issues)

    @property
    def blocker_count(self) -> int:
        """Count of blocker-level issues."""
        return sum(1 for issue in self.issues if issue.severity == CritiqueSeverity.BLOCKER)

    @property
    def warning_count(self) -> int:
        """Count of warning-level issues."""
        return sum(1 for issue in self.issues if issue.severity == CritiqueSeverity.WARNING)


@dataclass(slots=True)
class DelegationResult:
    """
    Result of delegating a task to an agent.
    """

    task_id: str
    agent_role: AgentRole
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: int = 0
    token_usage: dict[str, int] = field(default_factory=dict)


# =============================================================================
# AGENT PROTOCOLS
# =============================================================================


@runtime_checkable
class PIAgent(Protocol):
    """Principal Investigator agent protocol."""

    @abstractmethod
    async def decompose_task(
        self,
        request: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> list[SubTask]:
        """Decompose a high-level request into sub-tasks."""
        ...

    @abstractmethod
    async def create_problem_frame(
        self,
        request: str,
        *,
        domain_hint: str | None = None,
    ) -> ProblemFrame:
        """Create a ProblemFrame from a user request."""
        ...

    @abstractmethod
    async def delegate(
        self,
        task: SubTask,
        agent_role: AgentRole,
    ) -> DelegationResult:
        """Delegate a sub-task to a specialized agent."""
        ...

    @abstractmethod
    async def hold_problem_frame(
        self,
        problem_frame: ProblemFrame,
    ) -> None:
        """Set the current ProblemFrame for the session."""
        ...

    @property
    @abstractmethod
    def current_problem_frame(self) -> ProblemFrame | None:
        """Get the currently held ProblemFrame."""
        ...


@runtime_checkable
class DrafterAgent(Protocol):
    """Drafter agent protocol (creative hypothesis generator)."""

    @abstractmethod
    async def draft_policy(
        self,
        problem_frame: ProblemFrame,
        *,
        hints: list[str] | None = None,
        prior_drafts: list[DraftResult] | None = None,
    ) -> DraftResult:
        """Generate a policy draft from a ProblemFrame."""
        ...

    @abstractmethod
    async def refine_draft(
        self,
        draft: DraftResult,
        critique: CritiqueReport,
    ) -> DraftResult:
        """Refine a draft based on critique feedback."""
        ...


@runtime_checkable
class FormalizerAgent(Protocol):
    """Formalizer agent protocol (draft to IR translator)."""

    @abstractmethod
    async def formalize(
        self,
        draft: DraftResult,
        *,
        schema_version: str = "2.0",
    ) -> "PolicySurfaceIR":
        """Convert a natural language draft to PolicySurfaceIR."""
        ...

    @abstractmethod
    async def repair_ir(
        self,
        ir: "PolicySurfaceIR",
        errors: list[str],
        *,
        hint: str | None = None,
    ) -> "PolicySurfaceIR":
        """Repair an invalid IR based on validation errors."""
        ...

    @abstractmethod
    async def validate_structure(
        self,
        ir: "PolicySurfaceIR",
    ) -> tuple[bool, list[str]]:
        """Validate IR structure without full semantic check."""
        ...


@runtime_checkable
class CriticAgent(Protocol):
    """Critic agent protocol (IR reviewer)."""

    @abstractmethod
    async def critique(
        self,
        ir: "PolicySurfaceIR",
        problem_frame: ProblemFrame,
        *,
        depth: str = "standard",
    ) -> CritiqueReport:
        """Review IR against the ProblemFrame."""
        ...

    @abstractmethod
    async def generate_hint(
        self,
        issues: list[CritiqueIssue],
    ) -> str:
        """Generate a verbal hint from issues for Reflexion."""
        ...

    @abstractmethod
    async def check_alignment(
        self,
        ir: "PolicySurfaceIR",
        problem_frame: ProblemFrame,
    ) -> float:
        """Calculate alignment score between IR and ProblemFrame."""
        ...


# =============================================================================
# TYPE ALIASES AND REGISTRY HELPERS
# =============================================================================

AnyAgent = PIAgent | DrafterAgent | FormalizerAgent | CriticAgent
AgentFactory = type[PIAgent] | type[DrafterAgent] | type[FormalizerAgent] | type[CriticAgent]


AGENT_PROTOCOLS: dict[AgentRole, type] = {
    AgentRole.PI: PIAgent,
    AgentRole.DRAFTER: DrafterAgent,
    AgentRole.FORMALIZER: FormalizerAgent,
    AgentRole.CRITIC: CriticAgent,
}


def get_protocol_for_role(role: AgentRole) -> type:
    """Get the Protocol type for a given agent role."""
    return AGENT_PROTOCOLS[role]


def is_valid_agent(agent: object, role: AgentRole) -> bool:
    """Check if an object implements the protocol for a role."""
    protocol = get_protocol_for_role(role)
    return isinstance(agent, protocol)
