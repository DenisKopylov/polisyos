"""Content-bound substrate evidence shared by one generation-cycle run.

This module owns the intake envelope only. It does not load a domain pack,
construct a second substrate registry, or grant authority to candidate levers
or transport profiles.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any, Literal, Protocol, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_core import to_jsonable_python

from polisyos.core import artifacts, canon
from polisyos.core.artifacts.manifest import (
    ArtifactSameInputClosureInfo,
    ArtifactTenantContextInfo,
)
from polisyos.core.security import (
    get_current_access_scope_or_none,
    get_current_cell_id,
    get_current_tenant_id_or_none,
)
from polisyos.pdc import WORLD_MODEL_RECORD_SCHEMA_V2_VERSION, gy_content_hash
from polisyos.runtime.quality.design_problem import (
    DESIGN_PROBLEM_V1_SCHEMA_VERSION,
    DESIGN_PROBLEM_V2_SCHEMA_VERSION,
    DESIGN_PROBLEM_V3_SCHEMA_VERSION,
    DesignProblem,
    _QualifiedOutcomeOfInterestV3,
)
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
CYCLE_SUBSTRATE_CONTEXT_JOB_SCHEMA = (
    "policyos.runtime.cycle_substrate_context_job_artifact.v1"
)
CYCLE_SUBSTRATE_CONTEXT_JOB_KIND = "runtime.quality.cycle_substrate_context_job"
CYCLE_SUBSTRATE_CONTEXT_JOB_SCHEMA_VERSION = "1.0"
CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA = (
    "policyos.runtime.cycle_substrate_context_job_artifact.v2"
)
CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA_VERSION = "2.0"
CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA = (
    "policyos.runtime.cycle_substrate_context_job_artifact.v3"
)
CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA_VERSION = "3.0"
_HASH_PATTERN = r"^sha256:[0-9a-f]{64}$"
_CONTEXT_JOB_CANON = canon.CanonSpec(forbid_floats=False, exclude_none=False)
_REQUIRED_AUTHORITY_DENIALS = frozenset(
    {
        "grounding_authority",
        "transport_authority",
        "promotion_authority",
    }
)
_REQUIRED_CONTEXT_JOB_LIMITATIONS = frozenset(
    {
        "design_problem_population_identity_missing",
        "design_problem_time_roles_not_reconciled",
        "owner_profile_admission_missing",
        "s8_current_value_authority_missing",
    }
)
_VERIFIED_NL_EXECUTION_OWNER_ISSUER = object()
# This v1 artifact embeds only model versions whose field trees are frozen
# below. The L6 owner explicitly supports both its v1 and v2 bundle formats.
_CONTEXT_JOB_V1_SUPPORTED_MODEL_VERSIONS: dict[str, frozenset[str]] = {
    "polisyos.runtime.quality.design_problem.DesignProblem": frozenset(
        {
            DESIGN_PROBLEM_V1_SCHEMA_VERSION,
            DESIGN_PROBLEM_V2_SCHEMA_VERSION,
            DESIGN_PROBLEM_V3_SCHEMA_VERSION,
        }
    ),
    "polisyos.runtime.quality.cycle_substrate.CycleSubstrateContext": frozenset(
        {CYCLE_SUBSTRATE_CONTEXT_SCHEMA_VERSION}
    ),
    "polisyos.runtime.quality.substrate_registry.SubstrateRegistry": frozenset(
        {"policyos.runtime.substrate_registry.v1"}
    ),
    "polisyos.pdc._impl.world_model_record.WorldModelRecord": frozenset(
        {"policyos.runtime.world_model_record.v1"}
    ),
    "polisyos.runtime.quality.intervention_substrate.InterventionSubstrateBundle": frozenset(
        {
            "policyos.runtime.intervention_substrate_lift.v1",
            "policyos.runtime.intervention_substrate_lift.v2",
        }
    ),
}
_CONTEXT_JOB_V1_MODEL_FIELDS: dict[str, tuple[str, ...]] = {
    "polisyos.runtime.quality.cycle_substrate.CycleSubstrateContextJobArtifact": (
        "schema_version",
        "authority_purpose",
        "status",
        "profile_admission_status",
        "s8_status",
        "run_id",
        "job_id",
        "tenant_id",
        "cell_id",
        "design_problem_ref",
        "problem",
        "context",
        "limitation_codes",
        "content_hash",
    ),
    "polisyos.runtime.quality.design_problem.DesignProblem": (
        "schema_version",
        "design_problem_id",
        "problem_statement",
        "domain",
        "nl_provenance",
        "authority_profile",
        "jurisdiction_time",
        "objectives",
        "constraints",
        "stakeholders",
        "outcome_of_interest",
        "candidate_lever_space",
        "evidence_acquisition_needs",
        "model_spec_ref",
        "ir_problem_frame_ref",
        "policy_request_frame_ref",
        "runtime_hints",
    ),
    "polisyos.runtime.quality.design_problem.NLProvenance": (
        "raw_request", "source_surface", "source_context"
    ),
    "polisyos.runtime.quality.design_problem.AuthorityProfile": (
        "requester_authority",
        "requested_authority_level",
        "mandate",
        "authority_refs",
    ),
    "polisyos.runtime.quality.design_problem.JurisdictionTimeSemantics": (
        "region", "valid_time", "as_of", "policy_time", "data_time", "time_semantics"
    ),
    "polisyos.ir.kernel.time_semantics.TimeSemantics": (
        "frequency", "start_date", "step_count", "end_date", "notes"
    ),
    "polisyos.runtime.quality.design_problem.DesignObjective": (
        "objective_id", "description", "metric_id", "direction"
    ),
    "polisyos.runtime.quality.design_problem.DesignConstraint": (
        "constraint_id",
        "description",
        "hard",
        "admissibility_basis",
        "source_text",
        "evidence_ref",
    ),
    "polisyos.runtime.quality.design_problem.DesignStakeholder": (
        "stakeholder_id", "name", "role"
    ),
    "polisyos.runtime.quality.design_problem.OutcomeOfInterest": (
        "target_variable", "metric_id", "estimand", "direction"
    ),
    "polisyos.runtime.quality.design_problem.CandidateLeverSpace": (
        "allowed_operator_kinds", "candidate_levers"
    ),
    "polisyos.runtime.quality.design_problem.CandidateLever": (
        "lever_id", "operator_kind", "instrument", "target_slot"
    ),
    "polisyos.runtime.quality.design_problem.EvidenceAcquisitionNeeds": ("needs",),
    "polisyos.runtime.quality.design_problem.EvidenceNeed": (
        "need_id", "question", "required_for", "status", "source_hint", "artifact_ref"
    ),
    "polisyos.runtime.quality.cycle_substrate.CycleSubstrateContext": (
        "schema_version",
        "design_problem_ref",
        "domain",
        "source_pack_content_hash",
        "substrate_input_content_hash",
        "substrate_registry",
        "substrate_registry_content_hash",
        "selected_registry_entry_hashes",
        "world_model_record",
        "world_model_record_content_hash",
        "intervention_substrate",
        "candidate_levers",
        "transport_context",
        "authority_purpose",
        "may_not_use_for",
        "context_binding_hash",
        "content_hash",
    ),
    "polisyos.runtime.quality.cycle_substrate.CandidateLeverEvidence": (
        "lever_id",
        "instrument",
        "target_concept",
        "status",
        "entry_content_hash",
        "substrate_input_content_hash",
        "selected_registry_entry_hash",
        "context_binding_hash",
        "source_refs",
    ),
    "polisyos.runtime.quality.cycle_substrate.TransportContextEvidence": (
        "status",
        "source_context_id",
        "target_context_id",
        "source_profile_content_hash",
        "target_profile_content_hash",
        "substrate_input_content_hash",
        "context_binding_hash",
        "covariates",
    ),
    "polisyos.runtime.quality.cycle_substrate.TransportCovariateObservation": (
        "canonical_var",
        "source_value",
        "target_value",
        "source_row_content_hash",
        "target_row_content_hash",
    ),
    "polisyos.runtime.quality.substrate_registry.SubstrateRegistry": (
        "substrate_version_id",
        "schema_version",
        "producer_ref",
        "content_hash",
        "source_catalog_refs",
        "entries",
    ),
    "polisyos.runtime.quality.substrate_registry.SubstrateRegistryEntry": (
        "source_id",
        "family_id",
        "layer",
        "coverage",
        "trust_tier",
        "identification_mode",
        "schema_regime",
        "data_version",
        "snapshot_id",
        "source_snapshot_id",
        "provenance_refs",
        "authority_refs",
        "entry_content_hash",
    ),
    "polisyos.runtime.quality.substrate_registry.SubstrateCoverage": (
        "coverage_score",
        "coverage_kind",
        "coverage_rule_ref",
        "dataset_count",
        "metric_binding_count",
        "observation_count",
        "quality_scores",
        "coverage_dimensions",
    ),
    "polisyos.runtime.quality.substrate_registry.SubstrateTrustTier": (
        "tier",
        "trust_cap",
        "trust_multiplier",
        "min_coverage",
        "max_coverage",
        "authority_ref",
    ),
    "polisyos.runtime.quality.substrate_registry.SubstrateSchemaRegime": (
        "schema_regime_id",
        "authority_ref",
        "effective_start",
        "effective_end",
        "boundary_buffer_periods",
        "source_version",
    ),
    "polisyos.pdc._impl.world_model_record.WorldModelRecord": (
        "world_model_record_id",
        "schema_version",
        "authority_status",
        "created_at",
        "producer_ref",
        "content_hash",
        "region_or_jurisdiction",
        "population_scope",
        "policy_domain",
        "valid_time_scope",
        "tx_time_scope",
        "resolution",
        "branch_mode",
        "fabric_world_ref",
        "data_forge_binding_ref",
        "simulation_model_ref",
        "foundry_binding_ref",
        "skg_causal_prior_ref",
        "substrate_registry_ref",
        "policy_slot_map",
        "limitations",
        "deployment_update_refs",
    ),
    "polisyos.pdc._impl.world_model_record.FabricWorldRef": (
        "snapshot_root",
        "snapshot_id",
        "branch",
        "as_of_valid_time",
        "as_of_tx_time",
        "world_query_policy",
        "provenance_manifest_ref",
        "content_query_digest",
        "content_query_row_count",
    ),
    "polisyos.pdc._impl.world_model_record.DataForgeBindingRef": (
        "snapshot_id",
        "release_id",
        "role",
        "read_api_identity",
        "snapshot_ref",
        "merkle_root",
        "data_hash",
        "claim_requirement_bindings",
        "quality_gate_refs",
        "lineage_refs",
        "provenance_manifest_ref",
        "binding_path",
    ),
    "polisyos.pdc._impl.world_model_record.SimulationModelRef": (
        "model_spec_ref",
        "model_spec_hash",
        "model_id",
        "data_snapshot_ref",
        "registry_bundle_ref",
        "mechanism_refs",
        "gcm_refs",
        "ncm_refs",
        "program_graph_refs",
        "assumptions",
        "fidelity_level",
        "calibration_ref",
        "calibrated",
    ),
    "polisyos.pdc._impl.world_model_record.FoundryBindingRef": (
        "input_bindings_ref",
        "bound_state_snapshot_ref",
        "mapping_rules_ref",
        "state_slot_digest",
    ),
    "polisyos.pdc._impl.world_model_record.SkgCausalPriorRef": (
        "skg_snapshot_ref",
        "skg_version_id",
        "source_data_snapshot_id",
        "edge_prior_refs",
        "transport_score_refs",
        "query_trace_refs",
    ),
    "polisyos.pdc._impl.world_model_record.SubstrateRegistryRef": (
        "substrate_version_id", "content_hash", "registry_artifact_ref", "resolved_entries"
    ),
    "polisyos.pdc._impl.world_model_record.ResolvedSubstrateEntryRef": (
        "source_id",
        "family_id",
        "layer",
        "coverage_score",
        "trust_tier",
        "trust_cap",
        "identification_mode",
        "schema_regime_id",
        "data_version",
        "snapshot_id",
        "source_snapshot_id",
        "entry_content_hash",
    ),
    "polisyos.pdc._impl.world_model_record.PolicySlotBinding": (
        "slot_id", "state_path", "unit", "entity_scope", "temporal_granularity"
    ),
    "polisyos.pdc._impl.world_model_record.WorldModelLimitations": (
        "unavailable_data",
        "transport_limits",
        "calibration_envelope_status",
        "unresolved_conflicts",
        "admissibility_blockers",
    ),
    "polisyos.pdc._impl.world_model_record.DeploymentUpdateRefs": (
        "phase",
        "feedback_refs",
        "reissue_refs",
        "refute_refs",
        "incident_refs",
        "posterior_update_refs",
    ),
    "polisyos.runtime.quality.intervention_substrate.InterventionSubstrateBundle": (
        "schema_version",
        "knob_dictionary",
        "lex_intervention_map",
        "observation_manifest",
        "policy_scenario_templates",
        "slot_family_manifest",
        "world_mechanism_manifest",
        "lex_authority_manifest",
        "owner_authority_manifest",
        "source_refs",
        "source_content_hashes",
        "content_hash",
    ),
}
# Version 2 is a separately frozen field tree. Its new qualified outcome
# owner is registered by exact type; later v1 map changes cannot widen V2.
_CONTEXT_JOB_V2_SUPPORTED_MODEL_VERSIONS: dict[str, frozenset[str]] = {
    "polisyos.runtime.quality.cycle_substrate.CycleSubstrateContext": frozenset(
        {CYCLE_SUBSTRATE_CONTEXT_SCHEMA_VERSION}
    ),
    "polisyos.runtime.quality.substrate_registry.SubstrateRegistry": frozenset(
        {"policyos.runtime.substrate_registry.v1"}
    ),
    "polisyos.pdc._impl.world_model_record.WorldModelRecord": frozenset(
        {"policyos.runtime.world_model_record.v1"}
    ),
    "polisyos.runtime.quality.intervention_substrate.InterventionSubstrateBundle": frozenset(
        {
            "policyos.runtime.intervention_substrate_lift.v1",
            "policyos.runtime.intervention_substrate_lift.v2",
        }
    ),
}
_CONTEXT_JOB_V2_MODEL_FIELDS: dict[str, tuple[str, ...]] = {
    "polisyos.runtime.quality.design_problem.NLProvenance": (
        "raw_request", "source_surface", "source_context"
    ),
    "polisyos.runtime.quality.design_problem.AuthorityProfile": (
        "requester_authority",
        "requested_authority_level",
        "mandate",
        "authority_refs",
    ),
    "polisyos.runtime.quality.design_problem.JurisdictionTimeSemantics": (
        "region", "valid_time", "as_of", "policy_time", "data_time", "time_semantics"
    ),
    "polisyos.ir.kernel.time_semantics.TimeSemantics": (
        "frequency", "start_date", "step_count", "end_date", "notes"
    ),
    "polisyos.runtime.quality.design_problem.DesignObjective": (
        "objective_id", "description", "metric_id", "direction"
    ),
    "polisyos.runtime.quality.design_problem.DesignConstraint": (
        "constraint_id",
        "description",
        "hard",
        "admissibility_basis",
        "source_text",
        "evidence_ref",
    ),
    "polisyos.runtime.quality.design_problem.DesignStakeholder": (
        "stakeholder_id", "name", "role"
    ),
    "polisyos.runtime.quality.design_problem.OutcomeOfInterest": (
        "target_variable", "metric_id", "estimand", "direction"
    ),
    "polisyos.runtime.quality.design_problem.CandidateLeverSpace": (
        "allowed_operator_kinds", "candidate_levers"
    ),
    "polisyos.runtime.quality.design_problem.CandidateLever": (
        "lever_id", "operator_kind", "instrument", "target_slot"
    ),
    "polisyos.runtime.quality.design_problem.EvidenceAcquisitionNeeds": ("needs",),
    "polisyos.runtime.quality.design_problem.EvidenceNeed": (
        "need_id", "question", "required_for", "status", "source_hint", "artifact_ref"
    ),
    "polisyos.runtime.quality.cycle_substrate.CycleSubstrateContext": (
        "schema_version",
        "design_problem_ref",
        "domain",
        "source_pack_content_hash",
        "substrate_input_content_hash",
        "substrate_registry",
        "substrate_registry_content_hash",
        "selected_registry_entry_hashes",
        "world_model_record",
        "world_model_record_content_hash",
        "intervention_substrate",
        "candidate_levers",
        "transport_context",
        "authority_purpose",
        "may_not_use_for",
        "context_binding_hash",
        "content_hash",
    ),
    "polisyos.runtime.quality.cycle_substrate.CandidateLeverEvidence": (
        "lever_id",
        "instrument",
        "target_concept",
        "status",
        "entry_content_hash",
        "substrate_input_content_hash",
        "selected_registry_entry_hash",
        "context_binding_hash",
        "source_refs",
    ),
    "polisyos.runtime.quality.cycle_substrate.TransportContextEvidence": (
        "status",
        "source_context_id",
        "target_context_id",
        "source_profile_content_hash",
        "target_profile_content_hash",
        "substrate_input_content_hash",
        "context_binding_hash",
        "covariates",
    ),
    "polisyos.runtime.quality.cycle_substrate.TransportCovariateObservation": (
        "canonical_var",
        "source_value",
        "target_value",
        "source_row_content_hash",
        "target_row_content_hash",
    ),
    "polisyos.runtime.quality.substrate_registry.SubstrateRegistry": (
        "substrate_version_id",
        "schema_version",
        "producer_ref",
        "content_hash",
        "source_catalog_refs",
        "entries",
    ),
    "polisyos.runtime.quality.substrate_registry.SubstrateRegistryEntry": (
        "source_id",
        "family_id",
        "layer",
        "coverage",
        "trust_tier",
        "identification_mode",
        "schema_regime",
        "data_version",
        "snapshot_id",
        "source_snapshot_id",
        "provenance_refs",
        "authority_refs",
        "entry_content_hash",
    ),
    "polisyos.runtime.quality.substrate_registry.SubstrateCoverage": (
        "coverage_score",
        "coverage_kind",
        "coverage_rule_ref",
        "dataset_count",
        "metric_binding_count",
        "observation_count",
        "quality_scores",
        "coverage_dimensions",
    ),
    "polisyos.runtime.quality.substrate_registry.SubstrateTrustTier": (
        "tier",
        "trust_cap",
        "trust_multiplier",
        "min_coverage",
        "max_coverage",
        "authority_ref",
    ),
    "polisyos.runtime.quality.substrate_registry.SubstrateSchemaRegime": (
        "schema_regime_id",
        "authority_ref",
        "effective_start",
        "effective_end",
        "boundary_buffer_periods",
        "source_version",
    ),
    "polisyos.pdc._impl.world_model_record.WorldModelRecord": (
        "world_model_record_id",
        "schema_version",
        "authority_status",
        "created_at",
        "producer_ref",
        "content_hash",
        "region_or_jurisdiction",
        "population_scope",
        "policy_domain",
        "valid_time_scope",
        "tx_time_scope",
        "resolution",
        "branch_mode",
        "fabric_world_ref",
        "data_forge_binding_ref",
        "simulation_model_ref",
        "foundry_binding_ref",
        "skg_causal_prior_ref",
        "substrate_registry_ref",
        "policy_slot_map",
        "limitations",
        "deployment_update_refs",
    ),
    "polisyos.pdc._impl.world_model_record.FabricWorldRef": (
        "snapshot_root",
        "snapshot_id",
        "branch",
        "as_of_valid_time",
        "as_of_tx_time",
        "world_query_policy",
        "provenance_manifest_ref",
        "content_query_digest",
        "content_query_row_count",
    ),
    "polisyos.pdc._impl.world_model_record.DataForgeBindingRef": (
        "snapshot_id",
        "release_id",
        "role",
        "read_api_identity",
        "snapshot_ref",
        "merkle_root",
        "data_hash",
        "claim_requirement_bindings",
        "quality_gate_refs",
        "lineage_refs",
        "provenance_manifest_ref",
        "binding_path",
    ),
    "polisyos.pdc._impl.world_model_record.SimulationModelRef": (
        "model_spec_ref",
        "model_spec_hash",
        "model_id",
        "data_snapshot_ref",
        "registry_bundle_ref",
        "mechanism_refs",
        "gcm_refs",
        "ncm_refs",
        "program_graph_refs",
        "assumptions",
        "fidelity_level",
        "calibration_ref",
        "calibrated",
    ),
    "polisyos.pdc._impl.world_model_record.FoundryBindingRef": (
        "input_bindings_ref",
        "bound_state_snapshot_ref",
        "mapping_rules_ref",
        "state_slot_digest",
    ),
    "polisyos.pdc._impl.world_model_record.SkgCausalPriorRef": (
        "skg_snapshot_ref",
        "skg_version_id",
        "source_data_snapshot_id",
        "edge_prior_refs",
        "transport_score_refs",
        "query_trace_refs",
    ),
    "polisyos.pdc._impl.world_model_record.SubstrateRegistryRef": (
        "substrate_version_id", "content_hash", "registry_artifact_ref", "resolved_entries"
    ),
    "polisyos.pdc._impl.world_model_record.ResolvedSubstrateEntryRef": (
        "source_id",
        "family_id",
        "layer",
        "coverage_score",
        "trust_tier",
        "trust_cap",
        "identification_mode",
        "schema_regime_id",
        "data_version",
        "snapshot_id",
        "source_snapshot_id",
        "entry_content_hash",
    ),
    "polisyos.pdc._impl.world_model_record.PolicySlotBinding": (
        "slot_id", "state_path", "unit", "entity_scope", "temporal_granularity"
    ),
    "polisyos.pdc._impl.world_model_record.WorldModelLimitations": (
        "unavailable_data",
        "transport_limits",
        "calibration_envelope_status",
        "unresolved_conflicts",
        "admissibility_blockers",
    ),
    "polisyos.pdc._impl.world_model_record.DeploymentUpdateRefs": (
        "phase",
        "feedback_refs",
        "reissue_refs",
        "refute_refs",
        "incident_refs",
        "posterior_update_refs",
    ),
    "polisyos.runtime.quality.intervention_substrate.InterventionSubstrateBundle": (
        "schema_version",
        "knob_dictionary",
        "lex_intervention_map",
        "observation_manifest",
        "policy_scenario_templates",
        "slot_family_manifest",
        "world_mechanism_manifest",
        "lex_authority_manifest",
        "owner_authority_manifest",
        "source_refs",
        "source_content_hashes",
        "content_hash",
    ),
}
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


class CycleSubstrateContextOwnerError(ValueError):
    """Typed failure from job-scoped candidate-context intake and replay."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


