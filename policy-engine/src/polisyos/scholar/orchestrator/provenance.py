"""Scholar citation adapters backed by Fabric provenance."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.fabric.product_integration import (
    FabricProductEvidencePath,
    evidence_path_from_fabric_decision_data,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


class ScholarFabricCitation(BaseModel):
    """Citation-ready Scholar evidence record sourced from a Fabric trust envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    citation_id: str
    title: str
    source_contract_id: str
    lineage_id: str
    quality_status: str
    access_classification: str
    evidence_refs: tuple[str, ...] = ()
    export_links: dict[str, str] = Field(default_factory=dict)


def scholar_citation_from_fabric_decision_data(
    decision_data: Mapping[str, Any] | Any,
    *,
    title: str | None = None,
) -> ScholarFabricCitation:
    """Convert Fabric decision data into a Scholar citation/evidence path."""
    path = evidence_path_from_fabric_decision_data(decision_data, citation_label=title)
    return scholar_citation_from_evidence_path(path)


def scholar_citation_from_evidence_path(
    path: FabricProductEvidencePath,
) -> ScholarFabricCitation:
    """Convert a normalized Fabric evidence path into Scholar's citation shape."""
    return ScholarFabricCitation(
        citation_id=f"fabric:{path.lineage_id}",
        title=path.citation_label or path.subject_id,
        source_contract_id=path.source_contract_id,
        lineage_id=path.lineage_id,
        quality_status=path.quality_status,
        access_classification=path.access_classification,
        evidence_refs=path.evidence_refs,
        export_links=path.export_links,
    )


__all__ = [
    "ScholarFabricCitation",
    "scholar_citation_from_evidence_path",
    "scholar_citation_from_fabric_decision_data",
]
