import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";

import {
  authorityAbstainingRunPaperPacketFixture,
  runPaperPacketFixture,
} from "@/test/fixtures/runPaper";

import {
  caseInspectionQueryOptions,
  caseInspectionQueryPolicy,
  fetchCaseInspection,
  useCaseInspection,
} from "./useCaseInspection";

describe("case inspection governed adapter", () => {
  it("forwards the complete replay multiset and captures one exact response", async () => {
    const packet = runPaperPacketFixture();
    const wire = `\n${JSON.stringify(packet)}  `;
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

    const result = await fetchCaseInspection("run-1", rawSearch, fetchImpl);

    expect(requests).toHaveLength(1);
    expect(new URL(requests[0].url).pathname).toBe(
      "/api/v1/runs/run-1/case-inspection",
    );
    expect(new URL(requests[0].url).search).toBe(rawSearch);
    expect(new TextDecoder().decode(result.rawPacketBytes)).toBe(wire);
    expect(result.packet).toEqual(packet);
  });

  it("admits the exact authority-abstaining packet through case inspection", async () => {
    const packet = authorityAbstainingRunPaperPacketFixture();
    const fetchImpl = vi.fn(async () =>
      Response.json(packet, {
        headers: { "content-type": "application/json" },
        status: 200,
      }),
    );

    const result = await fetchCaseInspection("run-1", "", fetchImpl);

    expect(result.packet.case_record.availability).toBe(
      "record_available_authority_abstaining",
    );
  });

  it("removes only human-decision-owned keys from strict case replay input", async () => {
    const packet = runPaperPacketFixture();
    const requests: Request[] = [];
    const rawSearch =
      "?manifest_artifact_id=stale&source_kind=agent_action_authority&manifest_artifact_id=current&unknown_probe=x%2Fy&appeal_case_id=case-1&action_kind=data_request";
    const expectedReplaySearch =
      "?manifest_artifact_id=stale&manifest_artifact_id=current&unknown_probe=x%2Fy";
    const fetchImpl = vi.fn(async (request: Request) => {
      requests.push(request);
      return new Response(JSON.stringify(packet), {
        headers: { "content-type": "application/json" },
        status: 200,
      });
    });

    await fetchCaseInspection("run-1", rawSearch, fetchImpl);

    expect(requests).toHaveLength(1);
    expect(new URL(requests[0].url).search).toBe(expectedReplaySearch);

    const getCaseInspection = vi.fn().mockResolvedValue({
      packet,
      rawPacketBytes: new TextEncoder().encode(JSON.stringify(packet)),
    });
    const query = caseInspectionQueryOptions(
      { getCaseInspection },
      "run-1",
      rawSearch,
    );
    await query.queryFn();
    expect(query.queryKey.at(-1)).toEqual({
      rawReplaySearch: expectedReplaySearch,
    });
    expect(getCaseInspection).toHaveBeenCalledWith(
      "run-1",
      expectedReplaySearch,
    );
  });

  it("uses a replay-complete distinct key and never retains authority", async () => {
    const packet = runPaperPacketFixture();
    const rawPacketBytes = new TextEncoder().encode(JSON.stringify(packet));
    const getCaseInspection = vi
      .fn()
      .mockResolvedValue({ packet, rawPacketBytes });
    const rawSearch = "?paper_projection_hash=sha256%3Aabc";
    const query = caseInspectionQueryOptions(
      { getCaseInspection },
      "run-1",
      rawSearch,
    );

    await expect(query.queryFn()).resolves.toEqual({ packet, rawPacketBytes });
    expect(query.queryKey).toEqual([
      "runtime",
      "run",
      "run-1",
      "case-inspection",
      { rawReplaySearch: rawSearch },
    ]);
    expect(caseInspectionQueryPolicy()).toEqual({
      kind: "never_cache_authority",
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(
      () =>
        useCaseInspection("run-1", rawSearch, {
          getCaseInspection,
        }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(getCaseInspection).toHaveBeenCalledTimes(2);
  });
});
