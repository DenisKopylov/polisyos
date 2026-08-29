import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { ReactNode } from "react";

import type { AvailableConfidenceLedgerRiskSpendPacket } from "@polisyos/runtime-api-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";

import { queryKeys } from "@/api/queryKeys";

import {
  confidenceLedgerRiskSpendQueryOptions,
  confidenceLedgerRiskSpendQueryPolicy,
  useConfidenceLedgerRiskSpend,
} from "./useConfidenceLedgerRiskSpend";

function availablePacket(): AvailableConfidenceLedgerRiskSpendPacket {
  const openApi = JSON.parse(
    readFileSync(
      resolve(process.cwd(), "../../schemas/runtime_api_v1.openapi.json"),
      "utf8",
    ),
  ) as {
    paths: Record<
      string,
      {
        get: {
          responses: Record<
            string,
            {
              content: Record<
                string,
                {
                  examples: {
                    default: {
                      value: AvailableConfidenceLedgerRiskSpendPacket;
                    };
                  };
                }
              >;
            }
          >;
        };
      }
    >;
  };
  return structuredClone(
    openApi.paths[
      "/api/v1/exports/governed-projections/confidence-ledger-risk-spend"
    ].get.responses["200"].content["application/json"].examples.default.value,
  );
}

describe("confidence-ledger risk-spend query", () => {
  it("uses the generated owner operation, exact captured bytes, and a distinct never-cache key", async () => {
    const packet = availablePacket();
    const rawPacketBytes = new TextEncoder().encode("exact-owner-response");
    const getConfidenceLedgerRiskSpendProjection = vi.fn().mockResolvedValue({
      packet,
      rawPacketBytes,
    });

    const query = confidenceLedgerRiskSpendQueryOptions({
      getConfidenceLedgerRiskSpendProjection,
    });

    await expect(query.queryFn()).resolves.toEqual({
      packet,
      rawPacketBytes,
    });
    expect(query.queryKey).toEqual(
      queryKeys.confidenceLedgerRiskSpendProjection(),
    );
    expect(query.queryKey).not.toEqual([
      "governed-projection",
      "confidence-ledger-risk-spend",
    ]);
    expect(getConfidenceLedgerRiskSpendProjection).toHaveBeenCalledWith({});
    expect(confidenceLedgerRiskSpendQueryPolicy()).toEqual({
      kind: "never_cache_authority",
    });
  });

  it("admits the packet before exposing it to the surface", async () => {
    const packet = availablePacket();
    Object.assign(packet.payload, { hidden_authority: "publishable" });
    const getConfidenceLedgerRiskSpendProjection = vi.fn().mockResolvedValue({
      packet,
      rawPacketBytes: new Uint8Array([1, 2, 3]),
    });
    const query = confidenceLedgerRiskSpendQueryOptions({
      getConfidenceLedgerRiskSpendProjection,
    });

    await expect(query.queryFn()).rejects.toThrow(/contract_error/iu);
  });

  it("mounts the protected query without caching authority", async () => {
    const packet = availablePacket();
    const rawPacketBytes = new Uint8Array([4, 5, 6]);
    const getConfidenceLedgerRiskSpendProjection = vi.fn().mockResolvedValue({
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
      () =>
        useConfidenceLedgerRiskSpend({
          getConfidenceLedgerRiskSpendProjection,
        }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ packet, rawPacketBytes });
    expect(queryClient.getQueryCache().findAll()).toHaveLength(1);
  });
});
