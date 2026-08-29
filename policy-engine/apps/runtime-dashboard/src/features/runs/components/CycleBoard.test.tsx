import { render, screen, within } from "@testing-library/react";
import type { AcquisitionGrowthProjection } from "@/features/runs/api/useAcquisitionRoutes";

import { cycleBoardProjectionPacketFixture } from "@/test/fixtures/depthNCycleBoard";

import { CycleBoard } from "./CycleBoard";

const { useAcquisitionGrowthMock } = vi.hoisted(() => ({
  useAcquisitionGrowthMock: vi.fn(),
}));

vi.mock("@/features/runs/api/useAcquisitionRoutes", () => ({
  useAcquisitionGrowth: (...args: unknown[]) =>
    useAcquisitionGrowthMock(...args),
}));

const acquisitionGrowthFixture = {
  absence_reason: null,
  as_of: "2026-08-27T12:00:00Z",
  authoritative_for: ["acquisition_gap_shape"],
  availability: "available",
  export_replay_contract: "policyos.runtime.export_replay_binding.v1",
  freshness: {
    basis: "request_observation",
    observed_at: "2026-08-27T12:00:00Z",
    source_as_of: null,
    state: "observed",
  },
  intended_audience: "REVIEWER",
  may_not_use_for: ["current_acquisition_authority"],
  packet_schema_version: "policyos.runtime.governed_projection_packet.v1",
  payload: {
    backlog: Array.from({ length: 15 }, (_, index) => ({
      authority_boundary: "ranking_only_not_voi",
      binding_confidence: 0,
      classification_basis:
        index === 7 ? "independently_reconciled" : "not_established",
      gap_class: index === 7 ? "data_gap" : "not_established",
      rank: index + 1,
      ranking_method: "interim_binding_confidence_x_route_demand",
      ranking_score: 0,
      route_demand: index < 3 ? 2 : 1,
      variable_id: index === 7 ? "government.balance" : `residual.${index + 1}`,
      voi_owner_fit: "metric_residual_granularity_not_supported",
      voi_owner_integration: "routed_to_gy_n13b",
      voi_owner_ref:
        "polisyos.runtime.quality.acquisition_planner.plan_evidence_acquisition",
    })),
    carrier_liveness: {
      carrier_disposition: "carrier_current_source_profile_mismatch",
      connector_id: "worldbank.wdi",
      execution_tier: "transport_ready",
      tier_decay_findings: [
        "execution_tier_decay:transport_ready:carrier_current_source_profile_mismatch",
      ],
    },
    n13b_history: {
      admission: "not_reached",
      attempt_count: 5,
      epoch_qualification: {
        appointment_state: "unappointed",
        appointment_would_establish:
          "authority to qualify native semantic production, append its history head and permit overlay activation",
        appointment_would_not_establish: [
          "gap shape",
          "passport validity",
          "positive delta",
          "re-entry",
        ],
        authority_owner_ref: null,
        authority_role: "semantic epoch policy-admission qualifier",
        code: "policy_admission_missing",
        epoch_state: "pending_epoch_activation",
        status: "not_established",
      },
      execution_phase: "terminal",
      overlay_epoch_count: 0,
      quarantine: "raw_terminal",
      quarantine_count: 2,
      raw_response_count: 2,
      reentry: "deeper_terminal",
      response_admitted_count: 0,
      terminal_count: 5,
      world_growth: "no_growth",
    },
    schema_version: "policyos.runtime.acquisition_growth_projection.v1",
    structural_routes: [
      {
        action_eligibility: "not_applicable",
        available_catalog_rows: 99,
        cost: 1,
        gap_class: "structural_gap",
        missing_link: "grounding_relation_missing",
        route_class: "not_a_data_gap",
        route_id: "capstone:first_vertical",
        witness_kind: "estimand_binding_refusal",
      },
    ],
    summary: {
      actual_network_call_count: 18,
      backlog_count: 15,
      family_scorecard_count: 12,
      metric_resolution_count: 124,
      selected_record_count: 144,
      structural_route_count: 3,
    },
  },
  projection_hash: "sha256:projection",
  projection_id: "acquisition-growth",
  projection_rule_version: "policyos.runtime.governed_projection.v1",
  replay_address: "/api/v1/exports/governed-projections/acquisition-growth",
  source: {
    artifact_content_hash: "sha256:source",
    declared_content_hash: null,
    related_artifact_bindings: [],
    relative_path: "acquisition-growth:N13a+N13b",
    validation: {
      bound_artifact_content_hash: "sha256:source",
      bound_dependency_aggregate_identity: "sha256:dependencies",
      bound_dependency_count: 6,
      issue_codes: [],
      semantic_projection_hash: "sha256:semantic",
      semantic_projection_hash_rule_version: "v1",
      status: "passed",
      validator_id:
        "governed_projection_validation_worker:validate_acquisition_growth",
      validator_version: "policyos.runtime.acquisition_growth_projection.v1",
    },
  },
  source_dependency_hash: "sha256:dependencies",
  source_rule_version: "GY-plan-rev18+3.5.12-D1-D6",
  source_schema_version: "policyos.runtime.acquisition_growth_projection.v1",
  stable_address: "/api/v1/exports/governed-projections/acquisition-growth",
} as const;

