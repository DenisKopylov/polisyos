import { runDetailsSchema } from "../../../api/validators";

import { c41JointParentObservation } from "@/test/fixtures/c41JointParent";
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

function parsedResolvedHistoryProjection(
  version: "v3" | "v4",
  runId = "run-1",
) {
  const artifactRef = (kind: string, suffix: string) => ({
    artifact_id: "sha256:" + suffix.repeat(64),
    kind,
    media_type: "application/json",
  });
  const n6Cycle = {
    cycle_index: 1,
    design_problem_basis_ref: null,
    design_problem_ref: "sha256:" + "d".repeat(64),
    generation_cycle_run_terminal_status: "completed",
    grounding_current_valid: false,
    grounding_status: "grounded_shadow",
    node_ref: "design-problem://" + "d".repeat(64),
    refinement_decision: "refine",
    search_iteration_status: "refined_shadow",
    selected_candidate_content_hash: "sha256:" + "a".repeat(64),
    selected_candidate_ref: "candidate://candidate-a",
    terminal_kind: "grounded_partial_admissible",
    value_authority_blockers: ["publication_not_admitted"],
    value_decision_grade: "medium",
    value_ref: "sha256:" + "b".repeat(64),
    value_status: "value_conditional",
    voi_next_action: "advance",
  };
  const isCredalVersion = version === "v4";
  const projection = {
    artifact_status: "resolved",
    authority_purpose: "cycle_input_candidate_only",
    child_profile_bindings: [],
    child_profile_limitation_code: isCredalVersion
      ? "generic_n4_source_generation_not_complete"
      : null,
    child_profile_status: isCredalVersion ? "not_established" : "not_attempted",
    currentness_status: "not_established",
    limitation_code: isCredalVersion
      ? "candidate_source_authority_not_established"
      : null,
    n4_source_ref: isCredalVersion
      ? artifactRef("runtime.generation_source_handoff", "c")
      : null,
    n4_source_status: isCredalVersion ? "resolved" : null,
    n5_limitation_code: isCredalVersion
      ? "generic_n4_source_generation_not_complete"
      : null,
    n5_observations: [],
    n6_cycle_history: [n6Cycle],
    n6_cycle_history_limitation_code: null,
    n6_cycle_history_status: "resolved",
    parent_context_job_ref: isCredalVersion
      ? artifactRef("runtime.quality.cycle_substrate_context_job", "b")
      : null,
    parent_profile_id: isCredalVersion ? "parent-profile" : null,
    parent_profile_ref: isCredalVersion
      ? artifactRef("runtime.quality.generic_cycle_simulation_profile", "a")
      : null,
    publication_authority: false,
    run_id: runId,
    schema_version:
      version === "v3"
        ? "policyos.runtime.run_generic_cycle_simulation_projection.v3"
        : "policyos.runtime.run_generic_cycle_simulation_projection.v4",
    source_content_hash: "sha256:" + "f".repeat(64),
    source_ref: artifactRef("runtime.compiled_recursive_generation_cycle", "e"),
    ...(isCredalVersion
      ? {
          credal_source_attempt_ref: null,
          credal_source_limitation_code:
            "candidate_source_authority_not_established",
          credal_source_status: "not_established",
        }
      : {}),
  };
  return runDetailsSchema.parse({
    meta: {
      request_id: "req-generic-cycle",
      generated_at: "2026-10-11T10:00:00Z",
      source_kinds: ["core_run"],
    },
    run: {
      run_id: "run-1",
      source_kind: "core_run",
      status: "completed",
      generic_cycle_simulation: projection,
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

  it.each(["v3", "v4"] as const)(
    "accepts source-supported %s history only as a bound candidate projection",
    (version) => {
      const projection = parsedResolvedHistoryProjection(version);

      expect(
        normalizeGenericCycleSimulation("run-1", projection),
      ).toMatchObject({
        kind: "candidate_only",
        projection: {
          schema_version:
            version === "v3"
              ? "policyos.runtime.run_generic_cycle_simulation_projection.v3"
              : "policyos.runtime.run_generic_cycle_simulation_projection.v4",
          n6_cycle_history_status: "resolved",
          currentness_status: "not_established",
          publication_authority: false,
        },
      });
    },
  );

  it("refuses an unknown runtime projection version even when it has no extensions", () => {
    const projection = parsedProjection();
    if (!projection) {
      throw new Error("expected a parsed generic-cycle projection fixture");
    }
    const malformed = {
      ...projection,
      schema_version:
        "policyos.runtime.run_generic_cycle_simulation_projection.v6",
    } as unknown as RunGenericCycleSimulationProjection;

    expect(normalizeGenericCycleSimulation("run-1", malformed)).toEqual({
      kind: "refused",
      reason: "projection_version_binding_invalid",
    });
  });

  it("accepts v5 parent assessment only with a valid candidate extension", () => {
    const projection = parsedResolvedHistoryProjection("v3");
    if (!projection) throw new Error("expected a parsed projection");
    const v5 = {
      ...projection,
      schema_version:
        "policyos.runtime.run_generic_cycle_simulation_projection.v5",
      joint_parent_status: "resolved",
      joint_parent_observations: [c41JointParentObservation()],
    };
    const parsed = runDetailsSchema.parse({
      meta: {
        request_id: "req-v5",
        generated_at: "2026-10-11T10:00:00Z",
        source_kinds: ["core_run"],
      },
      run: {
        run_id: "run-1",
        source_kind: "core_run",
        status: "completed",
        generic_cycle_simulation: v5,
      },
      temporal_scope: null,
    }).run.generic_cycle_simulation;
    expect(normalizeGenericCycleSimulation("run-1", parsed)).toMatchObject({
      kind: "candidate_only",
    });
    const corrupted = {
      ...parsed!,
      joint_parent_status: "resolved",
      joint_parent_observations: [],
    };
    expect(
      normalizeGenericCycleSimulation(
        "run-1",
        corrupted as RunGenericCycleSimulationProjection,
      ),
    ).toEqual({
      kind: "refused",
      reason: "projection_version_binding_invalid",
    });
  });

  it("withholds N6 history when its projection is bound to a different run", () => {
    const projection = parsedResolvedHistoryProjection("v3", "run-other");

    expect(normalizeGenericCycleSimulation("run-1", projection)).toEqual({
      kind: "refused",
      reason: "run_id_mismatch",
    });
  });

  it("refuses a history/version mismatch even if a caller bypasses the DTO parser", () => {
    const projection = parsedResolvedHistoryProjection("v3");
    const malformed = {
      ...projection,
      schema_version:
        "policyos.runtime.run_generic_cycle_simulation_projection.v1",
    } as unknown as RunGenericCycleSimulationProjection;

    expect(normalizeGenericCycleSimulation("run-1", malformed)).toEqual({
      kind: "refused",
      reason: "projection_version_binding_invalid",
    });
  });
});
