"""Candidate-only source inventory for Ukraine demographic materializations.

This module binds one declared role mapping to outputs of an existing, verified
Ukraine stage. It does not establish source ownership, semantic truth, or
currentness. The inventory is a candidate artifact until an independent
source-owner verifier is wired.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError, model_validator

from polisyos.core import artifacts as core_artifacts
from polisyos.data_forge.domains.ukraine.manifests import ArtifactRecord, BuildRunManifest
from polisyos.data_forge.domains.ukraine.models import StageId
from polisyos.data_forge.kernel.io.generation_basis import (
    GenerationBasis,
    build_generation_basis,
    compare_generation_basis,
)
from polisyos.data_forge.read_api.ukraine import (
    UkraineJSONSnapshotProvenance,
    UkraineJSONSnapshotRefusalError,
    VerifiedUkraineStageArtifact,
    VerifiedUkraineStageArtifacts,
    load_verified_stage_artifacts,
    load_verified_stage_json_output,
    load_verified_stage_manifest_json,
    load_verified_stage_output_bytes,
    read_ukraine_json_snapshot,
)

SOURCE_INVENTORY_STAGE_ID = "demography_source_inventory"
SOURCE_INVENTORY_PRODUCER_ID = (
    "polisyos.data_forge.domains.ukraine.demography.source_inventory.v2"
)
SOURCE_INVENTORY_SCHEMA = "policyos.ukraine.demography.source_inventory.v2"
SOURCE_INVENTORY_RULE = "ukraine-demography-source-inventory.v2"
SOURCE_INVENTORY_BASIS_KIND = "ukraine_demography_source_inventory"
_REQUIRED_ROLES = ("targets", "priors")
_SOURCE_FACT_KEYS = frozenset(
    {
        "source_owner_id",
        "source_object_id",
        "source_version",
        "source_profile",
        "observed_at",
        "state_domain",
        "state_mapping",
        "state_refinement",
        "ordered_state_ids",
        "target_measure",
        "target_unit",
        "target_period",
        "target_mapping",
        "entrant_measure",
        "entrant_unit",
        "entrant_period",
        "entrant_mapping",
        "prior_origin_axis",
        "prior_destination_axis",
        "prior_derivation",
        "prior_unit",
        "prior_period",
        "prior_mapping",
        "donor_absence_reason",
    }
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
type FactProvenance = Literal["consumer_asserted", "not_established"]


class StrictFrozenModel(BaseModel):
    """Strict immutable model for the candidate-only inventory boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SourceFact(StrictFrozenModel):
    """One explicit source fact claim; absence is represented as not_established."""

    value: StrictStr | list[StrictStr] | None
    provenance: FactProvenance

    @model_validator(mode="after")
    def _require_explicit_fact_provenance(self) -> SourceFact:
        if self.value is None and self.provenance != "not_established":
            raise ValueError("a missing source fact must be not_established")
        if self.value is not None and self.provenance != "consumer_asserted":
            raise ValueError("caller-supplied facts cannot claim independent provenance")
        if isinstance(self.value, list) and not self.value:
            raise ValueError("a supplied ordered source fact cannot be empty")
        return self


class SourceSemanticClaims(StrictFrozenModel):
    """Full named semantic-fact denominator supplied as claims, never authority."""

    facts: dict[StrictStr, SourceFact]
    donor_disposition: Literal["present", "intentionally_absent", "not_established"]

    @model_validator(mode="after")
    def _require_complete_fact_denominator(self) -> SourceSemanticClaims:
        if set(self.facts) != _SOURCE_FACT_KEYS:
            missing = sorted(_SOURCE_FACT_KEYS.difference(self.facts))
            extra = sorted(set(self.facts).difference(_SOURCE_FACT_KEYS))
            raise ValueError(f"source fact denominator mismatch: missing={missing}, extra={extra}")
        sequence_facts = {
            "ordered_state_ids",
            "prior_origin_axis",
            "prior_destination_axis",
        }
        for name, fact in self.facts.items():
            if fact.value is None:
                continue
            if name in sequence_facts and not isinstance(fact.value, list):
                raise ValueError(f"{name} must be a list when supplied")
            if name not in sequence_facts and not isinstance(fact.value, str):
                raise ValueError(f"{name} must be a string when supplied")
        ordered_state_ids = self.facts["ordered_state_ids"].value
        if isinstance(ordered_state_ids, list) and len(ordered_state_ids) != len(
            set(ordered_state_ids)
        ):
            raise ValueError("ordered_state_ids must be unique")
        absence_reason = self.facts["donor_absence_reason"]
        if self.donor_disposition == "intentionally_absent":
            if (
                absence_reason.value is None
                or absence_reason.provenance != "consumer_asserted"
                or not isinstance(absence_reason.value, str)
                or not absence_reason.value.strip()
            ):
                raise ValueError("intentional donor absence requires a supplied reason claim")
        elif absence_reason.value is not None:
            raise ValueError("donor absence reason is only valid for intentional absence")
        return self


