"""Domain types for the dataset catalog graph (search results, distributions)."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class CatalogEmbeddingProfile(BaseModel):
    """Persisted or live encoder profile observed during Catalog query admission.

    This profile records retrieval compatibility inputs only. It does not attest
    executable encoder behavior, production ownership, model quality, or policy
    authority.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    embedding_model: str = Field(min_length=1)
    embedding_device: str = Field(min_length=1)
    embedding_dimension: int = Field(gt=0)
    encoder_asset_identity: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    basis_kind: str | None = Field(default=None, min_length=1)
    generator_rule_version: str | None = Field(default=None, min_length=1)
    basis_digest: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )

    @field_validator("embedding_model", "embedding_device")
    @classmethod
    def _nonblank_profile_value(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("embedding profile values cannot be blank")
        return normalized


class CatalogQueryGenerationContext(BaseModel):
    """Carry the selected generation and live reader profile for one query."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    state: Literal["selected", "absent", "refused", "unknown"] = "unknown"
    selected_generation_id: str | None = Field(default=None, min_length=1)
    selected_profile: CatalogEmbeddingProfile | None = None
    reader_profile: CatalogEmbeddingProfile | None = None

    @model_validator(mode="after")
    def _consistent_generation_context(self) -> CatalogQueryGenerationContext:
        if self.state == "selected" and (
            not self.selected_generation_id
            or self.selected_profile is None
            or self.reader_profile is None
        ):
            raise ValueError("selected query generation requires validated profiles")
        if self.state == "selected":
            if self.selected_profile is None or self.reader_profile is None:
                raise ValueError("selected query generation requires validated profiles")
            selected = self.selected_profile
            reader = self.reader_profile
            if (
                selected.embedding_model != reader.embedding_model
                or selected.embedding_device != reader.embedding_device
                or selected.embedding_dimension != reader.embedding_dimension
                or selected.encoder_asset_identity is None
                or selected.encoder_asset_identity != reader.encoder_asset_identity
            ):
                raise ValueError("selected query generation requires a matching live encoder")
        if self.state == "absent" and (
            self.selected_generation_id is not None
            or self.selected_profile is not None
            or self.reader_profile is not None
        ):
            raise ValueError("absent query generation cannot carry a selected profile")
        if self.state == "unknown" and (
            self.selected_generation_id is not None
            or self.selected_profile is not None
            or self.reader_profile is not None
        ):
            raise ValueError("unknown query generation cannot claim profile context")
        return self


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
    search_mode: Literal["text", "vector"] | None = Field(
        default=None,
        description=(
            "Query retrieval mode: vector-enabled hybrid search or text-only candidate search."
        ),
    )
    vector_refusal_code: str | None = Field(
        default=None,
        description="Named reason vector retrieval was refused for this query, if any.",
    )
    query_generation_context: CatalogQueryGenerationContext | None = Field(
        default=None,
        description=(
            "Selected generation and reader profile checked for this query, when available."
        ),
    )
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


class DatasetSearchResponse(BaseModel):
    """Atomic dataset query result and the retrieval status for that query.

    Unlike the legacy list result, this envelope can report a vector refusal
    when text fallback finds no datasets.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    results: list[DatasetSearchResult] = Field(
        default_factory=list,
        description="Dataset candidates returned by this query.",
    )
    search_mode: Literal["text", "vector"] | None = Field(
        default=None,
        description="Retrieval path completed by this query, when catalog search ran.",
    )
    vector_refusal_code: str | None = Field(
        default=None,
        description="Reason vector retrieval was refused before text fallback.",
    )
    limitation_code: str | None = Field(
        default=None,
        description="Reason this query's retrieval status could not be established.",
    )
    query_generation_context: CatalogQueryGenerationContext = Field(
        default_factory=CatalogQueryGenerationContext,
        description="Selected generation and reader profile checked for this query.",
    )

    @classmethod
    def from_result_rows(cls, results: Sequence[DatasetSearchResult]) -> DatasetSearchResponse:
        """Build a status envelope from legacy row results without inventing context.

        Older adapters return only rows. A true empty result therefore cannot
        establish retrieval status and is represented as a limitation. When row
        status is consistent, any shared generation context is retained; missing
        or divergent row context remains explicitly unknown.
        """
        if not results:
            return cls(limitation_code="query_status_unavailable")

        search_modes = {getattr(result, "search_mode", None) for result in results}
        refusal_codes = {getattr(result, "vector_refusal_code", None) for result in results}
        if len(search_modes) != 1 or len(refusal_codes) != 1:
            return cls(results=list(results), limitation_code="query_status_unavailable")

        search_mode = next(iter(search_modes))
        refusal_code = next(iter(refusal_codes))
        if (
            search_mode is None
            or (search_mode == "text" and not refusal_code)
            or (search_mode == "vector" and refusal_code is not None)
        ):
            return cls(results=list(results), limitation_code="query_status_unavailable")

        contexts = [getattr(result, "query_generation_context", None) for result in results]
        first_context = contexts[0]
        query_context = (
            first_context
            if first_context is not None and all(context == first_context for context in contexts)
            else CatalogQueryGenerationContext()
        )
        return cls(
            results=list(results),
            search_mode=search_mode,
            vector_refusal_code=refusal_code,
            query_generation_context=query_context,
        )

    @model_validator(mode="after")
    def _consistent_query_status(self) -> DatasetSearchResponse:
        if self.search_mode == "vector":
            if self.vector_refusal_code is not None or self.limitation_code is not None:
                raise ValueError("vector search cannot carry a refusal or limitation")
        elif self.search_mode == "text":
            if not self.vector_refusal_code or self.limitation_code is not None:
                raise ValueError("text fallback requires only a vector refusal code")
        elif self.vector_refusal_code is not None or not self.limitation_code:
            raise ValueError("unavailable search status requires only a limitation code")
        return self


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
