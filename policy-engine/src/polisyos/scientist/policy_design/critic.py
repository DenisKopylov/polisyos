"""Deterministic policy constraint critic built on governance passes."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.scientist.agent.constraint_context import ConstraintContextAssembler
from polisyos.scientist.governance.pass_entrypoints import (
    budget_pass_factory,
    equity_pass_factory,
    legal_pass_factory,
    pii_check_pass_factory,
    privacy_pass_factory,
    transportability_required_pass_factory,
)
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from polisyos.scientist.search.failure_cards import FailureSeverity, TypedFailureCard
from polisyos.scientist.search.funnel.orchestrator import FunnelOutcome
from polisyos.scientist.search.lessons import LessonCard, lesson_from_failure_card
from polisyos.scientist.search.uncertainty import UncertaintyType


class ConstraintFinding(BaseModel):
    """Constraint finding public type."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(default_factory=lambda: f"finding_{uuid4().hex[:10]}")
    check_name: str = Field(min_length=1)
    status: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source: str = Field(min_length=1)
    failure_type: str = Field(min_length=1)
    uncertainty_type: UncertaintyType | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConstraintTrace(BaseModel):
    """Constraint trace public type."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_type: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    mutation_hints: list[str] = Field(default_factory=list)


class ConstraintCritique(BaseModel):
    """Constraint critique public type."""
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    passed: bool
    findings: list[ConstraintFinding] = Field(default_factory=list)
    traces: list[ConstraintTrace] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def mutation_hints(self) -> list[str]:
        hints: list[str] = []
        seen: set[str] = set()
        for trace in self.traces:
            for hint in trace.mutation_hints:
                text = hint.strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                hints.append(text)
        return hints


class ConstraintCriticInput(BaseModel):
    """Constraint critic input public type."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    candidate: PolicyCandidateSchema
    evaluation_vector: PolicyEvaluationVector | None = None
    funnel_outcome: FunnelOutcome | None = None
    causal_effect_report: CausalEffectReport | None = None
    governance_report: GovernanceReport | None = None
    state: dict[str, Any] = Field(default_factory=dict)
    registry_bundle: object | None = None
    run_id: str = Field(default="constraint_critic", min_length=1)

    def build_state(self) -> dict[str, Any]:
        state = dict(self.state)
        if self.governance_report is not None:
            state.setdefault("governance_report", self.governance_report)
        if self.causal_effect_report is not None:
            state.setdefault("causal_report", self.causal_effect_report)
        if self.funnel_outcome is not None:
            state.setdefault("funnel_outcome", self.funnel_outcome)
        return state

    def build_pass_context(self, pass_ids: set[str]) -> PassContext:
        strict = ValidationProfile.strict()
        return PassContext(
            ir=self.candidate.trinity_bundle,
            state=self.build_state(),
            registry_bundle=self.registry_bundle,
            profile=ValidationProfile(
                level=strict.level,
                pass_ids=frozenset(pass_ids),
                thresholds=dict(strict.thresholds),
                short_circuit_on_blocker=False,
            ),
            run_id=self.run_id,
        )