class InventoryBuildRequest(StrictFrozenModel):
    """Explicit recipe input for one candidate inventory producer run."""

    upstream_manifest_path: Path
    upstream_allowed_root: Path
    upstream_expected_stage: StrictStr
    role_outputs: dict[StrictStr, StrictStr]
    source_claims: SourceSemanticClaims

    @model_validator(mode="after")
    def _validate_recipe(self) -> InventoryBuildRequest:
        if self.upstream_expected_stage not in {item.value for item in StageId}:
            raise ValueError("upstream_expected_stage must name a known Ukraine stage")
        expected = set(_REQUIRED_ROLES)
        if self.source_claims.donor_disposition == "present":
            expected.add("donor")
        if set(self.role_outputs) != expected:
            raise ValueError("role_outputs must exactly match required roles and donor disposition")
        names = list(self.role_outputs.values())
        if len(names) != len(set(names)):
            raise ValueError("source output names must be unique")
        if any(Path(name).name != name or name in {".", ".."} for name in names):
            raise ValueError("source output names must be single basenames")
        return self


class GenerationBasisMemberDTO(StrictFrozenModel):
    """Strict parse shape for the existing Data Forge GenerationBasis member."""

    identifier: StrictStr = Field(min_length=1)
    content_identity: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class GenerationBasisDTO(StrictFrozenModel):
    """Strict parse shape for the existing generation-basis contract."""

    schema_version: Literal["policyos.generation_basis.v1"]
    basis_kind: StrictStr = Field(min_length=1)
    generator_rule_version: StrictStr = Field(min_length=1)
    members: list[GenerationBasisMemberDTO] = Field(min_length=1)
    basis_digest: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class SourceInventoryMember(StrictFrozenModel):
    """One canonical demographic role backed by a verified stage output."""

    role: Literal["targets", "priors", "donor"]
    path: StrictStr
    source_output_name: StrictStr
    sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    content_ref: core_artifacts.ArtifactRef

    @model_validator(mode="after")
    def _canonical_role_path(self) -> SourceInventoryMember:
        if self.path != f"{self.role}.json":
            raise ValueError("inventory member paths must be canonical role basenames")
        if Path(self.source_output_name).name != self.source_output_name:
            raise ValueError("source_output_name must be a basename")
        if self.content_ref.artifact_id.hex != self.sha256:
            raise ValueError("member content ref must match its verified SHA-256")
        return self


class DemographyInventoryEnvelope(StrictFrozenModel):
    """Content-bound inventory whose semantics remain candidate-only."""

    inventory_id: StrictStr = Field(pattern=r"^[0-9a-f]{24}$")
    producer_identity: Literal[SOURCE_INVENTORY_PRODUCER_ID]
    schema_version: Literal[SOURCE_INVENTORY_SCHEMA]
    verification_rule_version: Literal[SOURCE_INVENTORY_RULE]
    evidence_band: Literal["candidate_only"]
    source_materialization: Literal["verified_stage_outputs"]
    source_stage_receipt: VerifiedUkraineStageArtifacts
    role_outputs: dict[StrictStr, StrictStr]
    source_claims: SourceSemanticClaims
    donor_disposition: Literal["present", "intentionally_absent", "not_established"]
    required_roles: list[Literal["targets", "priors"]]
    members: list[SourceInventoryMember]
    semantic_basis: GenerationBasisDTO
    source_authority_provenance: Literal["not_established"]
    source_currentness_provenance: Literal["not_established"]
    semantic_completeness_provenance: Literal["not_established"]

    @model_validator(mode="after")
    def _validate_complete_membership(self) -> DemographyInventoryEnvelope:
        if self.source_stage_receipt.stage_id == SOURCE_INVENTORY_STAGE_ID:
            raise ValueError("inventory cannot use itself as its upstream producer")
        if self.source_stage_receipt.status != "completed":
            raise ValueError("upstream stage receipt must be completed")
        if self.required_roles != list(_REQUIRED_ROLES):
            raise ValueError("required roles are fixed to targets and priors")
        expected = set(_REQUIRED_ROLES)
        if self.donor_disposition == "present":
            expected.add("donor")
        if self.donor_disposition != self.source_claims.donor_disposition:
            raise ValueError("donor disposition differs from the explicit source claim")
        if set(self.role_outputs) != expected:
            raise ValueError(
                "role output mapping differs from required roles and donor disposition"
            )
        members_by_role = {member.role: member for member in self.members}
        if len(members_by_role) != len(self.members) or set(members_by_role) != expected:
            raise ValueError("inventory member roles must exactly match the declared disposition")
        if set(self.source_stage_receipt.outputs) != set(self.role_outputs.values()):
            raise ValueError("source receipt must contain exactly the selected role outputs")
        for role, source_name in self.role_outputs.items():
            member = members_by_role[role]
            source_output = self.source_stage_receipt.outputs[source_name]
            if (
                member.source_output_name != source_name
                or member.sha256 != source_output.sha256
                or member.size_bytes != source_output.size_bytes
                or member.content_ref != source_output.content_ref
            ):
                raise ValueError("member declaration differs from its verified stage output")
        if self.semantic_basis.schema_version != "policyos.generation_basis.v1":
            raise ValueError("semantic basis schema is not supported")
        if self.source_authority_provenance != "not_established":
            raise ValueError("candidate inventory cannot claim source authority")
        if self.source_currentness_provenance != "not_established":
            raise ValueError("candidate inventory cannot claim source currentness")
        if self.semantic_completeness_provenance != "not_established":
            raise ValueError("candidate inventory cannot claim semantic completeness")
        return self


