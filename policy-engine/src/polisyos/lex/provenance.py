"""Lex evidence adapters backed by Fabric provenance."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.fabric.product_integration import (
    FabricProductEvidencePath,
    evidence_path_from_fabric_decision_data,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


class LexFabricEvidencePath(BaseModel):
    """Legal citation/evidence path projected from a Fabric trust envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    legal_evidence_id: str
    citation_label: str
    lineage_path: str
    source_contract_id: str
    quality_status: str
    access_classification: str
    replay_status: str
    raw_source_refs: tuple[str, ...] = ()
    export_links: dict[str, str] = Field(default_factory=dict)


def lex_evidence_from_fabric_decision_data(
    decision_data: Mapping[str, Any] | Any,
    *,
    citation_label: str | None = None,
) -> LexFabricEvidencePath:
    """Convert Fabric decision data into Lex citation/evidence metadata."""
    path = evidence_path_from_fabric_decision_data(
        decision_data,
        citation_label=citation_label,
    )
    return lex_evidence_from_evidence_path(path)


def lex_evidence_from_evidence_path(
    path: FabricProductEvidencePath,
) -> LexFabricEvidencePath:
    """Convert a normalized Fabric evidence path into Lex's evidence shape."""
    return LexFabricEvidencePath(
        legal_evidence_id=f"fabric:{path.subject_id}",
        citation_label=path.citation_label or path.subject_id,
        lineage_path=path.lineage_id,
        source_contract_id=path.source_contract_id,
        quality_status=path.quality_status,
        access_classification=path.access_classification,
        replay_status=path.replay_status,
        raw_source_refs=path.evidence_refs,
        export_links=path.export_links,
    )


__all__ = [
    "LexFabricEvidencePath",
    "lex_evidence_from_evidence_path",
    "lex_evidence_from_fabric_decision_data",
]
