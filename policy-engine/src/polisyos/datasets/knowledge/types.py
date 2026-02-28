"""Domain types for the dataset catalog graph (search results, distributions)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DistributionResult(BaseModel):
    """A concrete downloadable resource within a dataset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    dataset_id: str
    url: str = ""
    format: str = ""
    connector_type: str = ""
    connector_params: dict = Field(default_factory=dict)
    quality_score: float = 0.0


class DatasetSearchResult(BaseModel):
    """Dataset found by vector/text/metric search."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    description: str = ""
    publisher: str = ""
    themes: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    variables: list[str] = Field(default_factory=list)
    polisyos_metrics: list[str] = Field(default_factory=list)
    spatial: str = ""
    temporal_start: str | None = None
    temporal_end: str | None = None
    source_portal: str = ""
    formats: list[str] = Field(default_factory=list)
    similarity: float = 0.0

    # Canonical source identity fields
    source: str = ""
    agency: str = ""
    dataset_id: str = ""
    dedup_key: str = ""

    # Best distribution (for quick connector access)
    connector_type: str = ""
    connector_params: dict = Field(default_factory=dict)

    def embedding_text(self) -> str:
        """Text used for vector embedding."""
        parts = [self.title]
        if self.description:
            parts.append(self.description[:500])
        if self.keywords:
            parts.append(" ".join(self.keywords[:20]))
        if self.variables:
            parts.append(" ".join(self.variables[:20]))
        return " ".join(parts)


class DistributionRecord(BaseModel):
    """Distribution metadata for batch pipeline."""

    model_config = ConfigDict(extra="forbid")

    id: str = ""
    url: str = ""
    format: str = ""
    name: str = ""
    connector_type: str = ""
    connector_params: dict = Field(default_factory=dict)
    quality_score: float = 0.0


class DatasetRecord(BaseModel):
    """Normalized dataset metadata record (DCAT-aligned).

    Used during batch pipeline (normalize -> dedup -> graph builder).
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    description: str = ""
    publisher: str = ""
    themes: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    variables: list[str] = Field(default_factory=list)
    spatial: str = ""
    temporal_start: str | None = None
    temporal_end: str | None = None
    license: str = ""
    formats: list[str] = Field(default_factory=list)
    distributions: list[DistributionRecord] = Field(default_factory=list)
    polisyos_metrics: list[str] = Field(default_factory=list)
    source_portal: str = ""

    # Canonical source identity fields
    source: str = ""
    agency: str = ""
    dataset_id: str = ""
    dedup_key: str = ""