class DemographySourceEvidence(StrictFrozenModel):
    """P37 source evidence carried through Data Forge and Foundry diagnostics."""

    source_status: Literal["candidate_only", "legacy_limited"]
    source_identity: StrictStr = Field(min_length=1)
    source_layout: Literal["new", "legacy"] | None
    source_producer_identity: StrictStr | None
    source_stage_id: StrictStr | None
    source_run_id: StrictStr | None
    source_authority_provenance: Literal["not_established"]
    source_fact_provenance: FactProvenance
    source_currentness_provenance: Literal["not_established"]
    member_content_binding_provenance: Literal["recomputed", "not_established"]
    declared_basis_binding_provenance: Literal["recomputed", "not_established"]
    semantic_completeness_provenance: Literal["not_established"]
    donor_disposition: Literal["present", "intentionally_absent", "not_established"]
    compatibility_notes: list[StrictStr]
    source_claims: SourceSemanticClaims | None
    json_snapshot_profile_reads: list[UkraineJSONSnapshotProvenance] = Field(default_factory=list)


class InventorySourceRequest(StrictFrozenModel):
    """Read an inventory output only through the existing verified-stage/CAS path."""

    kind: Literal["inventory"]
    stage_receipt: VerifiedUkraineStageArtifacts
    store: core_artifacts.FileSystemCAS

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        arbitrary_types_allowed=True,
    )


class HistoricalLayoutRequest(StrictFrozenModel):
    """Explicit bounded adapter for the supported new and flat historical layouts."""

    kind: Literal["historical_layout"]
    root: Path
    layout: Literal["new", "legacy"] | None


DemographySourceRequest = Annotated[
    InventorySourceRequest | HistoricalLayoutRequest,
    Field(discriminator="kind"),
]


