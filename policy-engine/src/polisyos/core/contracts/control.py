"""Control Plane contracts — request/response DTOs for write operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .runtime import ApiMeta

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

RunMode = Literal["workflow", "agent_circuit"]
CheckpointPolicyType = Literal["strict", "lenient", "disabled"]
CachePolicyType = Literal["default", "static", "volatile", "smart"]
RunLaunchStatus = Literal["accepted", "rejected"]
IngestStatus = Literal["completed", "partial", "failed"]
ExecutionMode = Literal["batch_full", "batch_incremental", "streaming_windowed"]

# ---------------------------------------------------------------------------
# Data source binding
# ---------------------------------------------------------------------------


class DataSourceBinding(BaseModel):
    """Exactly one of these fields must be provided."""

    model_config = ConfigDict(extra="forbid")

    data_snapshot_ref: str | None = None
    input_bindings_ref: str | None = None
    data_view_request_ref: str | None = None


# ---------------------------------------------------------------------------
# Workflow run launch
# ---------------------------------------------------------------------------


class WorkflowRunRequest(BaseModel):
    """POST /api/v1/control/runs — launch a workflow run."""

    model_config = ConfigDict(extra="forbid")

    mode: RunMode = "workflow"
    data_source: DataSourceBinding
    trinity_bundle_ref: str | None = None
    policy_spec_ref: str | None = None
    model_spec_ref: str | None = None
    research_intent_ref: str | None = None
    knowledge_bundle_ref: str | None = None
    norm_pack_ref: str | None = None
    calibration_report_ref: str | None = None
    checkpoint_policy: CheckpointPolicyType = "strict"
    params: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Natural-language run launch (agent circuit)
# ---------------------------------------------------------------------------


class NaturalLanguageRunRequest(BaseModel):
    """POST /api/v1/control/runs/nl — NL request triggering agent circuit."""

    model_config = ConfigDict(extra="forbid")

    request: str = Field(..., min_length=1, max_length=10_000)
    context: dict[str, Any] = Field(default_factory=dict)
    domain_hint: str | None = None
    data_source: DataSourceBinding | None = None
    max_iterations: int = Field(default=3, ge=1, le=10)
    llm_model: str | None = None
    llm_models: list[str] | None = None
    max_parallel_models: int = Field(default=1, ge=1, le=16)
    run_budget_usd: float | None = Field(default=None, ge=0.0)
    per_model_budget_usd: float | None = Field(default=None, ge=0.0)
    checkpoint_policy: CheckpointPolicyType = "strict"


# ---------------------------------------------------------------------------
# Run launch response (shared by both endpoints)
# ---------------------------------------------------------------------------


class RunLaunchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    status: RunLaunchStatus
    run_id: str
    message: str


# ---------------------------------------------------------------------------
# Data ingestion
# ---------------------------------------------------------------------------


class DatasetFetchSpecRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str
    dataset_id: str
    filters: dict[str, list[str]] = Field(default_factory=dict)
    date_start: str | None = None
    date_end: str | None = None


class IngestRequest(BaseModel):
    """POST /api/v1/control/data/ingest — trigger data collection."""

    model_config = ConfigDict(extra="forbid")

    datasets: list[DatasetFetchSpecRequest] = Field(..., min_length=1)
    source: str = "dashboard"
    license_name: str = "open"
    cache_policy: str = "default"
    connection_profile: str | None = None
    execution_mode: ExecutionMode = "batch_full"
    produce_data_snapshot: bool = True
    record_mode: bool = False
    replay_ref: str | None = None
    binding_profile_id: str | None = None
    produce_input_bindings: bool = False


class IngestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    status: IngestStatus
    evidence_bundle_ref: str | None = None
    data_snapshot_ref: str | None = None
    datasets_fetched: int = 0
    message: str
    warnings: list[str] = Field(default_factory=list)
    cursor_ref: str | None = None
    mode_effective: str | None = None
    record_ref: str | None = None
    input_bindings_ref: str | None = None


# ---------------------------------------------------------------------------
# Connectors listing
# ---------------------------------------------------------------------------


class ConnectorInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str
    namespace: str
    version: str
    known_datasets: list[str] = Field(default_factory=list)
    loaded: bool = False
    last_health_check: datetime | None = None
    available_profiles: list[str] = Field(default_factory=list)


class ConnectorsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    connectors: list[ConnectorInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Source profiles
# ---------------------------------------------------------------------------


class SourceProfileInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    display_name: str
    description: str = ""
    connector_family: str
    base_url: str
    auth_policy: str = "none"
    tags: list[str] = Field(default_factory=list)
    source_organization: str = ""
    estimated_datasets: int | None = None
    connector_available: bool = False


class SourceProfilesListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    profiles: list[SourceProfileInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# LLM model profiles
# ---------------------------------------------------------------------------


class ModelProfileInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    display_name: str
    description: str = ""
    provider: str
    model_id: str
    base_url: str
    tags: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    input_cost_per_mtoken_usd: float | None = Field(default=None, ge=0.0)
    output_cost_per_mtoken_usd: float | None = Field(default=None, ge=0.0)
    enabled: bool = True


class ModelProfilesListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    profiles: list[ModelProfileInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Binding profiles
# ---------------------------------------------------------------------------


class BindingProfileInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    display_name: str
    description: str = ""
    schema_family: str
    strategy: str = "auto"
    rule_count: int = 0
    expected_columns: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class BindingProfilesListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    profiles: list[BindingProfileInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Cache status
# ---------------------------------------------------------------------------


class CacheEntryInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cache_key: str
    connector_id: str
    dataset_id: str
    created_at: datetime
    expires_at: datetime | None = None
    size_bytes: int = 0
    is_valid: bool = True


class CacheStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    total_entries: int = 0
    total_size_bytes: int = 0
    entries: list[CacheEntryInfo] = Field(default_factory=list)


__all__ = [
    "BindingProfileInfo",
    "BindingProfilesListResponse",
    "CacheEntryInfo",
    "CachePolicyType",
    "CacheStatusResponse",
    "CheckpointPolicyType",
    "ConnectorInfo",
    "ConnectorsListResponse",
    "DataSourceBinding",
    "DatasetFetchSpecRequest",
    "ExecutionMode",
    "IngestRequest",
    "IngestResponse",
    "IngestStatus",
    "NaturalLanguageRunRequest",
    "ModelProfileInfo",
    "ModelProfilesListResponse",
    "RunLaunchResponse",
    "RunLaunchStatus",
    "RunMode",
    "SourceProfileInfo",
    "SourceProfilesListResponse",
    "WorkflowRunRequest",
]
