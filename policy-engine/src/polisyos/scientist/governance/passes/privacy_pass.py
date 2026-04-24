"""Validate privacy-tier metadata and data-view access requests before execution."""

from __future__ import annotations

from polisyos.core.governance.passes.base import (
    ComplianceIssue,
    IssueSeverity,
    PassContext,
    ValidatorPass,
)
from polisyos.ir.analytics.data_views import AccessTier


def _access_tier_from_request(request: object) -> str | None:
    if isinstance(request, dict):
        value = request.get("access_tier")
        return str(value) if value is not None else None
    value = getattr(request, "access_tier", None)
    return str(value) if value is not None else None


class PrivacyPass(ValidatorPass):
    """Warn on high PII tiers, sensitive access requests, and unknown access tiers.

    The pass expects `pii_tier` and optional `data_view_requests` state payloads
    and emits non-blocking `PII_TIER_HIGH`, `SENSITIVE_ACCESS_TIER`, and
    `ACCESS_TIER_UNKNOWN` findings for downstream governance review.
    """

    @property
    def pass_id(self) -> str:
        return "privacy"

    @property
    def estimated_cost_ms(self) -> int:
        return 20

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        issues: list[ComplianceIssue] = []

        pii_tier = ctx.state.get("pii_tier")
        if pii_tier and str(pii_tier).lower() in {"high", "sensitive"}:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["pii_tier"],
                    message=f"PII tier is high ({pii_tier})",
                    severity=IssueSeverity.WARNING,
                    code="PII_TIER_HIGH",
                    suggestion="Consider human gate or lower sensitivity",
                    input_value=str(pii_tier),
                )
            )

        requests = ctx.state.get("data_view_requests") or []
        for idx, request in enumerate(requests):
            access_tier = _access_tier_from_request(request)
            if access_tier is None:
                continue
            normalized = access_tier.lower()
            if normalized == AccessTier.SENSITIVE.value:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["data_view_requests", idx, "access_tier"],
                        message="Sensitive access tier requested",
                        severity=IssueSeverity.WARNING,
                        code="SENSITIVE_ACCESS_TIER",
                        input_value=access_tier,
                    )
                )
            elif normalized not in {
                AccessTier.PUBLIC.value,
                AccessTier.INTERNAL.value,
                AccessTier.SENSITIVE.value,
            }:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["data_view_requests", idx, "access_tier"],
                        message=f"Unknown access tier '{access_tier}'",
                        severity=IssueSeverity.WARNING,
                        code="ACCESS_TIER_UNKNOWN",
                        input_value=access_tier,
                    )
                )

        return issues
