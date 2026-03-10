import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { runtimeApiClient } from "@/api/client";
import { useArtifactContent } from "@/api/hooks/useArtifactContent";
import { useArtifactLineage } from "@/api/hooks/useArtifactLineage";
import { useArtifactManifest } from "@/api/hooks/useArtifactManifest";
import { useArtifactSchema } from "@/api/hooks/useArtifactSchema";
import { useGovernanceDebug } from "@/api/hooks/useGovernanceDebug";
import { useLexGraphStats } from "@/api/hooks/useLexGraphStats";
import { useLexPipelineStatus } from "@/api/hooks/useLexPipelineStatus";
import { useNodeDebug } from "@/api/hooks/useNodeDebug";
import { useRunEvidenceContext } from "@/api/hooks/useRunEvidenceContext";
import { useRunLineage } from "@/api/hooks/useRunLineage";
import { useRunTimeline } from "@/api/hooks/useRunTimeline";
import { queryKeys } from "@/api/queryKeys";
import { createQueryHookHarness, createQueryHookWrapper } from "@/test/queryHook";
import { mockRuntimeGetFailure, mockRuntimeGetSuccess } from "@/test/runtimeApi";

const meta = {
  generated_at: "2026-03-09T10:00:00Z",
  request_id: "req-extra",
  source_kinds: ["core_run"],
};

describe("additional query hook behaviors", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not call the runtime API when required identifiers are missing", () => {
    const getSpy = vi.spyOn(runtimeApiClient, "GET");
    const scenarios = [
      () => useArtifactContent(undefined, { maxBytes: 128 }),
      () => useArtifactLineage(undefined),
      () => useArtifactManifest(undefined),
      () => useArtifactSchema(undefined),
      () => useGovernanceDebug(undefined),
      () => useLexGraphStats(""),
      () => useLexPipelineStatus(null),
      () => useNodeDebug(undefined, null),
      () => useRunEvidenceContext(undefined),
      () => useRunLineage(undefined),
      () => useRunTimeline(undefined),
    ];

    for (const scenario of scenarios) {
      const { result, unmount } = renderHook(() => scenario(), {
        wrapper: createQueryHookWrapper(),
      });

      expect(result.current.isFetching).toBe(false);
      unmount();
    }

    expect(getSpy).not.toHaveBeenCalled();
  });

  it("normalizes run evidence context collections and surfaces runtime errors", async () => {
    mockRuntimeGetSuccess({
      context: {
        run_id: "run-1",
        source_kind: "core_run",
      },
      meta,
    });

    const { result } = renderHook(() => useRunEvidenceContext("run-1"), {
      wrapper: createQueryHookWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.context.data_needs).toEqual([]);
    expect(result.current.data?.context.fetch_plans).toEqual([]);
    expect(result.current.data?.context.promotion_candidates).toEqual([]);
    expect(result.current.data?.context.related_artifacts).toEqual([]);
    expect(result.current.data?.context.warnings).toEqual([]);

    vi.restoreAllMocks();
    mockRuntimeGetFailure(500, {
      code: "evidence_context_failed",
      detail: "Evidence context failed",
      status: 500,
    });

    const failedView = renderHook(() => useRunEvidenceContext("run-1"), {
      wrapper: createQueryHookWrapper(),
    });

    await waitFor(() => {
      expect(failedView.result.current.isError).toBe(true);
    });

    expect(failedView.result.current.error).toMatchObject({
      code: "evidence_context_failed",
      status: 500,
    });
  });

  it("configures lex pipeline polling only while the pipeline is active", async () => {
    mockRuntimeGetSuccess({
      pipeline_id: "pipe-1",
      state: "running",
    });
    const { queryClient, wrapper } = createQueryHookHarness();
    const { result } = renderHook(() => useLexPipelineStatus("pipe-1"), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.data?.state).toBe("running");
    });

    const query = queryClient.getQueryCache().find({
      queryKey: queryKeys.lexPipelineStatus("pipe-1"),
    });
    const refetchInterval = (query?.options as {
      refetchInterval?: (
        query: { state: { data?: { state?: string } } },
      ) => number | false;
    }).refetchInterval as
      | ((query: { state: { data?: { state?: string } } }) => number | false)
      | undefined;

    expect(refetchInterval?.({ state: { data: { state: "running" } } })).toBe(
      3000,
    );
    expect(
      refetchInterval?.({ state: { data: { state: "completed" } } }),
    ).toBe(false);
  });
});
