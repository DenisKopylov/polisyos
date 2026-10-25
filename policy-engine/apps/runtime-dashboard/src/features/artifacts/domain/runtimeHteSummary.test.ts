import {
  hteRef,
  pointSummary,
  r4PointSummary,
  r5DualObservationSummary,
} from "./__test__/decisionPacketHteFixtures";
import { parseDirectMethodExecutionHTESummary } from "./decisionPacketHte";

function runtimePointSummary(): Record<string, unknown> {
  return pointSummary();
}

describe("Runtime GET HTE summary validation", () => {
  it("preserves a numeric point while reporting source identity and overall relation as unknown", () => {
    const parsed = parseDirectMethodExecutionHTESummary(runtimePointSummary());

    expect(parsed?.kind).toBe("point_estimate");
    if (parsed?.kind !== "point_estimate") {
      throw new Error("Expected a point-estimate runtime summary.");
    }
    expect(parsed.point_estimate).toBe(0.25);
    expect(parsed.target_relation.estimand_status).toBe("not_established");
    expect(parsed.target_relation.overall_disposition).toBe("not_established");
  });

  it("gives a proven requested-scope mismatch precedence over unknown source identity", () => {
    const summary = runtimePointSummary();
    summary.request_target_scope = "population";
    const relation = summary.target_relation as Record<string, unknown>;
    relation.requested_scope = "population";
    relation.scope_disposition = "requested_claim_not_satisfied";
    relation.overall_disposition = "requested_claim_not_satisfied";

    const parsed = parseDirectMethodExecutionHTESummary(summary);

    expect(parsed?.kind).toBe("point_estimate");
    if (parsed?.kind !== "point_estimate") {
      throw new Error("Expected a point-estimate runtime summary.");
    }
    expect(parsed.point_estimate).toBe(0.25);
    expect(parsed.target_relation.scope_disposition).toBe(
      "requested_claim_not_satisfied",
    );
    expect(parsed.target_relation.overall_disposition).toBe(
      "requested_claim_not_satisfied",
    );
  });

  it("rejects a self-attested recomputed source estimand identity", () => {
    const summary = runtimePointSummary();
    (summary.target_relation as Record<string, unknown>).estimand_status =
      "recomputed";

    expect(parseDirectMethodExecutionHTESummary(summary)).toBeNull();
  });

  it("accepts the actual R5 estimator and producer-scoped joblib observations", () => {
    const summary = r5DualObservationSummary();
    const parsed = parseDirectMethodExecutionHTESummary(summary);

    expect(parsed?.kind).toBe("point_estimate");
    if (parsed?.kind !== "point_estimate") {
      throw new Error("Expected an accepted point-estimate runtime summary.");
    }
    expect(parsed.resource_evidence.owner_policy_revision).toBe("r5");
    expect(parsed.resource_evidence.owner_policy_execution_scope).toBe(
      "producer_scoped_joblib_parallelism_one",
    );
    expect(parsed.resource_evidence.estimator_before_class_fqn).toBe(
      "econml.dml.CausalForestDML",
    );
    expect(parsed.resource_evidence.estimator_before_n_jobs).toBe(1);
    expect(parsed.resource_evidence.joblib_entry_effective_jobs).toBe(1);
    expect(parsed.resource_evidence.physical_thread_limit_status).toBe(
      "not_established",
    );
  });

  it("rejects boolean and over-cap R5 policy values", () => {
    for (const maxJobs of [true, 2]) {
      const summary = r5DualObservationSummary();
      const evidence = summary.resource_evidence as Record<string, unknown>;
      evidence.owner_policy_max_jobs = maxJobs;
      expect(parseDirectMethodExecutionHTESummary(summary)).toBeNull();
    }
  });

  it("requires and profile-binds the physical materialization reference for R5", () => {
    const missing = r5DualObservationSummary();
    delete missing.materialization_binding_ref;
    expect(parseDirectMethodExecutionHTESummary(missing)).toBeNull();

    const wrongKind = r5DualObservationSummary();
    wrongKind.materialization_binding_ref = hteRef(
      "8",
      "ir.observational_data",
    );
    expect(parseDirectMethodExecutionHTESummary(wrongKind)).toBeNull();
  });

  it("accepts the strict R4 owner DTO fixture without an R5 materialization field", () => {
    expect(parseDirectMethodExecutionHTESummary(r4PointSummary())?.kind).toBe(
      "point_estimate",
    );
  });
});
