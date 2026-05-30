"""Attestation records and trust-boundary closeout checks."""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ATTESTATION_SCHEMA_VERSION = "polisyos.runtime.attestation.v1"
DEFAULT_TRUST_BOUNDARY_REGISTRY = (
    Path(__file__).resolve().parents[4]
    / "architecture"
    / "production_quality"
    / "trust_boundaries.toml"
)
REQUIRED_TRUST_BOUNDARY_IDS = frozenset(
    {
        "runtime_worker",
        "cas_writer",
        "bundle_assembler",
        "scorecard_builder",
        "readiness_aggregator",
        "approval_packet_builder",
        "dashboard_projection",
        "public_export_renderer",
        "provider_model_gateway",
        "external_data_connector",
        "legal_kg_connector",
        "prompt_tool_parser_executor",
    }
)

IsolationStatus = Literal["isolated", "shared", "unknown", "violated"]
ConsumerVerificationStatus = Literal["verified", "failed", "not_verified"]
TamperCheckStatus = Literal["pass", "fail", "not_checked"]
TrustBoundaryClassification = Literal[
    "runtime_authority",
    "cas_authority",
    "packaging_only",
    "reader_enforcer",
    "projection_only",
    "public_export",
    "external_gateway",
    "external_connector",
    "tool_execution",
]
AttestationStatus = Literal[
    "verified",
    "missing",
    "not_required",
    "consumer_verification_failed",
    "tamper_check_failed",
    "isolation_failed",
    "service_generation_failed",
    "functionary_mismatch",
    "producer_identity_mismatch",
    "evidence_ref_missing",
    "signature_ref_missing",
    "synthetic_material_ref",
    "material_mismatch",
    "product_mismatch",
]


class AttestationError(RuntimeError):
    """Raised when a trust-boundary attestation cannot satisfy closeout."""


AttestationViolation = AttestationError


class TrustBoundaryRegistryError(ValueError):
    """Raised when the trust-boundary registry is missing or invalid."""


class AttestedMaterial(BaseModel):
    """Reference to one material or product observed across a trust boundary."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)


class FunctionaryIdentity(BaseModel):
    """Service or actor performing a trust-boundary step."""

    model_config = ConfigDict(extra="forbid")

    functionary_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    service_account: str | None = Field(default=None, min_length=1)


class ProducerIdentity(BaseModel):
    """Producer identity bound to an attested step."""

    model_config = ConfigDict(extra="forbid")

    component: str = Field(min_length=1)
    version: str = Field(min_length=1)
    owner: str = Field(min_length=1)


class EnvironmentIdentity(BaseModel):
    """Runtime environment identity where the attested step executed."""

    model_config = ConfigDict(extra="forbid")

    environment_id: str = Field(min_length=1)
    execution_profile: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str | None = Field(default=None, min_length=1)
    runner_id: str | None = Field(default=None, min_length=1)


class AttestationRecord(BaseModel):
    """Authority-bearing attestation for a trust-boundary step."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = ATTESTATION_SCHEMA_VERSION
    attestation_id: str = Field(min_length=1)
    trust_boundary_id: str = Field(min_length=1)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expected_materials: list[AttestedMaterial] = Field(default_factory=list)
    observed_materials: list[AttestedMaterial] = Field(default_factory=list)
    expected_products: list[AttestedMaterial] = Field(default_factory=list)
    observed_products: list[AttestedMaterial] = Field(default_factory=list)
    functionary: FunctionaryIdentity
    producer_identity: ProducerIdentity
    environment_identity: EnvironmentIdentity
    isolation_status: IsolationStatus
    service_generated: bool
    consumer_verification: ConsumerVerificationStatus
    tamper_check_status: TamperCheckStatus
    signature_ref: str | None = Field(default=None, min_length=1)
    evidence_ref: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrustBoundary(BaseModel):
    """Registry declaration for one trust boundary."""

    model_config = ConfigDict(extra="forbid")

    boundary_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    classification: TrustBoundaryClassification
    functionary: str = Field(min_length=1)
    producer_owner: str = Field(min_length=1)
    consumer: str = Field(min_length=1)
    requires_attestation: bool
    production_closeout_required: bool
    diagnostic_readable_without_attestation: bool
    isolation_required: bool
    service_generated_required: bool
    expected_material_kinds: list[str] = Field(default_factory=list)
    expected_product_kinds: list[str] = Field(default_factory=list)
    scorecard_gate_name: str = Field(min_length=1)
    scorecard_stage: str = Field(min_length=1)
    failure_code: str = Field(min_length=1)
    next_action: str = Field(min_length=1)


