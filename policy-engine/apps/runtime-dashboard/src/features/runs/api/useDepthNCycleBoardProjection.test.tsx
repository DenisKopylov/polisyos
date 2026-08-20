import type {
  ArtifactMissingGovernedProjectionPacket,
  AvailableGovernedProjectionPacket,
  CycleBoardProjectionPacket,
  InvalidGovernedProjectionPacket,
  ProjectionSourceIdentity,
} from "@polisyos/runtime-api-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import { queryKeys } from "@/api/queryKeys";

import {
  depthNCycleBoardHeroProjectionQueryOptions,
  depthNCycleBoardHeroProjectionQueryPolicy,
  depthNCycleBoardProjectionQueryOptions,
  narrowDepthNCycleBoardHeroProjection,
  narrowDepthNCycleBoardProjection,
  useDepthNCycleBoardProjection,
} from "./useDepthNCycleBoardProjection";

const SOURCE: ProjectionSourceIdentity = {
  artifact_content_hash: "sha256:source",
  declared_content_hash: "sha256:source",
  related_artifact_bindings: [],
  relative_path: "artifacts/depth-n-cycle-board.json",
  validation: {
    bound_artifact_content_hash: "sha256:source",
    bound_dependency_aggregate_identity: "sha256:dependencies",
    bound_dependency_count: 2,
    issue_codes: [],
    semantic_projection_hash: "sha256:projection",
    semantic_projection_hash_rule_version: "depth-n.semantic.v1",
    status: "passed",
    validator_id: "depth-n-owner-validator",
    validator_version: "1",
  },
};

const FRESHNESS = {
  basis: "source_timestamp",
  observed_at: "2026-07-29T10:05:00Z",
  source_as_of: "2026-07-29T10:00:00Z",
  state: "observed",
} as const;

function domainRun(runId: string) {
  return {
    acquisition_economics: null,
    acquisition_route: null,
    design_problem: {
      authority_profile: {
        mandate: "review the recorded owner projection",
        requested_authority_level: "research" as const,
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
        direction: "maximize" as const,
        estimand: "fixture estimand",
        metric_id: "fixture.metric",
        target_variable: "fixture_target",
      },
      problem_statement: `Fixture problem for ${runId}`,
      schema_version: "policyos.runtime.design_problem.v1",
    },
    design_problem_ref: `design-problem://${runId}`,
    domain_role: "legal",
    evidence_class: "owner_evidence_extension",
    evidence_witness: { ref: `evidence://${runId}` },
    generation_cycle_run_id: runId,
    search_terminal_kind: "acquisition_required",
    terminal_distribution: { owner_terminal_extension: 0.7 },
    weakest_links: [`owner weakest link for ${runId}`],
  };
}

function availablePacket(): AvailableGovernedProjectionPacket {
  return {
    as_of: "2026-07-29T10:00:00Z",
    authoritative_for: ["depth_n_cycle_board_projection"],
    availability: "available",
    export_replay_contract: "policyos.runtime.export_replay_binding.v1",
    freshness: FRESHNESS,
    intended_audience: "EXPERT",
    may_not_use_for: ["run_closeout"],
    packet_schema_version: "policyos.runtime.governed_projection_packet.v1",
    payload: {
      depth_evidence: { status: "owner-supplied" },
      domain_runs: {
        "global-domain-a": domainRun("generation-cycle-a"),
        "global-domain-b": domainRun("generation-cycle-b"),
      },
      terminal_distributions: {
        global: { owner_terminal_extension: 0.7 },
      },
    },
    projection_hash: "sha256:projection",
    projection_id: "depth-n-cycle-board",
    projection_rule_version: "policyos.runtime.governed_projection.v1",
    replay_address: "projection://depth-n-cycle-board",
    source: SOURCE,
    source_dependency_hash: "sha256:dependencies",
    source_rule_version: "depth-n.rule.v1",
    source_schema_version: "depth-n.schema.v1",
    stable_address: "projection://depth-n-cycle-board",
  };
}

