import {
  createNullablePredictiveCalibrationResponseFixture as currentResponse,
  createObservedOutcomeLevelResponseFixture,
} from "@/test/fixtures/predictiveCalibrationResponse";

import { predictiveCalibrationResponseSchema } from "./validators";

const n4Limitation =
  "s10://calibration/fail-closed/n4_outcome_target_binding_not_established";
const sourceLimitation =
  "s10://calibration/fail-closed/backtest_source_not_established";

function intervalResponse() {
  const response = currentResponse();
  const association = response.association;
  return {
    ...response,
    association: {
      ...association,
      schema_version: "polisyos.runtime.predictive_calibration_association.v6",
      s10: {
        ...association.s10,
        interval_support: {
          bundle_ref: { ...association.uncertainty_bundle_ref },
          observed_source_ref: { ...association.observed_source_ref },
          method_fqn: "forecasting.univariate.exponential_smoothing@1.0.0",
          target_metric: "policy_outcome",
          estimand: "predictive_interval_coverage",
          nominal_coverage: 0.9,
          forecast_profile_member_ref: null,
          measurement_unit: null,
        },
      },
    },
  };
}

describe("predictive calibration v6 interval support", () => {
  it("reads selected interval support while measured coverage remains unavailable", () => {
    const response = intervalResponse();
    const parsed = predictiveCalibrationResponseSchema.parse(response);
    expect(parsed).toEqual(response);
    expect(parsed.association.observed_hit_rate).toBeNull();
    expect(parsed.association.s10.calibration_status).toBe("blocked");
    expect(parsed.association.s10.outcome_binding_status).toBe(
      "not_established",
    );
  });

  it("accepts source-limited v6 when no interval can be resolved", () => {
    const response = currentResponse();
    response.association.schema_version =
      "polisyos.runtime.predictive_calibration_association.v6";
    expect(predictiveCalibrationResponseSchema.parse(response)).toEqual(
      response,
    );
  });

  it("keeps the exact profile-backed measurement and rejects a sibling manifest with the same bytes", () => {
    const response = intervalResponse();
    const profile = {
      ...response.association.model_spec_ref,
      kind: "runtime.value_data_profile",
    };
    const member = {
      ...response.association.policy_spec_ref,
      kind: "runtime.forecast_profile_member",
    };
    Object.assign(response.association, {
      value_data_profile_ref: profile,
      forecast_profile_member_ref: member,
      profile_join_status: "joined_candidate",
    });
    const support = response.association.s10.interval_support;
    Object.assign(support, {
      forecast_profile_member_ref: { ...member },
      measurement_unit: "USD",
    });
    expect(predictiveCalibrationResponseSchema.parse(response)).toEqual(
      response,
    );
    Object.assign(support, {
      forecast_profile_member_ref: {
        ...member,
        manifest_profile_sha256: `sha256:${"c".repeat(64)}`,
      },
    });
    expect(
      predictiveCalibrationResponseSchema.safeParse(response).success,
    ).toBe(false);
    Object.assign(support, { forecast_profile_member_ref: null });
    expect(
      predictiveCalibrationResponseSchema.safeParse(response).success,
    ).toBe(false);
  });

  it.each([
    "foreign_bundle",
    "foreign_source_profile",
    "unit_without_member",
    "wrong_nominal",
    "wrong_method",
    "wrong_estimand",
    "historical_version",
    "historical_null_interval",
    "unknown_interval_authority",
    "missing_bundle_profile",
    "numeric_source_unavailable",
  ])("rejects %s on a limited interval", (corruption) => {
    const response = intervalResponse();
    const association = response.association;
    const support = association.s10.interval_support;
    switch (corruption) {
      case "foreign_bundle":
        support.bundle_ref.artifact_id = `sha256:${"c".repeat(64)}`;
        break;
      case "foreign_source_profile":
        support.observed_source_ref.manifest_profile_sha256 = `sha256:${"c".repeat(64)}`;
        break;
      case "unit_without_member":
        Object.assign(support, { measurement_unit: "USD" });
        break;
      case "wrong_nominal":
        support.nominal_coverage = 0.8;
        break;
      case "wrong_method":
        support.method_fqn = "forecasting.univariate.another_method@1.0.0";
        break;
      case "wrong_estimand":
        support.estimand = "causal_effect";
        break;
      case "historical_version":
        association.schema_version =
          "polisyos.runtime.predictive_calibration_association.v5";
        break;
      case "historical_null_interval":
        association.schema_version =
          "polisyos.runtime.predictive_calibration_association.v5";
        Object.assign(association.s10, { interval_support: null });
        break;
      case "unknown_interval_authority":
        Object.assign(support, { publication_authority: true });
        break;
      case "missing_bundle_profile":
        Reflect.deleteProperty(support.bundle_ref, "manifest_profile_sha256");
        break;
      case "numeric_source_unavailable":
        Object.assign(association, {
          observed_numerator: 3,
          observed_denominator: 4,
          observed_hit_rate: 0.75,
        });
        break;
    }
    expect(
      predictiveCalibrationResponseSchema.safeParse(response).success,
    ).toBe(false);
  });
});