@dataclass(frozen=True)
class TrustBoundaryRegistry:
    """Loaded trust-boundary registry keyed by boundary id."""

    boundaries: dict[str, TrustBoundary]

    def require(self, boundary_id: str) -> TrustBoundary:
        try:
            return self.boundaries[boundary_id]
        except KeyError as exc:
            raise TrustBoundaryRegistryError(
                f"unknown trust boundary: {boundary_id}"
            ) from exc


@dataclass(frozen=True)
class AttestationRequirementResult:
    """Closeout relevance for one trust-boundary attestation requirement."""

    boundary: TrustBoundary
    status: AttestationStatus
    diagnostic_readable: bool
    production_closeout_satisfied: bool
    failure_code: str
    message: str
    next_action: str | None = None
    attestation_id: str | None = None
    attestation_ref: str | None = None

    def assert_production_closeout_satisfied(self) -> None:
        if not self.production_closeout_satisfied:
            raise AttestationViolation(self.failure_code)


def deserialize_attestation_record(payload: Mapping[str, Any]) -> AttestationRecord:
    """Validate and deserialize one attestation record."""

    return AttestationRecord.model_validate(payload)


def serialize_attestation_record(record: AttestationRecord) -> dict[str, Any]:
    """Serialize one attestation record for JSON-compatible persistence."""

    return record.model_dump(mode="json", exclude_none=True)


