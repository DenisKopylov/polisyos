"""Typed records for explicitly configured, candidate-only N5 scenarios.

These records describe a hypothetical simulation input. They do not establish
real-world scope, grounded effects, authority, promotion, or publication.
Persistence and runtime decisions remain with the existing context and source
owners.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    artifact_ref_identity_key,
)
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.cycle_substrate import (
    CandidateLeverEvidence,  # noqa: TC001 - Pydantic resolves these model fields at runtime.
    CycleSubstrateContext,  # noqa: TC001 - Pydantic resolves these model fields at runtime.
    TransportContextEvidence,  # noqa: TC001 - Pydantic resolves these model fields at runtime.
)
from polisyos.runtime.quality.intervention_atom_binding import (  # noqa: TC001
    InterventionAtomBinding,
)
from polisyos.runtime.quality.intervention_substrate import (  # noqa: TC001
    InterventionSubstrateBundle,
)
from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec  # noqa: TC001
from polisyos.runtime.quality.substrate_registry import SubstrateRegistry  # noqa: TC001
from polisyos.runtime.quality.world_model_record import WorldModelRecord  # noqa: TC001

_HASH_PATTERN = r"^sha256:[0-9a-f]{64}$"


class _StrictModel(BaseModel):
    """Base for immutable configuration and handoff DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CandidateSimulationContextInputs(_StrictModel):
    """Already-owned typed inputs used to compose one candidate context."""

    substrate_registry: SubstrateRegistry
    selected_registry_entry_hashes: tuple[str, ...]
    world_model_record: WorldModelRecord
    intervention_substrate: InterventionSubstrateBundle | None = None
    candidate_levers: tuple[CandidateLeverEvidence, ...] = ()
    transport_context: TransportContextEvidence | None = None
    source_pack_content_hash: str | None = Field(default=None, pattern=_HASH_PATTERN)
    substrate_input_content_hash: str | None = Field(default=None, pattern=_HASH_PATTERN)


class CandidateScenarioSetToRule(_StrictModel):
    """One exact integer-only hypothetical direct state edit."""

    schema_version: Literal["policyos.runtime.candidate_scenario.set_to.v1"] = (
        "policyos.runtime.candidate_scenario.set_to.v1"
    )
    operator_kind: str = Field(..., min_length=1, strict=True)
    parameter_id: str = Field(..., min_length=1, strict=True)
    target_world_slot: str = Field(..., min_length=1, strict=True)
    unit_id: str = Field(..., min_length=1, strict=True)
    minimum: int = Field(..., strict=True)
    maximum: int = Field(..., strict=True)

    @model_validator(mode="after")
    def _valid_integer_domain(self) -> CandidateScenarioSetToRule:
        if self.minimum > self.maximum:
            raise ValueError("candidate_scenario_integer_domain_invalid")
        return self


class CandidateScenarioN5Config(_StrictModel):
    """Server-owned, explicit request-shaping inputs for the N5 engine."""

    schema_version: Literal["policyos.runtime.candidate_scenario.n5_config.v1"] = (
        "policyos.runtime.candidate_scenario.n5_config.v1"
    )
    engine_kind: Literal["ncm_parallel_worlds"] = "ncm_parallel_worlds"
    budget_ref: str = Field(..., min_length=1, strict=True)
    horizon: HorizonSpec
    baseline_state: dict[str, float] = Field(default_factory=dict)
    comparator_refs: tuple[str, ...] = ()
    seed: int = Field(default=0, strict=True)
    replications: int = Field(default=1, ge=1, strict=True)

    @model_validator(mode="after")
    def _finite_baseline(self) -> CandidateScenarioN5Config:
        import math

        if any(not math.isfinite(value) for value in self.baseline_state.values()):
            raise ValueError("candidate_scenario_n5_baseline_non_finite")
        if len(self.comparator_refs) != len(set(self.comparator_refs)):
            raise ValueError("candidate_scenario_n5_comparator_duplicate")
        return self


class CandidateSimulationScenarioProfile(_StrictModel):
    """Server-configured scenario selected by a bounded semantic projection."""

    schema_version: Literal["policyos.runtime.candidate_simulation_profile.v2"] = (
        "policyos.runtime.candidate_simulation_profile.v2"
    )
    profile_id: str = Field(..., min_length=1, strict=True)
    purpose: Literal["synthetic_candidate_scenario"] = "synthetic_candidate_scenario"
    profile_selection_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    context_inputs: CandidateSimulationContextInputs
    rule: CandidateScenarioSetToRule
    n5: CandidateScenarioN5Config
    limitations: tuple[
        Literal[
            "scenario_only",
            "real_profile_not_established",
            "real_time_not_established",
            "grounding_not_established",
            "s8_blocked",
            "n9_not_admitted",
        ],
        ...,
    ]
    content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_profile_hash_and_limitations(self) -> CandidateSimulationScenarioProfile:
        required = {
            "scenario_only",
            "real_profile_not_established",
            "real_time_not_established",
            "grounding_not_established",
            "s8_blocked",
            "n9_not_admitted",
        }
        if not required.issubset(self.limitations):
            raise ValueError("candidate_simulation_profile_limitation_missing")
        if len(self.limitations) != len(set(self.limitations)):
            raise ValueError("candidate_simulation_profile_limitation_duplicate")
        expected = gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_simulation_profile_content_hash_mismatch")
        return self


