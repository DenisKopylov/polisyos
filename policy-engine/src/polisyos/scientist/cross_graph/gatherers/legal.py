"""Legal assessment gatherer."""

from __future__ import annotations

from typing import Any

from polisyos.ir.analytics.cross_graph import (
    CanonicalConcept,
    EvidenceNeed,
    LegalStatus,
)

from ..protocols import GathererResult


class LegalGatherer:
    """Assesses legal status for evidence needs."""

    @property
    def dimension(self) -> str:
        return "legal"

    def assess(
        self,
        need: EvidenceNeed,
        *,
        concepts: list[CanonicalConcept],
        context: dict[str, Any],
    ) -> GathererResult:
        legal_adapter = context.get("legal_adapter")
        compiler_fn = context.get("_legal_assess_need")

        if compiler_fn is not None:
            result = compiler_fn(need)
            return GathererResult(
                status=result.status.value
                if hasattr(result.status, "value")
                else str(result.status),
                confidence=result.confidence if hasattr(result, "confidence") else 0.5,
                diagnostics=list(result.diagnostics) if hasattr(result, "diagnostics") else [],
                provenance_refs=list(result.provenance_refs)
                if hasattr(result, "provenance_refs")
                else [],
                metadata={
                    "requires_expert_review": result.requires_expert_review
                    if hasattr(result, "requires_expert_review")
                    else False,
                    "blocking_reasons": list(result.blocking_reasons)
                    if hasattr(result, "blocking_reasons")
                    else [],
                },
            )

        if legal_adapter is None:
            return GathererResult(
                status=LegalStatus.UNKNOWN.value,
                confidence=0.3,
                diagnostics=[],
                provenance_refs=[],
                metadata={"reason": "no_legal_adapter"},
            )

        return GathererResult(
            status=LegalStatus.UNKNOWN.value,
            confidence=0.3,
            diagnostics=[],
            provenance_refs=[],
            metadata={"reason": "standalone_fallback"},
        )
