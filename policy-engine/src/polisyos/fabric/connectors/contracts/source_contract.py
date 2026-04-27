"""SourceContract v2 models for the Fabric contracted source platform."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.canon import content_hash as compute_content_hash
from polisyos.fabric.finite import ensure_probability
from polisyos.ir.canon import CanonSpec, to_canonical_bytes
from polisyos.ir.connectors import ConnectorMetadataSpec

from .contract import CONTRACT_ID_PATTERN, ConnectorSchemaContract
from .schema import DataSchema, FieldSpec, SchemaVersion

SOURCE_CONTRACT_SCHEMA_VERSION = "fabric.source_contract.v2"

SourceStatus = Literal["draft", "active", "deprecated", "sunset"]
SourceTrustTier = Literal[
    "institutional",
    "government",
    "community",
    "vendor",
    "internal",
    "synthetic",
    "unknown",
]
CalibrationStatus = Literal["measured", "heuristic", "declared", "unknown"]
Classification = Literal[
    "public",
    "internal",
    "confidential",
    "regulated_pii",
    "sensitive_policy_legal_signal",
]
PIITier = Literal["none", "low", "moderate", "high", "regulated"]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _version_token(value: str | SchemaVersion) -> str:
    return str(value)


class SourceContractSource(BaseModel):
    """Identity and profile routing for a production source surface."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connector_id: str = Field(..., min_length=1, max_length=256)
    dataset_pattern: str = Field(..., min_length=1, max_length=512)
    profile_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    source_name: str = Field(default="", max_length=256)
    source_organization: str = Field(default="", max_length=256)
    source_url: str | None = Field(default=None, max_length=2048)


class SourceContractSchema(BaseModel):
    """Schema contract view compatible with ConnectorSchemaContract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_id: str | None = Field(default=None, min_length=1, max_length=256)
    schema_version: str | None = Field(default=None, pattern=r"^\d+\.\d+(\.\d+)?$")
    fields: tuple[FieldSpec, ...] = Field(default=())
    schema_contract_ref: str | None = Field(default=None, max_length=512)
    compatibility_status: Literal[
        "contracted",
        "template_only",
        "pending_profile_specific_schema",
    ] = "contracted"

    @classmethod
    def from_connector_schema_contract(
        cls,
        contract: ConnectorSchemaContract,
        *,
        snapshot_ref: str = "schemas/snapshots/fabric/connector_contract_registry.json",
    ) -> SourceContractSchema:
        """Build the SourceContract schema block from an existing schema contract."""

        return cls(
            schema_id=contract.schema.schema_id,
            schema_version=_version_token(contract.schema_version),
            fields=contract.schema.fields,
            schema_contract_ref=f"{snapshot_ref}#/contracts/{contract.contract_id}",
            compatibility_status="contracted",
        )

    def to_data_schema(
        self,
        *,
        source: str = "",
        description: str = "",
    ) -> DataSchema:
        """Convert a fully-specified SourceContract schema block to DataSchema."""

        if not self.schema_id or not self.schema_version or not self.fields:
            raise ValueError("schema_id, schema_version, and fields are required")
        return DataSchema(
            schema_id=self.schema_id,
            version=SchemaVersion.parse(self.schema_version),
            fields=self.fields,
            source=source,
            description=description,
        )

    @property
    def has_schema_evidence(self) -> bool:
        return bool(self.schema_contract_ref or (self.schema_id and self.fields))


class SourceMetricDefinition(BaseModel):
    """Semantic metric definition carried by a source contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_id: str = Field(..., min_length=1, max_length=256)
    description: str = Field(default="", max_length=1024)
    unit: str | None = Field(default=None, max_length=128)
    canonical_field: str | None = Field(default=None, max_length=256)


class SourceContractSemantics(BaseModel):
    """Domain and canonical semantic IDs for source outputs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    domain: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    metric_definitions: tuple[SourceMetricDefinition, ...] = Field(default=())
    canonical_ids: tuple[str, ...] = Field(default=())


class SourceContractSecurity(BaseModel):
    """Security, access, and tenant-boundary contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pii_tier: PIITier = "none"
    classification: Classification = "public"
    tenant_scope: Literal["shared_public", "tenant_isolated", "restricted"] = "shared_public"
    safe_filters_required: bool = True
    audit_required: bool = True


