import type { components } from "@/api/types";

export const humanDecisionDigest = (character: string) =>
  `sha256:${character.repeat(64)}`;

export const humanDecisionSourceRef = humanDecisionDigest("a");
export const humanDecisionEvidenceDigest = humanDecisionDigest("9");

export function producerMissingHumanDecisionGate(
  overrides: Partial<components["schemas"]["HumanDecisionGateResponse"]> = {},
): components["schemas"]["HumanDecisionGateResponse"] {
  return {
    contestability: null,
    continuation: null,
    decision_request: null,
    decision_request_digest: null,
    decision_request_ref: null,
    exposure: {
      channel: null,
      completed_artifact_digests: [],
      exposure_session_ref: null,
      renderer_id: null,
      renderer_version: null,
      representation: null,
      required_artifact_digests: [],
    },
    governed_action_key: null,
    mandate: null,
    operational_authority: false,
    reason_codes: ["DS9-DECISION-PRODUCER-MISSING"],
    reasons: [
      {
        code: "DS9-DECISION-PRODUCER-MISSING",
        message: "The deployment human-decision producer is unavailable.",
        status: "producer_missing",
      },
    ],
    resolved_at: "2026-08-24T12:00:00Z",
    run_id: "run-1",
    source_kind: "agent_action_authority",
    source_ref: humanDecisionSourceRef,
    status: "producer_missing",
    submission: null,
    tenant_id: "tenant-fixture",
    verifier_epoch: "producer-missing",
    ...overrides,
  };
}

export function availableHumanDecisionGate(
  overrides: Partial<components["schemas"]["HumanDecisionGateResponse"]> = {},
): components["schemas"]["HumanDecisionGateResponse"] {
  const selector = {
    action_kind: "data_request",
    basis_digest: humanDecisionDigest("b"),
    basis_ref: humanDecisionDigest("b"),
    decision_request_digest: humanDecisionDigest("c"),
    decision_request_ref: humanDecisionDigest("c"),
    exposure_session_ref: humanDecisionDigest("1"),
    operational_authority: false,
    presentation_contract_ref: humanDecisionDigest("f"),
    principal_binding_ref: humanDecisionDigest("d"),
    reviewer_separation_ref: humanDecisionDigest("e"),
    source_kind: "agent_action_authority",
    source_ref: humanDecisionSourceRef,
  } as const satisfies components["schemas"]["HumanDecisionPA2ReplaySelector"];
  return {
    contestability: {
      case_id: "case.fixture",
      href:
        "/runs/run-1/case?appeal_case_id=case.fixture" +
        `&source_kind=agent_action_authority&source_ref=${encodeURIComponent(humanDecisionSourceRef)}`,
      source_ref: humanDecisionSourceRef,
    },
    continuation: selector,
    decision_request: {
      available_actions: ["approve", "reject", "request_evidence"],
      case_id: "case.fixture",
      decidable_until: "2026-08-24T12:30:00Z",
      decision_due_at: "2026-08-24T12:20:00Z",
      decision_rights_matrix_ref: "pdc://s7/rights",
      delegation_contract_ref: "pdc://s7/contract",
      five_rights_binding: {
        decision_class_id: "data_request",
        decision_rights_matrix_ref: "pdc://s7/rights",
        required_channel: "reviewer_console",
        required_information_refs: [humanDecisionEvidenceDigest],
        required_representation: "full",
        required_role: "data_steward",
        schema_version: "policyos.policy_design_case.layer2_s7_delegation.v2",
        time_rule: "intersection_of_signed_validity_intervals_pre_action",
      },
      five_rights_requirements: {
        right_decision: "data_request",
        right_format_channel: "reviewer_console",
        right_information: "evidence://opened",
        right_person: "data_steward",
        right_time: "before TTL",
        schema_version: "policyos.policy_design_case.layer2_s7_delegation.v1",
      },
      requested_at: "2026-08-24T12:00:00Z",
      required_role: "data_steward",
    },
    decision_request_digest: selector.decision_request_digest,
    decision_request_ref: selector.decision_request_ref,
    exposure: {
      channel: "reviewer_console",
      completed_artifact_digests: [
        selector.basis_digest,
        humanDecisionEvidenceDigest,
      ],
      exposure_session_ref: selector.exposure_session_ref,
      renderer_id: "atlas-human-decision-gate",
      renderer_version: "1",
      representation: "full",
      required_artifact_digests: [
        selector.basis_digest,
        humanDecisionEvidenceDigest,
      ],
    },
    governed_action_key: humanDecisionDigest("7"),
    mandate: {
      action_kind: "data_request",
      mandate_owner_ref: "actor://mandate-owner",
      mandate_record_ref: "mandate://fixture",
      operation_id: "data_request",
      valid_from: "2026-08-24T11:30:00Z",
      valid_until: "2026-08-24T12:30:00Z",
    },
    operational_authority: false,
    reason_codes: [],
    reasons: [],
    resolved_at: "2026-08-24T12:00:00Z",
    run_id: "run-1",
    source_kind: "agent_action_authority",
    source_ref: humanDecisionSourceRef,
    status: "available",
    submission: {
      allowed_decisions: [
        { action: "approve", decision_modes: ["ordinary", "override"] },
        { action: "reject", decision_modes: ["blocking"] },
        { action: "request_evidence", decision_modes: ["ordinary"] },
      ],
      operational_authority: false,
      selector,
    },
    tenant_id: "tenant-fixture",
    verifier_epoch: "verifier-epoch-fixture",
    ...overrides,
  };
}