describe("predictive calibration v5 wire contract", () => {
  it("accepts the nullable source-limited response with the complete S10 boundary", () => {
    const response = currentResponse();
    const parsed = predictiveCalibrationResponseSchema.parse(response);
    expect(parsed).toEqual(response);
    expect(parsed.association.observed_hit_rate).toBeNull();
    expect(parsed.association.s10.calibration_status).toBe("blocked");
  });

  it("accepts a complete numeric tuple when the source-unavailable reason is absent", () => {
    const response = currentResponse();
    Object.assign(response.association, {
      observed_numerator: 3,
      observed_denominator: 4,
      observed_hit_rate: 0.75,
      evidence_reason_codes: ["calibration_floor_not_met"],
    });
    response.association.s10.limitation_refs = [n4Limitation];
    const parsed = predictiveCalibrationResponseSchema.parse(response);
    expect(parsed.association.observed_hit_rate).toBe(0.75);
    expect(parsed.association.s10.forecast_tier).toBe("blocked");
  });

  it("accepts the real paired value-profile/member kinds and rejects a forged kind", () => {
    const response = currentResponse();
    Object.assign(response.association, {
      value_data_profile_ref: {
        ...response.association.model_spec_ref,
        kind: "runtime.value_data_profile",
      },
      forecast_profile_member_ref: {
        ...response.association.policy_spec_ref,
        kind: "runtime.forecast_profile_member",
      },
      profile_join_status: "joined_candidate",
    });
    expect(
      predictiveCalibrationResponseSchema.safeParse(response).success,
    ).toBe(true);
    Object.assign(response.association, {
      forecast_profile_member_ref: {
        ...response.association.policy_spec_ref,
        kind: "ir.policy_spec",
      },
    });
    expect(
      predictiveCalibrationResponseSchema.safeParse(response).success,
    ).toBe(false);
  });

  it("rejects a null tuple mislabeled as a historical association", () => {
    const response = currentResponse();
    response.association.schema_version =
      "polisyos.runtime.predictive_calibration_association.v4";
    expect(
      predictiveCalibrationResponseSchema.safeParse(response).success,
    ).toBe(false);
  });

  it.each([
    { label: "owner string locator", reference: "s10://calibration/fixture" },
    {
      label: "selected artifact view",
      reference: currentResponse().association.empirical_evidence_ref,
    },
  ])(
    "reads a $label as declared wire evidence without granting authority",
    ({ reference }) => {
      const response = currentResponse();
      Object.assign(response.association.s10.authority_boundary, {
        evidence_kind: "simulation",
        decision_grade: "advisory_admissible",
        evidence_basis: { calibration_refs: [reference] },
      });
      const parsed = predictiveCalibrationResponseSchema.parse(response);
      expect(parsed.association.assessment).toBe("limited");
      expect(parsed.association.authority_scope).toBe("predictive_only");
      expect(parsed.association.s10.outcome_binding_status).toBe(
        "not_established",
      );
    },
  );

  it.each([null, {}, "", " ", " padded ", { artifact_id: "sha256:missing" }])(
    "rejects malformed present calibration reference %j with declared markers intact",
    (reference) => {
      const response = currentResponse();
      Object.assign(response.association.s10.authority_boundary, {
        evidence_kind: "simulation",
        decision_grade: "advisory_admissible",
        evidence_basis: { calibration_refs: [reference] },
      });
      expect(response.association.assessment).toBe("limited");
      expect(
        predictiveCalibrationResponseSchema.safeParse(response).success,
      ).toBe(false);
    },
  );

  it.each(["v2", "v3", "v4"])(
    "preserves %s historical numeric diagnostics without converting them to v5",
    (version) => {
      const response = currentResponse();
      Object.assign(response.association, {
        schema_version: `polisyos.runtime.predictive_calibration_association.${version}`,
        observed_numerator: 3,
        observed_denominator: 4,
        observed_hit_rate: 0.75,
        evidence_reason_codes: ["calibration_floor_not_met"],
      });
      const parsed = predictiveCalibrationResponseSchema.parse(response);
      expect(parsed.association.schema_version.endsWith(version)).toBe(true);
      expect(parsed.association.assessment).toBe("limited");
    },
  );

  it.each([
    "mixed_tuple",
    "numeric_source_unavailable",
    "source_reason_removed",
    "source_ref_removed",
    "observed_s10_claim",
    "supported_owner",
    "n4_ref_removed",
    "denied_uses_mismatch",
    "authority_boundary_missing",
    "outcome_binding_missing",
    "profile_pair_incomplete",
    "unknown_s10_authority",
    "unknown_boundary_authority",
    "llm_authority_escalated",
    "nonfinite_observation",
    "unknown_version",
  ])(
    "rejects the %s corruption with candidate markers intact",
    (corruption) => {
      const response = currentResponse();
      switch (corruption) {
        case "mixed_tuple":
          response.association.observed_numerator = 0;
          break;
        case "numeric_source_unavailable":
          Object.assign(response.association, {
            observed_numerator: 3,
            observed_denominator: 4,
            observed_hit_rate: 0.75,
          });
          break;
        case "source_reason_removed":
          response.association.evidence_reason_codes = [];
          break;
        case "source_ref_removed":
          response.association.s10.limitation_refs = [n4Limitation];
          break;
        case "observed_s10_claim":
          response.association.s10.numerator = 0;
          break;
        case "supported_owner":
          response.association.owner_suitability = "supported";
          break;
        case "n4_ref_removed":
          response.association.s10.limitation_refs = [sourceLimitation];
          break;
        case "denied_uses_mismatch":
          response.association.s10.may_not_use_for = ["publication"];
          break;
        case "authority_boundary_missing":
          Reflect.deleteProperty(
            response.association.s10,
            "authority_boundary",
          );
          break;
        case "outcome_binding_missing":
          Reflect.deleteProperty(
            response.association.s10,
            "outcome_binding_status",
          );
          break;
        case "profile_pair_incomplete":
          Object.assign(response.association, {
            value_data_profile_ref: {
              ...response.association.model_spec_ref,
              kind: "runtime.value_data_profile",
            },
            profile_join_status: "joined_candidate",
          });
          break;
        case "unknown_s10_authority":
          Object.assign(response.association.s10, {
            publication_authority: true,
          });
          break;
        case "unknown_boundary_authority":
          Object.assign(response.association.s10.authority_boundary, {
            publication_authority: true,
          });
          break;
        case "llm_authority_escalated":
          response.association.s10.authority_boundary.source_authority =
            "llm_candidate";
          response.association.s10.authority_boundary.posture = "production";
          break;
        case "nonfinite_observation":
          response.association.observed_hit_rate = Number.NaN;
          break;
        case "unknown_version":
          response.association.schema_version =
            "polisyos.runtime.predictive_calibration_association.v8";
          break;
      }
      expect(response.association.assessment).toBe("limited");
      expect(response.association.authority_scope).toBe("predictive_only");
      expect(
        predictiveCalibrationResponseSchema.safeParse(response).success,
      ).toBe(false);
    },
  );
});