class CandidateSimulationSyntheticModelDeclarationV1(_StrictModel):
    """Declare one explicit candidate-only structural relationship.

    This is a server-configured assumption for a controlled simulation. It is
    not an empirical causal claim, calibration, or authority to publish.
    """

    schema_version: Literal[
        "policyos.runtime.candidate_simulation.synthetic_model_declaration.v1"
    ] = "policyos.runtime.candidate_simulation.synthetic_model_declaration.v1"
    profile_config_ref: str = Field(..., min_length=1, strict=True)
    profile_content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    profile_selection_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    target_world_slot: str = Field(..., min_length=1, strict=True)
    outcome_variable: str = Field(..., min_length=1, strict=True)
    target_unit_id: str = Field(..., min_length=1, strict=True)
    outcome_unit_id: str = Field(..., min_length=1, strict=True)
    target_baseline: float = Field(..., strict=True)
    outcome_baseline: float = Field(..., strict=True)
    outcome_per_target_unit: float = Field(..., strict=True)
    outcome_noise_stddev: float = Field(default=0.01, ge=0.0, strict=True)
    assumption: Literal["declared_candidate_scm_not_empirically_grounded"] = (
        "declared_candidate_scm_not_empirically_grounded"
    )
    content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_declaration(self) -> CandidateSimulationSyntheticModelDeclarationV1:
        import math

        numeric = (
            self.target_baseline,
            self.outcome_baseline,
            self.outcome_per_target_unit,
            self.outcome_noise_stddev,
        )
        if any(not math.isfinite(value) for value in numeric):
            raise ValueError("candidate_simulation_synthetic_model_non_finite")
        if self.target_world_slot == self.outcome_variable:
            raise ValueError("candidate_simulation_synthetic_model_edge_self_reference")
        if self.outcome_per_target_unit == 0.0:
            raise ValueError("candidate_simulation_synthetic_model_edge_missing")
        expected = gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_simulation_synthetic_model_hash_mismatch")
        return self


class CandidateSimulationContextOffer(_StrictModel):
    """Owner-produced exact profile/context pair before job persistence."""

    context: CycleSubstrateContext
    profile: CandidateSimulationScenarioProfile
    profile_config_ref: str = Field(..., min_length=1, strict=True)
    model_declaration: CandidateSimulationSyntheticModelDeclarationV1 | None = None
    model_declaration_ref: ArtifactRef | None = None
    ncm_ref: ArtifactRef | None = None

    @model_validator(mode="after")
    def _model_bindings(self) -> CandidateSimulationContextOffer:
        model_fields = (
            self.model_declaration,
            self.model_declaration_ref,
            self.ncm_ref,
        )
        if all(value is None for value in model_fields):
            if self.profile_config_ref != candidate_simulation_profile_ref(self.profile):
                raise ValueError("candidate_simulation_offer_profile_ref_mismatch")
            return self
        if any(value is None for value in model_fields):
            raise ValueError("candidate_simulation_offer_model_binding_incomplete")
        _validate_model_offer_bindings(
            profile=self.profile,
            profile_config_ref=self.profile_config_ref,
            declaration=self.model_declaration,
            declaration_ref=self.model_declaration_ref,
            ncm_ref=self.ncm_ref,
            context=self.context,
        )
        return self


