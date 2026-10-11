import { runDetailsSchema } from "@/api/validators";

import {
  normalizeGenericCycleSimulation,
  type RunGenericCycleSimulationProjection,
} from "./genericCycleSimulation";

function parsedProjection() {
  return runDetailsSchema.parse({
    meta: {
      request_id: "req-generic-cycle",
      generated_at: "2026-10-11T10:00:00Z",
      source_kinds: ["core_run"],
    },
    run: {
      run_id: "run-1",
      source_kind: "core_run",
      status: "failed",
      generic_cycle_simulation: {
        artifact_status: "not_established",
        authority_purpose: "cycle_input_candidate_only",
        child_profile_bindings: [],
        child_profile_status: "not_established",
        currentness_status: "not_established",
        n5_observations: [],
        publication_authority: false,
        run_id: "run-1",
        limitation_code: "compiled_cycle_artifact_integrity_not_established",
        source_content_hash: null,
        source_ref: null,
        n4_source_status: null,
        schema_version:
          "policyos.runtime.run_generic_cycle_simulation_projection.v1",
      },
    },
    temporal_scope: null,
  }).run.generic_cycle_simulation;
}

describe("normalizeGenericCycleSimulation", () => {
  it("preserves the parsed candidate-only projection without upgrading currentness", () => {
    const projection = parsedProjection();

    expect(normalizeGenericCycleSimulation("run-1", projection)).toEqual({
      kind: "candidate_only",
      projection,
    });
  });

  it.each([
    ["true", true],
    ["null", null],
    ["undefined", undefined],
    ["zero", 0],
  ] as const)(
    "refuses a malformed %s publication-authority value",
    (_label, publicationAuthority) => {
      const validProjection = parsedProjection();
      if (!validProjection) {
        throw new Error("expected a parsed generic-cycle projection fixture");
      }
      const malformedProjection = {
        ...validProjection,
        publication_authority: publicationAuthority,
      } as unknown as RunGenericCycleSimulationProjection;

      expect(
        normalizeGenericCycleSimulation("run-1", malformedProjection),
      ).toEqual({
        kind: "refused",
        reason: "candidate_authority_binding_invalid",
      });
    },
  );

  it("refuses a projection bound to another run instead of silently omitting it", () => {
    const projection = parsedProjection();

    expect(normalizeGenericCycleSimulation("run-2", projection)).toEqual({
      kind: "refused",
      reason: "run_id_mismatch",
    });
  });

  it("keeps genuine absence distinct from a supplied run mismatch", () => {
    expect(normalizeGenericCycleSimulation("run-1", undefined)).toEqual({
      kind: "absent",
    });
  });
});
