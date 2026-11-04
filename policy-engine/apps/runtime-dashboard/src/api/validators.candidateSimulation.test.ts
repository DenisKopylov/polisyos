import { failedCandidateSimulationFixture } from "@/test/fixtures/failedCandidateSimulation";
import {
  runDetailsSchema,
  runCandidateSimulationCurrentOccurrenceSchema,
  runCandidateSourceCurrentProjectionSchema,
} from "./validators";

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
  it("keeps v5 numbers bound to artifact epoch 5 rather than accepting mixed epochs", () => {
    const fixture = failedCandidateSimulationFixture();
    const body = fixture.n5_observations[0]!.result_body;
    body.artifact_schema_version = "5.0.0";
    body.result_schema_version = "policyos.runtime.joint_simulation_horizon.v5";
    const parsed = runDetailsSchema.parse(response(fixture)).run
      .candidate_simulation;
    expect(parsed?.n5_observations[0]?.result_body?.result_schema_version).toBe(
      "policyos.runtime.joint_simulation_horizon.v5",
    );
    body.artifact_schema_version = "4.0.0";
    expect(runDetailsSchema.safeParse(response(fixture)).success).toBe(false);
  });

  it("requires a complete declared unit map and its exact selected declaration view", () => {
    const fixture = failedCandidateSimulationFixture();
    const body = fixture.n5_observations[0]!.result_body;
    const declaration = {
      artifact_id: "sha256:" + "e".repeat(64),
      kind: "runtime.quality.candidate_simulation_model_declaration",
      media_type: "application/json",
      manifest_profile_sha256: "sha256:" + "f".repeat(64),
    };
    Object.assign(body, {
      outcome_units: { "government.balance": "declared_currency_unit" },
      unit_provenance: "declared_candidate_model",
      model_declaration_ref: declaration,
    });
    const parsed = runDetailsSchema.parse(response(fixture)).run
      .candidate_simulation;
    expect(parsed?.n5_observations[0]?.result_body?.outcome_units).toEqual({
      "government.balance": "declared_currency_unit",
    });
    const positive = structuredClone(body);
    for (const change of [
      { outcome_units: {} },
      { outcome_units: { "foreign.outcome": "declared_currency_unit" } },
      {
        model_declaration_ref: {
          ...declaration,
          manifest_profile_sha256: null,
        },
      },
      { unit_provenance: "not_established" },
    ]) {
      fixture.n5_observations[0]!.result_body = { ...positive, ...change };
      expect(runDetailsSchema.safeParse(response(fixture)).success).toBe(false);
    }
  });

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

function recordedLocalAttemptFixture() {
  return {
    node_ref: "design-problem://attempt",
    candidate_id: "candidate-refused",
    candidate_content_hash: "sha256:" + "a".repeat(64),
    cycle_index: 2,
    problem_ref: "sha256:" + "b".repeat(64),
    attempt_ref: "sha256:" + "c".repeat(64),
    failure_stage: "n8",
    simulation_status: "joint_simulated",
    simulation_authority_blockers: ["simulation_only_k_sim_not_world_evidence"],
    value_status: "value_blocked",
    value_decision_grade: "blocked",
    value_authority_blockers: ["candidate_value_unavailable"],
    simulation_result_ref: {
      artifact_id: "sha256:" + "d".repeat(64),
      kind: "polisyos.runtime.joint_simulation_result",
      media_type: "application/json",
    },
  };
}

function compiledAttemptProjection(attempt: unknown) {
  return {
    schema_version: "policyos.runtime.run_candidate_simulation_projection.v1",
    run_id: "run-1",
    artifact_status: "resolved",
    source_ref: {
      artifact_id: "sha256:" + "e".repeat(64),
      kind: "runtime.compiled_recursive_generation_cycle",
      media_type: "application/json",
    },
    source_content_hash: "sha256:" + "e".repeat(64),
    candidate_evaluation_attempts: [attempt],
  };
}

