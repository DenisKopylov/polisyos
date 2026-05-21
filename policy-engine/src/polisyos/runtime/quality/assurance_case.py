"""Assurance-case explanation layer for serious runtime closeout."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from polisyos.core.contracts.control import policy_authority_profile_mapping
from polisyos.runtime.quality.policy_design_case import (
    POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES,
    RECORD_REGISTRY_ENFORCEMENT_FUNCTION,
    RECORD_REGISTRY_READINESS_CHECK,
    RECORD_REGISTRY_SCORECARD_GATE,
)

SCHEMA_VERSION = "policyos.runtime.assurance_case.v1"
POLICY_DESIGN_CASE_SCHEMA_VERSION = "policyos.runtime.policy_design_case.v1"
POLICY_DESIGN_CASE_REGISTRY_ENTRY_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.registry_entry.v1"
)
POLICY_INTENT_ENVELOPE_SCHEMA_VERSION = "policyos.runtime.policy_intent_envelope.v1"
POLICY_DESIGN_CASE_PROFILE = "policy_design"
POLICY_DESIGN_CASE_OWNER = "team-runtime-quality"
POLICY_DESIGN_CASE_RUNTIME_QUALITY_COMPONENT = "polisyos.runtime.quality.assurance_case"
POLICY_DESIGN_WALKING_SKELETON_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.walking_skeleton.v1"
)
POLICY_DESIGN_JURISDICTION_SPINE_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.jurisdiction_spine.v1"
)
POLICY_DESIGN_JURISDICTION_SPINE_CONTRACT = (
    "policy_design_case.concept_jurisdiction_spine.v1"
)
POLICY_DESIGN_JURISDICTION_SPINE_PROJECTOR_COMPONENT = (
    f"{POLICY_DESIGN_CASE_RUNTIME_QUALITY_COMPONENT}.jurisdiction_spine_projector"
)
POLICY_DESIGN_JURISDICTION_AUTHORITY_LEVELS = (
    "supranational",
    "national",
    "regional",
    "local",
)
POLICY_DESIGN_WALKING_SKELETON_CONTRACT_ID = (
    "policy_design_case.walking_skeleton_case_contract.v1"
)
POLICY_DESIGN_WALKING_SKELETON_STUB_COMPONENT = (
    f"{POLICY_DESIGN_CASE_RUNTIME_QUALITY_COMPONENT}.walking_skeleton_stub"
)
POLICY_DESIGN_CAPABILITY_LEDGER_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.capability_ledger.v1"
)
POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.concept_spine.v1"
)
POLICY_DESIGN_CONCEPT_SPINE_CONTRACT_ID = "policy_design_case.concept_spine_contract.v1"
POLICY_DESIGN_CONCEPT_SPINE_OWNER = "team-policy-semantics"
POLICY_DESIGN_CONCEPT_SPINE_COMPONENT = (
    f"{POLICY_DESIGN_CASE_RUNTIME_QUALITY_COMPONENT}.concept_spine_projection"
)
POLICY_DESIGN_CONCEPT_SPINE_SOURCE_COMPONENTS = (
    "fabric_entity_resolution",
    "scientist_cross_graph",
    "ir_linker",
    "ir_registry",
    "ir_world",
)
POLICY_DESIGN_CONCEPT_SPINE_REQUIRED_CLOSURE_FIELDS = (
    "aliases",
    "source_terms",
    "metric_bindings",
    "dataset_column_bindings",
    "legal_concept_bindings",
    "method_requirement_bindings",
    "objective_tradeoff_bindings",
    "geography",
    "population",
    "time",
    "units",
    "currency",
    "price_bases",
    "exchange_rates",
    "inflation_adjustments",
    "calendars",
    "freshness",
)
DEFAULT_OWNER = "team-assurance"
DEFAULT_NEXT_DIAGNOSTIC_COMMAND = (
    "uv run python tools/quality/validation/check_honest_diagnostics_proof_harness.py "
    "--repo-root . --require-passing"
)
POLICY_DESIGN_REQUIRED_CAPABILITIES = (
    "lex",
    "fabric",
    "scholar",
    "foundry",
    "scientist",
    "compiler",
    "review",
    "publication",
    "audit",
)
POLICY_DESIGN_CAPABILITY_DUTY_STATES = (
    "selected",
    "skipped",
    "blocked",
    "fallback",
)
POLICY_DESIGN_CASE_CORE_NODE_TYPES = (
    "policy_intent",
    "capability_duty",
    "concept_spine",
    "jurisdiction_spine",
    "producer_evidence",
    "portfolio",
    "claim",
    "argument",
    "warrant",
    "rebuttal",
    "counter_evidence",
    "deficit",
)
POLICY_DESIGN_CASE_RESERVED_NODE_FAMILIES = (
    "oversight_effectiveness",
    "lifecycle_event",
    "audit_attestation",
    "publication_trust",
    "run_cost_proportionality",
    "ex_post_outcome",
    "calibration",
    "formal_invariant",
)
POLICY_DESIGN_CASE_NODE_MAPPING = {
    "policy_intent": "SACM.context",
    "capability_duty": "SACM.context",
    "concept_spine": "SACM.context",
    "jurisdiction_spine": "SACM.context",
    "producer_evidence": "SACM.artifact_reference",
    "portfolio": "CAE.evidence_set",
    "claim": "SACM.claim",
    "argument": "SACM.argument_reasoning",
    "warrant": "CAE.warrant",
    "rebuttal": "CAE.rebuttal",
    "counter_evidence": "CAE.defeater",
    "deficit": "SACM.assurance_deficit",
}
POLICY_DESIGN_CASE_PROFILE_METADATA = {
    "profile": POLICY_DESIGN_CASE_PROFILE,
    "schema_version": POLICY_DESIGN_CASE_SCHEMA_VERSION,
    "extends_schema_version": SCHEMA_VERSION,
    "owner": POLICY_DESIGN_CASE_OWNER,
    "authority_surface": "src/polisyos/runtime/quality/assurance_case.py",
    "runtime_quality_component": POLICY_DESIGN_CASE_RUNTIME_QUALITY_COMPONENT,
    "core_node_types": POLICY_DESIGN_CASE_CORE_NODE_TYPES,
    "reserved_node_families": POLICY_DESIGN_CASE_RESERVED_NODE_FAMILIES,
    "authority_chain": (
        "runtime_quality_owner",
        "runtime_event_ref",
        "cas_ref",
        "same_input_closure_ref",
        "effective_mode_ref",
        "schema_compatibility_ref",
        "tenant_id",
    ),
    "mapping": POLICY_DESIGN_CASE_NODE_MAPPING,
}
ASSURANCE_CASE_REQUIRED_FIELDS = frozenset(
    {
        "claim",
        "subclaims",
        "argument",
        "argument_strategy",
        "evidence",
        "assumptions",
        "contexts",
        "defeaters",
        "blockers",
        "unresolved_uncertainty",
        "confidence_limits",
        "non_overridable_blockers",
        "reviewer_attribution",
        "owner",
        "next_diagnostic_command",
    }
)
_NON_OVERRIDABLE_BLOCKER_CODES = frozenset(
    {
        "diagnostic_slo_evidence_missing",
        "diagnostic_slo_evidence_stale",
        "diagnostic_slo_error_budget_burned",
        "diagnostic_fitness_control_missing",
        "hds_runtime_ref_missing",
        "hds_bundle_ref_used_as_runtime_ref",
        "hds_schema_incompatible",
        "hds_semantic_binding_missing",
        "hds_unallowed_fallback",
        "phase_barrier_record_malformed",
        "scorecard_identity_not_verified",
    }
)
_POLICY_DESIGN_ALLOWED_AUTHORITY_ROLES = frozenset(
    {
        "producer_authority",
        "runtime_blocker",
    }
)
_POLICY_DESIGN_ALLOWED_PROVENANCE = frozenset(
    {
        "runtime_emitted",
        "runtime_blocker",
    }
)
_POLICY_DESIGN_CAPABILITY_ALIASES = {
    "claim_compiler": "compiler",
    "final_compiler": "compiler",
    "scholar_retrieval": "scholar",
}
_POLICY_DESIGN_CAPABILITY_OWNERS = {
    "lex": "team-lex",
    "fabric": "team-fabric",
    "scholar": "team-scholar",
    "foundry": "team-foundry",
    "scientist": "team-scientist",
    "compiler": "team-claim-compiler",
    "review": "team-runtime-review",
    "publication": "team-publication",
    "audit": "team-core-audit",
}
_POLICY_DESIGN_ALLOWED_DUTY_STATES = frozenset(POLICY_DESIGN_CAPABILITY_DUTY_STATES)
_POLICY_DESIGN_SELECTED_REF_FIELDS = (
    "evidence_ref",
    "producer_ref",
    "runtime_event_ref",
    "cas_ref",
)
_POLICY_DESIGN_BLOCKER_FIELDS = (
    "blocker_ref",
    "blocked_ref",
    "typed_blocker_ref",
    "skip_blocker_ref",
)
_POLICY_DESIGN_BLOCKER_RECORD_FIELDS = (
    "blocker",
    "typed_blocker",
    "skip_blocker",
    "blocker_record",
)
_POLICY_DESIGN_DEGRADATION_REF_FIELDS = (
    "degradation_ref",
    "degradation_ledger_ref",
    "fallback_degradation_ref",
)
_POLICY_DESIGN_DEGRADATION_RECORD_FIELDS = (
    "degradation_record",
    "degradation",
    "fallback_degradation_record",
)
_POLICY_DESIGN_REQUIRED_AUTHORITY_REFS = {
    "cas_ref": "policy_design_case_cas_ref_missing",
    "runtime_event_ref": "policy_design_case_runtime_event_ref_missing",
    "same_input_closure_ref": "policy_design_case_same_input_closure_ref_missing",
    "effective_mode_ref": "policy_design_case_effective_mode_ref_missing",
    "schema_compatibility_ref": "policy_design_case_schema_compatibility_ref_missing",
}
_POLICY_INTENT_REQUIRED_TEXT_FIELDS = {
    "intent_id": "policy_intent_id_missing",
    "run_id": "policy_intent_run_id_missing",
    "job_id": "policy_intent_job_id_missing",
    "tenant_id": "policy_intent_tenant_id_missing",
    "policy_problem": "policy_intent_policy_problem_missing",
    "desired_outcome": "policy_intent_desired_outcome_missing",
    "proposed_intervention": "policy_intent_proposed_intervention_missing",
    "jurisdiction": "policy_intent_jurisdiction_missing",
    "target_population": "policy_intent_target_population_missing",
    "policy_time": "policy_intent_policy_time_missing",
    "data_time": "policy_intent_data_time_missing",
    "requested_authority_level": "policy_intent_requested_authority_level_missing",
}
_POLICY_INTENT_REQUESTER_PREFERRED_CONCLUSION = "requester_preferred_conclusion"
_POLICY_DESIGN_WALKING_SKELETON_REQUIRED_NODE_TYPES = (
    "policy_intent",
    "concept_spine",
    "producer_evidence",
    "claim",
    "deficit",
)
_POLICY_DESIGN_WALKING_SKELETON_REQUIRED_REFS = (
    "cas_ref",
    "runtime_event_ref",
    "diagnostic_event_ref",
    "schema_compatibility_ref",
    "effective_mode_ref",
    "same_input_closure_ref",
)
_POLICY_DESIGN_WALKING_SKELETON_ACCEPTED_DEFICIT_KIND = (
    "single_line_evidence_deficit"
)
_POLICY_DESIGN_WALKING_SKELETON_ALLOWED_DEFICIT_PROFILES = frozenset({"research"})


class PolicyDesignCaseAuthorityError(ValueError):
    """Fail-closed Policy Design Case runtime authority violation."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


