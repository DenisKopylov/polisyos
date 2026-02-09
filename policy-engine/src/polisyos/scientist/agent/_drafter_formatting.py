"""Formatting, serialization, and constitution building for the multipass drafter.

These are mixed into ``MultiPassLLMDrafter`` via the
``_DrafterFormattingMixin`` helper base class.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import TYPE_CHECKING, Iterable

from polisyos.scientist.agent.protocols import DraftResult, ProblemFrame

from .drafter_models import (
    PassFinding,
)

if TYPE_CHECKING:
    from polisyos.scientist.agent.constitution import ConstitutionGenerator, PolicyConstitution
    from polisyos.scientist.agent.knowledge_base import CriticKnowledgeBase

    from .drafter_models import MultiPassConfig

logger = logging.getLogger(__name__)

__all__ = ["_DrafterFormattingMixin"]


class _DrafterFormattingMixin:
    """Problem-frame summarization, draft serialization, and constitution building."""

    # -- Provided by the orchestrator at runtime --
    _config: MultiPassConfig
    _constitution_gen: ConstitutionGenerator
    _knowledge_base: CriticKnowledgeBase | None
    _constitution_norm_pack: object | None
    _constitution_model_spec: object | None

    # ------------------------------------------------------------------
    # Problem frame / draft formatting
    # ------------------------------------------------------------------

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
        return "\n".join(
            f"{idx + 1}. {constraint}"
            for idx, constraint in enumerate(problem_frame.constraints)
        )

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

    # ------------------------------------------------------------------
    # Constitution building
    # ------------------------------------------------------------------

    def _build_constitution(self, problem_frame: ProblemFrame) -> PolicyConstitution | None:
        if not self._config.constitution_enabled:
            return None
        try:
            known_pitfalls = None
            if (
                self._config.constitution_enable_pitfalls
                and self._knowledge_base is not None
            ):
                known_pitfalls = self._knowledge_base.get_top_patterns(3)
            return self._constitution_gen.generate(
                problem_frame=problem_frame,
                norm_pack=self._constitution_norm_pack,
                model_spec=self._constitution_model_spec,
                known_pitfalls=known_pitfalls,
            )
        except Exception as exc:
            logger.warning("Constitution generation failed, continuing without it: %s", exc)
            return None

    def _inject_constitution_context(
        self,
        problem_frame: ProblemFrame,
        *,
        constitution: PolicyConstitution,
    ) -> ProblemFrame:
        context = getattr(problem_frame, "context", None)
        if not isinstance(context, dict):
            return problem_frame
        updated_context = dict(context)
        updated_context["policy_constitution"] = constitution.to_system_prompt()
        updated_context["policy_constitution_hash"] = constitution.compute_hash()
        try:
            return replace(problem_frame, context=updated_context)
        except Exception:
            return problem_frame
