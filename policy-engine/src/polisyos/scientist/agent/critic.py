"""Critic agents for Trinity-first review."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any

from polisyos.core.canon import content_hash, truncated_hash
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.agent.feasibility import FeasibilityProbe
from polisyos.scientist.agent.informed_critic import InformedCriticAgent, InformedCriticConfig
from polisyos.scientist.agent.knowledge_base import CriticKnowledgeBase
from polisyos.scientist.agent.norm_loader import NormPackLoader
from polisyos.scientist.agent.prompts import get_critic_prompt
from polisyos.scientist.agent.protocols import (
    CriticAgent,
    CritiqueCategory,
    CritiqueIssue,
    CritiqueReport,
    CritiqueSeverity,
    ProblemFrame,
)
from polisyos.scientist.llm import TracedLLMClient

_COMMON_WORDS = {
    "the",
    "a",
    "an",
    "to",
    "by",
    "for",
    "in",
    "of",
    "and",
    "or",
    "with",
    "on",
    "at",
    "from",
    "is",
    "are",
}


def _as_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _to_trinity_bundle(ir: TrinityBundle) -> TrinityBundle:
    if isinstance(ir, TrinityBundle):
        return ir

    raise TypeError(f"Unsupported IR type for critique: {type(ir)}")


def _tokenize(text: str) -> set[str]:
    tokens = {token.strip().lower() for token in text.replace("_", " ").split()}
    return {token for token in tokens if token and token not in _COMMON_WORDS}


class MockCriticAgent:
    """Mock implementation of CriticAgent."""

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
        ir: TrinityBundle,
        problem_frame: ProblemFrame,
        *,
        depth: str = "standard",
    ) -> CritiqueReport:
        self._critique_count += 1
        bundle = _to_trinity_bundle(ir)

        report_id = f"critique_{uuid.uuid4().hex[:8]}"
        ir_ref = f"bundle_{truncated_hash(bundle.model_dump_json(), length=16)}"

        issues: list[CritiqueIssue] = []
        issues.extend(await self._check_structure(bundle))

        alignment_score = await self.check_alignment(bundle, problem_frame)
        issues.extend(await self._check_alignment_issues(alignment_score))

        completeness_score, completeness_issues = await self._check_completeness(bundle)
        issues.extend(completeness_issues)

        if depth == "deep":
            issues.extend(await self._deep_analysis(bundle))

        has_blockers = any(issue.severity == CritiqueSeverity.BLOCKER for issue in issues)
        has_warnings = any(issue.severity == CritiqueSeverity.WARNING for issue in issues)

        if has_blockers:
            verdict = "REJECT"
        elif has_warnings or alignment_score < self._alignment_threshold:
            verdict = "NEEDS_REVISION"
        else:
            verdict = self._default_verdict

        blocker_penalty = sum(
            1 for issue in issues if issue.severity == CritiqueSeverity.BLOCKER
        ) * 0.3
        warning_penalty = sum(
            1 for issue in issues if issue.severity == CritiqueSeverity.WARNING
        ) * 0.1
        overall_quality = max(
            0.0,
            (alignment_score + completeness_score) / 2 - blocker_penalty - warning_penalty,
        )

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
                "artifact_kind": "trinity_bundle",
            },
            created_at=datetime.utcnow(),
        )

    async def _check_structure(self, bundle: TrinityBundle) -> list[CritiqueIssue]:
        issues: list[CritiqueIssue] = []

        if not bundle.policy_spec.interventions:
            issues.append(
                CritiqueIssue(
                    issue_id="struct_interventions",
                    category=CritiqueCategory.COMPLETENESS,
                    severity=CritiqueSeverity.BLOCKER,
                    message="No interventions defined in policy_spec",
                    location="policy_spec.interventions",
                    suggestion="Add at least one intervention.",
                )
            )

        if not bundle.problem_frame.objectives:
            issues.append(
                CritiqueIssue(
                    issue_id="struct_objectives",
                    category=CritiqueCategory.COMPLETENESS,
                    severity=CritiqueSeverity.WARNING,
                    message="No objectives defined in problem_frame",
                    location="problem_frame.objectives",
                    suggestion="Define measurable objectives aligned to goals.",
                )
            )

        if not bundle.model_spec.data_snapshot_ref:
            issues.append(
                CritiqueIssue(
                    issue_id="struct_data_snapshot",
                    category=CritiqueCategory.SCHEMA,
                    severity=CritiqueSeverity.BLOCKER,
                    message="Missing model_spec.data_snapshot_ref",
                    location="model_spec.data_snapshot_ref",
                    suggestion="Set a valid data snapshot artifact reference.",
                )
            )

        return issues

    async def _check_alignment_issues(self, alignment_score: float) -> list[CritiqueIssue]:
        issues: list[CritiqueIssue] = []
        if alignment_score < 0.5:
            issues.append(
                CritiqueIssue(
                    issue_id="align_blocker",
                    category=CritiqueCategory.ALIGNMENT,
                    severity=CritiqueSeverity.BLOCKER,
                    message=f"Low alignment with ProblemFrame (score: {alignment_score:.2f})",
                    location="policy_spec",
                    suggestion="Revise interventions to target explicit problem goals.",
                )
            )
        elif alignment_score < self._alignment_threshold:
            issues.append(
                CritiqueIssue(
                    issue_id="align_warning",
                    category=CritiqueCategory.ALIGNMENT,
                    severity=CritiqueSeverity.WARNING,
                    message=f"Moderate alignment with ProblemFrame (score: {alignment_score:.2f})",
                    location="policy_spec",
                    suggestion="Strengthen mapping between goals and interventions.",
                )
            )
        return issues

    async def _check_completeness(
        self,
        bundle: TrinityBundle,
    ) -> tuple[float, list[CritiqueIssue]]:
        issues: list[CritiqueIssue] = []
        checks_passed = 0
        total_checks = 4

        if bundle.policy_spec.interventions:
            checks_passed += 1
        if bundle.problem_frame.objectives:
            checks_passed += 1
        else:
            issues.append(
                CritiqueIssue(
                    issue_id="comp_objectives",
                    category=CritiqueCategory.COMPLETENESS,
                    severity=CritiqueSeverity.INFO,
                    message="Add explicit objectives for better optimization.",
                    location="problem_frame.objectives",
                )
            )
        if bundle.problem_frame.hard_constraints or bundle.problem_frame.soft_constraints:
            checks_passed += 1
        if bundle.model_spec.assumptions:
            checks_passed += 1

        return checks_passed / total_checks, issues

    async def _deep_analysis(self, bundle: TrinityBundle) -> list[CritiqueIssue]:
        issues: list[CritiqueIssue] = []
        for idx, intervention in enumerate(bundle.policy_spec.interventions):
            for param_name, value in intervention.params.items():
                if not isinstance(value, str):
                    continue
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    continue
                if param_name in {"rate", "tax_rate", "subsidy_rate"} and numeric > 1.0:
                    issues.append(
                        CritiqueIssue(
                            issue_id=f"deep_rate_{idx}_{param_name}",
                            category=CritiqueCategory.FEASIBILITY,
                            severity=CritiqueSeverity.WARNING,
                            message=f"Intervention parameter {param_name}={numeric} is likely unrealistic.",
                            location=f"policy_spec.interventions[{idx}].params.{param_name}",
                            suggestion="Use rates in [0, 1] unless intentionally scaled.",
                        )
                    )
        return issues

    async def generate_hint(self, issues: list[CritiqueIssue]) -> str:
        if not issues:
            return "No issues identified."

        blockers = [issue for issue in issues if issue.severity == CritiqueSeverity.BLOCKER]
        warnings = [issue for issue in issues if issue.severity == CritiqueSeverity.WARNING]

        lines: list[str] = []
        if blockers:
            top = blockers[0]
            lines.append(
                f"Fix blocker first: {top.message} at {top.location or 'unknown location'}."
            )
            if top.suggestion:
                lines.append(top.suggestion)
        elif warnings:
            top = warnings[0]
            lines.append(f"Address warning: {top.message}")
            if top.suggestion:
                lines.append(top.suggestion)
        else:
            lines.append("Apply informational improvements and re-run critique.")

        return " ".join(lines)

    async def check_alignment(
        self,
        ir: TrinityBundle,
        problem_frame: ProblemFrame,
    ) -> float:
        bundle = _to_trinity_bundle(ir)

        goal_tokens: set[str] = set()
        goal_tokens.update(_tokenize(problem_frame.problem_statement))
        for goal in problem_frame.goals:
            goal_tokens.update(_tokenize(goal))
        if not goal_tokens:
            return 0.8

        policy_tokens: set[str] = set()
        for intervention in bundle.policy_spec.interventions:
            policy_tokens.update(_tokenize(intervention.kind))
            policy_tokens.update(_tokenize(intervention.intervention_id))
            for key in intervention.params.keys():
                policy_tokens.update(_tokenize(str(key)))
        for objective in bundle.problem_frame.objectives:
            policy_tokens.update(_tokenize(objective.metric_id))

        if not policy_tokens:
            return 0.0

        overlap = len(goal_tokens & policy_tokens)
        score = overlap / max(min(len(goal_tokens), 10), 1)
        return min(1.0, max(0.0, 0.6 + 0.4 * score))

    @property
    def critique_count(self) -> int:
        return self._critique_count

    def reset(self) -> None:
        self._critique_count = 0

    def set_default_verdict(self, verdict: str) -> None:
        self._default_verdict = verdict


class LLMCriticAgent:
    """LLM-powered critic for Trinity bundles."""

    def __init__(self, llm_client: Any, model_name: str | None = None) -> None:
        if llm_client is not None and not isinstance(llm_client, TracedLLMClient):
            self._llm = TracedLLMClient(llm_client, model_name=model_name)
        else:
            self._llm = llm_client

    async def critique(
        self,
        ir: TrinityBundle,
        problem_frame: ProblemFrame,
        *,
        depth: str = "standard",
    ) -> CritiqueReport:
        prompt = get_critic_prompt()
        bundle = _to_trinity_bundle(ir)

        bundle_json = bundle.model_dump_json(indent=2)
        pf_payload = {
            "frame_id": problem_frame.frame_id,
            "domain": problem_frame.domain,
            "problem_statement": problem_frame.problem_statement,
            "goals": list(problem_frame.goals),
            "constraints": list(problem_frame.constraints),
            "success_criteria": problem_frame.success_criteria,
            "assumptions": list(problem_frame.assumptions),
        }

        user_message = f"""
