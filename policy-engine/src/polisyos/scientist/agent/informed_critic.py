"""Informed critic wrapper with feasibility, norm, and cross-run pattern prechecks."""

from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation
import os
import uuid
from typing import Any, Iterable

from polisyos.core.observability import get_metrics, get_tracer
from polisyos.ir.norm_pack import RuleType
from polisyos.ir.selector_expr import SelectorAll, SelectorAny, SelectorExpr, SelectorNot, SelectorPredicate
from polisyos.ir.trinity import TrinityBundle
from pydantic import BaseModel, ConfigDict, Field
from polisyos.scientist.agent.constraint_context import ConstraintContextAssembler
from polisyos.scientist.agent.feasibility import FeasibilityProbe, NullFeasibilityProbe
from polisyos.scientist.agent.knowledge_base import CriticKnowledgeBase
from polisyos.scientist.agent.norm_loader import NormPackLoader
from polisyos.scientist.agent.protocols import (
    CriticAgent,
    CritiqueCategory,
    CritiqueIssue,
    CritiqueReport,
    CritiqueSeverity,
    ProblemFrame,
)

_SEVERITY_ORDER: dict[CritiqueSeverity, int] = {
    CritiqueSeverity.INFO: 0,
    CritiqueSeverity.WARNING: 1,
    CritiqueSeverity.BLOCKER: 2,
}

_AMOUNT_PARAM_HINTS = (
    "amount",
    "subsidy",
    "transfer",
    "payment",
    "payout",
    "benefit",
    "grant",
)