class CandidateSimulationContextHandoff(_StrictModel):
    """Persisted context-job reference bound to one active worker identity."""

    context: CycleSubstrateContext
    context_job_ref: ArtifactRef
    profile: CandidateSimulationScenarioProfile
    profile_config_ref: str = Field(..., min_length=1, strict=True)
    job_id: str = Field(..., min_length=1, strict=True)
    run_id: str = Field(..., min_length=1, strict=True)
    tenant_id: str = Field(..., min_length=1, strict=True)
    cell_id: str = Field(..., min_length=1, strict=True)
    model_declaration: CandidateSimulationSyntheticModelDeclarationV1 | None = None
    model_declaration_ref: ArtifactRef | None = None
    ncm_ref: ArtifactRef | None = None

    @model_validator(mode="after")
    def _profile_context_binding(self) -> CandidateSimulationContextHandoff:
        if self.profile_config_ref != candidate_simulation_profile_ref(self.profile):
            raise ValueError("candidate_simulation_handoff_profile_ref_mismatch")
        if (
            self.context_job_ref.kind != "runtime.quality.cycle_substrate_context_job"
            or self.context_job_ref.media_type != "application/json"
        ):
            raise ValueError("candidate_simulation_handoff_context_kind_mismatch")
        model_fields = (
            self.model_declaration,
            self.model_declaration_ref,
            self.ncm_ref,
        )
        if all(value is None for value in model_fields):
            return self
        if any(value is None for value in model_fields):
            raise ValueError("candidate_simulation_handoff_model_binding_incomplete")
        _validate_model_offer_bindings(
            profile=self.profile,
            profile_config_ref=self.profile_config_ref,
            declaration=self.model_declaration,
            declaration_ref=self.model_declaration_ref,
            ncm_ref=self.ncm_ref,
            context=self.context,
        )
        return self


def _validate_model_offer_bindings(
    *,
    profile: CandidateSimulationScenarioProfile,
    profile_config_ref: str,
    declaration: CandidateSimulationSyntheticModelDeclarationV1,
    declaration_ref: ArtifactRef,
    ncm_ref: ArtifactRef,
    context: CycleSubstrateContext,
) -> None:
    """Check that an owner-produced model view is bound to this exact context."""

    if (
        profile_config_ref != candidate_simulation_profile_ref(profile)
        or declaration.profile_config_ref != profile_config_ref
        or declaration.profile_content_hash != profile.content_hash
        or declaration.profile_selection_ref != profile.profile_selection_ref
        or declaration.target_world_slot != profile.rule.target_world_slot
        or declaration.target_unit_id != profile.rule.unit_id
        or profile.n5.baseline_state.get(declaration.target_world_slot)
        != declaration.target_baseline
        or profile.n5.baseline_state.get(declaration.outcome_variable)
        != declaration.outcome_baseline
    ):
        raise ValueError("candidate_simulation_model_profile_binding_mismatch")
    if (
        declaration_ref.kind
        != "runtime.quality.candidate_simulation_model_declaration"
        or declaration_ref.media_type != "application/json"
        or ncm_ref.kind != "ir.ncm_spec"
        or ncm_ref.media_type != "application/json"
        or str(ncm_ref.artifact_id)
        not in context.world_model_record.simulation_model_ref.ncm_refs
    ):
        raise ValueError("candidate_simulation_model_selected_ref_mismatch")


class CandidateScenarioMaterializationV1(_StrictModel):
    """Content-bound derived N5 atom; the original N4 atom remains untouched."""

    schema_version: Literal["policyos.runtime.candidate_scenario.materialization.v1"] = (
        "policyos.runtime.candidate_scenario.materialization.v1"
    )
    profile_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    problem_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    context_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    context_job_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    world_model_record_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    source_handoff_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    candidate_id: str = Field(..., min_length=1, strict=True)
    original_candidate_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    original_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    operator_kind: str = Field(..., min_length=1, strict=True)
    parameter_id: str = Field(..., min_length=1, strict=True)
    value: int = Field(..., strict=True)
    target_world_slot: str = Field(..., min_length=1, strict=True)
    unit_id: str = Field(..., min_length=1, strict=True)
    derived_n5_atom: InterventionAtomBinding
    content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_content_hash(self) -> CandidateScenarioMaterializationV1:
        expected = gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_scenario_materialization_content_hash_mismatch")
        if self.derived_n5_atom.status != "candidate_unverified":
            raise ValueError("candidate_scenario_derived_atom_not_candidate")
        if self.derived_n5_atom.content_hash == self.original_atom_hash:
            raise ValueError("candidate_scenario_derived_atom_hash_not_changed")
        return self


