"""Enforce per-run usage ceilings for external API/tool calls."""

from __future__ import annotations

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass


class RateLimiterPass(ValidatorPass):
    """Block exceeded call quotas and warn as usage approaches configured limits.

    Checks usage counters for LLM calls, dataset queries, and legal
    lookups against configured thresholds. Reads `ctx.state["usage"]`;
    `RATE_LIMIT_EXCEEDED` blocks the DAG, while
    `RATE_LIMIT_APPROACHING` warns once a counter exceeds 80% of its limit.
    """

    def __init__(
        self,
        *,
        max_llm_calls: int = 100,
        max_dataset_queries: int = 500,
        max_legal_lookups: int = 200,
    ) -> None:
        self._limits = {
            "llm_calls": max_llm_calls,
            "dataset_queries": max_dataset_queries,
            "legal_lookups": max_legal_lookups,
        }

    @property
    def pass_id(self) -> str:
        return "rate_limiter"

    @property
    def estimated_cost_ms(self) -> int:
        return 5

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        issues: list[ComplianceIssue] = []

        usage = ctx.state.get("usage", {})
        if not isinstance(usage, dict):
            return issues

        for counter_name, limit in self._limits.items():
            count = usage.get(counter_name)
            if count is None:
                continue
            try:
                count_val = int(count)
            except (ValueError, TypeError):
                continue

            if count_val > limit:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["state", "usage", counter_name],
                        message=f"{counter_name} ({count_val}) exceeds limit ({limit})",
                        severity=IssueSeverity.BLOCKER,
                        code="RATE_LIMIT_EXCEEDED",
                        suggestion=f"Reduce {counter_name} or increase limit",
                    )
                )
            elif count_val > limit * 0.8:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["state", "usage", counter_name],
                        message=f"{counter_name} ({count_val}) approaching limit ({limit})",
                        severity=IssueSeverity.WARNING,
                        code="RATE_LIMIT_APPROACHING",
                        suggestion=f"Monitor {counter_name} usage",
                    )
                )

        return issues