def build_policy_intent_envelope(
    *,
    intent_id: str,
    run_id: str,
    job_id: str,
    tenant_id: str,
    policy_problem: str,
    desired_outcome: str,
    proposed_intervention: str,
    jurisdiction: str,
    target_population: str,
    policy_time: str,
    data_time: str,
    requester_preferred_conclusion: str | None,
    requested_authority_level: str,
    affected_stakeholders: Iterable[object] | None = None,
    constraints: Iterable[object] | None = None,
    objectives: Iterable[object] | None = None,
    assumptions: Iterable[object] | None = None,
    evidence_expectations: Iterable[object] | None = None,
    authoring_provenance: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build the canonical pre-routing policy intent envelope."""

    payload = {
        "schema_version": POLICY_INTENT_ENVELOPE_SCHEMA_VERSION,
        "intent_id": intent_id,
        "run_id": run_id,
        "job_id": job_id,
        "tenant_id": tenant_id,
        "policy_problem": policy_problem,
        "desired_outcome": desired_outcome,
        "proposed_intervention": proposed_intervention,
        "jurisdiction": jurisdiction,
        "target_population": target_population,
        "policy_time": policy_time,
        "data_time": data_time,
        _POLICY_INTENT_REQUESTER_PREFERRED_CONCLUSION: requester_preferred_conclusion,
        "requested_authority_level": requested_authority_level,
        "affected_stakeholders": _policy_design_text_list(affected_stakeholders),
        "constraints": _policy_design_text_list(constraints),
        "objectives": _policy_design_text_list(objectives),
        "assumptions": _policy_design_text_list(assumptions),
        "evidence_expectations": _policy_design_text_list(evidence_expectations),
        "authoring_provenance": dict(authoring_provenance or {}),
        "generated_at": _utc(generated_at).isoformat(),
    }
    return validate_policy_intent_envelope(payload)


def validate_policy_intent_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Validate requester intent capture before any producer interprets the run."""

    if not isinstance(envelope, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_intent_envelope_invalid",
            "Policy intent envelope must be a mapping.",
        )
    schema_version = _policy_design_text(envelope.get("schema_version"))
    if schema_version != POLICY_INTENT_ENVELOPE_SCHEMA_VERSION:
        raise PolicyDesignCaseAuthorityError(
            "policy_intent_schema_version_invalid",
            "Policy intent envelope must use the runtime-quality schema version.",
        )

    normalized: dict[str, Any] = {"schema_version": POLICY_INTENT_ENVELOPE_SCHEMA_VERSION}
    for field_name, code in _POLICY_INTENT_REQUIRED_TEXT_FIELDS.items():
        normalized[field_name] = _policy_design_required_text(envelope.get(field_name), code)
    try:
        authority_mapping = policy_authority_profile_mapping(
            normalized["requested_authority_level"]
        )
    except ValueError as exc:
        raise PolicyDesignCaseAuthorityError(
            "policy_intent_requested_authority_level_invalid",
            "Requested authority level must be research, governed, or production.",
        ) from exc
    normalized["requested_execution_profile"] = authority_mapping.execution_profile
    normalized["validation_profile"] = authority_mapping.validation_profile
    normalized["fallback_policy"] = authority_mapping.fallback_policy

    preferred_conclusion = _policy_intent_preferred_conclusion(envelope)
    normalized[_POLICY_INTENT_REQUESTER_PREFERRED_CONCLUSION] = preferred_conclusion
    normalized["affected_stakeholders"] = _policy_design_text_list(
        envelope.get("affected_stakeholders")
    )
    normalized["constraints"] = _policy_design_text_list(envelope.get("constraints"))
    normalized["objectives"] = _policy_design_text_list(envelope.get("objectives"))
    normalized["assumptions"] = _policy_design_text_list(envelope.get("assumptions"))
    normalized["evidence_expectations"] = _policy_design_text_list(
        envelope.get("evidence_expectations")
    )
    provenance = envelope.get("authoring_provenance")
    if not isinstance(provenance, Mapping) or not provenance:
        raise PolicyDesignCaseAuthorityError(
            "policy_intent_authoring_provenance_missing",
            "Policy intent envelope must record authoring provenance.",
        )
    normalized["authoring_provenance"] = dict(provenance)
    generated_at = _policy_design_text(envelope.get("generated_at"))
    if generated_at is not None:
        normalized["generated_at"] = generated_at

    normalized["requester_preference"] = _policy_intent_requester_preference(
        preferred_conclusion
    )
    normalized["analysis_independence"] = _policy_intent_analysis_independence()
    risk = _policy_intent_capture_risk(
        preferred_conclusion=preferred_conclusion,
        risk_factors=_policy_intent_risk_factors(envelope),
    )
    normalized["requester_capture_risk"] = risk
    normalized["challenge_depth_policy"] = _policy_intent_challenge_depth_policy(risk)
    return normalized


def build_policy_design_case_profile(
    *,
    case_id: str,
    run_id: str,
    job_id: str,
    tenant_id: str,
    effective_execution_profile: str,
    runtime_authority: Mapping[str, Any],
    capability_ledger: Mapping[str, Any] | None = None,
    intent_envelope: Mapping[str, Any] | None = None,
    jurisdiction_spine: Mapping[str, Any] | None = None,
    case_registry_entry: Mapping[str, Any] | None = None,
    nodes: Iterable[Mapping[str, Any]] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build the Policy Design Case as a runtime-quality assurance profile."""

    authority_chain = _policy_design_case_authority_chain(runtime_authority)
    validated_intent = (
        validate_policy_intent_envelope(intent_envelope)
        if intent_envelope is not None
        else None
    )
    case = {
        "schema_version": POLICY_DESIGN_CASE_SCHEMA_VERSION,
        "profile": POLICY_DESIGN_CASE_PROFILE,
        "case_id": _policy_design_required_text(
            case_id,
            "policy_design_case_id_missing",
        ),
        "run_id": _policy_design_required_text(run_id, "policy_design_case_run_id_missing"),
        "job_id": _policy_design_required_text(job_id, "policy_design_case_job_id_missing"),
        "tenant_id": _policy_design_required_text(
            tenant_id,
            "policy_design_case_tenant_id_missing",
        ),
        "effective_execution_profile": _policy_design_required_text(
            effective_execution_profile,
            "policy_design_case_effective_execution_profile_missing",
        ),
        "generated_at": _utc(generated_at).isoformat(),
        "owner": POLICY_DESIGN_CASE_OWNER,
        "authority_chain": authority_chain,
        "profile_metadata": _policy_design_case_profile_metadata(),
        "core_node_types": list(POLICY_DESIGN_CASE_CORE_NODE_TYPES),
        "reserved_node_families": list(POLICY_DESIGN_CASE_RESERVED_NODE_FAMILIES),
        "case_registry_entry": (
            dict(case_registry_entry)
            if case_registry_entry is not None
            else build_policy_design_case_registry_entry(generated_at=generated_at)
        ),
        "capability_ledger": capability_ledger,
        "intent_envelope": validated_intent,
        "jurisdiction_spine": jurisdiction_spine,
        "nodes": _policy_design_case_nodes(nodes or ()),
    }
    return validate_policy_design_case_profile(case)


def build_policy_design_case_concept_spine(
    *,
    run_id: str,
    job_id: str,
    tenant_id: str,
    policy_intent_ref: str,
    raw_user_terms: Iterable[str] | Mapping[str, Any] | str | None = None,
    fabric_entity_resolution: Mapping[str, Any] | None = None,
    scientist_cross_graph: Mapping[str, Any] | None = None,
    ir_linker: Mapping[str, Any] | None = None,
    ir_registry: Mapping[str, Any] | None = None,
    ir_world: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Project a per-run Policy Design Case concept spine over existing producers."""

    generated = _utc(generated_at)
    concepts: dict[str, dict[str, Any]] = {}
    unresolved: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    source_projection = _policy_design_concept_source_projection(
        fabric_entity_resolution=fabric_entity_resolution,
        scientist_cross_graph=scientist_cross_graph,
        ir_linker=ir_linker,
        ir_registry=ir_registry,
        ir_world=ir_world,
    )

    _policy_design_project_ir_registry_concepts(
        concepts,
        ir_registry,
        unresolved=unresolved,
    )
    _policy_design_project_fabric_entity_resolution(
        concepts,
        fabric_entity_resolution,
        unresolved=unresolved,
        conflicts=conflicts,
    )
    _policy_design_project_scientist_cross_graph(
        concepts,
        scientist_cross_graph,
        unresolved=unresolved,
        conflicts=conflicts,
    )
    _policy_design_project_ir_linker(
        concepts,
        ir_linker,
        unresolved=unresolved,
        conflicts=conflicts,
    )
    _policy_design_project_ir_world(
        concepts,
        ir_world,
        unresolved=unresolved,
        conflicts=conflicts,
    )
    _policy_design_apply_ir_registry_bindings(concepts, ir_registry)
    _policy_design_bind_claim_numerical_semantics(concepts)

    concept_rows = [
        _policy_design_concept_finalize(row)
        for _, row in sorted(concepts.items(), key=lambda item: item[0])
    ]
    semantic_mismatches = _policy_design_semantic_mismatches(concept_rows)
    reconciliation_trace = _policy_design_concept_reconciliation_trace(
        concept_rows,
        semantic_mismatches=semantic_mismatches,
    )
    normalization_trace = _policy_design_concept_normalization_trace(
        concept_rows,
        raw_user_terms=raw_user_terms,
    )
    closure_gaps = _policy_design_concept_closure_gaps(concept_rows)
    blockers = _policy_design_concept_blockers(
        unresolved=unresolved,
        conflicts=conflicts,
        closure_gaps=closure_gaps,
        semantic_mismatches=semantic_mismatches,
        normalization_trace=normalization_trace,
    )
    status = "blocked" if blockers else "pass"
    base_payload = {
        "schema_version": POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION,
        "contract_id": POLICY_DESIGN_CONCEPT_SPINE_CONTRACT_ID,
        "node_type": "concept_spine",
        "record_id": f"concept_spine.{_policy_design_required_text(run_id, 'run_id')}",
        "run_id": _policy_design_required_text(run_id, "policy_design_concept_run_id_missing"),
        "job_id": _policy_design_required_text(job_id, "policy_design_concept_job_id_missing"),
        "tenant_id": _policy_design_required_text(
            tenant_id,
            "policy_design_concept_tenant_id_missing",
        ),
        "policy_intent_ref": _policy_design_required_text(
            policy_intent_ref,
            "policy_design_concept_intent_ref_missing",
        ),
        "generated_at": generated.isoformat(),
        "owner": POLICY_DESIGN_CONCEPT_SPINE_OWNER,
        "producer_owner": POLICY_DESIGN_CONCEPT_SPINE_OWNER,
        "producer_component": POLICY_DESIGN_CONCEPT_SPINE_COMPONENT,
        "status": status,
        "source_projection": source_projection,
        "canonical_concept_ids": [
            str(row["canonical_concept_id"]) for row in concept_rows
        ],
        "canonical_concepts": concept_rows,
        "reconciliation_trace": reconciliation_trace,
        "normalization_trace": normalization_trace,
        "metric_bindings": _policy_design_collect_concept_bindings(
            concept_rows,
            "metric_bindings",
            id_key="metric_id",
        ),
        "dataset_column_bindings": _policy_design_collect_concept_bindings(
            concept_rows,
            "dataset_column_bindings",
            id_key="dataset_id",
        ),
        "legal_concept_bindings": _policy_design_collect_concept_bindings(
            concept_rows,
            "legal_concept_bindings",
            id_key="legal_concept_id",
        ),
        "method_requirement_bindings": _policy_design_collect_concept_bindings(
            concept_rows,
            "method_requirement_bindings",
            id_key="requirement_id",
        ),
        "objective_tradeoff_bindings": _policy_design_collect_concept_bindings(
            concept_rows,
            "objective_tradeoff_bindings",
            id_key="objective_id",
        ),
        "claim_bindings": _policy_design_collect_concept_bindings(
            concept_rows,
            "claim_bindings",
            id_key="claim_id",
        ),
        "claim_numerical_semantics_refs": _policy_design_collect_concept_bindings(
            concept_rows,
            "claim_numerical_semantics_refs",
            id_key="claim_id",
        ),
        "unresolved_concepts": unresolved,
        "conflicting_concepts": conflicts,
        "blockers": blockers,
    }
    cas_ref = _policy_design_cas_ref_from_payload(base_payload)
    schema_compatibility_ref = _policy_design_cas_ref_from_payload(
        {
            "schema_version": POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION,
            "contract_id": POLICY_DESIGN_CONCEPT_SPINE_CONTRACT_ID,
        }
    )
    effective_mode_ref = _policy_design_cas_ref_from_payload(
        {
            "run_id": base_payload["run_id"],
            "job_id": base_payload["job_id"],
            "status": status,
            "contract_id": POLICY_DESIGN_CONCEPT_SPINE_CONTRACT_ID,
        }
    )
    same_input_closure_ref = _policy_design_cas_ref_from_payload(
        {
            "policy_intent_ref": base_payload["policy_intent_ref"],
            "source_projection": source_projection,
            "canonical_concept_ids": base_payload["canonical_concept_ids"],
            "unresolved_concepts": unresolved,
            "conflicting_concepts": conflicts,
            "reconciliation_trace": reconciliation_trace,
            "normalization_trace": normalization_trace,
        }
    )
    runtime_event_ref = f"event://policy_design_case/concept_spine/{base_payload['run_id']}"
    envelope = {
        "artifact_ref": cas_ref,
        "cas_ref": cas_ref,
        "authority_role": "producer_authority" if status == "pass" else "runtime_blocker",
        "provenance_kind": "runtime_emitted" if status == "pass" else "runtime_blocker",
        "producer_component": POLICY_DESIGN_CONCEPT_SPINE_COMPONENT,
        "producer_version": "2026.05.17+phase8.1.concept_spine",
        "owner": POLICY_DESIGN_CASE_OWNER,
        "record_owner": POLICY_DESIGN_CONCEPT_SPINE_OWNER,
        "runtime_event_ref": runtime_event_ref,
        "diagnostic_event_ref": runtime_event_ref,
        "schema_name": "policyos.policy_design_case.concept_spine",
        "schema_version": POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION,
        "schema_compatibility_ref": schema_compatibility_ref,
        "effective_mode_ref": effective_mode_ref,
        "same_input_closure_ref": same_input_closure_ref,
        "reader_contract": POLICY_DESIGN_CONCEPT_SPINE_CONTRACT_ID,
        "tenant_id": base_payload["tenant_id"],
        "run_id": base_payload["run_id"],
        "job_id": base_payload["job_id"],
        "generated_at": generated.isoformat(),
        "validation_status": status,
    }
    node = {
        **base_payload,
        "concept_ref": cas_ref,
        "cas_ref": cas_ref,
        "runtime_event_ref": runtime_event_ref,
        "diagnostic_event_ref": runtime_event_ref,
        "schema_compatibility_ref": schema_compatibility_ref,
        "schema_compatibility": {
            "decision": "compatible",
            "reader_contract": POLICY_DESIGN_CONCEPT_SPINE_CONTRACT_ID,
        },
        "effective_mode_ref": effective_mode_ref,
        "same_input_closure_ref": same_input_closure_ref,
        "same_input_closure": {
            "closure_id": f"closure.concept_spine.{base_payload['run_id']}",
            "status": "closed" if status == "pass" else "blocked",
            "policy_intent_ref": base_payload["policy_intent_ref"],
            "evidence_input_refs": _policy_design_concept_input_refs(source_projection),
            "same_input_closure_ref": same_input_closure_ref,
        },
        "runtime_authority_envelope": envelope,
    }
    return validate_policy_design_case_concept_spine(node)


def validate_policy_design_case_concept_spine(spine: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one per-run concept-spine authority node."""

    if not isinstance(spine, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_invalid",
            "Concept spine must be a mapping.",
        )
    normalized = dict(spine)
    schema_version = _policy_design_required_text(
        spine.get("schema_version"),
        "policy_design_concept_spine_schema_version_missing",
    )
    if schema_version != POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_schema_version_invalid",
            "Concept spine must use the Phase 8.1 runtime-quality schema version.",
        )
    if _policy_design_required_text(
        spine.get("contract_id"),
        "policy_design_concept_spine_contract_id_missing",
    ) != POLICY_DESIGN_CONCEPT_SPINE_CONTRACT_ID:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_contract_id_invalid",
            "Concept spine contract id is not recognized.",
        )
    if _policy_design_required_text(
        spine.get("node_type"),
        "policy_design_concept_spine_node_type_missing",
    ) != "concept_spine":
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_node_type_invalid",
            "Concept spine node must use the concept_spine node type.",
        )
    if _policy_design_required_text(
        spine.get("owner"),
        "policy_design_concept_spine_owner_missing",
    ) != POLICY_DESIGN_CONCEPT_SPINE_OWNER:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_owner_invalid",
            "Concept spine must be owned by policy semantics.",
        )
    for key in (
        "run_id",
        "job_id",
        "tenant_id",
        "policy_intent_ref",
        "cas_ref",
        "runtime_event_ref",
        "diagnostic_event_ref",
        "schema_compatibility_ref",
        "effective_mode_ref",
        "same_input_closure_ref",
    ):
        value = _policy_design_required_text(
            spine.get(key),
            f"policy_design_concept_spine_{key}_missing",
        )
        _policy_design_skeleton_reject_forbidden_ref(value)
    authority = spine.get("runtime_authority_envelope")
    if not isinstance(authority, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_authority_missing",
            "Concept spine must carry a runtime authority envelope.",
        )
    source_projection = spine.get("source_projection")
    if not isinstance(source_projection, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_source_projection_missing",
            "Concept spine must record source projection inputs.",
        )
    components = _policy_design_text_list(source_projection.get("components"))
    missing_components = [
        component
        for component in POLICY_DESIGN_CONCEPT_SPINE_SOURCE_COMPONENTS
        if component not in components
    ]
    if missing_components:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_source_projection_incomplete",
            "Concept spine must project every Phase 8.1 source component.",
        )

    concept_rows = spine.get("canonical_concepts")
    if not isinstance(concept_rows, list):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_concepts_missing",
            "Concept spine must record canonical_concepts.",
        )
    normalized_concepts = [
        _policy_design_validate_concept_row(row)
        for row in concept_rows
    ]
    concept_ids = [str(row["canonical_concept_id"]) for row in normalized_concepts]
    if len(set(concept_ids)) != len(concept_ids):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_duplicate_concept",
            "Concept spine canonical concept ids must be unique.",
        )
    expected_ids = _policy_design_text_list(spine.get("canonical_concept_ids"))
    if expected_ids != concept_ids:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_id_index_mismatch",
            "Concept spine canonical_concept_ids must match canonical_concepts.",
        )
    unresolved = _policy_design_mapping_list(spine.get("unresolved_concepts"))
    conflicts = _policy_design_mapping_list(spine.get("conflicting_concepts"))
    raw_reconciliation_trace = spine.get("reconciliation_trace")
    if not isinstance(raw_reconciliation_trace, list):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_reconciliation_trace_missing",
            "Concept spine must record the Wave 9 reconciliation trace.",
        )
    reconciliation_trace = [
        _policy_design_validate_concept_reconciliation_trace_entry(entry)
        for entry in raw_reconciliation_trace
    ]
    raw_normalization_trace = spine.get("normalization_trace")
    if not isinstance(raw_normalization_trace, list):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_normalization_trace_missing",
            "Concept spine must record the Wave 9 normalization trace.",
        )
    normalization_trace = [
        _policy_design_validate_concept_normalization_trace_entry(entry)
        for entry in raw_normalization_trace
    ]
    blockers = _policy_design_mapping_list(spine.get("blockers"))
    closure_gaps = _policy_design_concept_closure_gaps(normalized_concepts)
    semantic_mismatches = _policy_design_semantic_mismatches(normalized_concepts)
    status = _policy_design_required_text(
        spine.get("status"),
        "policy_design_concept_spine_status_missing",
    )
    if status not in {"pass", "blocked"}:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_status_invalid",
            "Concept spine status must be pass or blocked.",
        )
    if status == "pass" and not normalized_concepts:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_empty",
            "Passing concept spine must include at least one canonical concept.",
        )
    unresolved_or_conflict = bool(unresolved or conflicts)
    if unresolved_or_conflict:
        blocker_codes = {str(blocker.get("code")) for blocker in blockers}
        if not {
            "policy_design_concept_unresolved",
            "policy_design_concept_conflict",
        }.intersection(blocker_codes):
            raise PolicyDesignCaseAuthorityError(
                "policy_design_concept_spine_blocker_missing",
                "Unresolved or conflicting concepts must emit typed blockers.",
            )
        if status != "blocked":
            raise PolicyDesignCaseAuthorityError(
                "policy_design_concept_spine_blocker_missing",
                "Concept spine with unresolved or conflicting concepts must be blocked.",
            )
    if closure_gaps:
        blocker_codes = {str(blocker.get("code")) for blocker in blockers}
        if "policy_design_concept_binding_missing" not in blocker_codes:
            raise PolicyDesignCaseAuthorityError(
                "policy_design_concept_spine_blocker_missing",
                "Concept spine closure gaps must emit a typed blocker.",
            )
        if status != "blocked":
            raise PolicyDesignCaseAuthorityError(
                "policy_design_concept_spine_blocker_missing",
                "Concept spine with incomplete closure fields must be blocked.",
            )
    if semantic_mismatches:
        blocker_codes = {str(blocker.get("code")) for blocker in blockers}
        missing_codes = {
            str(mismatch["code"])
            for mismatch in semantic_mismatches
            if str(mismatch["code"]) not in blocker_codes
        }
        if missing_codes:
            raise PolicyDesignCaseAuthorityError(
                "policy_design_concept_spine_blocker_missing",
                "Concept spine semantic mismatches must emit typed blockers.",
            )
        if status != "blocked":
            raise PolicyDesignCaseAuthorityError(
                "policy_design_concept_spine_blocker_missing",
                "Concept spine with semantic mismatches must be blocked.",
            )
    blocked_normalization = [
        entry
        for entry in normalization_trace
        if entry["status"] == "blocked"
    ]
    if blocked_normalization:
        blocker_codes = {str(blocker.get("code")) for blocker in blockers}
        missing_codes = {
            str(entry["typed_blocker"]["code"])
            for entry in blocked_normalization
            if str(entry["typed_blocker"]["code"]) not in blocker_codes
        }
        if missing_codes:
            raise PolicyDesignCaseAuthorityError(
                "policy_design_concept_spine_blocker_missing",
                "Blocked normalization trace entries must emit typed blockers.",
            )
        if status != "blocked":
            raise PolicyDesignCaseAuthorityError(
                "policy_design_concept_spine_blocker_missing",
                "Concept spine with blocked raw-term normalization must be blocked.",
            )
    if blockers and status != "blocked":
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_blocker_missing",
            "Concept spine blockers cannot be hidden behind a passing status.",
        )
    for blocker in blockers:
        _policy_design_validate_concept_blocker(blocker)
    normalized_authority = _policy_design_concept_authority_envelope(
        authority,
        status=status,
        cas_ref=_policy_design_required_text(
            spine.get("cas_ref"),
            "policy_design_concept_spine_cas_ref_missing",
        ),
        run_id=_policy_design_required_text(
            spine.get("run_id"),
            "policy_design_concept_spine_run_id_missing",
        ),
        job_id=_policy_design_required_text(
            spine.get("job_id"),
            "policy_design_concept_spine_job_id_missing",
        ),
        tenant_id=_policy_design_required_text(
            spine.get("tenant_id"),
            "policy_design_concept_spine_tenant_id_missing",
        ),
        policy_intent_ref=_policy_design_required_text(
            spine.get("policy_intent_ref"),
            "policy_design_concept_spine_policy_intent_ref_missing",
        ),
    )
    normalized["schema_version"] = POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION
    normalized["contract_id"] = POLICY_DESIGN_CONCEPT_SPINE_CONTRACT_ID
    normalized["node_type"] = "concept_spine"
    normalized["owner"] = POLICY_DESIGN_CONCEPT_SPINE_OWNER
    normalized["runtime_authority_envelope"] = normalized_authority
    normalized["canonical_concepts"] = normalized_concepts
    normalized["canonical_concept_ids"] = concept_ids
    normalized["reconciliation_trace"] = reconciliation_trace
    normalized["normalization_trace"] = normalization_trace
    normalized["unresolved_concepts"] = unresolved
    normalized["conflicting_concepts"] = conflicts
    normalized["claim_numerical_semantics_refs"] = _policy_design_collect_concept_bindings(
        normalized_concepts,
        "claim_numerical_semantics_refs",
        id_key="claim_id",
    )
    normalized["blockers"] = blockers
    return normalized


def policy_design_concept_spine_json_schema() -> dict[str, Any]:
    """Return the JSON schema for the Phase 8.1 concept spine record."""

    concept_required = [
        "canonical_concept_id",
        *POLICY_DESIGN_CONCEPT_SPINE_REQUIRED_CLOSURE_FIELDS,
        "world_refs",
    ]
    return {
        "$id": (
            "https://schemas.polisyos.dev/runtime_quality/"
            "policy_design_concept_spine_v1.schema.json"
        ),
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Policy Design Concept Spine",
        "type": "object",
        "required": [
            "schema_version",
            "contract_id",
            "node_type",
            "record_id",
            "run_id",
            "job_id",
            "tenant_id",
            "policy_intent_ref",
            "runtime_authority_envelope",
            "source_projection",
            "canonical_concept_ids",
            "canonical_concepts",
            "reconciliation_trace",
            "normalization_trace",
            "unresolved_concepts",
            "conflicting_concepts",
            "claim_numerical_semantics_refs",
            "blockers",
            "status",
        ],
        "properties": {
            "schema_version": {"const": POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION},
            "contract_id": {"const": POLICY_DESIGN_CONCEPT_SPINE_CONTRACT_ID},
            "node_type": {"const": "concept_spine"},
            "record_id": {"type": "string", "minLength": 1},
            "run_id": {"type": "string", "minLength": 1},
            "job_id": {"type": "string", "minLength": 1},
            "tenant_id": {"type": "string", "minLength": 1},
            "policy_intent_ref": {"type": "string", "minLength": 1},
            "runtime_authority_envelope": {"type": "object"},
            "source_projection": {"type": "object"},
            "canonical_concept_ids": {"type": "array", "items": {"type": "string"}},
            "canonical_concepts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": concept_required,
                },
            },
            "reconciliation_trace": {"type": "array"},
            "normalization_trace": {"type": "array"},
            "unresolved_concepts": {"type": "array"},
            "conflicting_concepts": {"type": "array"},
            "claim_numerical_semantics_refs": {"type": "array"},
            "blockers": {"type": "array"},
            "status": {"enum": ["pass", "blocked"]},
        },
        "additionalProperties": True,
    }


def build_policy_design_case_walking_skeleton(
    *,
    case_id: str = "pdc-wave-6-walking-skeleton-research",
    run_id: str = "run_pdc_wave_6_research_001",
    job_id: str = "job_pdc_wave_6_walking_skeleton_001",
    tenant_id: str = "tenant_pdc_demo",
    requested_authority_level: str = "research",
    effective_execution_profile: str = "research",
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build the Wave 6 research-only Policy Design Case walking skeleton.

    The skeleton proves the runtime-quality ref path before Lex, Fabric, Scholar,
    Foundry, Scientist, and claim compiler domain record families are complete.
    It is intentionally non-production and accepts only the narrow
    ``single_line_evidence_deficit`` in the research profile.
    """

    generated = _utc(generated_at)
    effective_profile = _policy_design_required_text(
        effective_execution_profile,
        "policy_design_case_effective_execution_profile_missing",
    )
    requested_profile = _policy_design_required_text(
        requested_authority_level,
        "policy_design_case_requested_authority_level_missing",
    )
    intent_ref = _policy_design_skeleton_cas_ref("1")
    concept_ref = _policy_design_skeleton_cas_ref("2")
    jurisdiction_ref = _policy_design_skeleton_cas_ref("3")
    producer_ref = _policy_design_skeleton_cas_ref("4")
    claim_ref = _policy_design_skeleton_cas_ref("5")
    deficit_ref = _policy_design_skeleton_cas_ref("6")

    intent_envelope = build_policy_intent_envelope(
        intent_id="intent-wave-6-walking-skeleton",
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        policy_problem="Stub research policy case needs vertical runtime refs.",
        desired_outcome="Prove the Policy Design Case reference path end to end.",
        proposed_intervention="Use a non-production walking skeleton case contract.",
        jurisdiction="UA",
        target_population="research fixture population",
        policy_time="2026-05-17",
        data_time="fixture-only",
        requester_preferred_conclusion=None,
        requested_authority_level=requested_profile,
        affected_stakeholders=["runtime quality", "domain producer owners"],
        constraints=["non-production walking skeleton only"],
        objectives=["prove intent to evidence to claim refs"],
        assumptions=["domain producer record families are not implemented yet"],
        evidence_expectations=["stub producer evidence accepted only for research"],
        authoring_provenance={
            "captured_by": POLICY_DESIGN_CASE_RUNTIME_QUALITY_COMPONENT,
            "capture_ref": intent_ref,
        },
        generated_at=generated,
    )
    capability_ledger = build_capability_selection_ledger(
        ledger_ref=_policy_design_skeleton_cas_ref("7"),
        literature_evidence_required=False,
        duties=[
            build_capability_duty_record(
                capability=capability,
                state="selected",
                evidence_ref=producer_ref,
                runtime_event_ref=(
                    "event://policy_design_case/wave6/walking_skeleton/"
                    f"capability/{capability}"
                ),
                cas_ref=producer_ref,
                reason=(
                    "Wave 6 walking skeleton selects a runtime-quality stub "
                    "instead of a real domain producer."
                ),
            )
            for capability in POLICY_DESIGN_REQUIRED_CAPABILITIES
        ],
    )
    nodes = [
        _policy_design_walking_skeleton_node(
            node_type="policy_intent",
            record_id="intent.wave6.walking_skeleton",
            cas_ref=intent_ref,
            schema_name="policy_design_case.walking_skeleton.intent_stub",
            generated_at=generated,
            run_id=run_id,
            job_id=job_id,
            tenant_id=tenant_id,
            requested_execution_profile=requested_profile,
            effective_execution_profile=effective_profile,
            policy_intent_ref=intent_ref,
            evidence_input_refs=[intent_ref],
            payload={
                "intent_ref": intent_ref,
                "intent_envelope_ref": intent_ref,
                "requested_authority_level": requested_profile,
                "stub_record": True,
            },
        ),
        _policy_design_walking_skeleton_node(
            node_type="concept_spine",
            record_id="concept.wave6.walking_skeleton",
            cas_ref=concept_ref,
            schema_name="policy_design_case.walking_skeleton.concept_jurisdiction_stub",
            generated_at=generated,
            run_id=run_id,
            job_id=job_id,
            tenant_id=tenant_id,
            requested_execution_profile=requested_profile,
            effective_execution_profile=effective_profile,
            policy_intent_ref=intent_ref,
            evidence_input_refs=[intent_ref],
            payload={
                "intent_ref": intent_ref,
                "concept_ref": concept_ref,
                "jurisdiction_ref": jurisdiction_ref,
                "canonical_concept_id": "stub.concept.policy_design_case_wave6",
                "jurisdiction_code": "UA",
                "stub_record": True,
            },
        ),
        _policy_design_walking_skeleton_node(
            node_type="producer_evidence",
            record_id="producer_evidence.wave6.walking_skeleton",
            cas_ref=producer_ref,
            schema_name="policy_design_case.walking_skeleton.producer_evidence_stub",
            generated_at=generated,
            run_id=run_id,
            job_id=job_id,
            tenant_id=tenant_id,
            requested_execution_profile=requested_profile,
            effective_execution_profile=effective_profile,
            policy_intent_ref=intent_ref,
            evidence_input_refs=[intent_ref, concept_ref, jurisdiction_ref],
            payload={
                "intent_ref": intent_ref,
                "producer_evidence_ref": producer_ref,
                "evidence_ref": producer_ref,
                "concept_ref": concept_ref,
                "jurisdiction_ref": jurisdiction_ref,
                "producer_component": POLICY_DESIGN_WALKING_SKELETON_STUB_COMPONENT,
                "producer_owner": POLICY_DESIGN_CASE_OWNER,
                "record_family": "walking_skeleton_stub_producer_evidence.v1",
                "stub_record": True,
                "real_domain_producer": False,
            },
        ),
        _policy_design_walking_skeleton_node(
            node_type="claim",
            record_id="claim.wave6.walking_skeleton",
            cas_ref=claim_ref,
            schema_name="policy_design_case.walking_skeleton.major_claim_stub",
            generated_at=generated,
            run_id=run_id,
            job_id=job_id,
            tenant_id=tenant_id,
            requested_execution_profile=requested_profile,
            effective_execution_profile=effective_profile,
            policy_intent_ref=intent_ref,
            evidence_input_refs=[producer_ref, deficit_ref],
            payload={
                "claim_ref": claim_ref,
                "claim_id": "claim.wave6.walking_skeleton.major",
                "text": "Wave 6 walking skeleton can carry runtime refs to a claim.",
                "major": True,
                "intent_ref": intent_ref,
                "concept_refs": [concept_ref],
                "jurisdiction_refs": [jurisdiction_ref],
                "producer_evidence_refs": [producer_ref],
                "accepted_deficit_refs": [deficit_ref],
                "stub_record": True,
            },
        ),
        _policy_design_walking_skeleton_node(
            node_type="deficit",
            record_id="deficit.wave6.single_line_evidence_deficit",
            cas_ref=deficit_ref,
            schema_name="policy_design_case.walking_skeleton.assurance_deficit_stub",
            generated_at=generated,
            run_id=run_id,
            job_id=job_id,
            tenant_id=tenant_id,
            requested_execution_profile=requested_profile,
            effective_execution_profile=effective_profile,
            policy_intent_ref=intent_ref,
            evidence_input_refs=[producer_ref],
            payload={
                "deficit_ref": deficit_ref,
                "deficit_kind": _POLICY_DESIGN_WALKING_SKELETON_ACCEPTED_DEFICIT_KIND,
                "status": "accepted",
                "claim_ref": claim_ref,
                "producer_evidence_ref": producer_ref,
                "accepted_profiles": ["research"],
                "rejected_profiles": ["governed", "production"],
                "rationale": (
                    "Single-line evidence is accepted only to prove the walking "
                    "skeleton ref path before domain producers exist."
                ),
                "stub_record": True,
            },
        ),
    ]
    case = build_policy_design_case_profile(
        case_id=case_id,
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        effective_execution_profile=effective_profile,
        runtime_authority={
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_emitted",
            "cas_ref": _policy_design_skeleton_cas_ref("8"),
            "runtime_event_ref": "event://policy_design_case/wave6/walking_skeleton/case",
            "same_input_closure_ref": _policy_design_skeleton_cas_ref("9"),
            "effective_mode_ref": _policy_design_skeleton_cas_ref("a"),
            "schema_compatibility_ref": _policy_design_skeleton_cas_ref("b"),
        },
        capability_ledger=capability_ledger,
        intent_envelope=intent_envelope,
        nodes=nodes,
        generated_at=generated,
    )
    case["walking_skeleton_contract"] = {
        "schema_version": POLICY_DESIGN_WALKING_SKELETON_SCHEMA_VERSION,
        "contract_id": POLICY_DESIGN_WALKING_SKELETON_CONTRACT_ID,
        "profile": "research",
        "non_production": True,
        "domain_record_maturity": "stub",
        "accepted_deficit_kind": _POLICY_DESIGN_WALKING_SKELETON_ACCEPTED_DEFICIT_KIND,
        "intent_ref": intent_ref,
        "concept_ref": concept_ref,
        "jurisdiction_ref": jurisdiction_ref,
        "producer_evidence_ref": producer_ref,
        "major_claim_ref": claim_ref,
        "accepted_deficit_ref": deficit_ref,
        "blocked_profiles": ["governed", "production"],
    }
    case["major_claims"] = [
        {
            "claim_id": "claim.wave6.walking_skeleton.major",
            "major": True,
            "claim_ref": claim_ref,
            "producer_evidence_refs": [producer_ref],
            "accepted_deficit_refs": [deficit_ref],
        }
    ]
    return validate_policy_design_case_profile(case)


def build_capability_duty_record(
    *,
    capability: str,
    state: str,
    owner: str | None = None,
    required: bool = True,
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
    cas_ref: str | None = None,
    blocker_ref: str | None = None,
    degradation_ref: str | None = None,
    allowed_profiles: Iterable[str] = (),
    reason: str | None = None,
    downstream_impact: str | None = None,
) -> dict[str, Any]:
    """Emit one normalized Policy Design Case capability-duty record."""

    canonical_capability = _policy_design_capability_name(capability)
    duty: dict[str, Any] = {
        "capability": canonical_capability,
        "state": _policy_design_duty_state(state),
        "owner": _policy_design_text(owner)
        or _POLICY_DESIGN_CAPABILITY_OWNERS[canonical_capability],
        "required": bool(required),
    }
    for key, value in (
        ("evidence_ref", evidence_ref),
        ("runtime_event_ref", runtime_event_ref),
        ("cas_ref", cas_ref),
        ("blocker_ref", blocker_ref),
        ("degradation_ref", degradation_ref),
        ("reason", reason),
        ("downstream_impact", downstream_impact),
    ):
        text = _policy_design_text(value)
        if text is not None:
            duty[key] = text
    profiles = tuple(
        profile
        for profile in (_policy_design_text(item) for item in allowed_profiles)
        if profile is not None
    )
    if profiles:
        duty["allowed_profiles"] = list(profiles)
    return duty


def build_capability_selection_ledger(
    *,
    ledger_ref: str,
    duties: Iterable[Mapping[str, Any]],
    literature_evidence_required: bool = False,
    schema_version: str = POLICY_DESIGN_CAPABILITY_LEDGER_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Emit the runtime-owned capability selection ledger payload."""

    return {
        "schema_version": schema_version,
        "ledger_ref": _policy_design_required_text(
            ledger_ref,
            "policy_design_capability_ledger_ref_missing",
        ),
        "literature_evidence_required": bool(literature_evidence_required),
        "duties": [dict(duty) for duty in duties],
    }


def build_policy_design_case_registry_entry(
    *,
    registry_ref: str = RECORD_REGISTRY_READINESS_CHECK,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Emit the runtime case's pointer into the minimum record-family registry."""

    return {
        "schema_version": POLICY_DESIGN_CASE_REGISTRY_ENTRY_SCHEMA_VERSION,
        "registry_ref": _policy_design_required_text(
            registry_ref,
            "policy_design_case_registry_ref_missing",
        ),
        "readiness_check": RECORD_REGISTRY_READINESS_CHECK,
        "scorecard_gate": RECORD_REGISTRY_SCORECARD_GATE,
        "enforcement_function": RECORD_REGISTRY_ENFORCEMENT_FUNCTION,
        "record_family_count": len(POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES),
        "generated_at": _utc(generated_at).isoformat(),
    }


def validate_capability_selection_ledger(
    ledger: Mapping[str, Any],
    *,
    effective_execution_profile: str,
    final_major_claims: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate and normalize the Policy Design Case capability ledger."""

    return _policy_design_case_capability_ledger(
        ledger,
        effective_execution_profile=effective_execution_profile,
        final_major_claims=final_major_claims,
    )


def validate_policy_design_case_profile(case: Mapping[str, Any]) -> dict[str, Any]:
    """Validate that a Policy Design Case remains inside runtime-quality authority."""

    if not isinstance(case, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_case_profile_invalid",
            "Policy Design Case profile must be a mapping.",
        )
    schema_version = _policy_design_text(case.get("schema_version"))
    if schema_version != POLICY_DESIGN_CASE_SCHEMA_VERSION:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_case_schema_version_invalid",
            "Policy Design Case profile must use the runtime-quality schema version.",
        )
    profile = _policy_design_text(case.get("profile"))
    if profile != POLICY_DESIGN_CASE_PROFILE:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_case_profile_name_invalid",
            "Policy Design Case profile must be policy_design.",
        )
    owner = _policy_design_text(case.get("owner"))
    if owner != POLICY_DESIGN_CASE_OWNER:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_case_runtime_quality_owner_required",
            "Policy Design Case authority must be owned by runtime quality.",
        )
    _policy_design_required_text(case.get("tenant_id"), "policy_design_case_tenant_id_missing")
    effective_execution_profile = _policy_design_required_text(
        case.get("effective_execution_profile"),
        "policy_design_case_effective_execution_profile_missing",
    )
    authority_source = case.get("authority_chain") or case.get("runtime_authority")
    if not isinstance(authority_source, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_case_authority_chain_missing",
            "Policy Design Case profile must carry runtime authority metadata.",
        )
    authority_chain = _policy_design_case_authority_chain(authority_source)
    intent_source = case.get("intent_envelope")
    if not isinstance(intent_source, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_intent_envelope_missing",
            "Policy Design Case profile must carry a validated intent envelope.",
        )
    intent_envelope = validate_policy_intent_envelope(intent_source)
    capability_ledger = _policy_design_case_capability_ledger(
        case.get("capability_ledger"),
        effective_execution_profile=effective_execution_profile,
        final_major_claims=_policy_design_case_final_major_claims(case),
    )
    case_registry_entry = _policy_design_case_registry_entry(
        case.get("case_registry_entry")
    )
    authority_profile = _policy_design_case_authority_profile(
        requested_authority_level=intent_envelope["requested_authority_level"],
        effective_execution_profile=effective_execution_profile,
    )
    nodes = _policy_design_case_validate_known_nodes(
        _policy_design_case_nodes(case.get("nodes") or ())
    )
    walking_skeleton_contract = _policy_design_case_walking_skeleton_contract(
        case.get("walking_skeleton_contract"),
        effective_execution_profile=effective_execution_profile,
        nodes=nodes,
    )
    jurisdiction_spine = case.get("jurisdiction_spine")
    validated_jurisdiction_spine = (
        validate_policy_design_jurisdiction_spine(jurisdiction_spine)
        if jurisdiction_spine is not None
        else None
    )
    validated = dict(case)
    validated["owner"] = POLICY_DESIGN_CASE_OWNER
    validated["authority_chain"] = authority_chain
    validated["intent_envelope"] = intent_envelope
    validated["capability_ledger"] = capability_ledger
    validated["case_registry_entry"] = case_registry_entry
    validated["authority_profile"] = authority_profile
    validated["profile_metadata"] = _policy_design_case_profile_metadata()
    validated["core_node_types"] = list(POLICY_DESIGN_CASE_CORE_NODE_TYPES)
    validated["reserved_node_families"] = list(POLICY_DESIGN_CASE_RESERVED_NODE_FAMILIES)
    validated["nodes"] = nodes
    if validated_jurisdiction_spine is not None:
        validated["jurisdiction_spine"] = validated_jurisdiction_spine
    if walking_skeleton_contract is not None:
        validated["walking_skeleton_contract"] = walking_skeleton_contract
    return validated


def build_assurance_case_for_scorecard(
    scorecard: Mapping[str, Any],
    *,
    owner: str = DEFAULT_OWNER,
    reviewer_attribution: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a claim-argument-evidence view over an existing quality scorecard."""

    generated_at = _utc(now)
    blockers = _blockers(scorecard)
    warnings = _warnings(scorecard)
    evidence = _evidence(scorecard)
    claim_status = _claim_status(scorecard, blockers=blockers)
    non_overridable = sorted(
        {
            str(blocker["code"])
            for blocker in blockers
            if str(blocker.get("code") or "") in _NON_OVERRIDABLE_BLOCKER_CODES
            or bool(blocker.get("non_overridable"))
        }
    )
    next_command = _next_diagnostic_command(blockers)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "claim": {
            "text": "Serious PolicyOS closeout is supported by runtime-owned diagnostic authority.",
            "status": claim_status,
            "run_id": _text_or_none(scorecard.get("run_id")),
            "job_id": _text_or_none(scorecard.get("job_id")),
            "canary_kind": _text_or_none(scorecard.get("canary_kind")),
            "quality_status": _text_or_none(scorecard.get("quality_status")),
            "approval_state": _text_or_none(scorecard.get("approval_state")),
        },
        "subclaims": _subclaims(scorecard),
        "argument": (
            "The scorecard may support closeout only when runtime refs, authority "
            "envelopes, phase barriers, mode/fallback ledgers, schema compatibility, "
            "semantic bindings, attestation, diagnostic SLOs, and fitness controls "
            "show no blocking defeaters."
        ),
        "argument_strategy": "runtime_authority_graph",
        "evidence": evidence,
        "assumptions": [
            "The scorecard is a reader of runtime authority, not an authority producer.",
            "Bundle-local files are diagnostic projections unless backed by runtime refs.",
            "Warnings and stale diagnostics cannot satisfy serious deterministic closeout.",
        ],
        "contexts": {
            "scorecard_generated_at": _text_or_none(scorecard.get("generated_at")),
            "quality_scorecard_ref": _text_or_none(scorecard.get("quality_scorecard_ref")),
            "quality_evidence_bundle_path": _text_or_none(
                scorecard.get("quality_evidence_bundle_path")
            ),
            "stage_scores": dict(scorecard.get("stage_scores") or {}),
        },
        "defeaters": [*blockers, *warnings],
        "blockers": blockers,
        "unresolved_uncertainty": _unresolved_uncertainty(blockers, warnings),
        "confidence_limits": _confidence_limits(claim_status, blockers, warnings),
        "non_overridable_blockers": non_overridable,
        "reviewer_attribution": dict(
            reviewer_attribution
            or {
                "reviewer_id": "unassigned",
                "reviewed_at": None,
                "review_status": "pending",
            }
        ),
        "owner": _required_text(owner, DEFAULT_OWNER),
        "next_diagnostic_command": next_command,
    }


def _subclaims(scorecard: Mapping[str, Any]) -> list[dict[str, Any]]:
    gates = [gate for gate in scorecard.get("quality_gates", []) if isinstance(gate, Mapping)]
    by_stage: dict[str, list[Mapping[str, Any]]] = {}
    for gate in gates:
        stage = _required_text(gate.get("stage"), "unknown")
        by_stage.setdefault(stage, []).append(gate)
    subclaims: list[dict[str, Any]] = []
    for stage, stage_gates in sorted(by_stage.items()):
        failing = [
            _required_text(gate.get("code") or gate.get("name"), "unknown_gate")
            for gate in stage_gates
            if gate.get("blocking") and gate.get("status") == "fail"
        ]
        subclaims.append(
            {
                "claim": f"{stage} diagnostic gates are satisfied.",
                "status": "blocked" if failing else "supported",
                "stage": stage,
                "gate_count": len(stage_gates),
                "blocking_codes": sorted(set(failing)),
                "evidence_refs": sorted(
                    {
                        ref
                        for ref in (
                            _text_or_none(gate.get("evidence_ref"))
                            for gate in stage_gates
                        )
                        if ref is not None
                    }
                ),
            }
        )
    return subclaims


def _evidence(scorecard: Mapping[str, Any]) -> list[dict[str, Any]]:
    refs = scorecard.get("evidence_refs")
    evidence: list[dict[str, Any]] = []
    if isinstance(refs, Mapping):
        for key, value in sorted(refs.items()):
            ref = _text_or_none(value)
            if ref is not None:
                evidence.append({"key": str(key), "ref": ref, "source": "scorecard.evidence_refs"})
    for gate in scorecard.get("quality_gates", []):
        if not isinstance(gate, Mapping):
            continue
        ref = _text_or_none(gate.get("evidence_ref"))
        if ref is None:
            continue
        evidence.append(
            {
                "key": _required_text(gate.get("name"), "quality_gate"),
                "ref": ref,
                "source": "scorecard.quality_gates",
                "status": _text_or_none(gate.get("status")),
            }
        )
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in evidence:
        deduped[(str(item["key"]), str(item["ref"]))] = item
    return list(deduped.values())


def _blockers(scorecard: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for failure in scorecard.get("blocking_quality_failures", []):
        if not isinstance(failure, Mapping):
            continue
        blockers.append(
            {
                "code": _required_text(
                    failure.get("code") or failure.get("gate"),
                    "quality_blocker",
                ),
                "message": _required_text(failure.get("message"), "Quality gate blocked closeout."),
                "layer": _text_or_none(failure.get("layer")),
                "phase": _text_or_none(failure.get("phase")),
                "evidence_ref": _text_or_none(failure.get("evidence_ref")),
                "next_action": _text_or_none(failure.get("next_action")),
            }
        )
    return blockers


def _warnings(scorecard: Mapping[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for warning in scorecard.get("warnings", []):
        if not isinstance(warning, Mapping):
            continue
        warnings.append(
            {
                "code": _required_text(
                    warning.get("code") or warning.get("gate"),
                    "quality_warning",
                ),
                "message": _required_text(warning.get("message"), "Quality warning."),
                "layer": _text_or_none(warning.get("layer")),
                "phase": _text_or_none(warning.get("phase")),
                "evidence_ref": _text_or_none(warning.get("evidence_ref")),
                "next_action": _text_or_none(warning.get("next_action")),
            }
        )
    return warnings


def _claim_status(scorecard: Mapping[str, Any], *, blockers: list[dict[str, Any]]) -> str:
    if blockers:
        return "blocked"
    if _required_text(scorecard.get("quality_status"), "").casefold() == "pass":
        return "supported"
    return "qualified"


def _unresolved_uncertainty(
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> list[str]:
    if blockers:
        return [
            "Closeout support is unresolved until blocking diagnostics are remediated: "
            + ", ".join(sorted({str(blocker["code"]) for blocker in blockers}))
        ]
    if warnings:
        return [
            "Closeout has warning-level diagnostic uncertainty: "
            + ", ".join(sorted({str(warning["code"]) for warning in warnings}))
        ]
    return []


def _confidence_limits(
    claim_status: str,
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    if claim_status == "supported":
        upper_bound = 0.99 if not warnings else 0.9
        lower_bound = 0.8 if not warnings else 0.6
    elif blockers:
        upper_bound = 0.49
        lower_bound = 0.0
    else:
        upper_bound = 0.75
        lower_bound = 0.25
    return {
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "basis": "scorecard blocker/warning projection over runtime authority graph",
    }


def _next_diagnostic_command(blockers: list[dict[str, Any]]) -> str:
    for blocker in blockers:
        next_action = _text_or_none(blocker.get("next_action"))
        if next_action is not None and next_action.startswith("uv run "):
            return next_action
    return DEFAULT_NEXT_DIAGNOSTIC_COMMAND


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC, microsecond=0)
    return value.astimezone(UTC).replace(microsecond=0)


def _text_or_none(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _required_text(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _policy_design_case_profile_metadata() -> dict[str, Any]:
    return {
        **POLICY_DESIGN_CASE_PROFILE_METADATA,
        "core_node_types": list(POLICY_DESIGN_CASE_CORE_NODE_TYPES),
        "reserved_node_families": list(POLICY_DESIGN_CASE_RESERVED_NODE_FAMILIES),
        "authority_chain": list(POLICY_DESIGN_CASE_PROFILE_METADATA["authority_chain"]),
        "mapping": dict(POLICY_DESIGN_CASE_NODE_MAPPING),
    }


def _policy_design_case_authority_chain(authority: Mapping[str, Any]) -> dict[str, Any]:
    role = _policy_design_required_text(
        authority.get("authority_role"),
        "policy_design_case_authority_role_missing",
    )
    if role not in _POLICY_DESIGN_ALLOWED_AUTHORITY_ROLES:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_case_authority_role_invalid",
            "Policy Design Case authority must be producer_authority or runtime_blocker.",
        )
    provenance = _policy_design_required_text(
        authority.get("provenance_kind"),
        "policy_design_case_provenance_missing",
    )
    if provenance not in _POLICY_DESIGN_ALLOWED_PROVENANCE:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_case_provenance_invalid",
            "Policy Design Case authority must be emitted by runtime quality.",
        )
    normalized: dict[str, Any] = {
        "runtime_quality_authority": True,
        "authority_role": role,
        "provenance_kind": provenance,
        "producer_component": _policy_design_text(authority.get("producer_component"))
        or POLICY_DESIGN_CASE_RUNTIME_QUALITY_COMPONENT,
        "owner": _policy_design_text(authority.get("owner")) or POLICY_DESIGN_CASE_OWNER,
        "schema_name": _policy_design_text(authority.get("schema_name"))
        or POLICY_DESIGN_CASE_SCHEMA_VERSION,
        "schema_version": _policy_design_text(authority.get("schema_version")) or "1.0",
    }
    if normalized["owner"] != POLICY_DESIGN_CASE_OWNER:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_case_runtime_quality_owner_required",
            "Policy Design Case authority must be owned by runtime quality.",
        )
    for key, code in _POLICY_DESIGN_REQUIRED_AUTHORITY_REFS.items():
        value = _policy_design_required_text(authority.get(key), code)
        if _looks_like_local_path(value):
            raise PolicyDesignCaseAuthorityError(
                "policy_design_case_local_ref_not_authority",
                "Policy Design Case authority refs must be runtime refs, not local paths.",
            )
        normalized[key] = value
    return normalized


def _policy_design_case_registry_entry(entry: object) -> dict[str, Any]:
    if not isinstance(entry, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_case_registry_entry_missing",
            "Policy Design Case profile must name its minimum record-registry entry.",
        )
    normalized = dict(entry)
    schema_version = _policy_design_required_text(
        entry.get("schema_version"),
        "policy_design_case_registry_entry_schema_version_missing",
    )
    if schema_version != POLICY_DESIGN_CASE_REGISTRY_ENTRY_SCHEMA_VERSION:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_case_registry_entry_schema_version_invalid",
            "Policy Design Case registry entry must use the runtime schema version.",
        )
    expected_fields = {
        "readiness_check": RECORD_REGISTRY_READINESS_CHECK,
        "scorecard_gate": RECORD_REGISTRY_SCORECARD_GATE,
        "enforcement_function": RECORD_REGISTRY_ENFORCEMENT_FUNCTION,
    }
    for field_name, expected in expected_fields.items():
        actual = _policy_design_required_text(
            entry.get(field_name),
            f"policy_design_case_registry_entry_{field_name}_missing",
        )
        if actual != expected:
            raise PolicyDesignCaseAuthorityError(
                "policy_design_case_registry_entry_mismatch",
                f"Policy Design Case registry entry has unexpected {field_name}.",
            )
        normalized[field_name] = actual
    normalized["registry_ref"] = _policy_design_required_text(
        entry.get("registry_ref"),
        "policy_design_case_registry_ref_missing",
    )
    try:
        record_family_count = int(entry.get("record_family_count"))
    except (TypeError, ValueError) as exc:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_case_registry_entry_count_invalid",
            "Policy Design Case registry entry must carry a record family count.",
        ) from exc
    minimum_count = len(POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES)
    if record_family_count < minimum_count:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_case_registry_entry_incomplete",
            "Policy Design Case registry entry does not cover all minimum families.",
        )
    normalized["schema_version"] = POLICY_DESIGN_CASE_REGISTRY_ENTRY_SCHEMA_VERSION
    normalized["record_family_count"] = record_family_count
    return normalized


def _policy_design_case_authority_profile(
    *,
    requested_authority_level: object,
    effective_execution_profile: object,
) -> dict[str, Any]:
    requested_profile = _policy_design_required_text(
        requested_authority_level,
        "policy_design_case_requested_authority_level_missing",
    )
    effective_profile = _policy_design_required_text(
        effective_execution_profile,
        "policy_design_case_effective_execution_profile_missing",
    )
    try:
        mapping = policy_authority_profile_mapping(requested_profile)
    except ValueError as exc:
        raise PolicyDesignCaseAuthorityError(
            "policy_intent_requested_authority_level_invalid",
            "Requested authority level must be research, governed, or production.",
        ) from exc
    if mapping.execution_profile != effective_profile:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_case_authority_profile_mismatch",
            (
                "Policy Design Case requested authority, effective execution, "
                "validation, and fallback profiles must reconcile."
            ),
        )
    return {
        "requested_authority_level": mapping.authority_profile,
        "requested_execution_profile": mapping.execution_profile,
        "effective_execution_profile": mapping.execution_profile,
        "validation_profile": mapping.validation_profile,
        "fallback_policy": mapping.fallback_policy,
    }


def _policy_design_concept_source_projection(
    *,
    fabric_entity_resolution: Mapping[str, Any] | None,
    scientist_cross_graph: Mapping[str, Any] | None,
    ir_linker: Mapping[str, Any] | None,
    ir_registry: Mapping[str, Any] | None,
    ir_world: Mapping[str, Any] | None,
) -> dict[str, Any]:
    sources = {
        "fabric_entity_resolution": fabric_entity_resolution,
        "scientist_cross_graph": scientist_cross_graph,
        "ir_linker": ir_linker,
        "ir_registry": ir_registry,
        "ir_world": ir_world,
    }
    return {
        "contract_id": POLICY_DESIGN_CONCEPT_SPINE_CONTRACT_ID,
        "components": list(POLICY_DESIGN_CONCEPT_SPINE_SOURCE_COMPONENTS),
        "component_status": [
            _policy_design_concept_component_status(name, payload)
            for name, payload in sources.items()
        ],
    }


def _policy_design_concept_component_status(
    component: str,
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {
            "component": component,
            "available": False,
            "record_count": 0,
            "input_ref": None,
        }
    input_ref = (
        _policy_design_text(payload.get("cas_ref"))
        or _policy_design_text(payload.get("artifact_ref"))
        or _policy_design_text(payload.get("batch_ref"))
        or _policy_design_text(payload.get("profile_ref"))
        or _policy_design_text(payload.get("schema_version"))
    )
    return {
        "component": component,
        "available": True,
        "record_count": _policy_design_concept_component_record_count(payload),
        "input_ref": input_ref,
    }


def _policy_design_concept_component_record_count(payload: Mapping[str, Any]) -> int:
    for key in (
        "records",
        "entities",
        "entity_records",
        "ontology_snapshot",
        "needs",
        "issues",
        "concepts",
        "world_refs",
        "dataset_bindings",
    ):
        value = payload.get(key)
        if isinstance(value, list | tuple | dict):
            return len(value)
    return len(payload)


def _policy_design_project_ir_registry_concepts(
    concepts: dict[str, dict[str, Any]],
    registry: Mapping[str, Any] | None,
    *,
    unresolved: list[dict[str, Any]],
) -> None:
    if not isinstance(registry, Mapping):
        unresolved.append(
            _policy_design_concept_unresolved(
                source_component="ir_registry",
                source_term="ir_registry",
                reason="missing IR registry projection",
            )
        )
        return
    registry_concepts = _policy_design_registry_items(registry, "concepts")
    for key, raw_spec in registry_concepts.items():
        if not isinstance(raw_spec, Mapping):
            continue
        concept_id = _policy_design_text(raw_spec.get("concept_id")) or _policy_design_text(key)
        if concept_id is None:
            unresolved.append(
                _policy_design_concept_unresolved(
                    source_component="ir_registry",
                    source_term=str(key),
                    reason="concept registry row is missing concept_id",
                )
            )
            continue
        row = _policy_design_concept_row(concepts, concept_id)
        _policy_design_append_text(row, "labels", raw_spec.get("name"))
        for note in _policy_design_text_list(raw_spec.get("notes")):
            if note.casefold().startswith("alias:"):
                _policy_design_append_text(row, "aliases", note.split(":", 1)[1])
            elif note.casefold().startswith("source_term:"):
                _policy_design_append_text(row, "source_terms", note.split(":", 1)[1])
        _policy_design_append_text(row, "source_refs", concept_id)
        _policy_design_append_text(row, "producer_refs", "ir_registry")


def _policy_design_project_fabric_entity_resolution(
    concepts: dict[str, dict[str, Any]],
    payload: Mapping[str, Any] | None,
    *,
    unresolved: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> None:
    if not isinstance(payload, Mapping):
        unresolved.append(
            _policy_design_concept_unresolved(
                source_component="fabric_entity_resolution",
                source_term="fabric_entity_resolution",
                reason="missing Fabric entity-resolution projection",
            )
        )
        return
    for raw_record in _policy_design_mapping_list(
        payload.get("records") or payload.get("entities") or payload.get("entity_records")
    ):
        attributes = raw_record.get("attributes")
        attrs = dict(attributes) if isinstance(attributes, Mapping) else {}
        concept_id = (
            _policy_design_text(raw_record.get("canonical_concept_id"))
            or _policy_design_text(attrs.get("canonical_concept_id"))
            or _policy_design_text(raw_record.get("concept_id"))
            or _policy_design_text(attrs.get("concept_id"))
        )
        source_term = (
            _policy_design_text(raw_record.get("canonical_name"))
            or _policy_design_text(raw_record.get("entity_id"))
            or "fabric_entity_resolution"
        )
        if concept_id is None:
            unresolved.append(
                _policy_design_concept_unresolved(
                    source_component="fabric_entity_resolution",
                    source_term=source_term,
                    reason="entity-resolution record has no canonical concept id",
                    refs=_policy_design_text_list(raw_record.get("provenance_ref")),
                )
            )
            continue
        row = _policy_design_concept_row(concepts, concept_id)
        _policy_design_append_text(row, "labels", raw_record.get("canonical_name"))
        _policy_design_extend_texts(row, "aliases", raw_record.get("aliases"))
        _policy_design_extend_texts(row, "aliases", attrs.get("aliases"))
        _policy_design_extend_terms(row, "source_terms", attrs.get("source_terms"))
        _policy_design_append_text(row, "source_terms", raw_record.get("canonical_name"))
        _policy_design_append_text(row, "source_refs", raw_record.get("provenance_ref"))
        _policy_design_append_text(row, "source_refs", raw_record.get("entity_id"))
        _policy_design_append_text(row, "producer_refs", "fabric_entity_resolution")
        for field_name, attr_key in (
            ("geography", "geography"),
            ("population", "population"),
            ("time", "time"),
            ("units", "unit_id"),
            ("currency", "currency"),
            ("price_bases", "price_base"),
            ("price_bases", "price_base_year"),
            ("exchange_rates", "exchange_rate_ref"),
            ("exchange_rates", "exchange_rate"),
            ("inflation_adjustments", "inflation_adjustment_ref"),
            ("inflation_adjustments", "inflation_adjustment"),
            ("calendars", "calendar"),
            ("freshness", "freshness_ref"),
            ("freshness", "source_freshness_at"),
        ):
            _policy_design_extend_terms(row, field_name, attrs.get(attr_key))
    for raw_unresolved in _policy_design_mapping_list(payload.get("unresolved")):
        unresolved.append(
            _policy_design_concept_unresolved(
                source_component=(
                    _policy_design_text(raw_unresolved.get("source_component"))
                    or "fabric_entity_resolution"
                ),
                source_term=(
                    _policy_design_text(raw_unresolved.get("source_term"))
                    or "fabric_entity_resolution"
                ),
                reason=(
                    _policy_design_text(raw_unresolved.get("reason"))
                    or "unresolved Fabric entity-resolution candidate"
                ),
                refs=_policy_design_text_list(raw_unresolved.get("refs")),
            )
        )
    for raw_conflict in _policy_design_mapping_list(payload.get("conflicts")):
        conflicts.append(
            _policy_design_concept_conflict(
                source_component=(
                    _policy_design_text(raw_conflict.get("source_component"))
                    or "fabric_entity_resolution"
                ),
                source_term=(
                    _policy_design_text(raw_conflict.get("source_term"))
                    or "fabric_entity_resolution"
                ),
                candidate_concept_ids=_policy_design_text_list(
                    raw_conflict.get("candidate_concept_ids")
                ),
                reason=(
                    _policy_design_text(raw_conflict.get("reason"))
                    or "conflicting Fabric entity-resolution candidate concepts"
                ),
                refs=_policy_design_text_list(raw_conflict.get("refs")),
            )
        )


def _policy_design_project_scientist_cross_graph(
    concepts: dict[str, dict[str, Any]],
    payload: Mapping[str, Any] | None,
    *,
    unresolved: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> None:
    if not isinstance(payload, Mapping):
        unresolved.append(
            _policy_design_concept_unresolved(
                source_component="scientist_cross_graph",
                source_term="scientist_cross_graph",
                reason="missing Scientist cross-graph projection",
            )
        )
        return
    for raw_concept in _policy_design_mapping_list(payload.get("ontology_snapshot")):
        concept_id = _policy_design_text(raw_concept.get("concept_id"))
        if concept_id is None:
            continue
        row = _policy_design_concept_row(concepts, concept_id)
        _policy_design_append_text(row, "labels", raw_concept.get("label"))
        _policy_design_append_text(row, "source_terms", raw_concept.get("label"))
        metadata = raw_concept.get("metadata")
        if isinstance(metadata, Mapping):
            _policy_design_extend_texts(row, "aliases", metadata.get("aliases"))
            _policy_design_extend_terms(row, "geography", metadata.get("geography"))
            _policy_design_extend_terms(row, "population", metadata.get("population"))
            _policy_design_extend_terms(row, "time", metadata.get("time"))
            _policy_design_extend_terms(row, "units", metadata.get("unit_id"))
            _policy_design_extend_terms(row, "currency", metadata.get("currency"))
            _policy_design_extend_terms(row, "price_bases", metadata.get("price_base"))
            _policy_design_extend_terms(row, "exchange_rates", metadata.get("exchange_rate_ref"))
            _policy_design_extend_terms(
                row,
                "inflation_adjustments",
                metadata.get("inflation_adjustment_ref"),
            )
            _policy_design_extend_terms(row, "calendars", metadata.get("calendar"))
            _policy_design_extend_terms(row, "freshness", metadata.get("freshness_ref"))
        _policy_design_append_text(row, "producer_refs", "scientist_cross_graph")
    for raw_need in _policy_design_mapping_list(payload.get("needs")):
        need = raw_need.get("need")
        need_map = need if isinstance(need, Mapping) else {}
        resolved_ids = _policy_design_text_list(raw_need.get("resolved_concept_ids"))
        if not resolved_ids:
            unresolved.append(
                _policy_design_concept_unresolved(
                    source_component="scientist_cross_graph",
                    source_term=(
                        _policy_design_text(need_map.get("metric_id"))
                        or _policy_design_text(need_map.get("need_id"))
                        or "scientist_cross_graph_need"
                    ),
                    reason="Scientist cross-graph need has no resolved concept id",
                    refs=_policy_design_text_list(raw_need.get("provenance_refs")),
                )
            )
        for concept_id in resolved_ids:
            row = _policy_design_concept_row(concepts, concept_id)
            _policy_design_extend_terms(row, "source_terms", need_map.get("labels"))
            _policy_design_append_text(row, "source_terms", need_map.get("metric_id"))
            _policy_design_extend_terms(row, "geography", need_map.get("geography"))
            _policy_design_extend_terms(row, "time", need_map.get("time_window"))
            _policy_design_extend_terms(row, "units", need_map.get("unit_id"))
            _policy_design_extend_terms(row, "currency", need_map.get("currency"))
            _policy_design_extend_terms(row, "price_bases", need_map.get("price_base"))
            _policy_design_extend_terms(
                row,
                "exchange_rates",
                need_map.get("exchange_rate_ref"),
            )
            _policy_design_extend_terms(
                row,
                "inflation_adjustments",
                need_map.get("inflation_adjustment_ref"),
            )
            _policy_design_extend_terms(row, "calendars", need_map.get("calendar"))
            _policy_design_extend_terms(row, "freshness", need_map.get("freshness_ref"))
            _policy_design_extend_texts(row, "source_refs", raw_need.get("provenance_refs"))
            _policy_design_append_text(row, "producer_refs", "scientist_cross_graph")
        for diagnostic in _policy_design_mapping_list(raw_need.get("diagnostics")):
            _policy_design_collect_cross_graph_diagnostic(
                diagnostic,
                unresolved=unresolved,
                conflicts=conflicts,
            )
    for diagnostic in _policy_design_mapping_list(payload.get("diagnostics")):
        _policy_design_collect_cross_graph_diagnostic(
            diagnostic,
            unresolved=unresolved,
            conflicts=conflicts,
        )
    for raw_bridge in _policy_design_mapping_list(payload.get("bridges")):
        concept_id = _policy_design_text(raw_bridge.get("dst_concept_id"))
        if concept_id is None:
            continue
        row = _policy_design_concept_row(concepts, concept_id)
        src_id = _policy_design_text(raw_bridge.get("src_id"))
        src_kind = (_policy_design_text(raw_bridge.get("src_kind")) or "").casefold()
        _policy_design_append_text(row, "source_refs", src_id)
        _policy_design_extend_texts(row, "source_refs", raw_bridge.get("provenance"))
        _policy_design_append_text(row, "producer_refs", "scientist_cross_graph")
        if src_id is not None and (src_kind == "claim" or src_id.startswith("claim.")):
            _policy_design_append_binding(
                row,
                "claim_bindings",
                _policy_design_claim_binding(
                    claim_id=src_id,
                    relation=_policy_design_text(raw_bridge.get("relation")),
                    source_component="scientist_cross_graph",
                    source=raw_bridge,
                ),
            )


def _policy_design_project_ir_linker(
    concepts: dict[str, dict[str, Any]],
    payload: Mapping[str, Any] | None,
    *,
    unresolved: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> None:
    if not isinstance(payload, Mapping):
        unresolved.append(
            _policy_design_concept_unresolved(
                source_component="ir_linker",
                source_term="ir_linker",
                reason="missing IR linker projection",
            )
        )
        return
    for raw_metric in _policy_design_mapping_list(payload.get("linked_metrics")):
        concept_id = _policy_design_text(raw_metric.get("canonical_concept_id"))
        metric_id = _policy_design_text(raw_metric.get("metric_id"))
        if concept_id is None:
            if metric_id is not None:
                unresolved.append(
                    _policy_design_concept_unresolved(
                        source_component="ir_linker",
                        source_term=metric_id,
                        reason="linked metric has no canonical concept id",
                    )
                )
            continue
        row = _policy_design_concept_row(concepts, concept_id)
        _policy_design_append_text(row, "source_terms", metric_id)
        _policy_design_append_text(row, "producer_refs", "ir_linker")
        if metric_id is not None:
            metric_binding = {
                "metric_id": metric_id,
                "unit_id": _policy_design_text(raw_metric.get("unit_id")),
                "source_component": "ir_linker",
            }
            for binding_key, source_key in (
                ("currency", "currency"),
                ("price_base", "price_base"),
                ("exchange_rate_ref", "exchange_rate_ref"),
                ("inflation_adjustment_ref", "inflation_adjustment_ref"),
                ("calendar", "calendar"),
                ("freshness_ref", "freshness_ref"),
            ):
                value = _policy_design_text(raw_metric.get(source_key))
                if value is not None:
                    metric_binding[binding_key] = value
            _policy_design_append_binding(row, "metric_bindings", metric_binding)
        _policy_design_extend_terms(row, "units", raw_metric.get("unit_id"))
        _policy_design_extend_terms(row, "currency", raw_metric.get("currency"))
        _policy_design_extend_terms(row, "price_bases", raw_metric.get("price_base"))
        _policy_design_extend_terms(row, "exchange_rates", raw_metric.get("exchange_rate_ref"))
        _policy_design_extend_terms(
            row,
            "inflation_adjustments",
            raw_metric.get("inflation_adjustment_ref"),
        )
        _policy_design_extend_terms(row, "calendars", raw_metric.get("calendar"))
        _policy_design_extend_terms(row, "freshness", raw_metric.get("freshness_ref"))
    for raw_issue in _policy_design_mapping_list(payload.get("issues")):
        code = _policy_design_text(raw_issue.get("code"))
        if code in {"unknown_concept", "unknown_metric"}:
            unresolved.append(
                _policy_design_concept_unresolved(
                    source_component="ir_linker",
                    source_term=_policy_design_link_issue_term(raw_issue),
                    reason=(
                        _policy_design_text(raw_issue.get("message"))
                        or "IR linker reported an unresolved concept"
                    ),
                    refs=_policy_design_text_list(raw_issue.get("path")),
                )
            )
        elif code in {"merge_rule_conflict", "merge_conflict", "unit_mismatch"}:
            conflicts.append(
                _policy_design_concept_conflict(
                    source_component="ir_linker",
                    source_term=_policy_design_link_issue_term(raw_issue),
                    candidate_concept_ids=_policy_design_text_list(
                        raw_issue.get("candidate_concept_ids")
                    ),
                    reason=(
                        _policy_design_text(raw_issue.get("message"))
                        or "IR linker reported a concept conflict"
                    ),
                    refs=_policy_design_text_list(raw_issue.get("path")),
                )
            )


def _policy_design_project_ir_world(
    concepts: dict[str, dict[str, Any]],
    payload: Mapping[str, Any] | None,
    *,
    unresolved: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> None:
    if not isinstance(payload, Mapping):
        unresolved.append(
            _policy_design_concept_unresolved(
                source_component="ir_world",
                source_term="ir_world",
                reason="missing IR world projection",
            )
        )
        return
    for raw_ref in _policy_design_mapping_list(payload.get("world_refs")):
        concept_id = _policy_design_text(raw_ref.get("canonical_concept_id"))
        if concept_id is None:
            continue
        row = _policy_design_concept_row(concepts, concept_id)
        _policy_design_append_text(row, "world_refs", raw_ref.get("world_id"))
        _policy_design_append_text(row, "source_refs", raw_ref.get("provenance_ref"))
        _policy_design_append_text(row, "producer_refs", "ir_world")
    for raw_binding in _policy_design_mapping_list(payload.get("dataset_bindings")):
        concept_id = _policy_design_text(raw_binding.get("canonical_concept_id"))
        if concept_id is None:
            continue
        row = _policy_design_concept_row(concepts, concept_id)
        dataset_id = _policy_design_text(raw_binding.get("dataset_id"))
        if dataset_id is not None:
            _policy_design_append_binding(
                row,
                "dataset_column_bindings",
                {
                    "dataset_id": dataset_id,
                    "column_ids": _policy_design_text_list(
                        raw_binding.get("columns") or raw_binding.get("column_ids")
                    ),
                    "metric_id": _policy_design_text(raw_binding.get("metric_id")),
                    "source_component": "ir_world",
                },
            )
    for raw_binding in _policy_design_mapping_list(payload.get("legal_concept_bindings")):
        _policy_design_append_world_binding(
            concepts,
            raw_binding,
            field_name="legal_concept_bindings",
            value_key="legal_concept_id",
        )
    for raw_binding in _policy_design_mapping_list(payload.get("method_requirement_bindings")):
        _policy_design_append_world_binding(
            concepts,
            raw_binding,
            field_name="method_requirement_bindings",
            value_key="requirement_id",
        )
    for raw_binding in _policy_design_mapping_list(payload.get("objective_tradeoff_bindings")):
        concept_id = _policy_design_text(raw_binding.get("canonical_concept_id"))
        if concept_id is None:
            continue
        row = _policy_design_concept_row(concepts, concept_id)
        objective_id = _policy_design_text(raw_binding.get("objective_id"))
        if objective_id is not None:
            _policy_design_append_binding(
                row,
                "objective_tradeoff_bindings",
                {
                    "objective_id": objective_id,
                    "tradeoff_id": _policy_design_text(raw_binding.get("tradeoff_id")),
                    "source_component": "ir_world",
                },
            )
    for raw_binding in _policy_design_mapping_list(payload.get("claim_bindings")):
        concept_id = _policy_design_text(raw_binding.get("canonical_concept_id"))
        claim_id = _policy_design_text(raw_binding.get("claim_id"))
        if concept_id is None or claim_id is None:
            continue
        row = _policy_design_concept_row(concepts, concept_id)
        _policy_design_append_binding(
            row,
            "claim_bindings",
            _policy_design_claim_binding(
                claim_id=claim_id,
                relation=_policy_design_text(raw_binding.get("relation")),
                source_component="ir_world",
                source=raw_binding,
            ),
        )
    for row in concepts.values():
        for field_name, key in (
            ("geography", "geography"),
            ("population", "population"),
            ("time", "time"),
            ("units", "units"),
            ("currency", "currency"),
            ("price_bases", "price_bases"),
            ("price_bases", "price_base"),
            ("exchange_rates", "exchange_rates"),
            ("exchange_rates", "exchange_rate_refs"),
            ("exchange_rates", "exchange_rate_ref"),
            ("inflation_adjustments", "inflation_adjustments"),
            ("inflation_adjustments", "inflation_adjustment_refs"),
            ("inflation_adjustments", "inflation_adjustment_ref"),
            ("calendars", "calendars"),
            ("calendars", "calendar"),
            ("freshness", "freshness"),
            ("freshness", "freshness_refs"),
            ("freshness", "freshness_ref"),
        ):
            _policy_design_extend_terms(row, field_name, payload.get(key))
    for raw_unresolved in _policy_design_mapping_list(payload.get("unresolved")):
        unresolved.append(
            _policy_design_concept_unresolved(
                source_component="ir_world",
                source_term=(
                    _policy_design_text(raw_unresolved.get("source_term"))
                    or "ir_world"
                ),
                reason=(
                    _policy_design_text(raw_unresolved.get("reason"))
                    or "IR world reported an unresolved concept"
                ),
                refs=_policy_design_text_list(raw_unresolved.get("refs")),
            )
        )
    for raw_conflict in _policy_design_mapping_list(payload.get("conflicts")):
        conflicts.append(
            _policy_design_concept_conflict(
                source_component="ir_world",
                source_term=(
                    _policy_design_text(raw_conflict.get("source_term"))
                    or "ir_world"
                ),
                candidate_concept_ids=_policy_design_text_list(
                    raw_conflict.get("candidate_concept_ids")
                ),
                reason=(
                    _policy_design_text(raw_conflict.get("reason"))
                    or "IR world reported a concept conflict"
                ),
                refs=_policy_design_text_list(raw_conflict.get("refs")),
            )
        )


def _policy_design_apply_ir_registry_bindings(
    concepts: dict[str, dict[str, Any]],
    registry: Mapping[str, Any] | None,
) -> None:
    if not isinstance(registry, Mapping):
        return
    metrics = _policy_design_registry_items(registry, "metrics")
    metric_units = {
        metric_id: _policy_design_text(spec.get("unit_id"))
        for metric_id, spec in metrics.items()
        if isinstance(spec, Mapping)
    }
    for row in concepts.values():
        for binding in row["metric_bindings"]:
            metric_id = _policy_design_text(binding.get("metric_id"))
            if metric_id is None:
                continue
            unit_id = _policy_design_text(binding.get("unit_id")) or metric_units.get(metric_id)
            if unit_id is not None:
                binding["unit_id"] = unit_id
                _policy_design_append_text(row, "units", unit_id)
                unit_spec = _policy_design_registry_unit(registry, unit_id)
                if unit_spec is not None:
                    _policy_design_extend_metric_semantics_from_registry(
                        row,
                        binding,
                        unit_spec,
                    )
        for unit_id in list(row["units"]):
            unit_spec = _policy_design_registry_unit(registry, unit_id)
            if unit_spec is None:
                continue
            currency = _policy_design_text(unit_spec.get("currency"))
            if currency is not None:
                _policy_design_append_text(row, "currency", currency)
            _policy_design_extend_terms(row, "price_bases", unit_spec.get("price_base"))
            _policy_design_extend_terms(row, "price_bases", unit_spec.get("nominal_year"))
            _policy_design_extend_terms(row, "exchange_rates", unit_spec.get("exchange_rate_ref"))
            _policy_design_extend_terms(
                row,
                "inflation_adjustments",
                unit_spec.get("inflation_adjustment_ref"),
            )


def _policy_design_extend_metric_semantics_from_registry(
    row: dict[str, Any],
    binding: dict[str, Any],
    unit_spec: Mapping[str, Any],
) -> None:
    for binding_key, row_field, keys in (
        ("currency", "currency", ("currency",)),
        ("price_base", "price_bases", ("price_base", "nominal_year")),
        ("exchange_rate_ref", "exchange_rates", ("exchange_rate_ref", "exchange_rate")),
        (
            "inflation_adjustment_ref",
            "inflation_adjustments",
            ("inflation_adjustment_ref", "inflation_adjustment"),
        ),
    ):
        value = _policy_design_first_semantic_value(unit_spec, *keys)
        if value is not None:
            binding[binding_key] = value
            _policy_design_append_text(row, row_field, value)


def _policy_design_claim_binding(
    *,
    claim_id: str,
    relation: str | None,
    source_component: str,
    source: Mapping[str, Any],
) -> dict[str, Any]:
    binding: dict[str, Any] = {
        "claim_id": claim_id,
        "source_component": source_component,
    }
    if relation is not None:
        binding["relation"] = relation
    nested = _policy_design_semantic_source(source)
    for target_key, source_keys in (
        ("unit_id", ("unit_id", "unit", "units")),
        ("currency", ("currency",)),
        ("price_base", ("price_base", "price_base_year", "nominal_year")),
        ("exchange_rate_ref", ("exchange_rate_ref", "exchange_rate", "exchange_rate_id")),
        (
            "inflation_adjustment_ref",
            ("inflation_adjustment_ref", "inflation_adjustment", "inflation_index_ref"),
        ),
        ("geography", ("geography", "geo_id")),
        ("geography_level", ("geography_level", "geo_level", "authority_level")),
        ("time", ("time", "time_window", "period")),
        ("time_basis", ("time_basis", "time_base", "time_axis")),
        ("calendar", ("calendar",)),
        ("freshness_ref", ("freshness_ref", "freshness", "source_freshness_at")),
    ):
        value = _policy_design_first_semantic_value(nested, *source_keys)
        if value is None:
            value = _policy_design_first_semantic_value(source, *source_keys)
        if value is not None:
            binding[target_key] = value
    return binding


def _policy_design_bind_claim_numerical_semantics(
    concepts: dict[str, dict[str, Any]],
) -> None:
    for row in concepts.values():
        concept_id = _policy_design_text(row.get("canonical_concept_id"))
        if concept_id is None:
            continue
        refs: list[dict[str, Any]] = []
        for binding in _policy_design_mapping_list(row.get("claim_bindings")):
            claim_id = _policy_design_text(binding.get("claim_id"))
            if claim_id is None:
                continue
            ref = {
                "claim_id": claim_id,
                "canonical_concept_id": concept_id,
                "source_component": (
                    _policy_design_text(binding.get("source_component"))
                    or "concept_spine_projection"
                ),
            }
            for target_key, binding_key, row_field in (
                ("unit_id", "unit_id", "units"),
                ("currency", "currency", "currency"),
                ("price_base", "price_base", "price_bases"),
                ("exchange_rate_ref", "exchange_rate_ref", "exchange_rates"),
                (
                    "inflation_adjustment_ref",
                    "inflation_adjustment_ref",
                    "inflation_adjustments",
                ),
                ("geography", "geography", "geography"),
                ("time", "time", "time"),
                ("calendar", "calendar", "calendars"),
                ("freshness_ref", "freshness_ref", "freshness"),
            ):
                value = (
                    _policy_design_semantic_text(binding.get(binding_key))
                    or _policy_design_first_text(row.get(row_field))
                )
                if value is not None:
                    ref[target_key] = value
                    _policy_design_append_text(row, row_field, value)
            for target_key in ("geography_level", "time_basis"):
                value = _policy_design_semantic_text(binding.get(target_key))
                if value is not None:
                    ref[target_key] = value
            ref["semantic_ref"] = _policy_design_cas_ref_from_payload(
                {
                    "schema_version": (
                        "policyos.runtime.policy_design_case."
                        "claim_numerical_semantics_ref.v1"
                    ),
                    **ref,
                }
            )
            refs.append(ref)
        row["claim_numerical_semantics_refs"] = refs


def _policy_design_semantic_source(source: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("numerical_semantics", "numeric_semantics", "semantic_dimensions"):
        value = source.get(key)
        if isinstance(value, Mapping):
            return value
    return source


def _policy_design_first_semantic_value(
    source: Mapping[str, Any],
    *keys: str,
) -> str | None:
    for key in keys:
        value = source.get(key)
        texts = _policy_design_semantic_text_list(value)
        if texts:
            return texts[0]
    return None


def _policy_design_semantic_text(value: object) -> str | None:
    text = _policy_design_text(value)
    if text is not None:
        return text
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(value)
    return None


def _policy_design_semantic_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str | int | float) and not isinstance(value, bool):
        text = _policy_design_semantic_text(value)
        return [text] if text is not None else []
    if isinstance(value, Mapping) or not isinstance(value, Iterable):
        return []
    texts: list[str] = []
    for item in value:
        text = _policy_design_semantic_text(item)
        if text is not None:
            texts.append(text)
    return list(dict.fromkeys(texts))


def _policy_design_first_text(value: object) -> str | None:
    texts = _policy_design_text_list(value)
    return texts[0] if texts else None


def _policy_design_append_world_binding(
    concepts: dict[str, dict[str, Any]],
    raw_binding: Mapping[str, Any],
    *,
    field_name: str,
    value_key: str,
) -> None:
    concept_id = _policy_design_text(raw_binding.get("canonical_concept_id"))
    if concept_id is None:
        return
    value = _policy_design_text(raw_binding.get(value_key))
    if value is None:
        return
    row = _policy_design_concept_row(concepts, concept_id)
    _policy_design_append_binding(
        row,
        field_name,
        {
            value_key: value,
            "source_component": "ir_world",
        },
    )


def _policy_design_concept_row(
    concepts: dict[str, dict[str, Any]],
    concept_id: str,
) -> dict[str, Any]:
    if concept_id not in concepts:
        concepts[concept_id] = {
            "canonical_concept_id": concept_id,
            "resolution_status": "resolved",
            "labels": [],
            "aliases": [],
            "source_terms": [],
            "source_refs": [],
            "producer_refs": [],
            "metric_bindings": [],
            "dataset_column_bindings": [],
            "legal_concept_bindings": [],
            "method_requirement_bindings": [],
            "objective_tradeoff_bindings": [],
            "claim_bindings": [],
            "geography": [],
            "population": [],
            "time": [],
            "units": [],
            "currency": [],
            "price_bases": [],
            "exchange_rates": [],
            "inflation_adjustments": [],
            "calendars": [],
            "freshness": [],
            "claim_numerical_semantics_refs": [],
            "world_refs": [],
        }
    return concepts[concept_id]


def _policy_design_concept_finalize(row: Mapping[str, Any]) -> dict[str, Any]:
    finalized = dict(row)
    for field_name in (
        "labels",
        "aliases",
        "source_terms",
        "source_refs",
        "producer_refs",
        "geography",
        "population",
        "time",
        "units",
        "currency",
        "price_bases",
        "exchange_rates",
        "inflation_adjustments",
        "calendars",
        "freshness",
        "world_refs",
    ):
        finalized[field_name] = _policy_design_text_list(row.get(field_name))
    for field_name in (
        "metric_bindings",
        "dataset_column_bindings",
        "legal_concept_bindings",
        "method_requirement_bindings",
        "objective_tradeoff_bindings",
        "claim_bindings",
        "claim_numerical_semantics_refs",
    ):
        finalized[field_name] = _policy_design_dedupe_mappings(
            _policy_design_mapping_list(row.get(field_name))
        )
    return finalized


def _policy_design_concept_closure_gaps(
    concept_rows: Iterable[Mapping[str, Any]],
) -> dict[str, list[str]]:
    gaps: dict[str, list[str]] = {}
    for row in concept_rows:
        concept_id = _policy_design_text(row.get("canonical_concept_id"))
        if concept_id is None:
            continue
        missing = [
            field_name
            for field_name in POLICY_DESIGN_CONCEPT_SPINE_REQUIRED_CLOSURE_FIELDS
            if not row.get(field_name)
        ]
        if missing:
            gaps[concept_id] = missing
    return gaps


def _policy_design_semantic_mismatches(
    concept_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = [dict(row) for row in concept_rows]
    return [
        *_policy_design_concept_semantic_mismatches(rows),
        *_policy_design_claim_semantic_mismatches(rows),
    ]


def _policy_design_concept_semantic_mismatches(
    concept_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for row in concept_rows:
        concept_id = _policy_design_text(row.get("canonical_concept_id"))
        if concept_id is None:
            continue
        for dimension, code in (
            ("units", "policy_design_concept_unit_mismatch"),
            ("currency", "policy_design_concept_currency_mismatch"),
            ("price_bases", "policy_design_concept_price_base_mismatch"),
            ("exchange_rates", "policy_design_concept_exchange_rate_mismatch"),
            (
                "inflation_adjustments",
                "policy_design_concept_inflation_adjustment_mismatch",
            ),
            ("geography", "policy_design_concept_geography_mismatch"),
            ("time", "policy_design_concept_time_mismatch"),
            ("calendars", "policy_design_concept_calendar_mismatch"),
            ("freshness", "policy_design_concept_freshness_mismatch"),
        ):
            values = _policy_design_distinct_semantic_values(row.get(dimension))
            if len(values) > 1:
                mismatches.append(
                    _policy_design_concept_mismatch(
                        code=code,
                        canonical_concept_id=concept_id,
                        dimension=dimension,
                        observed_values=values,
                    )
                )
        legal_ids = _policy_design_distinct_semantic_values(
            binding.get("legal_concept_id")
            for binding in _policy_design_mapping_list(row.get("legal_concept_bindings"))
        )
        if len(legal_ids) > 1:
            mismatches.append(
                _policy_design_concept_mismatch(
                    code="policy_design_concept_legal_mismatch",
                    canonical_concept_id=concept_id,
                    dimension="legal_concepts",
                    observed_values=legal_ids,
                )
            )
    return mismatches


def _policy_design_claim_semantic_mismatches(
    concept_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for row in concept_rows:
        concept_id = _policy_design_text(row.get("canonical_concept_id"))
        if concept_id is None:
            continue
        refs_by_claim: dict[str, list[dict[str, Any]]] = {}
        for ref in _policy_design_mapping_list(row.get("claim_numerical_semantics_refs")):
            claim_id = _policy_design_text(ref.get("claim_id"))
            if claim_id is not None:
                refs_by_claim.setdefault(claim_id, []).append(ref)
        for claim_id, refs in sorted(refs_by_claim.items()):
            for dimension, code in (
                ("unit_id", "policy_design_claim_unit_mismatch"),
                ("currency", "policy_design_claim_currency_mismatch"),
                ("price_base", "policy_design_claim_price_base_mismatch"),
                ("exchange_rate_ref", "policy_design_claim_exchange_rate_mismatch"),
                (
                    "inflation_adjustment_ref",
                    "policy_design_claim_inflation_adjustment_mismatch",
                ),
                ("geography_level", "policy_design_claim_geography_level_mismatch"),
                ("time_basis", "policy_design_claim_time_basis_mismatch"),
                ("calendar", "policy_design_claim_calendar_mismatch"),
                ("freshness_ref", "policy_design_claim_freshness_mismatch"),
            ):
                values = _policy_design_distinct_semantic_values(
                    ref.get(dimension) for ref in refs
                )
                if len(values) > 1:
                    mismatches.append(
                        _policy_design_claim_mismatch(
                            code=code,
                            canonical_concept_id=concept_id,
                            claim_id=claim_id,
                            dimension=dimension,
                            observed_values=values,
                        )
                    )
    return mismatches


def _policy_design_concept_mismatch(
    *,
    code: str,
    canonical_concept_id: str,
    dimension: str,
    observed_values: Iterable[str],
) -> dict[str, Any]:
    values = list(dict.fromkeys(observed_values))
    return {
        "code": code,
        "severity": "blocker",
        "canonical_concept_id": canonical_concept_id,
        "dimension": dimension,
        "observed_values": values,
        "message": (
            f"Concept {canonical_concept_id} has incompatible {dimension}: "
            f"{', '.join(values)}."
        ),
    }


def _policy_design_claim_mismatch(
    *,
    code: str,
    canonical_concept_id: str,
    claim_id: str,
    dimension: str,
    observed_values: Iterable[str],
) -> dict[str, Any]:
    values = list(dict.fromkeys(observed_values))
    return {
        "code": code,
        "severity": "blocker",
        "canonical_concept_id": canonical_concept_id,
        "claim_id": claim_id,
        "dimension": dimension,
        "observed_values": values,
        "message": (
            f"Claim {claim_id} has incompatible {dimension} semantics for "
            f"{canonical_concept_id}: {', '.join(values)}."
        ),
    }


def _policy_design_distinct_semantic_values(value: object) -> list[str]:
    by_normalized: dict[str, str] = {}
    for item in _policy_design_text_list(value):
        normalized = _policy_design_normalized_term_key(item)
        if normalized:
            by_normalized.setdefault(normalized, item)
    return [by_normalized[key] for key in sorted(by_normalized)]


def _policy_design_concept_reconciliation_trace(
    concept_rows: Iterable[Mapping[str, Any]],
    *,
    semantic_mismatches: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    mismatches_by_concept: dict[str, list[dict[str, Any]]] = {}
    for mismatch in semantic_mismatches:
        concept_id = _policy_design_text(mismatch.get("canonical_concept_id"))
        if concept_id is not None:
            mismatches_by_concept.setdefault(concept_id, []).append(dict(mismatch))

    trace: list[dict[str, Any]] = []
    binding_specs = (
        ("metric", "metric_bindings", "metric_id"),
        ("dataset", "dataset_column_bindings", "dataset_id"),
        ("legal", "legal_concept_bindings", "legal_concept_id"),
        ("method", "method_requirement_bindings", "requirement_id"),
        ("objective", "objective_tradeoff_bindings", "objective_id"),
        ("claim", "claim_bindings", "claim_id"),
    )
    for row in concept_rows:
        concept_id = _policy_design_text(row.get("canonical_concept_id"))
        if concept_id is None:
            continue
        row_mismatches = mismatches_by_concept.get(concept_id, [])
        for concept_type, field_name, id_key in binding_specs:
            bindings = _policy_design_mapping_list(row.get(field_name))
            binding_refs = [
                text
                for text in (
                    _policy_design_text(binding.get(id_key)) for binding in bindings
                )
                if text is not None
            ]
            if not binding_refs:
                continue
            source_components = _policy_design_trace_source_components(
                bindings,
                row.get("producer_refs"),
            )
            trace.append(
                {
                    "trace_id": f"{concept_id}:{concept_type}",
                    "concept_type": concept_type,
                    "canonical_concept_id": concept_id,
                    "status": "blocked" if row_mismatches else "resolved",
                    "binding_refs": list(dict.fromkeys(binding_refs)),
                    "source_components": source_components,
                    "semantic_dimensions": _policy_design_trace_semantic_dimensions(row),
                    "mismatches": [dict(mismatch) for mismatch in row_mismatches],
                }
            )
    return trace


def _policy_design_trace_source_components(
    bindings: Iterable[Mapping[str, Any]],
    fallback_components: object,
) -> list[str]:
    components: list[str] = []
    for binding in bindings:
        text = _policy_design_text(binding.get("source_component"))
        if text is not None:
            components.append(text)
    if not components:
        components.extend(_policy_design_text_list(fallback_components))
    return list(dict.fromkeys(components))


def _policy_design_trace_semantic_dimensions(row: Mapping[str, Any]) -> dict[str, list[str]]:
    return {
        "geography": _policy_design_text_list(row.get("geography")),
        "population": _policy_design_text_list(row.get("population")),
        "time": _policy_design_text_list(row.get("time")),
        "units": _policy_design_text_list(row.get("units")),
        "currency": _policy_design_text_list(row.get("currency")),
        "price_bases": _policy_design_text_list(row.get("price_bases")),
        "exchange_rates": _policy_design_text_list(row.get("exchange_rates")),
        "inflation_adjustments": _policy_design_text_list(
            row.get("inflation_adjustments")
        ),
        "calendars": _policy_design_text_list(row.get("calendars")),
        "freshness": _policy_design_text_list(row.get("freshness")),
        "legal_concepts": _policy_design_distinct_semantic_values(
            binding.get("legal_concept_id")
            for binding in _policy_design_mapping_list(row.get("legal_concept_bindings"))
        ),
    }


def _policy_design_concept_normalization_trace(
    concept_rows: Iterable[Mapping[str, Any]],
    *,
    raw_user_terms: Iterable[str] | Mapping[str, Any] | str | None,
) -> list[dict[str, Any]]:
    term_index = _policy_design_concept_term_index(concept_rows)
    requested_terms = _policy_design_raw_user_terms(raw_user_terms)
    requested_norms = {
        normalized
        for normalized in (_policy_design_normalized_term_key(term) for term in requested_terms)
        if normalized
    }
    if not requested_terms:
        requested_terms = [
            entry["raw_terms"][0]
            for _, entry in sorted(term_index.items(), key=lambda item: item[0])
            if entry["raw_terms"]
        ]
        requested_norms = {
            normalized
            for normalized in (
                _policy_design_normalized_term_key(term) for term in requested_terms
            )
            if normalized
        }
    for normalized, entry in sorted(term_index.items(), key=lambda item: item[0]):
        if len(entry["canonical_concept_refs"]) > 1 and normalized not in requested_norms:
            requested_terms.append(entry["raw_terms"][0])
            requested_norms.add(normalized)

    trace: list[dict[str, Any]] = []
    seen_norms: set[str] = set()
    for raw_term in requested_terms:
        normalized = _policy_design_normalized_term_key(raw_term)
        if not normalized or normalized in seen_norms:
            continue
        seen_norms.add(normalized)
        indexed = term_index.get(normalized)
        refs = (
            sorted(indexed["canonical_concept_refs"])
            if indexed is not None
            else []
        )
        if not refs:
            typed_blocker = _policy_design_normalization_blocker(
                code="policy_design_concept_unresolved",
                raw_term=raw_term,
                canonical_concept_refs=(),
            )
            status = "blocked"
        elif len(refs) > 1:
            typed_blocker = _policy_design_normalization_blocker(
                code="policy_design_concept_synonym_collision",
                raw_term=raw_term,
                canonical_concept_refs=refs,
            )
            status = "blocked"
        else:
            typed_blocker = None
            status = "mapped"
        trace.append(
            {
                "raw_term": raw_term,
                "normalized_term": normalized,
                "status": status,
                "canonical_concept_refs": refs,
                "match_kind": "raw_user_term" if raw_user_terms is not None else "source_term",
                "typed_blocker": typed_blocker,
            }
        )
    return trace


def _policy_design_concept_term_index(
    concept_rows: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in concept_rows:
        concept_id = _policy_design_text(row.get("canonical_concept_id"))
        if concept_id is None:
            continue
        terms: list[str] = []
        for field_name in ("labels", "aliases", "source_terms"):
            terms.extend(_policy_design_text_list(row.get(field_name)))
        for term in terms:
            normalized = _policy_design_normalized_term_key(term)
            if not normalized:
                continue
            entry = index.setdefault(
                normalized,
                {"raw_terms": [], "canonical_concept_refs": []},
            )
            if term not in entry["raw_terms"]:
                entry["raw_terms"].append(term)
            if concept_id not in entry["canonical_concept_refs"]:
                entry["canonical_concept_refs"].append(concept_id)
    return index


def _policy_design_raw_user_terms(
    raw_user_terms: Iterable[str] | Mapping[str, Any] | str | None,
) -> list[str]:
    if raw_user_terms is None:
        return []
    if isinstance(raw_user_terms, str):
        return _policy_design_text_list(raw_user_terms)
    if isinstance(raw_user_terms, Mapping):
        terms: list[str] = []
        for key in (
            "raw_user_terms",
            "terms",
            "source_terms",
            "policy_terms",
            "objectives",
            "claims",
        ):
            terms.extend(_policy_design_text_list(raw_user_terms.get(key)))
        if terms:
            return list(dict.fromkeys(terms))
        for value in raw_user_terms.values():
            terms.extend(_policy_design_text_list(value))
        return list(dict.fromkeys(terms))
    return _policy_design_text_list(raw_user_terms)


def _policy_design_normalized_term_key(term: object) -> str:
    text = _policy_design_text(term)
    if text is None:
        return ""
    chars = [char if char.isalnum() else " " for char in text.casefold()]
    return " ".join("".join(chars).split())


def _policy_design_normalization_blocker(
    *,
    code: str,
    raw_term: str,
    canonical_concept_refs: Iterable[str],
) -> dict[str, Any]:
    refs = list(dict.fromkeys(canonical_concept_refs))
    return {
        "code": code,
        "severity": "blocker",
        "owner": POLICY_DESIGN_CONCEPT_SPINE_OWNER,
        "raw_term": raw_term,
        "candidate_concept_refs": refs,
        "message": (
            "Raw user term maps to multiple canonical concepts."
            if code == "policy_design_concept_synonym_collision"
            else "Raw user term has no canonical concept ref."
        ),
    }


def _policy_design_validate_concept_reconciliation_trace_entry(
    entry: object,
) -> dict[str, Any]:
    if not isinstance(entry, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_reconciliation_trace_invalid",
            "Concept reconciliation trace entries must be mappings.",
        )
    concept_type = _policy_design_required_text(
        entry.get("concept_type"),
        "policy_design_concept_reconciliation_trace_type_missing",
    )
    if concept_type not in {"metric", "dataset", "legal", "method", "objective", "claim"}:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_reconciliation_trace_type_invalid",
            "Concept reconciliation trace type is not recognized.",
        )
    status = _policy_design_required_text(
        entry.get("status"),
        "policy_design_concept_reconciliation_trace_status_missing",
    )
    if status not in {"resolved", "blocked"}:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_reconciliation_trace_status_invalid",
            "Concept reconciliation trace status must be resolved or blocked.",
        )
    semantic_dimensions = entry.get("semantic_dimensions")
    if not isinstance(semantic_dimensions, Mapping):
        semantic_dimensions = {}
    mismatches = [
        _policy_design_validate_concept_mismatch(mismatch)
        for mismatch in _policy_design_mapping_list(entry.get("mismatches"))
    ]
    if mismatches and status != "blocked":
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_reconciliation_trace_status_invalid",
            "Trace entries with mismatches must be blocked.",
        )
    return {
        **dict(entry),
        "trace_id": _policy_design_required_text(
            entry.get("trace_id"),
            "policy_design_concept_reconciliation_trace_id_missing",
        ),
        "concept_type": concept_type,
        "canonical_concept_id": _policy_design_required_text(
            entry.get("canonical_concept_id"),
            "policy_design_concept_reconciliation_trace_concept_id_missing",
        ),
        "status": status,
        "binding_refs": _policy_design_text_list(entry.get("binding_refs")),
        "source_components": _policy_design_text_list(entry.get("source_components")),
        "semantic_dimensions": {
            key: _policy_design_text_list(value)
            for key, value in semantic_dimensions.items()
        },
        "mismatches": mismatches,
    }


def _policy_design_validate_concept_mismatch(mismatch: Mapping[str, Any]) -> dict[str, Any]:
    code = _policy_design_required_text(
        mismatch.get("code"),
        "policy_design_concept_mismatch_code_missing",
    )
    if code not in {
        "policy_design_concept_unit_mismatch",
        "policy_design_concept_currency_mismatch",
        "policy_design_concept_price_base_mismatch",
        "policy_design_concept_exchange_rate_mismatch",
        "policy_design_concept_inflation_adjustment_mismatch",
        "policy_design_concept_geography_mismatch",
        "policy_design_concept_time_mismatch",
        "policy_design_concept_calendar_mismatch",
        "policy_design_concept_freshness_mismatch",
        "policy_design_concept_legal_mismatch",
        "policy_design_claim_unit_mismatch",
        "policy_design_claim_currency_mismatch",
        "policy_design_claim_price_base_mismatch",
        "policy_design_claim_exchange_rate_mismatch",
        "policy_design_claim_inflation_adjustment_mismatch",
        "policy_design_claim_geography_level_mismatch",
        "policy_design_claim_time_basis_mismatch",
        "policy_design_claim_calendar_mismatch",
        "policy_design_claim_freshness_mismatch",
    }:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_mismatch_code_invalid",
            "Concept mismatch code is not recognized.",
        )
    return {
        **dict(mismatch),
        "code": code,
        "severity": _policy_design_text(mismatch.get("severity")) or "blocker",
        "canonical_concept_id": _policy_design_required_text(
            mismatch.get("canonical_concept_id"),
            "policy_design_concept_mismatch_concept_id_missing",
        ),
        "dimension": _policy_design_required_text(
            mismatch.get("dimension"),
            "policy_design_concept_mismatch_dimension_missing",
        ),
        "observed_values": _policy_design_text_list(mismatch.get("observed_values")),
        "message": _policy_design_text(mismatch.get("message")) or "Concept mismatch.",
    }


def _policy_design_validate_concept_normalization_trace_entry(
    entry: object,
) -> dict[str, Any]:
    if not isinstance(entry, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_normalization_trace_invalid",
            "Concept normalization trace entries must be mappings.",
        )
    raw_term = _policy_design_required_text(
        entry.get("raw_term"),
        "policy_design_concept_normalization_trace_raw_term_missing",
    )
    normalized_term = _policy_design_required_text(
        entry.get("normalized_term"),
        "policy_design_concept_normalization_trace_normalized_term_missing",
    )
    status = _policy_design_required_text(
        entry.get("status"),
        "policy_design_concept_normalization_trace_status_missing",
    )
    if status not in {"mapped", "blocked"}:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_normalization_trace_status_invalid",
            "Normalization trace status must be mapped or blocked.",
        )
    refs = _policy_design_text_list(entry.get("canonical_concept_refs"))
    typed_blocker = entry.get("typed_blocker")
    if status == "mapped":
        if not refs:
            raise PolicyDesignCaseAuthorityError(
                "policy_design_concept_normalization_trace_ref_missing",
                "Mapped raw terms must include a canonical concept ref.",
            )
        typed_blocker = None
    else:
        if not isinstance(typed_blocker, Mapping):
            raise PolicyDesignCaseAuthorityError(
                "policy_design_concept_normalization_trace_blocker_missing",
                "Blocked raw terms must include a typed blocker.",
            )
        code = _policy_design_required_text(
            typed_blocker.get("code"),
            "policy_design_concept_normalization_trace_blocker_code_missing",
        )
        if code not in {
            "policy_design_concept_unresolved",
            "policy_design_concept_synonym_collision",
        }:
            raise PolicyDesignCaseAuthorityError(
                "policy_design_concept_normalization_trace_blocker_code_invalid",
                "Normalization trace blocker code is not recognized.",
            )
        typed_blocker = {
            **dict(typed_blocker),
            "code": code,
            "owner": _policy_design_text(typed_blocker.get("owner"))
            or POLICY_DESIGN_CONCEPT_SPINE_OWNER,
        }
    return {
        **dict(entry),
        "raw_term": raw_term,
        "normalized_term": normalized_term,
        "status": status,
        "canonical_concept_refs": refs,
        "match_kind": _policy_design_text(entry.get("match_kind")) or "source_term",
        "typed_blocker": typed_blocker,
    }


def _policy_design_validate_concept_row(row: object) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_concept_invalid",
            "Canonical concept rows must be mappings.",
        )
    normalized = dict(row)
    normalized["canonical_concept_id"] = _policy_design_required_text(
        row.get("canonical_concept_id"),
        "policy_design_concept_spine_concept_id_missing",
    )
    for field_name in (
        "aliases",
        "source_terms",
        "source_refs",
        "producer_refs",
        "geography",
        "population",
        "time",
        "units",
        "currency",
        "price_bases",
        "exchange_rates",
        "inflation_adjustments",
        "calendars",
        "freshness",
        "world_refs",
    ):
        normalized[field_name] = _policy_design_text_list(row.get(field_name))
    for field_name in (
        "metric_bindings",
        "dataset_column_bindings",
        "legal_concept_bindings",
        "method_requirement_bindings",
        "objective_tradeoff_bindings",
        "claim_bindings",
        "claim_numerical_semantics_refs",
    ):
        normalized[field_name] = _policy_design_dedupe_mappings(
            _policy_design_mapping_list(row.get(field_name))
        )
    return normalized


def _policy_design_concept_blockers(
    *,
    unresolved: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    closure_gaps: Mapping[str, list[str]],
    semantic_mismatches: Iterable[Mapping[str, Any]],
    normalization_trace: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    blocked_normalization: dict[str, list[dict[str, Any]]] = {}
    for entry in normalization_trace:
        typed_blocker = entry.get("typed_blocker")
        if not isinstance(typed_blocker, Mapping):
            continue
        code = _policy_design_text(typed_blocker.get("code"))
        if code is not None:
            blocked_normalization.setdefault(code, []).append(dict(entry))
    if unresolved:
        blockers.append(
            {
                "code": "policy_design_concept_unresolved",
                "severity": "blocker",
                "owner": POLICY_DESIGN_CONCEPT_SPINE_OWNER,
                "source_component": "concept_spine_projection",
                "message": "Per-run concept spine has unresolved source terms.",
                "upstream_cause": "Fabric, Scientist, or IR did not resolve every concept.",
                "downstream_impact": (
                    "Legal, data, method, objective, and claim evidence cannot close "
                    "over one canonical concept spine."
                ),
                "missing_input": "accepted canonical concept id for every source term",
                "next_diagnostic_command": (
                    "uv run pytest "
                    "tests/unit/runtime/quality/test_policy_design_case_concept_spine.py -q"
                ),
                "unresolved_concepts": list(unresolved),
            }
        )
    elif "policy_design_concept_unresolved" in blocked_normalization:
        blockers.append(
            {
                "code": "policy_design_concept_unresolved",
                "severity": "blocker",
                "owner": POLICY_DESIGN_CONCEPT_SPINE_OWNER,
                "source_component": "concept_spine_normalization",
                "message": "Raw user terms did not map to canonical concept refs.",
                "upstream_cause": "No canonical concept spine row matched the raw term.",
                "downstream_impact": (
                    "Producer evidence cannot close over a user term without a canonical ref."
                ),
                "missing_input": "canonical concept ref for every raw user term",
                "next_diagnostic_command": (
                    "uv run pytest "
                    "tests/unit/runtime/quality/test_policy_design_case_concept_spine.py -q"
                ),
                "normalization_trace": blocked_normalization[
                    "policy_design_concept_unresolved"
                ],
            }
        )
    if conflicts:
        blockers.append(
            {
                "code": "policy_design_concept_conflict",
                "severity": "blocker",
                "owner": POLICY_DESIGN_CONCEPT_SPINE_OWNER,
                "source_component": "concept_spine_projection",
                "message": "Per-run concept spine has conflicting candidate concepts.",
                "upstream_cause": "Upstream resolution produced incompatible canonical candidates.",
                "downstream_impact": (
                    "Producer and claim evidence may bind different meanings to the same "
                    "source term."
                ),
                "missing_input": "accepted conflict resolution for each candidate collision",
                "next_diagnostic_command": (
                    "uv run pytest "
                    "tests/unit/runtime/quality/test_policy_design_case_concept_spine.py -q"
                ),
                "conflicting_concepts": list(conflicts),
            }
        )
    if "policy_design_concept_synonym_collision" in blocked_normalization:
        blockers.append(
            {
                "code": "policy_design_concept_synonym_collision",
                "severity": "blocker",
                "owner": POLICY_DESIGN_CONCEPT_SPINE_OWNER,
                "source_component": "concept_spine_normalization",
                "message": "Raw user term maps to multiple canonical concept refs.",
                "upstream_cause": (
                    "Aliases or source terms collided across canonical concepts."
                ),
                "downstream_impact": (
                    "Legal, data, method, objective, and claim evidence may bind "
                    "different concepts to the same user term."
                ),
                "missing_input": "accepted synonym disambiguation for each collision",
                "next_diagnostic_command": (
                    "uv run pytest "
                    "tests/unit/runtime/quality/test_policy_design_case_concept_spine.py -q"
                ),
                "normalization_trace": blocked_normalization[
                    "policy_design_concept_synonym_collision"
                ],
            }
        )
    if closure_gaps:
        blockers.append(
            {
                "code": "policy_design_concept_binding_missing",
                "severity": "blocker",
                "owner": POLICY_DESIGN_CONCEPT_SPINE_OWNER,
                "source_component": "concept_spine_projection",
                "message": "Per-run concept spine is missing required closure bindings.",
                "upstream_cause": (
                    "Fabric, Scientist, or IR projections did not provide every "
                    "Wave 8 concept binding and semantic field."
                ),
                "downstream_impact": (
                    "Legal, data, method, objective, and claim producers cannot "
                    "consume a fully closed concept spine."
                ),
                "missing_input": (
                    "canonical aliases/source terms, producer bindings, geography, "
                    "population, time, units, currency, and calendars"
                ),
                "next_diagnostic_command": (
                    "uv run pytest "
                    "tests/unit/runtime/quality/test_policy_design_case_concept_spine.py -q"
                ),
                "missing_fields_by_concept": {
                    concept_id: list(fields)
                    for concept_id, fields in sorted(closure_gaps.items())
                },
            }
        )
    mismatches_by_code: dict[str, list[dict[str, Any]]] = {}
    for mismatch in semantic_mismatches:
        code = _policy_design_text(mismatch.get("code"))
        if code is not None:
            mismatches_by_code.setdefault(code, []).append(dict(mismatch))
    for code, mismatches in sorted(mismatches_by_code.items()):
        dimension = _policy_design_text(mismatches[0].get("dimension")) or "semantic"
        blockers.append(
            {
                "code": code,
                "severity": "blocker",
                "owner": POLICY_DESIGN_CONCEPT_SPINE_OWNER,
                "source_component": "concept_spine_reconciliation",
                "message": f"Per-run concept spine has a {dimension} mismatch.",
                "upstream_cause": (
                    "Producer projections emitted incompatible semantic closure values."
                ),
                "downstream_impact": (
                    "Metric, dataset, legal, method, objective, and claim producers "
                    "cannot consume one semantic closure."
                ),
                "missing_input": f"one reconciled {dimension} value per canonical concept",
                "next_diagnostic_command": (
                    "uv run pytest "
                    "tests/unit/runtime/quality/test_policy_design_case_concept_spine.py -q"
                ),
                "mismatches": mismatches,
            }
        )
    return blockers


def _policy_design_validate_concept_blocker(blocker: Mapping[str, Any]) -> None:
    code = _policy_design_required_text(
        blocker.get("code"),
        "policy_design_concept_spine_blocker_code_missing",
    )
    if code not in {
        "policy_design_concept_unresolved",
        "policy_design_concept_conflict",
        "policy_design_concept_binding_missing",
        "policy_design_concept_synonym_collision",
        "policy_design_concept_unit_mismatch",
        "policy_design_concept_currency_mismatch",
        "policy_design_concept_price_base_mismatch",
        "policy_design_concept_exchange_rate_mismatch",
        "policy_design_concept_inflation_adjustment_mismatch",
        "policy_design_concept_geography_mismatch",
        "policy_design_concept_time_mismatch",
        "policy_design_concept_calendar_mismatch",
        "policy_design_concept_freshness_mismatch",
        "policy_design_concept_legal_mismatch",
        "policy_design_claim_unit_mismatch",
        "policy_design_claim_currency_mismatch",
        "policy_design_claim_price_base_mismatch",
        "policy_design_claim_exchange_rate_mismatch",
        "policy_design_claim_inflation_adjustment_mismatch",
        "policy_design_claim_geography_level_mismatch",
        "policy_design_claim_time_basis_mismatch",
        "policy_design_claim_calendar_mismatch",
        "policy_design_claim_freshness_mismatch",
    }:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_blocker_code_invalid",
            "Concept spine blockers must use typed concept blocker codes.",
        )
    if _policy_design_required_text(
        blocker.get("owner"),
        "policy_design_concept_spine_blocker_owner_missing",
    ) != POLICY_DESIGN_CONCEPT_SPINE_OWNER:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_blocker_owner_invalid",
            "Concept spine blockers must name the policy-semantics owner.",
        )
    next_command = _policy_design_required_text(
        blocker.get("next_diagnostic_command"),
        "policy_design_concept_spine_blocker_next_command_missing",
    )
    if not next_command.startswith("uv run "):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_blocker_next_command_invalid",
            "Concept spine blockers must include the next diagnostic command.",
        )
    for key in ("message", "upstream_cause", "downstream_impact", "missing_input"):
        _policy_design_required_text(
            blocker.get(key),
            f"policy_design_concept_spine_blocker_{key}_missing",
        )


def _policy_design_concept_authority_envelope(
    authority: Mapping[str, Any],
    *,
    status: str,
    cas_ref: str,
    run_id: str,
    job_id: str,
    tenant_id: str,
    policy_intent_ref: str,
) -> dict[str, Any]:
    role = _policy_design_required_text(
        authority.get("authority_role"),
        "policy_design_concept_spine_authority_role_missing",
    )
    provenance = _policy_design_required_text(
        authority.get("provenance_kind"),
        "policy_design_concept_spine_provenance_missing",
    )
    if role == "not_authoritative" or provenance == "static_inventory":
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_static_inventory_not_authority",
            "Static inventories cannot satisfy a per-run concept spine.",
        )
    if role not in {"producer_authority", "runtime_blocker"}:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_authority_role_invalid",
            "Concept spine authority must be producer_authority or runtime_blocker.",
        )
    if provenance not in {"runtime_emitted", "runtime_blocker"}:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_provenance_invalid",
            "Concept spine must be runtime-emitted or a runtime blocker.",
        )
    if status == "pass" and (role != "producer_authority" or provenance != "runtime_emitted"):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_authority_status_mismatch",
            "Passing concept spine must carry producer runtime authority.",
        )
    if status == "blocked" and (role != "runtime_blocker" or provenance != "runtime_blocker"):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_authority_status_mismatch",
            "Blocked concept spine must carry runtime blocker authority.",
        )
    authority_ref = _policy_design_required_text(
        authority.get("cas_ref") or authority.get("artifact_ref"),
        "policy_design_concept_spine_authority_ref_missing",
    )
    if authority_ref != cas_ref:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_concept_spine_authority_ref_mismatch",
            "Concept spine authority envelope must match the record CAS ref.",
        )
    _policy_design_skeleton_reject_forbidden_ref(authority_ref)
    runtime_event_ref = _policy_design_required_text(
        authority.get("runtime_event_ref"),
        "policy_design_concept_spine_authority_runtime_event_ref_missing",
    )
    _policy_design_skeleton_reject_forbidden_ref(runtime_event_ref)
    normalized = dict(authority)
    normalized.update(
        {
            "artifact_ref": authority_ref,
            "cas_ref": authority_ref,
            "authority_role": role,
            "provenance_kind": provenance,
            "producer_component": _policy_design_text(authority.get("producer_component"))
            or POLICY_DESIGN_CONCEPT_SPINE_COMPONENT,
            "producer_version": _policy_design_text(authority.get("producer_version"))
            or "2026.05.17+phase8.1.concept_spine",
            "owner": _policy_design_text(authority.get("owner")) or POLICY_DESIGN_CASE_OWNER,
            "record_owner": _policy_design_text(authority.get("record_owner"))
            or POLICY_DESIGN_CONCEPT_SPINE_OWNER,
            "runtime_event_ref": runtime_event_ref,
            "schema_name": _policy_design_text(authority.get("schema_name"))
            or "policyos.policy_design_case.concept_spine",
            "schema_version": _policy_design_text(authority.get("schema_version"))
            or POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION,
            "reader_contract": _policy_design_text(authority.get("reader_contract"))
            or POLICY_DESIGN_CONCEPT_SPINE_CONTRACT_ID,
            "run_id": _policy_design_text(authority.get("run_id")) or run_id,
            "job_id": _policy_design_text(authority.get("job_id")) or job_id,
            "tenant_id": _policy_design_text(authority.get("tenant_id")) or tenant_id,
            "policy_intent_ref": _policy_design_text(authority.get("policy_intent_ref"))
            or policy_intent_ref,
            "validation_status": status,
        }
    )
    for key in (
        "same_input_closure_ref",
        "effective_mode_ref",
        "schema_compatibility_ref",
    ):
        value = _policy_design_required_text(
            authority.get(key),
            f"policy_design_concept_spine_{key}_missing",
        )
        _policy_design_skeleton_reject_forbidden_ref(value)
        normalized[key] = value
    return normalized


