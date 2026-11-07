export const predictiveCalibrationRunId = "R_candidate_001";

const selectedProfile = `sha256:${"a".repeat(64)}`;

const artifactRef = (digest: string, kind: string) => ({
  artifact_id: `sha256:${digest.repeat(64)}`,
  kind,
  media_type: "application/json",
  manifest_profile_sha256: selectedProfile,
});

export const predictiveCalibrationResponseFixture = {
  meta: {
    request_id: "req_fixture",
    generated_at: "2026-10-12T08:00:00Z",
    source_kinds: ["core_run"],
  },
  association_ref: artifactRef(
    "e",
    "runtime.predictive_calibration_association",
  ),
  association: {
    schema_version: "polisyos.runtime.predictive_calibration_association.v2",
    event_id: "evt_fixture",
    intent_id: "intent-fixture",
    request_sha256: "b".repeat(64),
    run_id: predictiveCalibrationRunId,
    control_run_id: "control-run-fixture",
    job_id: "job_fixture",
    tenant_id: "tenant_fixture",
    cell_id: "cell_fixture",
    run_manifest_ref: artifactRef("1", "core.run_manifest"),
    candidate_source_ref: artifactRef(
      "2",
      "runtime.quality.n4_candidate_scenario_source",
    ),
    observed_source_ref: artifactRef("3", "fabric.data_snapshot"),
    model_spec_ref: artifactRef("4", "ir.model_spec"),
    policy_spec_ref: artifactRef("5", "ir.policy_spec"),
    calibration_rule_ref: artifactRef("6", "ir.forecast_calibration_rule"),
    backtest_report_ref: artifactRef("7", "ir.backtest_report"),
    empirical_evidence_ref: artifactRef(
      "8",
      "ir.empirical_calibration_evidence",
    ),
    uncertainty_bundle_ref: artifactRef(
      "9",
      "ir.forecasting_uncertainty_bundle",
    ),
    assessment: "limited",
    authority_scope: "predictive_only",
    issuer_status: "not_established",
    source_time_status: "not_established",
    population_scope_status: "not_established",
    counterfactual_credibility_status: "not_established",
    observed_numerator: 3,
    observed_denominator: 4,
    observed_hit_rate: 0.75,
    nominal_confidence_level: 0.9,
    owner_suitability: "limited",
    s10: {
      calibration_status: "limit",
      forecast_tier: "limited_local_model",
      counterfactual_credibility: "not_established",
      numerator: 3,
      denominator: 4,
      observed_pass_rate: 0.75,
      calibration_record_ref: "s10://fixture/calibration",
    },
    evidence_reason_codes: ["calibration_floor_not_met"],
    may_not_use_for: [
      "promotion",
      "publication",
      "policy_selection",
      "causal_effect_claim",
    ],
    created_at: "2026-10-12T08:00:00Z",
  },
};

export function responseWithoutSelectedRunManifestProfile(): unknown {
  const response = structuredClone(predictiveCalibrationResponseFixture);
  delete (response.association.run_manifest_ref as Record<string, unknown>)
    .manifest_profile_sha256;
  return response;
}

export function responseWithUnknownAssociationAuthority(): unknown {
  const response = structuredClone(predictiveCalibrationResponseFixture);
  Object.assign(response.association, { publication_authority: "approved" });
  return response;
}

export function responseWithUnknownMetaAuthority(): unknown {
  const response = structuredClone(predictiveCalibrationResponseFixture);
  Object.assign(response.meta, { authority_scope: "causal" });
  return response;
}

export function createNullablePredictiveCalibrationResponseFixture() {
  const legacy = structuredClone(predictiveCalibrationResponseFixture);
  const deniedUses = [
    "promotion",
    "publication",
    "policy_selection",
    "causal_effect_claim",
    "production_claim_authority",
  ];
  return {
    ...legacy,
    association: {
      ...legacy.association,
      schema_version: "polisyos.runtime.predictive_calibration_association.v5",
      observed_numerator: null as number | null,
      observed_denominator: null as number | null,
      observed_hit_rate: null as number | null,
      value_data_profile_ref: null,
      forecast_profile_member_ref: null,
      profile_join_status: "profileless_legacy",
      evidence_reason_codes: ["backtest_source_not_established"],
      may_not_use_for: [...deniedUses],
      s10: {
        ...legacy.association.s10,
        calibration_status: "blocked",
        forecast_tier: "blocked",
        numerator: null as number | null,
        denominator: null as number | null,
        observed_pass_rate: null as number | null,
        calibration_record_ref: null as string | null,
        outcome_binding_status: "not_established",
        limitation_refs: [
          "s10://calibration/fail-closed/n4_outcome_target_binding_not_established",
          "s10://calibration/fail-closed/backtest_source_not_established",
        ],
        authority_boundary: {
          boundary_id: null,
          authoritative_for: [
            "forecast_support_tiering",
            "observable_subset_calibration",
          ],
          may_not_use_for: [...deniedUses],
          source_authority: "deterministic_producer",
          posture: "shadow",
          rule_version_refs: ["policyos.layer2.s10.outcome_prediction.v1"],
          evidence_kind: null,
          decision_grade: null,
          evidence_basis: null,
          known_limits: [],
        },
        may_not_use_for: [...deniedUses],
      },
    },
  };
}
