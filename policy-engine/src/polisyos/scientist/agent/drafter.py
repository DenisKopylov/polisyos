"""
Drafter Agent Module
====================

LLM-based policy draft generation with protocol conformance.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from polisyos.core.observability import get_metrics, get_tracer
from polisyos.core.observability.pricing import estimate_llm_cost_usd
from polisyos.scientist.agent.memory import ShortTermMemory
from polisyos.scientist.agent.prompts import get_drafter_prompt, get_self_critique_prompt
from polisyos.scientist.agent.protocols import (
    CritiqueReport,
    DrafterAgent,
    DraftResult,
    ProblemFrame,
)
from polisyos.scientist.llm import TracedLLMClient

logger = logging.getLogger(__name__)


def _as_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class FindingSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingCategory(str, Enum):
    SIDE_EFFECT = "side_effect"
    MISSING_GROUP = "missing_group"
    BUDGET_VIOLATION = "budget_violation"
    CONSTRAINT_CONFLICT = "constraint_conflict"
    PARAMETER_ERROR = "parameter_error"
    TARGET_OVERLAP = "target_overlap"
    EQUITY_CONCERN = "equity_concern"
    FEASIBILITY_ISSUE = "feasibility_issue"
    OTHER = "other"


_SEVERITY_ORDER: dict[FindingSeverity, int] = {
    FindingSeverity.LOW: 0,
    FindingSeverity.MEDIUM: 1,
    FindingSeverity.HIGH: 2,
    FindingSeverity.CRITICAL: 3,
}


@dataclass(frozen=True, slots=True)
class PassFinding:
    """One issue discovered by a self-critique pass."""

    finding_id: str
    category: FindingCategory
    severity: FindingSeverity
    description: str
    suggested_fix: str = ""
    affected_intervention: str | None = None
    anchor: str = "none"
    source_pass: str = ""

    def as_memory_dict(self) -> dict[str, str]:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "description": self.description,
            "suggested_fix": self.suggested_fix,
            "affected_intervention": self.affected_intervention or "",
            "anchor": self.anchor,
        }


@dataclass(slots=True)
class PassExecution:
    """Execution details for one pass in the multipass pipeline."""

    pass_name: str
    pass_number: int
    executed: bool
    draft: DraftResult | None = None
    skip_reason: str = ""
    findings: list[PassFinding] = field(default_factory=list)
    raw_llm_response: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    parse_ok: bool = True
    confidence_adjustment: float | None = None


class MultiPassConfig(BaseModel):
    """Configuration for the multipass self-critique drafter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_passes: int = Field(default=4, ge=1, le=4)
    early_exit_confidence: float = Field(default=0.90, ge=0.0, le=1.0)
    finding_severity_threshold: FindingSeverity = Field(default=FindingSeverity.MEDIUM)
    budget_limit_usd: float = Field(default=0.20, ge=0.0)
    max_extra_llm_calls: int = Field(default=3, ge=0)
    pass_timeout_s: float = Field(default=30.0, gt=0.0, le=300.0)
    pass_retry_count: int = Field(default=1, ge=0, le=3)
    critique_model: str | None = Field(default=None)
    enable_memory_logging: bool = Field(default=True)
    shadow_mode: bool = Field(default=False)

    @field_validator("budget_limit_usd")
    @classmethod
    def _validate_budget(cls, value: float) -> float:
        if value < 0.01:
            raise ValueError("budget_limit_usd must be >= 0.01")
        return value

    @classmethod
    def from_env(cls) -> "MultiPassConfig":
        kwargs: dict[str, Any] = {}
        raw_max_passes = os.getenv("POLISYOS_DRAFTER_MAX_PASSES")
        if raw_max_passes:
            kwargs["max_passes"] = int(raw_max_passes)

        raw_early_exit = os.getenv("POLISYOS_DRAFTER_EARLY_EXIT_CONFIDENCE")
        if raw_early_exit:
            kwargs["early_exit_confidence"] = float(raw_early_exit)

        raw_budget = os.getenv("POLISYOS_DRAFTER_BUDGET_LIMIT_USD")
        if raw_budget:
            kwargs["budget_limit_usd"] = float(raw_budget)

        raw_extra_calls = os.getenv("POLISYOS_DRAFTER_MAX_EXTRA_LLM_CALLS")
        if raw_extra_calls:
            kwargs["max_extra_llm_calls"] = int(raw_extra_calls)

        raw_timeout = os.getenv("POLISYOS_DRAFTER_PASS_TIMEOUT_S")
        if raw_timeout:
            kwargs["pass_timeout_s"] = float(raw_timeout)

        raw_retry = os.getenv("POLISYOS_DRAFTER_PASS_RETRY_COUNT")
        if raw_retry:
            kwargs["pass_retry_count"] = int(raw_retry)

        raw_critique_model = os.getenv("POLISYOS_DRAFTER_CRITIQUE_MODEL")
        if raw_critique_model:
            kwargs["critique_model"] = raw_critique_model.strip()

        raw_memory = os.getenv("POLISYOS_DRAFTER_ENABLE_MEMORY_LOGGING")
        if raw_memory is not None:
            kwargs["enable_memory_logging"] = _as_bool(raw_memory, default=True)

        raw_threshold = os.getenv("POLISYOS_DRAFTER_FINDING_SEVERITY_THRESHOLD")
        if raw_threshold:
            kwargs["finding_severity_threshold"] = FindingSeverity(raw_threshold.strip().lower())

        raw_mode = os.getenv("POLISYOS_DRAFTER_MULTIPASS_MODE")
        if raw_mode:
            kwargs["shadow_mode"] = raw_mode.strip().lower() == "shadow"

        return cls(**kwargs)


