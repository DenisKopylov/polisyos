"""Validation-report contracts used when IR payload repair or schema checks fail."""

from __future__ import annotations

import difflib
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

if TYPE_CHECKING:
    from collections.abc import Iterable


class ValidationIssue(BaseModel):
    """Represent one normalized validation failure that governance/reporting can persist."""

    loc: list[str | int]
    message: str
    error_type: str
    input_value: Any | None = None
    path: str | None = None
    code: str | None = None
    expected: Any | None = None
    actual: Any | None = None
    severity: str | None = None
    model_config = ConfigDict(extra="forbid")


class ValidationReport(BaseModel):
    """Bundle issue summaries, optional repair notes, and diffs for a failed validation pass."""

    error_summary: str
    issues: list[ValidationIssue]
    repair_attempt: str | None = None
    diff_before_after: str | None = None
    normalized_payload: dict[str, Any] | None = None
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    model_config = ConfigDict(extra="forbid")


def _json_dump(payload: Any) -> list[str]:
    text = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)
    return text.splitlines()


def diff_payloads(before: Any, after: Any) -> str:
    """Render a unified diff so repair loops can compare pre- and post-validation payloads."""
    before_lines = _json_dump(before)
    after_lines = _json_dump(after)
    diff = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile="before",
        tofile="after",
        lineterm="",
    )
    return "\n".join(diff)


def issues_from_validation_error(error: ValidationError) -> list[ValidationIssue]:
    """Convert a Pydantic ``ValidationError`` into stable ``ValidationIssue`` records."""
    issues: list[ValidationIssue] = []
    for entry in error.errors():
        loc = list(entry.get("loc", ()))
        issues.append(
            ValidationIssue(
                loc=loc,
                message=entry.get("msg", ""),
                error_type=entry.get("type", ""),
                input_value=entry.get("input"),
                path=".".join(str(part) for part in loc),
                code=entry.get("type", ""),
                actual=entry.get("input"),
                severity="error",
            )
        )
    return issues


def summarize_issues(issues: Iterable[ValidationIssue]) -> str:
    """Collapse the first few validation issues into a short operator-facing summary."""
    issues_list = list(issues)
    if not issues_list:
        return "No validation issues."
    lines = [f"{len(issues_list)} validation issue(s)."]
    for issue in issues_list[:5]:
        loc = ".".join(str(part) for part in issue.loc) or "<root>"
        lines.append(f"{loc}: {issue.message}")
    return " ".join(lines)


def build_validation_report(
    error: ValidationError,
    *,
    before: Any | None = None,
    after: Any | None = None,
    repair_attempt: str | None = None,
) -> ValidationReport:
    """Build validation report."""
    issues = issues_from_validation_error(error)
    diff_text = None
    if before is not None or after is not None:
        diff_text = diff_payloads(before or {}, after or {})
    return ValidationReport(
        error_summary=summarize_issues(issues),
        issues=issues,
        repair_attempt=repair_attempt,
        diff_before_after=diff_text,
    )
