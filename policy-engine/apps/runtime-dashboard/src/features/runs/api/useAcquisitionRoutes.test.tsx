import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";

import { queryKeys } from "@/api/queryKeys";

import {
  acquisitionAuthorityQueryPolicy,
  acquisitionGrowthQueryOptions,
  narrowAcquisitionRouteCollection,
  useAcquisitionGrowth,
  type AcquisitionRoutesClient,
} from "./useAcquisitionRoutes";

function packetFixture() {
  return {
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
      backlog: [],
      carrier_liveness: {
        connector_id: "worldbank.wdi",
        execution_tier: "transport_ready",
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
      structural_routes: [],
      summary: {
        actual_network_call_count: 18,
        backlog_count: 0,
        family_scorecard_count: 12,
        metric_resolution_count: 124,
        selected_record_count: 144,
        structural_route_count: 0,
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
  };
}

function clientFixture(): AcquisitionRoutesClient {
  const packet = packetFixture();
  return {
    getAcquisitionGrowth: async () => ({
      packet,
      rawPacketBytes: new TextEncoder().encode("wire-growth-packet"),
    }),
    getAcquisitionRoute: async () => {
      throw new Error("not used");
    },
    listAcquisitionRoutes: async () => {
      throw new Error("not used");
    },
  };
}

describe("acquisition route governed reads", () => {
  it("captures one exact packet and uses a no-authority-cache key", async () => {
    const client = clientFixture();
    const query = acquisitionGrowthQueryOptions(client);
    const result = await query.queryFn();

    expect(query.queryKey).toEqual(queryKeys.acquisitionGrowth());
    expect(new TextDecoder().decode(result.rawPacketBytes)).toBe(
      "wire-growth-packet",
    );
    expect(result.packet.projection_id).toBe("acquisition-growth");
    expect(acquisitionAuthorityQueryPolicy()).toEqual({
      kind: "never_cache_authority",
    });
  });

  it("mounts through the governed wrapper without retaining authority", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { gcTime: Infinity, retry: false } },
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useAcquisitionGrowth(clientFixture()), {
      wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.packet.projection_id).toBe(
      "acquisition-growth",
    );
    const entry = queryClient.getQueryCache().find({
      queryKey: queryKeys.acquisitionGrowth(),
    });
    expect(entry?.options.gcTime).toBe(0);
    expect(
      (entry?.options as Readonly<{ staleTime?: number }> | undefined)
        ?.staleTime,
    ).toBe(0);
  });

  it("rejects a route list cross-bound to another run", () => {
    expect(() =>
      narrowAcquisitionRouteCollection("run-a", {
        packet: { routes: [], run_id: "run-b" },
        rawPacketBytes: new TextEncoder().encode("wire"),
      }),
    ).toThrow(/run mismatch/iu);
  });
});