describe("recorded local attempt wire", () => {
  it("keeps a completed N5 observation distinct from its N8 refusal", () => {
    const projection = runDetailsSchema.parse(
      response(compiledAttemptProjection(recordedLocalAttemptFixture())),
    ).run.candidate_simulation;
    if (
      projection?.schema_version !==
      "policyos.runtime.run_candidate_simulation_projection.v1"
    )
      throw new Error("wrong projection");
    const attempt = projection.candidate_evaluation_attempts![0]!;
    expect(attempt.simulation_status).toBe("joint_simulated");
    expect(attempt.value_status).toBe("value_blocked");
    expect(attempt.simulation_result_ref?.artifact_id).toBe(
      "sha256:" + "d".repeat(64),
    );
    expect(attempt.numerical_result_verification).toBe("not_established");
    expect(attempt.publication_authority).toBe(false);
  });

  it.each([
    { failure_stage: "n5" },
    { simulation_status: "simulation_pending_n5" },
    { value_status: "value_ready" },
    { failure_scope: "shared" },
    { scope: "execution_reservation" },
    { numerical_result_verification: "recomputed" },
    { publication_authority: true },
    {
      simulation_result_ref: {
        artifact_id: "sha256:" + "d".repeat(64),
        kind: "foreign.artifact",
        media_type: "application/json",
      },
    },
  ])("refuses corrupted failure or borrowed authority %j", (change) => {
    const projection = compiledAttemptProjection({
      ...recordedLocalAttemptFixture(),
      ...change,
    });
    expect(runDetailsSchema.safeParse(response(projection)).success).toBe(
      false,
    );
  });

  it("withholds attempts when the compiled source is not resolved", () => {
    const projection = {
      ...compiledAttemptProjection(recordedLocalAttemptFixture()),
      artifact_status: "not_established",
    };
    expect(runDetailsSchema.safeParse(response(projection)).success).toBe(
      false,
    );
  });
});

function candidateBasisOccurrenceFixture() {
  const limitation = "candidate_source_basis_prior_occurrence_not_revalidated";
  return {
    candidate_id: "historically-accepted",
    cycle_index: 1,
    content_hash: "sha256:" + "a".repeat(64),
    source_content_hash: null,
    front: "research",
    certified_by_n9: false,
    candidate_basis_cycle_index: 2,
    candidate_basis_content_hash: "sha256:" + "b".repeat(64),
    candidate_basis_status: "prior_basis_not_revalidated",
    candidate_basis_limitation_code: limitation,
    historical_front: "decision",
    historical_certified_by_n9: true,
    historical_value_status: "value_ready",
    historical_value_decision_grade: "high",
    historical_value_ref: "value://original",
    historical_value_blockers: [],
    value_status: "value_pending_n8",
    value_blockers: [limitation],
  };
}

function candidateCurrentViewFixture() {
  return {
    status: "resolved",
    generation_run_content_hash: "sha256:" + "c".repeat(64),
    basis_cycle_index: 2,
    basis_transition_content_hash: "sha256:" + "b".repeat(64),
    occurrences: [candidateBasisOccurrenceFixture()],
    fronts: {
      decision_candidate_ids: [],
      research_candidate_ids: ["historically-accepted"],
      quarantine_candidate_ids: [],
      portfolio_candidate_ids: [],
    },
  };
}

