import type {
  CycleBoardProjectionPacket,
  DepthNDomainRunProjection,
} from "@polisyos/runtime-api-client";

/** Source-shaped depth-N row for tests and stories that do not own a producer. */
export function depthNDomainRunFixture(
  overrides: Partial<DepthNDomainRunProjection> = {},
): DepthNDomainRunProjection {
  const runId = overrides.generation_cycle_run_id ?? "generation-cycle-fixture";
  return {
    acquisition_economics: null,
    acquisition_route: null,
    design_problem: {
      authority_profile: {
        mandate: "review the recorded owner projection",
        requested_authority_level: "research",
        requester_authority: "fixture.owner",
      },
      candidate_lever_space: {},
      design_problem_id: `design-problem-${runId}`,
      domain: "fixture",
      evidence_acquisition_needs: {},
      jurisdiction_time: {
        as_of: "2026-07-29T10:00:00Z",
        data_time: "2026-07-29T10:00:00Z",
        policy_time: "2026-07-29T10:00:00Z",
        region: "fixture-region",
        valid_time: "2026-07-29T10:00:00Z",
      },
      nl_provenance: {
        raw_request: `Review ${runId}`,
        source_surface: "fixture",
      },
      outcome_of_interest: {
        direction: "maximize",
        estimand: "fixture estimand",
        metric_id: "fixture.metric",
        target_variable: "fixture_target",
      },
      problem_statement: `Fixture problem for ${runId}`,
      schema_version: "policyos.runtime.design_problem.v1",
    },
    design_problem_ref: `design-problem://${runId}`,
    domain_role: "fixture_only",
    evidence_class: "fixture_only",
    evidence_witness: { availability: "artifact_missing" },
    generation_cycle_run_id: runId,
    search_terminal_kind: "acquisition_required",
    terminal_distribution: { fixture_only: 1 },
    weakest_links: [],
    ...overrides,
  };
}

function absent(
  reason: string,
  ownerRoute: string,
  availability:
    | "artifact_missing"
    | "invalid_source"
    | "not_established" = "not_established",
) {
  return {
    availability,
    owner_route: ownerRoute,
    reason,
  } as const;
}

function available<T>(value: T, sourceRef: string, sourceAsOf?: string) {
  return {
    availability: "available" as const,
    source_as_of: sourceAsOf,
    source_ref: sourceRef,
    value,
  };
}

function capstoneRow(
  role: "first_vertical" | "education" | "unseen",
  index: number,
) {
  const ownerRef = `artifact://n10/${role}`;
  const plannerReportContentHash = `sha256:planner-${role}`;
  const route =
    role === "education"
      ? absent(
          "the owner records an estimand-binding refusal, not an acquisition route",
          "GY-N13a",
        )
      : available(
          {
            owner_content_hash: `sha256:owner-${role}`,
            owner_schema: "policyos.runtime.acquisition_route_ref.v1",
            planner_report_content_hash: plannerReportContentHash,
            requirement_gap_id: `gap-${role}`,
          },
          ownerRef,
          "2026-07-29T10:00:00Z",
        );
  return {
    acquisition_economics: available(
      {
        decision_owner_ref: `owner://${role}`,
        execution_status: absent(
          "no admitted acquisition execution receipt is bound to this row",
          "GY-N13a",
        ),
        expected_cost: available(1250 + index, ownerRef),
        expected_voi: available(0.41 + index / 100, ownerRef),
        missing_requirement_fields: [],
        next_action: `acquire-owner-data-${role}`,
        planner_report_content_hash: plannerReportContentHash,
        planner_status: "pass",
        producer_expected: "GY-N13a",
        recommended_strategy: "production_snapshot_build",
        voi_rank: available(index + 1, ownerRef),
      },
      ownerRef,
      "2026-07-29T10:00:00Z",
    ),
    acquisition_route: route,
    cohort: "n10_capstone" as const,
    design_problem: available(
      depthNDomainRunFixture({
        domain_role: role,
        generation_cycle_run_id: `generation-cycle-${role}`,
      }).design_problem,
      ownerRef,
      "2026-07-29T10:00:00Z",
    ),
    domain_role: role,
    explanation_code: `cycle_board.${role}`,
    explanation_inputs: { role },
    generation_cycle_run_id: available(`generation-cycle-${role}`, ownerRef),
    lifecycle_terminality: absent(
      "no exact producer-signed lifecycle binding exists",
      "runtime.run_summary",
    ),
    missing_link: available(
      role === "education"
        ? "method_estimand_binding_mismatch"
        : `requirement_gap_${index + 1}`,
      ownerRef,
    ),
    movement_records: [],
    responsible_slices: ["GY-N10", "DS7"],
    row_id: `n10:${role}`,
    search_terminal_kind: available("acquisition_required", ownerRef),
    stage_trace_href: absent("DS8 stage-trace route is not bound", "DS8"),
    structural_evidence_class: available(
      role === "education"
        ? "estimand_binding_refusal"
        : "owner_acquisition_route",
      ownerRef,
    ),
    surface_readiness: absent(
      "the current environment has no readiness producer",
      "DS8",
      "artifact_missing",
    ),
    weakest_links: available(
      role === "education"
        ? ["unknown_blocked", "method_estimand_binding_mismatch"]
        : [`requirement_gap_${index + 1}`, "value_world_model_record_unwired"],
      ownerRef,
    ),
  };
}

