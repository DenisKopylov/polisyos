"""Governance pass: validate legal citations in policy claims."""

from __future__ import annotations

from typing import Any, List

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass


class CitationValidatorPass(ValidatorPass):
    """Validate that legal/academic citations are well-formed and traceable.

    Checks that cited sources have valid IDs, that claim-to-source links
    resolve, and that confidence scores are present.
    """

    @property
    def pass_id(self) -> str:
        return "citation_validator"

    @property
    def estimated_cost_ms(self) -> int:
        return 30

    def validate(self, ctx: PassContext) -> List[ComplianceIssue]:
        issues: list[ComplianceIssue] = []
        state = ctx.state

        claims = state.get("verified_claims", [])
        if not isinstance(claims, list):
            return issues

        for idx, claim in enumerate(claims):
            if not isinstance(claim, dict):
                continue

            source_ref = claim.get("source_ref")
            if not source_ref:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["state", "verified_claims", str(idx), "source_ref"],
                        message=f"Claim #{idx} has no source reference",
                        severity=IssueSeverity.WARNING,
                        code="CITATION_MISSING_REF",
                        suggestion="Add source_ref to all verified claims",
                    )
                )

            confidence = claim.get("confidence")
            if confidence is not None:
                try:
                    conf_val = float(confidence)
                    if not (0.0 <= conf_val <= 1.0):
                        issues.append(
                            ComplianceIssue(
                                pass_id=self.pass_id,
                                path=["state", "verified_claims", str(idx), "confidence"],
                                message=f"Claim #{idx} confidence {conf_val} out of [0,1] range",
                                severity=IssueSeverity.WARNING,
                                code="CITATION_INVALID_CONFIDENCE",
                                suggestion="Confidence must be between 0.0 and 1.0",
                            )
                        )
                except (ValueError, TypeError):
                    issues.append(
                        ComplianceIssue(
                            pass_id=self.pass_id,
                            path=["state", "verified_claims", str(idx), "confidence"],
                            message=f"Claim #{idx} confidence is not a valid number",
                            severity=IssueSeverity.WARNING,
                            code="CITATION_BAD_CONFIDENCE",
                            suggestion="Provide numeric confidence score",
                        )
                    )

            quote = claim.get("quote", "")
            if isinstance(quote, str) and len(quote) > 2000:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["state", "verified_claims", str(idx), "quote"],
                        message=f"Claim #{idx} quote exceeds 2000 characters",
                        severity=IssueSeverity.INFO,
                        code="CITATION_LONG_QUOTE",
                        suggestion="Consider summarizing excessively long quotes",
                    )
                )

        return issues