class _FindingPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: str = "other"
    severity: str = "medium"
    description: str
    suggested_fix: str = ""
    affected_intervention: str | None = None
    anchor: str = "none"


class _CritiquePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    findings: list[_FindingPayload] = Field(default_factory=list)
    confidence_adjustment: float | None = None


class _ConsolidationPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    narrative: str = ""
    interventions: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str = ""
    alternatives_considered: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class MockLLM:
    def invoke(self, prompt: str) -> str:
        """Эмулирует ответ GPT-4, возвращая валидный JSON."""
        print(f"   [MockLLM] 'Thinking' about: {prompt[:50]}...")

        return """
        {
          "schema_version": "2.0",
          "semantic": {
            "context_snapshot_ref": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "time_semantics": {
              "frequency": "M",
              "start_date": "2024-01-01",
              "step_count": 12
            },
            "objectives": [
              {
                "objective_id": "maximize_income",
                "metric_id": "avg_income",
                "direction": "maximize",
                "weight": "1"
              }
            ],
            "interventions": [
              {
                "intervention_id": "help_poor",
                "kind": "tax_subsidy",
                "target": {
                  "kind": "predicate",
                  "field": "income",
                  "operator": "<",
                  "value": "1000"
                },
                "schedule": {
                  "start_step": 0,
                  "duration_steps": 12
                },
                "params": {
                  "rate": "0.2"
                }
              }
            ],
            "constraints": [
              {
                "constraint_id": "min_balance",
                "value": {
                  "amount": "-5000",
                  "currency": "USD"
                }
              }
            ]
          },
          "advisory": {
            "entities": [
              {
                "entity_id": "poor_group",
                "entity_type": "agent",
                "name": {"en": "Poor", "ua": "Бідні"}
              }
            ],
            "labels": ["poverty"]
          }
        }
        """


class MockDrafterAgent:
    """Mock implementation of DrafterAgent for testing."""

    def __init__(self) -> None:
        self._draft_count: int = 0
        self._refine_count: int = 0

    async def draft_policy(
        self,
        problem_frame: ProblemFrame,
        *,
        hints: list[str] | None = None,
        prior_drafts: list[DraftResult] | None = None,
    ) -> DraftResult:
        if not problem_frame.frame_id:
            raise ValueError("ProblemFrame must have a valid frame_id")

        self._draft_count += 1

        base_hash = hashlib.sha256(problem_frame.frame_id.encode()).hexdigest()[:8]
        draft_id = f"draft_{base_hash}_{self._draft_count}"

        interventions = self._generate_interventions(problem_frame)
        narrative = self._build_narrative(problem_frame, hints)
        rationale = self._build_rationale(problem_frame, prior_drafts)

        confidence = 0.7
        if hints:
            confidence += 0.1
        if prior_drafts:
            confidence += 0.05 * min(len(prior_drafts), 3)

        return DraftResult(
            draft_id=draft_id,
            problem_frame_ref=problem_frame.frame_id,
            narrative=narrative,
            interventions=interventions,
            rationale=rationale,
            domain_references=self._get_domain_references(problem_frame.domain),
            confidence=min(0.95, confidence),
            alternatives_considered=self._get_alternatives(problem_frame),
            raw_llm_response=None,
            created_at=datetime.utcnow(),
        )

    def _generate_interventions(self, problem_frame: ProblemFrame) -> list[dict[str, Any]]:
        domain = problem_frame.domain.lower()

        if domain == "economic":
            return [
                {
                    "kind": "tax_subsidy",
                    "description": "Targeted subsidy for low-income groups",
                    "target": {
                        "kind": "predicate",
                        "field": "income",
                        "operator": "<",
                        "value": "1000",
                    },
                    "params": {"rate": "0.15"},
                },
                {
                    "kind": "income_tax",
                    "description": "Progressive taxation on high earners",
                    "target": {
                        "kind": "predicate",
                        "field": "income",
                        "operator": ">",
                        "value": "5000",
                    },
                    "params": {"rate": "0.25"},
                },
            ]
        if domain == "healthcare":
            return [
                {
                    "kind": "healthcare_subsidy",
                    "description": "Subsidized healthcare for vulnerable populations",
                    "target": {
                        "kind": "predicate",
                        "field": "health_coverage",
                        "operator": "==",
                        "value": "false",
                    },
                    "params": {"coverage_rate": "0.8"},
                }
            ]

        return [
            {
                "kind": "general_intervention",
                "description": "General policy intervention",
                "target": {
                    "kind": "predicate",
                    "field": "id",
                    "operator": "==",
                    "value": "all",
                },
                "params": {"rate": "0.1"},
            }
        ]

    def _build_narrative(self, problem_frame: ProblemFrame, hints: list[str] | None) -> str:
        parts = [
            f"Policy proposal to address: {problem_frame.problem_statement}",
            "",
            f"Domain: {problem_frame.domain}",
            f"Target actors: {', '.join(problem_frame.actors)}",
            "",
            "Proposed approach:",
            "This policy employs a multi-pronged strategy combining targeted interventions",
            "with careful consideration of the stated constraints.",
        ]

        if hints:
            parts.extend(
                [
                    "",
                    "Incorporating feedback from previous review:",
                    *[f"- {hint}" for hint in hints[:3]],
                ]
            )

        return "\n".join(parts)

    def _build_rationale(
        self,
        problem_frame: ProblemFrame,
        prior_drafts: list[DraftResult] | None,
    ) -> str:
        rationale_parts = [
            f"This approach was chosen to directly address the core problem: {problem_frame.problem_statement[:100]}",
        ]

        if prior_drafts:
            rationale_parts.append(
                f"Building on {len(prior_drafts)} prior draft(s), this iteration incorporates lessons learned."
            )

        rationale_parts.append(
            "The interventions are designed to work within the stated constraints while maximizing impact."
        )

        return " ".join(rationale_parts)

    def _get_domain_references(self, domain: str) -> list[str]:
        refs = {
            "economic": [
                "Piketty, T. (2014). Capital in the Twenty-First Century",
                "Banerjee & Duflo (2011). Poor Economics",
            ],
            "healthcare": [
                "WHO (2010). Health Systems Financing",
                "Hsiao, W. (2007). Why Is A Systemic View Of Health Financing Necessary?",
            ],
            "education": [
                "Heckman, J. (2006). Skill Formation and the Economics of Investing in Disadvantaged Children",
            ],
        }
        return refs.get(domain.lower(), ["General policy literature"])

    def _get_alternatives(self, problem_frame: ProblemFrame) -> list[str]:
        return [
            "Direct cash transfers (rejected: higher administrative overhead)",
            "Universal programs (rejected: less targeted, higher cost)",
            "Market-based solutions (rejected: may not reach most vulnerable)",
        ]

    async def refine_draft(
        self,
        draft: DraftResult,
        critique: CritiqueReport,
    ) -> DraftResult:
        if not draft.draft_id:
            raise ValueError("Draft must have a valid draft_id")

        self._refine_count += 1

        hints = [critique.reflexion_hint] if critique.reflexion_hint else []
        for issue in critique.issues[:3]:
            if issue.suggestion:
                hints.append(f"Addressing: {issue.suggestion}")

        refined_narrative = draft.narrative + "\n\n[REFINED]\n" + "\n".join(hints)

        return DraftResult(
            draft_id=f"{draft.draft_id}_refined_{self._refine_count}",
            problem_frame_ref=draft.problem_frame_ref,
            narrative=refined_narrative,
            interventions=draft.interventions,
            rationale=f"{draft.rationale} [Refined based on critique]",
            domain_references=draft.domain_references,
            confidence=min(0.95, draft.confidence + 0.05),
            alternatives_considered=draft.alternatives_considered,
            raw_llm_response=None,
            created_at=datetime.utcnow(),
        )

    @property
    def draft_count(self) -> int:
        return self._draft_count

    @property
    def refine_count(self) -> int:
        return self._refine_count

    def reset(self) -> None:
        self._draft_count = 0
        self._refine_count = 0


