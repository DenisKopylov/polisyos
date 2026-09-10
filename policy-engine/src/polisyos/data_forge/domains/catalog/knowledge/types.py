"""Domain types for the dataset catalog graph (search results, distributions)."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DistributionResult(BaseModel):
    """A concrete downloadable resource within a dataset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    dataset_id: str
    url: str = ""
    format: str = ""
    connector_type: str = ""
    connector_params: dict = Field(default_factory=dict)
    source_locator: str = ""
    profile_id: str = ""
    media_type: str = ""
    machine_readable: bool = False
    parser_supported: bool = False
    size_estimate_bytes: int | None = None
    checksum: str = ""
    default_filters: dict[str, list[str]] = Field(default_factory=dict)
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
    source_dataset_id: str = ""
    dedup_key: str = ""
    execution_tier: str = "catalog"
    update_frequency: str = ""
    last_updated: str | None = None
    coverage: DatasetCoverage = Field(default_factory=lambda: DatasetCoverage())
    access: DatasetAccess = Field(default_factory=lambda: DatasetAccess())
    quality: DatasetQuality = Field(default_factory=lambda: DatasetQuality())
    preferred_distribution_id: str = ""

    # Best distribution (for quick connector access)
    connector_type: str = ""
    connector_params: dict = Field(default_factory=dict)
    profile_id: str = ""
    search_explanation: dict[str, object] | None = None

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
    source_locator: str = ""
    profile_id: str = ""
    media_type: str = ""
    machine_readable: bool = False
    parser_supported: bool = False
    size_estimate_bytes: int | None = None
    checksum: str = ""
    default_filters: dict[str, list[str]] = Field(default_factory=dict)
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
    polisyos_metrics_methods: dict[str, str] = Field(default_factory=dict)
    source_portal: str = ""

    # Canonical source identity fields
    source: str = ""
    agency: str = ""
    dataset_id: str = ""
    source_dataset_id: str = ""
    dedup_key: str = ""
    execution_tier: str = "catalog"
    update_frequency: str = ""
    last_updated: str | None = None
    coverage: DatasetCoverage = Field(default_factory=lambda: DatasetCoverage())
    access: DatasetAccess = Field(default_factory=lambda: DatasetAccess())
    quality: DatasetQuality = Field(default_factory=lambda: DatasetQuality())
    preferred_distribution_id: str = ""


class DatasetVariable(BaseModel):
    """Mapping from raw dataset variable to canonical SKG variable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_name: str
    canonical_name: str
    mapping_confidence: float
    mapping_rationale: str
    is_proxy: bool = False
    proxy_penalty: float = 0.0


class DatasetCoverage(BaseModel):
    """Coverage metadata used in transportability matching."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    countries: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    time_range: str = ""
    time_start: str | None = None
    time_end: str | None = None
    granularity: str = ""


class DatasetAccess(BaseModel):
    """Access details for dataset discovery and retrieval."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    access_type: str = "open"
    api_endpoint: str | None = None
    bulk_download_url: str | None = None
    license: str = ""
    auth_required: bool = False


class DatasetQuality(BaseModel):
    """Quality/readiness scores for runtime-grade dataset selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    description_score: float = 0.0
    machine_readable_score: float = 0.0
    parser_support_score: float = 0.0
    freshness_score: float = 0.0
    execution_readiness_score: float = 0.0


class DatasetEntry(BaseModel):
    """High-level dataset registry entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str
    provider: str
    title: str
    variables: list[DatasetVariable] = Field(default_factory=list)
    coverage: DatasetCoverage = Field(default_factory=DatasetCoverage)
    access: DatasetAccess = Field(default_factory=DatasetAccess)
    update_frequency: str
    last_updated: str


class ResolvedFetchTarget(BaseModel):
    """Concrete fetch target derived from catalog metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_dataset_id: str
    connector_id: str
    profile_id: str = ""
    request_dataset_id: str
    distribution_id: str = ""
    connector_params: dict = Field(default_factory=dict)
    default_filters: dict[str, list[str]] = Field(default_factory=dict)
    machine_readable: bool = False
    parser_supported: bool = False


class MetricBindingMatch(BaseModel):
    """Deterministic metric -> dataset/distribution binding row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: str
    catalog_dataset_id: str
    distribution_id: str = ""
    connector_id: str
    profile_id: str = ""
    request_dataset_id: str
    confidence: float = 0.0
    metric_inference_confidence: float = 0.0
    default_filters: dict[str, list[str]] = Field(default_factory=dict)
    execution_tier: str = "catalog"
    source: str = ""
    title: str = ""


class CatalogContentIdentity(BaseModel):
    """Pin bytes of one catalog input without granting those bytes new authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_path: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    byte_size: int = Field(gt=0)


class CatalogFetchBinding(BaseModel):
    """Bind an executable tuple to the actual baseline/overlay catalog read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.data_forge.catalog_fetch_binding.v1"] = (
        "polisyos.data_forge.catalog_fetch_binding.v1"
    )
    baseline: CatalogContentIdentity
    overlay_path: str | None
    overlay: CatalogContentIdentity | None
    metric_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    profile_id: str | None
    requested_filters: dict[str, list[str]]
    binding: MetricBindingMatch | None
    target: ResolvedFetchTarget
    predicate_basis: Literal["recomputed"] = "recomputed"


class CatalogFetchRequest(BaseModel):
    """One exact tuple submitted to catalog admission, independent of transport."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    metric_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    profile_id: str | None
    filters: dict[str, list[str]]


class CatalogFetchResolution(BaseModel):
    """An ordered bulk outcome; unreadable source rows never become unsupported."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    request: CatalogFetchRequest
    status: Literal["bound", "not_admitted", "ambiguous"]
    binding: CatalogFetchBinding | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def _consistent_outcome(self) -> CatalogFetchResolution:
        if self.status == "bound":
            if self.binding is None or self.reason is not None:
                raise ValueError("bound outcome requires its binding and no refusal reason")
        elif self.binding is not None or not self.reason:
            raise ValueError("non-bound outcome requires a reason and no binding")
        return self


class DatasetMatch(BaseModel):
    """Candidate dataset match for canonical variable lookup."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str
    raw_variable: str
    canonical_variable: str
    is_proxy: bool = False
    proxy_penalty: float = 0.0
    mapping_confidence: float = 0.0
    coverage_match: str = "none"
    temporal_match: str = "none"
    actual_survey_year: int | None = None
    temporal_distance_years: int = 0
    alignment_method: str = ""
    alignment_evidence: str = ""


class DistributionType(str, Enum):
    """Distribution type public type."""

    POINT = "point"
    EMPIRICAL = "empirical"
    KDE = "kde"
    NORMAL = "normal"
    BOUNDED = "bounded"


class PStarZResult(BaseModel):
    """Computed P*(Z) (or P*(Z|X)) value with provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_variable: str
    value: float | None
    dataset_id: str | None
    raw_variable: str | None
    is_proxy: bool = False
    proxy_chain: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    penalty_breakdown: dict[str, float] = Field(default_factory=dict)
    is_conditional: bool = False
    condition_on: dict[str, float] = Field(default_factory=dict)
    distribution: list[float] | None = None
    distribution_type: DistributionType = DistributionType.POINT
    std_error: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    uncertainty_sources: list[str] = Field(default_factory=list)
    imputation_method: str | None = None
    imputation_penalty: float = 0.0
    data_support_year: int | None = None
    data_support_country: str | None = None


DatasetSearchResult.model_rebuild()
DatasetRecord.model_rebuild()
