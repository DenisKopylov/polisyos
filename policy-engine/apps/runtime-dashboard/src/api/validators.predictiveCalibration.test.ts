import { createNullablePredictiveCalibrationResponseFixture as currentResponse } from "@/test/fixtures/predictiveCalibrationResponse";

import { predictiveCalibrationResponseSchema } from "./validators";

const n4Limitation =
  "s10://calibration/fail-closed/n4_outcome_target_binding_not_established";
const sourceLimitation =
  "s10://calibration/fail-closed/backtest_source_not_established";

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
            "polisyos.runtime.predictive_calibration_association.v6";
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