function cycleBoardPacket(): CycleBoardProjectionPacket {
  return {
    composition_manifest: [],
    composition_manifest_hash: "sha256:composition-manifest",
    intended_audiences: ["REVIEWER", "EXPERT"],
    packet_schema_version: "policyos.runtime.cycle_board_packet.v1",
    payload: {
      coverage: {
        capability_state: "absent/unallocated",
        deficits: ["artifact_missing", "bridge_missing"],
        execution_status: "not_established",
        exhaustive: false,
        known_row_count: 0,
        known_scope: "N10 capstone + legacy fixture cohort",
        missing_link: "production_recursive_cycle_run_enumeration",
        owner_route: "GY-GAP5 -> runtime/quality GY-N12",
        unknown_scope: "future production recursive-cycle DesignProblems",
      },
      historical_producer_availability: {
        counts: { artifact_missing: 1, available: 5, invalid_source: 7 },
        environment_absence: "production_data",
        measurement_scope: "environment_relative",
        source_content_hash: "sha256:producer-availability",
        source_ref: "ds3-producer-availability",
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
        source_ref: "DS4-status-grammar-rebinding-closure.md",
      },
      rows: [],
    },
    projection_hash: "sha256:cycle-board-projection",
    projection_id: "depth-n-cycle-board",
    projection_observed_at: "2026-08-20T12:00:00Z",
    projection_rule_version: "policyos.runtime.depth_n_cycle_board.v2",
    replay_address: "/api/v1/exports/governed-projections/depth-n-cycle-board?replay_target=composed_v2",
    source_dependency_hash: "sha256:cycle-board-dependencies",
    stable_address: "/api/v1/exports/governed-projections/depth-n-cycle-board",
  };
}

function artifactMissingPacket(): ArtifactMissingGovernedProjectionPacket {
  return {
    absence_reason: "owner artifact is not present",
    as_of: "2026-07-29T10:00:00Z",
    authoritative_for: [],
    availability: "artifact_missing",
    export_replay_contract: "policyos.runtime.export_replay_binding.v1",
    freshness: { ...FRESHNESS, state: "artifact_missing" },
    intended_audience: "EXPERT",
    may_not_use_for: ["authority"],
    packet_schema_version: "policyos.runtime.governed_projection_packet.v1",
    projection_id: "depth-n-cycle-board",
    projection_rule_version: "policyos.runtime.governed_projection.v1",
    stable_address: "projection://depth-n-cycle-board",
  };
}

function invalidSourcePacket(): InvalidGovernedProjectionPacket {
  return {
    absence_reason: "owner source failed validation",
    as_of: "2026-07-29T10:00:00Z",
    authoritative_for: [],
    availability: "invalid_source",
    export_replay_contract: "policyos.runtime.export_replay_binding.v1",
    freshness: { ...FRESHNESS, state: "invalid_source" },
    intended_audience: "EXPERT",
    may_not_use_for: ["authority"],
    packet_schema_version: "policyos.runtime.governed_projection_packet.v1",
    projection_id: "depth-n-cycle-board",
    projection_rule_version: "policyos.runtime.governed_projection.v1",
    source: {
      ...SOURCE,
      validation: {
        ...SOURCE.validation,
        issue_codes: ["owner_validation_failure"],
        status: "failed",
      },
    },
    stable_address: "projection://depth-n-cycle-board",
  };
}