describe("selected observed outcome level", () => {
  it("retains exact scoped support and separate observed series coverage", () => {
    const value = createObservedOutcomeLevelResponseFixture();
    const parsed = predictiveCalibrationResponseSchema.parse(value);
    expect(parsed).toEqual(value);
    expect(parsed.association.s10.forecast_tier).toBe("blocked");
    expect(parsed.association.observed_hit_rate).toBeNull();
    expect(parsed.observed_outcome_level?.status).toBe("matched_candidate");
  });

  it("preserves the same candidate series and interval after losing only scope proof", () => {
    const warm = createObservedOutcomeLevelResponseFixture();
    const limited = predictiveCalibrationResponseSchema.parse({
      ...warm,
      observed_outcome_level: { status: "not_established" },
    });
    expect(limited.association).toEqual(warm.association);
    expect(limited.observed_outcome_level).toEqual({
      status: "not_established",
    });
  });

  it.each([
    "foreign_selected_relation",
    "wrong_series_metric",
    "gap_in_holdout",
    "unknown_issuer_claimed",
    "misstated_numeric_coverage",
    "v6_with_v7_scope",
    "support_under_refusal",
    "missing_v7_projection",
  ])("rejects %s with predictive markers intact", (fault) => {
    const value = createObservedOutcomeLevelResponseFixture();
    const support = value.observed_outcome_level.support;
    switch (fault) {
      case "foreign_selected_relation":
        support.relation_ref.manifest_profile_sha256 = `sha256:${"f".repeat(64)}`;
        break;
      case "wrong_series_metric":
        support.observed_target_metric = "fiscal.balance";
        break;
      case "gap_in_holdout":
        support.holdout_years = [2021, 2021, 2023, 2024];
        break;
      case "unknown_issuer_claimed":
        support.issuer_status = "established";
        break;
      case "misstated_numeric_coverage":
        value.association.s10.observed_series_coverage.holdout_coverage = 0.5;
        break;
      case "v6_with_v7_scope":
        value.association.schema_version =
          "polisyos.runtime.predictive_calibration_association.v6";
        break;
      case "support_under_refusal":
        value.observed_outcome_level.status = "not_established";
        break;
      case "missing_v7_projection":
        Reflect.deleteProperty(value, "observed_outcome_level");
        break;
    }
    expect(predictiveCalibrationResponseSchema.safeParse(value).success).toBe(
      false,
    );
  });
});
