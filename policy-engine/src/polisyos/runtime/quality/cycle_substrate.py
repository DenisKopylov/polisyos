"""Content-bound substrate evidence shared by one generation-cycle run.

This module owns the intake envelope only. It does not load a domain pack,
construct a second substrate registry, or grant authority to candidate levers
or transport profiles.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.intervention_substrate import (
    InterventionSubstrateBundle,
    InterventionSubstrateError,
    verify_intervention_substrate_bundle_content_hash,
)
from polisyos.runtime.quality.substrate_registry import SubstrateRegistry  # noqa: TC001
from polisyos.runtime.quality.world_model_record import WorldModelRecord  # noqa: TC001

CYCLE_SUBSTRATE_CONTEXT_SCHEMA_VERSION = "policyos.runtime.cycle_substrate_context.v1"
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
        if self.world_model_record.policy_domain != self.domain:
            raise ValueError("cycle_substrate_wmr_domain_mismatch")
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


__all__ = [
    "CYCLE_SUBSTRATE_CONTEXT_SCHEMA_VERSION",
    "CandidateLeverEvidence",
    "CycleSubstrateContext",
    "TransportContextEvidence",
    "TransportCovariateObservation",
    "build_cycle_substrate_context",
    "cycle_substrate_context_binding_hash",
    "cycle_substrate_context_content_hash",
    "revalidate_cycle_substrate_context",
]