class LLMDrafterAgent:
    """LLM-powered drafter agent for producing DraftResult artifacts."""

    def __init__(self, llm_client: Any, model_name: str | None = None) -> None:
        if llm_client is not None and not isinstance(llm_client, TracedLLMClient):
            self._llm = TracedLLMClient(llm_client, model_name=model_name)
        else:
            self._llm = llm_client

    async def draft_policy(
        self,
        problem_frame: ProblemFrame,
        *,
        hints: list[str] | None = None,
        prior_drafts: list[DraftResult] | None = None,
    ) -> DraftResult:
        if not problem_frame.frame_id:
            raise ValueError("ProblemFrame must have a valid frame_id")

        prompt = get_drafter_prompt(hints=hints)
        pf_payload = {
            "frame_id": problem_frame.frame_id,
            "domain": problem_frame.domain,
            "problem_statement": problem_frame.problem_statement,
            "actors": list(problem_frame.actors),
            "goals": list(problem_frame.goals),
            "constraints": list(problem_frame.constraints),
            "success_criteria": problem_frame.success_criteria,
            "assumptions": list(problem_frame.assumptions),
        }
        prior_payload = []
        if prior_drafts:
            prior_payload = [
                {"draft_id": draft.draft_id, "summary": draft.narrative[:200]}
                for draft in prior_drafts
            ]

        user_message = f"""
PROBLEM FRAME:
{json.dumps(pf_payload, indent=2)}

PRIOR DRAFTS:
{json.dumps(prior_payload, indent=2)}

Generate a draft JSON object.
"""

        response = await self._llm.generate(
            system=prompt,
            user=user_message,
            response_format={"type": "json_object"},
        )

        content = response.content if hasattr(response, "content") else str(response)
        try:
            data = json.loads(content)
            return DraftResult(
                draft_id=data.get("draft_id", f"draft_{uuid.uuid4().hex[:8]}"),
                problem_frame_ref=data.get("problem_frame_ref", problem_frame.frame_id),
                narrative=data.get("narrative", ""),
                interventions=data.get("interventions", []),
                rationale=data.get("rationale", ""),
                alternatives_considered=data.get("alternatives_considered", []),
                confidence=float(data.get("confidence", 0.6)),
                raw_llm_response=content,
                created_at=datetime.utcnow(),
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            fallback = MockDrafterAgent()
            return await fallback.draft_policy(
                problem_frame,
                hints=hints,
                prior_drafts=prior_drafts,
            )

    async def refine_draft(
        self,
        draft: DraftResult,
        critique: CritiqueReport,
    ) -> DraftResult:
        hints = [critique.reflexion_hint] if critique.reflexion_hint else []
        for issue in critique.issues[:3]:
            if issue.suggestion:
                hints.append(f"Addressing: {issue.suggestion}")
        refined_narrative = draft.narrative + "\n\n[REFINED]\n" + "\n".join(hints)
        return DraftResult(
            draft_id=f"{draft.draft_id}_refined",
            problem_frame_ref=draft.problem_frame_ref,
            narrative=refined_narrative,
            interventions=draft.interventions,
            rationale=f"{draft.rationale} [Refined based on critique]",
            domain_references=draft.domain_references,
            confidence=min(0.95, draft.confidence + 0.05),
            alternatives_considered=draft.alternatives_considered,
            raw_llm_response=draft.raw_llm_response,
            created_at=datetime.utcnow(),
        )


class MultiPassLLMDrafter:
    """
    Multipass self-critique wrapper over an existing DrafterAgent.

    Behavior:
    - Pass 1: delegate to inner drafter.
    - Pass 1.5: deterministic checks (no LLM call).
    - Pass 2: side effects check.
    - Pass 3: constraints verification.
    - Pass 4: consolidation.
    """

    def __init__(
        self,
        inner: DrafterAgent,
        *,
        config: MultiPassConfig | None = None,
        memory: ShortTermMemory | None = None,
        llm_client: Any | None = None,
    ) -> None:
        self._inner = inner
        self._config = config or MultiPassConfig()
        self._memory = memory
        self._llm = self._resolve_llm(llm_client, inner)

    async def draft_policy(
        self,
        problem_frame: ProblemFrame,
        *,
        hints: list[str] | None = None,
        prior_drafts: list[DraftResult] | None = None,
    ) -> DraftResult:
        try:
            return await self._draft_policy_impl(
                problem_frame,
                hints=hints,
                prior_drafts=prior_drafts,
            )
        except Exception as exc:
            logger.exception("Multipass drafter failed; fallback to single-pass: %s", exc)
            return await self._inner.draft_policy(
                problem_frame,
                hints=hints,
                prior_drafts=prior_drafts,
            )

    async def refine_draft(
        self,
        draft: DraftResult,
        critique: CritiqueReport,
    ) -> DraftResult:
        return await self._inner.refine_draft(draft, critique)

    async def _draft_policy_impl(
        self,
        problem_frame: ProblemFrame,
        *,
        hints: list[str] | None = None,
        prior_drafts: list[DraftResult] | None = None,
    ) -> DraftResult:
        tracer = get_tracer()
        metrics = get_metrics()
        pass_results: list[PassExecution] = []
        cumulative_cost_usd = 0.0
        extra_llm_calls = 0
        early_exit = False
        stop_reason = ""

        with tracer.start_as_current_span(
            "drafter.multi_pass",
            attributes={
                "polisyos.drafter.max_passes": self._config.max_passes,
                "polisyos.drafter.budget_limit_usd": self._config.budget_limit_usd,
                "polisyos.drafter.early_exit_confidence": self._config.early_exit_confidence,
                "polisyos.drafter.problem_frame_id": problem_frame.frame_id,
            },
        ) as parent_span:
            pass1 = await self._execute_pass1(
                problem_frame,
                hints=hints,
                prior_drafts=prior_drafts,
            )
            pass_results.append(pass1)
            if pass1.draft is None:
                raise RuntimeError("Pass 1 did not produce a draft")
            current_draft = pass1.draft
            cumulative_cost_usd += pass1.cost_usd

            deterministic = self._execute_deterministic_checks(current_draft)
            pass_results.append(deterministic)
            current_draft = self._update_confidence(
                current_draft,
                deterministic.findings,
                confidence_adjustment=None,
            )

            all_findings: list[PassFinding] = list(deterministic.findings)
            if self._config.max_passes <= 1:
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            can_continue, stop_reason = self._can_run_next_pass(
                cumulative_cost_usd=cumulative_cost_usd,
                extra_llm_calls=extra_llm_calls,
            )
            if not can_continue:
                pass_results.append(self._skipped_pass("side_effects_check", 2, stop_reason))
                if self._config.max_passes >= 3:
                    pass_results.append(self._skipped_pass("constraint_verify", 3, stop_reason))
                if self._config.max_passes >= 4:
                    pass_results.append(self._skipped_pass("consolidation", 4, stop_reason))
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            pass2 = await self._execute_critique_pass(
                pass_name="side_effects_check",
                pass_number=2,
                pass_type="side_effects",
                problem_frame=problem_frame,
                draft=current_draft,
                previous_findings=(),
            )
            pass_results.append(pass2)
            if pass2.executed:
                extra_llm_calls += 1
                cumulative_cost_usd += pass2.cost_usd
                all_findings.extend(pass2.findings)
                current_draft = self._update_confidence(
                    current_draft,
                    pass2.findings,
                    confidence_adjustment=pass2.confidence_adjustment,
                )

            if self._should_early_exit(current_draft, all_findings):
                early_exit = True
                pass_results.append(self._skipped_pass("constraint_verify", 3, "early_exit"))
                pass_results.append(self._skipped_pass("consolidation", 4, "early_exit"))
                stop_reason = "early_exit"
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            if self._config.max_passes <= 2:
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            can_continue, stop_reason = self._can_run_next_pass(
                cumulative_cost_usd=cumulative_cost_usd,
                extra_llm_calls=extra_llm_calls,
            )
            if not can_continue:
                pass_results.append(self._skipped_pass("constraint_verify", 3, stop_reason))
                if self._config.max_passes >= 4:
                    pass_results.append(self._skipped_pass("consolidation", 4, stop_reason))
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            pass3 = await self._execute_critique_pass(
                pass_name="constraint_verify",
                pass_number=3,
                pass_type="constraint_verify",
                problem_frame=problem_frame,
                draft=current_draft,
                previous_findings=all_findings,
            )
            pass_results.append(pass3)
            if pass3.executed:
                extra_llm_calls += 1
                cumulative_cost_usd += pass3.cost_usd
                all_findings.extend(pass3.findings)
                current_draft = self._update_confidence(
                    current_draft,
                    pass3.findings,
                    confidence_adjustment=pass3.confidence_adjustment,
                )

            if self._config.max_passes <= 3:
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            if not all_findings:
                pass_results.append(
                    self._skipped_pass("consolidation", 4, "no_findings_to_consolidate")
                )
                stop_reason = "no_findings_to_consolidate"
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            can_continue, stop_reason = self._can_run_next_pass(
                cumulative_cost_usd=cumulative_cost_usd,
                extra_llm_calls=extra_llm_calls,
            )
            if not can_continue:
                pass_results.append(self._skipped_pass("consolidation", 4, stop_reason))
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            pass4 = await self._execute_consolidation_pass(
                problem_frame=problem_frame,
                draft=current_draft,
                all_findings=all_findings,
            )
            pass_results.append(pass4)
            if pass4.executed and pass4.draft is not None:
                extra_llm_calls += 1
                cumulative_cost_usd += pass4.cost_usd
                current_draft = pass4.draft

            return self._finalize(
                problem_frame=problem_frame,
                draft=current_draft,
                pass_results=pass_results,
                cumulative_cost_usd=cumulative_cost_usd,
                extra_llm_calls=extra_llm_calls,
                early_exit=early_exit,
                stop_reason=stop_reason,
                parent_span=parent_span,
                metrics=metrics,
            )

    async def _execute_pass1(
        self,
        problem_frame: ProblemFrame,
        *,
        hints: list[str] | None,
        prior_drafts: list[DraftResult] | None,
    ) -> PassExecution:
        tracer = get_tracer()
        started = time.perf_counter()
        with tracer.start_as_current_span(
            "drafter.pass.naive_draft",
            attributes={
                "polisyos.drafter.pass_name": "naive_draft",
                "polisyos.drafter.pass_number": 1,
            },
        ):
            draft = await self._inner.draft_policy(
                problem_frame,
                hints=hints,
                prior_drafts=prior_drafts,
            )
            raw = draft.raw_llm_response
            cost = self._estimate_cost_from_text(raw, model=self._inner_model_name())
            return PassExecution(
                pass_name="naive_draft",
                pass_number=1,
                executed=True,
                draft=draft,
                findings=[],
                raw_llm_response=raw,
                cost_usd=cost,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )

    def _execute_deterministic_checks(self, draft: DraftResult) -> PassExecution:
        tracer = get_tracer()
        started = time.perf_counter()
        with tracer.start_as_current_span(
            "drafter.pass.deterministic_checks",
            attributes={
                "polisyos.drafter.pass_name": "deterministic_checks",
                "polisyos.drafter.pass_number": 1,
            },
        ):
            findings: list[PassFinding] = []
            findings.extend(self._check_parameter_ranges(draft))
            findings.extend(self._check_target_overlaps(draft))
            return PassExecution(
                pass_name="deterministic_checks",
                pass_number=1,
                executed=True,
                draft=draft,
                findings=findings,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )

    def _check_parameter_ranges(self, draft: DraftResult) -> list[PassFinding]:
        findings: list[PassFinding] = []
        for idx, intervention in enumerate(draft.interventions):
            params = intervention.get("params")
            if params is None:
                params = intervention.get("parameters")
            if not isinstance(params, dict):
                continue
            for key, value in params.items():
                key_lower = str(key).lower()
                if "rate" not in key_lower:
                    continue
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    findings.append(
                        PassFinding(
                            finding_id=f"det_rate_type_{idx}_{key}",
                            category=FindingCategory.PARAMETER_ERROR,
                            severity=FindingSeverity.MEDIUM,
                            description=f"Parameter `{key}` is non-numeric (`{value}`).",
                            suggested_fix=f"Set `{key}` to numeric value in [0, 1].",
                            anchor=f"intervention:{idx}",
                            source_pass="deterministic_checks",
                        )
                    )
                    continue
                if numeric < 0.0 or numeric > 1.0:
                    findings.append(
                        PassFinding(
                            finding_id=f"det_rate_range_{idx}_{key}",
                            category=FindingCategory.PARAMETER_ERROR,
                            severity=FindingSeverity.HIGH,
                            description=(
                                f"Parameter `{key}`={numeric} is out of allowed range [0, 1]."
                            ),
                            suggested_fix=f"Clamp `{key}` to [0, 1] or explain scaling.",
                            anchor=f"intervention:{idx}",
                            source_pass="deterministic_checks",
                        )
                    )
        return findings

    def _check_target_overlaps(self, draft: DraftResult) -> list[PassFinding]:
        findings: list[PassFinding] = []
        seen: dict[str, int] = {}
        for idx, intervention in enumerate(draft.interventions):
            target_population = intervention.get("target_population")
            if isinstance(target_population, str) and target_population.strip():
                key = target_population.strip().lower()
            else:
                target = intervention.get("target")
                key = json.dumps(target, sort_keys=True) if target else ""
            if not key:
                continue
            first_idx = seen.get(key)
            if first_idx is None:
                seen[key] = idx
                continue
            findings.append(
                PassFinding(
                    finding_id=f"det_target_overlap_{first_idx}_{idx}",
                    category=FindingCategory.TARGET_OVERLAP,
                    severity=FindingSeverity.MEDIUM,
                    description=(
                        f"Interventions {first_idx} and {idx} appear to target the same population."
                    ),
                    suggested_fix="Clarify targeting or merge conflicting interventions.",
                    anchor=f"intervention:{idx}",
                    source_pass="deterministic_checks",
                )
            )
        return findings

    async def _execute_critique_pass(
        self,
        *,
        pass_name: str,
        pass_number: int,
        pass_type: str,
        problem_frame: ProblemFrame,
        draft: DraftResult,
        previous_findings: Iterable[PassFinding],
    ) -> PassExecution:
        if self._llm is None:
            return self._skipped_pass(pass_name, pass_number, "missing_llm_client")

        tracer = get_tracer()
        started = time.perf_counter()
        prompt = get_self_critique_prompt(
            pass_type=pass_type,
            problem_frame_summary=self._summarize_problem_frame(problem_frame),
            draft_so_far=self._serialize_draft(draft),
            constraints_list=self._format_constraints(problem_frame),
            previous_pass_findings=self._format_findings(previous_findings),
        )

        attempts = self._config.pass_retry_count + 1
        with tracer.start_as_current_span(
            f"drafter.pass.{pass_name}",
            attributes={
                "polisyos.drafter.pass_name": pass_name,
                "polisyos.drafter.pass_number": pass_number,
            },
        ) as span:
            last_error: Exception | None = None
            for _ in range(attempts):
                try:
                    response = await asyncio.wait_for(
                        self._llm.generate(
                            system=prompt,
                            user=(
                                "Review the draft and return strict JSON with findings. "
                                "Do not include markdown."
                            ),
                            response_format={"type": "json_object"},
                        ),
                        timeout=self._config.pass_timeout_s,
                    )
                    content, prompt_tokens, completion_tokens = self._extract_response_data(response)
                    findings, confidence_adjustment, parse_ok = self._parse_findings(
                        content,
                        pass_name=pass_name,
                    )
                    cost = self._estimate_cost(
                        model=self._critique_model_name(),
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        raw_response=content,
                    )
                    span.set_attribute("polisyos.drafter.findings_count", len(findings))
                    return PassExecution(
                        pass_name=pass_name,
                        pass_number=pass_number,
                        executed=True,
                        findings=findings,
                        raw_llm_response=content,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        cost_usd=cost,
                        duration_ms=int((time.perf_counter() - started) * 1000),
                        parse_ok=parse_ok,
                        confidence_adjustment=confidence_adjustment,
                    )
                except Exception as exc:
                    last_error = exc
                    logger.warning("%s failed; retrying: %s", pass_name, exc)

            span.set_attribute("polisyos.drafter.pass_error", True)
            logger.warning("%s failed after retries: %s", pass_name, last_error)
            return self._skipped_pass(pass_name, pass_number, "pass_error")

    async def _execute_consolidation_pass(
        self,
        *,
        problem_frame: ProblemFrame,
        draft: DraftResult,
        all_findings: Iterable[PassFinding],
    ) -> PassExecution:
        if self._llm is None:
            return self._skipped_pass("consolidation", 4, "missing_llm_client")

        tracer = get_tracer()
        started = time.perf_counter()
        prompt = get_self_critique_prompt(
            pass_type="consolidation",
            problem_frame_summary=self._summarize_problem_frame(problem_frame),
            draft_so_far=self._serialize_draft(draft),
            constraints_list=self._format_constraints(problem_frame),
            previous_pass_findings=self._format_findings(all_findings),
        )
        attempts = self._config.pass_retry_count + 1
        with tracer.start_as_current_span(
            "drafter.pass.consolidation",
            attributes={
                "polisyos.drafter.pass_name": "consolidation",
                "polisyos.drafter.pass_number": 4,
            },
        ) as span:
            last_error: Exception | None = None
            for _ in range(attempts):
                try:
                    response = await asyncio.wait_for(
                        self._llm.generate(
                            system=prompt,
                            user=(
                                "Integrate findings and return strict JSON of the full revised draft. "
                                "Do not include markdown."
                            ),
                            response_format={"type": "json_object"},
                        ),
                        timeout=self._config.pass_timeout_s,
                    )
                    content, prompt_tokens, completion_tokens = self._extract_response_data(response)
                    updated_draft, parse_ok = self._parse_consolidated_draft(
                        raw_response=content,
                        original=draft,
                    )
                    cost = self._estimate_cost(
                        model=self._critique_model_name(),
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        raw_response=content,
                    )
                    span.set_attribute("polisyos.drafter.consolidation_parse_ok", parse_ok)
                    execution = PassExecution(
                        pass_name="consolidation",
                        pass_number=4,
                        executed=True,
                        draft=updated_draft,
                        findings=[],
                        raw_llm_response=content,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        cost_usd=cost,
                        duration_ms=int((time.perf_counter() - started) * 1000),
                        parse_ok=parse_ok,
                    )
                    return execution
                except Exception as exc:
                    last_error = exc
                    logger.warning("consolidation failed; retrying: %s", exc)

            span.set_attribute("polisyos.drafter.pass_error", True)
            logger.warning("consolidation failed after retries: %s", last_error)
            return self._skipped_pass("consolidation", 4, "pass_error")

    def _resolve_llm(self, llm_client: Any | None, inner: DrafterAgent) -> Any | None:
        if llm_client is not None:
            return self._normalize_critique_llm(llm_client)
        inner_llm = getattr(inner, "_llm", None)
        if inner_llm is None:
            return None
        return self._normalize_critique_llm(inner_llm)

    def _normalize_critique_llm(self, llm: Any) -> Any:
        if self._config.critique_model is None:
            return llm
        model_name = self._config.critique_model
        if isinstance(llm, TracedLLMClient):
            raw_client = getattr(llm, "_client", llm)
            return TracedLLMClient(raw_client, model_name=model_name)
        return TracedLLMClient(llm, model_name=model_name)

    def _should_early_exit(self, draft: DraftResult, findings: list[PassFinding]) -> bool:
        if self._config.max_passes < 3:
            return False
        if draft.confidence < self._config.early_exit_confidence:
            return False
        threshold = _SEVERITY_ORDER[self._config.finding_severity_threshold]
        return not any(_SEVERITY_ORDER[f.severity] >= threshold for f in findings)

    def _can_run_next_pass(
        self,
        *,
        cumulative_cost_usd: float,
        extra_llm_calls: int,
    ) -> tuple[bool, str]:
        if cumulative_cost_usd >= self._config.budget_limit_usd:
            return False, "budget_usd_exceeded"
        if extra_llm_calls >= self._config.max_extra_llm_calls:
            return False, "max_extra_calls_exceeded"
        return True, ""

    def _estimate_cost(
        self,
        *,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        raw_response: str,
    ) -> float:
        if prompt_tokens > 0 or completion_tokens > 0:
            return estimate_llm_cost_usd(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        return self._estimate_cost_from_text(raw_response, model=model)

    def _estimate_cost_from_text(self, raw_response: str | None, *, model: str) -> float:
        if not raw_response:
            return 0.0
        approx_completion = max(1, len(raw_response) // 4)
        approx_prompt = approx_completion * 2
        return estimate_llm_cost_usd(
            model=model,
            prompt_tokens=approx_prompt,
            completion_tokens=approx_completion,
        )

    def _extract_response_data(self, response: Any) -> tuple[str, int, int]:
        content = response.content if hasattr(response, "content") else str(response)
        prompt_tokens = 0
        completion_tokens = 0
        usage = getattr(response, "usage", None)
        if usage is not None:
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        return content, prompt_tokens, completion_tokens

    def _parse_findings(
        self,
        raw_response: str,
        *,
        pass_name: str,
    ) -> tuple[list[PassFinding], float | None, bool]:
        try:
            payload = _CritiquePayload.model_validate_json(raw_response)
        except ValidationError:
            try:
                decoded = json.loads(raw_response)
            except json.JSONDecodeError:
                return [], None, False
            try:
                payload = _CritiquePayload.model_validate(decoded)
            except ValidationError:
                return [], None, False

        findings: list[PassFinding] = []
        for idx, item in enumerate(payload.findings):
            category = self._parse_category(item.category)
            severity = self._parse_severity(item.severity)
            findings.append(
                PassFinding(
                    finding_id=f"{pass_name}_{idx}",
                    category=category,
                    severity=severity,
                    description=item.description.strip(),
                    suggested_fix=item.suggested_fix.strip(),
                    affected_intervention=item.affected_intervention,
                    anchor=item.anchor,
                    source_pass=pass_name,
                )
            )
        return findings, payload.confidence_adjustment, True

    def _parse_consolidated_draft(
        self,
        *,
        raw_response: str,
        original: DraftResult,
    ) -> tuple[DraftResult, bool]:
        try:
            payload = _ConsolidationPayload.model_validate_json(raw_response)
        except ValidationError:
            try:
                payload = _ConsolidationPayload.model_validate(json.loads(raw_response))
            except (ValidationError, json.JSONDecodeError):
                return original, False

        return (
            DraftResult(
                draft_id=f"{original.draft_id}_mp",
                problem_frame_ref=original.problem_frame_ref,
                narrative=payload.narrative or original.narrative,
                interventions=payload.interventions or original.interventions,
                rationale=payload.rationale or original.rationale,
                domain_references=original.domain_references,
                confidence=payload.confidence if payload.confidence is not None else original.confidence,
                alternatives_considered=(
                    payload.alternatives_considered or original.alternatives_considered
                ),
                raw_llm_response=raw_response,
                created_at=datetime.utcnow(),
            ),
            True,
        )

    def _parse_category(self, raw: str) -> FindingCategory:
        normalized = raw.strip().lower()
        try:
            return FindingCategory(normalized)
        except ValueError:
            return FindingCategory.OTHER

    def _parse_severity(self, raw: str) -> FindingSeverity:
        normalized = raw.strip().lower()
        try:
            return FindingSeverity(normalized)
        except ValueError:
            return FindingSeverity.MEDIUM

    def _update_confidence(
        self,
        draft: DraftResult,
        findings: list[PassFinding],
        confidence_adjustment: float | None,
    ) -> DraftResult:
        if confidence_adjustment is not None:
            adjustment = confidence_adjustment
        elif findings:
            adjustment = -sum(
                {
                    FindingSeverity.LOW: 0.02,
                    FindingSeverity.MEDIUM: 0.05,
                    FindingSeverity.HIGH: 0.10,
                    FindingSeverity.CRITICAL: 0.15,
                }[finding.severity]
                for finding in findings
            )
        else:
            adjustment = 0.0

        updated_confidence = min(0.99, max(0.05, draft.confidence + adjustment))
        if updated_confidence == draft.confidence:
            return draft
        return DraftResult(
            draft_id=draft.draft_id,
            problem_frame_ref=draft.problem_frame_ref,
            narrative=draft.narrative,
            interventions=draft.interventions,
            rationale=draft.rationale,
            domain_references=draft.domain_references,
            confidence=updated_confidence,
            alternatives_considered=draft.alternatives_considered,
            raw_llm_response=draft.raw_llm_response,
            created_at=draft.created_at,
        )

    def _summarize_problem_frame(self, problem_frame: ProblemFrame) -> str:
        return (
            f"Domain: {problem_frame.domain}\n"
            f"Problem: {problem_frame.problem_statement}\n"
            f"Goals: {', '.join(problem_frame.goals)}\n"
            f"Actors: {', '.join(problem_frame.actors)}\n"
            f"Success criteria: {json.dumps(problem_frame.success_criteria)}"
        )

    def _serialize_draft(self, draft: DraftResult) -> str:
        payload = {
            "narrative": draft.narrative,
            "interventions": draft.interventions,
            "rationale": draft.rationale,
            "confidence": draft.confidence,
            "alternatives_considered": draft.alternatives_considered,
        }
        return json.dumps(payload, ensure_ascii=True, indent=2)

    def _format_constraints(self, problem_frame: ProblemFrame) -> str:
        if not problem_frame.constraints:
            return "No explicit constraints provided."
        return "\n".join(f"{idx + 1}. {constraint}" for idx, constraint in enumerate(problem_frame.constraints))

    def _format_findings(self, findings: Iterable[PassFinding]) -> str:
        collected = list(findings)
        if not collected:
            return "No issues found in previous passes."
        lines: list[str] = []
        for finding in collected:
            line = (
                f"[{finding.severity.value.upper()}] {finding.category.value}: "
                f"{finding.description}"
            )
            if finding.suggested_fix:
                line += f" -> Fix: {finding.suggested_fix}"
            if finding.anchor and finding.anchor != "none":
                line += f" (anchor: {finding.anchor})"
            lines.append(line)
        return "\n".join(lines)

    def _skipped_pass(self, pass_name: str, pass_number: int, reason: str) -> PassExecution:
        return PassExecution(
            pass_name=pass_name,
            pass_number=pass_number,
            executed=False,
            skip_reason=reason,
            findings=[],
        )

    def _inner_model_name(self) -> str:
        if hasattr(self._inner, "_llm"):
            inner_llm = getattr(self._inner, "_llm")
            return str(getattr(inner_llm, "_model_name", "default"))
        return "default"

    def _critique_model_name(self) -> str:
        if self._config.critique_model:
            return self._config.critique_model
        if self._llm is None:
            return "default"
        return str(getattr(self._llm, "_model_name", "default"))

    def _finalize(
        self,
        *,
        problem_frame: ProblemFrame,
        draft: DraftResult,
        pass_results: list[PassExecution],
        cumulative_cost_usd: float,
        extra_llm_calls: int,
        early_exit: bool,
        stop_reason: str,
        parent_span: Any,
        metrics: Any,
    ) -> DraftResult:
        if self._config.shadow_mode and pass_results:
            pass1 = pass_results[0]
            if pass1.executed and pass1.draft is not None:
                draft = pass1.draft

        findings_total = sum(len(p.findings) for p in pass_results)
        executed_passes = sum(1 for p in pass_results if p.executed)
        budget_stop = stop_reason in {"budget_usd_exceeded", "max_extra_calls_exceeded"}

        parent_span.set_attribute("polisyos.drafter.total_passes", len(pass_results))
        parent_span.set_attribute("polisyos.drafter.executed_passes", executed_passes)
        parent_span.set_attribute("polisyos.drafter.total_findings", findings_total)
        parent_span.set_attribute("polisyos.drafter.total_cost_usd", cumulative_cost_usd)
        parent_span.set_attribute("polisyos.drafter.extra_llm_calls", extra_llm_calls)
        parent_span.set_attribute("polisyos.drafter.early_exit", early_exit)
        if stop_reason:
            parent_span.set_attribute("polisyos.drafter.stop_reason", stop_reason)

        metrics.record_drafter_multipass_run(
            domain=problem_frame.domain,
            executed_passes=executed_passes,
            total_findings=findings_total,
            total_cost_usd=cumulative_cost_usd,
            early_exit=early_exit,
            budget_stop=budget_stop,
            shadow_mode=self._config.shadow_mode,
        )
        for pass_result in pass_results:
            metrics.record_drafter_multipass_pass(
                pass_name=pass_result.pass_name,
                duration_seconds=max(0.0, pass_result.duration_ms / 1000.0),
                executed=pass_result.executed,
            )

        if self._config.enable_memory_logging and self._memory is not None:
            for pass_result in pass_results:
                if pass_result.findings:
                    self._memory.add_pass_findings(
                        pass_result.pass_name,
                        [finding.as_memory_dict() for finding in pass_result.findings],
                        cost_usd=pass_result.cost_usd,
                    )

        return draft


def create_drafter_agent(
    llm_client: Any,
    *,
    model_name: str | None = None,
    memory: ShortTermMemory | None = None,
    config: MultiPassConfig | None = None,
) -> DrafterAgent:
    """
    Build drafter according to feature flag `POLISYOS_DRAFTER_MULTIPASS_MODE`.

    Modes:
    - off (default): LLMDrafterAgent
    - active: MultiPassLLMDrafter
    - shadow: MultiPassLLMDrafter with shadow_mode=True
    """
    mode = os.getenv("POLISYOS_DRAFTER_MULTIPASS_MODE", "off").strip().lower()
    inner = LLMDrafterAgent(llm_client, model_name=model_name)
    if mode not in {"active", "shadow"}:
        return inner

    effective_config = config or MultiPassConfig.from_env()
    if mode == "shadow" and not effective_config.shadow_mode:
        effective_config = effective_config.model_copy(update={"shadow_mode": True})
    return MultiPassLLMDrafter(inner, config=effective_config, memory=memory)


def drafter_node(state: Any) -> Any:
    """
    Backward-compatible no-op node.

    Legacy LangGraph node flow was removed; canonical Scientist path uses engine DAG.
    """
    return state


def _verify_protocol() -> None:
    agent = MockDrafterAgent()
    if not isinstance(agent, DrafterAgent):
        raise TypeError("MockDrafterAgent does not implement DrafterAgent protocol")


_verify_protocol()