class ConstraintCritic:
    """Aggregate policy-critical constraints without LLMs."""

    def evaluate(self, payload: ConstraintCriticInput) -> ConstraintCritique:
        findings: list[ConstraintFinding] = []
        findings.extend(self._run_validator("budget", budget_pass_factory(), payload))
        findings.extend(self._run_validator("legal", legal_pass_factory(), payload))
        findings.extend(self._run_validator("equity", equity_pass_factory(), payload))
        findings.extend(self._run_validator("privacy", privacy_pass_factory(), payload))
        findings.extend(self._run_validator("pii_check", pii_check_pass_factory(), payload))
        findings.extend(
            self._run_validator(
                "transportability_required",
                transportability_required_pass_factory(),
                payload,
            )
        )
        findings.extend(self._budget_envelope_findings(payload))
        findings.extend(self._positivity_findings(payload))
        findings.extend(self._hard_constraint_findings(payload))
        findings.extend(self._governance_report_findings(payload))

        traces = _build_traces(findings)
        return ConstraintCritique(
            candidate_id=payload.candidate.candidate_id,
            passed=not any(item.severity == "blocker" for item in findings),
            findings=findings,
            traces=traces,
            metadata={"finding_count": len(findings)},
        )

    def _run_validator(
        self,
        check_name: str,
        validator: Any,
        payload: ConstraintCriticInput,
    ) -> list[ConstraintFinding]:
        try:
            issues = validator.validate(payload.build_pass_context({check_name}))
        except Exception as exc:
            return [
                ConstraintFinding(
                    check_name=check_name,
                    status="not_assessed",
                    severity="warning",
                    description=f"{check_name} could not be assessed: {exc}",
                    source="validator",
                    failure_type=f"{check_name}_not_assessed",
                    uncertainty_type=_check_uncertainty(check_name),
                )
            ]
        if not issues:
            return []
        return [_issue_to_finding(check_name, issue) for issue in issues]

    def _budget_envelope_findings(
        self,
        payload: ConstraintCriticInput,
    ) -> list[ConstraintFinding]:
        context = ConstraintContextAssembler().build(payload.candidate.trinity_bundle.problem_frame)
        if context.budget_envelope is None:
            return [
                ConstraintFinding(
                    check_name="budget_envelope",
                    status="not_assessed",
                    severity="warning",
                    description="Problem frame did not expose a budget envelope.",
                    source="constraint_context",
                    failure_type="budget_envelope_not_assessed",
                    uncertainty_type=UncertaintyType.OPTIMIZATION,
                )
            ]
        total_allocated = sum(
            (entry.amount.amount for entry in payload.candidate.budget_allocation),
            start=Decimal("0"),
        )
        status = "passed"
        severity = "info"
        failure_type = "budget_driver"
        if total_allocated > context.budget_envelope:
            status = "blocker"
            severity = "blocker"
            failure_type = "budget_overrun"
        elif context.budget_envelope > 0 and (
            total_allocated / context.budget_envelope >= Decimal("0.9")
        ):
            status = "warning"
            severity = "warning"
        return [
            ConstraintFinding(
                check_name="budget_envelope",
                status=status,
                severity=severity,
                description=(
                    f"Budget allocation {total_allocated} against envelope "
                    f"{context.budget_envelope}."
                ),
                source="constraint_context",
                failure_type=failure_type,
                uncertainty_type=UncertaintyType.OPTIMIZATION,
                metadata={
                    "allocated": str(total_allocated),
                    "envelope": str(context.budget_envelope),
                },
            )
        ]

    def _positivity_findings(
        self,
        payload: ConstraintCriticInput,
    ) -> list[ConstraintFinding]:
        signal = None
        if payload.funnel_outcome is not None and payload.funnel_outcome.final_result is not None:
            signal = payload.funnel_outcome.final_result.cheap_signal
        if signal is None:
            return [
                ConstraintFinding(
                    check_name="overlap_positivity",
                    status="not_assessed",
                    severity="warning",
                    description="Positivity/overlap could not be assessed from funnel signals.",
                    source="funnel",
                    failure_type="overlap_not_assessed",
                    uncertainty_type=UncertaintyType.STRUCTURAL,
                )
            ]
        positivity_risk = float(signal.positivity_risk)
        if positivity_risk > 0.8:
            status = "blocker"
            severity = "blocker"
            failure_type = "transport_break"
        elif positivity_risk > 0.6:
            status = "warning"
            severity = "warning"
            failure_type = "fragile_assumption"
        else:
            status = "passed"
            severity = "info"
            failure_type = "overlap_ok"
        return [
            ConstraintFinding(
                check_name="overlap_positivity",
                status=status,
                severity=severity,
                description=f"Positivity risk assessed at {positivity_risk:.3f}.",
                source="funnel",
                failure_type=failure_type,
                uncertainty_type=UncertaintyType.STRUCTURAL,
                metadata={"positivity_risk": positivity_risk},
            )
        ]

    def _hard_constraint_findings(
        self,
        payload: ConstraintCriticInput,
    ) -> list[ConstraintFinding]:
        evaluation = payload.evaluation_vector
        if evaluation is None:
            return [
                ConstraintFinding(
                    check_name="hard_constraints",
                    status="not_assessed",
                    severity="warning",
                    description="PolicyEvaluationVector missing; hard constraints not assessed.",
                    source="policy_evaluation",
                    failure_type="hard_constraints_not_assessed",
                    uncertainty_type=UncertaintyType.OPTIMIZATION,
                )
            ]
        findings: list[ConstraintFinding] = []
        for name, channel in evaluation.hard_constraints.items():
            status = channel.status.value if channel.status is not None else "not_assessed"
            severity = (
                "blocker"
                if status == "violated"
                else "warning"
                if status == "near_binding"
                else "info"
            )
            failure_type = (
                "binding_hard_constraint"
                if status == "near_binding"
                else "hard_constraint_violated"
                if status == "violated"
                else f"hard_constraint_{status}"
            )
            if status == "feasible":
                continue
            findings.append(
                ConstraintFinding(
                    check_name="hard_constraints",
                    status=status,
                    severity=severity,
                    description=(
                        f"Hard constraint '{name}' is {status} with value "
                        f"{channel.value:.4f}."
                    ),
                    source=channel.source or "policy_evaluation",
                    failure_type=failure_type,
                    uncertainty_type=UncertaintyType.OPTIMIZATION,
                    metadata={"constraint_name": name, "margin": channel.margin},
                )
            )
        return findings

    def _governance_report_findings(
        self,
        payload: ConstraintCriticInput,
    ) -> list[ConstraintFinding]:
        report = payload.governance_report
        if report is None:
            return []
        return [
            _issue_to_finding("governance_report", issue)
            for issue in report.issues
        ]