class SourceContractQuality(BaseModel):
    """Declarative data-quality contract reference."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_ref: str = Field(..., min_length=1, max_length=512)
    required_checks: tuple[str, ...] = Field(
        default=("schema_compliance", "finite_values", "bounded_reads")
    )
    min_quality_score: float = Field(default=0.8, ge=0.0, le=1.0)

    @field_validator("min_quality_score", mode="before")
    @classmethod
    def _validate_min_quality_score(cls, value: object) -> float:
        return ensure_probability(value, what="min_quality_score")


class SourceContractSLA(BaseModel):
    """Source SLO/SLA declaration used by scorecards and release gates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    refresh_frequency: str = Field(default="daily", min_length=1, max_length=64)
    max_latency: str = Field(default="PT2S", min_length=1, max_length=64)
    availability_target: float = Field(default=0.99, ge=0.0, le=1.0)
    freshness_slo_seconds: int = Field(default=86_400, ge=0)
    p95_latency_ms: float = Field(default=2_000.0, ge=0.0)
    replay_success_target: float = Field(default=0.99, ge=0.0, le=1.0)

    @classmethod
    def from_metadata(cls, metadata: ConnectorMetadataSpec) -> SourceContractSLA:
        sla = metadata.sla
        if sla is None:
            return cls()
        return cls(
            availability_target=sla.availability_target,
            freshness_slo_seconds=sla.freshness_slo_seconds,
            p95_latency_ms=sla.p95_latency_ms,
            replay_success_target=sla.replay_success_target,
        )


class SourceContractTerms(BaseModel):
    """Allowed/disallowed source use policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed_uses: tuple[str, ...] = Field(default=("policy_analysis", "reporting"))
    disallowed_uses: tuple[str, ...] = Field(default=())
    terms_url: str | None = Field(default=None, max_length=2048)
    attribution_required: bool = False


class SourceContractReplay(BaseModel):
    """Replay fixture or explicit non-replayable reason."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    required: bool = True
    fixture_ref: str | None = Field(default=None, max_length=512)
    non_replayable_reason: str | None = Field(default=None, max_length=512)
    determinism_key: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def _validate_replay_evidence(self) -> SourceContractReplay:
        if self.required and not self.fixture_ref:
            raise ValueError("replay.fixture_ref is required when replay.required=true")
        if not self.required and not self.non_replayable_reason:
            raise ValueError(
                "replay.non_replayable_reason is required when replay.required=false"
            )
        return self

    @property
    def has_replay_evidence(self) -> bool:
        return bool(self.fixture_ref or self.non_replayable_reason)


class SourceContractLineage(BaseModel):
    """Lineage seed required before a source becomes production-visible."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed_node_kind: str = Field(default="source_dataset", min_length=1, max_length=128)
    seed_fields: tuple[str, ...] = Field(default=())
    evidence_ref: str | None = Field(default=None, max_length=512)


class SourceContractTrust(BaseModel):
    """Source trust declaration and calibration state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tier: SourceTrustTier = "unknown"
    calibration_status: CalibrationStatus = "heuristic"
    rationale: str = Field(default="", max_length=1024)


class SourceContractRetention(BaseModel):
    """Retention contract for source artifacts and replay evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy: Literal["retain", "expire", "source_terms_bound"] = "retain"
    min_retention_days: int = Field(default=30, ge=0)
    artifact_retention_days: int = Field(default=365, ge=0)
    cold_storage_required: bool = False

    @model_validator(mode="after")
    def _validate_retention(self) -> SourceContractRetention:
        if self.artifact_retention_days < self.min_retention_days:
            raise ValueError("artifact_retention_days must be >= min_retention_days")
        return self


class SourceContractDocs(BaseModel):
    """Generated documentation targets for source platform reference."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reference_page: str = "docs/reference/fabric/source-platform.md"
    generated_anchor: str | None = None