describe("candidate-basis current view", () => {
  it("preserves original acceptance while withholding its old current certification and value", () => {
    const row = runCandidateSimulationCurrentOccurrenceSchema.parse(
      candidateBasisOccurrenceFixture(),
    );
    expect(row.historical_certified_by_n9).toBe(true);
    expect(row.historical_value_status).toBe("value_ready");
    expect(row.certified_by_n9).toBe(false);
    expect(row.value_status).toBe("value_pending_n8");
    const legacy = {
      candidate_id: "legacy",
      cycle_index: 0,
      content_hash: "sha256:" + "d".repeat(64),
      source_content_hash: null,
      front: "decision",
      certified_by_n9: true,
    };
    expect(runCandidateSimulationCurrentOccurrenceSchema.parse(legacy)).toEqual(
      legacy,
    );
  });

  it.each([
    { front: "decision" },
    { certified_by_n9: true },
    { value_status: "value_ready" },
    { value_ref: "value://original" },
    { value_decision_grade: "high" },
    { candidate_basis_status: "recorded_on_selected_basis" },
    { candidate_basis_content_hash: null },
    { candidate_basis_limitation_code: null },
    { historical_certified_by_n9: null },
    { historical_front: "quarantine" },
    { cycle_index: 2 },
    { value_blockers: [] },
  ])("refuses an unqualified old current claim %j", (change) => {
    expect(
      runCandidateSimulationCurrentOccurrenceSchema.safeParse({
        ...candidateBasisOccurrenceFixture(),
        ...change,
      }).success,
    ).toBe(false);
  });

  it("requires one complete view basis and full front denominator", () => {
    const view = runCandidateSourceCurrentProjectionSchema.parse(
      candidateCurrentViewFixture(),
    );
    expect(view.publication_authority).toBe(false);
    expect(view.currentness_status).toBe("not_established");
    for (const change of [
      { basis_transition_content_hash: "sha256:" + "e".repeat(64) },
      { generation_run_content_hash: null },
      { certified_candidate_ids: ["historically-accepted"] },
      {
        occurrences: [
          {
            candidate_id: "historically-accepted",
            cycle_index: 1,
            content_hash: "sha256:" + "a".repeat(64),
            source_content_hash: null,
            front: "research",
            certified_by_n9: false,
          },
        ],
      },
      {
        fronts: {
          ...candidateCurrentViewFixture().fronts,
          quarantine_candidate_ids: ["foreign"],
        },
      },
      { status: "not_established" },
    ]) {
      expect(
        runCandidateSourceCurrentProjectionSchema.safeParse({
          ...candidateCurrentViewFixture(),
          ...change,
        }).success,
      ).toBe(false);
    }
    const unavailable = runCandidateSourceCurrentProjectionSchema.parse({
      status: "not_established",
      issues: ["candidate_source_current_owner_refused"],
    });
    expect(unavailable.occurrences).toEqual([]);
    expect(unavailable.fronts).toBeUndefined();
  });
});

describe("candidate acquisition lineage", () => {
  it("keeps candidate-only blocked N5 and rejects observed admission or wrong source kinds", async () => {
    const { runCandidateSimulationAcquisitionHistoryEntryV4Schema } =
      await import("./validators");
    const ref = (kind: string) => ({
      artifact_id: "sha256:" + "1".repeat(64),
      kind,
      media_type: "application/json",
      manifest_profile_sha256: "sha256:" + "f".repeat(64),
    });
    const row = {
      schema_version:
        "policyos.runtime.run_candidate_simulation_acquisition_history.v4",
      route_receipt_ref: ref("runtime_quality.acquisition_route_loop_receipt"),
      reentry_receipt_ref: ref(
        "runtime_quality.candidate_source_reentry_receipt",
      ),
      route_id: "sha256:" + "2".repeat(64),
      action_generation: 1,
      terminal_outcome: "candidate_reentry_completed",
      candidate_action_ref: ref(
        "runtime_quality.acquisition_candidate_action_receipt",
      ),
      candidate_source_ref: ref("runtime.quality.candidate_acquisition_source"),
      data_snapshot_ref: ref("fabric.data_snapshot"),
      world_model_ref: ref("runtime.quality.world_model_record"),
      context_job_ref: ref("runtime.quality.cycle_substrate_context_job"),
      model_declaration_ref: ref(
        "runtime.quality.candidate_simulation_model_declaration",
      ),
      ncm_ref: ref("ir.ncm_spec"),
      n4_source_ref: null,
      n5_input_ref: null,
      n5_execution_ref: null,
      n5_result_ref: null,
      simulation_status: "simulation_blocked",
      simulation_authority_blockers: ["blocked"],
      source_cycle_index: 0,
      continued_cycle_index: 1,
      source_generation_run_content_hash: "sha256:" + "3".repeat(64),
      continued_generation_run_content_hash: "sha256:" + "4".repeat(64),
      basis_transition_content_hash: "sha256:" + "5".repeat(64),
      limitations: ["candidate_only"],
      observed_admission: false,
      currentness_status: "not_established",
      authority_purpose: "candidate_observation_only",
      publication_authority: false,
    };
    expect(
      runCandidateSimulationAcquisitionHistoryEntryV4Schema.parse(row)
        .simulation_status,
    ).toBe("simulation_blocked");
    for (const change of [
      { observed_admission: true },
      { publication_authority: true },
      { candidate_source_ref: ref("fabric.data_snapshot") },
      { continued_cycle_index: 0 },
    ]) {
      expect(
        runCandidateSimulationAcquisitionHistoryEntryV4Schema.safeParse({
          ...row,
          ...change,
        }).success,
      ).toBe(false);
    }
  });
});