def _policy_design_concept_unresolved(
    *,
    source_component: str,
    source_term: str,
    reason: str,
    refs: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "source_component": source_component,
        "source_term": source_term,
        "reason": reason,
        "refs": list(dict.fromkeys(refs)),
    }


def _policy_design_concept_conflict(
    *,
    source_component: str,
    source_term: str,
    candidate_concept_ids: Iterable[str],
    reason: str,
    refs: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "source_component": source_component,
        "source_term": source_term,
        "candidate_concept_ids": list(dict.fromkeys(candidate_concept_ids)),
        "reason": reason,
        "refs": list(dict.fromkeys(refs)),
    }


def _policy_design_collect_cross_graph_diagnostic(
    diagnostic: Mapping[str, Any],
    *,
    unresolved: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> None:
    code = _policy_design_text(diagnostic.get("code"))
    if code == "unknown_concept":
        unresolved.append(
            _policy_design_concept_unresolved(
                source_component="scientist_cross_graph",
                source_term=(
                    _policy_design_text(diagnostic.get("need_id"))
                    or "scientist_cross_graph"
                ),
                reason=(
                    _policy_design_text(diagnostic.get("message"))
                    or "Scientist cross-graph reported an unresolved concept"
                ),
            )
        )
    elif code in {"concept_conflict", "ontology_conflict"}:
        conflicts.append(
            _policy_design_concept_conflict(
                source_component="scientist_cross_graph",
                source_term=(
                    _policy_design_text(diagnostic.get("need_id"))
                    or "scientist_cross_graph"
                ),
                candidate_concept_ids=_policy_design_text_list(
                    diagnostic.get("candidate_concept_ids")
                ),
                reason=(
                    _policy_design_text(diagnostic.get("message"))
                    or "Scientist cross-graph reported a concept conflict"
                ),
            )
        )


def _policy_design_link_issue_term(issue: Mapping[str, Any]) -> str:
    ids = issue.get("ids")
    if isinstance(ids, Mapping):
        for key in (
            "concept_id",
            "metric_id",
            "unit_id",
            "slot_id",
            "constraint_id",
        ):
            text = _policy_design_text(ids.get(key))
            if text is not None:
                return text
    return _policy_design_text(issue.get("message")) or "ir_linker_issue"


def _policy_design_registry_items(
    registry: Mapping[str, Any],
    key: str,
) -> dict[str, Any]:
    value = registry.get(key)
    if isinstance(value, Mapping):
        nested = value.get(key)
        if isinstance(nested, Mapping):
            return dict(nested)
        return dict(value)
    return {}


def _policy_design_registry_unit(
    registry: Mapping[str, Any],
    unit_id: str,
) -> Mapping[str, Any] | None:
    units = registry.get("units")
    if not isinstance(units, Mapping):
        return None
    raw_units = units.get("units") if isinstance(units.get("units"), Mapping) else units
    if not isinstance(raw_units, Mapping):
        return None
    unit = raw_units.get(unit_id)
    return unit if isinstance(unit, Mapping) else None


def _policy_design_append_binding(
    row: dict[str, Any],
    field_name: str,
    binding: Mapping[str, Any],
) -> None:
    cleaned = {
        key: value
        for key, value in binding.items()
        if value not in (None, "", [], ())
    }
    if cleaned:
        row[field_name].append(cleaned)


def _policy_design_append_text(row: dict[str, Any], field_name: str, value: object) -> None:
    text = _policy_design_text(value)
    if text is not None and text not in row[field_name]:
        row[field_name].append(text)


def _policy_design_extend_texts(
    row: dict[str, Any],
    field_name: str,
    value: object,
) -> None:
    for text in _policy_design_text_list(value):
        _policy_design_append_text(row, field_name, text)


def _policy_design_extend_terms(
    row: dict[str, Any],
    field_name: str,
    value: object,
) -> None:
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
    else:
        parts = _policy_design_text_list(value)
    for part in parts:
        _policy_design_append_text(row, field_name, part)


def _policy_design_mapping_list(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if not isinstance(value, Iterable) or isinstance(value, str):
        return []
    rows: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            rows.append(dict(item))
    return rows


def _policy_design_dedupe_mappings(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        cleaned = {
            key: value
            for key, value in row.items()
            if value not in (None, "", [], ())
        }
        if not cleaned:
            continue
        key = json.dumps(cleaned, sort_keys=True, separators=(",", ":"), default=str)
        deduped[key] = dict(cleaned)
    return [deduped[key] for key in sorted(deduped)]


def _policy_design_collect_concept_bindings(
    concepts: Iterable[Mapping[str, Any]],
    field_name: str,
    *,
    id_key: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for concept in concepts:
        concept_id = _policy_design_text(concept.get("canonical_concept_id"))
        for binding in _policy_design_mapping_list(concept.get(field_name)):
            if id_key not in binding:
                continue
            row = {"canonical_concept_id": concept_id, **binding}
            rows.append(row)
    return _policy_design_dedupe_mappings(rows)


def _policy_design_concept_input_refs(source_projection: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for status in _policy_design_mapping_list(source_projection.get("component_status")):
        text = _policy_design_text(status.get("input_ref"))
        if text is not None:
            refs.append(text)
    return list(dict.fromkeys(refs))


def _policy_design_cas_ref_from_payload(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return "cas://sha256/" + hashlib.sha256(encoded).hexdigest()


def _policy_design_case_capability_ledger(
    ledger: object,
    *,
    effective_execution_profile: str,
    final_major_claims: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(ledger, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_capability_ledger_missing",
            "Policy Design Case must include a runtime-owned capability ledger.",
        )
    normalized: dict[str, Any] = dict(ledger)
    schema_version = _policy_design_required_text(
        ledger.get("schema_version"),
        "policy_design_capability_ledger_schema_version_missing",
    )
    if schema_version != POLICY_DESIGN_CAPABILITY_LEDGER_SCHEMA_VERSION:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_capability_ledger_schema_version_invalid",
            "Capability ledger must use the runtime-quality schema version.",
        )
    normalized["schema_version"] = POLICY_DESIGN_CAPABILITY_LEDGER_SCHEMA_VERSION
    normalized["ledger_ref"] = _policy_design_required_text(
        ledger.get("ledger_ref") or ledger.get("capability_ledger_ref"),
        "policy_design_capability_ledger_ref_missing",
    )
    duties = ledger.get("duties") or ledger.get("capability_duties")
    if not isinstance(duties, list) or not duties:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_capability_duties_missing",
            "Capability ledger must include duty records.",
        )
    profile = _policy_design_required_text(
        effective_execution_profile,
        "policy_design_case_effective_execution_profile_missing",
    )
    by_capability: dict[str, dict[str, Any]] = {}
    for raw_duty in duties:
        duty = _policy_design_case_capability_duty(
            raw_duty,
            effective_execution_profile=profile,
        )
        capability = str(duty["capability"])
        if capability in by_capability:
            raise PolicyDesignCaseAuthorityError(
                "policy_design_capability_duty_duplicate",
                f"Capability duty was emitted more than once: {capability}.",
            )
        by_capability[capability] = duty
    missing = [
        capability
        for capability in POLICY_DESIGN_REQUIRED_CAPABILITIES
        if capability not in by_capability
    ]
    literature_required = _policy_design_literature_required(
        ledger,
        final_major_claims=final_major_claims,
    )
    if "scholar" in missing and literature_required:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_scholar_literature_duty_missing",
            "Capability ledger requires literature evidence but omitted Scholar duty.",
        )
    if missing:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_capability_duty_missing",
            "Capability ledger omitted required duties: " + ", ".join(missing),
        )
    if literature_required and by_capability["scholar"]["state"] != "selected":
        state = str(by_capability["scholar"]["state"])
        raise PolicyDesignCaseAuthorityError(
            "policy_design_scholar_literature_duty_not_selected",
            f"Capability ledger requires literature evidence but Scholar is {state}.",
        )
    normalized["duties"] = [
        by_capability[capability] for capability in POLICY_DESIGN_REQUIRED_CAPABILITIES
    ]
    normalized["literature_evidence_required"] = literature_required
    return normalized


def _policy_design_case_capability_duty(
    duty: object,
    *,
    effective_execution_profile: str,
) -> dict[str, Any]:
    if not isinstance(duty, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_capability_duty_invalid",
            "Capability duty records must be mappings.",
        )
    normalized = dict(duty)
    capability = _policy_design_capability_name(duty.get("capability"))
    state = _policy_design_duty_state(duty.get("state") or duty.get("status"))
    normalized["capability"] = capability
    normalized["state"] = state
    normalized["owner"] = (
        _policy_design_text(duty.get("owner"))
        or _POLICY_DESIGN_CAPABILITY_OWNERS[capability]
    )
    if state == "selected":
        if not _policy_design_has_any_ref(duty, _POLICY_DESIGN_SELECTED_REF_FIELDS):
            raise PolicyDesignCaseAuthorityError(
                "policy_design_capability_selected_evidence_missing",
                f"Selected capability {capability} must include runtime evidence.",
            )
        _policy_design_reject_local_refs(duty, _POLICY_DESIGN_SELECTED_REF_FIELDS)
    elif state == "skipped":
        _policy_design_validate_skipped_duty(
            capability,
            duty,
            effective_execution_profile=effective_execution_profile,
        )
    elif state == "blocked":
        if not _policy_design_has_blocker(duty):
            raise PolicyDesignCaseAuthorityError(
                "policy_design_capability_blocker_missing",
                f"Blocked capability {capability} must include a typed blocker.",
            )
        raise PolicyDesignCaseAuthorityError(
            "policy_design_capability_duty_blocked",
            f"Capability {capability} emitted an explicit blocker.",
        )
    elif state == "fallback":
        _policy_design_validate_allowed_degradation(
            capability,
            duty,
            effective_execution_profile=effective_execution_profile,
            missing_code="policy_design_capability_fallback_degradation_missing",
        )
    return normalized


def _policy_design_validate_skipped_duty(
    capability: str,
    duty: Mapping[str, Any],
    *,
    effective_execution_profile: str,
) -> None:
    if _policy_design_has_degradation(duty):
        _policy_design_validate_allowed_degradation(
            capability,
            duty,
            effective_execution_profile=effective_execution_profile,
            missing_code="policy_design_capability_skip_degradation_missing",
        )
        return
    if _policy_design_has_blocker(duty):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_capability_duty_blocked",
            f"Skipped capability {capability} emitted a typed blocker.",
        )
    raise PolicyDesignCaseAuthorityError(
        "policy_design_capability_silent_skip_blocked",
        (
            f"Skipped capability {capability} must emit a blocker or an allowed-profile "
            "degradation record."
        ),
    )


def _policy_design_validate_allowed_degradation(
    capability: str,
    duty: Mapping[str, Any],
    *,
    effective_execution_profile: str,
    missing_code: str,
) -> None:
    if not _policy_design_has_degradation(duty):
        raise PolicyDesignCaseAuthorityError(
            missing_code,
            f"Capability {capability} must include a degradation record or ref.",
        )
    _policy_design_reject_local_refs(duty, _POLICY_DESIGN_DEGRADATION_REF_FIELDS)
    allowed_profiles = _policy_design_allowed_profiles(duty)
    if not allowed_profiles:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_capability_degradation_profile_missing",
            f"Capability {capability} degradation must declare allowed profiles.",
        )
    if effective_execution_profile not in allowed_profiles:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_capability_degradation_not_allowed",
            (
                f"Capability {capability} degradation is allowed for "
                f"{', '.join(sorted(allowed_profiles))}, not {effective_execution_profile}."
            ),
        )