class SourceDeprecationPolicy(BaseModel):
    """Deprecation/sunset policy for source contracts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    deprecated_at: datetime | None = None
    sunset_at: datetime | None = None
    replacement_contract_id: str | None = Field(default=None, max_length=256)
    reason: str = Field(default="", max_length=1024)
    migration_note: str = Field(default="", max_length=1024)

    @field_validator("deprecated_at", "sunset_at", mode="after")
    @classmethod
    def _ensure_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class SourceContract(BaseModel):
    """Best-in-class source contract covering schema, trust, quality, and replay."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
    )

    schema_version: str = SOURCE_CONTRACT_SCHEMA_VERSION
    id: str = Field(..., pattern=CONTRACT_ID_PATTERN)
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    owner: str = Field(..., min_length=1, max_length=128)
    reviewer: str = Field(..., min_length=1, max_length=128)
    source: SourceContractSource
    schema_contract: SourceContractSchema = Field(alias="schema")
    semantics: SourceContractSemantics
    security: SourceContractSecurity
    quality: SourceContractQuality
    sla: SourceContractSLA
    terms: SourceContractTerms
    replay: SourceContractReplay
    lineage: SourceContractLineage
    source_trust: SourceContractTrust
    retention: SourceContractRetention = Field(default_factory=SourceContractRetention)
    docs: SourceContractDocs = Field(default_factory=SourceContractDocs)
    status: SourceStatus = "active"
    deprecation: SourceDeprecationPolicy | None = None
    created_at: datetime = Field(default_factory=_utc_now)

    @field_validator("created_at", mode="after")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _validate_contract_evidence(self) -> SourceContract:
        if self.status == "active":
            if not self.schema_contract.has_schema_evidence:
                raise ValueError("active SourceContract requires schema evidence")
            if not self.quality.contract_ref:
                raise ValueError("active SourceContract requires quality contract ref")
            if not self.replay.has_replay_evidence:
                raise ValueError("active SourceContract requires replay evidence")
            if not self.lineage.seed_node_kind:
                raise ValueError("active SourceContract requires lineage seed")
        if self.status in {"deprecated", "sunset"}:
            if self.deprecation is None:
                raise ValueError(
                    "deprecated/sunset SourceContract requires deprecation policy"
                )
            if not self.deprecation.reason or not self.deprecation.migration_note:
                raise ValueError(
                    "deprecated/sunset SourceContract requires reason and migration_note"
                )
            if self.deprecation.sunset_at is None:
                raise ValueError(
                    "deprecated/sunset SourceContract requires a sunset_at date"
                )
        return self

    @property
    def schema(self) -> SourceContractSchema:
        """Backwards-compatible accessor for callers using ``contract.schema``."""
        return self.schema_contract

    @property
    def content_hash(self) -> str:
        payload = self.model_dump(
            mode="json",
            by_alias=True,
            exclude={"created_at"},
        )
        digest = compute_content_hash(
            to_canonical_bytes(payload, spec=CanonSpec(forbid_floats=False))
        )
        return f"sha256:{digest}"

    @property
    def is_replayable(self) -> bool:
        return bool(self.replay.fixture_ref)

    @classmethod
    def from_connector_schema_contract(
        cls,
        schema_contract: ConnectorSchemaContract,
        *,
        metadata: ConnectorMetadataSpec | None = None,
        profile_id: str,
        owner: str | None = None,
        reviewer: str = "@fabric-reviewers",
        version: str = "1.1.0",
        domain: str = "general_policy_data",
        replay_fixture_ref: str | None = None,
        non_replayable_reason: str | None = None,
    ) -> SourceContract:
        """Create SourceContract v2 from the legacy ConnectorSchemaContract."""

        source_name = metadata.source_name if metadata is not None else ""
        source_org = metadata.source_organization if metadata is not None else ""
        source_url = metadata.source_url if metadata is not None else None
        quality_ref = (
            metadata.quality_contract_id
            if metadata is not None and metadata.quality_contract_id
            else f"fabric.quality.{schema_contract.contract_id}.v1"
        )
        classification = (
            metadata.data_classification
            if metadata is not None
            else "public"
        )
        replay_required = replay_fixture_ref is not None
        return cls(
            id=schema_contract.contract_id,
            version=version,
            owner=owner or (metadata.owner if metadata is not None else "@fabric-owners"),
            reviewer=reviewer,
            source=SourceContractSource(
                connector_id=schema_contract.connector_id,
                dataset_pattern=schema_contract.dataset_id,
                profile_id=profile_id,
                source_name=source_name,
                source_organization=source_org,
                source_url=source_url,
            ),
            schema=SourceContractSchema.from_connector_schema_contract(schema_contract),
            semantics=SourceContractSemantics(
                domain=domain,
                canonical_ids=(schema_contract.schema.schema_id,),
            ),
            security=SourceContractSecurity(classification=classification),  # type: ignore[arg-type]
            quality=SourceContractQuality(
                contract_ref=quality_ref,
                required_checks=(
                    "schema_compliance",
                    "finite_values",
                    "freshness",
                    "safe_filters",
                    "bounded_reads",
                ),
            ),
            sla=SourceContractSLA.from_metadata(metadata) if metadata is not None else SourceContractSLA(),
            terms=SourceContractTerms(
                terms_url=source_url,
                attribution_required=bool(source_org),
            ),
            replay=SourceContractReplay(
                required=replay_required,
                fixture_ref=replay_fixture_ref,
                non_replayable_reason=(
                    None
                    if replay_required
                    else non_replayable_reason
                    or "Replay fixture has not been recorded for this migrated source yet."
                ),
                determinism_key=schema_contract.content_hash,
            ),
            lineage=SourceContractLineage(
                seed_node_kind="source_dataset",
                seed_fields=tuple(schema_contract.schema.field_names()[:8]),
                evidence_ref=schema_contract.content_hash,
            ),
            source_trust=SourceContractTrust(
                tier="institutional",
                calibration_status="heuristic",
                rationale="Migrated from ConnectorSchemaContract and connector metadata.",
            ),
        )

    def to_snapshot_record(self) -> dict[str, Any]:
        """Serialize contract with stable evidence fields for snapshots."""

        payload = self.model_dump(mode="json", by_alias=True, exclude={"created_at"})
        return {
            "id": self.id,
            "version": self.version,
            "connector_id": self.source.connector_id,
            "profile_id": self.source.profile_id,
            "status": self.status,
            "content_hash": self.content_hash,
            "contract": payload,
        }


