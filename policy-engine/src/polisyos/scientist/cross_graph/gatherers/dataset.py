"""Dataset observability gatherer."""

from __future__ import annotations

from typing import Any

from polisyos.ir.analytics.cross_graph import (
    CanonicalConcept,
    EvidenceNeed,
    ObservabilityStatus,
)

from ..protocols import GathererResult


class DatasetGatherer:
    """Assesses dataset availability and observability for evidence needs."""

    @property
    def dimension(self) -> str:
        return "dataset"

    def assess(
        self,
        need: EvidenceNeed,
        *,
        concepts: list[CanonicalConcept],
        context: dict[str, Any],
    ) -> GathererResult:
        registry = context.get("dataset_registry")
        compiler_fn = context.get("_assess_dataset_need")

        if compiler_fn is not None:
            result = compiler_fn(
                need,
                concepts=concepts,
                registry=registry,
                academic_query=context.get("academic_query"),
                country_code=context.get("country_code"),
                target_year=context.get("target_year"),
            )
            return GathererResult(
                status=result.status.value
                if hasattr(result.status, "value")
                else str(result.status),
                confidence=result.confidence if hasattr(result, "confidence") else 0.5,
                diagnostics=list(result.diagnostics) if hasattr(result, "diagnostics") else [],
                provenance_refs=list(result.provenance_refs)
                if hasattr(result, "provenance_refs")
                else [],
                metadata=result.metadata if hasattr(result, "metadata") else {},
            )

        if registry is None:
            return GathererResult(
                status=ObservabilityStatus.UNKNOWN.value,
                confidence=0.3,
                diagnostics=[],
                provenance_refs=[],
                metadata={"reason": "no_dataset_registry"},
            )

        return GathererResult(
            status=ObservabilityStatus.UNKNOWN.value,
            confidence=0.3,
            diagnostics=[],
            provenance_refs=[],
            metadata={"reason": "standalone_fallback"},
        )