def _policy_design_capability_name(value: object) -> str:
    text = _policy_design_required_text(value, "policy_design_capability_name_missing")
    normalized = text.casefold().replace("-", "_")
    normalized = _POLICY_DESIGN_CAPABILITY_ALIASES.get(normalized, normalized)
    if normalized not in POLICY_DESIGN_REQUIRED_CAPABILITIES:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_capability_unknown",
            f"Unknown Policy Design Case capability: {text}.",
        )
    return normalized


def _policy_design_duty_state(value: object) -> str:
    state = _policy_design_required_text(value, "policy_design_capability_state_missing")
    normalized = state.casefold().replace("-", "_")
    if normalized not in _POLICY_DESIGN_ALLOWED_DUTY_STATES:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_capability_state_invalid",
            f"Capability duty state is not supported: {state}.",
        )
    return normalized


def _policy_design_has_blocker(duty: Mapping[str, Any]) -> bool:
    return _policy_design_has_any_ref(duty, _POLICY_DESIGN_BLOCKER_FIELDS) or any(
        isinstance(duty.get(field), Mapping)
        for field in _POLICY_DESIGN_BLOCKER_RECORD_FIELDS
    )


def _policy_design_has_degradation(duty: Mapping[str, Any]) -> bool:
    return _policy_design_has_any_ref(duty, _POLICY_DESIGN_DEGRADATION_REF_FIELDS) or any(
        isinstance(duty.get(field), Mapping)
        for field in _POLICY_DESIGN_DEGRADATION_RECORD_FIELDS
    )


