"""
Drafter Agent Module
====================

LLM-based policy draft generation with protocol conformance.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from polisyos.ir.surface import PolicySurfaceIR
from polisyos.scientist.agent.prompts import get_system_prompt
from polisyos.scientist.agent.protocols import (
    CritiqueReport,
    DrafterAgent,
    DraftResult,
    ProblemFrame,
)
from polisyos.scientist.orchestrator.audit import append_audit
from polisyos.scientist.orchestrator.state import ExperimentState


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


def drafter_node(state: ExperimentState) -> ExperimentState:
    """Узел Drafter: User Request -> Policy IR JSON."""
    user_request = state.get("user_request")
    if not user_request:
        if state.get("ir") is not None:
            print("   [Drafter] Skipping: IR already provided.")
            return append_audit(
                state, "drafter", "skip_existing_ir", {"reason": "missing_user_request"}
            )
        state = {**state, "last_error": "Missing required field: user_request", "ir": None}
        return append_audit(state, "drafter", "invalid_input", {"reason": "missing_user_request"})

    if state.get("ir") is not None and not (
        state.get("feedback") and state["feedback"].get("verdict") == "NEEDS_REVISION"
    ):
        print(f"   [Drafter] Skipping: IR already provided for request: '{user_request}'")
        return append_audit(state, "drafter", "skip_existing_ir", {"reason": "ir_present"})

    print(f"   [Drafter] Processing request: '{user_request}'")
    prior_feedback = state.get("feedback")
    prior_issues = []
    if prior_feedback and prior_feedback.get("verdict") == "NEEDS_REVISION":
        prior_issues = prior_feedback.get("issues", [])
        state = {**state, "revision_count": (state.get("revision_count") or 0) + 1}

    system_prompt = get_system_prompt()
    user_prompt = f"USER REQUEST: {user_request}"
    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    llm = MockLLM()
    response_text = llm.invoke(full_prompt)

    try:
        clean_json = response_text.strip().replace("```json", "").replace("```", "")
        data = json.loads(clean_json)

        ir = PolicySurfaceIR(**data)
        print("   [Drafter] ✅ Generated valid IR.")
        after_json = json.dumps(data, sort_keys=True)
        new_state = {**state, "ir": ir, "last_ir_json": after_json, "last_error": None}
        if prior_issues:
            repair_log = list(state.get("repair_log") or [])
            error_summary = "; ".join([i.get("message", "") for i in prior_issues])
            repair_log.append(
                {
                    "repair_attempt": state.get("revision_count") or 1,
                    "error_summary": error_summary,
                    "diff_before_after": {"before": state.get("last_ir_json"), "after": after_json},
                }
            )
            new_state["repair_log"] = repair_log
        return append_audit(new_state, "drafter", "ir_generated", {"valid": True})

    except Exception as e:
        attempt = state.get("revision_count") or 0
        if attempt == 0:
            attempt = 1
        before = state.get("last_ir_json")
        error_summary = str(e)
        diff = {"before": before, "after": clean_json}
        repair_log = list(state.get("repair_log") or [])
        repair_log.append(
            {
                "repair_attempt": attempt,
                "error_summary": error_summary,
                "diff_before_after": diff,
            }
        )
        new_state = {
            **state,
            "ir": None,
            "last_error": error_summary,
            "revision_count": attempt,
            "repair_log": repair_log,
        }
        new_state = append_audit(
            new_state,
            "drafter",
            "ir_invalid",
            {"attempt": attempt, "error_summary": error_summary},
        )
        print(f"   [Drafter] ❌ Failed to generate valid IR: {e}")
        return new_state


def _verify_protocol() -> None:
    agent = MockDrafterAgent()
    if not isinstance(agent, DrafterAgent):
        raise TypeError("MockDrafterAgent does not implement DrafterAgent protocol")


_verify_protocol()
