import type {
  ArtifactMissingGovernedProjectionPacket,
  AvailableGovernedProjectionPacket,
  InvalidGovernedProjectionPacket,
  ProjectionSourceIdentity,
} from "@polisyos/runtime-api-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import { queryKeys } from "@/api/queryKeys";

import {
  depthNCycleBoardProjectionQueryOptions,
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
    acquisition_route: { route: "owner-supplied" },
    design_problem_ref: `design-problem://${runId}`,
    domain_role: "legal",
    evidence_class: "owner_evidence_extension",
    evidence_witness: { ref: `evidence://${runId}` },
    generation_cycle_run_id: runId,
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
