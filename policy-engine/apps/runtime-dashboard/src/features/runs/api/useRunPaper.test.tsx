import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";

import { queryKeys } from "@/api/queryKeys";
import { runPaperPacketFixture } from "@/test/fixtures/runPaper";

import {
  fetchRunPaper,
  narrowCapturedRunPaper,
  runPaperQueryOptions,
  runPaperQueryPolicy,
  useRunPaper,
} from "./useRunPaper";

describe("run paper governed adapter", () => {
  it("forwards the raw replay multiset and captures the exact one response", async () => {
    const packet = runPaperPacketFixture();
    const wire = `  ${JSON.stringify(packet)}\n`;
    const requests: Request[] = [];
    const rawSearch =
      "?manifest_artifact_id=stale&manifest_artifact_id=current&paper_projection_hash=x";
    const fetchImpl = vi.fn(async (request: Request) => {
      requests.push(request);
      return new Response(wire, {
        headers: { "content-type": "application/json" },
        status: 200,
      });
    });

    const result = await fetchRunPaper("run-1", rawSearch, fetchImpl);

    expect(requests).toHaveLength(1);
    expect(new URL(requests[0].url).search).toBe(rawSearch);
    expect(new TextDecoder().decode(result.rawPacketBytes)).toBe(wire);
    expect(result.packet).toEqual(packet);
  });

  it("fails closed on missing bytes or the wrong frozen packet union", () => {
    const packet = runPaperPacketFixture();
    expect(() => narrowCapturedRunPaper("run-1", packet, null)).toThrow(
      /response bytes were not captured/iu,
    );
    expect(() =>
      narrowCapturedRunPaper(
        "run-1",
        { ...packet, packet_schema_version: "future" } as never,
        new Uint8Array([1]),
      ),
    ).toThrow(/contract_error.*packet version/iu);
    expect(() =>
      narrowCapturedRunPaper(
        "run-1",
        {
          ...packet,
          case_record: { availability: "empty" },
        } as never,
        new Uint8Array([1]),
      ),
    ).toThrow(/contract_error.*case/iu);
    expect(() =>
      narrowCapturedRunPaper(
        "run-2",
        packet,
        new TextEncoder().encode(JSON.stringify(packet)),
      ),
    ).toThrow(/contract_error.*requested run/iu);
    for (const mayNotUseFor of [[], ["case_identity"], ["placeholder"]]) {
      expect(() =>
        narrowCapturedRunPaper(
          "run-1",
          {
            ...packet,
            case_record: {
              ...packet.case_record,
              may_not_use_for: mayNotUseFor,
            },
          },
          new Uint8Array([1]),
        ),
      ).toThrow(/contract_error.*unavailable case/iu);
    }
  });

  it("uses a replay-complete key and never retains authority", async () => {
    const packet = runPaperPacketFixture();
    const rawPacketBytes = new TextEncoder().encode(JSON.stringify(packet));
    const getRunPaper = vi.fn().mockResolvedValue({ packet, rawPacketBytes });
    const rawSearch = "?paper_projection_hash=sha256%3Aabc";
    const query = runPaperQueryOptions({ getRunPaper }, "run-1", rawSearch);

    await expect(query.queryFn()).resolves.toEqual({ packet, rawPacketBytes });
    expect(query.queryKey).toEqual(queryKeys.runPaper("run-1", rawSearch));
    expect(runPaperQueryPolicy()).toEqual({ kind: "never_cache_authority" });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(
      () => useRunPaper("run-1", rawSearch, { getRunPaper }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(getRunPaper).toHaveBeenCalledTimes(2);
  });
});