def critique_to_failure_cards(critique: ConstraintCritique) -> list[TypedFailureCard]:
    """Convert failed policy critiques into reusable failure cards for future search loops."""
    cards: list[TypedFailureCard] = []
    for finding in critique.findings:
        severity = {
            "blocker": FailureSeverity.BLOCKER,
            "warning": FailureSeverity.WARNING,
        }.get(finding.severity)
        if severity is None:
            continue
        cards.append(
            TypedFailureCard(
                judge_name="constraint_critic",
                failure_type=finding.failure_type,
                severity=severity,
                description=finding.description,
                uncertainty_type=finding.uncertainty_type,
                remediation_hint=_default_remediation_hint(finding.failure_type),
                metadata=dict(finding.metadata),
            )
        )
    return cards


def critique_to_lesson_cards(
    critique: ConstraintCritique,
    *,
    candidate_hash: str,
    source_run_id: str,
) -> list[LessonCard]:
    """Convert critique findings into lesson cards that later candidates can retrieve."""
    return [
        lesson_from_failure_card(
            card,
            candidate_hash=candidate_hash,
            stage_name="constraint_critic",
            fidelity_level=4,
            source_run_id=source_run_id,
            tags=["policy_mode", "constraint_critic"],
            trace_refs=[trace.trace_type for trace in critique.traces],
        )
        for card in critique_to_failure_cards(critique)
    ]


def trace_to_mutation_hints(trace: ConstraintTrace) -> list[str]:
    """Extract concise mutation hints from a constraint trace for the next search iteration."""
    return list(trace.mutation_hints)


