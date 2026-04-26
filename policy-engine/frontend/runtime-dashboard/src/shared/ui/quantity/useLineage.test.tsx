import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createQueryHookWrapper } from "@/test/queryHook";
import {
  mockRuntimeGetSuccess,
  mockRuntimePostSuccess,
} from "@/test/runtimeApi";

import { useLineage } from "./useLineage";
import { useLineageBatch } from "./useLineageBatch";

const meta = {
  generated_at: "2026-04-24T12:00:00Z",
  request_id: "req-lineage-hook",
  source_kinds: ["core_run"],
};

const lineage = {
  id: "lin_a",
  status: "verified",
  freshness: "current",
  exports: { openlineage: "/openlineage", prov: "/prov" },
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("lineage hooks", () => {
  it("loads one lineage with temporal query params", async () => {
    const getSpy = mockRuntimeGetSuccess({
      meta,
      temporal_scope: { valid_at: "2026-04-15T12:00:00Z" },
      lineage,
    });

    const { result } = renderHook(
      () =>
        useLineage("lin_a", {
          temporalScope: { validAt: "2026-04-15T12:00:00Z" },
        }),
      { wrapper: createQueryHookWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(getSpy).toHaveBeenCalledWith("/api/v1/lineage/{lineage_id}", {
      params: {
        path: { lineage_id: "lin_a" },
        query: { valid_at: "2026-04-15T12:00:00.000Z" },
      },
    });
  });

  it("deduplicates batch lineage ids", async () => {
    const postSpy = mockRuntimePostSuccess({
      meta,
      temporal_scope: null,
      lineages: [lineage],
    });

    const { result } = renderHook(() => useLineageBatch(["lin_a", "lin_a"]), {
      wrapper: createQueryHookWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(postSpy).toHaveBeenCalledWith("/api/v1/lineage/batch", {
      params: { query: {} },
      body: { lineage_ids: ["lin_a"] },
    });
  });
});
