import { hteRef } from "@/features/artifacts/domain/__test__/decisionPacketHteFixtures";
import {
  RUN_HTE_LIMITATIONS,
  r5RunHteSelectedProjection,
  runHteIntervalSelectedProjection,
  runHteSelectedProjection,
} from "./__test__/runExecutionHteFixtures";
import { parseRunExecutionHteProjection } from "./runExecutionHte";

describe("RunDetails GET direct-method HTE consumer", () => {
  it("distinguishes absent, non-HTE selected, and selected HTE projection states", () => {
    expect(parseRunExecutionHteProjection(null)).toEqual({ kind: "absent" });
    expect(
      parseRunExecutionHteProjection({
        status: "absent",
        candidate_only: true,
        limitations: ["no_direct_method_request"],
      }),
    ).toMatchObject({ kind: "without_hte", projection_status: "absent" });
    expect(
      parseRunExecutionHteProjection({
        status: "selected",
        candidate_only: true,
        limitations: RUN_HTE_LIMITATIONS,
        selection: {
          selection_kind: "direct_method",
          method_fqn: "causal.hte.forest_dr@1.0.0",
        },
      }),
    ).toMatchObject({ kind: "selected_without_hte" });

    const parsed = parseRunExecutionHteProjection(runHteSelectedProjection());
    expect(parsed.kind).toBe("hte");
    if (parsed.kind !== "hte") {
      throw new Error("Expected a selected HTE projection.");
    }
    expect(parsed.summary.kind).toBe("point_estimate");
    expect(parsed.summary.point_estimate).toBe(0.25);
    expect(parsed.summary.target_relation.estimand_status).toBe(
      "not_established",
    );
  });

  it("consumes the owner's hte_result_ref selection field for a real interval wire", () => {
    const projection = runHteIntervalSelectedProjection();
    const parsed = parseRunExecutionHteProjection(projection);
    expect(parsed.kind).toBe("hte");
    if (parsed.kind !== "hte") {
      throw new Error("Expected the owner-selected interval HTE projection.");
    }
    if (
      parsed.summary.kind !== "interval_estimate" ||
      parsed.summary.hte_result_ref === null
    ) {
      throw new Error("Expected the interval result reference branch.");
    }
    expect(parsed.summary.hte_result_ref.kind).toBe("ir.hte_result");

    const staleAlias = runHteIntervalSelectedProjection();
    const selection = staleAlias.selection as Record<string, unknown>;
    selection.native_mean_result_ref = selection.hte_result_ref;
    delete selection.hte_result_ref;
    expect(parseRunExecutionHteProjection(staleAlias).kind).toBe("invalid");
  });

  it("rejects an HTE row detached from the owner-selected method references", () => {
    const projection = runHteSelectedProjection();
    projection.selection.effective_input_ref = hteRef(
      "c",
      "ir.observation_method_input",
    );

    expect(parseRunExecutionHteProjection(projection).kind).toBe("invalid");
  });

  it("rejects unknown projection and selection fields rather than silently projecting them", () => {
    const projection = runHteSelectedProjection() as Record<string, unknown>;
    projection.unreviewed_surface = true;
    expect(parseRunExecutionHteProjection(projection).kind).toBe("invalid");

    const selectionDrift = runHteSelectedProjection();
    (selectionDrift.selection as Record<string, unknown>).unreviewed_field =
      true;
    expect(parseRunExecutionHteProjection(selectionDrift).kind).toBe("invalid");
  });

  it("requires the context-captured binding to match a selected R5 summary", () => {
    const projection = r5RunHteSelectedProjection();
    const summary = projection.selection.hte as Record<string, unknown>;
    const evidence = summary.resource_evidence as Record<string, unknown>;
    evidence.owner_policy_schema_version =
      "polisyos.runtime.observational_input_resource_policy.v5";
    evidence.owner_policy_revision = "r5";
    evidence.owner_policy_execution_scope =
      "producer_scoped_joblib_parallelism_one";
    evidence.joblib_observation_status = "recomputed";
    evidence.joblib_profile_id = "joblib.parallel_config.current_thread@1.0";
    evidence.joblib_profile_revision = "1.0";
    evidence.joblib_implementation = "joblib.parallel_config";
    evidence.joblib_implementation_version = "1.5.2";
    evidence.joblib_scope = "current_thread_joblib";
    evidence.joblib_max_jobs = 1;
    evidence.joblib_started = true;
    evidence.joblib_finished = true;
    evidence.joblib_exit_status = "returned";
    evidence.joblib_entry_effective_jobs = 1;
    evidence.joblib_entry_backend_fqn = "joblib._parallel_backends.LokyBackend";
    evidence.joblib_entry_config_sha256 = "c".repeat(64);
    evidence.joblib_entry_implementation_version = "1.5.2";
    evidence.joblib_exit_effective_jobs = 1;
    evidence.joblib_exit_backend_fqn = "joblib._parallel_backends.LokyBackend";
    evidence.joblib_exit_config_sha256 = "c".repeat(64);
    evidence.joblib_exit_implementation_version = "1.5.2";
    summary.materialization_binding_ref = hteRef(
      "7",
      "foundry.hte.physical_source_materialization_binding",
    );
    const context = projection.selection.owned_hte_request_context as Record<
      string,
      unknown
    >;
    context.materialization_binding_ref = summary.materialization_binding_ref;

    expect(parseRunExecutionHteProjection(projection).kind).toBe("hte");
    context.materialization_binding_ref = hteRef("8", "wrong.kind");
    expect(parseRunExecutionHteProjection(projection).kind).toBe("invalid");
  });
});