describe("candidate terminal frontier wire", () => {
  it("keeps a blocked reentry nonnumeric and rejects an old success graft", async () => {
    const { runCandidateSimulationAcquisitionHistoryEntryV5Schema } =
      await import("./validators");
    const ref = (kind: string) => ({
      artifact_id: "sha256:" + "1".repeat(64),
      kind,
      media_type: "application/json",
      manifest_profile_sha256: "sha256:" + "f".repeat(64),
    });
    const route = ref("runtime_quality.acquisition_route_loop_receipt");
    const action = ref("runtime_quality.acquisition_candidate_action_receipt");
    const source = ref("runtime.quality.candidate_acquisition_source");
    const failure = ref("runtime_quality.candidate_source_reentry_receipt");
    const reentry = {
      schema_version:
        "policyos.runtime.run_candidate_simulation_acquisition_history.v4",
      route_receipt_ref: route,
      reentry_receipt_ref: failure,
      route_id: "sha256:" + "2".repeat(64),
      action_generation: 2,
      terminal_outcome: "candidate_reentry_completed",
      candidate_action_ref: action,
      candidate_source_ref: source,
      data_snapshot_ref: ref("fabric.data_snapshot"),
      world_model_ref: ref("runtime.quality.world_model_record"),
      context_job_ref: ref("runtime.quality.cycle_substrate_context_job"),
      model_declaration_ref: ref(
        "runtime.quality.candidate_simulation_model_declaration",
      ),
      ncm_ref: ref("ir.ncm_spec"),
      n4_source_ref: null,
      n5_input_ref: null,
      n5_execution_ref: null,
      n5_result_ref: null,
      simulation_status: "simulation_blocked",
      simulation_authority_blockers: ["n5_blocked"],
      source_cycle_index: 0,
      continued_cycle_index: 1,
      source_generation_run_content_hash: "sha256:" + "3".repeat(64),
      continued_generation_run_content_hash: "sha256:" + "4".repeat(64),
      basis_transition_content_hash: "sha256:" + "5".repeat(64),
      limitations: ["candidate_only"],
      observed_admission: false,
      currentness_status: "not_established",
      authority_purpose: "candidate_observation_only",
      publication_authority: false,
    };
    const row = {
      schema_version:
        "policyos.runtime.run_candidate_simulation_acquisition_history.v5",
      route_receipt_ref: route,
      route_id: reentry.route_id,
      action_generation: 2,
      terminal_outcome: "candidate_reentry_completed",
      candidate_action_ref: action,
      candidate_source_ref: source,
      evaluation_decision_ref: ref(
        "runtime_quality.acquisition_evaluation_decision",
      ),
      current_basis_ref: ref("runtime_quality.acquisition_evaluation_basis"),
      selected_basis_ref: ref("runtime_quality.acquisition_evaluation_basis"),
      selected_evaluation_witness_ref: failure,
      comparison_result: "not_established",
      predicate_provenance: "not_established",
      comparison_reason_codes: ["prior_comparison_unavailable"],
      selected_basis_role: "blocked",
      current_basis_provenance: "not_established",
      selected_basis_provenance: "not_established",
      current_basis_limitations: ["candidate_only"],
      selected_basis_limitations: ["candidate_only"],
      frontier_ref: "sha256:" + "6".repeat(64),
      frontier_revision: 2,
      frontier_selection: "selected",
      selected_evaluation: null,
      selected_n5_observation: null,
      reentry,
      current_continuation_ref: null,
      current_cheap_consequences: null,
      evaluation_provenance: "not_established",
      observed_admission: false,
      currentness_status: "not_established",
      authority_purpose: "candidate_observation_only",
      publication_authority: false,
    };
    expect(
      runCandidateSimulationAcquisitionHistoryEntryV5Schema.parse(row).reentry
        ?.simulation_status,
    ).toBe("simulation_blocked");
    for (const change of [
      {
        selected_evaluation_witness_ref: ref(
          "runtime.quality.candidate_simulation_execution",
        ),
      },
      {
        selected_evaluation_witness_ref: {
          ...failure,
          artifact_id: "sha256:" + "9".repeat(64),
        },
      },
      { route_id: "sha256:" + "9".repeat(64) },
      { evaluation_provenance: "retained_prior" },
      { selected_basis_role: "evaluated" },
      { comparison_reason_codes: [] },
      {
        comparison_result: "equivalent",
        predicate_provenance: "recomputed",
        comparison_reason_codes: [],
      },
      { publication_authority: true },
      { comparison_result: "different" },
    ]) {
      expect(
        runCandidateSimulationAcquisitionHistoryEntryV5Schema.safeParse({
          ...row,
          ...change,
        }).success,
      ).toBe(false);
    }
    for (const field of [
      "route_receipt_ref",
      "candidate_action_ref",
      "candidate_source_ref",
      "reentry_receipt_ref",
    ] as const) {
      const changed = {
        ...reentry,
        [field]: {
          ...reentry[field],
          manifest_profile_sha256: "sha256:" + "e".repeat(64),
        },
      };
      expect(
        runCandidateSimulationAcquisitionHistoryEntryV5Schema.safeParse({
          ...row,
          reentry: changed,
        }).success,
      ).toBe(false);
    }
    const { retainedAcquisitionHistoryFixture } =
      await import("@/test/fixtures/retainedAcquisitionHistory");
    const fresh = retainedAcquisitionHistoryFixture().retained_evaluation;
    const freshRow = {
      ...row,
      selected_basis_ref: fresh.basis_ref,
      selected_evaluation_witness_ref: fresh.n5_execution_ref,
      selected_basis_role: "evaluated",
      selected_basis_provenance: "recomputed",
      selected_evaluation: fresh,
      evaluation_provenance: "new_execution",
      reentry: {
        ...reentry,
        simulation_status: "joint_simulated",
        n4_source_ref: fresh.n4_source_ref,
        context_job_ref: fresh.context_job_ref,
        n5_input_ref: fresh.n5_input_ref,
        n5_execution_ref: fresh.n5_execution_ref,
        n5_result_ref: fresh.n5_result_ref,
      },
    };
    const freshResult =
      runCandidateSimulationAcquisitionHistoryEntryV5Schema.parse(freshRow);
    expect(freshResult.comparison_result).toBe("not_established");
    expect(freshResult.evaluation_provenance).toBe("new_execution");
  });
});