class InformedCriticConfig(BaseModel):
    """Feature flags and thresholds for informed critic rollout control."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enable_feasibility_check: bool = Field(default=True)
    enable_budget_check: bool = Field(default=True)
    enable_norm_check: bool = Field(default=True)
    enable_failure_patterns: bool = Field(default=True)
    feasibility_min_match_ratio: float = Field(default=0.001, ge=0.0, le=1.0)
    failure_pattern_threshold: int = Field(default=3, ge=1, le=20)

    @classmethod
    def from_env(cls) -> "InformedCriticConfig":
        kwargs: dict[str, Any] = {}
        if os.getenv("POLISYOS_FEASIBILITY_CHECK_ENABLED", "").lower() == "false":
            kwargs["enable_feasibility_check"] = False
        if os.getenv("POLISYOS_BUDGET_FEASIBILITY_ENABLED", "").lower() == "false":
            kwargs["enable_budget_check"] = False
        if os.getenv("POLISYOS_NORM_CHECK_ENABLED", "").lower() == "false":
            kwargs["enable_norm_check"] = False
        if os.getenv("POLISYOS_FAILURE_PATTERN_CHECK_ENABLED", "").lower() == "false":
            kwargs["enable_failure_patterns"] = False
        ratio = os.getenv("POLISYOS_FEASIBILITY_MIN_MATCH_RATIO")
        if ratio:
            kwargs["feasibility_min_match_ratio"] = float(ratio)
        threshold = os.getenv("POLISYOS_FAILURE_PATTERN_THRESHOLD")
        if threshold:
            kwargs["failure_pattern_threshold"] = int(threshold)
        return cls(**kwargs)


class InformedCriticAgent:
    """Decorates existing critic with deterministic prechecks and pattern memory."""

    def __init__(
        self,
        inner: CriticAgent,
        *,
        norm_loader: NormPackLoader | None = None,
        feasibility_probe: FeasibilityProbe | None = None,
        knowledge_base: CriticKnowledgeBase | None = None,
        config: InformedCriticConfig | None = None,
        enable_feasibility_check: bool = True,
        enable_budget_check: bool = True,
        enable_norm_check: bool = True,
        enable_failure_patterns: bool = True,
        feasibility_min_match_ratio: float = 0.001,
        failure_pattern_threshold: int = 3,
    ) -> None:
        resolved_config = config or InformedCriticConfig(
            enable_feasibility_check=enable_feasibility_check,
            enable_budget_check=enable_budget_check,
            enable_norm_check=enable_norm_check,
            enable_failure_patterns=enable_failure_patterns,
            feasibility_min_match_ratio=feasibility_min_match_ratio,
            failure_pattern_threshold=failure_pattern_threshold,
        )
        self._inner = inner
        self._norm_loader = norm_loader
        self._feasibility = feasibility_probe or NullFeasibilityProbe()
        self._knowledge_base = knowledge_base
        self._enable_feasibility_check = resolved_config.enable_feasibility_check
        self._enable_budget_check = resolved_config.enable_budget_check
        self._enable_norm_check = resolved_config.enable_norm_check
        self._enable_failure_patterns = resolved_config.enable_failure_patterns
        self._feasibility_min_match_ratio = max(0.0, resolved_config.feasibility_min_match_ratio)
        self._failure_pattern_threshold = max(1, resolved_config.failure_pattern_threshold)
        self._constraint_assembler = ConstraintContextAssembler()

    async def critique(
        self,
        ir: TrinityBundle,
        problem_frame: ProblemFrame,
        *,
        depth: str = "standard",
    ) -> CritiqueReport:
        bundle = self._to_bundle(ir)
        metrics = get_metrics()
        tracer = get_tracer()
        domain = self._domain(problem_frame)

        with metrics.time_informed_critic({"domain": domain}):
            with tracer.start_as_current_span(
                "critic.informed_critique",
                attributes={
                    "polisyos.critic.domain": domain,
                    "polisyos.critic.depth": depth,
                },
            ) as span:
                pre_issues: list[CritiqueIssue] = []

                if self._enable_failure_patterns:
                    pre_issues.extend(self._pattern_issues(problem_frame))

                if self._enable_feasibility_check:
                    pre_issues.extend(await self._feasibility_issues(bundle, problem_frame))

                if self._enable_norm_check:
                    pre_issues.extend(self._norm_issues(bundle, problem_frame))

                inner_report = await self._inner.critique(bundle, problem_frame, depth=depth)
                merged_issues = self._merge_issues(pre_issues, inner_report.issues, domain)

                verdict = self._recompute_verdict(inner_report.verdict, merged_issues)
                hint = await self._inner.generate_hint(merged_issues) if merged_issues else ""

                report = CritiqueReport(
                    report_id=inner_report.report_id or f"critique_{uuid.uuid4().hex[:8]}",
                    ir_ref=(
                        inner_report.ir_ref
                        or f"bundle_{hashlib.sha256(bundle.model_dump_json().encode()).hexdigest()[:16]}"
                    ),
                    problem_frame_ref=inner_report.problem_frame_ref or problem_frame.frame_id,
                    verdict=verdict,
                    issues=merged_issues,
                    alignment_score=inner_report.alignment_score,
                    completeness_score=inner_report.completeness_score,
                    overall_quality=inner_report.overall_quality,
                    reflexion_hint=hint,
                    metadata={
                        **inner_report.metadata,
                        "informed_critic": True,
                        "pre_issues_count": len(pre_issues),
                    },
                    created_at=inner_report.created_at or datetime.utcnow(),
                )

                if self._knowledge_base is not None:
                    self._knowledge_base.record_critique(report, problem_frame)
                    metrics.set_failure_pattern_index_size(self._knowledge_base.pattern_count)

                span.set_attribute("polisyos.critic.pre_issues", len(pre_issues))
                span.set_attribute("polisyos.critic.total_issues", len(report.issues))
                span.set_attribute("polisyos.critic.verdict", report.verdict)
                return report

    async def generate_hint(self, issues: list[CritiqueIssue]) -> str:
        return await self._inner.generate_hint(issues)

    async def check_alignment(self, ir: TrinityBundle, problem_frame: ProblemFrame) -> float:
        return await self._inner.check_alignment(ir, problem_frame)

    def _pattern_issues(self, problem_frame: ProblemFrame) -> list[CritiqueIssue]:
        if self._knowledge_base is None:
            return []

        metrics = get_metrics()
        domain = self._domain(problem_frame)
        issues: list[CritiqueIssue] = []
        for pattern, score in self._knowledge_base.search_patterns(
            domain=domain,
            top_k=3,
            min_occurrence=self._failure_pattern_threshold,
        ):
            message = (
                f"Recurring failure pattern '{pattern.error_code}' observed "
                f"{pattern.occurrence_count} times (similarity={score:.2f})."
            )
            issues.append(
                CritiqueIssue(
                    issue_id=f"pattern_{pattern.signature_id}",
                    category=CritiqueCategory.COMPLIANCE,
                    severity=CritiqueSeverity.WARNING,
                    message=message,
                    location="",
                    suggestion=pattern.remediation,
                    evidence={"occurrence_count": pattern.occurrence_count},
                )
            )
            metrics.record_critic_preemptive_catch(catch_type="pattern_match")
        return issues

    async def _feasibility_issues(
        self,
        bundle: TrinityBundle,
        problem_frame: ProblemFrame,
    ) -> list[CritiqueIssue]:
        metrics = get_metrics()
        issues: list[CritiqueIssue] = []
        budget_limit = self._budget_limit(bundle, problem_frame)

        for idx, intervention in enumerate(bundle.policy_spec.interventions):
            selector = intervention.target
            fields = list(self._selector_fields(selector))
            snapshot_ref = bundle.model_spec.data_snapshot_ref

            for field in fields:
                exists = await self._feasibility.check_attribute_exists(
                    attribute_name=field,
                    data_snapshot_ref=snapshot_ref,
                )
                if exists:
                    continue
                issues.append(
                    CritiqueIssue(
                        issue_id=f"feasibility_attr_missing_{idx}_{field}",
                        category=CritiqueCategory.FEASIBILITY,
                        severity=CritiqueSeverity.BLOCKER,
                        message=(
                            f"Intervention '{intervention.intervention_id}' references "
                            f"selector field '{field}' absent in snapshot."
                        ),
                        location=f"policy_spec.interventions[{idx}].target",
                        suggestion="Use an existing selector field or adjust registry mapping.",
                    )
                )
                metrics.record_critic_preemptive_catch(catch_type="feasibility_attr")

            query_started = datetime.utcnow()
            result = await self._feasibility.count_matching_agents(
                selector_expr=selector,
                data_snapshot_ref=snapshot_ref,
            )
            query_duration = (datetime.utcnow() - query_started).total_seconds()
            metrics.record_feasibility_query(duration_seconds=query_duration, status="ok")

            if result.matching_count == 0:
                issues.append(
                    CritiqueIssue(
                        issue_id=f"feasibility_empty_target_{idx}",
                        category=CritiqueCategory.FEASIBILITY,
                        severity=CritiqueSeverity.BLOCKER,
                        message=(
                            f"Intervention '{intervention.intervention_id}' selector "
                            f"matches 0/{result.total_count} agents."
                        ),
                        location=f"policy_spec.interventions[{idx}].target",
                        suggestion="Broaden selector or verify population attributes.",
                        evidence={"snapshot_ref": snapshot_ref},
                    )
                )
                metrics.record_critic_preemptive_catch(catch_type="feasibility_empty")
            elif result.matching_count > 0 and result.match_ratio < self._feasibility_min_match_ratio:
                issues.append(
                    CritiqueIssue(
                        issue_id=f"feasibility_tiny_target_{idx}",
                        category=CritiqueCategory.FEASIBILITY,
                        severity=CritiqueSeverity.WARNING,
                        message=(
                            f"Intervention '{intervention.intervention_id}' selector "
                            f"matches only {result.matching_count}/{result.total_count} agents "
                            f"({result.match_ratio:.4%})."
                        ),
                        location=f"policy_spec.interventions[{idx}].target",
                        suggestion="Confirm this very narrow target is intentional.",
                        evidence={"snapshot_ref": snapshot_ref},
                    )
                )

            if self._enable_budget_check and budget_limit is not None:
                amount = self._extract_amount_per_agent(intervention.params)
                if amount is None:
                    continue

                budget_started = datetime.utcnow()
                budget = await self._feasibility.estimate_budget_impact(
                    selector_expr=selector,
                    amount_per_agent=amount,
                    data_snapshot_ref=snapshot_ref,
                    budget_limit=float(budget_limit),
                )
                budget_duration = (datetime.utcnow() - budget_started).total_seconds()
                metrics.record_feasibility_query(duration_seconds=budget_duration, status="budget")

                if budget.feasible is False:
                    issues.append(
                        CritiqueIssue(
                            issue_id=f"feasibility_budget_exhausted_{idx}",
                            category=CritiqueCategory.FEASIBILITY,
                            severity=CritiqueSeverity.BLOCKER,
                            message=(
                                f"Estimated intervention cost {budget.estimated_total_cost:.2f} "
                                f"exceeds budget limit {float(budget_limit):.2f}."
                            ),
                            location=f"policy_spec.interventions[{idx}].params",
                            suggestion="Reduce per-agent amount or tighten targeting.",
                            evidence={
                                "estimated_total_cost": budget.estimated_total_cost,
                                "budget_limit": float(budget_limit),
                            },
                        )
                    )
                    metrics.record_critic_preemptive_catch(catch_type="budget_exhausted")

        return issues

    def _norm_issues(
        self,
        bundle: TrinityBundle,
        problem_frame: ProblemFrame,
    ) -> list[CritiqueIssue]:
        if self._norm_loader is None:
            return []

        metrics = get_metrics()
        domain = self._domain(problem_frame)
        jurisdiction = self._jurisdiction(bundle, problem_frame)
        norm_pack = self._norm_loader.load_for_context(
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=None,
        )
        if norm_pack is None:
            return []

        issues: list[CritiqueIssue] = []
        for prohibition in (norm for norm in norm_pack.norms if norm.rule_type == RuleType.PROHIBITION):
            prohibition_tokens = set(self._keywords(prohibition.description))
            if not prohibition_tokens:
                continue
            for idx, intervention in enumerate(bundle.policy_spec.interventions):
                kind_tokens = set(self._keywords(intervention.kind))
                if not (kind_tokens & prohibition_tokens):
                    continue
                issues.append(
                    CritiqueIssue(
                        issue_id=f"norm_risk_{prohibition.norm_id}_{idx}",
                        category=CritiqueCategory.COMPLIANCE,
                        severity=CritiqueSeverity.WARNING,
                        message=(
                            f"Intervention '{intervention.intervention_id}' may conflict with "
                            f"prohibition '{prohibition.norm_id}'."
                        ),
                        location=f"policy_spec.interventions[{idx}]",
                        suggestion=f"Review prohibition: {prohibition.description[:180]}",
                    )
                )
                metrics.record_critic_preemptive_catch(catch_type="norm_prohibition")
        return issues

    def _merge_issues(
        self,
        pre_issues: Iterable[CritiqueIssue],
        inner_issues: Iterable[CritiqueIssue],
        domain: str,
    ) -> list[CritiqueIssue]:
        merged: dict[str, CritiqueIssue] = {}
        for issue in list(pre_issues) + list(inner_issues):
            signature = self._issue_signature(issue, domain=domain)
            current = merged.get(signature)
            if current is None or _SEVERITY_ORDER[issue.severity] > _SEVERITY_ORDER[current.severity]:
                merged[signature] = issue
        return list(merged.values())

    def _recompute_verdict(self, inner_verdict: str, issues: list[CritiqueIssue]) -> str:
        has_blockers = any(issue.severity == CritiqueSeverity.BLOCKER for issue in issues)
        warning_count = sum(1 for issue in issues if issue.severity == CritiqueSeverity.WARNING)

        if inner_verdict == "REJECT" or has_blockers:
            return "REJECT"
        if inner_verdict == "NEEDS_REVISION" or warning_count > 2:
            return "NEEDS_REVISION"
        return "APPROVE" if inner_verdict == "APPROVE" else "NEEDS_REVISION"

    def _budget_limit(self, bundle: TrinityBundle, problem_frame: ProblemFrame) -> Decimal | None:
        # Use agent-problem-frame if it contains explicit budget string; otherwise fallback to IR bundle.
        context = self._constraint_assembler.build(problem_frame)
        if context.budget_envelope is not None:
            return context.budget_envelope
        return self._constraint_assembler.build(bundle.problem_frame).budget_envelope

    @staticmethod
    def _extract_amount_per_agent(params: dict[str, Any]) -> float | None:
        for key, value in params.items():
            key_lower = str(key).lower()
            if not any(hint in key_lower for hint in _AMOUNT_PARAM_HINTS):
                continue
            numeric = InformedCriticAgent._to_float(value)
            if numeric is None:
                continue
            if numeric < 0:
                continue
            return numeric
        return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            try:
                return float(Decimal(value.strip()))
            except (InvalidOperation, ValueError):
                return None
        return None

    @staticmethod
    def _selector_fields(selector: SelectorExpr) -> set[str]:
        fields: set[str] = set()
        if isinstance(selector, SelectorPredicate):
            fields.add(selector.field)
        elif isinstance(selector, SelectorNot):
            fields.update(InformedCriticAgent._selector_fields(selector.clause))
        elif isinstance(selector, (SelectorAll, SelectorAny)):
            for clause in selector.clauses:
                fields.update(InformedCriticAgent._selector_fields(clause))
        return fields

    @staticmethod
    def _keywords(text: str) -> list[str]:
        return [token for token in text.lower().replace("_", " ").split() if len(token) > 3]

    @staticmethod
    def _domain(problem_frame: ProblemFrame) -> str:
        domain = getattr(problem_frame, "domain", "general")
        return str(getattr(domain, "value", domain or "general"))

    @staticmethod
    def _jurisdiction(bundle: TrinityBundle, problem_frame: ProblemFrame) -> str:
        labels = getattr(bundle.problem_frame, "labels", None)
        if isinstance(labels, list) and labels:
            return str(labels[0])
        context = getattr(problem_frame, "context", {})
        if isinstance(context, dict) and isinstance(context.get("jurisdiction"), str):
            return str(context["jurisdiction"])
        return "default"

    @staticmethod
    def _to_bundle(ir: TrinityBundle) -> TrinityBundle:
        if isinstance(ir, TrinityBundle):
            return ir
        raise TypeError(f"Unsupported IR type for informed critique: {type(ir)}")

    @staticmethod
    def _issue_signature(issue: CritiqueIssue, *, domain: str) -> str:
        normalized_location = issue.location.replace("[", "[]") if issue.location else ""
        material = "|".join(
            [
                issue.category.value,
                issue.severity.value,
                normalized_location,
                issue.message.lower().strip(),
                domain.lower(),
            ]
        )
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        return digest[:24]


__all__ = ["InformedCriticAgent", "InformedCriticConfig"]
