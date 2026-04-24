"""Transport assessment gatherer."""

from __future__ import annotations

from typing import Any

from polisyos.ir.analytics.cross_graph import (
    CanonicalConcept,
    EvidenceNeed,
    TransportStatus,
)

from ..protocols import GathererResult


class TransportGatherer:
    """Assesses transportability of evidence to target context."""

    @property
    def dimension(self) -> str:
        return "transport"

    def assess(
        self,
        need: EvidenceNeed,
        *,
        concepts: list[CanonicalConcept],
        context: dict[str, Any],
    ) -> GathererResult:
        compiler_fn = context.get("_compose_transportability_view")

        if compiler_fn is not None:
            observability_status = context.get("observability_status")
            evidence_result = context.get("evidence_result")
            target_context = context.get("target_context")

            result = compiler_fn(
                need,
                target_context=target_context,
                observability_status=observability_status,
                evidence_result=evidence_result,
            )
            return GathererResult(
                status=result.transport_status.value
                if hasattr(result.transport_status, "value")
                else str(result.transport_status),
                confidence=result.confidence if hasattr(result, "confidence") else 0.5,
                diagnostics=list(result.diagnostics) if hasattr(result, "diagnostics") else [],
                provenance_refs=[],
                metadata={
                    "transport_mode": result.transport_mode.value
                    if hasattr(result, "transport_mode") and hasattr(result.transport_mode, "value")
                    else "",
                    "recommendations": list(result.recommendations)
                    if hasattr(result, "recommendations")
                    else [],
                },
            )

        return GathererResult(
            status=TransportStatus.UNSUPPORTED.value,
            confidence=0.3,
            diagnostics=[],
            provenance_refs=[],
            metadata={"reason": "no_transport_fn"},
        )
