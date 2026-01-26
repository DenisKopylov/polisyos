"""
Mock Critic Agent.

Implements the CriticAgent protocol with deterministic critique behavior.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from polisyos.scientist.agent.protocols import (
    CriticAgent,
    CritiqueCategory,
    CritiqueIssue,
    CritiqueReport,
    CritiqueSeverity,
    ProblemFrame,
)

if TYPE_CHECKING:
    from polisyos.ir.surface import PolicySurfaceIR


class MockCriticAgent:
    """Mock implementation of CriticAgent for testing."""

    def __init__(
        self,
        *,
        default_verdict: str = "APPROVE",
        alignment_threshold: float = 0.7,
    ) -> None:
        self._critique_count: int = 0
        self._default_verdict = default_verdict
        self._alignment_threshold = alignment_threshold

    async def critique(
        self,
        ir: "PolicySurfaceIR",
        problem_frame: ProblemFrame,
        *,
        depth: str = "standard",
    ) -> CritiqueReport:
        self._critique_count += 1

        report_id = f"critique_{uuid.uuid4().hex[:8]}"
        ir_ref = f"ir_{hashlib.sha256(str(ir.model_dump()).encode()).hexdigest()[:16]}"

        issues: list[CritiqueIssue] = []

        issues.extend(await self._check_structure(ir))

        alignment_score = await self.check_alignment(ir, problem_frame)
        issues.extend(await self._check_alignment_issues(ir, problem_frame, alignment_score))

        completeness_score, completeness_issues = await self._check_completeness(ir, problem_frame)
        issues.extend(completeness_issues)

        if depth == "deep":
            issues.extend(await self._deep_analysis(ir, problem_frame))

        has_blockers = any(issue.severity == CritiqueSeverity.BLOCKER for issue in issues)
        has_warnings = any(issue.severity == CritiqueSeverity.WARNING for issue in issues)

        if has_blockers:
            verdict = "REJECT"
        elif has_warnings or alignment_score < self._alignment_threshold:
            verdict = "NEEDS_REVISION"
        else:
            verdict = self._default_verdict

        blocker_penalty = sum(1 for issue in issues if issue.severity == CritiqueSeverity.BLOCKER) * 0.3
        warning_penalty = sum(1 for issue in issues if issue.severity == CritiqueSeverity.WARNING) * 0.1
        overall_quality = max(0.0, (alignment_score + completeness_score) / 2 - blocker_penalty - warning_penalty)

        reflexion_hint = await self.generate_hint(issues) if issues else ""

        return CritiqueReport(
            report_id=report_id,
            ir_ref=ir_ref,
            problem_frame_ref=problem_frame.frame_id,
            verdict=verdict,
            issues=issues,
            alignment_score=alignment_score,
            completeness_score=completeness_score,
            overall_quality=min(1.0, max(0.0, overall_quality)),
            reflexion_hint=reflexion_hint,
            metadata={
                "depth": depth,
                "mock_generated": True,
                "critique_count": self._critique_count,
            },
            created_at=datetime.utcnow(),
        )

    async def _check_structure(self, ir: "PolicySurfaceIR") -> list[CritiqueIssue]:
        issues: list[CritiqueIssue] = []
        issue_id = 0

        if not ir.semantic.interventions:
            issues.append(
                CritiqueIssue(
                    issue_id=f"struct_{issue_id}",
                    category=CritiqueCategory.COMPLETENESS,
                    severity=CritiqueSeverity.BLOCKER,
                    message="No interventions defined in IR",
                    location="semantic.interventions",
                    suggestion="Add at least one intervention to address the policy goals",
                )
            )
            issue_id += 1

        if not ir.semantic.objectives:
            issues.append(
                CritiqueIssue(
                    issue_id=f"struct_{issue_id}",
                    category=CritiqueCategory.COMPLETENESS,
                    severity=CritiqueSeverity.WARNING,
                    message="No objectives defined in IR",
                    location="semantic.objectives",
                    suggestion="Define explicit objectives to enable optimization",
                )
            )
            issue_id += 1

        return issues

    async def _check_alignment_issues(
        self,
        ir: "PolicySurfaceIR",
        problem_frame: ProblemFrame,
        alignment_score: float,
    ) -> list[CritiqueIssue]:
        issues: list[CritiqueIssue] = []

        if alignment_score < 0.5:
            issues.append(
                CritiqueIssue(
                    issue_id="align_0",
                    category=CritiqueCategory.ALIGNMENT,
                    severity=CritiqueSeverity.BLOCKER,
                    message=f"Low alignment with ProblemFrame (score: {alignment_score:.2f})",
                    location="semantic",
                    suggestion="Review the ProblemFrame goals and adjust interventions to better address them",
                    evidence={"alignment_score": alignment_score, "threshold": self._alignment_threshold},
                )
            )
        elif alignment_score < self._alignment_threshold:
            issues.append(
                CritiqueIssue(
                    issue_id="align_1",
                    category=CritiqueCategory.ALIGNMENT,
                    severity=CritiqueSeverity.WARNING,
                    message=f"Moderate alignment with ProblemFrame (score: {alignment_score:.2f})",
                    location="semantic",
                    suggestion="Consider strengthening the connection to stated goals",
                    evidence={"alignment_score": alignment_score, "threshold": self._alignment_threshold},
                )
            )

        return issues

    async def _check_completeness(
        self,
        ir: "PolicySurfaceIR",
        problem_frame: ProblemFrame,
    ) -> tuple[float, list[CritiqueIssue]]:
        issues: list[CritiqueIssue] = []
        checks_passed = 0
        total_checks = 4

        if ir.semantic.interventions:
            checks_passed += 1

        if ir.semantic.objectives:
            checks_passed += 1
        else:
            issues.append(
                CritiqueIssue(
                    issue_id="comp_0",
                    category=CritiqueCategory.COMPLETENESS,
                    severity=CritiqueSeverity.INFO,
                    message="Consider adding explicit objectives for better optimization",
                    location="semantic.objectives",
                    suggestion="Define measurable objectives based on ProblemFrame goals",
                )
            )

        if ir.semantic.constraints:
            checks_passed += 1

        if ir.advisory and (ir.advisory.entities or ir.advisory.narrative):
            checks_passed += 1

        completeness_score = checks_passed / total_checks
        return completeness_score, issues

    async def _deep_analysis(
        self,
        ir: "PolicySurfaceIR",
        problem_frame: ProblemFrame,
    ) -> list[CritiqueIssue]:
        issues: list[CritiqueIssue] = []

        for i, intervention in enumerate(ir.semantic.interventions):
            params = intervention.params if hasattr(intervention, "params") else {}
            rate = params.get("rate", "0")
            try:
                rate_float = float(rate)
                if rate_float > 1.0:
                    issues.append(
                        CritiqueIssue(
                            issue_id=f"deep_{i}_rate",
                            category=CritiqueCategory.FEASIBILITY,
                            severity=CritiqueSeverity.WARNING,
                            message=f"Intervention {i} has unrealistic rate: {rate_float}",
                            location=f"semantic.interventions[{i}].params.rate",
                            suggestion="Rates typically should be between 0 and 1",
                        )
                    )
            except (ValueError, TypeError):
                continue

        return issues

    async def generate_hint(self, issues: list[CritiqueIssue]) -> str:
        if not issues:
            return "The IR looks good. No major issues found."

        sorted_issues = sorted(issues, key=lambda issue: issue.severity.value)
        hints: list[str] = []

        blockers = [issue for issue in sorted_issues if issue.severity == CritiqueSeverity.BLOCKER]
        if blockers:
            hints.append("CRITICAL ISSUES that must be fixed:")
            for issue in blockers:
                hint_text = f"- {issue.message}"
                if issue.suggestion:
                    hint_text += f" Suggestion: {issue.suggestion}"
                hints.append(hint_text)

        warnings = [issue for issue in sorted_issues if issue.severity == CritiqueSeverity.WARNING]
        if warnings:
            hints.append("\nIssues that should be addressed:")
            for issue in warnings:
                hint_text = f"- {issue.message}"
                if issue.suggestion:
                    hint_text += f" Suggestion: {issue.suggestion}"
                hints.append(hint_text)

        if not blockers and not warnings:
            infos = [issue for issue in sorted_issues if issue.severity == CritiqueSeverity.INFO]
            if infos:
                hints.append("Suggestions for improvement:")
                for issue in infos[:3]:
                    hints.append(f"- {issue.message}")

        return "\n".join(hints)

    async def check_alignment(
        self,
        ir: "PolicySurfaceIR",
        problem_frame: ProblemFrame,
    ) -> float:
        pf_keywords = set(problem_frame.problem_statement.lower().split())
        for goal in problem_frame.goals:
            pf_keywords.update(goal.lower().split())

        ir_keywords: set[str] = set()
        for intervention in ir.semantic.interventions:
            if hasattr(intervention, "kind") and intervention.kind:
                ir_keywords.update(intervention.kind.lower().split("_"))

        for objective in ir.semantic.objectives:
            if hasattr(objective, "metric_id") and objective.metric_id:
                ir_keywords.update(objective.metric_id.lower().split("_"))

        if ir.advisory and ir.advisory.narrative:
            ir_keywords.update(ir.advisory.narrative.lower().split()[:20])

        if not pf_keywords:
            return 0.8

        common_words = {"the", "a", "an", "to", "by", "for", "in", "of", "and", "or"}
        pf_keywords -= common_words
        ir_keywords -= common_words

        if not pf_keywords:
            return 0.8

        overlap = len(pf_keywords & ir_keywords)
        max_possible = min(len(pf_keywords), 10)

        base_score = 0.6
        overlap_score = (overlap / max_possible) * 0.4 if max_possible > 0 else 0

        return min(1.0, base_score + overlap_score)

    @property
    def critique_count(self) -> int:
        return self._critique_count

    def reset(self) -> None:
        self._critique_count = 0

    def set_default_verdict(self, verdict: str) -> None:
        self._default_verdict = verdict


def create_mock_problem_frame(
    *,
    frame_id: str | None = None,
    domain: str = "economic",
    problem_statement: str = "Reduce poverty by implementing targeted social programs",
) -> ProblemFrame:
    return ProblemFrame(
        frame_id=frame_id or f"pf_{uuid.uuid4().hex[:8]}",
        domain=domain,
        problem_statement=problem_statement,
        actors=("government", "citizens"),
        goals=(f"Address: {problem_statement}",),
        constraints=("Budget deficit <= 3%",),
        success_criteria={"improvement_rate": 0.1},
        created_at=datetime.utcnow(),
    )


def _verify_protocol() -> None:
    agent = MockCriticAgent()
    if not isinstance(agent, CriticAgent):
        raise TypeError("MockCriticAgent does not implement CriticAgent protocol")


_verify_protocol()
