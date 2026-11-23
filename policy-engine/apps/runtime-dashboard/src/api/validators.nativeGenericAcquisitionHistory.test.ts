import actualPartialCapacityRunDetails from "./__fixtures__/partial-capacity-run-details.json";
import { normalizeGenericCycleSimulation } from "@/features/runs/domain/genericCycleSimulation";
import { runDetailsSchema } from "./validators";

const WORLD_HASH = "sha256:" + "a".repeat(64);

const REF_KINDS = {
  route_receipt_ref: "runtime_quality.acquisition_route_loop_receipt",
  reentry_receipt_ref: "runtime_quality.acquisition_overlay_reentry_receipt",
  source_compiled_ref: "runtime.compiled_recursive_generation_cycle",
  pending_action_phase_ref: "runtime_quality.acquisition_route_phase_receipt",
  native_world_checkpoint_ref:
    "runtime_quality.acquisition_candidate_world_checkpoint",
  native_input_collection_ref:
    "runtime_quality.native_derivation_input_checkpoint",
  original_generic_input_ref:
    "runtime.quality.generic_cycle_simulation_n5_input",
  original_profile_ref: "runtime.quality.generic_cycle_simulation_profile",
  context_job_ref: "runtime.quality.cycle_substrate_context_job",
  n4_source_ref: "runtime.generation_source_handoff",
  n5_input_ref: "runtime.quality.generic_cycle_simulation_n5_input",
  n5_execution_ref: "runtime.quality.generic_cycle_simulation_n5_execution",
  n5_result_ref: "polisyos.runtime.joint_simulation_result",
  prepared_checkpoint_ref: "runtime_quality.native_source_reentry_checkpoint",
  n5_completed_checkpoint_ref:
    "runtime_quality.native_source_reentry_checkpoint",
  cycle_completed_checkpoint_ref:
    "runtime_quality.native_source_reentry_checkpoint",
} as const;

type HistoryPosition = "candidate_simulation" | "generic_cycle_simulation";
type MutableRecord = Record<string, unknown>;

function record(value: unknown): MutableRecord {
  if (value == null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("expected object fixture");
  }
  return value as MutableRecord;
}

function digest(character: string): string {
  return "sha256:" + character.repeat(64);
}

function nativeGenericHistoryFixture(requestProfileVersion = "v5") {
  const refsByName: Record<string, MutableRecord> = Object.fromEntries(
    Object.entries(REF_KINDS).map(([name, kind], index) => {
      const character = "0123456789abcdef"[index]!;
      const selected = digest(character);
      return [
        name,
        {
          artifact_id: selected,
          kind,
          media_type: "application/json",
          manifest_profile_sha256: selected,
        },
      ];
    }),
  );
  const n5ResultRef = refsByName.n5_result_ref;
  if (n5ResultRef == null) {
    throw new TypeError("native history fixture omitted n5_result_ref");
  }

  return {
    schema_version:
      "policyos.runtime.run_native_generic_acquisition_history.v1",
    source_job_id: "source-job-1",
    action_job_id: "action-job-2",
    candidate_id: "candidate-native-1",
    route_id: digest("c"),
    action_generation: 3,
    ...refsByName,
    source_cycle_index: 4,
    continued_cycle_index: 5,
    original_profile_selection_ref: digest("d"),
    current_profile_selection_ref: digest("e"),
    world_model_record_content_hash: WORLD_HASH,
    terminal_outcome: "reentry_completed",
    n5_input_schema_version:
      "policyos.runtime.generic_cycle_simulation_n5_input.v2",
    request_profile_schema_version: `policyos.runtime.generic_cycle_n5_request_profile.${requestProfileVersion}`,
    n5_execution_schema_version:
      "policyos.runtime.generic_cycle_simulation_n5_execution.v3",
    n5_owner_join_status: "resolved",
    simulation_status: "joint_simulated",
    simulation_authority_blockers: [],
    simulation_result_body: {
      schema_version:
        "policyos.runtime.run_generic_cycle_simulation_n5_result_body.v1",
      artifact_ref: { ...n5ResultRef },
      artifact_schema_name: "policyos.runtime.n5.joint_simulation_result",
      artifact_schema_version: "5.0.0",
      result_schema_version: "policyos.runtime.joint_simulation_horizon.v5",
      selected_manifest_profile_sha256: n5ResultRef.manifest_profile_sha256,
      world_model_record_ref: "world-model://native-history-test",
      world_model_record_content_hash: WORLD_HASH,
      atom_ids: ["atom-configured"],
      selected_outcomes: ["government.balance"],
      horizon: {
        start: 0,
        end: 1,
        step: 1,
        valid_time_role: "policy_horizon",
        transaction_time_role: "recorded_at",
        scenario_branch_policy: "selected_branch_only",
      },
      trajectories: [
        {
          run_level: "joint",
          atom_ids: ["atom-configured"],
          points: [
            {
              step: 0,
              outcomes: { "government.balance": 0.25 },
              effects: { "government.balance": 0 },
            },
            {
              step: 1,
              outcomes: { "government.balance": 0.3 },
              effects: { "government.balance": 0.05 },
            },
          ],
        },
      ],
      uncertainty_kind: "K_sim",
      authority_purpose: "cycle_input_candidate_only",
      candidate_status: "candidate_unverified",
      currentness_status: "not_established",
      publication_authority: false,
    },
    limitations: [
      "simulation_only_k_sim_not_world_evidence",
      "historical_native_reentry_not_current_permission",
    ],
    currentness_status: "not_established",
    authority_purpose: "candidate_observation_only",
    publication_authority: false,
  };
}

