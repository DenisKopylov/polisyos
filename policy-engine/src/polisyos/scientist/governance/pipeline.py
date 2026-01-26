from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .passes.base import ValidatorPass, PassContext, ComplianceIssue, IssueSeverity
from .profiles import ValidationProfile
from .telemetry import ValidationTrace, PassSpan


class ValidationPipeline:
    """
    Orchestrates validation passes using Chain of Responsibility pattern.

    Features:
    - Pass ordering by estimated cost (cheapest first)
    - Short-circuit on blocker (configurable per profile)
    - Comprehensive telemetry capture
    - Graceful error handling per pass
    """

    def __init__(self, passes: List[ValidatorPass]):
        self._passes: Dict[str, ValidatorPass] = {p.pass_id: p for p in passes}

    def validate(
        self,
        ctx: PassContext,
        profile: ValidationProfile,
    ) -> Tuple[List[ComplianceIssue], ValidationTrace]:
        trace = ValidationTrace(run_id=ctx.run_id, profile=profile.level.value)
        all_issues: List[ComplianceIssue] = []

        ordered_passes = sorted(
            [self._passes[pid] for pid in profile.pass_ids if pid in self._passes],
            key=lambda p: p.estimated_cost_ms,
        )

        for validator in ordered_passes:
            span = PassSpan(pass_id=validator.pass_id, start_time=datetime.utcnow())

            if ctx.ir:
                try:
                    span.set_inputs_hash(ctx.ir.model_dump(mode="json"))
                except Exception:
                    pass

            try:
                issues = validator.validate(ctx)
                span.issue_count = len(issues)
                span.blocker_count = sum(1 for issue in issues if issue.severity == IssueSeverity.BLOCKER)
                span.warning_count = sum(1 for issue in issues if issue.severity == IssueSeverity.WARNING)
                all_issues.extend(issues)
            except Exception as exc:
                span.error = str(exc)
                all_issues.append(
                    ComplianceIssue(
                        pass_id=validator.pass_id,
                        path=["_internal", "pass_error"],
                        message=f"Pass '{validator.pass_id}' failed: {exc}",
                        severity=IssueSeverity.BLOCKER,
                        code="PASS_EXECUTION_ERROR",
                    )
                )
                span.blocker_count = 1
            finally:
                span.close()
                trace.add_span(span)

            if profile.short_circuit_on_blocker and span.blocker_count > 0:
                trace.complete(short_circuited=True)
                return all_issues, trace

        trace.complete(short_circuited=False)
        return all_issues, trace

    def get_pass(self, pass_id: str) -> Optional[ValidatorPass]:
        """Retrieve a specific pass by ID."""
        return self._passes.get(pass_id)

    @property
    def available_passes(self) -> List[str]:
        """List of available pass IDs."""
        return list(self._passes.keys())