vi.mock("@/shared/i18n/LocaleProvider", () => {
  const t = (key: string, values?: Record<string, unknown>) => {
    if (key === "pages.cycleBoard.acquisition.backlog.title") {
      return "Interim residual ordering — ranking only, not VOI";
    }
    if (key === "pages.cycleBoard.acquisition.backlog.zeroScoreBasis") {
      return `${String(values?.scoreCount)} of ${String(values?.total)} ranking scores are 0.0; ${String(values?.confidenceCount)} of ${String(values?.total)} binding-confidence values are 0.0`;
    }
    if (key === "pages.cycleBoard.acquisition.quarantine.counts") {
      return `${String(values?.raw)} raw responses · ${String(values?.admitted)} admitted`;
    }
    return key;
  };
  return {
    useI18n: () => ({ t }),
    useOptionalI18n: () => ({ t }),
  };
});

function projectionFixture() {
  const packet = cycleBoardProjectionPacketFixture();
  return {
    packet,
    payload: packet.payload,
    rawPacketBytes: new TextEncoder().encode(JSON.stringify(packet)),
  };
}

function growthProjectionFixture(): AcquisitionGrowthProjection {
  const packet =
    acquisitionGrowthFixture as unknown as AcquisitionGrowthProjection["packet"];
  return {
    packet,
    payload: packet.payload,
    rawPacketBytes: new TextEncoder().encode(JSON.stringify(packet)),
  };
}

function growthProjectionAt(asOf: string): AcquisitionGrowthProjection {
  const opening = growthProjectionFixture();
  const packet: AcquisitionGrowthProjection["packet"] = {
    ...opening.packet,
    as_of: asOf,
    freshness: { ...opening.packet.freshness, observed_at: asOf },
  };
  return {
    packet,
    payload: packet.payload,
    rawPacketBytes: new TextEncoder().encode(JSON.stringify(packet)),
  };
}