def _require_context_evidence_refreshable(
    *,
    candidate_levers: Sequence[CandidateLeverEvidence],
    transport_context: TransportContextEvidence | None,
) -> None:
    """Refuse to carry profile evidence across a changed context without reissue."""

    if candidate_levers or transport_context is not None:
        raise CycleSubstrateContextOwnerError(
            "candidate_simulation_context_evidence_refresh_not_established",
            "the profile evidence is bound to a prior context and no source-backed "
            "issuer can revalidate it for the refreshed world model",
        )


class VerifiedNLJobScope(_StrictModel):
    """Ephemeral, purpose-limited scope for replayed simulate-only NL work.

    This is not an ``AccessScope`` and is never serialized into the v1 context
    artifact. The owner still reconciles its identities to the active persisted
    worker lease and ambient tenant/cell before it writes or reads any bytes.
    """

    authority_purpose: Literal["cycle_input_candidate_only"] = (
        "cycle_input_candidate_only"
    )
    admission_status: Literal["established"]
    intent_band: Literal["simulate_only_attempt"]
    canonical_mode: Literal["simulate_only"]
    route_id: Literal["POST /api/v1/control/runs/nl"]
    route_action: Literal["control.launch_nl_run"]
    admission_surface: Literal["served_route"]
    actor_subject: str = Field(..., min_length=1)
    actor_authenticated: Literal[True]
    intent_digest: str = Field(..., pattern=_HASH_PATTERN)
    job_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    cell_id: str = Field(..., min_length=1)
    worker_id: str = Field(..., min_length=1)
    attempt: int = Field(..., ge=1)
    _issuer: object = PrivateAttr(default=None)

    @property
    def _was_issued_by_verified_nl_execution_owner(self) -> bool:
        return self._issuer is _VERIFIED_NL_EXECUTION_OWNER_ISSUER