describe("depth-N Cycle Board governed projection adapter", () => {
  it("narrows only the unpinned composed-v2 hero packet", async () => {
    const packet = cycleBoardPacket();
    const getDepthNCycleBoardProjection = vi.fn().mockResolvedValue(packet);
    const query = depthNCycleBoardHeroProjectionQueryOptions({
      getDepthNCycleBoardProjection,
    });

    await expect(query.queryFn()).resolves.toEqual({
      packet,
      payload: packet.payload,
    });
    expect(query.queryKey).toEqual(queryKeys.cycleBoardProjection());
    expect(query.queryKey).not.toEqual(
      queryKeys.governedProjection("depth-n-cycle-board"),
    );
    expect(getDepthNCycleBoardProjection).toHaveBeenCalledWith({});
    expect(depthNCycleBoardHeroProjectionQueryPolicy()).toEqual({
      kind: "never_cache_authority",
    });
    expect(packet).not.toHaveProperty("as_of");
  });

  it("rejects a raw-v1 packet on the hero contract", () => {
    expect(() => narrowDepthNCycleBoardHeroProjection(availablePacket())).toThrow(
      /contract_error.*cycle board.*v2|contract_error.*version/iu,
    );
  });

  it("preserves available artifact-missing and invalid-source producer states", () => {
    const available = availablePacket();
    const missing = artifactMissingPacket();
    const invalid = invalidSourcePacket();

    expect(narrowDepthNCycleBoardProjection(available)).toEqual({
      packet: available,
      payload: available.payload,
    });
    expect(narrowDepthNCycleBoardProjection(missing)).toEqual({
      packet: missing,
      payload: null,
    });
    expect(narrowDepthNCycleBoardProjection(invalid)).toEqual({
      packet: invalid,
      payload: null,
    });
  });

  it("rejects a mismatched projection id without guessing a depth payload", () => {
    const mismatchedId = {
      ...availablePacket(),
      projection_id: "value-gate",
    } as AvailableGovernedProjectionPacket;
    const siblingPayload = {
      ...availablePacket(),
      payload: { gate: "sibling-payload" },
    } as unknown as AvailableGovernedProjectionPacket;

    expect(() => narrowDepthNCycleBoardProjection(mismatchedId)).toThrow(
      /contract_error.*projection id/iu,
    );
    expect(() => narrowDepthNCycleBoardProjection(siblingPayload)).toThrow(
      /contract_error.*payload/iu,
    );
  });

  it("does not correlate global domain rows to the route run", async () => {
    const packet = availablePacket();
    const getGovernedProjection = vi.fn().mockResolvedValue(packet);
    const query = depthNCycleBoardProjectionQueryOptions({
      getGovernedProjection,
    });

    expect(query.queryKey).toEqual(
      queryKeys.governedProjection("depth-n-cycle-board"),
    );
    expect(query.queryKey).not.toContain("route-run-42");

    const result = await query.queryFn();
    expect(Object.keys(result.payload?.domain_runs ?? {})).toEqual([
      "global-domain-a",
      "global-domain-b",
    ]);
    expect(getGovernedProjection).toHaveBeenCalledWith({
      projection_id: "depth-n-cycle-board",
    });
  });

  it("emits a live cache observation after fetching an owner packet", async () => {
    const getGovernedProjection = vi.fn().mockResolvedValue(availablePacket());
    const queryClient = new QueryClient({
      defaultOptions: { queries: { gcTime: Infinity, retry: false, staleTime: Infinity } },
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(
      () => useDepthNCycleBoardProjection({ getGovernedProjection }),
      { wrapper },
    );

    await waitFor(() => {
      expect(result.current.cacheObservation).toEqual({
        asOf: "2026-07-29T10:00:00Z",
        posture: "live",
      });
    });
  });

  it("retains only packets carrying an explicit owner as_of", async () => {
    const packet = availablePacket();
    const getGovernedProjection = vi.fn().mockResolvedValue({
      ...packet,
      as_of: undefined,
      freshness: { ...packet.freshness, observed_at: "2026-08-10T10:00:00Z" },
      source: { ...packet.source, generated_at: "2026-08-10T10:00:00Z" },
    } as unknown as AvailableGovernedProjectionPacket);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { gcTime: Infinity, retry: false } },
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(
      () => useDepthNCycleBoardProjection({ getGovernedProjection }),
      { wrapper },
    );

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});
