"""Enforce human-escalation and conflict-acknowledgement rules for high-stakes decisions."""

from __future__ import annotations

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.scientist.governance.accountability import resolve_governance_threshold


class EscalationPass(ValidatorPass):
    """Block missing human review for high-impact items and critical conflicts.

    Checks that high-risk or high-impact decisions have the required
    human review markers, and that escalation conditions trigger
    appropriate review flags. Reads `impact_score`, `human_reviewed`,
    `escalation_acknowledged`, and `unresolved_conflicts` from state. Scores
    above `require_human_review_above` emit blockers, scores above
    `impact_threshold` emit warnings, and critical unresolved conflicts are
    always blockers.
    """

    def __init__(
        self,
        *,
        impact_threshold: float = 0.8,
        require_human_review_above: float = 0.9,
    ) -> None:
        self._impact_threshold = impact_threshold
        self._human_review_threshold = require_human_review_above

    @property
    def pass_id(self) -> str:
        return "escalation"

    @property
    def estimated_cost_ms(self) -> int:
        return 10

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        issues: list[ComplianceIssue] = []
        state = ctx.state

        impact_score = state.get("impact_score")
        if impact_score is not None:
            try:
                score = float(impact_score)
            except (ValueError, TypeError):
                score = 0.0

            human_review_threshold = resolve_governance_threshold(
                "require_human_review_above",
                ctx.profile.thresholds,
                fallback=self._human_review_threshold,
            )
            impact_threshold = resolve_governance_threshold(
                "impact_threshold",
                ctx.profile.thresholds,
                fallback=self._impact_threshold,
            )

            if score >= human_review_threshold:
                human_reviewed = bool(state.get("human_reviewed", False))
                if not human_reviewed:
                    issues.append(
                        ComplianceIssue(
                            pass_id=self.pass_id,
                            path=["state", "human_reviewed"],
                            message=(
                                f"Impact score {score:.2f} >= {human_review_threshold:.2f} "
                                "requires human review"
                            ),
                            severity=IssueSeverity.BLOCKER,
                            code="ESCALATION_HUMAN_REVIEW_REQUIRED",
                            suggestion="Flag this decision for human expert review before proceeding",
                        )
                    )

            elif score >= impact_threshold:
                escalation_acknowledged = bool(state.get("escalation_acknowledged", False))
                if not escalation_acknowledged:
                    issues.append(
                        ComplianceIssue(
                            pass_id=self.pass_id,
                            path=["state", "escalation_acknowledged"],
                            message=(
                                f"Impact score {score:.2f} >= {impact_threshold:.2f} "
                                "requires escalation acknowledgement"
                            ),
                            severity=IssueSeverity.WARNING,
                            code="ESCALATION_ACKNOWLEDGE_REQUIRED",
                            suggestion="Acknowledge high-impact escalation before proceeding",
                        )
                    )

        # Check for conflict escalation
        conflicts = state.get("unresolved_conflicts", [])
        if isinstance(conflicts, list) and conflicts:
            n_critical = sum(
                1 for c in conflicts if isinstance(c, dict) and c.get("severity") == "critical"
            )
            if n_critical > 0:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["state", "unresolved_conflicts"],
                        message=f"{n_critical} critical unresolved conflict(s) require escalation",
                        severity=IssueSeverity.BLOCKER,
                        code="ESCALATION_CRITICAL_CONFLICTS",
                        suggestion="Resolve critical conflicts or escalate to domain expert",
                    )
                )

        return issues