function blockedNativeGenericHistoryFixture() {
  const selectedRef = (kind: string, id: string, profile: string) => ({
    artifact_id: digest(id),
    kind,
    media_type: "application/json",
    manifest_profile_sha256: digest(profile),
  });

  return {
    schema_version:
      "policyos.runtime.run_native_generic_blocked_acquisition_history.v1",
    source_job_id: "source-job-1",
    action_job_id: "action-job-3",
    candidate_id: "candidate-native-1",
    route_id: digest("c"),
    action_generation: 4,
    route_receipt_ref: selectedRef(REF_KINDS.route_receipt_ref, "a", "b"),
    reentry_receipt_ref: selectedRef(REF_KINDS.reentry_receipt_ref, "c", "d"),
    source_compiled_ref: selectedRef(REF_KINDS.source_compiled_ref, "2", "2"),
    pending_action_phase_ref: selectedRef(
      REF_KINDS.pending_action_phase_ref,
      "e",
      "f",
    ),
    source_cycle_index: 5,
    continued_cycle_index: 6,
    terminal_outcome: "reentry_completed",
    terminal_kind: "acquisition_required",
    simulation_status: "simulation_blocked",
    scheduler_action: "defer",
    blocker_code: "budget_exhausted_for_next_level",
    numerical_result_status: "not_established",
    currentness_status: "not_established",
    authority_purpose: "candidate_observation_only",
    publication_authority: false,
  };
}

function responseWithNativeHistory(
  position: HistoryPosition,
  history: MutableRecord[] = [nativeGenericHistoryFixture()],
): MutableRecord {
  const payload = structuredClone(
    actualPartialCapacityRunDetails,
  ) as unknown as MutableRecord;
  const run = record(payload.run);

  if (position === "candidate_simulation") {
    run.candidate_simulation = {
      schema_version: "policyos.runtime.run_candidate_simulation_projection.v1",
      run_id: run.run_id,
      artifact_status: "resolved",
      authority_purpose: "candidate_observation_only",
      publication_authority: false,
      source_ref: {
        artifact_id: digest("f"),
        kind: "runtime.compiled_recursive_generation_cycle",
        media_type: "application/json",
        manifest_profile_sha256: digest("e"),
      },
      source_content_hash: WORLD_HASH,
      acquisition_history: history,
      acquisition_history_limitation_code: null,
    };
  } else {
    const projection = record(run.generic_cycle_simulation);
    projection.acquisition_history = history;
    projection.acquisition_history_limitation_code = null;
  }

  return payload;
}

function historyRow(payload: MutableRecord, position: HistoryPosition) {
  const run = record(payload.run);
  const projection = record(run[position]);
  const history = projection.acquisition_history;
  if (!Array.isArray(history) || history.length !== 1) {
    throw new TypeError("expected one native history row");
  }
  return record(history[0]);
}

const expectedNativeHistory = {
  schema_version: "policyos.runtime.run_native_generic_acquisition_history.v1",
  simulation_result_body: {
    world_model_record_content_hash: WORLD_HASH,
    trajectories: [
      {
        points: [
          { outcomes: { "government.balance": 0.25 } },
          { outcomes: { "government.balance": 0.3 } },
        ],
      },
    ],
  },
  limitations: [
    "simulation_only_k_sim_not_world_evidence",
    "historical_native_reentry_not_current_permission",
  ],
  simulation_authority_blockers: [],
  currentness_status: "not_established",
  authority_purpose: "candidate_observation_only",
  publication_authority: false,
};

const invalidNativeHistoryMutations: Array<
  [string, (row: MutableRecord) => void]
> = [
  [
    "a missing selected profile",
    (row) => {
      delete record(row.route_receipt_ref).manifest_profile_sha256;
    },
  ],
  [
    "a mismatched result body",
    (row) => {
      record(row.simulation_result_body).world_model_record_content_hash =
        digest("f");
    },
  ],
  [
    "a mismatched result profile",
    (row) => {
      const body = record(row.simulation_result_body);
      const artifactRef = record(body.artifact_ref);
      artifactRef.manifest_profile_sha256 = digest("f");
      body.selected_manifest_profile_sha256 = digest("f");
      expect(body.artifact_ref).not.toEqual(row.n5_result_ref);
    },
  ],
  [
    "publication authority",
    (row) => {
      row.publication_authority = true;
    },
  ],
  [
    "an empty blocker",
    (row) => {
      row.simulation_authority_blockers = [""];
    },
  ],
];

