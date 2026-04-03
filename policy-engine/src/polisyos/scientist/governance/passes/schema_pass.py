"""Validate that the active IR payload is present and schema-compatible."""
from __future__ import annotations

from typing import List

from pydantic import ValidationError

from polisyos.core.governance.passes.base import (
    ComplianceIssue,
    IssueSeverity,
    PassContext,
    ValidatorPass,
)
from polisyos.ir.governance.validation import build_validation_report
from polisyos.ir.trinity import TrinityBundle


class SchemaPass(ValidatorPass):
    """Block missing IR, Pydantic validation failures, and empty intervention sets.

    The pass validates `ctx.ir` against `TrinityBundle`, maps Pydantic
    `ValidationError` entries into `SCHEMA_VALIDATION_ERROR` blockers, emits
    `IR_MISSING` when no IR exists, and requires at least one intervention via
    `NO_INTERVENTIONS`.
    """

    @property
    def pass_id(self) -> str:
        return "schema"

    @property
    def estimated_cost_ms(self) -> int:
        return 15

    def validate(self, ctx: PassContext) -> List[ComplianceIssue]:
        issues: List[ComplianceIssue] = []

        if ctx.ir is None:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["ir"],
                    message="IR is missing",
                    severity=IssueSeverity.BLOCKER,
                    code="IR_MISSING",
                )
            )
            return issues

        try:
            payload = ctx.ir.model_dump(mode="json")
            TrinityBundle.model_validate(payload)
        except ValidationError as exc:
            report = build_validation_report(exc, before=payload, after=payload)
            for validation_issue in report.issues:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=list(validation_issue.loc),
                        message=validation_issue.message,
                        severity=IssueSeverity.BLOCKER,
                        code="SCHEMA_VALIDATION_ERROR",
                        input_value=str(validation_issue.input_value),
                    )
                )

        if not ctx.ir.policy_spec.interventions:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["policy_spec", "interventions"],
                    message="At least one intervention is required",
                    severity=IssueSeverity.BLOCKER,
                    code="NO_INTERVENTIONS",
                )
            )

        return issues