class _CurrentControlJobRecord(Protocol):
    """Minimal persisted job identity exposed by the control-store owner."""

    job_id: str
    run_id: str | None
    submitted_by: str | None
    state: str
    lease_owner: str | None
    attempt: int


class _CurrentControlJobExecutionOwner(Protocol):
    """Resolve the authenticated worker's persisted job through its lease fence."""

    def current_execution_job_record(self) -> _CurrentControlJobRecord: ...


class CycleSubstrateContextJobArtifact(_StrictModel):
    """Bind one candidate-only context to the compiled problem and served job.

    The record carries explicit unresolved profile and value-authority limits.
    It is a candidate input handoff, never a DataState profile admission or S8
    authority receipt.
    """

    schema_version: Literal[
        "policyos.runtime.cycle_substrate_context_job_artifact.v1"
    ] = CYCLE_SUBSTRATE_CONTEXT_JOB_SCHEMA
    authority_purpose: Literal["cycle_input_candidate_only"] = (
        "cycle_input_candidate_only"
    )
    status: Literal["candidate_limited"] = "candidate_limited"
    profile_admission_status: Literal["not_established"] = "not_established"
    s8_status: Literal["blocked"] = "blocked"
    run_id: str = Field(..., min_length=1)
    job_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    cell_id: str = Field(..., min_length=1)
    design_problem_ref: str = Field(..., pattern=_HASH_PATTERN)
    problem: DesignProblem
    context: CycleSubstrateContext
    limitation_codes: tuple[str, ...]
    content_hash: str = Field(..., pattern=_HASH_PATTERN)

    @field_validator("limitation_codes")
    @classmethod
    def _required_profile_limits(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("cycle_substrate_context_job_limitation_duplicate")
        missing = _REQUIRED_CONTEXT_JOB_LIMITATIONS.difference(value)
        if missing:
            raise ValueError(
                "cycle_substrate_context_job_limitation_missing:"
                + ",".join(sorted(missing))
            )
        return value

    @model_validator(mode="after")
    def _validate_job_artifact(self) -> CycleSubstrateContextJobArtifact:
        problem_ref = _cycle_job_v1_design_problem_ref(self.problem)
        if self.design_problem_ref != problem_ref:
            raise ValueError("cycle_substrate_context_job_problem_hash_mismatch")
        context = revalidate_cycle_substrate_context(self.context)
        if context.design_problem_ref != problem_ref:
            raise ValueError("cycle_substrate_context_job_context_problem_mismatch")
        _validate_problem_world_match(self.problem, context)
        expected_hash = cycle_substrate_context_job_content_hash(self)
        if self.content_hash != expected_hash:
            raise ValueError("cycle_substrate_context_job_content_hash_mismatch")
        if context.authority_purpose != "cycle_input_candidate_only":
            raise ValueError("cycle_substrate_context_job_authority_purpose_invalid")
        if self.profile_admission_status != "not_established" or self.s8_status != "blocked":
            raise ValueError("cycle_substrate_context_job_authority_limit_removed")
        return self


class CycleSubstrateContextJobArtifactV2(_StrictModel):
    """Version 2 candidate handoff for current DesignProblem v3.

    The frozen v1 projection remains the historical serializer. This version
    records the current typed v3 model tree without changing v1 bytes or
    candidate-only authority limitations.
    """

    schema_version: Literal[
        "policyos.runtime.cycle_substrate_context_job_artifact.v2"
    ] = CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA
    authority_purpose: Literal["cycle_input_candidate_only"] = (
        "cycle_input_candidate_only"
    )
    status: Literal["candidate_limited"] = "candidate_limited"
    profile_admission_status: Literal["not_established"] = "not_established"
    s8_status: Literal["blocked"] = "blocked"
    run_id: str = Field(..., min_length=1)
    job_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    cell_id: str = Field(..., min_length=1)
    design_problem_ref: str = Field(..., pattern=_HASH_PATTERN)
    problem: DesignProblem
    context: CycleSubstrateContext
    limitation_codes: tuple[str, ...]
    content_hash: str = Field(..., pattern=_HASH_PATTERN)

    @field_validator("limitation_codes")
    @classmethod
    def _required_profile_limits(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("cycle_substrate_context_job_limitation_duplicate")
        missing = _REQUIRED_CONTEXT_JOB_LIMITATIONS.difference(value)
        if missing:
            raise ValueError(
                "cycle_substrate_context_job_limitation_missing:"
                + ",".join(sorted(missing))
            )
        return value

    @model_validator(mode="after")
    def _validate_job_artifact(self) -> CycleSubstrateContextJobArtifactV2:
        if type(self.problem) is not DesignProblem:
            raise ValueError("cycle_substrate_context_job_v2_design_problem_owner_unregistered")
        if self.problem.schema_version != DESIGN_PROBLEM_V3_SCHEMA_VERSION:
            raise ValueError("cycle_substrate_context_job_v2_design_problem_schema_unsupported")
        problem_ref = cycle_job_design_problem_ref(self.problem)
        if self.design_problem_ref != problem_ref:
            raise ValueError("cycle_substrate_context_job_problem_hash_mismatch")
        context = revalidate_cycle_substrate_context(self.context)
        if context.design_problem_ref != problem_ref:
            raise ValueError("cycle_substrate_context_job_context_problem_mismatch")
        _validate_problem_world_match(self.problem, context)
        expected_hash = cycle_substrate_context_job_content_hash(self)
        if self.content_hash != expected_hash:
            raise ValueError("cycle_substrate_context_job_content_hash_mismatch")
        if context.authority_purpose != "cycle_input_candidate_only":
            raise ValueError("cycle_substrate_context_job_authority_purpose_invalid")
        if self.profile_admission_status != "not_established" or self.s8_status != "blocked":
            raise ValueError("cycle_substrate_context_job_authority_limit_removed")
        return self


class CycleSubstrateContextJobArtifactV3(_StrictModel):
    """Version 3 handoff binding current v3 problems to WMRv2 exact views."""

    schema_version: Literal[
        "policyos.runtime.cycle_substrate_context_job_artifact.v3"
    ] = CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA
    authority_purpose: Literal["cycle_input_candidate_only"] = (
        "cycle_input_candidate_only"
    )
    status: Literal["candidate_limited"] = "candidate_limited"
    profile_admission_status: Literal["not_established"] = "not_established"
    s8_status: Literal["blocked"] = "blocked"
    run_id: str = Field(..., min_length=1)
    job_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    cell_id: str = Field(..., min_length=1)
    design_problem_ref: str = Field(..., pattern=_HASH_PATTERN)
    problem: DesignProblem
    context: CycleSubstrateContext
    limitation_codes: tuple[str, ...]
    content_hash: str = Field(..., pattern=_HASH_PATTERN)

    @field_validator("limitation_codes")
    @classmethod
    def _required_profile_limits(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("cycle_substrate_context_job_limitation_duplicate")
        missing = _REQUIRED_CONTEXT_JOB_LIMITATIONS.difference(value)
        if missing:
            raise ValueError(
                "cycle_substrate_context_job_limitation_missing:"
                + ",".join(sorted(missing))
            )
        return value

    @model_validator(mode="after")
    def _validate_job_artifact(self) -> CycleSubstrateContextJobArtifactV3:
        if type(self.problem) is not DesignProblem:
            raise ValueError("cycle_substrate_context_job_v3_design_problem_owner_unregistered")
        if self.problem.schema_version != DESIGN_PROBLEM_V3_SCHEMA_VERSION:
            raise ValueError("cycle_substrate_context_job_v3_design_problem_schema_unsupported")
        if self.context.world_model_record.schema_version != WORLD_MODEL_RECORD_SCHEMA_V2_VERSION:
            raise ValueError("cycle_substrate_context_job_v3_world_model_schema_unsupported")
        if self.context.world_model_record.artifact_views is None:
            raise ValueError("cycle_substrate_context_job_v3_world_model_views_missing")
        problem_ref = cycle_job_design_problem_ref(self.problem)
        if self.design_problem_ref != problem_ref:
            raise ValueError("cycle_substrate_context_job_problem_hash_mismatch")
        context = revalidate_cycle_substrate_context(self.context)
        if context.design_problem_ref != problem_ref:
            raise ValueError("cycle_substrate_context_job_context_problem_mismatch")
        _validate_problem_world_match(self.problem, context)
        expected_hash = cycle_substrate_context_job_content_hash(self)
        if self.content_hash != expected_hash:
            raise ValueError("cycle_substrate_context_job_content_hash_mismatch")
        if context.authority_purpose != "cycle_input_candidate_only":
            raise ValueError("cycle_substrate_context_job_authority_purpose_invalid")
        if self.profile_admission_status != "not_established" or self.s8_status != "blocked":
            raise ValueError("cycle_substrate_context_job_authority_limit_removed")
        return self


_CONTEXT_JOB_ARTIFACT_TYPES_BY_SCHEMA: dict[str, type[BaseModel]] = {
    CYCLE_SUBSTRATE_CONTEXT_JOB_SCHEMA: CycleSubstrateContextJobArtifact,
    CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA: CycleSubstrateContextJobArtifactV2,
    CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA: CycleSubstrateContextJobArtifactV3,
}


def is_supported_cycle_substrate_context_job_artifact(value: object) -> bool:
    """Check the exact schema/type pair admitted by the context-job owner."""

    if not isinstance(value, BaseModel):
        return False
    schema_version = getattr(value, "schema_version", None)
    if not isinstance(schema_version, str):
        return False
    return _CONTEXT_JOB_ARTIFACT_TYPES_BY_SCHEMA.get(schema_version) is type(value)


_CONTEXT_JOB_V2_EXACT_MODEL_FIELDS: dict[type[BaseModel], tuple[str, ...]] = {
    CycleSubstrateContextJobArtifactV2: (
        "schema_version",
        "authority_purpose",
        "status",
        "profile_admission_status",
        "s8_status",
        "run_id",
        "job_id",
        "tenant_id",
        "cell_id",
        "design_problem_ref",
        "problem",
        "context",
        "limitation_codes",
        "content_hash",
    ),
    DesignProblem: (
        "schema_version",
        "design_problem_id",
        "problem_statement",
        "domain",
        "nl_provenance",
        "authority_profile",
        "jurisdiction_time",
        "objectives",
        "constraints",
        "stakeholders",
        "outcome_of_interest",
        "candidate_lever_space",
        "evidence_acquisition_needs",
        "model_spec_ref",
        "ir_problem_frame_ref",
        "policy_request_frame_ref",
        "runtime_hints",
    ),
    _QualifiedOutcomeOfInterestV3: (
        "target_variable",
        "metric_id",
        "estimand",
        "direction",
    ),
}
_CONTEXT_JOB_V2_EXACT_MODEL_VERSIONS: dict[type[BaseModel], frozenset[str]] = {
    CycleSubstrateContextJobArtifactV2: frozenset(
        {CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA}
    ),
    DesignProblem: frozenset({DESIGN_PROBLEM_V3_SCHEMA_VERSION}),
}

# V3 is a new frozen tree. V1/V2 maps stay byte-stable; only V3 admits the
# WMRv2 view bundle and ArtifactRef selector fields.
_CONTEXT_JOB_V3_SUPPORTED_MODEL_VERSIONS = {
    **_CONTEXT_JOB_V2_SUPPORTED_MODEL_VERSIONS,
    "polisyos.pdc._impl.world_model_record.WorldModelRecord": frozenset(
        {WORLD_MODEL_RECORD_SCHEMA_V2_VERSION}
    ),
}
_CONTEXT_JOB_V3_MODEL_FIELDS = {
    **_CONTEXT_JOB_V2_MODEL_FIELDS,
    "polisyos.pdc._impl.world_model_record.WorldModelRecord": (
        *_CONTEXT_JOB_V2_MODEL_FIELDS[
            "polisyos.pdc._impl.world_model_record.WorldModelRecord"
        ],
        "artifact_views",
    ),
    "polisyos.pdc._impl.world_model_record.WorldModelArtifactViews": (
        "data_snapshot_ref",
        "registry_bundle_ref",
        "model_spec_ref",
        "input_bindings_ref",
        "bound_state_snapshot_ref",
        "input_binding_report_ref",
        "substrate_registry_ref",
        "program_graph_refs",
        "ncm_refs",
    ),
    "polisyos.core.artifacts.manifest.ArtifactRef": (
        "artifact_id",
        "kind",
        "media_type",
        "manifest_profile_sha256",
    ),
}
_CONTEXT_JOB_V3_EXACT_MODEL_FIELDS: dict[type[BaseModel], tuple[str, ...]] = {
    **_CONTEXT_JOB_V2_EXACT_MODEL_FIELDS,
    CycleSubstrateContextJobArtifactV3: (
        "schema_version",
        "authority_purpose",
        "status",
        "profile_admission_status",
        "s8_status",
        "run_id",
        "job_id",
        "tenant_id",
        "cell_id",
        "design_problem_ref",
        "problem",
        "context",
        "limitation_codes",
        "content_hash",
    ),
}
_CONTEXT_JOB_V3_EXACT_MODEL_VERSIONS: dict[type[BaseModel], frozenset[str]] = {
    **_CONTEXT_JOB_V2_EXACT_MODEL_VERSIONS,
    CycleSubstrateContextJobArtifactV3: frozenset(
        {CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA}
    ),
}


def _validate_problem_world_match(
    problem: DesignProblem,
    context: CycleSubstrateContext,
) -> None:
    """Require exact domain, jurisdiction, and qualified lever-slot identity."""

    world = context.world_model_record
    if context.domain != problem.domain or world.policy_domain != problem.domain:
        raise CycleSubstrateContextOwnerError(
            "cycle_substrate_context_job_domain_mismatch"
        )
    if world.region_or_jurisdiction != problem.jurisdiction_time.region:
        raise CycleSubstrateContextOwnerError(
            "cycle_substrate_context_job_jurisdiction_mismatch"
        )
    world_slots = {binding.slot_id for binding in world.policy_slot_map}
    problem_slots = {
        lever.target_slot for lever in problem.candidate_lever_space.candidate_levers
    }
    missing_slots = sorted(problem_slots.difference(world_slots))
    if missing_slots:
        raise CycleSubstrateContextOwnerError(
            "cycle_substrate_context_job_policy_slot_unresolved",
            ",".join(missing_slots),
        )


def _current_job_scope(
    *,
    current_job: _CurrentControlJobRecord,
    verified_nl_job_scope: VerifiedNLJobScope | None = None,
) -> tuple[str, str]:
    """Resolve the authenticated request scope or a replayed NL worker scope."""

    tenant_id = get_current_tenant_id_or_none()
    cell_id = get_current_cell_id()
    access_scope = get_current_access_scope_or_none()
    if verified_nl_job_scope is None:
        if access_scope is None or not tenant_id or not cell_id:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_authenticated_scope_not_established"
            )
        if access_scope.tenant_id != tenant_id or access_scope.cell_id != cell_id:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_authenticated_scope_mismatch"
            )
        return tenant_id, cell_id

    if (
        not tenant_id
        or not cell_id
        or verified_nl_job_scope.tenant_id != tenant_id
        or verified_nl_job_scope.cell_id != cell_id
        or current_job.job_id != verified_nl_job_scope.job_id
        or current_job.run_id != verified_nl_job_scope.run_id
        or current_job.submitted_by != verified_nl_job_scope.actor_subject
        or current_job.state != "running"
        or current_job.lease_owner != verified_nl_job_scope.worker_id
        or current_job.attempt != verified_nl_job_scope.attempt
        or not verified_nl_job_scope._was_issued_by_verified_nl_execution_owner
        or verified_nl_job_scope.authority_purpose != "cycle_input_candidate_only"
        or verified_nl_job_scope.admission_status != "established"
        or verified_nl_job_scope.intent_band != "simulate_only_attempt"
        or verified_nl_job_scope.canonical_mode != "simulate_only"
        or verified_nl_job_scope.route_id != "POST /api/v1/control/runs/nl"
        or verified_nl_job_scope.route_action != "control.launch_nl_run"
        or verified_nl_job_scope.admission_surface != "served_route"
        or verified_nl_job_scope.actor_authenticated is not True
    ):
        raise CycleSubstrateContextOwnerError("cycle_substrate_context_job_verified_scope_mismatch")
    if access_scope is not None and (
        access_scope.tenant_id != tenant_id or access_scope.cell_id != cell_id
    ):
        raise CycleSubstrateContextOwnerError(
            "cycle_substrate_context_job_authenticated_scope_mismatch"
        )
    return tenant_id, cell_id


def _serialize_context_job_v1_value(value: object) -> object:
    """Serialize known v1 model fields without consulting live model shape.

    A newly added nested model or an unsupported nested schema version fails
    closed. Extending this field tree requires a new outer context-job schema.
    """

    if isinstance(value, BaseModel):
        model_name = f"{type(value).__module__}.{type(value).__qualname__}"
        fields = _CONTEXT_JOB_V1_MODEL_FIELDS.get(model_name)
        if fields is None:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_v1_serializer_model_unregistered",
                model_name,
            )
        supported_versions = _CONTEXT_JOB_V1_SUPPORTED_MODEL_VERSIONS.get(model_name)
        nested_version = getattr(value, "schema_version", None)
        if (
            supported_versions is not None
            and nested_version not in supported_versions
        ):
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_v1_nested_schema_unsupported",
                f"{model_name}: {nested_version}",
            )
        return {
            field_name: _serialize_context_job_v1_value(getattr(value, field_name))
            for field_name in fields
        }
    if isinstance(value, Mapping):
        return {
            str(key): _serialize_context_job_v1_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_serialize_context_job_v1_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        serialized = [_serialize_context_job_v1_value(item) for item in value]
        return sorted(serialized, key=repr)
    return to_jsonable_python(value, by_alias=False)


def _serialize_context_job_v2_value(value: object) -> object:
    """Serialize V2's frozen tree, requiring exact types for V2-specific owners."""

    if isinstance(value, BaseModel):
        model_name = f"{type(value).__module__}.{type(value).__qualname__}"
        fields = _CONTEXT_JOB_V2_EXACT_MODEL_FIELDS.get(type(value))
        if fields is None:
            fields = _CONTEXT_JOB_V2_MODEL_FIELDS.get(model_name)
        if fields is None:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_v2_serializer_model_unregistered",
                model_name,
            )
        supported_versions = _CONTEXT_JOB_V2_EXACT_MODEL_VERSIONS.get(type(value))
        if supported_versions is None:
            supported_versions = _CONTEXT_JOB_V2_SUPPORTED_MODEL_VERSIONS.get(model_name)
        nested_version = getattr(value, "schema_version", None)
        if supported_versions is not None and nested_version not in supported_versions:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_v2_nested_schema_unsupported",
                f"{model_name}: {nested_version}",
            )
        return {
            field_name: _serialize_context_job_v2_value(getattr(value, field_name))
            for field_name in fields
        }
    if isinstance(value, Mapping):
        return {
            str(key): _serialize_context_job_v2_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_serialize_context_job_v2_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        serialized = [_serialize_context_job_v2_value(item) for item in value]
        return sorted(serialized, key=repr)
    return to_jsonable_python(value, by_alias=False)


def _serialize_context_job_v3_value(value: object) -> object:
    """Serialize V3's frozen WMRv2 tree with typed CAS view selectors."""

    if isinstance(value, BaseModel):
        model_name = f"{type(value).__module__}.{type(value).__qualname__}"
        fields = _CONTEXT_JOB_V3_EXACT_MODEL_FIELDS.get(type(value))
        if fields is None:
            fields = _CONTEXT_JOB_V3_MODEL_FIELDS.get(model_name)
        if fields is None:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_v3_serializer_model_unregistered",
                model_name,
            )
        supported_versions = _CONTEXT_JOB_V3_EXACT_MODEL_VERSIONS.get(type(value))
        if supported_versions is None:
            supported_versions = _CONTEXT_JOB_V3_SUPPORTED_MODEL_VERSIONS.get(model_name)
        nested_version = getattr(value, "schema_version", None)
        if supported_versions is not None and nested_version not in supported_versions:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_v3_nested_schema_unsupported",
                f"{model_name}: {nested_version}",
            )
        return {
            field_name: _serialize_context_job_v3_value(getattr(value, field_name))
            for field_name in fields
        }
    if isinstance(value, Mapping):
        return {
            str(key): _serialize_context_job_v3_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_serialize_context_job_v3_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        serialized = [_serialize_context_job_v3_value(item) for item in value]
        return sorted(serialized, key=repr)
    return to_jsonable_python(value, by_alias=False)


def _serialize_cycle_substrate_context_job_artifact(
    artifact: CycleSubstrateContextJobArtifact
    | CycleSubstrateContextJobArtifactV2
    | CycleSubstrateContextJobArtifactV3
    | Mapping[str, Any],
) -> dict[str, Any]:
    """Dispatch to the frozen byte serializer for the artifact's schema version."""

    schema_version = (
        artifact.schema_version
        if isinstance(artifact, BaseModel)
        else artifact.get("schema_version")
    )
    if schema_version == CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA:
        if isinstance(artifact, BaseModel):
            return cast("dict[str, Any]", _serialize_context_job_v2_value(artifact))
        fields = _CONTEXT_JOB_V2_EXACT_MODEL_FIELDS[
            CycleSubstrateContextJobArtifactV2
        ]
        values = {name: artifact[name] for name in fields if name in artifact}
        return cast("dict[str, Any]", _serialize_context_job_v2_value(values))
    if schema_version == CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA:
        if isinstance(artifact, BaseModel):
            return cast("dict[str, Any]", _serialize_context_job_v3_value(artifact))
        fields = _CONTEXT_JOB_V3_EXACT_MODEL_FIELDS[
            CycleSubstrateContextJobArtifactV3
        ]
        values = {name: artifact[name] for name in fields if name in artifact}
        return cast("dict[str, Any]", _serialize_context_job_v3_value(values))
    if schema_version != CYCLE_SUBSTRATE_CONTEXT_JOB_SCHEMA:
        raise CycleSubstrateContextOwnerError(
            "cycle_substrate_context_job_schema_version_unsupported",
            str(schema_version),
        )
    fields = _CONTEXT_JOB_V1_MODEL_FIELDS[
        "polisyos.runtime.quality.cycle_substrate.CycleSubstrateContextJobArtifact"
    ]
    if isinstance(artifact, BaseModel):
        values = {name: getattr(artifact, name) for name in fields}
    else:
        values = {name: artifact[name] for name in fields if name in artifact}
    return cast("dict[str, Any]", _serialize_context_job_v1_value(values))


def _cycle_job_v1_design_problem_ref(problem: DesignProblem) -> str:
    """Hash DesignProblem through the frozen v1 context-artifact projection."""

    return gy_content_hash(_serialize_context_job_v1_value(problem))


_CYCLE_JOB_PROFILE_SELECTION_EXECUTION_KEYS = frozenset(
    {"tenant_id", "cell_id", "job_id", "run_id"}
)


def _cycle_job_v1_profile_selection_ref(problem: DesignProblem) -> str:
    """Hash the frozen v1 projection for static candidate-scenario selection.

    The selector omits only server-assigned execution IDs from
    ``nl_provenance.source_context``. It is not a DesignProblem identity,
    context/job identity, tenant claim, grounding result, or authority ref.
    Persisted custody continues to use :func:`_cycle_job_v1_design_problem_ref`.
    """

    projection = _serialize_context_job_v1_value(problem)
    if not isinstance(projection, dict):
        raise CycleSubstrateContextOwnerError(
            "candidate_simulation_profile_selection_projection_invalid"
        )
    provenance = projection.get("nl_provenance")
    if not isinstance(provenance, dict):
        raise CycleSubstrateContextOwnerError(
            "candidate_simulation_profile_selection_provenance_invalid"
        )
    source_context = provenance.get("source_context")
    if not isinstance(source_context, dict):
        raise CycleSubstrateContextOwnerError(
            "candidate_simulation_profile_selection_source_context_invalid"
        )
    for key in _CYCLE_JOB_PROFILE_SELECTION_EXECUTION_KEYS:
        source_context.pop(key, None)
    return gy_content_hash(projection)


def _uses_cycle_job_v2_problem_projection(problem: DesignProblem) -> bool:
    """Return whether the current DesignProblem schema uses the v2 model tree."""

    return problem.schema_version == DESIGN_PROBLEM_V3_SCHEMA_VERSION


def cycle_job_design_problem_ref(problem: DesignProblem) -> str:
    """Return the current content ref, preserving v1/v2 and plain-v3 identity."""

    if problem.schema_version in {
        DESIGN_PROBLEM_V1_SCHEMA_VERSION,
        DESIGN_PROBLEM_V2_SCHEMA_VERSION,
    }:
        return _cycle_job_v1_design_problem_ref(problem)
    if _uses_cycle_job_v2_problem_projection(problem):
        return gy_content_hash(_serialize_context_job_v2_value(problem))
    raise CycleSubstrateContextOwnerError(
        "cycle_substrate_context_job_design_problem_schema_unsupported",
        problem.schema_version,
    )


def cycle_job_profile_selection_ref(problem: DesignProblem) -> str:
    """Return the configured-profile key for the selected problem projection."""

    if problem.schema_version in {
        DESIGN_PROBLEM_V1_SCHEMA_VERSION,
        DESIGN_PROBLEM_V2_SCHEMA_VERSION,
    }:
        return _cycle_job_v1_profile_selection_ref(problem)
    if not _uses_cycle_job_v2_problem_projection(problem):
        raise CycleSubstrateContextOwnerError(
            "cycle_substrate_context_job_design_problem_schema_unsupported",
            problem.schema_version,
        )
    projection = _serialize_context_job_v2_value(problem)
    if not isinstance(projection, dict):
        raise CycleSubstrateContextOwnerError(
            "candidate_simulation_profile_selection_projection_invalid"
        )
    provenance = projection.get("nl_provenance")
    if not isinstance(provenance, dict):
        raise CycleSubstrateContextOwnerError(
            "candidate_simulation_profile_selection_provenance_invalid"
        )
    source_context = provenance.get("source_context")
    if not isinstance(source_context, dict):
        raise CycleSubstrateContextOwnerError(
            "candidate_simulation_profile_selection_source_context_invalid"
        )
    for key in _CYCLE_JOB_PROFILE_SELECTION_EXECUTION_KEYS:
        source_context.pop(key, None)
    return gy_content_hash(projection)


def parse_cycle_substrate_context_job_artifact(
    payload: Mapping[str, Any],
) -> (
    CycleSubstrateContextJobArtifact
    | CycleSubstrateContextJobArtifactV2
    | CycleSubstrateContextJobArtifactV3
):
    """Parse a persisted context-job payload using its exact outer schema."""

    if not isinstance(payload, Mapping):
        raise CycleSubstrateContextOwnerError(
            "cycle_substrate_context_job_record_invalid",
            "payload_root_not_object",
        )
    schema_version = payload.get("schema_version")
    model_type = (
        _CONTEXT_JOB_ARTIFACT_TYPES_BY_SCHEMA.get(schema_version)
        if isinstance(schema_version, str)
        else None
    )
    if model_type is None:
        raise CycleSubstrateContextOwnerError(
            "cycle_substrate_context_job_schema_version_unsupported",
            str(schema_version),
        )
    return model_type.model_validate(payload)


def cycle_substrate_context_job_content_hash(
    artifact: CycleSubstrateContextJobArtifact
    | CycleSubstrateContextJobArtifactV2
    | CycleSubstrateContextJobArtifactV3
    | Mapping[str, Any],
) -> str:
    """Hash the frozen, schema-dispatched job-context payload without its hash."""

    payload = _serialize_cycle_substrate_context_job_artifact(artifact)
    payload.pop("content_hash", None)
    return gy_content_hash(payload)


def _build_cycle_substrate_context_job_artifact(
    context: CycleSubstrateContext,
    *,
    problem: DesignProblem,
    current_job: _CurrentControlJobRecord,
    verified_nl_job_scope: VerifiedNLJobScope | None = None,
) -> (
    CycleSubstrateContextJobArtifact
    | CycleSubstrateContextJobArtifactV2
    | CycleSubstrateContextJobArtifactV3
):
    """Build candidate handoff from the current persisted control-job record.

    The context must already exist as an owner-built typed object. This intake
    binds it to the job resolved by the control-store execution fence but does
    not mint a WMR, profile admission, population identity, or S8 value authority.
    """

    if not current_job.job_id.strip() or not current_job.run_id:
        raise CycleSubstrateContextOwnerError(
            "cycle_substrate_context_job_persisted_identity_missing"
        )
    tenant_id, cell_id = _current_job_scope(
        current_job=current_job,
        verified_nl_job_scope=verified_nl_job_scope,
    )
    verified_context = revalidate_cycle_substrate_context(context)
    problem_ref = cycle_job_design_problem_ref(problem)
    if verified_context.design_problem_ref != problem_ref:
        raise CycleSubstrateContextOwnerError(
            "cycle_substrate_context_job_context_problem_mismatch"
        )
    _validate_problem_world_match(problem, verified_context)
    uses_v2_projection = _uses_cycle_job_v2_problem_projection(problem)
    wmr_schema_version = verified_context.world_model_record.schema_version
    if wmr_schema_version == WORLD_MODEL_RECORD_SCHEMA_V2_VERSION:
        if not uses_v2_projection:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_v3_design_problem_required"
            )
        schema_version = CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA
    elif wmr_schema_version == "policyos.runtime.world_model_record.v1":
        schema_version = (
            CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA
            if uses_v2_projection
            else CYCLE_SUBSTRATE_CONTEXT_JOB_SCHEMA
        )
    else:
        raise CycleSubstrateContextOwnerError(
            "cycle_substrate_context_job_world_model_schema_unsupported",
            str(wmr_schema_version),
        )
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "authority_purpose": "cycle_input_candidate_only",
        "status": "candidate_limited",
        "profile_admission_status": "not_established",
        "s8_status": "blocked",
        "run_id": current_job.run_id,
        "job_id": current_job.job_id,
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "design_problem_ref": problem_ref,
        "problem": problem,
        "context": verified_context,
        "limitation_codes": tuple(sorted(_REQUIRED_CONTEXT_JOB_LIMITATIONS)),
    }
    payload["content_hash"] = cycle_substrate_context_job_content_hash(payload)
    if schema_version == CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA:
        return CycleSubstrateContextJobArtifactV3.model_validate(payload)
    if schema_version == CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA:
        return CycleSubstrateContextJobArtifactV2.model_validate(payload)
    return CycleSubstrateContextJobArtifact.model_validate(payload)


