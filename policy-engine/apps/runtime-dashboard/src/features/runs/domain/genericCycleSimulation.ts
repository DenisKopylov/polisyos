import type { components } from "@/api/types";

export type RunGenericCycleSimulationProjection =
  components["schemas"]["RunGenericCycleSimulationProjection"];

export type GenericCycleSimulationPresentation =
  | Readonly<{ kind: "absent" }>
  | Readonly<{
      kind: "candidate_only";
      projection: RunGenericCycleSimulationProjection;
    }>
  | Readonly<{
      kind: "refused";
      reason: "run_id_mismatch" | "candidate_authority_binding_invalid";
    }>;

/** Bind one parsed run projection to its owning run without upgrading its authority. */
export function normalizeGenericCycleSimulation(
  runId: string,
  projection: RunGenericCycleSimulationProjection | null | undefined,
): GenericCycleSimulationPresentation {
  if (projection == null) {
    return { kind: "absent" };
  }
  if (projection.run_id !== runId) {
    return { kind: "refused", reason: "run_id_mismatch" };
  }
  if (
    (projection.schema_version !==
      "policyos.runtime.run_generic_cycle_simulation_projection.v1" &&
      projection.schema_version !==
        "policyos.runtime.run_generic_cycle_simulation_projection.v2") ||
    projection.authority_purpose !== "cycle_input_candidate_only" ||
    projection.currentness_status !== "not_established" ||
    !Object.is(projection.publication_authority, false)
  ) {
    return { kind: "refused", reason: "candidate_authority_binding_invalid" };
  }
  return { kind: "candidate_only", projection };
}
