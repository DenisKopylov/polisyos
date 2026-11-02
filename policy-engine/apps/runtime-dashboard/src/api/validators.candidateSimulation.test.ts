import { failedCandidateSimulationFixture } from "@/test/fixtures/failedCandidateSimulation";
import { runDetailsSchema } from "./validators";

function response(candidate: unknown) {
  return {
    meta: {
      request_id: "candidate-wire",
      generated_at: "2026-11-02T00:00:00Z",
      source_kinds: ["core_run"],
    },
    run: {
      run_id: "run-1",
      source_kind: "core_run",
      status: "error",
      candidate_simulation: candidate,
    },
    temporal_scope: null,
  };
}

describe("retained candidate simulation wire", () => {
  it("retains exact finite numbers and failed-cycle boundaries", () => {
    const fixture = failedCandidateSimulationFixture();
    const projection = runDetailsSchema.parse(response(fixture)).run
      .candidate_simulation;
    expect(projection?.schema_version).toBe(
      "policyos.runtime.run_failed_candidate_simulation_projection.v1",
    );
    expect(projection?.n5_observations[0]?.result_body?.trajectories).toEqual(
      fixture.n5_observations[0]!.result_body.trajectories,
    );
    expect(projection?.publication_authority).toBe(false);
    expect(projection?.n5_observations[0]?.authority_blockers).toEqual(
      fixture.n5_observations[0]!.authority_blockers,
    );
  });

  it("keeps the completed compiled schema compatible with its new optional numbers", () => {
    const fixture = failedCandidateSimulationFixture();
    const compiled = {
      schema_version: "policyos.runtime.run_candidate_simulation_projection.v1",
      run_id: fixture.run_id,
      artifact_status: "resolved",
      authority_purpose: "candidate_observation_only",
      publication_authority: false,
      source_ref: {
        ...fixture.source_ref,
        kind: "runtime.compiled_recursive_generation_cycle",
      },
      source_content_hash: fixture.source_content_hash,
      n5_observations: fixture.n5_observations,
    };
    expect(
      runDetailsSchema.parse(response(compiled)).run.candidate_simulation
        ?.n5_observations[0]?.result_body,
    ).toMatchObject({ authority_purpose: "candidate_scenario_n5_only" });
  });

  it("keeps an independently verified compiled numerical body when child-family lineage is explicitly limited", () => {
    const fixture = failedCandidateSimulationFixture();
    const row = fixture.n5_observations[0]!;
    row.lineage_status = "not_established";
    Reflect.set(
      row,
      "lineage_limitation_code",
      "n4_child_profile_family_not_established",
    );
    row.context_job_ref = { ...row.context_job_ref };
    Reflect.set(row.context_job_ref, "manifest_profile_sha256", null);
    const compiled = {
      schema_version: "policyos.runtime.run_candidate_simulation_projection.v1",
      run_id: fixture.run_id,
      artifact_status: "resolved",
      authority_purpose: "candidate_observation_only",
      publication_authority: false,
      source_ref: {
        ...fixture.source_ref,
        kind: "runtime.compiled_recursive_generation_cycle",
      },
      source_content_hash: fixture.source_content_hash,
      n5_observations: fixture.n5_observations,
    };
    const observation = runDetailsSchema.parse(response(compiled)).run
      .candidate_simulation?.n5_observations[0];
    expect(observation?.lineage_status).toBe("not_established");
    expect(observation?.lineage_limitation_code).toBe(
      "n4_child_profile_family_not_established",
    );
    expect(observation?.result_body?.trajectories).toEqual(
      row.result_body.trajectories,
    );
    expect(observation?.context_job_ref?.manifest_profile_sha256).toBeNull();
  });

  it("does not reinterpret a failed execution as legacy compiled data without its discriminator", () => {
    const fixture = failedCandidateSimulationFixture();
    for (const field of [
      "schema_version",
      "cycle_index",
      "cycle_completed",
      "failed_stage",
      "failure_source",
    ])
      Reflect.deleteProperty(fixture, field);
    expect(runDetailsSchema.safeParse(response(fixture)).success).toBe(false);
    const legacy = {
      ...fixture,
      source_ref: {
        ...fixture.source_ref,
        kind: "runtime.compiled_recursive_generation_cycle",
      },
    };
    expect(
      runDetailsSchema.parse(response(legacy)).run.candidate_simulation
        ?.schema_version,
    ).toBe("policyos.runtime.run_candidate_simulation_projection.v1");
  });

  it("retains a declared refusal without exposing any numerical body", () => {
    const refusal = {
      schema_version:
        "policyos.runtime.run_failed_candidate_simulation_projection.v1",
      run_id: "run-1",
      artifact_status: "not_established",
      limitation_code: "candidate_n5_output_not_established",
    };
    expect(
      runDetailsSchema.parse(response(refusal)).run.candidate_simulation
        ?.n5_observations,
    ).toEqual([]);
  });

  const mutations: Array<
    [
      string,
      (fixture: ReturnType<typeof failedCandidateSimulationFixture>) => void,
    ]
  > = [
    [
      "publication authority",
      (value) => {
        value.publication_authority = true;
      },
    ],
    [
      "completed-cycle forgery",
      (value) => {
        value.cycle_completed = true;
      },
    ],
    [
      "wrong outer purpose",
      (value) => {
        value.authority_purpose = "runtime_closeout_authority";
      },
    ],
    [
      "unknown schema",
      (value) => {
        value.schema_version =
          "policyos.runtime.run_failed_candidate_simulation_projection.v2";
      },
    ],
    [
      "completed source in failed schema",
      (value) => {
        value.source_ref.kind = "runtime.compiled_recursive_generation_cycle";
      },
    ],
    [
      "foreign execution view",
      (value) => {
        value.n5_observations[0]!.n5_execution_ref = {
          ...value.source_ref,
          manifest_profile_sha256: "sha256:" + "c".repeat(64),
        };
      },
    ],
    [
      "missing selected N4 source",
      (value) => {
        Reflect.deleteProperty(
          value.n5_observations[0]!.n4_source_ref,
          "manifest_profile_sha256",
        );
      },
    ],
    [
      "missing selected N5 input",
      (value) => {
        Reflect.deleteProperty(
          value.n5_observations[0]!.n5_input_ref,
          "manifest_profile_sha256",
        );
      },
    ],
    [
      "missing selected execution",
      (value) => {
        Reflect.deleteProperty(value.n5_observations[0]!, "n5_execution_ref");
      },
    ],
    [
      "generic body in configured slot",
      (value) => {
        value.n5_observations[0]!.result_body.schema_version =
          "policyos.runtime.run_generic_cycle_simulation_n5_result_body.v1";
        value.n5_observations[0]!.result_body.authority_purpose =
          "cycle_input_candidate_only";
      },
    ],
    [
      "body promotion",
      (value) => {
        value.n5_observations[0]!.result_body.publication_authority = true;
      },
    ],
    [
      "selected result mismatch",
      (value) => {
        value.n5_observations[0]!.result_body.selected_manifest_profile_sha256 =
          "sha256:" + "c".repeat(64);
      },
    ],
    [
      "world basis mismatch",
      (value) => {
        value.n5_observations[0]!.result_body.world_model_record_content_hash =
          "sha256:" + "c".repeat(64);
      },
    ],
    [
      "foreign trajectory atom",
      (value) => {
        value.n5_observations[0]!.result_body.trajectories[0]!.atom_ids = [
          "foreign-atom",
        ];
      },
    ],
    [
      "foreign selected outcome",
      (value) => {
        value.n5_observations[0]!.result_body.selected_outcomes = [
          "foreign.outcome",
        ];
      },
    ],
    [
      "missing body behind resolved marker",
      (value) => {
        Reflect.deleteProperty(value.n5_observations[0]!, "result_body");
      },
    ],
    [
      "refused projection with numbers",
      (value) => {
        value.artifact_status = "not_established";
        Reflect.set(
          value,
          "limitation_code",
          "candidate_n5_output_not_established",
        );
      },
    ],
    [
      "wrong lineage kind",
      (value) => {
        value.n5_observations[0]!.context_job_ref.kind = "runtime.other";
      },
    ],
    [
      "unresolved lineage",
      (value) => {
        value.n5_observations[0]!.lineage_status = "not_established";
      },
    ],
    [
      "injected compiled checkpoint",
      (value) => {
        Reflect.set(value, "recursive_cycle_checkpoint", {});
      },
    ],
  ];
  it.each(mutations)("rejects %s", (_name, mutate) => {
    const fixture = failedCandidateSimulationFixture();
    mutate(fixture);
    expect(runDetailsSchema.safeParse(response(fixture)).success).toBe(false);
  });
});