def _context_job_write_options(
    artifact: (
        CycleSubstrateContextJobArtifact
        | CycleSubstrateContextJobArtifactV2
        | CycleSubstrateContextJobArtifactV3
    ),
) -> artifacts.ArtifactWriteOptions:
    """Build the exact tenant and job manifest profile for this artifact."""

    schema_name = artifact.schema_version
    expected_type = _CONTEXT_JOB_ARTIFACT_TYPES_BY_SCHEMA.get(schema_name)
    if expected_type is not type(artifact):
        raise CycleSubstrateContextOwnerError(
            "cycle_substrate_context_job_schema_version_unsupported",
            str(schema_name),
        )
    schema_version = {
        CYCLE_SUBSTRATE_CONTEXT_JOB_SCHEMA: CYCLE_SUBSTRATE_CONTEXT_JOB_SCHEMA_VERSION,
        CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA: CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA_VERSION,
        CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA: CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA_VERSION,
    }[schema_name]
    return artifacts.ArtifactWriteOptions(
        kind=CYCLE_SUBSTRATE_CONTEXT_JOB_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(
            name=schema_name,
            version=schema_version,
        ),
        producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
        canon=artifacts.CanonInfo.from_spec(_CONTEXT_JOB_CANON),
        tenant_context=ArtifactTenantContextInfo(
            tenant_id=artifact.tenant_id,
            cell_id=artifact.cell_id,
        ),
        same_input_closure=ArtifactSameInputClosureInfo(
            closure_id=f"cycle-substrate-context:{artifact.run_id}:{artifact.job_id}",
            status="candidate_only",
            run_id=artifact.run_id,
            job_id=artifact.job_id,
            tenant_id=artifact.tenant_id,
            cell_id=artifact.cell_id,
        ),
    )