def _policy_design_has_any_ref(
    duty: Mapping[str, Any],
    fields: Iterable[str],
) -> bool:
    return any(_policy_design_text(duty.get(field)) is not None for field in fields)


def _policy_design_allowed_profiles(duty: Mapping[str, Any]) -> set[str]:
    candidates: list[object] = [duty.get("allowed_profiles"), duty.get("allowed_profile")]
    for field in _POLICY_DESIGN_DEGRADATION_RECORD_FIELDS:
        record = duty.get(field)
        if isinstance(record, Mapping):
            candidates.extend([record.get("allowed_profiles"), record.get("allowed_profile")])
    profiles: set[str] = set()
    for candidate in candidates:
        if isinstance(candidate, str):
            text = _policy_design_text(candidate)
            if text is not None:
                profiles.add(text)
        elif isinstance(candidate, Iterable):
            for item in candidate:
                text = _policy_design_text(item)
                if text is not None:
                    profiles.add(text)
    return profiles


def _policy_design_reject_local_refs(
    duty: Mapping[str, Any],
    fields: Iterable[str],
) -> None:
    for field in fields:
        value = _policy_design_text(duty.get(field))
        if value is not None and _looks_like_local_path(value):
            raise PolicyDesignCaseAuthorityError(
                "policy_design_capability_local_ref_not_authority",
                "Capability duty refs must be runtime refs, not local paths.",
            )