def _issue_to_finding(check_name: str, issue: ComplianceIssue) -> ConstraintFinding:
    severity = {
        IssueSeverity.BLOCKER: "blocker",
        IssueSeverity.WARNING: "warning",
        IssueSeverity.INFO: "info",
    }[issue.severity]
    status = "blocker" if severity == "blocker" else "warning" if severity == "warning" else "info"
    return ConstraintFinding(
        check_name=check_name,
        status=status,
        severity=severity,
        description=issue.message,
        source=check_name,
        failure_type=str(issue.code or issue.pass_id),
        uncertainty_type=_check_uncertainty(check_name),
        metadata={"path": list(issue.path), "suggestion": issue.suggestion},
    )


def _build_traces(findings: list[ConstraintFinding]) -> list[ConstraintTrace]:
    traces: list[ConstraintTrace] = []
    for finding in findings:
        if finding.failure_type.startswith("legal"):
            traces.append(
                ConstraintTrace(
                    trace_type="legal_blocker",
                    summary=finding.description,
                    evidence=[finding.failure_type],
                    mutation_hints=["Revise the intervention or legal basis to satisfy blocked norms."],
                )
            )
        elif "harm" in finding.failure_type or "equity" in finding.check_name:
            traces.append(
                ConstraintTrace(
                    trace_type="harmed_subgroup",
                    summary=finding.description,
                    evidence=[finding.failure_type],
                    mutation_hints=["Adjust targeting or fallback design to reduce subgroup harm."],
                )
            )
        elif "fragile" in finding.failure_type or "overlap" in finding.check_name:
            traces.append(
                ConstraintTrace(
                    trace_type="fragile_assumption",
                    summary=finding.description,
                    evidence=[finding.failure_type],
                    mutation_hints=["Simplify the policy family or restrict the target population."],
                )
            )
        elif "timeout" in finding.failure_type:
            traces.append(
                ConstraintTrace(
                    trace_type="timeout_estimator",
                    summary=finding.description,
                    evidence=[finding.failure_type],
                    mutation_hints=["Reduce compute intensity or narrative complexity."],
                )
            )
        elif "literature" in finding.failure_type:
            traces.append(
                ConstraintTrace(
                    trace_type="weak_literature_support",
                    summary=finding.description,
                    evidence=[finding.failure_type],
                    mutation_hints=["Increase evidence depth before promotion."],
                )
            )
        elif "transport" in finding.failure_type:
            traces.append(
                ConstraintTrace(
                    trace_type="transport_break",
                    summary=finding.description,
                    evidence=[finding.failure_type],
                    mutation_hints=["Narrow target geography or add transport assumptions explicitly."],
                )
            )
        elif "budget" in finding.failure_type:
            traces.append(
                ConstraintTrace(
                    trace_type="budget_driver",
                    summary=finding.description,
                    evidence=[finding.failure_type],
                    mutation_hints=["Reduce allocation size or add a cheaper fallback variant."],
                )
            )
    deduped: list[ConstraintTrace] = []
    seen: set[tuple[str, str]] = set()
    for trace in traces:
        key = (trace.trace_type, trace.summary)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(trace)
    return deduped


def _check_uncertainty(check_name: str) -> UncertaintyType | None:
    if check_name in {"budget", "budget_envelope", "hard_constraints"}:
        return UncertaintyType.OPTIMIZATION
    if check_name in {"legal", "equity", "privacy", "pii_check"}:
        return UncertaintyType.MEASUREMENT
    if check_name in {"transportability_required", "overlap_positivity"}:
        return UncertaintyType.STRUCTURAL
    return None


def _default_remediation_hint(failure_type: str) -> str | None:
    hints = {
        "budget_overrun": "Reduce the budget allocation or change the rollout scope.",
        "binding_hard_constraint": "Increase slack around the binding hard constraint.",
        "transport_break": "Restrict transport scope or add stronger supporting evidence.",
    }
    return hints.get(failure_type)


__all__ = [
    "ConstraintCritic",
    "ConstraintCriticInput",
    "ConstraintCritique",
    "ConstraintFinding",
    "ConstraintTrace",
    "critique_to_failure_cards",
    "critique_to_lesson_cards",
    "trace_to_mutation_hints",
]
