import {
  intervalSummary,
  legacyLimitedProjection,
  legacyUnavailableProjection,
  pointSummary,
  refusalSummary,
  hteRef,
} from "./__test__/decisionPacketHteFixtures";
import { parseDecisionPacketHTEProjection } from "./decisionPacketHte";

function parseLegacyProjectionForTest(legacy: Record<string, unknown>) {
  return parseDecisionPacketHTEProjection({
    hte_projection_status: "legacy_limited",
    hte: null,
    hte_legacy_limited: legacy,
  });
}

describe("parseDecisionPacketHTEProjection", () => {
  it("distinguishes absent HTE from present malformed data without reading accessors", () => {
    expect(parseDecisionPacketHTEProjection({})).toEqual({ status: "absent" });
    expect(parseDecisionPacketHTEProjection({ hte: null })).toEqual({
      status: "invalid",
    });

    const accessorPayload = {};
    Object.defineProperty(accessorPayload, "hte", {
      enumerable: true,
      get() {
        throw new Error("The preview parser must not evaluate getters.");
      },
    });
    expect(parseDecisionPacketHTEProjection(accessorPayload)).toEqual({
      status: "invalid",
    });
  });

  it("rejects array index accessors without evaluating them", () => {
    const summary = pointSummary();
    const limitations = summary.limitations as string[];
    let indexReads = 0;
    Object.defineProperty(limitations, "0", {
      enumerable: true,
      get() {
        indexReads += 1;
        return "must not be observed";
      },
    });

    const parsed = parseDecisionPacketHTEProjection({ hte: summary });
    expect(indexReads).toBe(0);
    expect(parsed).toEqual({ status: "invalid" });
  });

  it("rejects custom array methods without invoking their getters or functions", () => {
    const summary = pointSummary();
    const limitations = summary.limitations as string[];
    let everyReads = 0;
    let mapReads = 0;
    Object.defineProperty(limitations, "every", {
      configurable: true,
      get() {
        everyReads += 1;
        return () => true;
      },
    });
    Object.defineProperty(limitations, "map", {
      configurable: true,
      value() {
        mapReads += 1;
        return [];
      },
    });

    const parsed = parseDecisionPacketHTEProjection({ hte: summary });
    expect(everyReads).toBe(0);
    expect(mapReads).toBe(0);
    expect(parsed).toEqual({ status: "invalid" });
  });

  it("rejects sparse arrays instead of accepting skipped entries", () => {
    const summary = pointSummary();
    summary.limitations = new Array(1) as string[];

    expect(parseDecisionPacketHTEProjection({ hte: summary })).toEqual({
      status: "invalid",
    });
  });

  it("rejects inherited numeric keys on the standard array prototype chain", () => {
    const summary = pointSummary();
    let inheritedReads = 0;
    const inheritedIndex = "4294967294";
    Object.defineProperty(Array.prototype, inheritedIndex, {
      configurable: true,
      get() {
        inheritedReads += 1;
        return "must not be observed";
      },
    });

    let parsed: ReturnType<typeof parseDecisionPacketHTEProjection> | undefined;
    try {
      parsed = parseDecisionPacketHTEProjection({ hte: summary });
    } finally {
      Reflect.deleteProperty(Array.prototype, inheritedIndex);
    }

    expect(inheritedReads).toBe(0);
    expect(parsed).toEqual({ status: "invalid" });
  });

  it("parses the strict scalar point branch and never reads a CATE vector", () => {
    const parsed = parseDecisionPacketHTEProjection({ hte: pointSummary() });
    expect(parsed.status).toBe("valid");
    if (parsed.status !== "valid") {
      throw new Error("Expected a valid point projection.");
    }
    expect(parsed.outcome.kind).toBe("point_estimate");
    if (parsed.outcome.kind !== "point_estimate") {
      throw new Error("Expected the point-estimate outcome branch.");
    }
    expect(parsed.outcome.point_estimate).toBe(0.25);
    expect(parsed.outcome.point_result_ref.kind).toBe("ir.hte_point_result");
    expect(parsed.outcome.target_relation.overall_disposition).toBe(
      "not_established",
    );

    const withRows = pointSummary();
    Object.defineProperty(withRows, "cate_values", {
      enumerable: true,
      get() {
        throw new Error("The bounded projection read per-row CATE output.");
      },
    });
    expect(parseDecisionPacketHTEProjection({ hte: withRows })).toEqual({
      status: "invalid",
    });
  });

  it("rejects a population request that the selected-row result does not satisfy while preserving the point", () => {
    const requestedPopulation = pointSummary();
    requestedPopulation.request_estimand =
      "population_average_treatment_effect";
    requestedPopulation.request_target_scope = "population";
    requestedPopulation.target_relation = {
      ...(requestedPopulation.target_relation as Record<string, unknown>),
      requested_scope: "population",
      scope_disposition: "requested_claim_not_satisfied",
      overall_disposition: "requested_claim_not_satisfied",
    };
    const parsed = parseDecisionPacketHTEProjection({
      hte: requestedPopulation,
    });
    expect(parsed.status).toBe("valid");
    if (parsed.status !== "valid") {
      throw new Error("Expected a valid requested-scope projection.");
    }
    if (parsed.outcome.kind !== "point_estimate") {
      throw new Error("Expected the point-estimate outcome branch.");
    }
    expect(parsed.outcome.point_estimate).toBe(0.25);
    expect(parsed.outcome.target_relation.overall_disposition).toBe(
      "requested_claim_not_satisfied",
    );
  });

  it("parses only a native conditional interval with paired typed refs", () => {
    const parsed = parseDecisionPacketHTEProjection({ hte: intervalSummary() });
    expect(parsed.status).toBe("valid");
    if (parsed.status !== "valid") {
      throw new Error("Expected a valid native interval projection.");
    }
    expect(parsed.outcome.kind).toBe("interval_estimate");
    if (parsed.outcome.kind !== "interval_estimate") {
      throw new Error("Expected the interval-estimate outcome branch.");
    }
    expect(parsed.outcome.lower_bound).toBe(0.12);
    expect(parsed.outcome.upper_bound).toBe(0.72);
    expect(parsed.outcome.point_result_ref).toBeNull();
    expect(parsed.outcome.hte_result_ref.kind).toBe("ir.hte_result");
    expect(parsed.outcome.inference_basis_ref.kind).toBe(
      "ir.ate_inference_basis",
    );

    const wrongHteRef = intervalSummary();
    wrongHteRef.hte_result_ref = hteRef("7", "ir.hte_point_result");
    expect(parseDecisionPacketHTEProjection({ hte: wrongHteRef })).toEqual({
      status: "invalid",
    });

    const unpaired = intervalSummary();
    unpaired.inference_basis_ref = null;
    expect(parseDecisionPacketHTEProjection({ hte: unpaired })).toEqual({
      status: "invalid",
    });
  });

  it("rejects legacy result refs and raw arrays even if summary markers remain", () => {
    const legacyRef = pointSummary();
    delete legacyRef.point_result_ref;
    legacyRef.hte_result_ref = hteRef("6", "ir.hte_result");
    expect(parseDecisionPacketHTEProjection({ hte: legacyRef })).toEqual({
      status: "invalid",
    });

    const inlineNative = intervalSummary();
    inlineNative.native_mean_result = { lower_bound: 0.12, upper_bound: 0.72 };
    expect(parseDecisionPacketHTEProjection({ hte: inlineNative })).toEqual({
      status: "invalid",
    });
  });

  it("keeps typed refusal free of numerical and result fields, with a diagnostic ref", () => {
    const parsed = parseDecisionPacketHTEProjection({ hte: refusalSummary() });
    expect(parsed.status).toBe("valid");
    if (parsed.status !== "valid") {
      throw new Error("Expected a valid typed refusal projection.");
    }
    expect(parsed.outcome.kind).toBe("refusal");
    if (parsed.outcome.kind !== "refusal") {
      throw new Error("Expected the refusal outcome branch.");
    }
    expect(parsed.outcome.refusal_reason).toBe("method_execution_failed");
    expect(parsed.outcome.refusal_diagnostic_ref.kind).toBe(
      "ir.hte_refusal_diagnostic",
    );

    const falsePoint = refusalSummary();
    falsePoint.point_estimate = 0.42;
    expect(parseDecisionPacketHTEProjection({ hte: falsePoint })).toEqual({
      status: "invalid",
    });

    const wrongDiagnostic = refusalSummary();
    wrongDiagnostic.refusal_diagnostic_ref = hteRef("b", "ir.hte_point_result");
    expect(parseDecisionPacketHTEProjection({ hte: wrongDiagnostic })).toEqual({
      status: "invalid",
    });
  });

  it("recomputes target dispositions and rejects a form-only satisfied claim", () => {
    const inconsistent = pointSummary();
    inconsistent.target_relation = {
      ...(inconsistent.target_relation as Record<string, unknown>),
      source_content_status: "not_established",
    };
    expect(parseDecisionPacketHTEProjection({ hte: inconsistent })).toEqual({
      status: "invalid",
    });
  });

  it("rejects mismatched estimator entry and exit resource evidence", () => {
    const resourceDrift = pointSummary();
    resourceDrift.resource_evidence = {
      ...(resourceDrift.resource_evidence as Record<string, unknown>),
      estimator_after_n_jobs: 2,
    };
    expect(parseDecisionPacketHTEProjection({ hte: resourceDrift })).toEqual({
      status: "invalid",
    });
  });

  it("requires a source profile and computed estimand status in the frozen shape", () => {
    const missingSource = pointSummary();
    missingSource.source_data_ref = hteRef("5", "datasets.policy-input");
    (
      missingSource.source_data_ref as Record<string, unknown>
    ).manifest_profile_sha256 = null;
    expect(parseDecisionPacketHTEProjection({ hte: missingSource })).toEqual({
      status: "invalid",
    });

    const missingStatus = pointSummary();
    delete missingStatus.computed_estimand_status;
    expect(parseDecisionPacketHTEProjection({ hte: missingStatus })).toEqual({
      status: "invalid",
    });
  });

  it("accepts only the typed limited legacy sidecar and refuses mixed modern fields", () => {
    const legacy = legacyLimitedProjection();
    const parsed = parseDecisionPacketHTEProjection({
      hte_projection_status: "legacy_limited",
      hte: null,
      hte_legacy_limited: legacy,
    });
    expect(parsed.status).toBe("valid");
    if (parsed.status !== "valid") {
      throw new Error("Expected a valid typed legacy projection.");
    }
    expect(parsed.outcome.kind).toBe("legacy_limited");
    if (parsed.outcome.kind !== "legacy_limited") {
      throw new Error("Expected the limited legacy branch.");
    }
    expect(parsed.outcome.ate).toBe(0.25);
    expect(parsed.outcome.population_coverage_status).toBe("not_established");

    expect(
      parseDecisionPacketHTEProjection({
        hte_projection_status: "legacy_limited",
        hte: pointSummary(),
        hte_legacy_limited: legacy,
      }),
    ).toEqual({ status: "invalid" });
  });
  it("matches the complete Python legacy DTO literal and text-length bounds", () => {
    const parseLegacy = (legacy: Record<string, unknown>) =>
      parseDecisionPacketHTEProjection({
        hte_projection_status: "legacy_limited",
        hte: null,
        hte_legacy_limited: legacy,
      });

    const upperBounds = legacyLimitedProjection();
    upperBounds.method = "m".repeat(128);
    const upperFeature = (
      upperBounds.top_features as Array<Record<string, unknown>>
    )[0];
    upperFeature.feature_name = "f".repeat(256);
    upperFeature.method = "m".repeat(128);
    upperBounds.warnings = ["w".repeat(512)];
    expect(parseLegacy(upperBounds).status).toBe("valid");

    const invalidLiteral = legacyLimitedProjection();
    (invalidLiteral.limitations as unknown[])[0] = "legacy_unknown";
    const tooFewLimitations = legacyLimitedProjection();
    tooFewLimitations.limitations = (
      tooFewLimitations.limitations as unknown[]
    ).slice(0, 4);
    const tooManyLimitations = legacyLimitedProjection();
    tooManyLimitations.limitations = [
      ...(tooManyLimitations.limitations as unknown[]),
      "legacy_source_reference_unprofiled",
    ];
    const longMethod = legacyLimitedProjection();
    longMethod.method = "m".repeat(129);
    const longFeatureName = legacyLimitedProjection();
    (
      longFeatureName.top_features as Array<Record<string, unknown>>
    )[0].feature_name = "f".repeat(257);
    const longFeatureMethod = legacyLimitedProjection();
    (
      longFeatureMethod.top_features as Array<Record<string, unknown>>
    )[0].method = "m".repeat(129);
    const longWarning = legacyLimitedProjection();
    longWarning.warnings = ["w".repeat(513)];

    for (const payload of [
      invalidLiteral,
      tooFewLimitations,
      tooManyLimitations,
      longMethod,
      longFeatureName,
      longFeatureMethod,
      longWarning,
    ]) {
      expect(parseLegacy(payload)).toEqual({ status: "invalid" });
    }
  });

  it("requires the explicit Python parse-failure reason for unavailable legacy data", () => {
    const missingReason = legacyUnavailableProjection();
    delete missingReason.parse_warning;
    expect(
      parseDecisionPacketHTEProjection({
        hte_projection_status: "legacy_limited",
        hte: null,
        hte_legacy_limited: missingReason,
      }),
    ).toEqual({ status: "invalid" });
  });

  it("accepts the empty unavailable DTO and preserves available warnings", () => {
    const unavailable = parseLegacyProjectionForTest(
      legacyUnavailableProjection() as Record<string, unknown>,
    );
    expect(unavailable.status).toBe("valid");

    const availableWire = legacyLimitedProjection() as Record<string, unknown>;
    availableWire.warnings = ["legacy source warning"];
    const available = parseLegacyProjectionForTest(availableWire);
    expect(available.status).toBe("valid");
    if (
      available.status !== "valid" ||
      available.outcome.kind !== "legacy_limited"
    ) {
      throw new Error("Expected the available legacy projection.");
    }
    expect(available.outcome.warnings).toEqual(["legacy source warning"]);
  });

  it.each([
    ["method", "legacy"],
    ["ate", 0.25],
    ["ate_ci_lower", -0.1],
    ["ate_ci_upper", 0.4],
    ["n_samples", 8],
    ["n_features", 3],
    ["n_subgroups", 2],
  ] as const)(
    "rejects unavailable legacy HTE when %s is populated",
    (field, populatedValue) => {
      const candidate = legacyUnavailableProjection() as Record<
        string,
        unknown
      >;
      candidate[field] = populatedValue;
      expect(parseLegacyProjectionForTest(candidate)).toEqual({
        status: "invalid",
      });
    },
  );

  it.each([
    ["method and sample count", { method: "legacy", n_samples: 8 }],
    ["effect and lower bound", { ate: 0.25, ate_ci_lower: -0.1 }],
    ["feature and subgroup counts", { n_features: 3, n_subgroups: 2 }],
  ] as const)(
    "rejects unavailable legacy HTE with mixed values: %s",
    (_caseName, populatedValues) => {
      const candidate = legacyUnavailableProjection() as Record<
        string,
        unknown
      >;
      Object.assign(candidate, populatedValues);
      expect(parseLegacyProjectionForTest(candidate)).toEqual({
        status: "invalid",
      });
    },
  );

  it.each([
    ["method", null],
    ["ate", null],
    ["ate_ci_lower", null],
    ["ate_ci_upper", null],
    ["n_samples", null],
    ["n_features", null],
    ["n_subgroups", null],
  ] as const)(
    "rejects available legacy HTE when required field %s is null",
    (field, missingValue) => {
      const candidate = legacyLimitedProjection() as Record<string, unknown>;
      candidate[field] = missingValue;
      expect(parseLegacyProjectionForTest(candidate)).toEqual({
        status: "invalid",
      });
    },
  );

  it("rejects an available legacy DTO with a parse warning", () => {
    const candidate = legacyLimitedProjection() as Record<string, unknown>;
    candidate.parse_warning = "hte_result_parse_failed";
    expect(parseLegacyProjectionForTest(candidate)).toEqual({
      status: "invalid",
    });
  });

  it.each([
    ["top_features", legacyLimitedProjection().top_features],
    ["warnings", ["legacy source warning"]],
  ] as const)(
    "rejects unavailable legacy HTE with nonempty %s",
    (field, populatedValue) => {
      const candidate = legacyUnavailableProjection() as Record<
        string,
        unknown
      >;
      candidate[field] = populatedValue;
      expect(parseLegacyProjectionForTest(candidate)).toEqual({
        status: "invalid",
      });
    },
  );

  it.each([
    ["source_reference_profile_status", "qualified"],
    ["target_scope_status", "declared"],
    ["bounds_meaning_status", "established"],
    ["conditional_coverage_status", "recomputed"],
    ["population_coverage_status", "recomputed"],
  ] as const)("rejects a legacy DTO that changes %s", (field, changedValue) => {
    const candidate = legacyLimitedProjection() as Record<string, unknown>;
    candidate[field] = changedValue;
    expect(parseLegacyProjectionForTest(candidate)).toEqual({
      status: "invalid",
    });
  });
});
