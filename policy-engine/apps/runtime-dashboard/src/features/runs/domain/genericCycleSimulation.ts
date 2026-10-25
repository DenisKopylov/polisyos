import type { RunDetailsView } from "@/api/validators";

export type RunGenericCycleSimulationProjection = NonNullable<
  RunDetailsView["generic_cycle_simulation"]
>;

export type GenericCycleSimulationPresentation =
  | Readonly<{ kind: "absent" }>
  | Readonly<{
      kind: "candidate_only";
      projection: RunGenericCycleSimulationProjection;
    }>
  | Readonly<{
      kind: "refused";
      reason:
        | "run_id_mismatch"
        | "candidate_authority_binding_invalid"
        | "projection_version_binding_invalid";
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
  const version = projection.schema_version;
  const supportedVersions = new Set<string>([
    "policyos.runtime.run_generic_cycle_simulation_projection.v1",
    "policyos.runtime.run_generic_cycle_simulation_projection.v2",
    "policyos.runtime.run_generic_cycle_simulation_projection.v3",
    "policyos.runtime.run_generic_cycle_simulation_projection.v4",
  ]);
  if (!supportedVersions.has(version)) {
    return { kind: "refused", reason: "projection_version_binding_invalid" };
  }
  const credalExpected =
    version === "policyos.runtime.run_generic_cycle_simulation_projection.v2" ||
    version === "policyos.runtime.run_generic_cycle_simulation_projection.v4";
  const historyExpected =
    version === "policyos.runtime.run_generic_cycle_simulation_projection.v3" ||
    version === "policyos.runtime.run_generic_cycle_simulation_projection.v4";
  const hasCredal =
    projection.credal_source_attempt_ref != null ||
    projection.credal_source_status != null ||
    projection.credal_source_limitation_code != null;
  const history = projection.n6_cycle_history ?? [];
  const hasHistory =
    projection.n6_cycle_history_status != null ||
    projection.n6_cycle_history_limitation_code != null ||
    history.length > 0;
  const historyStatusMatches = historyExpected
    ? (projection.n6_cycle_history_status === "resolved" &&
        history.length > 0 &&
        projection.n6_cycle_history_limitation_code == null) ||
      (projection.n6_cycle_history_status === "not_established" &&
        history.length === 0 &&
        projection.n6_cycle_history_limitation_code ===
          "n6_cycle_history_not_emitted")
    : !hasHistory;
  const historyKeys = history.map((row) =>
    JSON.stringify([row.node_ref, row.cycle_index]),
  );
  const extensionBindingValid =
    hasCredal === credalExpected &&
    (!credalExpected ||
      (projection.credal_source_status === "not_established" &&
        projection.credal_source_limitation_code != null &&
        projection.child_profile_status === "not_established" &&
        projection.n5_observations.length === 0)) &&
    historyStatusMatches &&
    new Set(historyKeys).size === historyKeys.length;
  if (!extensionBindingValid) {
    return { kind: "refused", reason: "projection_version_binding_invalid" };
  }
  if (
    projection.authority_purpose !== "cycle_input_candidate_only" ||
    projection.currentness_status !== "not_established" ||
    !Object.is(projection.publication_authority, false)
  ) {
    return { kind: "refused", reason: "candidate_authority_binding_invalid" };
  }
  return { kind: "candidate_only", projection };
}