class CandidateScenarioMaterializationV2(_StrictModel):
    """N5 materialization with full CAS views while preserving the N4 source."""

    schema_version: Literal["policyos.runtime.candidate_scenario.materialization.v2"] = (
        "policyos.runtime.candidate_scenario.materialization.v2"
    )
    profile_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    problem_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    context_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    context_job_ref: ArtifactRef
    world_model_record_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    source_handoff_ref: ArtifactRef
    candidate_id: str = Field(..., min_length=1, strict=True)
    original_candidate_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    original_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    operator_kind: str = Field(..., min_length=1, strict=True)
    parameter_id: str = Field(..., min_length=1, strict=True)
    value: int = Field(..., strict=True)
    target_world_slot: str = Field(..., min_length=1, strict=True)
    unit_id: str = Field(..., min_length=1, strict=True)
    derived_n5_atom: InterventionAtomBinding
    content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_content_hash(self) -> CandidateScenarioMaterializationV2:
        expected = gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_scenario_materialization_content_hash_mismatch")
        if self.derived_n5_atom.status != "candidate_unverified":
            raise ValueError("candidate_scenario_derived_atom_not_candidate")
        if self.derived_n5_atom.content_hash == self.original_atom_hash:
            raise ValueError("candidate_scenario_derived_atom_hash_not_changed")
        if (
            self.context_job_ref.kind != "runtime.quality.cycle_substrate_context_job"
            or self.context_job_ref.media_type != "application/json"
            or self.source_handoff_ref.kind != "runtime.generation_source_handoff"
            or self.source_handoff_ref.media_type != "application/json"
        ):
            raise ValueError("candidate_scenario_materialization_owner_kind_mismatch")
        return self


class CandidateScenarioMaterializationV3(_StrictModel):
    """N5 materialization bound to the proposal-specific N4 source owner."""

    schema_version: Literal["policyos.runtime.candidate_scenario.materialization.v3"] = (
        "policyos.runtime.candidate_scenario.materialization.v3"
    )
    profile_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    problem_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    context_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    context_job_ref: ArtifactRef
    world_model_record_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    n4_source_ref: ArtifactRef
    candidate_id: str = Field(..., min_length=1, strict=True)
    original_candidate_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    original_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    operator_kind: str = Field(..., min_length=1, strict=True)
    parameter_id: str = Field(..., min_length=1, strict=True)
    value: int = Field(..., strict=True)
    target_world_slot: str = Field(..., min_length=1, strict=True)
    unit_id: str = Field(..., min_length=1, strict=True)
    derived_n5_atom: InterventionAtomBinding
    content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_content_hash(self) -> CandidateScenarioMaterializationV3:
        expected = gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_scenario_materialization_content_hash_mismatch")
        if self.derived_n5_atom.status != "candidate_unverified":
            raise ValueError("candidate_scenario_derived_atom_not_candidate")
        if self.derived_n5_atom.content_hash == self.original_atom_hash:
            raise ValueError("candidate_scenario_derived_atom_hash_not_changed")
        if (
            self.context_job_ref.kind != "runtime.quality.cycle_substrate_context_job"
            or self.context_job_ref.media_type != "application/json"
            or self.n4_source_ref.kind != "runtime.quality.n4_candidate_scenario_source"
            or self.n4_source_ref.media_type != "application/json"
        ):
            raise ValueError("candidate_scenario_materialization_owner_kind_mismatch")
        return self


class CandidateScenarioMaterializationV4(_StrictModel):
    """N5 atom projection bound to versioned source and selected model views."""

    schema_version: Literal["policyos.runtime.candidate_scenario.materialization.v4"] = (
        "policyos.runtime.candidate_scenario.materialization.v4"
    )
    profile_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    problem_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    context_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    context_job_ref: ArtifactRef
    world_model_record_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    n4_source_ref: ArtifactRef
    model_declaration_ref: ArtifactRef
    ncm_ref: ArtifactRef
    candidate_id: str = Field(..., min_length=1, strict=True)
    original_candidate_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    original_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    operator_kind: str = Field(..., min_length=1, strict=True)
    parameter_id: str = Field(..., min_length=1, strict=True)
    value: int = Field(..., strict=True)
    target_world_slot: str = Field(..., min_length=1, strict=True)
    unit_id: str = Field(..., min_length=1, strict=True)
    outcome_variable: str = Field(..., min_length=1, strict=True)
    derived_n5_atom: InterventionAtomBinding
    content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_materialization(self) -> CandidateScenarioMaterializationV4:
        if self.derived_n5_atom.status != "candidate_unverified":
            raise ValueError("candidate_scenario_derived_atom_not_candidate")
        if self.derived_n5_atom.content_hash == self.original_atom_hash:
            raise ValueError("candidate_scenario_derived_atom_hash_not_changed")
        refs = (
            (self.context_job_ref, "runtime.quality.cycle_substrate_context_job"),
            (self.n4_source_ref, "runtime.quality.n4_candidate_scenario_source"),
            (self.model_declaration_ref, "runtime.quality.candidate_simulation_model_declaration"),
            (self.ncm_ref, "ir.ncm_spec"),
        )
        if any(ref.kind != kind or ref.media_type != "application/json" for ref, kind in refs):
            raise ValueError("candidate_scenario_materialization_owner_kind_mismatch")
        expected = gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_scenario_materialization_content_hash_mismatch")
        return self


