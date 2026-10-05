"""Content-bound substrate evidence shared by one generation-cycle run.

This module owns the intake envelope only. It does not load a domain pack,
construct a second substrate registry, or grant authority to candidate levers
or transport profiles.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.intervention_atom_binding import (
    InterventionAtomBinding,
)
from polisyos.runtime.quality.intervention_substrate import (
    InterventionLeverRefusal,
    InterventionSubstrateBundle,
    InterventionSubstrateError,
    verify_intervention_substrate_bundle_content_hash,
)
from polisyos.runtime.quality.substrate_registry import SubstrateRegistry  # noqa: TC001
from polisyos.runtime.quality.world_model_record import (
    ResolvedWorldModelAtomBinding,
    WorldModelRecord,
    WorldModelRecordError,
    resolve_intervention_atom_world_binding,
)

CYCLE_SUBSTRATE_CONTEXT_SCHEMA_VERSION = "policyos.runtime.cycle_substrate_context.v1"
CYCLE_SUBSTRATE_CONTEXT_ARTIFACT_KIND = "runtime.quality.cycle_substrate_context"
CYCLE_SUBSTRATE_CONTEXT_ARTIFACT_SCHEMA = "polisyos.runtime.CycleSubstrateContext"
_HASH_PATTERN = r"^sha256:[0-9a-f]{64}$"
_REQUIRED_AUTHORITY_DENIALS = frozenset(
    {
        "grounding_authority",
        "transport_authority",
        "promotion_authority",
    }
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CandidateLeverEvidence(_StrictModel):
    """One pack/registry-carried lever that remains candidate-only."""

    lever_id: str = Field(..., min_length=1)
    instrument: str = Field(..., min_length=1)
    target_concept: str = Field(..., min_length=1)
    status: Literal["candidate_unbound"] = "candidate_unbound"
    entry_content_hash: str = Field(..., pattern=_HASH_PATTERN)
    substrate_input_content_hash: str = Field(..., pattern=_HASH_PATTERN)
    selected_registry_entry_hash: str = Field(..., pattern=_HASH_PATTERN)
    context_binding_hash: str = Field(..., pattern=_HASH_PATTERN)
    source_refs: tuple[str, ...]

    @field_validator("source_refs")
    @classmethod
    def _source_refs_required(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not item.strip() for item in value):
            raise ValueError("candidate_lever_source_refs_missing")
        return value


class TransportCovariateObservation(_StrictModel):
    """One measured source/target context dimension from owner evidence."""

    canonical_var: str = Field(..., min_length=1)
    source_value: float = Field(..., allow_inf_nan=False)
    target_value: float = Field(..., allow_inf_nan=False)
    source_row_content_hash: str = Field(..., pattern=_HASH_PATTERN)
    target_row_content_hash: str = Field(..., pattern=_HASH_PATTERN)


class TransportContextEvidence(_StrictModel):
    """Candidate-only source/target profiles; never transport authority."""

    status: Literal["candidate_context_only_not_transport_authority"]
    source_context_id: str = Field(..., min_length=1)
    target_context_id: str = Field(..., min_length=1)
    source_profile_content_hash: str = Field(..., pattern=_HASH_PATTERN)
    target_profile_content_hash: str = Field(..., pattern=_HASH_PATTERN)
    substrate_input_content_hash: str = Field(..., pattern=_HASH_PATTERN)
    context_binding_hash: str = Field(..., pattern=_HASH_PATTERN)
    covariates: tuple[TransportCovariateObservation, ...]

    @model_validator(mode="after")
    def _validate_context_denominator(self) -> TransportContextEvidence:
        if self.source_context_id == self.target_context_id:
            raise ValueError("transport_context_roles_not_distinct")
        if not self.covariates:
            raise ValueError("transport_context_covariates_missing")
        names = [item.canonical_var for item in self.covariates]
        if len(names) != len(set(names)):
            raise ValueError("transport_context_covariate_duplicate")
        return self


class CycleSubstrateContext(_StrictModel):
    """One content-bound candidate-evidence envelope shared by cycle owners."""

    schema_version: Literal["policyos.runtime.cycle_substrate_context.v1"] = (
        CYCLE_SUBSTRATE_CONTEXT_SCHEMA_VERSION
    )
    design_problem_ref: str = Field(..., pattern=_HASH_PATTERN)
    domain: str = Field(..., min_length=1)
    source_pack_content_hash: str | None = Field(None, pattern=_HASH_PATTERN)
    substrate_input_content_hash: str | None = Field(None, pattern=_HASH_PATTERN)
    substrate_registry: SubstrateRegistry
    substrate_registry_content_hash: str = Field(..., pattern=_HASH_PATTERN)
    selected_registry_entry_hashes: tuple[str, ...]
    world_model_record: WorldModelRecord
    world_model_record_content_hash: str = Field(..., pattern=_HASH_PATTERN)
    intervention_substrate: InterventionSubstrateBundle | None = None
    candidate_levers: tuple[CandidateLeverEvidence, ...] = ()
    transport_context: TransportContextEvidence | None = None
    authority_purpose: Literal["cycle_input_candidate_only"] = (
        "cycle_input_candidate_only"
    )
    may_not_use_for: tuple[str, ...]
    context_binding_hash: str = Field(..., pattern=_HASH_PATTERN)
    content_hash: str = Field(..., pattern=_HASH_PATTERN)

    @model_validator(mode="after")
    def _validate_content_bindings(self) -> CycleSubstrateContext:
        if self.substrate_registry_content_hash != self.substrate_registry.content_hash:
            raise ValueError("cycle_substrate_registry_hash_mismatch")
        if self.world_model_record_content_hash != self.world_model_record.content_hash:
            raise ValueError("cycle_substrate_wmr_hash_mismatch")
        expected_wmr_id = (
            "world_model_record_"
            + self.world_model_record_content_hash.removeprefix("sha256:")[:16]
        )
        if self.world_model_record.world_model_record_id != expected_wmr_id:
            raise ValueError("cycle_substrate_wmr_id_mismatch")
        if self.intervention_substrate is not None:
            try:
                verify_intervention_substrate_bundle_content_hash(
                    self.intervention_substrate
                )
            except InterventionSubstrateError as exc:
                raise ValueError(
                    "cycle_substrate_intervention_bundle_hash_mismatch"
                ) from exc
        registry_ref = self.world_model_record.substrate_registry_ref
        if (
            registry_ref.content_hash != self.substrate_registry.content_hash
            or registry_ref.substrate_version_id
            != self.substrate_registry.substrate_version_id
        ):
            raise ValueError("wmr_registry_content_mismatch")
        selected = tuple(self.selected_registry_entry_hashes)
        if not selected:
            raise ValueError("cycle_substrate_selected_registry_entries_missing")
        if len(selected) != len(set(selected)):
            raise ValueError("cycle_substrate_selected_registry_entry_duplicate")
        registry_by_hash = {
            entry.entry_content_hash: entry for entry in self.substrate_registry.entries
        }
        missing_registry = sorted(set(selected).difference(registry_by_hash))
        if missing_registry:
            raise ValueError(
                "cycle_substrate_selected_entry_registry_unresolved:"
                + ",".join(missing_registry)
            )
        wmr_hashes = [
            entry.entry_content_hash for entry in registry_ref.resolved_entries
        ]
        if len(wmr_hashes) != len(set(wmr_hashes)):
            raise ValueError(
                "cycle_substrate_wmr_resolved_entry_hash_duplicate"
            )
        wmr_by_hash = {
            entry.entry_content_hash: entry for entry in registry_ref.resolved_entries
        }
        missing_wmr = sorted(set(selected).difference(wmr_by_hash))
        if missing_wmr:
            raise ValueError(
                "cycle_substrate_selected_entry_wmr_unresolved:"
                + ",".join(missing_wmr)
            )
        for entry_hash in selected:
            registry_entry = registry_by_hash[entry_hash]
            expected_projection = {
                "source_id": registry_entry.source_id,
                "family_id": registry_entry.family_id,
                "layer": registry_entry.layer.value,
                "coverage_score": registry_entry.coverage.coverage_score,
                "trust_tier": registry_entry.trust_tier.tier,
                "trust_cap": registry_entry.trust_tier.trust_cap,
                "identification_mode": registry_entry.identification_mode,
                "schema_regime_id": registry_entry.schema_regime.schema_regime_id,
                "data_version": registry_entry.data_version,
                "snapshot_id": registry_entry.snapshot_id,
                "source_snapshot_id": registry_entry.source_snapshot_id,
                "entry_content_hash": registry_entry.entry_content_hash,
            }
            if wmr_by_hash[entry_hash].model_dump(mode="json") != expected_projection:
                raise ValueError(
                    "cycle_substrate_selected_entry_projection_mismatch:"
                    + entry_hash
                )
        expected_binding = cycle_substrate_context_binding_hash(
            design_problem_ref=self.design_problem_ref,
            domain=self.domain,
            substrate_input_content_hash=self.substrate_input_content_hash,
            substrate_registry_content_hash=self.substrate_registry_content_hash,
            world_model_record_id=self.world_model_record.world_model_record_id,
            world_model_record_content_hash=self.world_model_record_content_hash,
            world_model_record_authority_status=(
                self.world_model_record.authority_status
            ),
            selected_registry_entry_hashes=selected,
        )
        if self.context_binding_hash != expected_binding:
            raise ValueError("cycle_substrate_context_binding_hash_mismatch")
        for candidate in self.candidate_levers:
            if candidate.context_binding_hash != self.context_binding_hash:
                raise ValueError("candidate_context_binding_mismatch")
            if candidate.substrate_input_content_hash != self.substrate_input_content_hash:
                raise ValueError("candidate_substrate_input_binding_mismatch")
            if candidate.selected_registry_entry_hash not in selected:
                raise ValueError("candidate_selected_registry_entry_mismatch")
        if self.transport_context is not None:
            if (
                self.transport_context.context_binding_hash
                != self.context_binding_hash
            ):
                raise ValueError("transport_context_binding_mismatch")
            if (
                self.transport_context.substrate_input_content_hash
                != self.substrate_input_content_hash
            ):
                raise ValueError("transport_substrate_input_binding_mismatch")
        if not _REQUIRED_AUTHORITY_DENIALS.issubset(self.may_not_use_for):
            raise ValueError("cycle_substrate_authority_boundary_missing")
        expected_content_hash = cycle_substrate_context_content_hash(self)
        if self.content_hash != expected_content_hash:
            raise ValueError("cycle_substrate_content_hash_mismatch")
        return self


class CycleSubstrateContextResolution(_StrictModel):
    """Typed candidate-context lookup; this owner never grants authority."""

    status: Literal["resolved_candidate_context", "unavailable", "unrun"]
    context: CycleSubstrateContext | None = None
    limitation: str = Field(..., min_length=1)
    authority_eligible: Literal[False] = False

    @model_validator(mode="after")
    def _status_matches_context(self) -> CycleSubstrateContextResolution:
        if (self.status == "resolved_candidate_context") != (self.context is not None):
            raise ValueError("cycle_substrate_context_resolution_status_mismatch")
        return self


def cycle_substrate_context_binding_hash(
    *,
    design_problem_ref: str,
    domain: str,
    substrate_input_content_hash: str | None,
    substrate_registry_content_hash: str,
    world_model_record_id: str,
    world_model_record_content_hash: str,
    world_model_record_authority_status: str,
    selected_registry_entry_hashes: Sequence[str],
) -> str:
    """Return the stable parent binding inherited by every candidate lever."""

    return gy_content_hash(
        {
            "schema_version": CYCLE_SUBSTRATE_CONTEXT_SCHEMA_VERSION,
            "design_problem_ref": design_problem_ref,
            "domain": domain,
            "substrate_input_content_hash": substrate_input_content_hash,
            "substrate_registry_content_hash": substrate_registry_content_hash,
            "world_model_record_id": world_model_record_id,
            "world_model_record_content_hash": world_model_record_content_hash,
            "world_model_record_authority_status": (
                world_model_record_authority_status
            ),
            "selected_registry_entry_hashes": sorted(
                str(item) for item in selected_registry_entry_hashes
            ),
        }
    )


def cycle_substrate_context_content_hash(
    context: CycleSubstrateContext | Mapping[str, Any],
) -> str:
    """Return the stable envelope hash without embedding owner objects twice."""

    payload = (
        context.model_dump(mode="json")
        if isinstance(context, CycleSubstrateContext)
        else dict(context)
    )
    intervention = payload.get("intervention_substrate")
    if isinstance(intervention, BaseModel):
        intervention_hash = intervention.model_dump(mode="json").get("content_hash")
    else:
        intervention_hash = (
            intervention.get("content_hash")
            if isinstance(intervention, Mapping)
            else None
        )
    candidate_rows = [
        item.model_dump(mode="json")
        if isinstance(item, BaseModel)
        else dict(item)
        if isinstance(item, Mapping)
        else item
        for item in payload.get("candidate_levers") or []
    ]
    transport = payload.get("transport_context")
    if isinstance(transport, BaseModel):
        transport_payload: object = transport.model_dump(mode="json")
    elif isinstance(transport, Mapping):
        transport_payload = dict(transport)
    else:
        transport_payload = transport
    world_model_record = payload.get("world_model_record")
    if isinstance(world_model_record, BaseModel):
        world_model_record_payload: Mapping[str, Any] = world_model_record.model_dump(
            mode="json"
        )
    elif isinstance(world_model_record, Mapping):
        world_model_record_payload = world_model_record
    else:
        world_model_record_payload = {}
    return gy_content_hash(
        {
            "schema_version": payload.get("schema_version"),
            "design_problem_ref": payload.get("design_problem_ref"),
            "domain": payload.get("domain"),
            "source_pack_content_hash": payload.get("source_pack_content_hash"),
            "substrate_input_content_hash": payload.get(
                "substrate_input_content_hash"
            ),
            "substrate_registry_content_hash": payload.get(
                "substrate_registry_content_hash"
            ),
            "selected_registry_entry_hashes": sorted(
                payload.get("selected_registry_entry_hashes") or []
            ),
            "world_model_record_content_hash": payload.get(
                "world_model_record_content_hash"
            ),
            "world_model_record_id": world_model_record_payload.get(
                "world_model_record_id"
            ),
            "world_model_record_authority_status": world_model_record_payload.get(
                "authority_status"
            ),
            "intervention_substrate_content_hash": intervention_hash,
            "candidate_levers": candidate_rows,
            "transport_context": transport_payload,
            "authority_purpose": payload.get("authority_purpose"),
            "may_not_use_for": sorted(payload.get("may_not_use_for") or []),
            "context_binding_hash": payload.get("context_binding_hash"),
        }
    )


def build_cycle_substrate_context(
    *,
    design_problem_ref: str,
    domain: str,
    substrate_registry: SubstrateRegistry,
    selected_registry_entry_hashes: Sequence[str],
    world_model_record: WorldModelRecord,
    intervention_substrate: InterventionSubstrateBundle | None,
    candidate_levers: Sequence[CandidateLeverEvidence],
    transport_context: TransportContextEvidence | None,
    source_pack_content_hash: str | None,
    substrate_input_content_hash: str | None,
) -> CycleSubstrateContext:
    """Build and fully revalidate one candidate-only cycle substrate envelope."""

    selected = tuple(str(item) for item in selected_registry_entry_hashes)
    context_binding_hash = cycle_substrate_context_binding_hash(
        design_problem_ref=design_problem_ref,
        domain=domain,
        substrate_input_content_hash=substrate_input_content_hash,
        substrate_registry_content_hash=substrate_registry.content_hash,
        world_model_record_id=world_model_record.world_model_record_id,
        world_model_record_content_hash=world_model_record.content_hash,
        world_model_record_authority_status=world_model_record.authority_status,
        selected_registry_entry_hashes=selected,
    )
    payload: dict[str, Any] = {
        "schema_version": CYCLE_SUBSTRATE_CONTEXT_SCHEMA_VERSION,
        "design_problem_ref": design_problem_ref,
        "domain": domain,
        "source_pack_content_hash": source_pack_content_hash,
        "substrate_input_content_hash": substrate_input_content_hash,
        "substrate_registry": substrate_registry,
        "substrate_registry_content_hash": substrate_registry.content_hash,
        "selected_registry_entry_hashes": selected,
        "world_model_record": world_model_record,
        "world_model_record_content_hash": world_model_record.content_hash,
        "intervention_substrate": intervention_substrate,
        "candidate_levers": tuple(candidate_levers),
        "transport_context": transport_context,
        "authority_purpose": "cycle_input_candidate_only",
        "may_not_use_for": tuple(sorted(_REQUIRED_AUTHORITY_DENIALS)),
        "context_binding_hash": context_binding_hash,
    }
    payload["content_hash"] = cycle_substrate_context_content_hash(payload)
    return CycleSubstrateContext.model_validate(payload)


def revalidate_cycle_substrate_context(
    context: CycleSubstrateContext,
) -> CycleSubstrateContext:
    """Return a fresh, fully content-verified snapshot for owner consumption."""

    if context.intervention_substrate is not None:
        try:
            verify_intervention_substrate_bundle_content_hash(
                context.intervention_substrate
            )
        except InterventionSubstrateError as exc:
            raise ValueError(
                "cycle_substrate_intervention_bundle_hash_mismatch"
            ) from exc
    return CycleSubstrateContext.model_validate(context.model_dump(mode="python"))


def persist_cycle_substrate_context(
    store: Any,
    *,
    context: CycleSubstrateContext,
    world_model_record_ref: Any,
    substrate_registry_artifact_ref: Any,
    tenant_context: Any,
) -> Any:
    """Persist a candidate context with exact owner-issued WMR/registry lineage.

    The context is only an N4/N5 input envelope. Persisting it does not change
    its candidate-only authority purpose or admit any WMR for promotion.
    """

    from polisyos.core.artifacts import ArtifactRef, InputRef, PutOptions, SchemaInfo
    from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo
    from polisyos.core.canon import CanonSpec
    from polisyos.core.security.tenant_context import (
        get_current_cell_id,
        get_current_tenant_id_or_none,
    )
    from polisyos.runtime.quality.substrate_registry import load_substrate_registry
    from polisyos.runtime.quality.world_model_record import (
        WORLD_MODEL_RECORD_ARTIFACT_KIND,
        load_world_model_record,
    )

    if not isinstance(world_model_record_ref, ArtifactRef):
        raise TypeError("cycle_substrate_wmr_ref_must_be_owner_artifact_ref")
    if not isinstance(substrate_registry_artifact_ref, ArtifactRef):
        raise TypeError("cycle_substrate_registry_ref_must_be_owner_artifact_ref")
    if not isinstance(tenant_context, ArtifactTenantContextInfo):
        raise TypeError("cycle_substrate_tenant_context_must_be_typed")
    active_tenant = get_current_tenant_id_or_none()
    active_cell = get_current_cell_id()
    if (
        active_tenant != tenant_context.tenant_id
        or (active_cell or None) != (tenant_context.cell_id or None)
    ):
        raise ValueError("cycle_substrate_context_tenant_scope_mismatch")

    verified = revalidate_cycle_substrate_context(context)
    wmr_manifest = store.get_manifest(world_model_record_ref)
    registry_manifest = store.get_manifest(substrate_registry_artifact_ref)
    if (
        wmr_manifest.kind != WORLD_MODEL_RECORD_ARTIFACT_KIND
        or wmr_manifest.artifact_schema is None
        or wmr_manifest.artifact_schema.name
        != "polisyos.runtime.quality.WorldModelRecord"
        or registry_manifest.kind != "runtime.quality.production_data_substrate_registry"
        or registry_manifest.artifact_schema is None
        or registry_manifest.artifact_schema.name
        != "polisyos.runtime.quality.SubstrateRegistry"
    ):
        raise ValueError("cycle_substrate_owner_input_manifest_invalid")
    wmr = load_world_model_record(store, world_model_record_ref)
    registry = load_substrate_registry(store, substrate_registry_artifact_ref)
    if wmr.model_dump(mode="json") != verified.world_model_record.model_dump(mode="json"):
        raise ValueError("cycle_substrate_wmr_owner_ref_content_mismatch")
    if registry.model_dump(mode="json") != verified.substrate_registry.model_dump(mode="json"):
        raise ValueError("cycle_substrate_registry_owner_ref_content_mismatch")
    if (
        wmr.substrate_registry_ref.registry_artifact_ref
        != str(substrate_registry_artifact_ref.artifact_id)
    ):
        raise ValueError("cycle_substrate_wmr_registry_ref_mismatch")

    return store.put_json(
        verified,
        PutOptions(
            kind=CYCLE_SUBSTRATE_CONTEXT_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=CYCLE_SUBSTRATE_CONTEXT_ARTIFACT_SCHEMA,
                version=CYCLE_SUBSTRATE_CONTEXT_SCHEMA_VERSION,
            ),
            inputs=[
                InputRef(
                    artifact_id=world_model_record_ref.artifact_id,
                    role="world_model_record",
                ),
                InputRef(
                    artifact_id=substrate_registry_artifact_ref.artifact_id,
                    role="substrate_registry",
                ),
            ],
            tenant_context=tenant_context,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def resolve_cycle_substrate_context_artifact(
    store: Any,
    *,
    context_ref: Any,
    design_problem_ref: str,
    target_region: str,
    tenant_id: str,
    cell_id: str | None,
) -> CycleSubstrateContextResolution:
    """Read one tenant-owned persisted candidate context through its owners.

    Exact problem and jurisdiction bindings are checked here. Population,
    outcome, time, intervention semantics, and promotion authority remain
    separate predicates; the returned context always declares that limitation.
    """

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.security.tenant_context import (
        get_current_cell_id,
        get_current_tenant_id_or_none,
    )
    from polisyos.runtime.quality.substrate_registry import load_substrate_registry
    from polisyos.runtime.quality.world_model_record import (
        WORLD_MODEL_RECORD_ARTIFACT_KIND,
        load_world_model_record,
    )

    if not isinstance(context_ref, ArtifactRef):
        return CycleSubstrateContextResolution(
            status="unavailable",
            limitation="cycle_substrate_context_ref_not_owner_artifact_ref",
        )
    active_tenant = get_current_tenant_id_or_none()
    active_cell = get_current_cell_id()
    if (
        active_tenant != tenant_id
        or (active_cell or None) != (cell_id or None)
    ):
        return CycleSubstrateContextResolution(
            status="unavailable",
            limitation="cycle_substrate_context_tenant_scope_not_established",
        )
    try:
        manifest = store.get_manifest(context_ref)
        if (
            manifest.kind != CYCLE_SUBSTRATE_CONTEXT_ARTIFACT_KIND
            or manifest.media_type != "application/json"
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != CYCLE_SUBSTRATE_CONTEXT_ARTIFACT_SCHEMA
            or manifest.artifact_schema.version != CYCLE_SUBSTRATE_CONTEXT_SCHEMA_VERSION
        ):
            return CycleSubstrateContextResolution(
                status="unavailable",
                limitation="cycle_substrate_context_manifest_not_owner_profile",
            )
        if manifest.tenant_context is None or (
            manifest.tenant_context.tenant_id != tenant_id
            or (manifest.tenant_context.cell_id or None) != (cell_id or None)
        ):
            return CycleSubstrateContextResolution(
                status="unavailable",
                limitation="cycle_substrate_context_foreign_tenant_binding",
            )
        input_refs = {item.role: item for item in manifest.inputs}
        if set(input_refs) != {"world_model_record", "substrate_registry"}:
            return CycleSubstrateContextResolution(
                status="unavailable",
                limitation="cycle_substrate_context_owner_lineage_incomplete",
            )
        context = CycleSubstrateContext.model_validate(
            from_canonical_bytes(store.get_bytes(context_ref))
        )
        verified = revalidate_cycle_substrate_context(context)
        wmr_ref = ArtifactRef(
            artifact_id=input_refs["world_model_record"].artifact_id,
            kind=WORLD_MODEL_RECORD_ARTIFACT_KIND,
            media_type="application/json",
        )
        registry_ref = ArtifactRef(
            artifact_id=input_refs["substrate_registry"].artifact_id,
            kind="runtime.quality.production_data_substrate_registry",
            media_type="application/json",
        )
        wmr = load_world_model_record(store, wmr_ref)
        registry = load_substrate_registry(store, registry_ref)
        if (
            wmr.model_dump(mode="json")
            != verified.world_model_record.model_dump(mode="json")
            or registry.model_dump(mode="json")
            != verified.substrate_registry.model_dump(mode="json")
            or wmr.substrate_registry_ref.registry_artifact_ref
            != str(registry_ref.artifact_id)
        ):
            return CycleSubstrateContextResolution(
                status="unavailable",
                limitation="cycle_substrate_context_owner_lineage_content_mismatch",
            )
        if verified.design_problem_ref != design_problem_ref:
            return CycleSubstrateContextResolution(
                status="unavailable",
                limitation="cycle_substrate_context_design_problem_mismatch",
            )
        if (
            not target_region.strip()
            or verified.world_model_record.region_or_jurisdiction
            != target_region.strip()
        ):
            return CycleSubstrateContextResolution(
                status="unavailable",
                limitation="cycle_substrate_context_jurisdiction_mismatch",
            )
        return CycleSubstrateContextResolution(
            status="resolved_candidate_context",
            context=verified,
            limitation=(
                "cycle_substrate_context_candidate_only; population, outcome, time, "
                "intervention semantics, and authority are not established by this owner"
            ),
        )
    except Exception as exc:
        return CycleSubstrateContextResolution(
            status="unavailable",
            limitation=(
                "cycle_substrate_context_store_inspection_failed:"
                + str(getattr(exc, "code", type(exc).__name__))
            ),
        )


def resolve_cycle_substrate_context_from_store(
    store: Any,
    *,
    design_problem_ref: str,
    target_region: str,
    tenant_id: str,
    cell_id: str | None,
) -> CycleSubstrateContextResolution:
    """Resolve a unique exact-problem context from the active tenant's CAS.

    The artifact store protocol exposes enumeration but no kind index. This
    owner therefore declares a full tenant-store scan as its current cost;
    an unavailable or failed inventory never becomes a successful lookup.
    """

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.security.tenant_context import (
        get_current_cell_id,
        get_current_tenant_id_or_none,
    )

    if (
        get_current_tenant_id_or_none() != tenant_id
        or (get_current_cell_id() or None) != (cell_id or None)
    ):
        return CycleSubstrateContextResolution(
            status="unavailable",
            limitation="cycle_substrate_context_tenant_scope_not_established",
        )
    try:
        artifact_ids = store.iter_artifact_ids()
        matches: dict[str, CycleSubstrateContext] = {}
        for artifact_id in artifact_ids:
            manifest = store.get_manifest(artifact_id)
            if manifest.kind != CYCLE_SUBSTRATE_CONTEXT_ARTIFACT_KIND:
                continue
            context_ref = ArtifactRef(
                artifact_id=artifact_id,
                kind=manifest.kind,
                media_type=manifest.media_type,
            )
            result = resolve_cycle_substrate_context_artifact(
                store,
                context_ref=context_ref,
                design_problem_ref=design_problem_ref,
                target_region=target_region,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            if result.status == "resolved_candidate_context" and result.context is not None:
                matches[result.context.content_hash] = result.context
        if not matches:
            return CycleSubstrateContextResolution(
                status="unavailable",
                limitation="cycle_substrate_context_owner_match_not_found",
            )
        if len(matches) != 1:
            return CycleSubstrateContextResolution(
                status="unavailable",
                limitation="cycle_substrate_context_owner_match_ambiguous",
            )
        return CycleSubstrateContextResolution(
            status="resolved_candidate_context",
            context=next(iter(matches.values())),
            limitation=(
                "cycle_substrate_context_candidate_only; population, outcome, time, "
                "intervention semantics, and authority are not established by this owner"
            ),
        )
    except Exception as exc:
        return CycleSubstrateContextResolution(
            status="unrun",
            limitation=(
                "cycle_substrate_context_store_census_failed:"
                + str(getattr(exc, "code", type(exc).__name__))
            ),
        )


def resolve_cycle_substrate_context_for_world(
    contexts: Sequence[CycleSubstrateContext],
    *,
    design_problem_ref: str,
    region_or_jurisdiction: str,
) -> CycleSubstrateContext:
    """Resolve one content-bound cycle context without trusting domain labels.

    The DesignProblem content reference and the WMR's concrete jurisdiction are
    the selection evidence. Producer-scoped ``domain`` labels remain recorded
    provenance and are deliberately absent from this decision.

    Args:
        contexts: Available owner-built contexts for the active request.
        design_problem_ref: Exact content hash of the active DesignProblem.
        region_or_jurisdiction: Concrete target world named by that problem.

    Returns:
        The unique fully revalidated matching context.

    Raises:
        WorldModelRecordError: If no unique context resolves.
    """

    target_region = str(region_or_jurisdiction or "").strip()
    if not target_region:
        raise WorldModelRecordError(
            "cycle_substrate_context_unresolved",
            "target region or jurisdiction is missing",
        )
    verified_by_hash: dict[str, CycleSubstrateContext] = {}
    for context in contexts:
        verified = revalidate_cycle_substrate_context(context)
        verified_by_hash[verified.content_hash] = verified
    matches = tuple(
        context
        for context in verified_by_hash.values()
        if context.design_problem_ref == design_problem_ref
        and context.world_model_record.region_or_jurisdiction == target_region
    )
    if not matches:
        raise WorldModelRecordError(
            "cycle_substrate_context_unresolved",
            "no owner context resolves the active DesignProblem and target world",
        )
    if len(matches) != 1:
        raise WorldModelRecordError(
            "cycle_substrate_context_ambiguous",
            "multiple owner contexts resolve the active DesignProblem and target world",
        )
    return matches[0]


def resolve_cycle_substrate_world_identity(
    context: CycleSubstrateContext,
    *,
    atom: InterventionAtomBinding,
) -> ResolvedWorldModelAtomBinding:
    """Resolve one candidate atom against the context's content-bound world.

    Domain labels remain provenance because their producers have different
    scopes. World identity is granted only by resolving the atom's world ref
    and every target slot against the concrete WMR bound into this context.
    """

    verified = revalidate_cycle_substrate_context(context)
    return resolve_world_model_atom_identity(
        atom=atom,
        world_model_record=verified.world_model_record,
        design_problem_ref=verified.design_problem_ref,
        expected_world_model_content_hash=verified.world_model_record_content_hash,
    )


def resolve_candidate_lever_world_identity(
    context: CycleSubstrateContext,
    *,
    refusal: InterventionLeverRefusal,
) -> CandidateLeverEvidence:
    """Resolve one non-binding lever refusal against its exact cycle context.

    This resolver carries world identity only. It never creates an intervention
    atom or changes the refusal's ``candidate_unbound`` authority posture.

    Args:
        context: Content-bound substrate context for the active DesignProblem.
        refusal: N4/L6 refusal whose hashes must resolve to one candidate lever.

    Returns:
        The exact candidate-lever evidence row bound by the refusal.

    Raises:
        WorldModelRecordError: If any refusal/context identity is unresolved.
    """

    verified = revalidate_cycle_substrate_context(context)
    try:
        resolved_refusal = InterventionLeverRefusal.model_validate(
            refusal.model_dump(mode="python")
        )
    except (AttributeError, TypeError, ValidationError, ValueError) as exc:
        raise WorldModelRecordError(
            "world_identity_unresolved",
            "candidate lever refusal is not owner-valid",
        ) from exc
    if resolved_refusal.status != "candidate_unbound":
        raise WorldModelRecordError(
            "world_identity_unresolved",
            "candidate lever refusal is not candidate_unbound",
        )
    matches = tuple(
        candidate
        for candidate in verified.candidate_levers
        if candidate.lever_id == resolved_refusal.lever_id
        and candidate.instrument == resolved_refusal.instrument
        and candidate.entry_content_hash
        == resolved_refusal.candidate_entry_content_hash
    )
    if len(matches) != 1:
        raise WorldModelRecordError(
            "world_identity_unresolved",
            "candidate lever refusal does not resolve exactly once",
        )
    candidate = matches[0]
    observed = {
        "context_binding_hash": resolved_refusal.context_binding_hash,
        "substrate_input_content_hash": resolved_refusal.substrate_input_content_hash,
        "substrate_registry_content_hash": resolved_refusal.substrate_registry_content_hash,
        "world_model_record_content_hash": (
            resolved_refusal.world_model_record_content_hash
        ),
        "selected_registry_entry_hash": resolved_refusal.selected_registry_entry_hash,
        "source_refs": resolved_refusal.source_refs,
    }
    expected = {
        "context_binding_hash": verified.context_binding_hash,
        "substrate_input_content_hash": verified.substrate_input_content_hash,
        "substrate_registry_content_hash": verified.substrate_registry_content_hash,
        "world_model_record_content_hash": verified.world_model_record_content_hash,
        "selected_registry_entry_hash": candidate.selected_registry_entry_hash,
        "source_refs": candidate.source_refs,
    }
    if observed != expected:
        raise WorldModelRecordError(
            "world_identity_unresolved",
            "candidate lever refusal is bound to another context",
        )
    return candidate


def resolve_world_model_atom_identity(
    *,
    atom: InterventionAtomBinding,
    world_model_record: WorldModelRecord,
    design_problem_ref: str | None = None,
    expected_world_model_content_hash: str | None = None,
) -> ResolvedWorldModelAtomBinding:
    """Resolve a strict atom against one concrete, content-bound world.

    The optional DesignProblem ref binds a selected candidate to its producing
    problem. Composed request atoms may omit that check while still resolving
    their world ref and every target slot through the same owner.
    """

    if not isinstance(atom, InterventionAtomBinding):
        raise WorldModelRecordError(
            "world_identity_unresolved",
            "candidate atom does not resolve through InterventionAtomBinding",
        )
    try:
        verified_atom = InterventionAtomBinding.model_validate(
            atom.model_dump(mode="python")
        )
        if (
            design_problem_ref is not None
            and verified_atom.problem_frame_ref != design_problem_ref
        ):
            raise WorldModelRecordError(
                "world_identity_unresolved",
                "candidate atom names another DesignProblem",
            )
        resolved = resolve_intervention_atom_world_binding(
            verified_atom,
            world_model_record,
        )
    except (AttributeError, TypeError, ValidationError, WorldModelRecordError) as exc:
        reason = str(getattr(exc, "code", None) or type(exc).__name__)
        raise WorldModelRecordError(
            "world_identity_unresolved",
            reason,
        ) from exc
    expected_hash = expected_world_model_content_hash or world_model_record.content_hash
    if (
        resolved.world_model_record_id != world_model_record.world_model_record_id
        or resolved.world_model_record_content_hash
        != expected_hash
    ):
        raise WorldModelRecordError(
            "world_identity_unresolved",
            "resolved atom binding does not name the context WMR",
        )
    return resolved


__all__ = [
    "CYCLE_SUBSTRATE_CONTEXT_SCHEMA_VERSION",
    "CYCLE_SUBSTRATE_CONTEXT_ARTIFACT_KIND",
    "CYCLE_SUBSTRATE_CONTEXT_ARTIFACT_SCHEMA",
    "CandidateLeverEvidence",
    "CycleSubstrateContext",
    "CycleSubstrateContextResolution",
    "TransportContextEvidence",
    "TransportCovariateObservation",
    "build_cycle_substrate_context",
    "cycle_substrate_context_binding_hash",
    "cycle_substrate_context_content_hash",
    "persist_cycle_substrate_context",
    "resolve_candidate_lever_world_identity",
    "resolve_cycle_substrate_context_artifact",
    "resolve_cycle_substrate_context_from_store",
    "resolve_cycle_substrate_context_for_world",
    "resolve_cycle_substrate_world_identity",
    "resolve_world_model_atom_identity",
    "revalidate_cycle_substrate_context",
]
