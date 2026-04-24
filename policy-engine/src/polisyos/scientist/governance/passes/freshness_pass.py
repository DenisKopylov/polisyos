"""Validate data and knowledge timestamps against freshness warning/block thresholds."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass


class FreshnessPass(ValidatorPass):
    """Warn on stale timestamps and block critically old evidence.

    Checks last_updated timestamps against configurable staleness
    thresholds. Emits warnings for stale data and blockers for
    critically outdated sources. Reads `data_sources` and `knowledge_metadata`
    from state, emits `FRESHNESS_NO_TIMESTAMP` info findings when timestamps are
    absent, and applies constructor thresholds rather than profile thresholds.
    """

    def __init__(
        self,
        *,
        warn_after_days: int = 90,
        block_after_days: int = 365,
    ) -> None:
        self._warn_days = warn_after_days
        self._block_days = block_after_days

    @property
    def pass_id(self) -> str:
        return "freshness"

    @property
    def estimated_cost_ms(self) -> int:
        return 15

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        issues: list[ComplianceIssue] = []
        state = ctx.state
        now = datetime.now(UTC)

        # Check dataset freshness
        data_sources = state.get("data_sources", [])
        if isinstance(data_sources, list):
            for idx, source in enumerate(data_sources):
                if not isinstance(source, dict):
                    continue
                self._check_freshness(
                    issues,
                    source,
                    path=["state", "data_sources", str(idx)],
                    label=source.get("name", f"source_{idx}"),
                    now=now,
                )

        # Check knowledge base freshness
        knowledge_meta = state.get("knowledge_metadata")
        if isinstance(knowledge_meta, dict) and knowledge_meta:
            self._check_freshness(
                issues,
                knowledge_meta,
                path=["state", "knowledge_metadata"],
                label="knowledge_base",
                now=now,
            )

        return issues

    def _check_freshness(
        self,
        issues: list[ComplianceIssue],
        source: dict[str, Any],
        *,
        path: list[str],
        label: str,
        now: datetime,
    ) -> None:
        last_updated = source.get("last_updated")
        if last_updated is None:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=[*path, "last_updated"],
                    message=f"'{label}' has no last_updated timestamp",
                    severity=IssueSeverity.INFO,
                    code="FRESHNESS_NO_TIMESTAMP",
                    suggestion="Add last_updated to data source metadata",
                )
            )
            return

        try:
            if isinstance(last_updated, str):
                ts = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            elif isinstance(last_updated, datetime):
                ts = last_updated if last_updated.tzinfo else last_updated.replace(tzinfo=UTC)
            else:
                return
        except (ValueError, TypeError):
            return

        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        age_days = (now - ts).days

        if age_days >= self._block_days:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=[*path, "last_updated"],
                    message=f"'{label}' is {age_days} days old (block threshold: {self._block_days})",
                    severity=IssueSeverity.BLOCKER,
                    code="FRESHNESS_CRITICAL",
                    suggestion=f"Update '{label}' to a version less than {self._block_days} days old",
                )
            )
        elif age_days >= self._warn_days:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=[*path, "last_updated"],
                    message=f"'{label}' is {age_days} days old (warn threshold: {self._warn_days})",
                    severity=IssueSeverity.WARNING,
                    code="FRESHNESS_STALE",
                    suggestion=f"Consider updating '{label}'",
                )
            )
