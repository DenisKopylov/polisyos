"""
FailureCard: Structured artifact for self-healing workflows.

A FailureCard is the "ticket" that enables the Reflexion loop. It captures:
- What went wrong (error_code, violation_summary)
- Where it went wrong (source_step, technical_details)
- How to fix it (remediation_advice, governor_advice)
- Iteration tracking (attempt_number, max_iterations)

Design Principles:
1. Concise: Must fit in LLM context window without bloating.
2. Actionable: Contains specific, implementable remediation steps.
3. Immutable: Once created, a FailureCard is never modified.
4. Traceable: Links to previous artifacts via CAS references.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field

from polisyos.core.canon import content_hash

class FailureSource(str, Enum):
    """Origin of the failure detection."""

    CRITIC = "critic"
    GOVERNOR_SAFETY = "governor_safety"
    GOVERNOR_BUDGET = "governor_budget"
    GOVERNOR_POLICY = "governor_policy"
    VALIDATOR_SCHEMA = "validator_schema"
    VALIDATOR_SEMANTIC = "validator_semantic"
    RUNTIME_COMPILE = "runtime_compile"
    RUNTIME_SIMULATE = "runtime_simulate"
    UNKNOWN = "unknown"


class FailureSeverity(str, Enum):
    """Severity determines retry eligibility."""

    RECOVERABLE = "recoverable"
    NEEDS_HUMAN = "needs_human"
    FATAL = "fatal"


class RemediationTarget(str, Enum):
    """Which agent should handle the fix."""

    FORMALIZER = "formalizer"
    DRAFTER = "drafter"
    HUMAN = "human"
    NONE = "none"


class ConstraintViolation(BaseModel):
    """Detailed constraint violation record."""

    constraint_id: str = Field(description="Unique identifier for the constraint")
    constraint_type: str = Field(description="Category: safety, budget, schema, semantic")
    field_path: Optional[str] = Field(default=None, description="JSON path to violating field")
    expected: Optional[str] = Field(default=None, description="What was expected")
    actual: Optional[str] = Field(default=None, description="What was found")
    message: str = Field(description="Human-readable explanation")


class StateDiff(BaseModel):
    """Captures state changes that led to failure."""

    before_ref: Optional[str] = Field(default=None, description="CAS ref to state before operation")
    after_ref: Optional[str] = Field(default=None, description="CAS ref to state after operation")
    changed_fields: List[str] = Field(default_factory=list, description="List of modified field paths")
    delta_summary: str = Field(default="", description="Human-readable summary of changes")


class FailureCard(BaseModel):
    """
    Structured failure artifact for Reflexion loop.

    This is the primary data structure that enables self-healing. It captures
    all context needed for an LLM agent to understand and fix the error.
    """

    # === Identity ===
    card_id: UUID = Field(default_factory=uuid4, description="Unique identifier for this card")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this card was created",
    )

    # === Source Information ===
    source_step: FailureSource = Field(description="Component that detected the failure")
    run_id: str = Field(description="Parent run identifier for traceability")

    # === Error Classification ===
    error_code: str = Field(description="Machine-readable error identifier")
    severity: FailureSeverity = Field(
        default=FailureSeverity.RECOVERABLE,
        description="Determines retry eligibility",
    )

    # === Human-Readable Description ===
    violation_summary: str = Field(
        max_length=500,
        description="Concise explanation of what went wrong (for humans and LLMs)",
    )

    # === Technical Details ===
    violations: List[ConstraintViolation] = Field(
        default_factory=list,
        description="Detailed list of specific constraint violations",
    )
    technical_details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context: stack traces, diffs, constraint IDs",
    )
    state_diff: Optional[StateDiff] = Field(
        default=None,
        description="Changes that triggered the failure",
    )

    # === Remediation Guidance ===
    remediation_advice: str = Field(
        max_length=1000,
        description="Specific instructions for fixing the issue",
    )
    governor_advice: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Additional guidance from Governor component",
    )
    remediation_target: RemediationTarget = Field(
        default=RemediationTarget.FORMALIZER,
        description="Which agent should handle the fix",
    )

    # === Iteration Tracking ===
    attempt_number: int = Field(ge=1, description="Current attempt (1-indexed)")
    max_iterations: int = Field(default=3, ge=1, le=10, description="Budget for retries")

    # === Artifact References ===
    failed_artifact_ref: Optional[str] = Field(
        default=None,
        description="CAS reference to the artifact that failed validation",
    )
    previous_card_ref: Optional[str] = Field(
        default=None,
        description="CAS reference to previous FailureCard (if this is a retry)",
    )

    # === Computed Properties ===
    @computed_field
    @property
    def can_retry(self) -> bool:
        """Whether another retry attempt is allowed."""
        return (
            self.severity == FailureSeverity.RECOVERABLE
            and self.attempt_number < self.max_iterations
        )

    @computed_field
    @property
    def content_hash(self) -> str:
        """Content-addressable hash for CAS storage."""
        content = f"{self.error_code}:{self.violation_summary}:{self.attempt_number}"
        return content_hash(content, prefix=True)

    # === Methods ===
    def to_prompt_context(self, include_history: bool = False) -> str:
        """
        Format the FailureCard for injection into an LLM prompt.

        Args:
            include_history: If True, include reference to previous failures

        Returns:
            Formatted string suitable for LLM context injection
        """
        lines = [
            "## FAILURE CONTEXT (Attempt {}/{})".format(
                self.attempt_number, self.max_iterations
            ),
            "",
            "### What Went Wrong",
            f"**Error Code:** `{self.error_code}`",
            f"**Source:** {self.source_step.value}",
            f"**Summary:** {self.violation_summary}",
        ]

        # Add specific violations (limited to top 3 for context efficiency)
        if self.violations:
            lines.extend(["", "### Specific Violations"])
            for i, violation in enumerate(self.violations[:3], 1):
                lines.append(f"{i}. [{violation.constraint_type}] {violation.message}")
                if violation.field_path:
                    lines.append(f"   - Field: `{violation.field_path}`")
                if violation.expected and violation.actual:
                    lines.append(f"   - Expected: {violation.expected}, Got: {violation.actual}")

        # Add remediation guidance (most important section)
        lines.extend(["", "### How to Fix", self.remediation_advice])

        if self.governor_advice:
            lines.extend(["", "### Governor Guidance", self.governor_advice])

        # Add state context if available (abbreviated)
        state_summary = self._summarize_state_diff()
        if state_summary:
            lines.extend(["", "### Recent Changes", state_summary])

        # Previous failure reference for learning
        if include_history and self.previous_card_ref:
            lines.extend(["", f"*Previous failure: {self.previous_card_ref}*"])

        return "\n".join(lines)

    def to_audit_entry(self) -> Dict[str, Any]:
        """Format for audit trail logging."""
        return {
            "card_id": str(self.card_id),
            "error_code": self.error_code,
            "source_step": self.source_step.value,
            "severity": self.severity.value,
            "attempt": f"{self.attempt_number}/{self.max_iterations}",
            "can_retry": self.can_retry,
            "remediation_target": self.remediation_target.value,
        }

    @classmethod
    def generate(
        cls,
        source_step: FailureSource,
        error_code: str,
        violation_summary: str,
        remediation_advice: str,
        run_id: str,
        attempt_number: int = 1,
        max_iterations: int = 3,
        violations: Optional[List[ConstraintViolation]] = None,
        technical_details: Optional[Dict[str, Any]] = None,
        governor_advice: Optional[str] = None,
        failed_artifact_ref: Optional[str] = None,
        previous_card_ref: Optional[str] = None,
        severity: Optional[FailureSeverity] = None,
        remediation_target: Optional[RemediationTarget] = None,
        state_diff: Optional[StateDiff] = None,
    ) -> "FailureCard":
        """
        Factory method for generating FailureCards with sensible defaults.

        This is the primary entry point for creating FailureCards from various
        error sources (Critic, Governor, Validator, etc.).
        """
        # Auto-detect severity if not provided
        if severity is None:
            severity = cls._infer_severity(source_step, error_code)

        # Auto-detect remediation target if not provided
        if remediation_target is None:
            remediation_target = cls._infer_target(source_step, error_code, severity)

        return cls(
            source_step=source_step,
            error_code=error_code,
            violation_summary=violation_summary,
            remediation_advice=remediation_advice,
            run_id=run_id,
            attempt_number=attempt_number,
            max_iterations=max_iterations,
            violations=violations or [],
            technical_details=technical_details or {},
            governor_advice=governor_advice,
            failed_artifact_ref=failed_artifact_ref,
            previous_card_ref=previous_card_ref,
            severity=severity,
            remediation_target=remediation_target,
            state_diff=state_diff,
        )

    @staticmethod
    def _infer_severity(source: FailureSource, error_code: str) -> FailureSeverity:
        """Infer severity from source and error code patterns."""
        fatal_patterns = ["BUDGET_EXHAUSTED", "SAFETY_CRITICAL", "AUTH_", "PERMISSION_"]
        if any(pattern in error_code.upper() for pattern in fatal_patterns):
            return FailureSeverity.FATAL

        human_patterns = ["AMBIGUOUS_INTENT", "POLICY_CONFLICT", "GOVERNANCE_VETO"]
        if any(pattern in error_code.upper() for pattern in human_patterns):
            return FailureSeverity.NEEDS_HUMAN

        if source in [FailureSource.GOVERNOR_SAFETY]:
            return FailureSeverity.NEEDS_HUMAN

        return FailureSeverity.RECOVERABLE

    @staticmethod
    def _infer_target(
        source: FailureSource,
        error_code: str,
        severity: FailureSeverity,
    ) -> RemediationTarget:
        """Infer which agent should handle remediation."""
        if severity == FailureSeverity.FATAL:
            return RemediationTarget.NONE
        if severity == FailureSeverity.NEEDS_HUMAN:
            return RemediationTarget.HUMAN

        drafter_patterns = ["ALIGNMENT", "INTENT", "SCOPE", "OBJECTIVE"]
        if any(pattern in error_code.upper() for pattern in drafter_patterns):
            return RemediationTarget.DRAFTER

        return RemediationTarget.FORMALIZER

    def _summarize_state_diff(self) -> str | None:
        if not self.state_diff:
            return None
        summary = (self.state_diff.delta_summary or "").strip()
        max_chars = 240
        if summary and len(summary) <= max_chars:
            return summary
        if self.state_diff.changed_fields:
            fields = self.state_diff.changed_fields
            top_fields = fields[:5]
            remainder = len(fields) - len(top_fields)
            summary = "Top changed fields: " + ", ".join(top_fields)
            if remainder > 0:
                summary += f", and {remainder} more."
            return summary
        if summary:
            return summary[: max_chars - 3] + "..."
        return None


# === Converter Functions for Integration ===


def from_critic_feedback(
    critique: Dict[str, Any],
    run_id: str,
    attempt_number: int = 1,
    max_iterations: int = 3,
    failed_artifact_ref: Optional[str] = None,
) -> FailureCard:
    """
    Convert Critic agent feedback into a FailureCard.
    """
    violations: list[ConstraintViolation] = []
    issues = critique.get("issues", []) if isinstance(critique, dict) else []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        violations.append(
            ConstraintViolation(
                constraint_id=issue.get("issue_id", f"critic_{len(violations)}"),
                constraint_type=issue.get("category", "critic"),
                field_path=issue.get("location"),
                message=issue.get("message", "Critic issue"),
            )
        )

    suggestions = []
    for issue in issues:
        if isinstance(issue, dict):
            suggestion = issue.get("suggestion")
            if suggestion:
                suggestions.append(suggestion)

    reflexion_hint = critique.get("reflexion_hint") if isinstance(critique, dict) else None
    if reflexion_hint:
        suggestions.insert(0, reflexion_hint)

    remediation = (
        "\n".join(f"- {suggestion}" for suggestion in suggestions)
        if suggestions
        else "Review the violations above and revise the IR to address each issue."
    )

    violation_summary = critique.get(
        "summary",
        critique.get("verdict", "Critic rejected the generated IR"),
    )

    return FailureCard.generate(
        source_step=FailureSource.CRITIC,
        error_code=critique.get("error_code", "CRITIC_REJECTION"),
        violation_summary=violation_summary,
        remediation_advice=remediation,
        run_id=run_id,
        attempt_number=attempt_number,
        max_iterations=max_iterations,
        violations=violations,
        technical_details=critique if isinstance(critique, dict) else {},
        failed_artifact_ref=failed_artifact_ref,
        remediation_target=RemediationTarget.DRAFTER,
    )


def from_validation_error(
    validation_report: Dict[str, Any],
    run_id: str,
    attempt_number: int = 1,
    max_iterations: int = 3,
) -> FailureCard:
    """
    Convert a ValidationReport into a FailureCard.
    """
    issues = validation_report.get("issues", [])
    violations = []

    for issue in issues:
        if not isinstance(issue, dict):
            continue
        loc = issue.get("loc") or issue.get("location") or []
        field_path = ".".join(str(item) for item in loc) if isinstance(loc, list) else str(loc)
        constraint_id = issue.get("constraint_id") or field_path or "unknown"
        message = issue.get("message") or issue.get("msg") or "Validation failed"
        violations.append(
            ConstraintViolation(
                constraint_id=str(constraint_id),
                constraint_type=issue.get("error_type", "validation"),
                field_path=field_path,
                message=message,
            )
        )

    remediation_parts = []
    for violation in violations[:3]:
        message_lower = violation.message.lower()
        if "required" in message_lower:
            remediation_parts.append(
                f"Add missing required field at `{violation.field_path}`"
            )
        elif "type" in message_lower:
            remediation_parts.append(
                f"Fix type error at `{violation.field_path}`: {violation.message}"
            )
        else:
            remediation_parts.append(f"Fix validation error at `{violation.field_path}`")

    return FailureCard.generate(
        source_step=FailureSource.VALIDATOR_SCHEMA,
        error_code="SCHEMA_VALIDATION_ERROR",
        violation_summary=f"IR failed schema validation with {len(violations)} issue(s)",
        remediation_advice="\n".join(remediation_parts)
        or "Fix the validation errors listed above",
        run_id=run_id,
        attempt_number=attempt_number,
        max_iterations=max_iterations,
        violations=violations,
        technical_details=validation_report,
    )


def from_governor_feedback(
    feedback: Dict[str, Any],
    run_id: str,
    attempt_number: int = 1,
    max_iterations: int = 3,
) -> FailureCard:
    """
    Convert Governor feedback into a FailureCard.
    """
    verdict = feedback.get("verdict", "UNKNOWN")
    issues = feedback.get("issues", [])

    violations = []
    for issue in issues:
        if isinstance(issue, dict):
            loc = issue.get("loc") or issue.get("location") or []
            violations.append(
                ConstraintViolation(
                    constraint_id=issue.get("constraint_id", "gov_check"),
                    constraint_type=issue.get("error_type", "governance"),
                    field_path=".".join(str(item) for item in loc) if isinstance(loc, list) else str(loc),
                    message=issue.get("message") or issue.get("msg") or "Governance check failed",
                )
            )

    source = FailureSource.GOVERNOR_POLICY
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        error_type = str(issue.get("error_type", "")).lower()
        if error_type == "safety":
            source = FailureSource.GOVERNOR_SAFETY
            break
        if error_type == "budget":
            source = FailureSource.GOVERNOR_BUDGET
            break

    severity = FailureSeverity.RECOVERABLE
    if verdict == "REJECT":
        severity = FailureSeverity.NEEDS_HUMAN

    return FailureCard.generate(
        source_step=source,
        error_code=f"GOVERNOR_{verdict}",
        violation_summary=f"Governor issued {verdict} verdict with {len(issues)} issue(s)",
        remediation_advice=feedback.get("remediation_hint", "Address the governance issues and resubmit"),
        governor_advice=feedback.get("advice"),
        run_id=run_id,
        attempt_number=attempt_number,
        max_iterations=max_iterations,
        violations=violations,
        severity=severity,
        technical_details=feedback,
    )