describe("CycleBoard honest hero rendering", () => {
  beforeEach(() => {
    useAcquisitionGrowthMock.mockReset();
    useAcquisitionGrowthMock.mockReturnValue({
      data: undefined,
      isError: true,
      isLoading: false,
    });
  });

  it("renders acquisition refusals and owner limits without laundering a structural route", () => {
    render(
      <CycleBoard
        acquisitionGrowth={growthProjectionFixture()}
        projection={projectionFixture()}
      />,
    );

    expect(screen.getByTestId("acquisition-growth-backlog")).toHaveTextContent(
      /15 of 15.*ranking scores.*0\.0/iu,
    );
    expect(screen.getByTestId("acquisition-growth-backlog")).toHaveTextContent(
      "metric_residual_granularity_not_supported",
    );
    expect(screen.getByTestId("acquisition-growth-backlog")).toHaveTextContent(
      /ranking only, not VOI/iu,
    );
    expect(
      screen.getByTestId("connector-acquisition-scorecard"),
    ).toHaveTextContent("carrier_current_source_profile_mismatch");
    expect(
      screen.getByTestId("connector-acquisition-scorecard"),
    ).not.toHaveTextContent(/healthy/iu);
    expect(
      screen.getByTestId("acquisition-quarantine-ledger"),
    ).toHaveTextContent(/2 raw responses.*0 admitted/iu);
    expect(screen.getByTestId("acquisition-passport-panel")).toHaveTextContent(
      "pending_epoch_activation",
    );
    expect(screen.getByTestId("acquisition-passport-panel")).toHaveTextContent(
      "policy_admission_missing",
    );
    expect(screen.getByTestId("acquisition-passport-panel")).toHaveTextContent(
      /unappointed.*semantic epoch policy-admission qualifier/iu,
    );

    const structural = screen.getByTestId(
      "acquisition-structural-route-capstone:first_vertical",
    );
    expect(structural).toHaveTextContent("not_a_data_gap");
    expect(structural).toHaveTextContent("not_applicable");
    expect(within(structural).queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders all known rows and the board's own two typed absences", () => {
    const projection = projectionFixture();
    const { packet } = projection;

    render(
      <CycleBoard
        acquisitionGrowth={growthProjectionFixture()}
        projection={projection}
      />,
    );

    const board = screen.getByTestId("cycle-board");
    expect(board).toHaveAttribute("data-audiences", "REVIEWER,EXPERT");
    expect(board).not.toHaveAttribute(
      "data-audiences",
      expect.stringContaining("PUBLIC"),
    );
    const rows = screen.getAllByTestId("cycle-board-row");
    expect(rows).toHaveLength(16);
    expect(rows.slice(0, 3).map((row) => row.dataset.rowId)).toEqual([
      "n10:first_vertical",
      "n10:education",
      "n10:unseen",
    ]);
    expect(rows.slice(3).map((row) => row.dataset.rowId)).toEqual(
      Array.from(
        { length: 13 },
        (_, index) => `legacy:case-${String(index + 1).padStart(2, "0")}`,
      ),
    );

    const coverage = screen.getByTestId("cycle-board-coverage-gap");
    expect(coverage).toHaveTextContent(
      "production_recursive_cycle_run_enumeration",
    );
    expect(coverage).toHaveTextContent("not_established");
    expect(coverage).toHaveTextContent("GY-GAP5 -> runtime/quality GY-N12");
    expect(coverage).toHaveAttribute("data-exhaustive", "false");
    expect(coverage).toHaveAttribute("data-known-row-count", "16");

    const movement = screen.getByTestId("cycle-board-movement-gap");
    expect(movement).toHaveTextContent(
      "acquisition_reentry_deeper_terminal_binding",
    );
    expect(movement).toHaveTextContent("not_established");
    expect(movement).toHaveTextContent("GY-GAP6 -> GY-N13b");
    expect(screen.queryAllByTestId("cycle-board-movement")).toHaveLength(0);
  });

  it("renders owner route references and separately resolved economics", () => {
    const projection = projectionFixture();

    render(
      <CycleBoard
        acquisitionGrowth={growthProjectionFixture()}
        projection={projection}
      />,
    );

    const firstRow = screen.getAllByTestId("cycle-board-row")[0];
    const educationRow = screen.getAllByTestId("cycle-board-row")[1];
    if (!firstRow || !educationRow) {
      throw new Error("fixture must render the ordered capstone cohort");
    }
    const route = within(firstRow).getByTestId("cycle-board-acquisition-route");
    const economics = within(firstRow).getByTestId(
      "cycle-board-acquisition-economics",
    );
    expect(route).toHaveTextContent("sha256:owner-first_vertical");
    expect(route).toHaveTextContent("gap-first_vertical");
    expect(economics).toHaveTextContent("production_snapshot_build");
    expect(economics).toHaveTextContent("1250");
    expect(economics).toHaveTextContent("0.41");
    expect(economics).toHaveTextContent("not_established");

    expect(
      within(educationRow).getByTestId("cycle-board-acquisition-route"),
    ).toHaveAttribute("data-availability", "not_established");
    expect(
      within(educationRow).getByTestId("cycle-board-acquisition-economics"),
    ).toHaveTextContent("production_snapshot_build");
  });

  it("renders absent lifecycle terminality as absent, never false", () => {
    const projection = projectionFixture();

    render(
      <CycleBoard
        acquisitionGrowth={growthProjectionFixture()}
        projection={projection}
      />,
    );

    const firstRow = screen.getAllByTestId("cycle-board-row")[0];
    if (!firstRow) {
      throw new Error("fixture must render its first capstone row");
    }
    const lifecycle = within(firstRow).getByTestId(
      "cycle-board-lifecycle-terminality",
    );
    const searchTerminal = within(firstRow).getByTestId(
      "cycle-board-search-terminal",
    );
    expect(lifecycle).toHaveAttribute("data-availability", "not_established");
    expect(lifecycle).not.toHaveTextContent(/false|non.?terminal/iu);
    expect(searchTerminal).toHaveTextContent("acquisition_required");
    expect(searchTerminal).not.toHaveTextContent("not_established");
  });

  it("renders every source's own state and never invents board-global freshness", () => {
    const projection = projectionFixture();
    const { packet } = projection;

    render(
      <CycleBoard
        acquisitionGrowth={growthProjectionFixture()}
        projection={projection}
      />,
    );

    const sources = screen.getAllByTestId("cycle-board-source");
    expect(sources).toHaveLength(packet.composition_manifest.length);
    expect(sources.map((source) => source.dataset.sourceId)).toEqual(
      packet.composition_manifest.map((source) => source.source_id),
    );
    expect(sources[0]).toHaveTextContent("2026-07-29T10:00:00Z");
    expect(sources[0]).toHaveTextContent("source_timestamp");
    expect(sources[0]).toHaveTextContent("observed");
    expect(sources[1]).toHaveAttribute("data-availability", "invalid_source");
    expect(sources[4]).toHaveAttribute("data-availability", "artifact_missing");
    expect(
      screen.queryByTestId("cycle-board-global-freshness"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        /^(?:current|fresh|up[- ]to[- ]date|board (?:is )?(?:current|fresh|up[- ]to[- ]date))$/iu,
      ),
    ).not.toBeInTheDocument();
  });

  it("keeps packet time attached through the production growth bridge", () => {
    const projection = projectionFixture();
    useAcquisitionGrowthMock.mockReturnValue({
      data: growthProjectionAt("2026-08-29T12:00:00Z"),
      isError: false,
      isLoading: false,
    });
    const { rerender } = render(<CycleBoard projection={projection} />);
    const semanticsIds = [
      "acquisition-growth-boundary-time-semantics",
      "acquisition-growth-time-semantics",
      "connector-acquisition-time-semantics",
      "acquisition-quarantine-time-semantics",
      "acquisition-passport-time-semantics",
      "acquisition-backlog-time-semantics",
    ] as const;
    for (const testId of semanticsIds) {
      expect(
        within(screen.getByTestId(testId)).getByTestId(
          "time-semantics-payload-as-of",
        ),
      ).toHaveTextContent("2026-08-29T12:00:00Z");
    }

    useAcquisitionGrowthMock.mockReturnValue({
      data: growthProjectionAt("2026-08-29T13:00:00Z"),
      isError: false,
      isLoading: false,
    });
    rerender(<CycleBoard projection={projection} />);
    for (const testId of semanticsIds) {
      expect(
        within(screen.getByTestId(testId)).getByTestId(
          "time-semantics-payload-as-of",
        ),
      ).toHaveTextContent("2026-08-29T13:00:00Z");
    }
  });

  it("renders an unavailable acquisition query as a temporal nonreceipt", () => {
    render(<CycleBoard projection={projectionFixture()} />);

    const refusal = screen.getByTestId("acquisition-growth-unavailable");
    expect(refusal).toBeInTheDocument();
    const semantics = screen.getByTestId(
      "acquisition-growth-boundary-time-semantics",
    );
    expect(
      within(semantics).getByTestId("time-semantics-epoch-status"),
    ).toHaveTextContent("epochChrome.status.not_established");
    expect(
      within(semantics).getByTestId("time-semantics-validity"),
    ).toHaveTextContent("epochChrome.status.not_established");
  });
});