class CycleSubstrateContextArtifactOwner:
    """Persist and directly resolve one tenant/job-bound candidate context."""

    def __init__(
        self,
        *,
        store: artifacts.ArtifactStore,
        control_store: _CurrentControlJobExecutionOwner | None = None,
    ) -> None:
        self._store = store
        self._control_store = control_store

    def persist_for_current_job(
        self,
        context: CycleSubstrateContext,
        *,
        problem: DesignProblem,
        verified_nl_job_scope: VerifiedNLJobScope | None = None,
    ) -> artifacts.ArtifactRef:
        """Persist through the runtime store under the current persisted job lease."""

        if self._control_store is None:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_current_job_owner_unavailable"
            )
        current_job = self._control_store.current_execution_job_record()
        artifact = _build_cycle_substrate_context_job_artifact(
            context,
            problem=problem,
            current_job=current_job,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        return self._store.put_json(
            _serialize_cycle_substrate_context_job_artifact(artifact),
            _context_job_write_options(artifact),
            canon_spec=_CONTEXT_JOB_CANON,
        )

    def resolve_for_current_job(
        self,
        ref: artifacts.ArtifactRef,
        *,
        problem: DesignProblem,
        verified_nl_job_scope: VerifiedNLJobScope | None = None,
    ) -> (
        CycleSubstrateContextJobArtifact
        | CycleSubstrateContextJobArtifactV2
        | CycleSubstrateContextJobArtifactV3
    ):
        """Verify a ref against the persisted job authorized by the active lease."""

        if self._control_store is None:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_current_job_owner_unavailable"
            )
        current_job = self._control_store.current_execution_job_record()
        if not current_job.job_id.strip() or not current_job.run_id:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_persisted_identity_missing"
            )
        tenant_id, cell_id = _current_job_scope(
            current_job=current_job,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        expected_problem_ref = cycle_job_design_problem_ref(problem)
        if not self._store.verify(ref).ok:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_cas_integrity_failed"
            )
        manifest = self._store.get_manifest(ref)
        body = self._store.get_bytes(ref)
        if "sha256:" + hashlib.sha256(body).hexdigest() != str(ref.artifact_id):
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_cas_content_mismatch"
            )
        try:
            artifact = parse_cycle_substrate_context_job_artifact(
                canon.from_canonical_bytes(body)
            )
        except (TypeError, ValueError) as exc:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_record_invalid", str(exc)
            ) from exc
        if (
            artifact.run_id != current_job.run_id
            or artifact.job_id != current_job.job_id
        ):
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_binding_mismatch"
            )
        if (
            artifact.tenant_id != tenant_id
            or artifact.cell_id != cell_id
            or artifact.design_problem_ref != expected_problem_ref
        ):
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_binding_mismatch"
            )
        if not _has_context_job_owner_profile(manifest, artifact):
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_owner_profile_mismatch"
            )
        return artifact

    def resolve_historical_job_artifact(
        self,
        ref: artifacts.ArtifactRef | str,
        *,
        problem: DesignProblem,
        expected_job_id: str,
        expected_run_id: str,
        expected_tenant_id: str,
        expected_cell_id: str,
    ) -> (
        CycleSubstrateContextJobArtifact
        | CycleSubstrateContextJobArtifactV2
        | CycleSubstrateContextJobArtifactV3
    ):
        """Replay a persisted context-job artifact without requiring its old lease.

        This validates historical integrity and identity. It does not authorize
        a new execution; served N5 still calls :meth:`resolve_for_current_job`
        under the current verified worker scope.
        """

        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                expected_job_id,
                expected_run_id,
                expected_tenant_id,
                expected_cell_id,
            )
        ):
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_historical_identity_missing"
            )
        if not self._store.verify(ref).ok:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_cas_integrity_failed"
            )
        manifest = self._store.get_manifest(ref)
        body = self._store.get_bytes(ref)
        artifact_id = str(getattr(ref, "artifact_id", ref))
        if "sha256:" + hashlib.sha256(body).hexdigest() != artifact_id:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_cas_content_mismatch"
            )
        try:
            artifact = parse_cycle_substrate_context_job_artifact(
                canon.from_canonical_bytes(body)
            )
        except (TypeError, ValueError) as exc:
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_record_invalid", str(exc)
            ) from exc
        expected_problem_ref = cycle_job_design_problem_ref(problem)
        if (
            artifact.job_id != expected_job_id
            or artifact.run_id != expected_run_id
            or artifact.tenant_id != expected_tenant_id
            or artifact.cell_id != expected_cell_id
            or artifact.design_problem_ref != expected_problem_ref
            or artifact.problem != problem
        ):
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_historical_binding_mismatch"
            )
        if not _has_context_job_owner_profile(manifest, artifact):
            raise CycleSubstrateContextOwnerError(
                "cycle_substrate_context_job_owner_profile_mismatch"
            )
        return artifact


