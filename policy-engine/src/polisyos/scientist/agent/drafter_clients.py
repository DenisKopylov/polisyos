"""Single-pass drafter implementations and mocks."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from polisyos.common.llm_json import extract_llm_json_object
from polisyos.core.canon import truncated_hash
from polisyos.scientist.agent.prompts import get_drafter_prompt
from polisyos.scientist.agent.protocols import CritiqueReport, DraftResult, ProblemFrame
from polisyos.scientist.orchestration.llm import TracedLLMClient


class MockLLM:
    """Mock LLM public type."""

    def invoke(self, prompt: str) -> str:
        """Эмулирует ответ GPT-4, возвращая валидный JSON."""
        print(f"   [MockLLM] 'Thinking' about: {prompt[:50]}...")

        return """
        {
          "schema_version": "2.0",
          "semantic": {
            "context_snapshot_ref": (
                "sha256:0000000000000000000000000000000000000000000000000000000000000000"
            ),
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
        data_context: dict[str, Any] | None = None,
        hints: list[str] | None = None,
        prior_drafts: list[DraftResult] | None = None,
    ) -> DraftResult:
        if not problem_frame.frame_id:
            raise ValueError("ProblemFrame must have a valid frame_id")

        self._draft_count += 1

        base_hash = truncated_hash(problem_frame.frame_id, length=8)
        draft_id = f"draft_{base_hash}_{self._draft_count}"

        interventions = self._generate_interventions(problem_frame)
        narrative = self._build_narrative(problem_frame, hints, data_context=data_context)
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
            citations=_context_citations(problem_frame),
            claim_supports=_context_claim_supports(problem_frame),
            grounding_notes=_context_grounding_notes(problem_frame),
            confidence=min(0.95, confidence),
            alternatives_considered=self._get_alternatives(problem_frame),
            raw_llm_response=None,
            created_at=datetime.now(UTC),
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

    def _build_narrative(
        self,
        problem_frame: ProblemFrame,
        hints: list[str] | None,
        *,
        data_context: dict[str, Any] | None,
    ) -> str:
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

        if data_context:
            parts.extend(
                [
                    "",
                    "Data context highlights:",
                    *[f"- {key}: {value}" for key, value in list(data_context.items())[:4]],
                ]
            )

        return "\n".join(parts)

    def _build_rationale(
        self,
        problem_frame: ProblemFrame,
        prior_drafts: list[DraftResult] | None,
    ) -> str:
        rationale_parts = [
            (
                "This approach was chosen to directly address the core problem: "
                f"{problem_frame.problem_statement[:100]}"
            ),
        ]

        if prior_drafts:
            rationale_parts.append(
                f"Building on {len(prior_drafts)} prior draft(s), this iteration "
                "incorporates lessons learned."
            )

        rationale_parts.append(
            "The interventions are designed to work within the stated constraints "
            "while maximizing impact."
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
                (
                    "Heckman, J. (2006). Skill Formation and the Economics of "
                    "Investing in Disadvantaged Children"
                ),
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
            created_at=datetime.now(UTC),
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
        data_context: dict[str, Any] | None = None,
        hints: list[str] | None = None,
        prior_drafts: list[DraftResult] | None = None,
    ) -> DraftResult:
        if not problem_frame.frame_id:
            raise ValueError("ProblemFrame must have a valid frame_id")

        prompt = get_drafter_prompt(hints=hints)
        constitution_text = self._extract_constitution(problem_frame)
        if constitution_text:
            prompt = f"{constitution_text}\n\n{prompt}"
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

DATA CONTEXT:
{json.dumps(data_context or {}, indent=2)}

WEB EVIDENCE:
{_web_evidence_prompt_block(problem_frame)}

Generate a draft JSON object.
"""

        response = await self._llm.generate(
            system=prompt,
            user=user_message,
            response_format={"type": "json_object"},
        )

        content = response.content if hasattr(response, "content") else str(response)
        try:
            data = extract_llm_json_object(content)
        except json.JSONDecodeError:
            fallback = MockDrafterAgent()
            return await fallback.draft_policy(
                problem_frame,
                data_context=data_context,
                hints=hints,
                prior_drafts=prior_drafts,
            )
        return DraftResult(
            draft_id=data.get("draft_id", f"draft_{uuid.uuid4().hex[:8]}"),
            problem_frame_ref=data.get("problem_frame_ref", problem_frame.frame_id),
            narrative=data.get("narrative", ""),
            interventions=data.get("interventions", []),
            rationale=data.get("rationale", ""),
            domain_references=(
                list(data.get("domain_references", []))
                if isinstance(data.get("domain_references"), list)
                else []
            ),
            citations=_context_citations(problem_frame),
            claim_supports=_context_claim_supports(problem_frame),
            grounding_notes=_context_grounding_notes(problem_frame),
            alternatives_considered=data.get("alternatives_considered", []),
            confidence=float(data.get("confidence", 0.6)),
            raw_llm_response=content,
            created_at=datetime.now(UTC),
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
            citations=list(draft.citations),
            claim_supports=list(draft.claim_supports),
            grounding_notes=list(draft.grounding_notes),
            confidence=min(0.95, draft.confidence + 0.05),
            alternatives_considered=draft.alternatives_considered,
            raw_llm_response=draft.raw_llm_response,
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _extract_constitution(problem_frame: ProblemFrame) -> str:
        context = getattr(problem_frame, "context", None)
        if not isinstance(context, dict):
            return ""
        value = context.get("policy_constitution")
        if not isinstance(value, str):
            return ""
        return value.strip()


def _web_evidence_prompt_block(problem_frame: ProblemFrame) -> str:
    context = getattr(problem_frame, "context", None)
    if not isinstance(context, dict):
        return "{}"
    if (
        isinstance(context.get("web_evidence_context"), str)
        and context["web_evidence_context"].strip()
    ):
        return context["web_evidence_context"]
    payload = context.get("web_evidence")
    if isinstance(payload, dict) and payload:
        return json.dumps(payload, indent=2, default=str)
    return "{}"


def _context_citations(problem_frame: ProblemFrame) -> list[dict[str, Any]]:
    context = getattr(problem_frame, "context", None)
    if not isinstance(context, dict):
        return []
    payload = context.get("web_evidence")
    if not isinstance(payload, dict):
        return []
    snippets = payload.get("snippets")
    if not isinstance(snippets, list):
        return []
    citations: list[dict[str, Any]] = []
    for item in snippets[:12]:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        text = str(item.get("text") or "")
        if not url or not text:
            continue
        citations.append(
            {
                "url": url,
                "source_id": str(item.get("source_id") or ""),
                "snippet": text,
                "start_char": item.get("start_char"),
                "end_char": item.get("end_char"),
            }
        )
    return citations


def _context_claim_supports(problem_frame: ProblemFrame) -> list[dict[str, Any]]:
    context = getattr(problem_frame, "context", None)
    if not isinstance(context, dict):
        return []
    supports: list[dict[str, Any]] = []
    payload = context.get("web_evidence")
    if isinstance(payload, dict):
        raw_supports = payload.get("claim_supports")
        if isinstance(raw_supports, list):
            supports.extend(dict(item) for item in raw_supports if isinstance(item, dict))
    for source in (context, payload if isinstance(payload, dict) else None):
        if not isinstance(source, dict):
            continue
        for key in (
            "policy_recommendations",
            "recommendation_claims",
            "recommendations",
            "policy_claims",
        ):
            raw_items = source.get(key)
            if isinstance(raw_items, list):
                supports.extend(dict(item) for item in raw_items if isinstance(item, dict))

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(supports):
        fingerprint = str(
            item.get("claim_id")
            or item.get("id")
            or item.get("text")
            or item.get("claim")
            or index
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(item)
    return deduped[:12]


def _context_grounding_notes(problem_frame: ProblemFrame) -> list[str]:
    context = getattr(problem_frame, "context", None)
    if not isinstance(context, dict):
        return []
    payload = context.get("web_evidence")
    if not isinstance(payload, dict):
        return []
    notes = payload.get("uncertainty_notes")
    if not isinstance(notes, list):
        return []
    return [str(item) for item in notes[:12] if str(item).strip()]


__all__ = ["LLMDrafterAgent", "MockDrafterAgent", "MockLLM"]