class CandidateSimulationN5InputV2(_StrictModel):
    """Versioned, purpose-specific N5 request admission record."""

    schema_version: Literal["policyos.runtime.candidate_simulation.n5_input.v2"] = (
        "policyos.runtime.candidate_simulation.n5_input.v2"
    )
    authority_purpose: Literal["candidate_scenario_n5_only"] = "candidate_scenario_n5_only"
    source_role: Literal["runtime-config:candidate-simulation"] = (
        "runtime-config:candidate-simulation"
    )
    profile: CandidateSimulationScenarioProfile
    profile_config_ref: str = Field(..., min_length=1, strict=True)
    n4_source_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    context_job_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    job_id: str = Field(..., min_length=1, strict=True)
    run_id: str = Field(..., min_length=1, strict=True)
    tenant_id: str = Field(..., min_length=1, strict=True)
    cell_id: str = Field(..., min_length=1, strict=True)
    original_candidate_id: str = Field(..., min_length=1, strict=True)
    original_candidate_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    original_n4_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    outcome_variable: str = Field(..., min_length=1, strict=True)
    materialization: CandidateScenarioMaterializationV1
    n5: CandidateScenarioN5Config
    content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_bindings(self) -> CandidateSimulationN5InputV2:
        if self.profile_config_ref != candidate_simulation_profile_ref(self.profile):
            raise ValueError("candidate_simulation_n5_profile_ref_mismatch")
        if self.materialization.profile_hash != self.profile.content_hash:
            raise ValueError("candidate_simulation_n5_profile_hash_mismatch")
        if (
            self.materialization.source_handoff_ref != self.n4_source_ref
            or self.materialization.candidate_id != self.original_candidate_id
            or self.materialization.original_candidate_hash != self.original_candidate_hash
            or self.materialization.original_atom_hash != self.original_n4_atom_hash
            or self.materialization.context_job_ref != self.context_job_ref
        ):
            raise ValueError("candidate_simulation_n5_source_binding_mismatch")
        if self.n5 != self.profile.n5:
            raise ValueError("candidate_simulation_n5_config_mismatch")
        expected = gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_simulation_n5_input_content_hash_mismatch")
        return self


class CandidateSimulationExecutionV2(_StrictModel):
    """Historical binding from one admitted N5 input to its persisted result."""

    schema_version: Literal["policyos.runtime.candidate_simulation.execution.v2"] = (
        "policyos.runtime.candidate_simulation.execution.v2"
    )
    authority_purpose: Literal["candidate_scenario_n5_only"] = "candidate_scenario_n5_only"
    n5_input_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    n4_source_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    context_job_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    profile_config_ref: str = Field(..., min_length=1, strict=True)
    job_id: str = Field(..., min_length=1, strict=True)
    run_id: str = Field(..., min_length=1, strict=True)
    tenant_id: str = Field(..., min_length=1, strict=True)
    cell_id: str = Field(..., min_length=1, strict=True)
    original_candidate_id: str = Field(..., min_length=1, strict=True)
    original_candidate_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    original_n4_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    derived_n5_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    problem_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    world_model_record_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    n5_result_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    n5_result_content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    k_world_ref_before: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    k_world_ref_after: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_execution(self) -> CandidateSimulationExecutionV2:
        if self.k_world_ref_before != self.k_world_ref_after:
            raise ValueError("candidate_simulation_execution_changed_k_world")
        expected = gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_simulation_execution_content_hash_mismatch")
        return self


class CandidateSimulationN5InputV3(_StrictModel):
    """N5 admission with selector-preserving source and context lineage."""

    schema_version: Literal["policyos.runtime.candidate_simulation.n5_input.v3"] = (
        "policyos.runtime.candidate_simulation.n5_input.v3"
    )
    authority_purpose: Literal["candidate_scenario_n5_only"] = "candidate_scenario_n5_only"
    source_role: Literal["runtime-config:candidate-simulation"] = (
        "runtime-config:candidate-simulation"
    )
    profile: CandidateSimulationScenarioProfile
    profile_config_ref: str = Field(..., min_length=1, strict=True)
    n4_source_ref: ArtifactRef
    context_job_ref: ArtifactRef
    job_id: str = Field(..., min_length=1, strict=True)
    run_id: str = Field(..., min_length=1, strict=True)
    tenant_id: str = Field(..., min_length=1, strict=True)
    cell_id: str = Field(..., min_length=1, strict=True)
    original_candidate_id: str = Field(..., min_length=1, strict=True)
    original_candidate_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    original_n4_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    outcome_variable: str = Field(..., min_length=1, strict=True)
    materialization: CandidateScenarioMaterializationV2
    n5: CandidateScenarioN5Config
    content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_bindings(self) -> CandidateSimulationN5InputV3:
        if self.profile_config_ref != candidate_simulation_profile_ref(self.profile):
            raise ValueError("candidate_simulation_n5_profile_ref_mismatch")
        if self.materialization.profile_hash != self.profile.content_hash:
            raise ValueError("candidate_simulation_n5_profile_hash_mismatch")
        if (
            artifact_ref_identity_key(self.materialization.source_handoff_ref)
            != artifact_ref_identity_key(self.n4_source_ref)
            or artifact_ref_identity_key(self.materialization.context_job_ref)
            != artifact_ref_identity_key(self.context_job_ref)
            or self.materialization.candidate_id != self.original_candidate_id
            or self.materialization.original_candidate_hash != self.original_candidate_hash
            or self.materialization.original_atom_hash != self.original_n4_atom_hash
        ):
            raise ValueError("candidate_simulation_n5_source_binding_mismatch")
        if (
            self.n4_source_ref.kind != "runtime.generation_source_handoff"
            or self.n4_source_ref.media_type != "application/json"
            or self.context_job_ref.kind != "runtime.quality.cycle_substrate_context_job"
            or self.context_job_ref.media_type != "application/json"
        ):
            raise ValueError("candidate_simulation_n5_source_kind_mismatch")
        if self.n5 != self.profile.n5:
            raise ValueError("candidate_simulation_n5_config_mismatch")
        expected = gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_simulation_n5_input_content_hash_mismatch")
        return self


