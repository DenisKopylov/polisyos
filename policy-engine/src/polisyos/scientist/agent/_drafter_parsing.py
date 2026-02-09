"""Response parsing helpers for the multipass drafter.

These are mixed into ``MultiPassLLMDrafter`` via the
``_DrafterParsingMixin`` helper base class.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from polisyos.scientist.agent.protocols import DraftResult

from .drafter_models import (
    FindingCategory,
    FindingSeverity,
    PassFinding,
    _ConsolidationPayload,
    _CritiquePayload,
)

__all__ = ["_DrafterParsingMixin"]


class _DrafterParsingMixin:
    """Critique and consolidation response parsing."""

    # ------------------------------------------------------------------
    # Critique payload parsing
    # ------------------------------------------------------------------

    def _parse_findings(
        self,
        raw_response: str,
        *,
        pass_name: str,
    ) -> tuple[list[PassFinding], float | None, bool]:
        findings, confidence_adjustment, parse_ok, _verification_code = self._parse_critique_payload(
            raw_response,
            pass_name=pass_name,
        )
        return findings, confidence_adjustment, parse_ok

    def _parse_critique_payload(
        self,
        raw_response: str,
        *,
        pass_name: str,
    ) -> tuple[list[PassFinding], float | None, bool, str | None]:
        try:
            payload = _CritiquePayload.model_validate_json(raw_response)
        except ValidationError:
            try:
                decoded = json.loads(raw_response)
            except json.JSONDecodeError:
                return [], None, False, None
            try:
                payload = _CritiquePayload.model_validate(decoded)
            except ValidationError:
                return [], None, False, None

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
        verification_code = payload.verification_code.strip() if payload.verification_code else None
        if verification_code == "":
            verification_code = None
        return findings, payload.confidence_adjustment, True, verification_code

    # ------------------------------------------------------------------
    # Consolidation payload parsing
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Enum parsing helpers
    # ------------------------------------------------------------------

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