function legacyRow(index: number) {
  const rowId = `legacy:case-${String(index + 1).padStart(2, "0")}`;
  return {
    acquisition_economics: absent(
      "no persisted runtime planner result exists",
      "legacy-proving-ground",
      "artifact_missing",
    ),
    acquisition_route: absent(
      "fixture identity has no runtime route",
      "legacy-proving-ground",
      "artifact_missing",
    ),
    cohort: "legacy_fixture" as const,
    design_problem: absent(
      "legacy fixture has no canonical DesignProblem",
      "legacy-proving-ground",
      "artifact_missing",
    ),
    domain_role: `legacy-${index + 1}`,
    explanation_code: "cycle_board.legacy.runtime_absent",
    explanation_inputs: { row_id: rowId },
    generation_cycle_run_id: absent(
      "no persisted runtime result exists",
      "legacy-proving-ground",
      "artifact_missing",
    ),
    lifecycle_terminality: absent(
      "no producer-signed lifecycle result exists",
      "legacy-proving-ground",
      "artifact_missing",
    ),
    missing_link: absent(
      "legacy runtime semantics are unavailable",
      "legacy-proving-ground",
      "artifact_missing",
    ),
    movement_records: [],
    responsible_slices: ["legacy-proving-ground", "DS7"],
    row_id: rowId,
    search_terminal_kind: absent(
      "no recursive-cycle terminal exists",
      "legacy-proving-ground",
      "artifact_missing",
    ),
    stage_trace_href: absent(
      "no DS8 runtime trace exists",
      "DS8",
      "artifact_missing",
    ),
    structural_evidence_class: absent(
      "no runtime evidence witness exists",
      "legacy-proving-ground",
      "artifact_missing",
    ),
    surface_readiness: absent(
      "no readiness result exists",
      "DS8",
      "artifact_missing",
    ),
    weakest_links: absent(
      "no producer terminal blockers exist",
      "legacy-proving-ground",
      "artifact_missing",
    ),
  };
}