def build_attestation_record(
    *,
    boundary_id: str,
    expected_materials: Iterable[Mapping[str, Any]],
    observed_materials: Iterable[Mapping[str, Any]],
    expected_products: Iterable[Mapping[str, Any]],
    observed_products: Iterable[Mapping[str, Any]],
    functionary: Mapping[str, Any],
    producer_identity: Mapping[str, Any],
    environment_identity: Mapping[str, Any],
    isolation_status: IsolationStatus,
    service_generated: bool,
    consumer_verification: ConsumerVerificationStatus,
    tamper_check_status: TamperCheckStatus,
    attestation_id: str | None = None,
    evidence_ref: str | None = None,
    signature_ref: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> AttestationRecord:
    """Build an attestation from explicit expected and observed boundary evidence."""

    return AttestationRecord(
        attestation_id=attestation_id or f"att-{boundary_id}",
        trust_boundary_id=boundary_id,
        expected_materials=[AttestedMaterial.model_validate(item) for item in expected_materials],
        observed_materials=[AttestedMaterial.model_validate(item) for item in observed_materials],
        expected_products=[AttestedMaterial.model_validate(item) for item in expected_products],
        observed_products=[AttestedMaterial.model_validate(item) for item in observed_products],
        functionary=FunctionaryIdentity.model_validate(functionary),
        producer_identity=ProducerIdentity.model_validate(producer_identity),
        environment_identity=EnvironmentIdentity.model_validate(environment_identity),
        isolation_status=isolation_status,
        service_generated=service_generated,
        consumer_verification=consumer_verification,
        tamper_check_status=tamper_check_status,
        evidence_ref=evidence_ref,
        signature_ref=signature_ref,
        metadata=dict(metadata or {}),
    )


def build_verified_attestation_record(
    *,
    boundary_id: str,
    material_refs: Mapping[str, str] | None = None,
    product_refs: Mapping[str, str] | None = None,
    attestation_id: str | None = None,
    evidence_ref: str | None = None,
    signature_ref: str | None = None,
    producer_component: str | None = None,
    producer_version: str = "2026.05.15+hds-phase4.6",
    environment_id: str = "prod-cell-a",
    execution_profile: str = "production",
    tenant_id: str = "tenant-1",
    cell_id: str | None = "cell-a",
    runner_id: str | None = "runtime-worker-1",
    functionary_id: str | None = None,
    service_account: str | None = None,
    isolation_status: IsolationStatus | None = None,
    service_generated: bool = True,
    consumer_verification: ConsumerVerificationStatus = "verified",
    tamper_check_status: TamperCheckStatus = "pass",
    allow_synthetic: bool = False,
    metadata: Mapping[str, Any] | None = None,
    registry: TrustBoundaryRegistry | None = None,
) -> AttestationRecord:
    """Build a verified attestation record from one registry boundary declaration."""

    loaded = registry or load_trust_boundary_registry()
    boundary = loaded.require(boundary_id)
    material_map = dict(material_refs or {})
    product_map = dict(product_refs or {})
    expected_materials = _materials_for_kinds(
        boundary.expected_material_kinds,
        refs=material_map,
        fallback_prefix=f"attestation://{boundary_id}/material",
        allow_synthetic=allow_synthetic,
    )
    expected_products = _materials_for_kinds(
        boundary.expected_product_kinds,
        refs=product_map,
        fallback_prefix=f"attestation://{boundary_id}/product",
        allow_synthetic=allow_synthetic,
    )
    merged_metadata = {
        "source": f"runtime.{boundary_id}",
        "type": "trust_boundary_attestation",
        "phase": boundary.boundary_id,
        "blocker_status": "blocking" if boundary.production_closeout_required else "diagnostic",
        "authority_role": "producer_authority",
        **dict(metadata or {}),
    }
    return AttestationRecord(
        attestation_id=attestation_id or f"att-{boundary_id}",
        trust_boundary_id=boundary.boundary_id,
        expected_materials=expected_materials,
        observed_materials=list(expected_materials),
        expected_products=expected_products,
        observed_products=list(expected_products),
        functionary=FunctionaryIdentity(
            functionary_id=functionary_id or f"{boundary.functionary}@{environment_id}",
            role=boundary.functionary,
            service_account=service_account or boundary.functionary,
        ),
        producer_identity=ProducerIdentity(
            component=producer_component or f"polisyos.{boundary.boundary_id}",
            version=producer_version,
            owner=boundary.producer_owner,
        ),
        environment_identity=EnvironmentIdentity(
            environment_id=environment_id,
            execution_profile=execution_profile,
            tenant_id=tenant_id,
            cell_id=cell_id,
            runner_id=runner_id,
        ),
        isolation_status=(
            isolation_status
            if isolation_status is not None
            else ("isolated" if boundary.isolation_required else "shared")
        ),
        service_generated=service_generated,
        consumer_verification=consumer_verification,
        tamper_check_status=tamper_check_status,
        signature_ref=signature_ref or f"signature://{boundary.boundary_id}",
        evidence_ref=(
            evidence_ref
            or f"quality_evidence/attestation_records.json#/{boundary.boundary_id}"
        ),
        metadata=merged_metadata,
    )


def build_required_production_attestations(
    *,
    material_refs: Mapping[str, str] | None = None,
    product_refs: Mapping[str, str] | None = None,
    evidence_refs: Mapping[str, str] | None = None,
    registry: TrustBoundaryRegistry | None = None,
    **record_kwargs: Any,
) -> list[AttestationRecord]:
    """Build verified records for every attested production closeout boundary."""

    loaded = registry or load_trust_boundary_registry()
    records: list[AttestationRecord] = []
    evidence_ref_map = dict(evidence_refs or {})
    for boundary in iter_required_production_attestation_boundaries(loaded):
        records.append(
            build_verified_attestation_record(
                boundary_id=boundary.boundary_id,
                material_refs=material_refs,
                product_refs=product_refs,
                evidence_ref=evidence_ref_map.get(boundary.boundary_id),
                registry=loaded,
                **record_kwargs,
            )
        )
    return records


def load_trust_boundary_registry(
    path: str | Path | None = None,
) -> TrustBoundaryRegistry:
    """Load and validate the production-quality trust-boundary registry."""

    registry_path = Path(path) if path is not None else DEFAULT_TRUST_BOUNDARY_REGISTRY
    with registry_path.open("rb") as stream:
        payload = tomllib.load(stream)
    rows = payload.get("trust_boundaries")
    if not isinstance(rows, list) or not rows:
        raise TrustBoundaryRegistryError("trust_boundaries registry is empty")

    boundaries: dict[str, TrustBoundary] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise TrustBoundaryRegistryError(f"trust_boundaries[{index}] is not a table")
        boundary = TrustBoundary.model_validate(row)
        if boundary.boundary_id in boundaries:
            raise TrustBoundaryRegistryError(
                f"duplicate trust boundary: {boundary.boundary_id}"
            )
        boundaries[boundary.boundary_id] = boundary
    missing = sorted(REQUIRED_TRUST_BOUNDARY_IDS - set(boundaries))
    if missing:
        raise TrustBoundaryRegistryError(
            "missing required trust boundaries: " + ", ".join(missing)
        )
    return TrustBoundaryRegistry(boundaries=boundaries)


def iter_required_production_attestation_boundaries(
    registry: TrustBoundaryRegistry | None = None,
) -> tuple[TrustBoundary, ...]:
    """Return registry rows that are mandatory for production closeout."""

    loaded = registry or load_trust_boundary_registry()
    return tuple(
        boundary
        for boundary in loaded.boundaries.values()
        if boundary.requires_attestation and boundary.production_closeout_required
    )


def evaluate_trust_boundary_attestation(
    *,
    boundary_id: str,
    attestations: Iterable[AttestationRecord | Mapping[str, Any]],
    registry: TrustBoundaryRegistry | None = None,
) -> AttestationRequirementResult:
    """Evaluate whether records satisfy one trust-boundary closeout requirement."""

    loaded = registry or load_trust_boundary_registry()
    boundary = loaded.require(boundary_id)
    if not boundary.requires_attestation:
        return _result(
            boundary,
            status="not_required",
            production_closeout_satisfied=True,
            failure_code="attestation_not_required",
            message=f"Trust boundary {boundary_id} does not require attestation.",
        )

    candidates = [
        record
        for record in _coerce_attestation_records(attestations)
        if record.trust_boundary_id == boundary_id
    ]
    if not candidates:
        satisfied = not boundary.production_closeout_required
        return _result(
            boundary,
            status="missing",
            production_closeout_satisfied=satisfied,
            failure_code=boundary.failure_code,
            message=(
                f"Trust boundary {boundary_id} has no verified attestation. "
                "Evidence remains diagnostic-readable but cannot satisfy production closeout."
            ),
        )

    first_failure: AttestationRequirementResult | None = None
    for record in candidates:
        status = _record_failure_status(record, boundary)
        if status == "verified":
            return _result(
                boundary,
                status="verified",
                production_closeout_satisfied=True,
                failure_code="attestation_verified",
                message=f"Trust boundary {boundary_id} has verified attestation.",
                record=record,
            )
        failure = _result(
            boundary,
            status=status,
            production_closeout_satisfied=False,
            failure_code=_failure_code(status),
            message=(
                f"Trust boundary {boundary_id} attestation failed with status {status}."
            ),
            record=record,
        )
        first_failure = first_failure or failure

    if first_failure is None:
        raise TrustBoundaryRegistryError(f"no attestation evaluation for {boundary_id}")
    return first_failure


def _coerce_attestation_records(
    attestations: Iterable[AttestationRecord | Mapping[str, Any]],
) -> list[AttestationRecord]:
    records: list[AttestationRecord] = []
    for candidate in attestations:
        if isinstance(candidate, AttestationRecord):
            records.append(candidate)
        elif isinstance(candidate, Mapping):
            records.append(deserialize_attestation_record(candidate))
    return records


def _record_failure_status(
    record: AttestationRecord,
    boundary: TrustBoundary,
) -> AttestationStatus:
    if record.consumer_verification != "verified":
        return "consumer_verification_failed"
    if record.tamper_check_status != "pass":
        return "tamper_check_failed"
    if boundary.production_closeout_required and record.evidence_ref is None:
        return "evidence_ref_missing"
    if boundary.production_closeout_required and record.signature_ref is None:
        return "signature_ref_missing"
    if _contains_synthetic_attestation_refs(record):
        return "synthetic_material_ref"
    if boundary.isolation_required and record.isolation_status != "isolated":
        return "isolation_failed"
    if boundary.service_generated_required and not record.service_generated:
        return "service_generation_failed"
    if record.functionary.role != boundary.functionary:
        return "functionary_mismatch"
    if record.producer_identity.owner != boundary.producer_owner:
        return "producer_identity_mismatch"
    if not _observed_materials_match(
        expected=record.expected_materials,
        observed=record.observed_materials,
    ):
        return "material_mismatch"
    if not _observed_materials_match(
        expected=record.expected_products,
        observed=record.observed_products,
    ):
        return "product_mismatch"
    return "verified"


def _observed_materials_match(
    *,
    expected: list[AttestedMaterial],
    observed: list[AttestedMaterial],
) -> bool:
    observed_by_key = {material.key: material for material in observed}
    for material in expected:
        observed_material = observed_by_key.get(material.key)
        if observed_material is None:
            return False
        if observed_material.ref != material.ref:
            return False
        if material.sha256 is not None and observed_material.sha256 != material.sha256:
            return False
    return True


def _contains_synthetic_attestation_refs(record: AttestationRecord) -> bool:
    materials = [
        *record.expected_materials,
        *record.observed_materials,
        *record.expected_products,
        *record.observed_products,
    ]
    return any(material.ref.startswith("attestation://") for material in materials)


def _materials_for_kinds(
    kinds: Iterable[str],
    *,
    refs: Mapping[str, str],
    fallback_prefix: str,
    allow_synthetic: bool,
) -> list[AttestedMaterial]:
    materials: list[AttestedMaterial] = []
    for kind in kinds:
        ref = refs.get(kind) or refs.get(f"{kind}_ref")
        if ref is None:
            ref = f"{fallback_prefix}/{kind}"
        materials.append(AttestedMaterial(key=kind, ref=ref))
    return materials


def _result(
    boundary: TrustBoundary,
    *,
    status: AttestationStatus,
    production_closeout_satisfied: bool,
    failure_code: str,
    message: str,
    record: AttestationRecord | None = None,
) -> AttestationRequirementResult:
    return AttestationRequirementResult(
        boundary=boundary,
        status=status,
        diagnostic_readable=boundary.diagnostic_readable_without_attestation
        or status == "verified",
        production_closeout_satisfied=production_closeout_satisfied,
        failure_code=failure_code,
        message=message,
        next_action=None if production_closeout_satisfied else boundary.next_action,
        attestation_id=record.attestation_id if record is not None else None,
        attestation_ref=record.evidence_ref if record is not None else None,
    )


def _failure_code(status: AttestationStatus) -> str:
    return {
        "consumer_verification_failed": "attestation_consumer_verification_failed",
        "tamper_check_failed": "attestation_tamper_check_failed",
        "isolation_failed": "attestation_isolation_failed",
        "service_generation_failed": "attestation_service_generation_failed",
        "functionary_mismatch": "attestation_functionary_mismatch",
        "producer_identity_mismatch": "attestation_producer_identity_mismatch",
        "evidence_ref_missing": "attestation_evidence_ref_missing",
        "signature_ref_missing": "attestation_signature_ref_missing",
        "synthetic_material_ref": "attestation_synthetic_material_ref",
        "material_mismatch": "attestation_material_mismatch",
        "product_mismatch": "attestation_product_mismatch",
    }.get(status, "attestation_failed")


__all__ = [
    "ATTESTATION_SCHEMA_VERSION",
    "REQUIRED_TRUST_BOUNDARY_IDS",
    "AttestationError",
    "AttestationRecord",
    "AttestationRequirementResult",
    "AttestationViolation",
    "AttestedMaterial",
    "EnvironmentIdentity",
    "FunctionaryIdentity",
    "ProducerIdentity",
    "TrustBoundary",
    "TrustBoundaryRegistry",
    "TrustBoundaryRegistryError",
    "build_attestation_record",
    "build_required_production_attestations",
    "build_verified_attestation_record",
    "deserialize_attestation_record",
    "evaluate_trust_boundary_attestation",
    "iter_required_production_attestation_boundaries",
    "load_trust_boundary_registry",
    "serialize_attestation_record",
]