def _policy_design_literature_required(
    ledger: Mapping[str, Any],
    *,
    final_major_claims: Iterable[Mapping[str, Any]] | None,
) -> bool:
    explicit = ledger.get("literature_evidence_required")
    if explicit is None:
        explicit = ledger.get("requires_literature_evidence")
    if isinstance(explicit, bool):
        return explicit
    if isinstance(explicit, str):
        return explicit.strip().casefold() in {"1", "true", "yes", "required"}
    for claim in final_major_claims or ():
        if _policy_design_truthy_refs(claim.get("literature_refs")):
            return True
        if _policy_design_truthy_refs(claim.get("scholar_refs")):
            return True
    return False


def _policy_design_truthy_refs(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Iterable):
        return any(_policy_design_text(item) is not None for item in value)
    return False


def _policy_design_case_final_major_claims(
    case: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    claims = case.get("final_major_claims") or case.get("major_claims")
    if not isinstance(claims, list):
        return ()
    return tuple(claim for claim in claims if isinstance(claim, Mapping))


def _policy_intent_preferred_conclusion(envelope: Mapping[str, Any]) -> str | None:
    if _POLICY_INTENT_REQUESTER_PREFERRED_CONCLUSION not in envelope:
        raise PolicyDesignCaseAuthorityError(
            "policy_intent_requester_preferred_conclusion_missing",
            "Policy intent envelope must explicitly record requester preferred conclusion.",
        )
    value = envelope.get(_POLICY_INTENT_REQUESTER_PREFERRED_CONCLUSION)
    if value is None:
        return None
    text = _policy_design_text(value)
    if text is None:
        raise PolicyDesignCaseAuthorityError(
            "policy_intent_requester_preferred_conclusion_missing",
            "Requester preferred conclusion must be text or explicit null.",
        )
    return text


def _policy_intent_requester_preference(
    preferred_conclusion: str | None,
) -> dict[str, Any]:
    return {
        "provided": preferred_conclusion is not None,
        "preferred_conclusion": preferred_conclusion,
        "separation_required": True,
        "may_not_determine_independent_conclusion": True,
    }


def _policy_intent_analysis_independence() -> dict[str, Any]:
    return {
        "independent_analysis_required": True,
        "requester_preference_may_not_determine_conclusion": True,
        "requires_alternative_analysis": True,
        "requires_counter_evidence_assessment": True,
    }


def _policy_intent_capture_risk(
    *,
    preferred_conclusion: str | None,
    risk_factors: list[str],
) -> dict[str, Any]:
    factors = list(dict.fromkeys(risk_factors))
    preferred_present = preferred_conclusion is not None
    if preferred_present:
        factors.append("requester_preferred_conclusion_present")
    risk_level = "high" if preferred_present else "low"
    challenge_depth = "heightened" if preferred_present else "standard"
    if any(
        factor
        in {
            "financial_conflict",
            "political_pressure",
            "single_outcome_mandate",
            "suppressed_counter_evidence",
        }
        for factor in factors
    ):
        risk_level = "critical"
        challenge_depth = "adversarial"
    return {
        "preferred_conclusion_present": preferred_present,
        "risk_level": risk_level,
        "risk_factors": list(dict.fromkeys(factors)),
        "challenge_depth": challenge_depth,
        "mitigation": "separate requester preference from independent analysis before routing",
    }


def _policy_intent_challenge_depth_policy(
    risk: Mapping[str, Any],
) -> dict[str, Any]:
    depth = _policy_design_text(risk.get("challenge_depth")) or "standard"
    if depth == "adversarial":
        minimum_alternative_count = 3
    elif depth == "heightened":
        minimum_alternative_count = 2
    else:
        minimum_alternative_count = 1
        depth = "standard"
    return {
        "depth": depth,
        "minimum_alternative_count": minimum_alternative_count,
        "requires_disconfirming_evidence": depth in {"heightened", "adversarial"},
        "requires_requester_capture_challenge": bool(
            risk.get("preferred_conclusion_present")
        ),
    }


def _policy_intent_risk_factors(envelope: Mapping[str, Any]) -> list[str]:
    factors = _policy_design_text_list(envelope.get("requester_capture_risk_factors"))
    risk = envelope.get("requester_capture_risk")
    if isinstance(risk, Mapping):
        factors.extend(_policy_design_text_list(risk.get("risk_factors")))
    return list(dict.fromkeys(factors))


def _policy_design_case_nodes(nodes: Iterable[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, Mapping):
            raise PolicyDesignCaseAuthorityError(
                "policy_design_case_node_invalid",
                "Policy Design Case nodes must be mappings.",
            )
        node_type = _policy_design_required_text(
            node.get("node_type"),
            "policy_design_case_node_type_missing",
        )
        node_family = _policy_design_text(node.get("node_family"))
        if (
            node_type not in POLICY_DESIGN_CASE_CORE_NODE_TYPES
            and node_family not in POLICY_DESIGN_CASE_RESERVED_NODE_FAMILIES
        ):
            raise PolicyDesignCaseAuthorityError(
                "policy_design_case_node_type_unregistered",
                "Policy Design Case nodes must use a core type or reserved family.",
            )
        normalized.append(dict(node))
    return normalized


def _policy_design_case_validate_known_nodes(
    nodes: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for node in nodes:
        node_type = _policy_design_text(node.get("node_type"))
        schema_version = _policy_design_text(node.get("schema_version"))
        contract_id = _policy_design_text(node.get("contract_id"))
        if node_type == "concept_spine" and (
            schema_version == POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION
            or contract_id == POLICY_DESIGN_CONCEPT_SPINE_CONTRACT_ID
        ):
            normalized.append(validate_policy_design_case_concept_spine(node))
            continue
        normalized.append(dict(node))
    return normalized


def _policy_design_case_walking_skeleton_contract(
    contract: object,
    *,
    effective_execution_profile: str,
    nodes: Iterable[Mapping[str, Any]],
) -> dict[str, Any] | None:
    if contract is None:
        return None
    if not isinstance(contract, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_contract_invalid",
            "Walking skeleton contract must be a mapping.",
        )
    _policy_design_skeleton_reject_forbidden_surfaces(contract)
    normalized = dict(contract)
    schema_version = _policy_design_required_text(
        contract.get("schema_version"),
        "policy_design_skeleton_schema_version_missing",
    )
    if schema_version != POLICY_DESIGN_WALKING_SKELETON_SCHEMA_VERSION:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_schema_version_invalid",
            "Walking skeleton contract must use the runtime-quality schema version.",
        )
    contract_id = _policy_design_required_text(
        contract.get("contract_id"),
        "policy_design_skeleton_contract_id_missing",
    )
    if contract_id != POLICY_DESIGN_WALKING_SKELETON_CONTRACT_ID:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_contract_id_invalid",
            "Walking skeleton contract id is not recognized.",
        )
    if _policy_design_required_text(
        contract.get("profile"),
        "policy_design_skeleton_profile_missing",
    ) != "research":
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_profile_invalid",
            "Walking skeleton contract must be research-profile only.",
        )
    if contract.get("non_production") is not True:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_non_production_marker_missing",
            "Walking skeleton contract must be explicitly non-production.",
        )

    by_type: dict[str, list[Mapping[str, Any]]] = {
        node_type: [] for node_type in _POLICY_DESIGN_WALKING_SKELETON_REQUIRED_NODE_TYPES
    }
    for node in nodes:
        node_type = _policy_design_text(node.get("node_type"))
        if node_type in by_type:
            by_type[node_type].append(node)
    missing = [node_type for node_type, matches in by_type.items() if not matches]
    if missing:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_node_missing",
            "Walking skeleton is missing nodes: " + ", ".join(missing),
        )
    duplicates = [node_type for node_type, matches in by_type.items() if len(matches) > 1]
    if duplicates:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_node_duplicate",
            "Walking skeleton must carry exactly one node for: " + ", ".join(duplicates),
        )

    typed_nodes = {
        node_type: matches[0]
        for node_type, matches in by_type.items()
        if matches
    }
    for node_type, node in typed_nodes.items():
        _policy_design_validate_walking_skeleton_record(
            node,
            expected_node_type=node_type,
        )
    _policy_design_validate_walking_skeleton_flow(
        contract,
        nodes=typed_nodes,
        effective_execution_profile=effective_execution_profile,
    )
    normalized["schema_version"] = POLICY_DESIGN_WALKING_SKELETON_SCHEMA_VERSION
    normalized["contract_id"] = POLICY_DESIGN_WALKING_SKELETON_CONTRACT_ID
    normalized["profile"] = "research"
    normalized["non_production"] = True
    return normalized