export function humanDecisionReviewEffectivenessFixture(
  overrides: Partial<
    components["schemas"]["HumanDecisionReviewEffectivenessResponse"]
  > = {},
): components["schemas"]["HumanDecisionReviewEffectivenessResponse"] {
  return {
    advisory_signal_codes: ["human_decision_review_coverage_incomplete"],
    approval_count: 0,
    audit_predicate_provenance: "institutionally_supplied",
    audit_read_error_count: 0,
    authoritative_for: [
      "review_effectiveness_measurement",
      "future_policy_calibration",
      "reviewer_load_observability",
    ],
    authorization_allow_count: 2,
    blocking_count: 0,
    blocking_permitted: false,
    candidate_human_decision_count: 2,
    completed_human_decision_count: 0,
    coverage_claim_scope: "retained_trail_bytes_only",
    coverage_status: "incomplete",
    dissent_count: 0,
    duplicate_authorization_request_count: 0,
    duplicate_record_event_count: 0,
    duplicate_record_request_count: 0,
    exact_join_count: 0,
    invalid_authorization_event_count: 0,
    invalid_record_event_count: 0,
    malformed_json_line_count: 0,
    may_not_use_for: [
      "current_run_closeout_block",
      "publication_block",
      "claim_support_downgrade",
      "authorization_writer_provenance",
      "forensic_tamper_detection",
    ],
    measurement_status: "partial",
    nonblank_line_count: 2,
    nonobject_line_count: 0,
    override_count: 0,
    parsed_object_count: 2,
    report_status_effect: "pass_advisory_only",
    retained_or_missing_record_count: 2,
    review_count: 0,
    review_posture: "advisory",
    review_time_established_count: 0,
    review_time_not_established_count: 0,
    review_time_status: "not_established",
    reviewer_independence_rate: null,
    run_id: "run-1",
    schema_version: "policyos.runtime.human_decision_review_effectiveness.v1",
    separation_of_duty_attestation_rate: null,
    tenant_scope_unknown_record_event_count: 0,
    threshold_scope: "established_signals_only",
    threshold_status: "fail",
    trail_path_exists: true,
    unmatched_authorization_count: 2,
    unmatched_record_event_count: 0,
    ...overrides,
  };
}