/** Complete known 3+13 packet for Cycle Board presentation and parity tests. */
export function cycleBoardProjectionPacketFixture(): CycleBoardProjectionPacket {
  const rows = [
    capstoneRow("first_vertical", 0),
    capstoneRow("education", 1),
    capstoneRow("unseen", 2),
    ...Array.from({ length: 13 }, (_, index) => legacyRow(index)),
  ];
  return {
    composition_manifest: [
      {
        artifact_content_hash: "sha256:n10",
        as_of: "2026-07-29T10:00:00Z",
        authoritative_for: ["recorded_depth_n_semantics"],
        availability: "available",
        freshness: {
          basis: "source_timestamp",
          observed_at: "2026-07-29T10:01:00Z",
          source_as_of: "2026-07-29T10:00:00Z",
          state: "observed",
        },
        may_not_use_for: ["lifecycle_terminality", "exhaustiveness"],
        source_dependency_hash: "sha256:n10-dependencies",
        source_id: "depth-n-cycle-board",
        source_kind: "governed_projection",
        source_ref: "artifact://n10",
      },
      {
        absence_reason: "production_data is absent in this environment",
        authoritative_for: [],
        availability: "invalid_source",
        freshness: null,
        may_not_use_for: ["current_producer_availability"],
        source_id: "n13a-acquisition-census",
        source_kind: "governed_projection",
        source_ref: "artifact://n13a",
      },
      {
        absence_reason: "the current environment has no live probe source",
        authoritative_for: [],
        availability: "invalid_source",
        freshness: null,
        may_not_use_for: ["current_live_probe_state"],
        source_id: "n13a-live-probe-journal",
        source_kind: "governed_projection",
        source_ref: "artifact://n13a-live-probe",
      },
      {
        artifact_content_hash: "sha256:legacy",
        as_of: "2026-07-29T10:00:00Z",
        authoritative_for: ["legacy_fixture_identity"],
        availability: "available",
        freshness: {
          basis: "source_timestamp",
          observed_at: "2026-07-29T10:01:00Z",
          source_as_of: "2026-07-29T10:00:00Z",
          state: "observed",
        },
        may_not_use_for: ["runtime_terminal_semantics"],
        source_dependency_hash: "sha256:legacy-dependencies",
        source_id: "legacy-proving-ground",
        source_kind: "governed_projection",
        source_ref: "artifact://legacy-proving-ground",
      },
      {
        absence_reason: "DS8 readiness producer is unavailable",
        authoritative_for: [],
        availability: "artifact_missing",
        freshness: null,
        may_not_use_for: ["surface_readiness"],
        source_id: "surface-readiness",
        source_kind: "governed_projection",
        source_ref: "artifact://ds8-readiness",
      },
      {
        artifact_content_hash: "sha256:n13b",
        authoritative_for: ["global_demonstration_status"],
        availability: "available",
        may_not_use_for: [
          "per_row_movement",
          "row_enumeration",
          "exhaustiveness",
        ],
        source_id: "n13b-global-deeper-terminal",
        source_kind: "control_plane_evidence",
        source_ref: "artifact://n13b-global",
      },
      {
        artifact_content_hash: "sha256:ds4-disposition",
        authoritative_for: ["historical_ds4_component_disposition"],
        availability: "available",
        may_not_use_for: ["current_readiness", "current_producer_availability"],
        source_id: "ds4-realized-disposition",
        source_kind: "historical_owner_record",
        source_ref: "docs://ds4-disposition",
      },
      {
        artifact_content_hash: "sha256:historical-availability",
        authoritative_for: ["historical_environment_relative_measurement"],
        availability: "available",
        may_not_use_for: ["current_readiness", "current_producer_availability"],
        source_id: "historical-producer-availability",
        source_kind: "historical_owner_record",
        source_ref: "docs://ds3-producer-availability",
      },
      ...(["first_vertical", "education", "unseen"] as const).map((role) => ({
        absence_reason: "exact signed lifecycle binding is absent",
        authoritative_for: ["run_lifecycle_terminality"],
        availability: "not_established" as const,
        may_not_use_for: [
          "status_proxy",
          "time_proxy",
          "search_terminal_proxy",
        ],
        source_id: `run-summary:generation-cycle-${role}`,
        source_kind: "run_summary_lookup" as const,
        source_ref: `run-summary:generation-cycle-${role}`,
      })),
    ],
    composition_manifest_hash: "sha256:manifest",
    intended_audiences: ["REVIEWER", "EXPERT"],
    packet_schema_version: "policyos.runtime.cycle_board_packet.v1",
    payload: {
      coverage: {
        capability_state: "absent/unallocated",
        deficits: ["artifact_missing", "bridge_missing"],
        execution_status: "not_established",
        exhaustive: false,
        known_row_count: rows.length,
        known_scope: "N10 capstone + legacy fixture cohort",
        missing_link: "production_recursive_cycle_run_enumeration",
        owner_route: "GY-GAP5 -> runtime/quality GY-N12",
        unknown_scope: "future production recursive-cycle DesignProblems",
      },
      historical_producer_availability: {
        counts: { artifact_missing: 1, available: 5, invalid_source: 7 },
        environment_absence: "production_data",
        measurement_scope: "environment_relative",
        source_content_hash: "sha256:historical-availability",
        source_ref: "docs://ds3-producer-availability",
      },
      movement_gap: {
        capability_state: "absent/unallocated",
        chronology_route: "GY-N12",
        deficits: ["artifact_missing", "bridge_missing"],
        execution_status: "not_established",
        missing_link: "acquisition_reentry_deeper_terminal_binding",
        movement_records: [],
        producer_route: "GY-GAP6 -> GY-N13b",
      },
      realized_ds4_disposition: {
        counts: { package: 27, rebind: 41, retire: 3, use_as_is: 18 },
        denominator: 89,
        source_class: "historical_ds4_component_disposition",
        source_content_hash: "sha256:ds4-disposition",
        source_ref: "docs://ds4-disposition",
      },
      rows,
    },
    projection_hash: "sha256:projection",
    projection_id: "depth-n-cycle-board",
    projection_observed_at: "2026-07-29T10:02:00Z",
    projection_rule_version: "policyos.runtime.depth_n_cycle_board.v2",
    replay_address: "cycle-board://sha256:projection",
    source_dependency_hash: "sha256:dependencies",
    stable_address: "/api/v1/exports/governed-projections/depth-n-cycle-board",
  };
}