def _policy_design_validate_walking_skeleton_record(
    node: Mapping[str, Any],
    *,
    expected_node_type: str,
) -> None:
    _policy_design_skeleton_reject_forbidden_surfaces(node)
    node_type = _policy_design_required_text(
        node.get("node_type"),
        "policy_design_skeleton_node_type_missing",
    )
    if node_type != expected_node_type:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_node_type_mismatch",
            "Walking skeleton node type does not match its required slot.",
        )
    envelope = node.get("runtime_authority_envelope")
    if not isinstance(envelope, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_authority_envelope_missing",
            "Walking skeleton records must carry runtime authority envelopes.",
        )
    _policy_design_skeleton_reject_forbidden_surfaces(envelope)
    if _policy_design_text(envelope.get("authority_role")) != "producer_authority":
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_authority_role_invalid",
            "Walking skeleton records must be producer-authority runtime records.",
        )
    if _policy_design_text(envelope.get("provenance_kind")) != "runtime_emitted":
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_static_inventory_not_authority",
            "Walking skeleton records must be runtime-emitted.",
        )

    for ref_key in _POLICY_DESIGN_WALKING_SKELETON_REQUIRED_REFS:
        ref_value = _policy_design_required_text(
            node.get(ref_key),
            f"policy_design_skeleton_{ref_key}_missing",
        )
        _policy_design_validate_walking_skeleton_ref(ref_key, ref_value)
        envelope_value = envelope.get(ref_key)
        if ref_key == "cas_ref" and _policy_design_text(envelope_value) is None:
            envelope_value = envelope.get("artifact_ref")
        if _policy_design_text(envelope_value) != ref_value:
            raise PolicyDesignCaseAuthorityError(
                "policy_design_skeleton_authority_envelope_ref_mismatch",
                f"Walking skeleton envelope {ref_key} must match the record.",
            )

    schema_compatibility = node.get("schema_compatibility")
    if isinstance(schema_compatibility, Mapping):
        decision = _policy_design_text(schema_compatibility.get("decision"))
        if decision != "compatible":
            raise PolicyDesignCaseAuthorityError(
                "policy_design_skeleton_schema_incompatible",
                "Walking skeleton records must carry compatible schema evidence.",
            )


def _policy_design_validate_walking_skeleton_flow(
    contract: Mapping[str, Any],
    *,
    nodes: Mapping[str, Mapping[str, Any]],
    effective_execution_profile: str,
) -> None:
    intent = nodes["policy_intent"]
    concept = nodes["concept_spine"]
    producer = nodes["producer_evidence"]
    claim = nodes["claim"]
    deficit = nodes["deficit"]
    intent_ref = _policy_design_required_text(
        intent.get("cas_ref"),
        "policy_design_skeleton_intent_ref_missing",
    )
    concept_ref = _policy_design_required_text(
        concept.get("concept_ref"),
        "policy_design_skeleton_concept_ref_missing",
    )
    jurisdiction_ref = _policy_design_required_text(
        concept.get("jurisdiction_ref"),
        "policy_design_skeleton_jurisdiction_ref_missing",
    )
    producer_ref = _policy_design_required_text(
        producer.get("cas_ref"),
        "policy_design_skeleton_producer_evidence_ref_missing",
    )
    claim_ref = _policy_design_required_text(
        claim.get("cas_ref"),
        "policy_design_skeleton_major_claim_ref_missing",
    )
    deficit_ref = _policy_design_required_text(
        deficit.get("cas_ref"),
        "policy_design_skeleton_deficit_ref_missing",
    )
    expected_contract_refs = {
        "intent_ref": intent_ref,
        "concept_ref": concept_ref,
        "jurisdiction_ref": jurisdiction_ref,
        "producer_evidence_ref": producer_ref,
        "major_claim_ref": claim_ref,
        "accepted_deficit_ref": deficit_ref,
    }
    for key, expected in expected_contract_refs.items():
        if _policy_design_text(contract.get(key)) != expected:
            raise PolicyDesignCaseAuthorityError(
                "policy_design_skeleton_contract_ref_mismatch",
                f"Walking skeleton contract {key} must match the node ref.",
            )

    if _policy_design_text(concept.get("intent_ref")) != intent_ref:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_concept_intent_ref_missing",
            "Concept spine must consume the intent ref.",
        )
    if _policy_design_text(producer.get("intent_ref")) != intent_ref:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_producer_intent_ref_missing",
            "Stub producer evidence must consume the intent ref.",
        )
    if _policy_design_text(producer.get("concept_ref")) != concept_ref:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_producer_concept_ref_missing",
            "Stub producer evidence must consume the concept ref.",
        )
    if _policy_design_text(producer.get("jurisdiction_ref")) != jurisdiction_ref:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_producer_jurisdiction_ref_missing",
            "Stub producer evidence must consume the jurisdiction ref.",
        )
    if producer.get("stub_record") is not True:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_stub_producer_missing",
            "Walking skeleton must use an explicit stub producer evidence record.",
        )
    if claim.get("major") is not True:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_major_claim_missing",
            "Walking skeleton must carry one major claim.",
        )
    if producer_ref not in _policy_design_text_list(claim.get("producer_evidence_refs")):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_claim_producer_ref_missing",
            "Major claim must cite the stub producer evidence ref.",
        )
    if concept_ref not in _policy_design_text_list(claim.get("concept_refs")):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_claim_concept_ref_missing",
            "Major claim must cite the concept ref.",
        )
    if jurisdiction_ref not in _policy_design_text_list(claim.get("jurisdiction_refs")):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_claim_jurisdiction_ref_missing",
            "Major claim must cite the jurisdiction ref.",
        )
    if _policy_design_text(deficit.get("deficit_kind")) != (
        _POLICY_DESIGN_WALKING_SKELETON_ACCEPTED_DEFICIT_KIND
    ):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_deficit_kind_invalid",
            "Walking skeleton must use a single_line_evidence_deficit.",
        )
    if _policy_design_text(deficit.get("status")) != "accepted":
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_deficit_status_invalid",
            "Walking skeleton deficit must be explicitly accepted.",
        )
    if _policy_design_text(deficit.get("claim_ref")) != claim_ref:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_deficit_claim_ref_missing",
            "Accepted deficit must cite the major claim ref.",
        )
    if _policy_design_text(deficit.get("producer_evidence_ref")) != producer_ref:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_deficit_producer_ref_missing",
            "Accepted deficit must cite the stub producer evidence ref.",
        )
    if deficit_ref not in _policy_design_text_list(claim.get("accepted_deficit_refs")):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_claim_deficit_ref_missing",
            "Major claim must cite the accepted single-line deficit.",
        )
    if (
        effective_execution_profile
        not in _POLICY_DESIGN_WALKING_SKELETON_ALLOWED_DEFICIT_PROFILES
    ):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_single_line_deficit_not_allowed",
            (
                "Accepted single-line evidence deficits are allowed only for the "
                "research walking skeleton."
            ),
        )


def _policy_design_validate_walking_skeleton_ref(ref_key: str, value: str) -> None:
    _policy_design_skeleton_reject_forbidden_ref(value)
    if ref_key in {
        "cas_ref",
        "schema_compatibility_ref",
        "effective_mode_ref",
        "same_input_closure_ref",
    } and not _policy_design_is_cas_authority_ref(value):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_runtime_ref_invalid",
            f"Walking skeleton {ref_key} must be a CAS authority ref.",
        )
    if ref_key in {"runtime_event_ref", "diagnostic_event_ref"} and not value.startswith(
        "event://"
    ):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_diagnostic_event_ref_invalid",
            f"Walking skeleton {ref_key} must be a diagnostic event ref.",
        )


def _policy_design_skeleton_reject_forbidden_surfaces(value: object) -> None:
    for text in _policy_design_walk_text(value):
        _policy_design_skeleton_reject_forbidden_ref(text)


def _policy_design_skeleton_reject_forbidden_ref(value: str) -> None:
    normalized = value.strip().replace("\\", "/")
    lowered = normalized.casefold()
    tokenized = lowered.replace("-", "_").replace(" ", "_")
    if "static_inventory" in tokenized or normalized.startswith("repo://"):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_static_inventory_not_authority",
            "Static inventory cannot satisfy the walking skeleton contract.",
        )
    if "public_export" in tokenized or normalized.startswith("public://"):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_public_export_not_authority",
            "Public exports are projection-only and cannot satisfy the skeleton.",
        )
    if "dashboard_state" in tokenized or normalized.startswith("dashboard://"):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_dashboard_state_not_authority",
            "Dashboard state cannot satisfy the walking skeleton contract.",
        )
    if (
        normalized.startswith("bundle://")
        or normalized.startswith("bundle/")
        or normalized.startswith("quality_evidence/")
    ):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_bundle_local_ref_not_authority",
            "Bundle-local refs cannot satisfy the walking skeleton contract.",
        )
    if (
        _looks_like_local_path(normalized)
        or normalized.startswith("file://")
        or normalized.startswith("local://")
    ):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_skeleton_local_ref_not_authority",
            "Local paths cannot satisfy the walking skeleton contract.",
        )


def _policy_design_walk_text(value: object) -> Iterable[str]:
    if isinstance(value, str):
        text = _policy_design_text(value)
        if text is not None:
            yield text
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = _policy_design_text(key)
            if key_text is not None:
                yield key_text
            yield from _policy_design_walk_text(item)
        return
    if isinstance(value, Iterable):
        for item in value:
            yield from _policy_design_walk_text(item)


def _policy_design_is_cas_authority_ref(value: str) -> bool:
    if value.startswith("cas://sha256/"):
        digest = value.removeprefix("cas://sha256/")
    elif value.startswith("sha256:"):
        digest = value.removeprefix("sha256:")
    else:
        return False
    return len(digest) == 64 and all(char in "0123456789abcdefABCDEF" for char in digest)


def _policy_design_skeleton_cas_ref(char: str) -> str:
    return f"cas://sha256/{char * 64}"


def _policy_design_walking_skeleton_node(
    *,
    node_type: str,
    record_id: str,
    cas_ref: str,
    schema_name: str,
    generated_at: datetime,
    run_id: str,
    job_id: str,
    tenant_id: str,
    requested_execution_profile: str,
    effective_execution_profile: str,
    policy_intent_ref: str,
    evidence_input_refs: Iterable[str],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    ref_char = cas_ref.removeprefix("cas://sha256/")[0]
    runtime_event_ref = f"event://policy_design_case/wave6/walking_skeleton/{record_id}"
    schema_compatibility_ref = _policy_design_skeleton_cas_ref("c")
    effective_mode_ref = _policy_design_skeleton_cas_ref("d")
    same_input_closure_ref = _policy_design_skeleton_cas_ref(ref_char)
    same_input_closure = {
        "closure_id": f"closure.{record_id}",
        "status": "closed",
        "policy_intent_ref": policy_intent_ref,
        "evidence_input_refs": list(evidence_input_refs),
        "same_input_closure_ref": same_input_closure_ref,
    }
    envelope = {
        "artifact_ref": cas_ref,
        "cas_ref": cas_ref,
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "producer_component": POLICY_DESIGN_WALKING_SKELETON_STUB_COMPONENT,
        "producer_version": "2026.05.17+wave6.walking_skeleton",
        "owner": POLICY_DESIGN_CASE_OWNER,
        "runtime_event_ref": runtime_event_ref,
        "diagnostic_event_ref": runtime_event_ref,
        "schema_name": schema_name,
        "schema_version": "1.0.0",
        "schema_compatibility_ref": schema_compatibility_ref,
        "effective_mode_ref": effective_mode_ref,
        "same_input_closure_ref": same_input_closure_ref,
        "reader_contract": POLICY_DESIGN_WALKING_SKELETON_CONTRACT_ID,
        "tenant_id": tenant_id,
        "run_id": run_id,
        "job_id": job_id,
        "requested_execution_profile": requested_execution_profile,
        "effective_execution_profile": effective_execution_profile,
        "generated_at": generated_at.isoformat(),
        "same_input_closure": same_input_closure,
        "validation_status": "pass",
    }
    return {
        "node_type": node_type,
        "record_id": record_id,
        "cas_ref": cas_ref,
        "runtime_event_ref": runtime_event_ref,
        "diagnostic_event_ref": runtime_event_ref,
        "schema_compatibility_ref": schema_compatibility_ref,
        "schema_compatibility": {
            "decision": "compatible",
            "reader_contract": POLICY_DESIGN_WALKING_SKELETON_CONTRACT_ID,
        },
        "effective_mode_ref": effective_mode_ref,
        "same_input_closure_ref": same_input_closure_ref,
        "same_input_closure": same_input_closure,
        "runtime_authority_envelope": envelope,
        **dict(payload),
    }


def build_policy_design_jurisdiction_spine(
    *,
    spine_id: str,
    jurisdiction_spine_ref: str,
    run_id: str,
    job_id: str,
    tenant_id: str,
    policy_intent_ref: str,
    lex_normative_report: Mapping[str, Any],
    runtime_authority: Mapping[str, Any],
    normative_arbitration_result: Mapping[str, Any] | None = None,
    cross_graph_conflicts: Iterable[Mapping[str, Any]] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Project a per-run jurisdiction spine from Lex, IR, and cross-graph surfaces."""

    generated = _utc(generated_at)
    authority = _policy_design_jurisdiction_authority_envelope(
        runtime_authority,
        jurisdiction_spine_ref=jurisdiction_spine_ref,
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        policy_intent_ref=policy_intent_ref,
        generated_at=generated,
    )
    lex_report = dict(lex_normative_report)
    cross_graph_conflict_rows = list(cross_graph_conflicts or ())
    target_context = (
        dict(lex_report.get("target_context"))
        if isinstance(lex_report.get("target_context"), Mapping)
        else {}
    )
    as_of = _policy_design_text(target_context.get("as_of"))
    jurisdiction_rows = _policy_design_jurisdiction_rows_from_lex(
        lex_report,
        default_jurisdiction=_policy_design_text(target_context.get("jurisdiction")),
        default_as_of=as_of,
    )
    jurisdiction_rows = _policy_design_attach_jurisdiction_children(jurisdiction_rows)
    conflict_surfaces = [
        *_policy_design_jurisdiction_conflicts_from_arbitration(
            normative_arbitration_result
        ),
        *_policy_design_jurisdiction_conflicts_from_cross_graph(cross_graph_conflict_rows),
    ]
    payload = {
        "schema_version": POLICY_DESIGN_JURISDICTION_SPINE_SCHEMA_VERSION,
        "spine_id": _policy_design_required_text(
            spine_id,
            "policy_design_jurisdiction_spine_id_missing",
        ),
        "jurisdiction_spine_ref": _policy_design_required_text(
            jurisdiction_spine_ref,
            "policy_design_jurisdiction_spine_ref_missing",
        ),
        "run_id": _policy_design_required_text(
            run_id,
            "policy_design_jurisdiction_spine_run_id_missing",
        ),
        "job_id": _policy_design_required_text(
            job_id,
            "policy_design_jurisdiction_spine_job_id_missing",
        ),
        "tenant_id": _policy_design_required_text(
            tenant_id,
            "policy_design_jurisdiction_spine_tenant_id_missing",
        ),
        "policy_intent_ref": _policy_design_required_text(
            policy_intent_ref,
            "policy_design_jurisdiction_policy_intent_ref_missing",
        ),
        "generated_at": generated.isoformat(),
        "runtime_authority_envelope": authority,
        "authority_level_taxonomy": list(POLICY_DESIGN_JURISDICTION_AUTHORITY_LEVELS),
        "jurisdictions": jurisdiction_rows,
        "conflict_surfaces": conflict_surfaces,
        "unresolved_conflicts": [
            conflict
            for conflict in conflict_surfaces
            if _policy_design_jurisdiction_conflict_is_unresolved(conflict)
        ],
        "blockers": [],
        "projection_sources": _policy_design_jurisdiction_projection_sources(
            lex_report=lex_report,
            normative_arbitration_result=normative_arbitration_result,
            cross_graph_conflicts=cross_graph_conflict_rows,
        ),
    }
    return validate_policy_design_jurisdiction_spine(payload)


def validate_policy_design_jurisdiction_spine(
    spine: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the runtime jurisdiction spine and materialize typed blockers."""

    if not isinstance(spine, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_spine_invalid",
            "Jurisdiction spine must be a mapping.",
        )
    schema_version = _policy_design_text(spine.get("schema_version"))
    if schema_version != POLICY_DESIGN_JURISDICTION_SPINE_SCHEMA_VERSION:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_spine_schema_version_invalid",
            "Jurisdiction spine must use the runtime-quality schema version.",
        )
    authority = spine.get("runtime_authority_envelope") or spine.get("runtime_authority")
    if not isinstance(authority, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_spine_authority_missing",
            "Jurisdiction spine must carry a runtime authority envelope.",
        )
    normalized_authority = _policy_design_jurisdiction_authority_envelope(
        authority,
        jurisdiction_spine_ref=_policy_design_required_text(
            spine.get("jurisdiction_spine_ref"),
            "policy_design_jurisdiction_spine_ref_missing",
        ),
        run_id=_policy_design_required_text(
            spine.get("run_id"),
            "policy_design_jurisdiction_spine_run_id_missing",
        ),
        job_id=_policy_design_required_text(
            spine.get("job_id"),
            "policy_design_jurisdiction_spine_job_id_missing",
        ),
        tenant_id=_policy_design_required_text(
            spine.get("tenant_id"),
            "policy_design_jurisdiction_spine_tenant_id_missing",
        ),
        policy_intent_ref=_policy_design_required_text(
            spine.get("policy_intent_ref"),
            "policy_design_jurisdiction_policy_intent_ref_missing",
        ),
        generated_at=None,
    )
    taxonomy = _policy_design_jurisdiction_authority_taxonomy(
        spine.get("authority_level_taxonomy")
    )
    raw_rows = spine.get("jurisdictions")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_rows_missing",
            "Jurisdiction spine must include jurisdiction rows.",
        )
    jurisdictions = [
        _policy_design_validate_jurisdiction_row(row, taxonomy=taxonomy)
        for row in raw_rows
    ]
    conflict_surfaces = [
        _policy_design_validate_jurisdiction_conflict_surface(conflict)
        for conflict in _policy_design_list(spine.get("conflict_surfaces"))
    ]
    unresolved_conflicts = [
        _policy_design_validate_jurisdiction_conflict_surface(conflict)
        for conflict in _policy_design_list(spine.get("unresolved_conflicts"))
    ]
    for conflict in conflict_surfaces:
        if (
            _policy_design_jurisdiction_conflict_is_unresolved(conflict)
            and conflict not in unresolved_conflicts
        ):
            unresolved_conflicts.append(conflict)
    blockers = [
        _policy_design_jurisdiction_blocker(blocker)
        for blocker in _policy_design_list(spine.get("blockers"))
    ]
    for row in jurisdictions:
        competence = row["competence"]
        if competence["status"] in {"unresolved", "conflicting", "out_of_scope"}:
            blockers.append(_policy_design_unresolved_competence_blocker(row))
            unresolved_conflicts.append(
                {
                    "conflict_id": f"jurisdiction_competence:{row['jurisdiction_id']}",
                    "code": "policy_design_jurisdiction_unresolved_competence_blocker",
                    "severity": "blocker",
                    "blocking": True,
                    "surface": "lex.normative_applicability",
                    "jurisdiction_id": row["jurisdiction_id"],
                    "message": (
                        f"Jurisdiction {row['jurisdiction_id']} lacks resolved "
                        "competence evidence."
                    ),
                }
            )
    blockers = _policy_design_dedupe_blockers(blockers)
    unresolved_conflicts = [
        _policy_design_jurisdiction_typed_conflict(conflict)
        for conflict in unresolved_conflicts
    ]
    blocker_codes = {str(blocker.get("code")) for blocker in blockers}
    for conflict in unresolved_conflicts:
        if str(conflict.get("code")) not in blocker_codes:
            blocker = _policy_design_unresolved_jurisdiction_conflict_blocker(conflict)
            blockers.append(blocker)
            blocker_codes.add(str(blocker["code"]))
    blockers = _policy_design_dedupe_blockers(blockers)
    unresolved_conflicts = _policy_design_dedupe_conflicts(unresolved_conflicts)
    normalized = dict(spine)
    normalized.update(
        {
            "schema_version": POLICY_DESIGN_JURISDICTION_SPINE_SCHEMA_VERSION,
            "spine_id": _policy_design_required_text(
                spine.get("spine_id"),
                "policy_design_jurisdiction_spine_id_missing",
            ),
            "runtime_authority_envelope": normalized_authority,
            "authority_level_taxonomy": list(taxonomy),
            "jurisdictions": jurisdictions,
            "conflict_surfaces": conflict_surfaces,
            "unresolved_conflicts": unresolved_conflicts,
            "blockers": blockers,
            "status": "blocked" if blockers or unresolved_conflicts else "pass",
        }
    )
    return normalized


def policy_design_jurisdiction_spine_json_schema() -> dict[str, Any]:
    """Return the JSON schema for the Phase 8.2 jurisdiction spine record."""

    return {
        "$id": (
            "https://schemas.polisyos.dev/runtime_quality/"
            "policy_design_jurisdiction_spine_v1.schema.json"
        ),
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Policy Design Jurisdiction Spine",
        "type": "object",
        "required": [
            "schema_version",
            "spine_id",
            "jurisdiction_spine_ref",
            "run_id",
            "job_id",
            "tenant_id",
            "policy_intent_ref",
            "runtime_authority_envelope",
            "authority_level_taxonomy",
            "jurisdictions",
            "conflict_surfaces",
            "unresolved_conflicts",
            "blockers",
            "status",
        ],
        "properties": {
            "schema_version": {
                "const": POLICY_DESIGN_JURISDICTION_SPINE_SCHEMA_VERSION
            },
            "spine_id": {"type": "string", "minLength": 1},
            "jurisdiction_spine_ref": {"type": "string", "minLength": 1},
            "run_id": {"type": "string", "minLength": 1},
            "job_id": {"type": "string", "minLength": 1},
            "tenant_id": {"type": "string", "minLength": 1},
            "policy_intent_ref": {"type": "string", "minLength": 1},
            "runtime_authority_envelope": {"type": "object"},
            "authority_level_taxonomy": {
                "type": "array",
                "items": {"enum": list(POLICY_DESIGN_JURISDICTION_AUTHORITY_LEVELS)},
                "minItems": 4,
            },
            "jurisdictions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "jurisdiction_id",
                        "authority_level",
                        "temporal_validity",
                        "competence",
                        "hierarchy",
                        "delegation",
                        "pre_emption",
                    ],
                },
                "minItems": 1,
            },
            "conflict_surfaces": {"type": "array"},
            "unresolved_conflicts": {"type": "array"},
            "blockers": {"type": "array"},
            "status": {"enum": ["pass", "blocked"]},
        },
        "additionalProperties": True,
    }