class CandidateSimulationN5InputV4(_StrictModel):
    """N5 admission for the versioned proposal-profile source lane."""

    schema_version: Literal["policyos.runtime.candidate_simulation.n5_input.v4"] = (
        "policyos.runtime.candidate_simulation.n5_input.v4"
    )
    authority_purpose: Literal["candidate_scenario_n5_only"] = "candidate_scenario_n5_only"
    source_role: Literal["runtime-config:candidate-simulation"] = (
        "runtime-config:candidate-simulation"
    )
    profile: CandidateSimulationScenarioProfile
    profile_config_ref: str = Field(..., min_length=1, strict=True)
    n4_source_ref: ArtifactRef
    context_job_ref: ArtifactRef
    job_id: str = Field(..., min_length=1, strict=True)
    run_id: str = Field(..., min_length=1, strict=True)
    tenant_id: str = Field(..., min_length=1, strict=True)
    cell_id: str = Field(..., min_length=1, strict=True)
    original_candidate_id: str = Field(..., min_length=1, strict=True)
    original_candidate_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    original_n4_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    outcome_variable: str = Field(..., min_length=1, strict=True)
    materialization: CandidateScenarioMaterializationV3
    n5: CandidateScenarioN5Config
    content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_bindings(self) -> CandidateSimulationN5InputV4:
        if self.profile_config_ref != candidate_simulation_profile_ref(self.profile):
            raise ValueError("candidate_simulation_n5_profile_ref_mismatch")
        if self.materialization.profile_hash != self.profile.content_hash:
            raise ValueError("candidate_simulation_n5_profile_hash_mismatch")
        if (
            artifact_ref_identity_key(self.materialization.n4_source_ref)
            != artifact_ref_identity_key(self.n4_source_ref)
            or artifact_ref_identity_key(self.materialization.context_job_ref)
            != artifact_ref_identity_key(self.context_job_ref)
            or self.materialization.candidate_id != self.original_candidate_id
            or self.materialization.original_candidate_hash != self.original_candidate_hash
            or self.materialization.original_atom_hash != self.original_n4_atom_hash
        ):
            raise ValueError("candidate_simulation_n5_source_binding_mismatch")
        if (
            self.n4_source_ref.kind != "runtime.quality.n4_candidate_scenario_source"
            or self.n4_source_ref.media_type != "application/json"
            or self.context_job_ref.kind != "runtime.quality.cycle_substrate_context_job"
            or self.context_job_ref.media_type != "application/json"
        ):
            raise ValueError("candidate_simulation_n5_source_kind_mismatch")
        if self.n5 != self.profile.n5:
            raise ValueError("candidate_simulation_n5_config_mismatch")
        expected = gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_simulation_n5_input_content_hash_mismatch")
        return self