class ConfiguredCandidateSimulationContextAdmissionOwner:
    """Compose a candidate context only for an exact server-configured problem."""

    def __init__(
        self,
        *,
        profiles: Sequence[object],
        model_declarations: Sequence[object] = (),
        store: artifacts.ArtifactStore | None = None,
    ) -> None:
        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationScenarioProfile,
            CandidateSimulationSyntheticModelDeclarationV1,
            candidate_simulation_profile_ref,
        )

        validated: list[CandidateSimulationScenarioProfile] = []
        profile_ids: set[str] = set()
        profile_selection_refs: set[str] = set()
        for profile in profiles:
            if type(profile) is not CandidateSimulationScenarioProfile:
                raise TypeError("candidate_simulation_profile_untyped")
            checked = CandidateSimulationScenarioProfile.model_validate(
                profile.model_dump(mode="python")
            )
            if checked.profile_id in profile_ids:
                raise ValueError("candidate_simulation_profile_id_duplicate")
            if checked.profile_selection_ref in profile_selection_refs:
                raise ValueError("candidate_simulation_profile_problem_ref_ambiguous")
            profile_ids.add(checked.profile_id)
            profile_selection_refs.add(checked.profile_selection_ref)
            validated.append(checked)
        self._profiles = tuple(validated)
        profiles_by_config_ref = {
            candidate_simulation_profile_ref(profile): profile for profile in self._profiles
        }
        declarations_by_profile: dict[
            str, CandidateSimulationSyntheticModelDeclarationV1
        ] = {}
        for declaration in model_declarations:
            if type(declaration) is not CandidateSimulationSyntheticModelDeclarationV1:
                raise TypeError("candidate_simulation_model_declaration_untyped")
            checked_declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
                declaration.model_dump(mode="python")
            )
            profile = profiles_by_config_ref.get(checked_declaration.profile_config_ref)
            if profile is None:
                raise ValueError("candidate_simulation_model_profile_not_configured")
            if (
                checked_declaration.profile_content_hash != profile.content_hash
                or checked_declaration.profile_selection_ref != profile.profile_selection_ref
                or checked_declaration.target_world_slot != profile.rule.target_world_slot
                or checked_declaration.target_unit_id != profile.rule.unit_id
                or profile.n5.baseline_state.get(checked_declaration.target_world_slot)
                != checked_declaration.target_baseline
                or profile.n5.baseline_state.get(checked_declaration.outcome_variable)
                != checked_declaration.outcome_baseline
            ):
                raise ValueError("candidate_simulation_model_profile_binding_mismatch")
            if checked_declaration.profile_config_ref in declarations_by_profile:
                raise ValueError("candidate_simulation_model_profile_declaration_duplicate")
            declarations_by_profile[checked_declaration.profile_config_ref] = (
                checked_declaration
            )
        if declarations_by_profile and store is None:
            raise ValueError("candidate_simulation_model_store_not_supplied")
        self._model_declarations = declarations_by_profile
        self._store = store

    def configured_profile_for_selection_ref(self, profile_selection_ref: str) -> object:
        """Resolve one exact immutable configured profile without admitting it."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationScenarioProfile,
        )

        matches = tuple(
            profile
            for profile in self._profiles
            if profile.profile_selection_ref == profile_selection_ref
        )
        if len(matches) != 1 or type(matches[0]) is not CandidateSimulationScenarioProfile:
            raise CycleSubstrateContextOwnerError(
                "candidate_simulation_profile_selection_unresolved"
            )
        return matches[0]

    def admit_context_for_acquired_world(
        self,
        *,
        problem: DesignProblem,
        profile_selection_ref: str,
        world_model_record: WorldModelRecord,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> object:
        """Rebind an exact configured candidate profile to an owner-built world.

        This reissues the existing candidate model declaration and NCM views
        through GenerationSourceRepository, then persists no context itself.
        Caller-owned world construction is accepted only as a limited WMR with
        explicit acquisition, measurement, and causal-coupling blockers. Source
        time remains unresolved. Profiles with candidate-lever or transport
        evidence are refused until a source-backed owner can revalidate them for
        the new world.
        """

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationContextOffer,
            CandidateSimulationScenarioProfile,
            candidate_simulation_profile_ref,
        )
        from polisyos.runtime.quality.generation_source import GenerationSourceRepository
        from polisyos.runtime.quality.world_model_record import (
            derive_candidate_scenario_world_model_record,
        )

        if type(problem) is not DesignProblem or type(world_model_record) is not WorldModelRecord:
            raise CycleSubstrateContextOwnerError(
                "candidate_acquisition_context_inputs_untyped"
            )
        if not all(
            isinstance(value, str) and value.strip()
            for value in (job_id, run_id, tenant_id, cell_id, profile_selection_ref)
        ):
            raise CycleSubstrateContextOwnerError(
                "candidate_simulation_job_scope_not_established"
            )
        required_blockers = {
            "source_time_not_established",
            "source_to_target_measurement_contract_not_established",
            "causal_coupling_not_established",
        }
        if (
            world_model_record.authority_status != "limited"
            or not required_blockers.issubset(
                set(world_model_record.limitations.admissibility_blockers)
            )
        ):
            raise CycleSubstrateContextOwnerError(
                "candidate_acquisition_world_limitations_not_established"
            )
        configured = self.configured_profile_for_selection_ref(profile_selection_ref)
        if type(configured) is not CandidateSimulationScenarioProfile:
            raise CycleSubstrateContextOwnerError(
                "candidate_simulation_profile_untyped"
            )
        _require_context_evidence_refreshable(
            candidate_levers=configured.context_inputs.candidate_levers,
            transport_context=configured.context_inputs.transport_context,
        )
        if self._store is None:
            raise CycleSubstrateContextOwnerError(
                "candidate_simulation_model_store_not_supplied"
            )
        original_profile_ref = candidate_simulation_profile_ref(configured)
        original_declaration = self._model_declarations.get(original_profile_ref)
        if original_declaration is None:
            raise CycleSubstrateContextOwnerError(
                "candidate_simulation_acquisition_model_declaration_missing"
            )
        if (
            original_declaration.outcome_variable
            != problem.outcome_of_interest.target_variable
        ):
            raise CycleSubstrateContextOwnerError(
                "candidate_simulation_acquisition_problem_outcome_mismatch"
            )
        if (
            configured.profile_selection_ref != cycle_job_profile_selection_ref(problem)
            or world_model_record.region_or_jurisdiction
            != configured.context_inputs.world_model_record.region_or_jurisdiction
            or configured.rule.target_world_slot
            not in {binding.slot_id for binding in world_model_record.policy_slot_map}
        ):
            raise CycleSubstrateContextOwnerError(
                "candidate_simulation_acquisition_profile_world_mismatch"
            )

        from polisyos.foundry.data_plane.bindings import load_state_snapshot
        from polisyos.foundry.execute.executor import get_state_path
        from polisyos.runtime.quality.world_model_record import world_model_artifact_views

        state_ref = world_model_artifact_views(
            world_model_record
        ).bound_state_snapshot_ref
        if not self._store.verify(state_ref).ok:
            raise CycleSubstrateContextOwnerError(
                "candidate_simulation_acquisition_state_snapshot_unverified"
            )
        state = load_state_snapshot(self._store, snapshot_ref=state_ref)
        slot_bindings = {
            binding.slot_id: binding for binding in world_model_record.policy_slot_map
        }
        target_binding = slot_bindings.get(original_declaration.target_world_slot)
        outcome_binding = slot_bindings.get(original_declaration.outcome_variable)
        if (
            target_binding is None
            or outcome_binding is None
            or target_binding.unit != original_declaration.target_unit_id
            or outcome_binding.unit != original_declaration.outcome_unit_id
        ):
            raise CycleSubstrateContextOwnerError(
                "candidate_simulation_acquisition_model_slot_unit_mismatch"
            )
        required_baseline_slots = set(configured.n5.baseline_state)
        if not required_baseline_slots:
            raise CycleSubstrateContextOwnerError(
                "candidate_simulation_acquisition_baseline_missing"
            )
        refreshed_baseline: dict[str, float] = {}
        import math

        for slot_id in sorted(required_baseline_slots):
            binding = slot_bindings.get(slot_id)
            if binding is None or not binding.state_path:
                raise CycleSubstrateContextOwnerError(
                    "candidate_simulation_acquisition_baseline_slot_unresolved",
                    slot_id,
                )
            try:
                value = get_state_path(state, binding.state_path)
                scalar = float(value)
            except (AttributeError, TypeError, ValueError) as exc:
                raise CycleSubstrateContextOwnerError(
                    "candidate_simulation_acquisition_baseline_not_scalar",
                    slot_id,
                ) from exc
            if not math.isfinite(scalar):
                raise CycleSubstrateContextOwnerError(
                    "candidate_simulation_acquisition_baseline_non_finite",
                    slot_id,
                )
            refreshed_baseline[slot_id] = scalar

        profile_payload = configured.model_dump(mode="json")
        profile_payload["context_inputs"]["world_model_record"] = (
            world_model_record.model_dump(mode="json")
        )
        profile_payload["n5"]["baseline_state"] = refreshed_baseline
        profile_payload["content_hash"] = gy_content_hash(
            {key: value for key, value in profile_payload.items() if key != "content_hash"}
        )
        profile = CandidateSimulationScenarioProfile.model_validate(profile_payload)
        profile_config_ref = candidate_simulation_profile_ref(profile)

        declaration_payload = original_declaration.model_dump(mode="json")
        outcome_variable = original_declaration.outcome_variable
        target_slot = original_declaration.target_world_slot
        if (
            target_slot != configured.rule.target_world_slot
            or outcome_variable not in refreshed_baseline
        ):
            raise CycleSubstrateContextOwnerError(
                "candidate_simulation_acquisition_declaration_baseline_unresolved"
            )
        declaration_payload.update(
            {
                "profile_config_ref": profile_config_ref,
                "profile_content_hash": profile.content_hash,
                "target_baseline": refreshed_baseline[target_slot],
                "outcome_baseline": refreshed_baseline[outcome_variable],
            }
        )
        declaration_payload["content_hash"] = gy_content_hash(
            {
                key: value
                for key, value in declaration_payload.items()
                if key != "content_hash"
            }
        )
        declaration = type(original_declaration).model_validate(declaration_payload)
        repository = GenerationSourceRepository(store=self._store)
        declaration_ref = repository.persist_candidate_model_declaration(
            declaration=declaration,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        from polisyos.ir.analytics.ncm import candidate_ncm_spec_from_declaration

        ncm_ref = repository.persist_candidate_ncm_selected_view(
            ncm_spec=candidate_ncm_spec_from_declaration(declaration),
            declaration_ref=declaration_ref,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            profile_content_hash=profile.content_hash,
        )
        candidate_world = derive_candidate_scenario_world_model_record(
            world_model_record,
            ncm_artifact_ref=ncm_ref,
            declaration_content_hash=declaration.content_hash,
        )
        inputs = configured.context_inputs
        selected_hashes = tuple(inputs.selected_registry_entry_hashes)
        context = build_cycle_substrate_context(
            design_problem_ref=cycle_job_design_problem_ref(problem),
            domain=problem.domain,
            substrate_registry=inputs.substrate_registry,
            selected_registry_entry_hashes=selected_hashes,
            world_model_record=candidate_world,
            intervention_substrate=inputs.intervention_substrate,
            candidate_levers=(),
            transport_context=None,
            source_pack_content_hash=inputs.source_pack_content_hash,
            substrate_input_content_hash=inputs.substrate_input_content_hash,
        )
        _validate_problem_world_match(problem, context)
        context = revalidate_cycle_substrate_context(context)
        return CandidateSimulationContextOffer(
            context=context,
            profile=profile,
            profile_config_ref=profile_config_ref,
            model_declaration=declaration,
            model_declaration_ref=declaration_ref,
            ncm_ref=ncm_ref,
        )

    @property
    def profiles(self) -> tuple[object, ...]:
        """Return the immutable server-configured profile set."""

        return self._profiles

    @property
    def model_declarations(self) -> tuple[object, ...]:
        """Return the immutable declaration set bound to configured profiles."""

        return tuple(self._model_declarations.values())

    @property
    def store(self) -> artifacts.ArtifactStore | None:
        """Return the exact runtime-supplied artifact store, if configured."""

        return self._store

    def admit_context(
        self,
        *,
        problem: DesignProblem,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> object | None:
        """Compose the unique matching candidate context; never infer a profile."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationContextOffer,
            candidate_simulation_profile_ref,
        )

        if not all(
            isinstance(value, str) and value.strip()
            for value in (job_id, run_id, tenant_id, cell_id)
        ):
            raise CycleSubstrateContextOwnerError(
                "candidate_simulation_job_scope_not_established"
            )
        problem_ref = cycle_job_design_problem_ref(problem)
        profile_selection_ref = cycle_job_profile_selection_ref(problem)
        matches = tuple(
            profile
            for profile in self._profiles
            if profile.profile_selection_ref == profile_selection_ref
        )
        if not matches:
            return None
        if len(matches) != 1:
            raise CycleSubstrateContextOwnerError(
                "candidate_simulation_profile_problem_ref_ambiguous"
            )
        profile = matches[0]
        inputs = profile.context_inputs
        profile_config_ref = candidate_simulation_profile_ref(profile)
        declaration = self._model_declarations.get(profile_config_ref)
        model_declaration_ref = None
        ncm_ref = None
        world_model_record = inputs.world_model_record
        if declaration is not None:
            if self._store is None:
                raise CycleSubstrateContextOwnerError(
                    "candidate_simulation_model_store_not_supplied"
                )
            slot_units = {
                item.slot_id: item.unit
                for item in inputs.world_model_record.policy_slot_map
            }
            if (
                declaration.outcome_variable
                != problem.outcome_of_interest.target_variable
            ):
                raise CycleSubstrateContextOwnerError(
                    "candidate_simulation_model_outcome_problem_mismatch"
                )
            if (
                slot_units.get(declaration.target_world_slot)
                != declaration.target_unit_id
                or slot_units.get(declaration.outcome_variable)
                != declaration.outcome_unit_id
            ):
                raise CycleSubstrateContextOwnerError(
                    "candidate_simulation_model_unit_binding_mismatch"
                )
            _require_context_evidence_refreshable(
                candidate_levers=inputs.candidate_levers,
                transport_context=inputs.transport_context,
            )
            from polisyos.ir.analytics.ncm import candidate_ncm_spec_from_declaration
            from polisyos.runtime.quality.generation_source import GenerationSourceRepository
            from polisyos.runtime.quality.world_model_record import (
                derive_candidate_scenario_world_model_record,
            )

            repository = GenerationSourceRepository(store=self._store)
            model_declaration_ref = repository.persist_candidate_model_declaration(
                declaration=declaration,
                job_id=job_id,
                run_id=run_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            ncm_ref = repository.persist_candidate_ncm_selected_view(
                ncm_spec=candidate_ncm_spec_from_declaration(declaration),
                declaration_ref=model_declaration_ref,
                job_id=job_id,
                run_id=run_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
                profile_content_hash=profile.content_hash,
            )
            world_model_record = derive_candidate_scenario_world_model_record(
                inputs.world_model_record,
                ncm_artifact_ref=ncm_ref,
                declaration_content_hash=declaration.content_hash,
            )
        context = build_cycle_substrate_context(
            design_problem_ref=problem_ref,
            domain=problem.domain,
            substrate_registry=inputs.substrate_registry,
            selected_registry_entry_hashes=inputs.selected_registry_entry_hashes,
            world_model_record=world_model_record,
            intervention_substrate=inputs.intervention_substrate,
            candidate_levers=inputs.candidate_levers,
            transport_context=inputs.transport_context,
            source_pack_content_hash=inputs.source_pack_content_hash,
            substrate_input_content_hash=inputs.substrate_input_content_hash,
        )
        _validate_problem_world_match(problem, context)
        context = revalidate_cycle_substrate_context(context)
        return CandidateSimulationContextOffer(
            context=context,
            profile=profile,
            profile_config_ref=profile_config_ref,
            model_declaration=declaration,
            model_declaration_ref=model_declaration_ref,
            ncm_ref=ncm_ref,
        )


def _has_context_job_owner_profile(
    manifest: artifacts.ArtifactManifest,
    artifact: (
        CycleSubstrateContextJobArtifact
        | CycleSubstrateContextJobArtifactV2
        | CycleSubstrateContextJobArtifactV3
    ),
) -> bool:
    """Require the full declared owner profile on the selected artifact view."""

    options = _context_job_write_options(artifact)
    actual = {
        field.alias or name: getattr(manifest, name)
        for name, field in type(manifest).model_fields.items()
    }
    for name, field in type(options).__dataclass_fields__.items():
        expected = getattr(options, name)
        if name in {"inputs", "warnings"}:
            expected = list(expected or [])
        if field is None or name not in actual or actual[name] != expected:
            return False
    return True


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
    "CYCLE_SUBSTRATE_CONTEXT_JOB_KIND",
    "CYCLE_SUBSTRATE_CONTEXT_JOB_SCHEMA",
    "CYCLE_SUBSTRATE_CONTEXT_JOB_SCHEMA_VERSION",
    "CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA",
    "CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA_VERSION",
    "CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA",
    "CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA_VERSION",
    "CYCLE_SUBSTRATE_CONTEXT_SCHEMA_VERSION",
    "CandidateLeverEvidence",
    "CycleSubstrateContext",
    "CycleSubstrateContextArtifactOwner",
    "CycleSubstrateContextJobArtifact",
    "CycleSubstrateContextJobArtifactV2",
    "CycleSubstrateContextJobArtifactV3",
    "CycleSubstrateContextOwnerError",
    "TransportContextEvidence",
    "TransportCovariateObservation",
    "build_cycle_substrate_context",
    "cycle_job_design_problem_ref",
    "cycle_job_profile_selection_ref",
    "cycle_substrate_context_binding_hash",
    "cycle_substrate_context_content_hash",
    "cycle_substrate_context_job_content_hash",
    "is_supported_cycle_substrate_context_job_artifact",
    "parse_cycle_substrate_context_job_artifact",
    "resolve_candidate_lever_world_identity",
    "resolve_cycle_substrate_context_for_world",
    "resolve_cycle_substrate_world_identity",
    "resolve_world_model_atom_identity",
    "revalidate_cycle_substrate_context",
]