def _policy_design_jurisdiction_authority_envelope(
    authority: Mapping[str, Any],
    *,
    jurisdiction_spine_ref: str,
    run_id: str,
    job_id: str,
    tenant_id: str,
    policy_intent_ref: str,
    generated_at: datetime | None,
) -> dict[str, Any]:
    role = _policy_design_required_text(
        authority.get("authority_role"),
        "policy_design_jurisdiction_spine_authority_role_missing",
    )
    provenance = _policy_design_required_text(
        authority.get("provenance_kind"),
        "policy_design_jurisdiction_spine_provenance_missing",
    )
    if role == "not_authoritative" or provenance == "static_inventory":
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_spine_static_inventory_not_authority",
            "Static inventories cannot satisfy a per-run jurisdiction spine.",
        )
    if role not in {"producer_authority", "runtime_blocker"}:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_spine_authority_role_invalid",
            "Jurisdiction spine authority must be producer_authority or runtime_blocker.",
        )
    if provenance not in {"runtime_emitted", "runtime_blocker"}:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_spine_provenance_invalid",
            "Jurisdiction spine must be runtime-emitted or a runtime blocker.",
        )
    cas_ref = _policy_design_required_text(
        authority.get("cas_ref") or authority.get("artifact_ref") or jurisdiction_spine_ref,
        "policy_design_jurisdiction_spine_cas_ref_missing",
    )
    _policy_design_reject_jurisdiction_local_ref(cas_ref)
    runtime_event_ref = _policy_design_required_text(
        authority.get("runtime_event_ref"),
        "policy_design_jurisdiction_spine_runtime_event_ref_missing",
    )
    _policy_design_reject_jurisdiction_local_ref(runtime_event_ref)
    normalized = dict(authority)
    normalized.update(
        {
            "artifact_ref": cas_ref,
            "cas_ref": cas_ref,
            "authority_role": role,
            "provenance_kind": provenance,
            "producer_component": _policy_design_text(authority.get("producer_component"))
            or POLICY_DESIGN_JURISDICTION_SPINE_PROJECTOR_COMPONENT,
            "producer_version": _policy_design_text(authority.get("producer_version"))
            or "2026.05.17+pdc-phase8.2",
            "owner": _policy_design_text(authority.get("owner"))
            or "team-policy-semantics",
            "runtime_event_ref": runtime_event_ref,
            "schema_name": _policy_design_text(authority.get("schema_name"))
            or "policy_design_case.jurisdiction_spine",
            "schema_version": _policy_design_text(authority.get("schema_version"))
            or "1.0.0",
            "reader_contract": _policy_design_text(authority.get("reader_contract"))
            or POLICY_DESIGN_JURISDICTION_SPINE_CONTRACT,
            "run_id": _policy_design_text(authority.get("run_id")) or run_id,
            "job_id": _policy_design_text(authority.get("job_id")) or job_id,
            "tenant_id": _policy_design_text(authority.get("tenant_id")) or tenant_id,
            "policy_intent_ref": _policy_design_text(authority.get("policy_intent_ref"))
            or policy_intent_ref,
        }
    )
    if generated_at is not None and _policy_design_text(authority.get("generated_at")) is None:
        normalized["generated_at"] = generated_at.isoformat()
    for key in (
        "same_input_closure_ref",
        "effective_mode_ref",
        "schema_compatibility_ref",
    ):
        value = _policy_design_required_text(
            authority.get(key),
            f"policy_design_jurisdiction_spine_{key}_missing",
        )
        _policy_design_reject_jurisdiction_local_ref(value)
        normalized[key] = value
    return normalized


def _policy_design_jurisdiction_rows_from_lex(
    lex_report: Mapping[str, Any],
    *,
    default_jurisdiction: str | None,
    default_as_of: str | None,
) -> list[dict[str, Any]]:
    rows_by_id: dict[str, dict[str, Any]] = {}
    for norm in _policy_design_lex_norms(lex_report):
        row = _policy_design_jurisdiction_row_from_norm(
            norm,
            default_jurisdiction=default_jurisdiction,
            default_as_of=default_as_of,
        )
        existing = rows_by_id.get(str(row["jurisdiction_id"]))
        if existing is None:
            rows_by_id[str(row["jurisdiction_id"])] = row
        else:
            rows_by_id[str(row["jurisdiction_id"])] = _policy_design_merge_jurisdiction_rows(
                existing,
                row,
            )
    if not rows_by_id and default_jurisdiction is not None:
        row = _policy_design_jurisdiction_row_from_norm(
            {"jurisdiction": default_jurisdiction, "effective_from": default_as_of},
            default_jurisdiction=default_jurisdiction,
            default_as_of=default_as_of,
        )
        rows_by_id[str(row["jurisdiction_id"])] = row
    return list(rows_by_id.values())


def _policy_design_lex_norms(lex_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    norms: list[dict[str, Any]] = []
    for key in ("applied_norms", "candidate_norms", "selected_norms", "norms"):
        value = lex_report.get(key)
        if isinstance(value, list):
            norms.extend(dict(item) for item in value if isinstance(item, Mapping))
    return norms


def _policy_design_jurisdiction_row_from_norm(
    norm: Mapping[str, Any],
    *,
    default_jurisdiction: str | None,
    default_as_of: str | None,
) -> dict[str, Any]:
    jurisdiction_id = _policy_design_required_text(
        norm.get("jurisdiction") or norm.get("jurisdiction_norm") or default_jurisdiction,
        "policy_design_jurisdiction_id_missing",
    ).upper()
    authority_level = _policy_design_jurisdiction_authority_level(
        norm.get("jurisdiction_authority_level")
        or norm.get("authority_level")
        or norm.get("source_authority_level"),
        jurisdiction_id=jurisdiction_id,
    )
    norm_ref = _policy_design_text(
        norm.get("norm_id") or norm.get("id") or norm.get("artifact_id")
    )
    effective_from = _policy_design_text(
        norm.get("effective_from")
        or norm.get("valid_from")
        or norm.get("as_of")
        or default_as_of
    )
    effective_to = _policy_design_text(norm.get("effective_to") or norm.get("valid_to"))
    competence_scope = _policy_design_text(
        norm.get("competence")
        or norm.get("competence_scope")
        or norm.get("institutional_competence")
    )
    competent_authority = _policy_design_text(
        norm.get("competent_authority")
        or norm.get("implementing_authority")
        or norm.get("source_authority")
        or norm.get("authority")
        or norm.get("publisher")
    )
    parent_ids = _policy_design_text_list(
        norm.get("hierarchy_parent_jurisdiction_ids")
        or norm.get("parent_jurisdiction_ids")
        or norm.get("parent_jurisdictions")
    )
    if not parent_ids:
        parent_ids = _policy_design_inferred_parent_jurisdictions(
            jurisdiction_id,
            authority_level=authority_level,
        )
    delegated_from = _policy_design_text_list(norm.get("delegated_from"))
    delegated_to = _policy_design_text_list(norm.get("delegated_to"))
    preempts = _policy_design_text_list(norm.get("preempts") or norm.get("preempts_jurisdictions"))
    preempted_by = _policy_design_text_list(
        norm.get("preempted_by") or norm.get("preempted_by_jurisdictions")
    )
    return {
        "jurisdiction_id": jurisdiction_id,
        "authority_level": authority_level,
        "temporal_validity": {
            "valid_from": effective_from,
            "valid_to": effective_to,
        },
        "competence": {
            "status": "resolved" if competence_scope or competent_authority else "unresolved",
            "authority": competent_authority,
            "scope": competence_scope,
        },
        "hierarchy": {
            "parent_jurisdiction_ids": parent_ids,
            "child_jurisdiction_ids": _policy_design_text_list(
                norm.get("child_jurisdiction_ids") or norm.get("child_jurisdictions")
            ),
        },
        "delegation": {
            "delegated_from": delegated_from,
            "delegated_to": delegated_to,
            "delegation_refs": _policy_design_text_list(norm.get("delegation_refs"))
            or ([norm_ref] if (delegated_from or delegated_to) and norm_ref else []),
        },
        "pre_emption": {
            "preempts": preempts,
            "preempted_by": preempted_by,
            "rule_refs": _policy_design_text_list(norm.get("preemption_rule_refs")),
        },
        "source_norm_refs": [norm_ref] if norm_ref is not None else [],
    }


def _policy_design_jurisdiction_authority_level(
    value: object,
    *,
    jurisdiction_id: str,
) -> str:
    text = _policy_design_text(value)
    normalized = text.casefold().replace("-", "_") if text is not None else ""
    aliases = {
        "supra_national": "supranational",
        "supra": "supranational",
        "state": "regional",
        "province": "regional",
        "oblast": "regional",
        "municipal": "local",
        "city": "local",
    }
    candidate = aliases.get(normalized, normalized)
    if candidate in POLICY_DESIGN_JURISDICTION_AUTHORITY_LEVELS:
        return candidate
    upper = jurisdiction_id.upper()
    if upper in {"EU", "UN", "OECD", "COE", "COUNCIL_OF_EUROPE"}:
        return "supranational"
    parts = [part for part in upper.replace("_", "-").split("-") if part]
    if len(parts) >= 3:
        return "local"
    if len(parts) == 2:
        return "regional"
    return "national"


def _policy_design_inferred_parent_jurisdictions(
    jurisdiction_id: str,
    *,
    authority_level: str,
) -> list[str]:
    if authority_level in {"national", "supranational"}:
        return []
    parts = [part for part in jurisdiction_id.replace("_", "-").split("-") if part]
    if len(parts) <= 1:
        return []
    return ["-".join(parts[:-1])]


def _policy_design_merge_jurisdiction_rows(
    first: dict[str, Any],
    second: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(first)
    merged["source_norm_refs"] = _policy_design_merge_text_lists(
        first.get("source_norm_refs"),
        second.get("source_norm_refs"),
    )
    for nested_key, fields in {
        "hierarchy": ("parent_jurisdiction_ids", "child_jurisdiction_ids"),
        "delegation": ("delegated_from", "delegated_to", "delegation_refs"),
        "pre_emption": ("preempts", "preempted_by", "rule_refs"),
    }.items():
        merged_nested = dict(first.get(nested_key) or {})
        second_value = second.get(nested_key)
        second_nested = second_value if isinstance(second_value, Mapping) else {}
        for field in fields:
            merged_nested[field] = _policy_design_merge_text_lists(
                merged_nested.get(field),
                second_nested.get(field),
            )
        merged[nested_key] = merged_nested
    competence = dict(first.get("competence") or {})
    second_competence = (
        second.get("competence") if isinstance(second.get("competence"), Mapping) else {}
    )
    if competence.get("status") == "unresolved" and second_competence.get("status") != "unresolved":
        merged["competence"] = dict(second_competence)
    return merged


def _policy_design_attach_jurisdiction_children(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    children_by_parent: dict[str, list[str]] = {}
    for row in rows:
        jurisdiction_id = str(row["jurisdiction_id"])
        hierarchy = row.get("hierarchy") if isinstance(row.get("hierarchy"), Mapping) else {}
        for parent in _policy_design_text_list(hierarchy.get("parent_jurisdiction_ids")):
            children_by_parent.setdefault(parent, []).append(jurisdiction_id)
    attached: list[dict[str, Any]] = []
    for row in rows:
        clone = dict(row)
        hierarchy = dict(row.get("hierarchy") or {})
        hierarchy["child_jurisdiction_ids"] = _policy_design_merge_text_lists(
            hierarchy.get("child_jurisdiction_ids"),
            children_by_parent.get(str(row["jurisdiction_id"])),
        )
        clone["hierarchy"] = hierarchy
        attached.append(clone)
    return attached


def _policy_design_jurisdiction_conflicts_from_arbitration(
    result: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(result, Mapping):
        return []
    conflicts: list[dict[str, Any]] = []
    for key in ("rights_audit", "hard_constraint_audit"):
        for index, item in enumerate(_policy_design_list(result.get(key)), start=1):
            if not isinstance(item, Mapping):
                continue
            status = _policy_design_text(item.get("status")) or "unevaluated"
            conflict_id = _policy_design_text(
                item.get("right_id")
                or item.get("constraint_id")
                or item.get("binding_ref")
                or f"{key}:{index}"
            )
            conflicts.append(
                {
                    "surface": "ir.normative_arbitration",
                    "conflict_id": conflict_id,
                    "status": "resolved" if status in {"satisfied", "resolved"} else status,
                    "severity": "blocker" if status == "violated" else "info",
                    "blocking": status == "violated",
                    "message": "; ".join(_policy_design_text_list(item.get("notes")))
                    or f"IR normative arbitration {key} entry.",
                }
            )
    for index, item in enumerate(_policy_design_list(result.get("residual_dissent")), start=1):
        if not isinstance(item, Mapping):
            continue
        conflicts.append(
            {
                "surface": "ir.normative_arbitration",
                "conflict_id": _policy_design_text(item.get("policy"))
                or f"residual_dissent:{index}",
                "status": "unresolved",
                "severity": "warning",
                "blocking": False,
                "message": _policy_design_text(item.get("rationale")) or "Residual dissent.",
            }
        )
    return conflicts


def _policy_design_jurisdiction_conflicts_from_cross_graph(
    conflicts: Iterable[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, conflict in enumerate(conflicts or (), start=1):
        if not isinstance(conflict, Mapping):
            continue
        severity = (_policy_design_text(conflict.get("severity")) or "medium").casefold()
        blocking = bool(conflict.get("blocking")) or severity in {"critical", "blocker", "fail"}
        resolved = _policy_design_text(
            conflict.get("resolved_status") or conflict.get("status")
        )
        rows.append(
            {
                "surface": "scientist.cross_graph.conflict",
                "conflict_id": _policy_design_text(
                    conflict.get("conflict_id") or conflict.get("need_id")
                )
                or f"cross_graph_conflict:{index}",
                "status": resolved or ("unresolved" if blocking else "reviewable"),
                "severity": severity,
                "blocking": blocking,
                "message": _policy_design_text(conflict.get("description"))
                or "Cross-graph conflict.",
                "dimension": _policy_design_text(conflict.get("dimension")),
            }
        )
    return rows


def _policy_design_jurisdiction_projection_sources(
    *,
    lex_report: Mapping[str, Any],
    normative_arbitration_result: Mapping[str, Any] | None,
    cross_graph_conflicts: Iterable[Mapping[str, Any]] | None,
) -> dict[str, list[str]]:
    sources = {
        "lex": [
            _policy_design_text(lex_report.get("schema_version"))
            or "policyos.lex.normative_applicability_report.v1"
        ],
        "ir_normative_arbitration": [],
        "cross_graph_conflict": [],
    }
    if isinstance(normative_arbitration_result, Mapping):
        sources["ir_normative_arbitration"].append("ir.normative_arbitration_result")
    for index, conflict in enumerate(cross_graph_conflicts or (), start=1):
        if not isinstance(conflict, Mapping):
            continue
        sources["cross_graph_conflict"].append(
            _policy_design_text(conflict.get("conflict_id") or conflict.get("need_id"))
            or f"cross_graph_conflict:{index}"
        )
    return sources


def _policy_design_jurisdiction_authority_taxonomy(value: object) -> tuple[str, ...]:
    levels = tuple(_policy_design_text_list(value))
    if set(levels) != set(POLICY_DESIGN_JURISDICTION_AUTHORITY_LEVELS):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_authority_taxonomy_missing",
            "Jurisdiction spine must record supranational, national, regional, and local levels.",
        )
    return POLICY_DESIGN_JURISDICTION_AUTHORITY_LEVELS


def _policy_design_validate_jurisdiction_row(
    row: object,
    *,
    taxonomy: tuple[str, ...],
) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_row_invalid",
            "Jurisdiction rows must be mappings.",
        )
    jurisdiction_id = _policy_design_required_text(
        row.get("jurisdiction_id") or row.get("jurisdiction"),
        "policy_design_jurisdiction_id_missing",
    )
    authority_level = _policy_design_required_text(
        row.get("authority_level"),
        "policy_design_jurisdiction_authority_level_missing",
    )
    if authority_level not in taxonomy:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_authority_level_invalid",
            "Jurisdiction row authority_level must be in the Phase 8.2 taxonomy.",
        )
    temporal = row.get("temporal_validity")
    if not isinstance(temporal, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_temporal_validity_missing",
            "Jurisdiction row must record temporal validity.",
        )
    competence = row.get("competence")
    if not isinstance(competence, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_competence_missing",
            "Jurisdiction row must record competence.",
        )
    competence_status = (
        _policy_design_text(competence.get("status")) or "unresolved"
    ).casefold()
    if competence_status not in {
        "resolved",
        "delegated",
        "not_applicable",
        "unresolved",
        "conflicting",
        "out_of_scope",
    }:
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_competence_status_invalid",
            "Competence status must be resolved, delegated, not_applicable, or blocker-shaped.",
        )
    return {
        **dict(row),
        "jurisdiction_id": jurisdiction_id,
        "authority_level": authority_level,
        "temporal_validity": {
            "valid_from": _policy_design_text(temporal.get("valid_from")),
            "valid_to": _policy_design_text(temporal.get("valid_to")),
        },
        "competence": {
            "status": competence_status,
            "authority": _policy_design_text(competence.get("authority")),
            "scope": _policy_design_text(competence.get("scope")),
        },
        "hierarchy": _policy_design_jurisdiction_relation(
            row.get("hierarchy"),
            fields=("parent_jurisdiction_ids", "child_jurisdiction_ids"),
            code="policy_design_jurisdiction_hierarchy_missing",
        ),
        "delegation": _policy_design_jurisdiction_relation(
            row.get("delegation"),
            fields=("delegated_from", "delegated_to", "delegation_refs"),
            code="policy_design_jurisdiction_delegation_missing",
        ),
        "pre_emption": _policy_design_jurisdiction_relation(
            row.get("pre_emption") or row.get("preemption"),
            fields=("preempts", "preempted_by", "rule_refs"),
            code="policy_design_jurisdiction_preemption_missing",
        ),
        "source_norm_refs": _policy_design_text_list(row.get("source_norm_refs")),
    }


def _policy_design_jurisdiction_relation(
    value: object,
    *,
    fields: tuple[str, ...],
    code: str,
) -> dict[str, list[str]]:
    if not isinstance(value, Mapping):
        raise PolicyDesignCaseAuthorityError(
            code,
            "Jurisdiction spine row is missing a required relation block.",
        )
    return {field: _policy_design_text_list(value.get(field)) for field in fields}


def _policy_design_validate_jurisdiction_conflict_surface(
    conflict: object,
) -> dict[str, Any]:
    if not isinstance(conflict, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_conflict_surface_invalid",
            "Jurisdiction conflict surfaces must be mappings.",
        )
    return {
        **dict(conflict),
        "surface": _policy_design_required_text(
            conflict.get("surface"),
            "policy_design_jurisdiction_conflict_surface_missing",
        ),
        "conflict_id": _policy_design_required_text(
            conflict.get("conflict_id"),
            "policy_design_jurisdiction_conflict_id_missing",
        ),
        "status": _policy_design_text(conflict.get("status")) or "unresolved",
        "severity": _policy_design_text(conflict.get("severity")) or "warning",
        "blocking": bool(conflict.get("blocking")),
        "message": _policy_design_text(conflict.get("message")) or "Jurisdiction conflict.",
    }


def _policy_design_jurisdiction_conflict_is_unresolved(
    conflict: Mapping[str, Any],
) -> bool:
    status = (_policy_design_text(conflict.get("status")) or "").casefold()
    severity = (_policy_design_text(conflict.get("severity")) or "").casefold()
    return bool(conflict.get("blocking")) or status in {
        "unresolved",
        "violated",
        "requires_review",
    } or severity in {"critical", "blocker", "fail", "failed"}


def _policy_design_jurisdiction_blocker(blocker: object) -> dict[str, Any]:
    if not isinstance(blocker, Mapping):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_blocker_invalid",
            "Jurisdiction spine blockers must be mappings.",
        )
    return {
        "code": _policy_design_required_text(
            blocker.get("code"),
            "policy_design_jurisdiction_blocker_code_missing",
        ),
        "owner": _policy_design_text(blocker.get("owner")) or "team-policy-semantics",
        "missing_input": _policy_design_text(blocker.get("missing_input")),
        "upstream_cause": _policy_design_text(blocker.get("upstream_cause")),
        "downstream_impact": _policy_design_text(blocker.get("downstream_impact")),
        "next_command": _policy_design_text(blocker.get("next_command"))
        or (
            "uv run pytest "
            "tests/unit/runtime/quality/test_policy_design_jurisdiction_spine.py -q"
        ),
    }


def _policy_design_jurisdiction_typed_conflict(
    conflict: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = dict(conflict)
    normalized["code"] = (
        _policy_design_text(conflict.get("code"))
        or "policy_design_jurisdiction_unresolved_conflict_blocker"
    )
    normalized["severity"] = (
        _policy_design_text(conflict.get("severity")) or "blocker"
    )
    normalized["blocking"] = True
    return normalized


def _policy_design_unresolved_competence_blocker(
    row: Mapping[str, Any],
) -> dict[str, Any]:
    jurisdiction_id = str(row["jurisdiction_id"])
    return {
        "code": "policy_design_jurisdiction_unresolved_competence_blocker",
        "owner": "team-policy-semantics",
        "missing_input": f"competence evidence for {jurisdiction_id}",
        "upstream_cause": (
            "Lex selected a jurisdictional norm without competent authority or "
            "competence scope."
        ),
        "downstream_impact": (
            "Legal, data, method, and claim evidence cannot close over the same "
            "jurisdiction spine."
        ),
        "next_command": (
            "uv run pytest "
            "tests/unit/runtime/quality/test_policy_design_jurisdiction_spine.py -q"
        ),
    }


def _policy_design_unresolved_jurisdiction_conflict_blocker(
    conflict: Mapping[str, Any],
) -> dict[str, Any]:
    conflict_id = _policy_design_text(conflict.get("conflict_id")) or "unknown"
    surface = _policy_design_text(conflict.get("surface")) or "jurisdiction_spine"
    return {
        "code": _policy_design_text(conflict.get("code"))
        or "policy_design_jurisdiction_unresolved_conflict_blocker",
        "owner": "team-policy-semantics",
        "missing_input": f"resolved jurisdiction conflict for {conflict_id}",
        "upstream_cause": (
            f"{surface} emitted an unresolved or blocking jurisdiction conflict."
        ),
        "downstream_impact": (
            "Legal, data, method, and claim evidence cannot close over the same "
            "jurisdiction spine."
        ),
        "next_command": (
            "uv run pytest "
            "tests/unit/runtime/quality/test_policy_design_jurisdiction_spine.py -q"
        ),
    }


def _policy_design_dedupe_blockers(
    blockers: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for blocker in blockers:
        deduped[str(blocker["code"])] = dict(blocker)
    return list(deduped.values())


def _policy_design_dedupe_conflicts(
    conflicts: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for conflict in conflicts:
        deduped[
            (
                str(conflict.get("surface") or "unknown"),
                str(conflict.get("conflict_id") or "unknown"),
            )
        ] = dict(conflict)
    return list(deduped.values())


def _policy_design_merge_text_lists(first: object, second: object) -> list[str]:
    return list(
        dict.fromkeys(
            [*_policy_design_text_list(first), *_policy_design_text_list(second)]
        )
    )


def _policy_design_list(value: object) -> list[Any]:
    if isinstance(value, list | tuple):
        return list(value)
    return []


def _policy_design_reject_jurisdiction_local_ref(value: str) -> None:
    if (
        _looks_like_local_path(value)
        or value.startswith("repo://")
        or value.startswith("file://")
        or value.startswith("quality_evidence/")
        or value.startswith("dashboard://")
        or value.startswith("public://")
    ):
        raise PolicyDesignCaseAuthorityError(
            "policy_design_jurisdiction_spine_local_ref_not_authority",
            "Jurisdiction spine refs must be runtime authority refs.",
        )


def _policy_design_required_text(value: object, code: str) -> str:
    text = _policy_design_text(value)
    if text is None:
        raise PolicyDesignCaseAuthorityError(code)
    return text


def _policy_design_text(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return None


def _policy_design_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = _policy_design_text(value)
        return [text] if text is not None else []
    if not isinstance(value, Iterable):
        return []
    items: list[str] = []
    for item in value:
        text = _policy_design_text(item)
        if text is not None:
            items.append(text)
    return list(dict.fromkeys(items))


def _looks_like_local_path(value: str) -> bool:
    return (
        value.startswith("/")
        or value.startswith("./")
        or value.startswith("../")
        or "\\" in value
    )


__all__ = [
    "ASSURANCE_CASE_REQUIRED_FIELDS",
    "POLICY_DESIGN_CAPABILITY_DUTY_STATES",
    "POLICY_DESIGN_CAPABILITY_LEDGER_SCHEMA_VERSION",
    "POLICY_DESIGN_CASE_CORE_NODE_TYPES",
    "POLICY_DESIGN_CASE_OWNER",
    "POLICY_DESIGN_CASE_PROFILE",
    "POLICY_DESIGN_CASE_PROFILE_METADATA",
    "POLICY_DESIGN_CASE_REGISTRY_ENTRY_SCHEMA_VERSION",
    "POLICY_DESIGN_CASE_RESERVED_NODE_FAMILIES",
    "POLICY_DESIGN_CASE_SCHEMA_VERSION",
    "POLICY_DESIGN_CONCEPT_SPINE_CONTRACT_ID",
    "POLICY_DESIGN_CONCEPT_SPINE_REQUIRED_CLOSURE_FIELDS",
    "POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION",
    "POLICY_DESIGN_JURISDICTION_AUTHORITY_LEVELS",
    "POLICY_DESIGN_JURISDICTION_SPINE_SCHEMA_VERSION",
    "POLICY_DESIGN_REQUIRED_CAPABILITIES",
    "POLICY_DESIGN_WALKING_SKELETON_CONTRACT_ID",
    "POLICY_DESIGN_WALKING_SKELETON_SCHEMA_VERSION",
    "POLICY_INTENT_ENVELOPE_SCHEMA_VERSION",
    "PolicyDesignCaseAuthorityError",
    "build_assurance_case_for_scorecard",
    "build_capability_duty_record",
    "build_capability_selection_ledger",
    "build_policy_design_case_concept_spine",
    "build_policy_design_case_profile",
    "build_policy_design_case_registry_entry",
    "build_policy_design_case_walking_skeleton",
    "build_policy_design_jurisdiction_spine",
    "build_policy_intent_envelope",
    "policy_design_concept_spine_json_schema",
    "policy_design_jurisdiction_spine_json_schema",
    "validate_capability_selection_ledger",
    "validate_policy_design_case_concept_spine",
    "validate_policy_design_case_profile",
    "validate_policy_design_jurisdiction_spine",
    "validate_policy_intent_envelope",
]
