import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";

import { queryKeys } from "@/api/queryKeys";
import { cycleBoardProjectionPacketFixture } from "@/test/fixtures/depthNCycleBoard";

import {
  depthNCycleBoardHeroProjectionQueryOptions,
  depthNCycleBoardHeroProjectionQueryPolicy,
  narrowDepthNCycleBoardHeroProjection,
  useDepthNCycleBoardProjection,
} from "./useDepthNCycleBoardProjection";

describe("depth-N Cycle Board composed-v2 adapter", () => {
  it("uses only the unpinned static operation and representation-specific key", async () => {
    const packet = cycleBoardProjectionPacketFixture();
    const rawPacketBytes = new TextEncoder().encode("wire-packet");
    const getDepthNCycleBoardProjection = vi.fn().mockResolvedValue({
      packet,
      rawPacketBytes,
    });
    const query = depthNCycleBoardHeroProjectionQueryOptions({
      getDepthNCycleBoardProjection,
    });

    await expect(query.queryFn()).resolves.toEqual({
      packet,
      payload: packet.payload,
      rawPacketBytes,
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

  it("rejects raw-v1 and mismatched composed packets", () => {
    const packet = cycleBoardProjectionPacketFixture();
    const rawPacketBytes = new TextEncoder().encode("wire-packet");
    expect(() =>
      narrowDepthNCycleBoardHeroProjection(
        {
          ...packet,
          packet_schema_version:
            "policyos.runtime.governed_projection_packet.v1",
        } as never,
        rawPacketBytes,
      ),
    ).toThrow(/contract_error.*cycle board.*v2|contract_error.*version/iu);
    expect(() =>
      narrowDepthNCycleBoardHeroProjection(
        {
          ...packet,
          projection_rule_version: "policyos.runtime.depth_n_cycle_board.v1",
        } as never,
        rawPacketBytes,
      ),
    ).toThrow(/contract_error.*cycle board.*v2|contract_error.*version/iu);
  });

  it("mounts the composed-v2 query without fabricating an owner clock", async () => {
    const packet = cycleBoardProjectionPacketFixture();
    const rawPacketBytes = new TextEncoder().encode("wire-packet");
    const getDepthNCycleBoardProjection = vi.fn().mockResolvedValue({
      packet,
      rawPacketBytes,
    });
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { gcTime: Infinity, retry: false, staleTime: Infinity },
      },
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(
      () => useDepthNCycleBoardProjection({ getDepthNCycleBoardProjection }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({
      packet,
      payload: packet.payload,
      rawPacketBytes,
    });
    expect(result.current).not.toHaveProperty("cacheObservation");
    expect(result.current.data?.packet).not.toHaveProperty("as_of");
  });
});