class SourceResolutionRefusalError(ValueError):
    """Typed refusal that remains catchable as a historical reader ValueError."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ResolvedDemographySource:
    """One immutable source snapshot and the status that limits its use."""

    status: Literal["candidate_only", "legacy_limited"]
    source_identity: str
    member_bytes: dict[str, bytes]
    member_json_values: dict[str, dict[str, Any]]
    evidence: DemographySourceEvidence
    donor_disposition: Literal["present", "intentionally_absent", "not_established"]


@dataclass(frozen=True, eq=False)
class DemographyRoleProjection(Mapping[str, object]):
    """Mapping view whose equality follows payload values; evidence stays attached."""

    role: Literal["targets", "priors", "donor"]
    payload: dict[str, object]
    evidence: DemographySourceEvidence

    def __getitem__(self, key: str) -> object:
        return self.payload[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.payload)

    def __len__(self) -> int:
        return len(self.payload)

    def __eq__(self, other: object) -> bool:
        """Compare the public mapping view by its keys and values."""
        if not isinstance(other, Mapping):
            return False
        return self.payload == dict(other.items())

    __hash__ = None


class InventoryBuildRequestProtocol(Protocol):
    """Minimal structural contract for explicitly supplied producer requests."""

    upstream_manifest_path: Path
    upstream_allowed_root: Path
    upstream_expected_stage: str
    role_outputs: Mapping[str, str]
    source_claims: SourceSemanticClaims


@dataclass(frozen=True)
class ProducedCandidateInventory:
    """Candidate envelope plus exact verified producer outputs recorded as stage inputs."""

    envelope: DemographyInventoryEnvelope
    stage_inputs: tuple[ArtifactRecord, ...]


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _artifact_record_set(
    records: list[ArtifactRecord],
    *,
    refusal_code: str,
) -> tuple[bytes, ...]:
    """Return a full-record set key after rejecting duplicate declared paths."""
    paths = [str(Path(record.path).resolve()) for record in records]
    if len(paths) != len(set(paths)):
        raise SourceResolutionRefusalError(refusal_code, "artifact record paths are duplicated")
    return tuple(
        sorted(_canonical_json(record.model_dump(mode="json")) for record in records)
    )


def _selected_upstream_receipt(
    request: InventoryBuildRequestProtocol,
    *,
    store: core_artifacts.FileSystemCAS,
) -> tuple[
    VerifiedUkraineStageArtifacts,
    dict[str, bytes],
    bytes,
    tuple[ArtifactRecord, ...],
]:
    try:
        receipt = load_verified_stage_artifacts(
            request.upstream_manifest_path,
            store=store,
            allowed_root=request.upstream_allowed_root,
            expected_stage=request.upstream_expected_stage,
            required_outputs=tuple(request.role_outputs.values()),
        )
    except Exception as exc:
        raise SourceResolutionRefusalError("upstream_stage_unverified", str(exc)) from exc
    try:
        source_manifest_read = load_verified_stage_manifest_json(
            store,
            receipt,
            model_type=BuildRunManifest,
            consumer_contract="demography_inventory.upstream_manifest_generation_basis",
        )
        source_manifest_bytes = source_manifest_read.raw_payload_bytes
        source_manifest = source_manifest_read.value_for_candidate()
    except Exception as exc:
        code = getattr(exc, "code", "upstream_manifest_profile_or_content_invalid")
        raise SourceResolutionRefusalError(str(code), str(exc)) from exc
    if (
        source_manifest.stage_id.value != receipt.stage_id
        or source_manifest.run_id != receipt.run_id
        or source_manifest.status != "completed"
    ):
        raise SourceResolutionRefusalError(
            "upstream_manifest_identity_mismatch", "verified receipt differs from manifest"
        )
    selected_outputs: dict[str, VerifiedUkraineStageArtifact] = {}
    member_bytes: dict[str, bytes] = {}
    selected_input_records: dict[str, ArtifactRecord] = {}
    for role, output_name in sorted(request.role_outputs.items()):
        output = receipt.outputs.get(output_name)
        if output is None:
            raise SourceResolutionRefusalError("upstream_output_missing", output_name)
        records = [
            item for item in source_manifest.outputs if Path(item.path).name == output_name
        ]
        if len(records) != 1:
            raise SourceResolutionRefusalError(
                "upstream_output_record_ambiguous", output_name
            )
        record = records[0]
        if (
            record.sha256 != output.sha256
            or record.size_bytes != output.size_bytes
            or record.row_count != output.row_count
            or record.nnz != output.nnz
            or record.artifact_id != output.producer_artifact_id
        ):
            raise SourceResolutionRefusalError(
                "upstream_output_record_mismatch", output_name
            )
        try:
            raw = load_verified_stage_output_bytes(store, receipt, output_name)
        except Exception as exc:
            raise SourceResolutionRefusalError("upstream_output_unreadable", output_name) from exc
        member_bytes[role] = raw
        selected_outputs[output_name] = output
        selected_input_records[output_name] = record
    selected_receipt = VerifiedUkraineStageArtifacts(
        stage_id=receipt.stage_id,
        run_id=receipt.run_id,
        finished_at=receipt.finished_at,
        manifest_source_path=receipt.manifest_source_path,
        manifest_ref=receipt.manifest_ref,
        manifest_sha256=receipt.manifest_sha256,
        outputs=selected_outputs,
    )
    return (
        selected_receipt,
        member_bytes,
        source_manifest_bytes,
        tuple(selected_input_records[name] for name in sorted(selected_input_records)),
    )


def _basis_for(
    *,
    claims: SourceSemanticClaims,
    receipt: VerifiedUkraineStageArtifacts,
    role_outputs: Mapping[str, str],
    member_bytes: Mapping[str, bytes],
    source_manifest_bytes: bytes,
) -> GenerationBasis:
    claims_bytes = _canonical_json(claims.model_dump(mode="json"))
    role_map_bytes = _canonical_json(
        {
            "source_stage_id": receipt.stage_id,
            "source_run_id": receipt.run_id,
            "role_outputs": dict(sorted(role_outputs.items())),
        }
    )
    inputs: list[tuple[str, bytes]] = [
        ("source-claims.json", claims_bytes),
        ("source-manifest.json", source_manifest_bytes),
        ("source-role-map.json", role_map_bytes),
    ]
    inputs.extend(
        (f"member:{role}", raw) for role, raw in sorted(member_bytes.items())
    )
    return build_generation_basis(
        basis_kind=SOURCE_INVENTORY_BASIS_KIND,
        generator_rule_version=SOURCE_INVENTORY_RULE,
        members=inputs,
    )


def produce_candidate_inventory(
    request: InventoryBuildRequestProtocol,
    *,
    store: core_artifacts.FileSystemCAS,
) -> ProducedCandidateInventory:
    """Produce one candidate inventory from verified producer-materialized outputs.

    This function inventories existing outputs; it does not transform raw data,
    certify the source owner, or promote source claims to authority.
    """
    receipt, member_bytes, source_manifest_bytes, stage_inputs = _selected_upstream_receipt(
        request, store=store
    )
    role_outputs = dict(request.role_outputs)
    members = [
        SourceInventoryMember(
            role=cast("Literal['targets', 'priors', 'donor']", role),
            path=f"{role}.json",
            source_output_name=output_name,
            sha256=receipt.outputs[output_name].sha256,
            size_bytes=receipt.outputs[output_name].size_bytes,
            content_ref=receipt.outputs[output_name].content_ref,
        )
        for role, output_name in sorted(role_outputs.items())
    ]
    basis = _basis_for(
        claims=request.source_claims,
        receipt=receipt,
        role_outputs=role_outputs,
        member_bytes=member_bytes,
        source_manifest_bytes=source_manifest_bytes,
    )
    identity_seed = _canonical_json(
        {
            "producer": SOURCE_INVENTORY_PRODUCER_ID,
            "upstream_manifest_sha256": receipt.manifest_sha256,
            "role_outputs": dict(sorted(role_outputs.items())),
            "source_claims": request.source_claims.model_dump(mode="json"),
            "semantic_basis": basis.basis_digest,
        }
    )
    inventory_id = _sha256(identity_seed)[:24]
    envelope = DemographyInventoryEnvelope(
        inventory_id=inventory_id,
        producer_identity=SOURCE_INVENTORY_PRODUCER_ID,
        schema_version=SOURCE_INVENTORY_SCHEMA,
        verification_rule_version=SOURCE_INVENTORY_RULE,
        evidence_band="candidate_only",
        source_materialization="verified_stage_outputs",
        source_stage_receipt=receipt,
        role_outputs=role_outputs,
        source_claims=request.source_claims,
        donor_disposition=request.source_claims.donor_disposition,
        required_roles=list(_REQUIRED_ROLES),
        members=members,
        semantic_basis=GenerationBasisDTO.model_validate(basis.to_dict()),
        source_authority_provenance="not_established",
        source_currentness_provenance="not_established",
        semantic_completeness_provenance="not_established",
    )
    return ProducedCandidateInventory(envelope=envelope, stage_inputs=stage_inputs)


def _source_manifest_from_receipt(
    receipt: VerifiedUkraineStageArtifacts,
    *,
    store: core_artifacts.FileSystemCAS,
) -> tuple[BuildRunManifest, bytes, UkraineJSONSnapshotProvenance]:
    try:
        raw = store.get_bytes(receipt.manifest_ref)
    except Exception as exc:
        raise SourceResolutionRefusalError("upstream_manifest_unreadable", str(exc)) from exc
    if _sha256(raw) != receipt.manifest_sha256:
        raise SourceResolutionRefusalError(
            "upstream_manifest_hash_mismatch", "manifest bytes differ"
        )
    try:
        manifest_read = read_ukraine_json_snapshot(
            store,
            receipt.manifest_ref,
            raw_payload_bytes=raw,
            expected_sha256=receipt.manifest_sha256,
            expected_size_bytes=len(raw),
            expected_kind="data_forge.ukraine.stage_manifest_snapshot",
            expected_schema=("polisyos.data_forge.ukraine.BuildRunManifest", "1.0"),
            consumer_contract="demography_inventory.source_manifest",
            model_type=BuildRunManifest,
        )
        manifest = manifest_read.value_for_candidate()
    except Exception as exc:
        raise SourceResolutionRefusalError("upstream_manifest_malformed", str(exc)) from exc
    if (
        manifest.stage_id.value != receipt.stage_id
        or manifest.run_id != receipt.run_id
        or manifest.status != "completed"
    ):
        raise SourceResolutionRefusalError(
            "upstream_manifest_identity_mismatch", "verified receipt differs from manifest"
        )
    return manifest, raw, manifest_read.provenance


def _check_claimed_cross_member_consistency(
    envelope: DemographyInventoryEnvelope,
    member_json_values: Mapping[str, dict[str, Any]],
) -> None:
    """Recompute only explicit cross-member equalities; do not infer source truth."""
    targets = member_json_values["targets"]
    priors = member_json_values["priors"]
    ordered_states = envelope.source_claims.facts["ordered_state_ids"].value
    target_state_ids = targets.get("state_ids")
    if (
        isinstance(ordered_states, list)
        and target_state_ids is not None
        and target_state_ids != ordered_states
    ):
            raise SourceResolutionRefusalError(
                "declared_state_order_mismatch",
                "target state order differs from the explicit claim",
            )
    prior_matrix = priors.get("transition_prior_matrix")
    if isinstance(prior_matrix, list):
        for fact_name, axis in (
            ("prior_origin_axis", 0),
            ("prior_destination_axis", 1),
        ):
            declared_axis = envelope.source_claims.facts[fact_name].value
            if isinstance(declared_axis, list):
                expected_length = len(prior_matrix) if axis == 0 else (
                    len(prior_matrix[0]) if prior_matrix else 0
                )
                if len(declared_axis) != expected_length:
                    raise SourceResolutionRefusalError(
                        "declared_prior_axis_shape_mismatch",
                        f"{fact_name} length differs from the materialized matrix",
                    )
                if (
                    axis == 1
                    and isinstance(target_state_ids, list)
                    and declared_axis != target_state_ids
                ):
                        raise SourceResolutionRefusalError(
                            "declared_prior_destination_order_mismatch",
                            "prior destination axis differs from target state order",
                        )


def _resolve_inventory(request: InventorySourceRequest) -> ResolvedDemographySource:
    """Recompute stage membership and basis; never establish source semantics."""
    receipt = request.stage_receipt
    if receipt.stage_id != SOURCE_INVENTORY_STAGE_ID:
        raise SourceResolutionRefusalError(
            "wrong_inventory_stage", "verified receipt is not the inventory producer stage"
        )
    if set(receipt.outputs) != {"inventory.json"}:
        raise SourceResolutionRefusalError(
            "inventory_stage_outputs_unexpected", "inventory stage must expose inventory.json only"
        )
    (
        inventory_manifest,
        _inventory_manifest_bytes,
        inventory_manifest_read,
    ) = _source_manifest_from_receipt(receipt, store=request.store)
    json_snapshot_profile_reads = [inventory_manifest_read]
    inventory_record = [
        item for item in inventory_manifest.outputs if Path(item.path).name == "inventory.json"
    ]
    inventory_output = receipt.outputs["inventory.json"]
    if (
        len(inventory_record) != 1
        or inventory_record[0].sha256 != inventory_output.sha256
        or inventory_record[0].size_bytes != inventory_output.size_bytes
        or inventory_record[0].artifact_id != inventory_output.producer_artifact_id
    ):
        raise SourceResolutionRefusalError(
            "inventory_manifest_record_mismatch", "inventory output differs from its stage manifest"
        )
    try:
        inventory_read = load_verified_stage_json_output(
            request.store,
            receipt,
            "inventory.json",
            model_type=DemographyInventoryEnvelope,
            consumer_contract="demography_inventory.candidate_envelope",
        )
        envelope = inventory_read.value_for_candidate()
        inventory_bytes = inventory_read.raw_payload_bytes
        json_snapshot_profile_reads.append(inventory_read.provenance)
    except Exception as exc:
        malformed_model = isinstance(exc, ValidationError) or (
            isinstance(exc, UkraineJSONSnapshotRefusalError)
            and isinstance(exc.__cause__, ValidationError)
        )
        code = (
            "inventory_malformed"
            if malformed_model
            else "inventory_profile_or_payload_refused"
        )
        raise SourceResolutionRefusalError(code, str(exc)) from exc
    source_manifest, source_manifest_bytes, source_manifest_read = _source_manifest_from_receipt(
        envelope.source_stage_receipt, store=request.store
    )
    json_snapshot_profile_reads.append(source_manifest_read)
    member_bytes: dict[str, bytes] = {}
    member_json_values: dict[str, dict[str, Any]] = {}
    expected_stage_inputs: list[ArtifactRecord] = []
    for member in envelope.members:
        output_name = member.source_output_name
        output = envelope.source_stage_receipt.outputs.get(output_name)
        if output is None:
            raise SourceResolutionRefusalError("source_member_receipt_missing", output_name)
        records = [
            item for item in source_manifest.outputs if Path(item.path).name == output_name
        ]
        if len(records) != 1:
            raise SourceResolutionRefusalError(
                "source_member_manifest_record_ambiguous", output_name
            )
        record = records[0]
        if (
            record.sha256 != output.sha256
            or record.size_bytes != output.size_bytes
            or record.row_count != output.row_count
            or record.nnz != output.nnz
            or record.artifact_id != output.producer_artifact_id
            or member.sha256 != output.sha256
            or member.size_bytes != output.size_bytes
        ):
            raise SourceResolutionRefusalError(
                "source_member_manifest_record_mismatch", output_name
            )
        expected_stage_inputs.append(record)
        try:
            member_read = load_verified_stage_json_output(
                request.store,
                envelope.source_stage_receipt,
                output_name,
                model_type=dict[str, Any],
                consumer_contract=f"demography_inventory.source_member.{member.role}",
            )
            raw = member_read.raw_payload_bytes
            member_json_values[member.role] = member_read.value_for_candidate()
            json_snapshot_profile_reads.append(member_read.provenance)
        except Exception as exc:
            raise SourceResolutionRefusalError(
                "source_member_profile_or_payload_refused", output_name
            ) from exc
        if _sha256(raw) != member.sha256 or len(raw) != member.size_bytes:
            raise SourceResolutionRefusalError("source_member_content_mismatch", output_name)
        member_bytes[member.role] = raw
    actual_input_set = _artifact_record_set(
        inventory_manifest.inputs,
        refusal_code="inventory_stage_input_membership_invalid",
    )
    expected_input_set = _artifact_record_set(
        expected_stage_inputs,
        refusal_code="source_stage_input_membership_invalid",
    )
    if actual_input_set != expected_input_set:
        raise SourceResolutionRefusalError(
            "inventory_stage_input_membership_mismatch",
            "candidate stage inputs differ from all selected producer outputs",
        )
    _check_claimed_cross_member_consistency(envelope, member_json_values)
    current_basis = _basis_for(
        claims=envelope.source_claims,
        receipt=envelope.source_stage_receipt,
        role_outputs=envelope.role_outputs,
        member_bytes=member_bytes,
        source_manifest_bytes=source_manifest_bytes,
    )
    comparison = compare_generation_basis(
        envelope.semantic_basis.model_dump(mode="json"),
        current=current_basis,
    )
    if not comparison.is_current:
        raise SourceResolutionRefusalError(
            "semantic_basis_mismatch", f"declared basis is {comparison.status}"
        )
    fact_provenances = {fact.provenance for fact in envelope.source_claims.facts.values()}
    fact_provenance: FactProvenance = (
        "consumer_asserted" if "consumer_asserted" in fact_provenances else "not_established"
    )
    evidence = DemographySourceEvidence(
        source_status="candidate_only",
        source_identity=f"sha256:{_sha256(inventory_bytes)}",
        source_layout=None,
        source_producer_identity=envelope.producer_identity,
        source_stage_id=envelope.source_stage_receipt.stage_id,
        source_run_id=envelope.source_stage_receipt.run_id,
        source_authority_provenance="not_established",
        source_fact_provenance=fact_provenance,
        source_currentness_provenance="not_established",
        member_content_binding_provenance="recomputed",
        declared_basis_binding_provenance="recomputed",
        semantic_completeness_provenance="not_established",
        donor_disposition=envelope.donor_disposition,
        compatibility_notes=[],
        source_claims=envelope.source_claims,
        json_snapshot_profile_reads=json_snapshot_profile_reads,
    )
    return ResolvedDemographySource(
        status="candidate_only",
        source_identity=evidence.source_identity,
        member_bytes={f"{role}.json": raw for role, raw in member_bytes.items()},
        member_json_values=member_json_values,
        evidence=evidence,
        donor_disposition=envelope.donor_disposition,
    )


def _read_json_object(
    raw: bytes,
    *,
    role: str,
    typed_errors: bool = True,
) -> dict[str, Any]:
    """Decode one member while retaining the selected boundary error contract."""
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        if not typed_errors:
            raise
        raise SourceResolutionRefusalError("member_json_malformed", role) from exc
    if not isinstance(payload, dict):
        if not typed_errors:
            raise ValueError(f"demography {role} must be a JSON object")
        raise SourceResolutionRefusalError("member_json_not_object", role)
    return cast("dict[str, Any]", payload)


def _resolve_historical_layout(
    request: HistoricalLayoutRequest,
    *,
    standalone_member: str | None,
) -> ResolvedDemographySource:
    from . import _select_demography_layout

    selected, paths = _select_demography_layout(
        request.root,
        request.layout,
        standalone_member=standalone_member,
    )
    member_bytes: dict[str, bytes] = {}
    compatibility_notes = [
        "historical filesystem adapter; source owner, producer receipt, "
        "and currentness are not established"
    ]
    for role, path in paths.items():
        if path.is_file():
            member_bytes[f"{role}.json"] = path.read_bytes()
    if selected is None:
        compatibility_notes.append(
            "no declared historical members are present; a standalone optional donor "
            "projects as empty while absence intent remains not established"
        )
    elif "donor.json" not in member_bytes:
        compatibility_notes.append(
            "optional donor is absent in this historical layout; intent is not established"
        )
    identity_bytes = _canonical_json(
        {
            "layout": selected,
            "members": {
                name: _sha256(raw) for name, raw in sorted(member_bytes.items())
            },
        }
    )
    evidence = DemographySourceEvidence(
        source_status="legacy_limited",
        source_identity=f"legacy:{_sha256(identity_bytes)}",
        source_layout=selected,
        source_producer_identity=None,
        source_stage_id=None,
        source_run_id=None,
        source_authority_provenance="not_established",
        source_fact_provenance="not_established",
        source_currentness_provenance="not_established",
        member_content_binding_provenance="not_established",
        declared_basis_binding_provenance="not_established",
        semantic_completeness_provenance="not_established",
        donor_disposition="present" if "donor.json" in member_bytes else "not_established",
        compatibility_notes=compatibility_notes,
        source_claims=None,
        json_snapshot_profile_reads=[],
    )
    return ResolvedDemographySource(
        status="legacy_limited",
        source_identity=evidence.source_identity,
        member_bytes=member_bytes,
        member_json_values={},
        evidence=evidence,
        donor_disposition=evidence.donor_disposition,
    )


def resolve_demography_source(
    request: DemographySourceRequest,
    *,
    standalone_member: str | None = None,
) -> ResolvedDemographySource:
    """Resolve inventory or historical input through one non-fallback gate."""
    if isinstance(request, InventorySourceRequest):
        if standalone_member is not None:
            raise SourceResolutionRefusalError(
                "inventory_requires_complete_snapshot", "scalar member bypass is unavailable"
            )
        return _resolve_inventory(request)
    if isinstance(request, HistoricalLayoutRequest):
        return _resolve_historical_layout(request, standalone_member=standalone_member)
    raise SourceResolutionRefusalError("source_request_unknown", "unsupported source request")


def read_demography_role(
    resolved: ResolvedDemographySource,
    role: Literal["targets", "priors", "donor"],
) -> DemographyRoleProjection:
    """Read one member from the resolved inventory or limited historical adapter."""
    raw = resolved.member_bytes.get(f"{role}.json")
    if raw is None:
        if role == "donor" and resolved.status == "legacy_limited":
            payload: dict[str, Any] = {}
        elif role == "donor" and resolved.donor_disposition == "intentionally_absent":
            payload = {}
        else:
            raise SourceResolutionRefusalError("member_not_established", role)
    elif resolved.status == "candidate_only":
        payload = resolved.member_json_values.get(role)
        if payload is None:
            raise SourceResolutionRefusalError("member_profile_value_not_established", role)
    else:
        payload = _read_json_object(raw, role=role, typed_errors=False)
    return DemographyRoleProjection(role=role, payload=payload, evidence=resolved.evidence)


__all__ = (
    "SOURCE_INVENTORY_PRODUCER_ID",
    "SOURCE_INVENTORY_STAGE_ID",
    "DemographyInventoryEnvelope",
    "DemographyRoleProjection",
    "DemographySourceEvidence",
    "DemographySourceRequest",
    "FactProvenance",
    "HistoricalLayoutRequest",
    "InventoryBuildRequest",
    "InventorySourceRequest",
    "SourceFact",
    "SourceResolutionRefusalError",
    "SourceSemanticClaims",
    "produce_candidate_inventory",
    "read_demography_role",
    "resolve_demography_source",
)