class CandidateSimulationN5InputV5(_StrictModel):
    """N5 admission retaining the selected synthetic model and CAS views."""

    schema_version: Literal["policyos.runtime.candidate_simulation.n5_input.v5"] = (
        "policyos.runtime.candidate_simulation.n5_input.v5"
    )
    authority_purpose: Literal["candidate_scenario_n5_only"] = "candidate_scenario_n5_only"
    source_role: Literal["runtime-config:candidate-simulation"] = (
        "runtime-config:candidate-simulation"
    )
    profile: CandidateSimulationScenarioProfile
    profile_config_ref: str = Field(..., min_length=1, strict=True)
    n4_source_ref: ArtifactRef
    context_job_ref: ArtifactRef
    model_declaration_ref: ArtifactRef
    ncm_ref: ArtifactRef
    job_id: str = Field(..., min_length=1, strict=True)
    run_id: str = Field(..., min_length=1, strict=True)
    tenant_id: str = Field(..., min_length=1, strict=True)
    cell_id: str = Field(..., min_length=1, strict=True)
    original_candidate_id: str = Field(..., min_length=1, strict=True)
    original_candidate_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    original_n4_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    outcome_variable: str = Field(..., min_length=1, strict=True)
    materialization: CandidateScenarioMaterializationV4
    n5: CandidateScenarioN5Config
    content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_bindings(self) -> CandidateSimulationN5InputV5:
        if self.profile_config_ref != candidate_simulation_profile_ref(self.profile):
            raise ValueError("candidate_simulation_n5_profile_ref_mismatch")
        if self.n5 != self.profile.n5:
            raise ValueError("candidate_simulation_n5_config_mismatch")
        refs = (
            (self.n4_source_ref, self.materialization.n4_source_ref),
            (self.context_job_ref, self.materialization.context_job_ref),
            (self.model_declaration_ref, self.materialization.model_declaration_ref),
            (self.ncm_ref, self.materialization.ncm_ref),
        )
        if any(
            artifact_ref_identity_key(left) != artifact_ref_identity_key(right)
            for left, right in refs
        ):
            raise ValueError("candidate_simulation_n5_selected_view_mismatch")
        if (
            self.n4_source_ref.kind != "runtime.quality.n4_candidate_scenario_source"
            or self.context_job_ref.kind != "runtime.quality.cycle_substrate_context_job"
            or self.model_declaration_ref.kind
            != "runtime.quality.candidate_simulation_model_declaration"
            or self.ncm_ref.kind != "ir.ncm_spec"
            or any(ref.media_type != "application/json" for ref, _ in refs)
            or self.materialization.profile_hash != self.profile.content_hash
            or self.materialization.candidate_id != self.original_candidate_id
            or self.materialization.original_candidate_hash != self.original_candidate_hash
            or self.materialization.original_atom_hash != self.original_n4_atom_hash
            or self.materialization.outcome_variable != self.outcome_variable
        ):
            raise ValueError("candidate_simulation_n5_source_binding_mismatch")
        if (
            self.materialization.target_world_slot
            != self.materialization.derived_n5_atom.causal_do_expr.write_variables[0]
        ):
            raise ValueError("candidate_simulation_n5_selected_target_mismatch")
        expected = gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_simulation_n5_input_content_hash_mismatch")
        return self


class CandidateSimulationExecutionV3(_StrictModel):
    """Replayable candidate-only execution with all selected CAS views retained."""

    schema_version: Literal["policyos.runtime.candidate_simulation.execution.v3"] = (
        "policyos.runtime.candidate_simulation.execution.v3"
    )
    authority_purpose: Literal["candidate_scenario_n5_only"] = "candidate_scenario_n5_only"
    n5_input_ref: ArtifactRef
    n4_source_ref: ArtifactRef
    context_job_ref: ArtifactRef
    profile_config_ref: str = Field(..., min_length=1, strict=True)
    job_id: str = Field(..., min_length=1, strict=True)
    run_id: str = Field(..., min_length=1, strict=True)
    tenant_id: str = Field(..., min_length=1, strict=True)
    cell_id: str = Field(..., min_length=1, strict=True)
    original_candidate_id: str = Field(..., min_length=1, strict=True)
    original_candidate_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    original_n4_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    derived_n5_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    problem_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    world_model_record_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    n5_result_ref: ArtifactRef
    n5_result_content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    k_world_ref_before: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    k_world_ref_after: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_execution(self) -> CandidateSimulationExecutionV3:
        if self.k_world_ref_before != self.k_world_ref_after:
            raise ValueError("candidate_simulation_execution_changed_k_world")
        if (
            self.n5_input_ref.kind != "runtime.quality.candidate_simulation_n5_input"
            or self.n5_input_ref.media_type != "application/json"
            or self.n4_source_ref.kind != "runtime.generation_source_handoff"
            or self.n4_source_ref.media_type != "application/json"
            or self.context_job_ref.kind != "runtime.quality.cycle_substrate_context_job"
            or self.context_job_ref.media_type != "application/json"
            or self.n5_result_ref.kind != "polisyos.runtime.joint_simulation_result"
            or self.n5_result_ref.media_type != "application/json"
        ):
            raise ValueError("candidate_simulation_execution_owner_kind_mismatch")
        expected = gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_simulation_execution_content_hash_mismatch")
        return self


