"""Canonical runtime quality-report role, file, and reference registry.

This module is deliberately dependency-light so ref intake, scorecards, and
canary assembly share one complete registry without importing a consumer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from polisyos.core.canon import CanonSpec, to_canonical_bytes

REQUIRED_QUALITY_REF_KEYS = (
    "production_data_quality_report_ref",
    "normative_applicability_report_ref",
    "fabric_retrieval_trace_ref",
    "foundry_method_report_ref",
    "policy_grounding_matrix_ref",
    "conflict_check_ref",
)
LIFECYCLE_QUALITY_REF_KEYS = (
    "continuous_governance_stale_report_ref",
    "continuous_governance_reissue_report_ref",
    "continuous_governance_supersede_report_ref",
    "continuous_governance_withdraw_report_ref",
)
KNOWN_QUALITY_REF_KEYS = (
    *REQUIRED_QUALITY_REF_KEYS,
    *LIFECYCLE_QUALITY_REF_KEYS,
    "security_assurance_report_ref",
)

# These contract constants are re-exported by their former owning modules.
# Keeping their literal values here lets this registry stay below all consumers.
COST_DEGRADATION_TELEMETRY_REPORT_KEY = "cost_degradation_telemetry"
COST_DEGRADATION_TELEMETRY_FILENAME = "cost_degradation_telemetry.json"
RUN_COST_GATE_REPORT_KEY = "run_cost_gate"
RUN_COST_GATE_FILENAME = "run_cost_gate.json"
DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY = "data_forge_snapshot_binding"
DATA_FORGE_SNAPSHOT_BINDING_FILE = "data_forge_snapshot_binding.json"
HYPOTHESIS_LEDGER_REPORT_KEY = "hypothesis_ledger"
HYPOTHESIS_LEDGER_REF_KEY = "hypothesis_ledger_ref"
HYPOTHESIS_LEDGER_FILENAME = "hypothesis_ledger.json"
PROMPT_TOOL_LEDGER_REPORT_KEY = "prompt_tool_ledger"
PROMPT_TOOL_LEDGER_REF_KEY = "prompt_tool_ledger_ref"
PROMPT_TOOL_LEDGER_FILENAME = "prompt_tool_ledger.json"

QUALITY_REPORT_FILES = {
    "golden_scenario_contract": "golden_scenario_contract.json",
    "production_data_quality": "production_data_quality.json",
    "normative_evidence": "normative_evidence.json",
    "fabric_retrieval_trace": "fabric_retrieval_trace.json",
    "foundry_method_report": "foundry_method_report.json",
    "policy_grounding_matrix": "policy_grounding_matrix.json",
    "semantic_binding_ledger": "semantic_binding_ledger.json",
    "conflict_check": "conflict_check.json",
    "causal_statistical_validity": "causal_statistical_validity.json",
    "replay_manifest": "replay_manifest.json",
    "drift_explanation": "drift_explanation.json",
    "resilience_matrix": "resilience_matrix.json",
    "human_review_calibration": "human_review_calibration_report.json",
    "decision_artifact_quality": "decision_artifact_quality.json",
    "provider_model_quality_ledger": "provider_model_quality_ledger.json",
    "prompt_tool_ledger": PROMPT_TOOL_LEDGER_FILENAME,
    HYPOTHESIS_LEDGER_REPORT_KEY: HYPOTHESIS_LEDGER_FILENAME,
    COST_DEGRADATION_TELEMETRY_REPORT_KEY: COST_DEGRADATION_TELEMETRY_FILENAME,
    RUN_COST_GATE_REPORT_KEY: RUN_COST_GATE_FILENAME,
    "security_assurance_report": "security_assurance_report.json",
    "privacy_compliance_report": "privacy_compliance_report.json",
    "policy_design_case": "policy_design_case.json",
    "claim_registry": "claim_registry.json",
    "scholar_evidence": "scholar_academic_evidence.json",
    "scenario_contract_propagation_graph": "scenario_contract_propagation_graph.json",
    "evidence_spine_handoff_ledger": "evidence_spine_handoff_ledger.json",
    "producer_pipeline": "producer_pipeline.json",
    "producer_handshake_ledger": "producer_handshake_ledger.json",
    "producer_pipeline_readiness": "producer_pipeline_readiness.json",
    "producer_pipeline_control_plane": "producer_pipeline_control_plane.json",
    "producer_pipeline_replay": "producer_pipeline_replay.json",
    "producer_pipeline_bundle_assembly": "producer_pipeline_bundle_assembly.json",
    "producer_pipeline_inspection": "producer_pipeline_inspection.json",
    DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY: DATA_FORGE_SNAPSHOT_BINDING_FILE,
    "continuous_governance_stale": "continuous_governance_stale_report.json",
    "continuous_governance_reissue": "continuous_governance_reissue_report.json",
    "continuous_governance_supersede": "continuous_governance_supersede_report.json",
    "continuous_governance_withdraw": "continuous_governance_withdraw_report.json",
    "source_truth_conflicts": "source_truth_conflicts.json",
    "formal_invariants": "formal_invariants.json",
    "source_truth": "source_truth.json",
    "conflict_materialization": "conflict_materialization_closeout.json",
    "attestation": "attestation.json",
    "policy_design_case_i4_graph": "policy_design_case_i4_graph.json",
    "policy_design_portfolio_effective_support": ("policy_design_portfolio_effective_support.json"),
    "lifecycle_reissue_report": "lifecycle_reissue_report.json",
    "policy_design_case_projection": "policy_design_case_projection.json",
    "projection_publication_state": "projection_publication_state.json",
    "policy_design_case_projection_contract_fixture": (
        "policy_design_case_projection_contract_fixture.json"
    ),
    "calibration_ledger": "calibration_ledger.json",
    "run_cost_proportionality": "run_cost_proportionality.json",
    "audit_verifier_ingestion": "audit_verifier.json",
    "can_i_closeout": "can_i_closeout.json",
}

QUALITY_REPORT_RUNTIME_REFS = {
    "production_data_quality": "production_data_quality_report_ref",
    "normative_evidence": "normative_applicability_report_ref",
    "fabric_retrieval_trace": "fabric_retrieval_trace_ref",
    "foundry_method_report": "foundry_method_report_ref",
    "policy_grounding_matrix": "policy_grounding_matrix_ref",
    "semantic_binding_ledger": "semantic_binding_ledger_ref",
    "conflict_check": "conflict_check_ref",
    "causal_statistical_validity": "causal_statistical_validity_report_ref",
    "replay_manifest": "replay_manifest_ref",
    "drift_explanation": "drift_explanation_ref",
    "resilience_matrix": "resilience_report_ref",
    "human_review_calibration": "human_review_calibration_report_ref",
    "decision_artifact_quality": "decision_artifact_quality_report_ref",
    "provider_model_quality_ledger": "provider_model_quality_ledger_ref",
    HYPOTHESIS_LEDGER_REPORT_KEY: HYPOTHESIS_LEDGER_REF_KEY,
    "security_assurance_report": "security_assurance_report_ref",
    "privacy_compliance_report": "privacy_compliance_report_ref",
    "continuous_governance_stale": "continuous_governance_stale_report_ref",
    "continuous_governance_reissue": "continuous_governance_reissue_report_ref",
    "continuous_governance_supersede": "continuous_governance_supersede_report_ref",
    "continuous_governance_withdraw": "continuous_governance_withdraw_report_ref",
    "can_i_closeout": "can_i_closeout_ref",
}


# Closure pointers prefer a typed current input with exact role, ref, and profile;
# current owner-produced report refs use the shared strict CAS re-entry verifier.
RUNTIME_QUALITY_PUBLICATION_CLOSURE_REFERENCE_BINDINGS = (
    (
        "policy_intent_ref",
        "policy_intent_envelope_ref",
        "policy_intent_envelope",
        "runtime.policy_intent_envelope",
        "polisyos.runtime.PolicyIntentEnvelope",
        "1.0",
    ),
    (
        "production_data_manifest_ref",
        "production_data_quality_report_ref",
        "production_data_quality_report",
        "runtime.production_data_quality_report",
        "polisyos.runtime.ProductionDataQualityReport",
        "1.0",
    ),
    (
        "legal_snapshot_ref",
        "normative_applicability_report_ref",
        "normative_applicability_report",
        "lex.normative_applicability_report",
        "polisyos.lex.NormativeApplicabilityReport",
        "1.0",
    ),
)
RUNTIME_QUALITY_PUBLICATION_SEMANTIC_BINDING_REFERENCE_BINDING = (
    "semantic_binding_ledger_ref",
    "semantic_binding_ledger",
    "runtime.semantic_binding_ledger",
    "polisyos.runtime.SemanticBindingLedger",
    "1.0",
)


# Exact producer identity is separate from intake aliases: aliases locate candidate
# refs but never establish report ownership or artifact authority.
RUNTIME_QUALITY_OWNER_PRODUCER_VERSION = "2026.05.15+hds-phase2.4"
RUNTIME_QUALITY_OWNER_SCHEMA_VERSION = "1.0"
RUNTIME_QUALITY_OWNER_MEDIA_TYPE = "application/json"
RUNTIME_QUALITY_OWNER_MARKER_SCHEMA = "policyos.runtime.authority_payload_marker.v1"


@dataclass(frozen=True, slots=True)
class RuntimeQualityReportOwnerContract:
    """Exact writer identity for one registered runtime quality report."""

    report_key: str
    ref_key: str
    artifact_kind: str
    schema_name: str
    phase: str
    schema_version: str = RUNTIME_QUALITY_OWNER_SCHEMA_VERSION
    media_type: str = RUNTIME_QUALITY_OWNER_MEDIA_TYPE
    producer_component: str = ""
    producer_version: str = RUNTIME_QUALITY_OWNER_PRODUCER_VERSION

    def __post_init__(self) -> None:
        if not self.producer_component:
            object.__setattr__(
                self,
                "producer_component",
                f"polisyos.runtime.quality.{self.report_key}",
            )


def _runtime_quality_owner_contract(
    report_key: str,
    ref_key: str,
    artifact_kind: str,
    schema_name: str,
    phase: str,
) -> RuntimeQualityReportOwnerContract:
    return RuntimeQualityReportOwnerContract(
        report_key=report_key,
        ref_key=ref_key,
        artifact_kind=artifact_kind,
        schema_name=schema_name,
        phase=phase,
    )


RUNTIME_QUALITY_REPORT_OWNER_CONTRACTS = {
    "production_data_quality": _runtime_quality_owner_contract(
        "production_data_quality",
        "production_data_quality_report_ref",
        "runtime.production_data_quality_report",
        "polisyos.runtime.ProductionDataQualityReport",
        "production_data_quality",
    ),
    "normative_evidence": _runtime_quality_owner_contract(
        "normative_evidence",
        "normative_applicability_report_ref",
        "lex.normative_applicability_report",
        "polisyos.lex.NormativeApplicabilityReport",
        "normative_applicability_report",
    ),
    "fabric_retrieval_trace": _runtime_quality_owner_contract(
        "fabric_retrieval_trace",
        "fabric_retrieval_trace_ref",
        "fabric.retrieval_trace",
        "polisyos.fabric.SourceSelectionTrace",
        "fabric_retrieval_trace",
    ),
    "foundry_method_report": _runtime_quality_owner_contract(
        "foundry_method_report",
        "foundry_method_report_ref",
        "foundry.method_quality_report",
        "polisyos.foundry.MethodQualityReport",
        "foundry_method_report",
    ),
    "policy_grounding_matrix": _runtime_quality_owner_contract(
        "policy_grounding_matrix",
        "policy_grounding_matrix_ref",
        "scientist.policy_grounding_matrix",
        "polisyos.scientist.PolicyGroundingMatrix",
        "policy_grounding_matrix",
    ),
    "semantic_binding_ledger": _runtime_quality_owner_contract(
        "semantic_binding_ledger",
        "semantic_binding_ledger_ref",
        "runtime.semantic_binding_ledger",
        "polisyos.runtime.SemanticBindingLedger",
        "semantic_binding",
    ),
    "conflict_check": _runtime_quality_owner_contract(
        "conflict_check",
        "conflict_check_ref",
        "lex.policy_conflict_check",
        "polisyos.lex.PolicyConflictCheck",
        "conflict_check",
    ),
    "causal_statistical_validity": _runtime_quality_owner_contract(
        "causal_statistical_validity",
        "causal_statistical_validity_report_ref",
        "foundry.causal_statistical_validity_report",
        "polisyos.foundry.CausalStatisticalValidityReport",
        "causal_statistical_validity",
    ),
    "replay_manifest": _runtime_quality_owner_contract(
        "replay_manifest",
        "replay_manifest_ref",
        "runtime.replay_manifest",
        "polisyos.runtime.ReplayManifest",
        "deterministic_replay",
    ),
    "drift_explanation": _runtime_quality_owner_contract(
        "drift_explanation",
        "drift_explanation_ref",
        "runtime.drift_explanation",
        "polisyos.runtime.DriftExplanation",
        "deterministic_replay",
    ),
    "resilience_matrix": _runtime_quality_owner_contract(
        "resilience_matrix",
        "resilience_report_ref",
        "runtime.resilience_matrix",
        "polisyos.runtime.ResilienceMatrix",
        "resilience_report",
    ),
    "human_review_calibration": _runtime_quality_owner_contract(
        "human_review_calibration",
        "human_review_calibration_report_ref",
        "runtime.human_review_calibration_report",
        "polisyos.runtime.HumanReviewCalibrationReport",
        "human_review_calibration",
    ),
    "decision_artifact_quality": _runtime_quality_owner_contract(
        "decision_artifact_quality",
        "decision_artifact_quality_report_ref",
        "scientist.decision_artifact_quality_report",
        "polisyos.scientist.DecisionArtifactQualityReport",
        "decision_artifact_quality",
    ),
    "provider_model_quality_ledger": _runtime_quality_owner_contract(
        "provider_model_quality_ledger",
        "provider_model_quality_ledger_ref",
        "runtime.provider_model_quality_ledger",
        "polisyos.runtime.ProviderModelQualityLedger",
        "provider_model_quality",
    ),
    "privacy_compliance_report": _runtime_quality_owner_contract(
        "privacy_compliance_report",
        "privacy_compliance_report_ref",
        "runtime.privacy_compliance_report",
        "polisyos.runtime.PrivacyComplianceReport",
        "privacy_compliance_report",
    ),
    "security_assurance_report": _runtime_quality_owner_contract(
        "security_assurance_report",
        "security_assurance_report_ref",
        "runtime.security_assurance_report",
        "polisyos.runtime.SecurityAssuranceReport",
        "security_assurance_report",
    ),
}


def runtime_quality_report_owner_contract(
    report_key: str,
    ref_key: str | None = None,
) -> RuntimeQualityReportOwnerContract | None:
    """Return the exact registered producer identity for a report/ref pair."""
    contract = RUNTIME_QUALITY_REPORT_OWNER_CONTRACTS.get(report_key)
    if contract is None:
        return None
    if QUALITY_REPORT_RUNTIME_REFS.get(report_key) != contract.ref_key:
        return None
    if ref_key is not None and ref_key != contract.ref_key:
        return None
    return contract


def runtime_quality_report_owner_identity_issues(
    *,
    report_key: str,
    ref_key: str,
    artifact_kind: object,
    schema_name: object,
    schema_version: object,
    phase: object,
    media_type: object,
    producer_component: object,
    producer_version: object,
) -> tuple[str, ...]:
    """Compare a publisher identity with its exact shared owner contract."""
    contract = runtime_quality_report_owner_contract(report_key, ref_key)
    if contract is None:
        return ("owner_contract_not_established",)
    expected = {
        "artifact_kind": contract.artifact_kind,
        "schema_name": contract.schema_name,
        "schema_version": contract.schema_version,
        "phase": contract.phase,
        "media_type": contract.media_type,
        "producer_component": contract.producer_component,
        "producer_version": contract.producer_version,
    }
    observed = {
        "artifact_kind": artifact_kind,
        "schema_name": schema_name,
        "schema_version": schema_version,
        "phase": phase,
        "media_type": media_type,
        "producer_component": producer_component,
        "producer_version": producer_version,
    }
    return tuple(
        name
        for name, value in expected.items()
        if type(observed[name]) is not str or observed[name] != value
    )


def runtime_quality_report_owner_marker(
    report_key: str,
    ref_key: str,
) -> dict[str, object] | None:
    """Return the exact payload marker for a registered runtime report owner."""
    if runtime_quality_report_owner_contract(report_key, ref_key) is None:
        return None
    return {
        "schema_version": RUNTIME_QUALITY_OWNER_MARKER_SCHEMA,
        "report_key": report_key,
        "ref_key": ref_key,
        "projection": False,
    }


_RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY = "runtime_quality_publication_basis"
_RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_SCHEMA = (
    "polisyos.runtime.quality_report_publication_basis.v1"
)


@dataclass(frozen=True, slots=True)
class _RuntimeQualityReportPublicationBasis:
    """Complete publisher input and selected bindings for one returned report view."""

    report_key: str
    ref_key: str
    report_payload: dict[str, object]
    artifact_ref: dict[str, object]
    runtime_event_ref: str
    runtime_event_manifest_profile_sha256: str
    authority_envelope_ref: str
    authority_envelope: dict[str, object]
    manifest_ref: str
    payload_sha256: str

    def as_payload(self) -> dict[str, object]:
        """Return the strict wire-shaped basis carried beside the compatibility view."""
        return {
            "schema_version": _RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_SCHEMA,
            "report_key": self.report_key,
            "ref_key": self.ref_key,
            "report_payload": dict(self.report_payload),
            "publication": {
                "artifact_ref": dict(self.artifact_ref),
                "runtime_event_ref": self.runtime_event_ref,
                "runtime_event_manifest_profile_sha256": (
                    self.runtime_event_manifest_profile_sha256
                ),
                "authority_envelope_ref": self.authority_envelope_ref,
                "authority_envelope": dict(self.authority_envelope),
                "manifest_ref": self.manifest_ref,
                "payload_sha256": self.payload_sha256,
            },
        }


def _runtime_quality_report_writer_payload(
    report_payload: Mapping[str, object],
    *,
    report_key: str,
    ref_key: str,
) -> dict[str, object]:
    """Derive the exact CAS payload while preserving every producer input field."""
    marker = runtime_quality_report_owner_marker(report_key, ref_key)
    if marker is None:
        raise ValueError("runtime_quality_owner_contract_not_established")
    if _RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY in report_payload:
        raise ValueError("runtime_quality_publication_basis_is_publisher_owned")
    if any(type(key) is not str for key in report_payload):
        raise ValueError("runtime_quality_report_payload_key_invalid")
    payload = dict(report_payload)
    if "runtime_authority_payload" in payload and payload["runtime_authority_payload"] != marker:
        raise ValueError("runtime_quality_owner_payload_marker_mismatch")
    payload.setdefault("runtime_authority_payload", marker)
    return payload


def _build_runtime_quality_report_publication_basis(
    *,
    report_key: str,
    ref_key: str,
    report_payload: Mapping[str, object],
    artifact_ref: Mapping[str, object],
    runtime_event_ref: str,
    runtime_event_manifest_profile_sha256: str,
    authority_envelope_ref: str,
    authority_envelope: Mapping[str, object],
    manifest_ref: str,
    payload_sha256: str,
) -> _RuntimeQualityReportPublicationBasis:
    """Build the publisher-owned basis after the selected CAS write has succeeded."""
    if runtime_quality_report_owner_contract(report_key, ref_key) is None:
        raise ValueError("runtime_quality_owner_contract_not_established")
    _runtime_quality_report_writer_payload(
        report_payload,
        report_key=report_key,
        ref_key=ref_key,
    )
    if any(type(key) is not str for key in report_payload):
        raise ValueError("runtime_quality_report_payload_key_invalid")
    if any(type(key) is not str for key in artifact_ref):
        raise ValueError("runtime_quality_artifact_ref_key_invalid")
    if any(type(key) is not str for key in authority_envelope):
        raise ValueError("runtime_quality_authority_envelope_key_invalid")
    copied_ref = dict(artifact_ref)
    copied_envelope = dict(authority_envelope)
    required_ref_fields = ("artifact_id", "manifest_profile_sha256", "kind", "media_type")
    if any(
        type(copied_ref.get(name)) is not str or not copied_ref[name]
        for name in required_ref_fields
    ):
        raise ValueError("runtime_quality_selected_artifact_ref_incomplete")
    required_text = (
        runtime_event_ref,
        runtime_event_manifest_profile_sha256,
        authority_envelope_ref,
        manifest_ref,
        payload_sha256,
    )
    if any(type(value) is not str or not value for value in required_text):
        raise ValueError("runtime_quality_publication_binding_incomplete")
    return _RuntimeQualityReportPublicationBasis(
        report_key=report_key,
        ref_key=ref_key,
        report_payload=dict(report_payload),
        artifact_ref=copied_ref,
        runtime_event_ref=runtime_event_ref,
        runtime_event_manifest_profile_sha256=runtime_event_manifest_profile_sha256,
        authority_envelope_ref=authority_envelope_ref,
        authority_envelope=copied_envelope,
        manifest_ref=manifest_ref,
        payload_sha256=payload_sha256,
    )


def _parse_runtime_quality_report_publication_basis(
    value: object,
    *,
    expected_report_key: str,
    expected_ref_key: str,
) -> _RuntimeQualityReportPublicationBasis | None:
    """Parse only the exact publisher-owned publication basis shape."""
    if type(value) is not dict or set(value) != {
        "schema_version",
        "report_key",
        "ref_key",
        "report_payload",
        "publication",
    }:
        return None
    if (
        value.get("schema_version") != _RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_SCHEMA
        or type(value.get("report_key")) is not str
        or value.get("report_key") != expected_report_key
        or type(value.get("ref_key")) is not str
        or value.get("ref_key") != expected_ref_key
        or runtime_quality_report_owner_contract(expected_report_key, expected_ref_key) is None
    ):
        return None
    report_payload = value.get("report_payload")
    publication = value.get("publication")
    if (
        type(report_payload) is not dict
        or any(type(key) is not str for key in report_payload)
        or _RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY in report_payload
        or type(publication) is not dict
        or set(publication)
        != {
            "artifact_ref",
            "runtime_event_ref",
            "runtime_event_manifest_profile_sha256",
            "authority_envelope_ref",
            "authority_envelope",
            "manifest_ref",
            "payload_sha256",
        }
    ):
        return None
    artifact_ref = publication.get("artifact_ref")
    authority_envelope = publication.get("authority_envelope")
    if (
        type(artifact_ref) is not dict
        or any(type(key) is not str for key in artifact_ref)
        or type(authority_envelope) is not dict
        or any(type(key) is not str for key in authority_envelope)
    ):
        return None
    ref_fields = ("artifact_id", "manifest_profile_sha256", "kind", "media_type")
    if any(
        type(artifact_ref.get(name)) is not str or not artifact_ref[name] for name in ref_fields
    ):
        return None
    text_fields = (
        "runtime_event_ref",
        "runtime_event_manifest_profile_sha256",
        "authority_envelope_ref",
        "manifest_ref",
        "payload_sha256",
    )
    if any(type(publication.get(name)) is not str or not publication[name] for name in text_fields):
        return None
    return _RuntimeQualityReportPublicationBasis(
        report_key=expected_report_key,
        ref_key=expected_ref_key,
        report_payload=cast("dict[str, object]", report_payload),
        artifact_ref=cast("dict[str, object]", artifact_ref),
        runtime_event_ref=cast("str", publication["runtime_event_ref"]),
        runtime_event_manifest_profile_sha256=cast(
            "str",
            publication["runtime_event_manifest_profile_sha256"],
        ),
        authority_envelope_ref=cast("str", publication["authority_envelope_ref"]),
        authority_envelope=cast("dict[str, object]", authority_envelope),
        manifest_ref=cast("str", publication["manifest_ref"]),
        payload_sha256=cast("str", publication["payload_sha256"]),
    )


def _runtime_quality_report_publication_view(
    basis: _RuntimeQualityReportPublicationBasis,
) -> dict[str, object]:
    """Project the full source report plus selected writer bindings for compatibility."""
    report = dict(basis.report_payload)
    artifact_id = basis.artifact_ref["artifact_id"]
    report[basis.ref_key] = artifact_id
    report["runtime_quality_artifact_refs"] = {
        basis.ref_key: dict(basis.artifact_ref),
    }
    report["runtime_event_ref"] = basis.runtime_event_ref
    report["runtime_event_manifest_profile_sha256"] = basis.runtime_event_manifest_profile_sha256
    report["authority_envelope_ref"] = basis.authority_envelope_ref
    report["authority_envelope"] = dict(basis.authority_envelope)
    report["manifest_ref"] = basis.manifest_ref
    report["payload_sha256"] = basis.payload_sha256
    report[_RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY] = basis.as_payload()
    return report


def _runtime_quality_report_source_payload(
    report_payload: Mapping[str, object],
    *,
    report_key: str,
    ref_key: str,
) -> tuple[dict[str, object], _RuntimeQualityReportPublicationBasis | None]:
    """Recover publisher input only from the exact complete compatibility view."""
    payload = dict(report_payload)
    if any(type(key) is not str for key in payload):
        raise ValueError("runtime_quality_report_payload_key_invalid")
    if _RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY not in payload:
        return payload, None
    basis = _parse_runtime_quality_report_publication_basis(
        payload[_RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY],
        expected_report_key=report_key,
        expected_ref_key=ref_key,
    )
    if basis is None:
        raise ValueError("runtime_quality_report_publication_basis_not_established")
    if payload != _runtime_quality_report_publication_view(basis):
        raise ValueError("runtime_quality_publication_view_mismatch")
    return dict(basis.report_payload), basis


def _runtime_quality_report_reuse_basis(
    report_payload: Mapping[str, object],
    *,
    current_publication_view: object,
    report_key: str,
    ref_key: str,
) -> _RuntimeQualityReportPublicationBasis | None:
    """Return an exact same-source publication candidate, never a lossy match.

    A supplied complete view can identify a candidate when a fresh consumer has
    no in-memory view. The selected CAS and current publisher identity remain
    independently verified by the caller before any reuse occurs.
    """
    if runtime_quality_report_owner_contract(report_key, ref_key) is None:
        return None
    source_payload, supplied_basis = _runtime_quality_report_source_payload(
        report_payload,
        report_key=report_key,
        ref_key=ref_key,
    )
    if not isinstance(current_publication_view, Mapping):
        if supplied_basis is None:
            return None
        try:
            supplied_bytes = to_canonical_bytes(
                dict(report_payload),
                CanonSpec(forbid_floats=False),
            )
            expected_bytes = to_canonical_bytes(
                _runtime_quality_report_publication_view(supplied_basis),
                CanonSpec(forbid_floats=False),
            )
        except Exception as exc:
            raise ValueError("runtime_quality_publication_view_not_canonical") from exc
        if supplied_bytes != expected_bytes:
            raise ValueError("runtime_quality_publication_view_mismatch")
        return supplied_basis
    current_source, current_basis = _runtime_quality_report_source_payload(
        current_publication_view,
        report_key=report_key,
        ref_key=ref_key,
    )
    if current_basis is None:
        if supplied_basis is not None:
            raise ValueError("runtime_quality_current_publication_not_established")
        return None
    if supplied_basis is not None:
        expected_view = _runtime_quality_report_publication_view(supplied_basis)
        try:
            supplied_bytes = to_canonical_bytes(
                dict(report_payload),
                CanonSpec(forbid_floats=False),
            )
            expected_bytes = to_canonical_bytes(
                expected_view,
                CanonSpec(forbid_floats=False),
            )
            current_bytes = to_canonical_bytes(
                dict(current_publication_view),
                CanonSpec(forbid_floats=False),
            )
        except Exception as exc:
            raise ValueError("runtime_quality_publication_view_not_canonical") from exc
        if supplied_bytes != expected_bytes or current_bytes != expected_bytes:
            raise ValueError("runtime_quality_publication_view_mismatch")
        if supplied_basis.artifact_ref != current_basis.artifact_ref:
            raise ValueError("runtime_quality_current_publication_changed")
        return supplied_basis
    try:
        supplied_writer_payload = _runtime_quality_report_writer_payload(
            source_payload,
            report_key=report_key,
            ref_key=ref_key,
        )
        current_writer_payload = _runtime_quality_report_writer_payload(
            current_source,
            report_key=report_key,
            ref_key=ref_key,
        )
        supplied_bytes = to_canonical_bytes(
            supplied_writer_payload,
            CanonSpec(forbid_floats=False),
        )
        current_bytes = to_canonical_bytes(
            current_writer_payload,
            CanonSpec(forbid_floats=False),
        )
    except Exception:
        return None
    return current_basis if supplied_bytes == current_bytes else None


def _runtime_quality_report_reuse_closure_matches(
    basis: _RuntimeQualityReportPublicationBasis,
    expected_closure: Mapping[str, object],
) -> bool:
    """Require the complete current closure to match the selected publication."""
    persisted_closure = basis.authority_envelope.get("same_input_closure")
    if not isinstance(persisted_closure, Mapping):
        return False
    try:
        expected_bytes = to_canonical_bytes(
            dict(expected_closure),
            CanonSpec(forbid_floats=False),
        )
        persisted_bytes = to_canonical_bytes(
            dict(persisted_closure),
            CanonSpec(forbid_floats=False),
        )
    except Exception:
        return False
    return expected_bytes == persisted_bytes


@dataclass(frozen=True)
class QualityReportBodyLocator:
    """One schema-owned report field that names a bundle path, not a CAS object."""

    report_key: str
    schema_version: str
    ref_key: str
    field_name: str
    value: str


QUALITY_REPORT_BODY_LOCATORS = (
    QualityReportBodyLocator(
        report_key="security_assurance_report",
        schema_version="policyos.security_assurance_report.v1",
        ref_key=QUALITY_REPORT_RUNTIME_REFS["security_assurance_report"],
        field_name="security_assurance_report_ref",
        value=f"quality_evidence/{QUALITY_REPORT_FILES['security_assurance_report']}",
    ),
)


def quality_report_body_locator_for_field(
    *,
    schema_version: object,
    ref_key: str,
    field_name: str,
) -> QualityReportBodyLocator | None:
    """Return a locator only for its registered schema, owner role, and field."""
    for locator in QUALITY_REPORT_BODY_LOCATORS:
        if (
            schema_version == locator.schema_version
            and ref_key == locator.ref_key
            and field_name == locator.field_name
            and QUALITY_REPORT_RUNTIME_REFS.get(locator.report_key) == locator.ref_key
        ):
            return locator
    return None


QUALITY_REF_HINTS = {
    "production_data_quality": "production_data_quality_report_ref",
    "production.data_quality": "production_data_quality_report_ref",
    "data_quality_report": "production_data_quality_report_ref",
    "normative_applicability": "normative_applicability_report_ref",
    "normative.applicability": "normative_applicability_report_ref",
    "applicability_report": "normative_applicability_report_ref",
    "fabric_retrieval_trace": "fabric_retrieval_trace_ref",
    "fabric.retrieval_trace": "fabric_retrieval_trace_ref",
    "retrieval_trace": "fabric_retrieval_trace_ref",
    "foundry_method_report": "foundry_method_report_ref",
    "foundry.method_report": "foundry_method_report_ref",
    "method_quality_report": "foundry_method_report_ref",
    "policy_grounding_matrix": "policy_grounding_matrix_ref",
    "policy.grounding_matrix": "policy_grounding_matrix_ref",
    "grounding_matrix": "policy_grounding_matrix_ref",
    "conflict_check": "conflict_check_ref",
    "policy_conflict_check": "conflict_check_ref",
    "security_assurance_report": "security_assurance_report_ref",
    "security.assurance_report": "security_assurance_report_ref",
    "continuous_governance_stale": "continuous_governance_stale_report_ref",
    "governance_lifecycle_stale": "continuous_governance_stale_report_ref",
    "continuous_governance_reissue": "continuous_governance_reissue_report_ref",
    "governance_lifecycle_reissue": "continuous_governance_reissue_report_ref",
    "continuous_governance_supersede": "continuous_governance_supersede_report_ref",
    "governance_lifecycle_supersede": "continuous_governance_supersede_report_ref",
    "continuous_governance_withdraw": "continuous_governance_withdraw_report_ref",
    "governance_lifecycle_withdraw": "continuous_governance_withdraw_report_ref",
}


QUALITY_REPORT_BODY_KEYS = frozenset(
    alias
    for report_key, filename in QUALITY_REPORT_FILES.items()
    for alias in (report_key, filename.removesuffix(".json"))
)


def _build_quality_report_intake_registry() -> tuple[tuple[str, ...], dict[str, str]]:
    """Build actual report-ref roles and aliases for registered report bodies."""
    ref_keys: set[str] = set(KNOWN_QUALITY_REF_KEYS)
    body_ref_keys: dict[str, str] = {}

    def add_alias(alias: str, ref_key: str) -> None:
        prior = body_ref_keys.get(alias)
        if prior is not None and prior != ref_key:
            raise ValueError(f"quality report body alias {alias!r} maps to multiple ref roles")
        body_ref_keys[alias] = ref_key

    for report_key, filename in QUALITY_REPORT_FILES.items():
        ref_key = QUALITY_REPORT_RUNTIME_REFS.get(report_key)
        if ref_key is None:
            continue
        add_alias(report_key, ref_key)
        add_alias(filename.removesuffix(".json"), ref_key)
    for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items():
        ref_keys.add(ref_key)
        add_alias(report_key, ref_key)
    for alias, ref_key in QUALITY_REF_HINTS.items():
        ref_keys.add(ref_key)
        add_alias(alias, ref_key)
    return tuple(sorted(ref_keys)), body_ref_keys


QUALITY_REPORT_REF_KEYS, QUALITY_REPORT_BODY_REF_KEYS = _build_quality_report_intake_registry()


def quality_report_ref_intake_registry() -> tuple[tuple[str, ...], dict[str, str]]:
    """Return canonical runtime-ref roles and report aliases with real owners.

    The registry identifies which supplied ref roles must be screened. Report-body
    names without a producer-owned runtime ref are listed separately in
    `QUALITY_REPORT_BODY_KEYS`; they do not acquire a synthetic ref role. This
    registry does not verify a reference or promote a report to evidence authority.
    """
    return QUALITY_REPORT_REF_KEYS, dict(QUALITY_REPORT_BODY_REF_KEYS)