def source_contracts_snapshot_payload(
    contracts: Sequence[SourceContract],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build deterministic SourceContract v2 snapshot payload."""

    return {
        "schema_version": SOURCE_CONTRACT_SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now().isoformat(),
        "contracts": {
            contract.id: contract.to_snapshot_record()
            for contract in sorted(contracts, key=lambda item: item.id)
        },
    }


def source_contracts_compatibility_evidence(
    contracts: Sequence[SourceContract],
) -> dict[str, Any]:
    """Summarize SourceContract v2 migration state for the Fabric inventory."""

    rows = list(contracts)
    active = [contract for contract in rows if contract.status == "active"]
    replayable = [contract for contract in rows if contract.is_replayable]
    non_replayable_with_reason = [
        contract
        for contract in rows
        if not contract.is_replayable and contract.replay.non_replayable_reason
    ]
    return {
        "schema_version": SOURCE_CONTRACT_SCHEMA_VERSION,
        "contract_count": len(rows),
        "active_contract_count": len(active),
        "replay_fixture_count": len(replayable),
        "non_replayable_reason_count": len(non_replayable_with_reason),
        "contracts": [contract.id for contract in sorted(rows, key=lambda item: item.id)],
    }


def load_source_contracts(payload: Mapping[str, Any]) -> tuple[SourceContract, ...]:
    """Parse SourceContract v2 snapshot payload or a raw mapping of contracts."""

    raw_contracts = payload.get("contracts", payload)
    if not isinstance(raw_contracts, Mapping):
        raise TypeError("SourceContract payload must contain a contracts mapping")
    contracts: list[SourceContract] = []
    for raw_value in raw_contracts.values():
        if isinstance(raw_value, Mapping) and "contract" in raw_value:
            raw_value = raw_value["contract"]
        contracts.append(SourceContract.model_validate(raw_value))
    return tuple(sorted(contracts, key=lambda item: item.id))