class CandidateSimulationExecutionV4(_StrictModel):
    """Replayable candidate-only execution over the proposal-specific source."""

    schema_version: Literal["policyos.runtime.candidate_simulation.execution.v4"] = (
        "policyos.runtime.candidate_simulation.execution.v4"
    )
    authority_purpose: Literal["candidate_scenario_n5_only"] = "candidate_scenario_n5_only"
    n5_input_ref: ArtifactRef
    n4_source_ref: ArtifactRef
    context_job_ref: ArtifactRef
    profile_config_ref: str = Field(..., min_length=1, strict=True)
    job_id: str = Field(..., min_length=1, strict=True)
    run_id: str = Field(..., min_length=1, strict=True)
    tenant_id: str = Field(..., min_length=1, strict=True)
    cell_id: str = Field(..., min_length=1, strict=True)
    original_candidate_id: str = Field(..., min_length=1, strict=True)
    original_candidate_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    original_n4_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    derived_n5_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    problem_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    world_model_record_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    n5_result_ref: ArtifactRef
    n5_result_content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    k_world_ref_before: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    k_world_ref_after: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_execution(self) -> CandidateSimulationExecutionV4:
        if self.k_world_ref_before != self.k_world_ref_after:
            raise ValueError("candidate_simulation_execution_changed_k_world")
        if (
            self.n5_input_ref.kind != "runtime.quality.candidate_simulation_n5_input"
            or self.n5_input_ref.media_type != "application/json"
            or self.n4_source_ref.kind != "runtime.quality.n4_candidate_scenario_source"
            or self.n4_source_ref.media_type != "application/json"
            or self.context_job_ref.kind != "runtime.quality.cycle_substrate_context_job"
            or self.context_job_ref.media_type != "application/json"
            or self.n5_result_ref.kind != "polisyos.runtime.joint_simulation_result"
            or self.n5_result_ref.media_type != "application/json"
        ):
            raise ValueError("candidate_simulation_execution_owner_kind_mismatch")
        expected = gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_simulation_execution_content_hash_mismatch")
        return self


class CandidateSimulationExecutionV5(_StrictModel):
    """Replayable N5 execution retaining every selected source/model/result view."""

    schema_version: Literal["policyos.runtime.candidate_simulation.execution.v5"] = (
        "policyos.runtime.candidate_simulation.execution.v5"
    )
    authority_purpose: Literal["candidate_scenario_n5_only"] = "candidate_scenario_n5_only"
    n5_input_ref: ArtifactRef
    n4_source_ref: ArtifactRef
    context_job_ref: ArtifactRef
    model_declaration_ref: ArtifactRef
    ncm_ref: ArtifactRef
    profile_config_ref: str = Field(..., min_length=1, strict=True)
    job_id: str = Field(..., min_length=1, strict=True)
    run_id: str = Field(..., min_length=1, strict=True)
    tenant_id: str = Field(..., min_length=1, strict=True)
    cell_id: str = Field(..., min_length=1, strict=True)
    original_candidate_id: str = Field(..., min_length=1, strict=True)
    original_candidate_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    original_n4_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    derived_n5_atom_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    problem_ref: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    world_model_record_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    n5_result_ref: ArtifactRef
    n5_result_content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    k_world_ref_before: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    k_world_ref_after: str = Field(..., pattern=_HASH_PATTERN, strict=True)
    content_hash: str = Field(..., pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_execution(self) -> CandidateSimulationExecutionV5:
        if self.k_world_ref_before != self.k_world_ref_after:
            raise ValueError("candidate_simulation_execution_changed_k_world")
        if any(
            ref.kind != kind or ref.media_type != "application/json"
            for ref, kind in (
                (self.n5_input_ref, "runtime.quality.candidate_simulation_n5_input"),
                (self.n4_source_ref, "runtime.quality.n4_candidate_scenario_source"),
                (self.context_job_ref, "runtime.quality.cycle_substrate_context_job"),
                (self.model_declaration_ref, "runtime.quality.candidate_simulation_model_declaration"),
                (self.ncm_ref, "ir.ncm_spec"),
                (self.n5_result_ref, "polisyos.runtime.joint_simulation_result"),
            )
        ):
            raise ValueError("candidate_simulation_execution_owner_kind_mismatch")
        expected = gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("candidate_simulation_execution_content_hash_mismatch")
        return self


def candidate_simulation_profile_ref(
    profile: CandidateSimulationScenarioProfile,
) -> str:
    """Return the stable reference for the exact configured profile bytes."""

    return f"runtime-config:candidate-simulation/{profile.profile_id}@{profile.content_hash}"


def content_hash_for_candidate_simulation(payload: dict[str, object]) -> str:
    """Hash one custom candidate-simulation record before model validation."""

    return gy_content_hash(payload)