describe("candidate retained terminal wire", () => {
  it("preserves the selected prior evaluation and refuses invented equivalence", async () => {
    const { runCandidateSimulationAcquisitionHistoryEntryV5Schema } =
      await import("./validators");
    const { retainedAcquisitionHistoryFixture } =
      await import("@/test/fixtures/retainedAcquisitionHistory");
    const ref = (kind: string) => ({
      artifact_id: "sha256:" + "1".repeat(64),
      kind,
      media_type: "application/json",
      manifest_profile_sha256: "sha256:" + "f".repeat(64),
    });
    const prior = retainedAcquisitionHistoryFixture().retained_evaluation;
    const cheap = {
      source_cycle_index: prior.cycle_index,
      candidate_id: prior.candidate_id,
      candidate_content_hash: prior.candidate_content_hash,
      grounding_status: "grounding_gap",
      grounding_current_valid: false,
      value_status: "value_blocked",
      value_decision_grade: "blocked",
      value_authority_blockers: ["current_grounding_gap"],
      value_ref: null,
      voi_next_action: "stop",
      voi_reason: "resource_budget_exhausted",
      terminal_kind: "budget_exhausted",
      refinement_decision: "stop",
      search_iteration_status: "stopped",
      current_planner_report_ref: null,
      scope: "current_cheap_consequences_at_recorded_action",
      numerical_provenance: "retained_prior",
    };
    const row = {
      schema_version:
        "policyos.runtime.run_candidate_simulation_acquisition_history.v5",
      route_receipt_ref: ref("runtime_quality.acquisition_route_loop_receipt"),
      route_id: "sha256:" + "2".repeat(64),
      action_generation: 2,
      terminal_outcome: "candidate_evaluation_retained",
      candidate_action_ref: ref(
        "runtime_quality.acquisition_candidate_action_receipt",
      ),
      candidate_source_ref: ref("runtime.quality.candidate_acquisition_source"),
      evaluation_decision_ref: ref(
        "runtime_quality.acquisition_evaluation_decision",
      ),
      current_basis_ref: ref("runtime_quality.acquisition_evaluation_basis"),
      selected_basis_ref: prior.basis_ref,
      selected_evaluation_witness_ref: prior.n5_execution_ref,
      comparison_result: "equivalent",
      predicate_provenance: "recomputed",
      comparison_reason_codes: [],
      selected_basis_role: "evaluated",
      current_basis_provenance: "recomputed",
      selected_basis_provenance: "recomputed",
      current_basis_limitations: ["candidate_only"],
      selected_basis_limitations: ["candidate_only"],
      frontier_ref: "sha256:" + "6".repeat(64),
      frontier_revision: 2,
      frontier_selection: "selected",
      selected_evaluation: prior,
      selected_n5_observation: null,
      reentry: null,
      current_continuation_ref: ref(
        "runtime_quality.candidate_acquisition_retained_continuation",
      ),
      current_cheap_consequences: cheap,
      evaluation_provenance: "retained_prior",
      observed_admission: false,
      currentness_status: "not_established",
      authority_purpose: "candidate_observation_only",
      publication_authority: false,
    };
    const parsed =
      runCandidateSimulationAcquisitionHistoryEntryV5Schema.parse(row);
    expect(parsed.selected_evaluation?.n5_execution_ref).toEqual(
      prior.n5_execution_ref,
    );
    expect(parsed.current_cheap_consequences?.value_status).toBe(
      "value_blocked",
    );
    for (const change of [
      {
        comparison_result: "not_established",
        predicate_provenance: "not_established",
      },
      { current_continuation_ref: null },
      { comparison_reason_codes: ["invented"] },
      {
        selected_evaluation_witness_ref: ref(
          "runtime.quality.candidate_simulation_execution",
        ),
      },
      { current_cheap_consequences: { ...cheap, candidate_id: "foreign" } },
    ]) {
      expect(
        runCandidateSimulationAcquisitionHistoryEntryV5Schema.safeParse({
          ...row,
          ...change,
        }).success,
      ).toBe(false);
    }
  });
});
