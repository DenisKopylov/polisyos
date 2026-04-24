"""
Lex (legal) contracts.

Defines stable DTOs and protocols for legal/compliance evaluation.
This module is the canonical ABI for Lex backends.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.norm_pack import NormPack, NormRef, NormRule, RuleType

from ..artifacts.manifest import ArtifactRef
from .fabric import FabricResultRef
from .foundry import ExecPlanRef, SimulationResultRef
from .trinity import ModelSpecRef, PolicySpecRef, ProblemFrameRef, TrinityBundle, TrinityBundleRef


class IssueSeverity(str, Enum):
    """Severity levels for compliance issues."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


class ComplianceIssue(BaseModel):
    """
    Immutable compliance issue from a validation pass.

    Attributes:
        pass_id: Identifier of the pass that raised this issue
        path: JSON path to the problematic field
        message: Human-readable description of the issue
        severity: Issue severity level
        code: Machine-readable error code
        suggestion: Optional fix suggestion
        input_value: The actual value that caused the issue
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pass_id: str
    path: list[str | int]
    message: str
    severity: IssueSeverity
    code: str | None = None
    suggestion: str | None = None
    input_value: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format compatible with GovernorFeedback."""
        return {
            "loc": self.path,
            "message": self.message,
            "error_type": self.pass_id,
            "input_value": self.input_value,
            "severity": self.severity.value,
            "code": self.code,
            "suggestion": self.suggestion,
        }


@runtime_checkable
class RuleBackend(Protocol):
    """
    Protocol for legal rule evaluation backends.

    Implementations MUST:
    - Return ComplianceIssue objects (not custom types)
    - Be stateless (no side effects between calls)
    - Avoid writing to external systems directly (caller handles IO)
    """

    @property
    def backend_id(self) -> str:  # pragma: no cover - Protocol signature
        """Unique identifier for this backend."""
        ...

    def evaluate(
        self,
        norm_pack: NormPack,
        context: dict[str, Any],
    ) -> list[ComplianceIssue]:  # pragma: no cover - Protocol signature
        """
        Evaluate norms against context.

        Args:
            norm_pack: Collection of norms to evaluate
            context: State dictionary containing policy/IR data

        Returns:
            List of ComplianceIssue objects for any violations/info
        """
        ...


class FoundryRefs(BaseModel):
    """Optional Foundry artifacts that contextualize a Lex evaluation request."""

    model_config = ConfigDict(extra="forbid")

    exec_plan_ref: ExecPlanRef | None = None
    simulation_result_ref: SimulationResultRef | None = None


class LegalContext(BaseModel):
    """Typed input envelope for Lex evaluation."""

    model_config = ConfigDict(extra="forbid")

    trinity: TrinityBundle | None = None
    trinity_bundle_ref: TrinityBundleRef | None = None
    problem_frame_ref: ProblemFrameRef | None = None
    policy_spec_ref: PolicySpecRef | None = None
    model_spec_ref: ModelSpecRef | None = None

    fabric_results: list[FabricResultRef] | None = None
    foundry: FoundryRefs | None = None

    jurisdiction: str
    as_of_date: str | None = None

    norm_pack_ref: ArtifactRef | None = None
    norm_pack: NormPack | None = None

    notes: list[str] = Field(default_factory=list)


class LegalReportRef(ArtifactRef):
    """Artifact reference for a persisted Lex legality report."""

    kind: str = "lex.legal_report"
    media_type: str = "application/json"


class ChangeProposalRef(ArtifactRef):
    """Artifact reference for a persisted Lex change-proposal bundle."""

    kind: str = "lex.change_proposal"
    media_type: str = "application/json"


class NormDiffRef(ArtifactRef):
    """Artifact reference for a diff between two norm-pack revisions."""

    kind: str = "lex.norm_diff"
    media_type: str = "application/json"


class NormImpactReportRef(ArtifactRef):
    """Artifact reference for a report estimating policy impact from legal changes."""

    kind: str = "lex.norm_impact_report"
    media_type: str = "application/json"


class LegalEvaluationRequest(BaseModel):
    """Stable input contract for legality evaluation against a simulation result."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    jurisdiction: str
    as_of: str

    trinity_bundle_ref: TrinityBundleRef | None = None
    policy_spec_ref: PolicySpecRef | None = None
    model_spec_ref: ModelSpecRef | None = None
    simulation_result_ref: SimulationResultRef
    norm_pack_ref: ArtifactRef

    eval_policy_id: str = "lex.eval.simple_v1"
    strict: bool = True


class LegalReport(BaseModel):
    """Legality evaluation result with jurisdictional context, issues, and summary counts."""

    model_config = ConfigDict(extra="forbid")

    context: LegalContext
    issues: list[ComplianceIssue] = Field(default_factory=list)
    summary: dict[str, int] | None = None
    notes: list[str] = Field(default_factory=list)


class ChangeProposal(BaseModel):
    """Change proposal public type."""

    model_config = ConfigDict(extra="forbid")

    context: LegalContext | None = None
    proposals: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


__all__ = [
    "ChangeProposal",
    "ChangeProposalRef",
    "ComplianceIssue",
    "FoundryRefs",
    "IssueSeverity",
    "LegalContext",
    "LegalEvaluationRequest",
    "LegalReport",
    "LegalReportRef",
    "NormDiffRef",
    "NormImpactReportRef",
    "NormPack",
    "NormRef",
    "NormRule",
    "RuleBackend",
    "RuleType",
]