describe("Native Generic acquisition history wire", () => {
  it.each(["v4", "v5"] as const)(
    "accepts Native history in both projection unions and normalizes Generic with request profile %s",
    (profileVersion) => {
      const candidatePayload = responseWithNativeHistory(
        "candidate_simulation",
      );
      historyRow(
        candidatePayload,
        "candidate_simulation",
      ).request_profile_schema_version =
        `policyos.runtime.generic_cycle_n5_request_profile.${profileVersion}`;

      const candidateParsed = runDetailsSchema.parse(candidatePayload);
      const candidateProjection = record(
        candidateParsed.run.candidate_simulation,
      );
      expect(candidateProjection.acquisition_history).toMatchObject([
        expectedNativeHistory,
      ]);

      const genericPayload = responseWithNativeHistory(
        "generic_cycle_simulation",
      );
      historyRow(
        genericPayload,
        "generic_cycle_simulation",
      ).request_profile_schema_version =
        `policyos.runtime.generic_cycle_n5_request_profile.${profileVersion}`;

      const genericParsed = runDetailsSchema.parse(genericPayload);
      const projection = genericParsed.run.generic_cycle_simulation;
      expect(record(projection).acquisition_history).toMatchObject([
        expectedNativeHistory,
      ]);
      const normalized = normalizeGenericCycleSimulation(
        genericParsed.run.run_id,
        projection,
      );
      expect(normalized.kind).toBe("candidate_only");
    },
  );

  it.each(["candidate_simulation", "generic_cycle_simulation"] as const)(
    "accepts a budget-deferred row alongside successful Native history in %s",
    (position) => {
      const blocked = blockedNativeGenericHistoryFixture();
      const payload = responseWithNativeHistory(position, [
        nativeGenericHistoryFixture(),
        blocked,
      ]);

      const parsed = runDetailsSchema.parse(payload);
      const projection = record(parsed.run[position]);

      expect(projection.acquisition_history).toMatchObject([
        expectedNativeHistory,
        blocked,
      ]);
      expect(
        (projection.acquisition_history as unknown[])[1],
      ).not.toHaveProperty("simulation_result_body");
    },
  );

  const invalidBlockedHistory: Array<[string, (row: MutableRecord) => void]> = [
    [
      "a missing pending phase profile",
      (row) => {
        delete record(row.pending_action_phase_ref).manifest_profile_sha256;
      },
    ],
    [
      "the wrong receipt kind",
      (row) => {
        record(row.reentry_receipt_ref).kind = REF_KINDS.route_receipt_ref;
      },
    ],
    [
      "a numerical result from a successful row",
      (row) => {
        row.simulation_result_body =
          nativeGenericHistoryFixture().simulation_result_body;
      },
    ],
    [
      "a non-adjacent continued cycle",
      (row) => {
        row.continued_cycle_index = 7;
      },
    ],
    [
      "publication authority",
      (row) => {
        row.publication_authority = true;
      },
    ],
  ];

  it.each(invalidBlockedHistory)(
    "rejects budget-deferred history with %s",
    (_label, mutate) => {
      const position = "generic_cycle_simulation";
      const payload = responseWithNativeHistory(position, [
        blockedNativeGenericHistoryFixture(),
      ]);
      mutate(historyRow(payload, position));
      expect(runDetailsSchema.safeParse(payload).success).toBe(false);
    },
  );

  it.each(invalidNativeHistoryMutations)(
    "rejects Native history with %s",
    (_label, mutate) => {
      const payload = responseWithNativeHistory("generic_cycle_simulation");
      const row = historyRow(payload, "generic_cycle_simulation");
      mutate(row);
      expect(runDetailsSchema.safeParse(payload).success).toBe(false);
    },
  );

  it("rejects duplicate limitations while both required codes remain present", () => {
    const payload = responseWithNativeHistory("generic_cycle_simulation");
    const row = historyRow(payload, "generic_cycle_simulation");
    const limitations = [
      "simulation_only_k_sim_not_world_evidence",
      "historical_native_reentry_not_current_permission",
      "simulation_only_k_sim_not_world_evidence",
    ];
    row.limitations = limitations;
    expect(limitations).toContain("simulation_only_k_sim_not_world_evidence");
    expect(limitations).toContain(
      "historical_native_reentry_not_current_permission",
    );
    expect(limitations.length - new Set(limitations).size).toBe(1);
    expect(runDetailsSchema.safeParse(payload).success).toBe(false);
  });
});