PROBLEM FRAME:
{json.dumps(pf_payload, indent=2)}

TRINITY BUNDLE TO REVIEW:
{bundle_json}

REVIEW DEPTH: {depth}

Provide your critique as a JSON object.
"""

        response = await self._llm.generate(
            system=prompt,
            user=user_message,
            response_format={"type": "json_object"},
        )

        content = response.content if hasattr(response, "content") else str(response)
        try:
            data = json.loads(content)
            issues = []
            for idx, issue in enumerate(data.get("issues", [])):
                category = issue.get("category", "SCHEMA")
                severity = issue.get("severity", "WARNING")
                try:
                    category_enum = CritiqueCategory(category.lower())
                except ValueError:
                    category_enum = CritiqueCategory.SCHEMA
                try:
                    severity_enum = CritiqueSeverity(severity.lower())
                except ValueError:
                    severity_enum = CritiqueSeverity.WARNING
                issues.append(
                    CritiqueIssue(
                        issue_id=issue.get("issue_id", f"issue_{idx}"),
                        category=category_enum,
                        severity=severity_enum,
                        message=issue.get("message", ""),
                        location=issue.get("location", ""),
                        suggestion=issue.get("suggestion", ""),
                    )
                )

            ir_ref = data.get("ir_ref")
            if not ir_ref:
                ir_ref = content_hash(bundle_json)

            return CritiqueReport(
                report_id=data.get("report_id", str(uuid.uuid4())),
                ir_ref=ir_ref,
                problem_frame_ref=problem_frame.frame_id,
                verdict=data.get("verdict", "NEEDS_REVISION"),
                issues=issues,
                alignment_score=float(data.get("alignment_score", 0.5)),
                completeness_score=float(data.get("completeness_score", 0.5)),
                overall_quality=float(data.get("overall_quality", 0.5)),
                reflexion_hint=data.get("reflexion_hint", ""),
                metadata={"artifact_kind": "trinity_bundle", "depth": depth},
                created_at=datetime.utcnow(),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            return CritiqueReport(
                report_id=str(uuid.uuid4()),
                ir_ref="",
                problem_frame_ref=problem_frame.frame_id,
                verdict="NEEDS_REVISION",
                issues=[
                    CritiqueIssue(
                        issue_id="parse_error",
                        category=CritiqueCategory.SCHEMA,
                        severity=CritiqueSeverity.WARNING,
                        message=f"Critique parse error: {exc}",
                    )
                ],
                reflexion_hint="Unable to parse critique response. Please review manually.",
                metadata={"artifact_kind": "trinity_bundle", "depth": depth},
            )

    async def generate_hint(self, issues: list[CritiqueIssue]) -> str:
        if not issues:
            return "No issues identified."

        blockers = [issue for issue in issues if issue.severity == CritiqueSeverity.BLOCKER]
        warnings = [issue for issue in issues if issue.severity == CritiqueSeverity.WARNING]

        hint_parts = []
        if blockers:
            top_blocker = blockers[0]
            hint_parts.append(
                f"CRITICAL: {top_blocker.message}. "
                f"Fix at {top_blocker.location or 'unspecified location'}. "
                f"{top_blocker.suggestion or ''}"
            )
        if warnings and len(hint_parts) < 2:
            top_warning = warnings[0]
            hint_parts.append(f"WARNING: {top_warning.message}. {top_warning.suggestion or ''}")

        return " ".join(part for part in hint_parts if part).strip() or (
            "Review all issues and address systematically."
        )

    async def check_alignment(
        self,
        ir: TrinityBundle,
        problem_frame: ProblemFrame,
    ) -> float:
        return await MockCriticAgent().check_alignment(ir, problem_frame)


def create_critic_agent(
    llm_client: Any | None,
    *,
    model_name: str | None = None,
    inner: CriticAgent | None = None,
    informed_config: InformedCriticConfig | None = None,
    norm_loader: NormPackLoader | None = None,
    feasibility_probe: FeasibilityProbe | None = None,
    knowledge_base: CriticKnowledgeBase | None = None,
) -> CriticAgent:
    """
    Build critic according to feature flag `POLISYOS_INFORMED_CRITIC_ENABLED`.

    Defaults:
    - Base critic: `LLMCriticAgent` when llm client is provided, else `MockCriticAgent`.
    - Informed wrapper: disabled unless env flag is enabled.
    """
    critic_mode = os.getenv("POLISYOS_CRITIC_MODE", "").strip().lower()
    if inner is not None:
        base_critic: CriticAgent = inner
    elif critic_mode == "mock" or llm_client is None:
        base_critic = MockCriticAgent()
    else:
        base_critic = LLMCriticAgent(llm_client, model_name=model_name)

    informed_enabled = _as_bool(
        os.getenv("POLISYOS_INFORMED_CRITIC_ENABLED"),
        default=False,
    )
    if not informed_enabled:
        return base_critic

    config = informed_config or InformedCriticConfig.from_env()
    return InformedCriticAgent(
        inner=base_critic,
        norm_loader=norm_loader,
        feasibility_probe=feasibility_probe,
        knowledge_base=knowledge_base,
        config=config,
    )


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


__all__ = [
    "InformedCriticAgent",
    "InformedCriticConfig",
    "LLMCriticAgent",
    "MockCriticAgent",
    "create_critic_agent",
    "create_mock_problem_frame",
]
