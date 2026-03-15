import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useDiscoverDataSources } from "@/api/hooks/useDiscoverDataSources";
import { useIngestData } from "@/api/hooks/useIngestData";
import { useLaunchNlRun } from "@/api/hooks/useLaunchNlRun";
import { useLaunchRun } from "@/api/hooks/useLaunchRun";
import { useLexSearch } from "@/api/hooks/useLexSearch";
import { useLexTrigger } from "@/api/hooks/useLexTrigger";
import { usePreviewFetchPlan } from "@/api/hooks/usePreviewFetchPlan";
import { useResolveDataNeeds } from "@/api/hooks/useResolveDataNeeds";
import { queryKeys } from "@/api/queryKeys";
import { createQueryHookHarness } from "@/test/queryHook";
import { mockRuntimePostFailure, mockRuntimePostSuccess } from "@/test/runtimeApi";

const runListKey = queryKeys.runs({ limit: 24 });

function createMeta() {
  return {
    generated_at: "2026-03-10T10:00:00Z",
    request_id: "req-mutation",
    source_kinds: ["core_run"],
  };
}

function createRunsCache() {
  return {
    meta: {
      generated_at: "2026-03-09T10:00:00Z",
      request_id: "req-runs",
      source_kinds: ["core_run"],
    },
    page: {
      count: 1,
      cursor: null,
      limit: 24,
      next_cursor: null,
      total: 1,
    },
    runs: [
      {
        duration_ms: 1_200,
        finished_at: null,
        has_trace: true,
        has_workflow_report: true,
        root_artifact_count: 1,
        run_id: "existing-run",
        source_kind: "core_run",
        started_at: "2026-03-09T10:00:00Z",
        status: "completed",
        tenant_id: null,
        warnings: [],
      },
    ],
  };
}

describe("mutation hooks", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("optimistically inserts and replaces workflow launches in the runs cache", async () => {
    vi.spyOn(Date, "now").mockReturnValue(111);
    const postSpy = mockRuntimePostSuccess({
      message: "accepted",
      meta: {
        generated_at: "2026-03-09T10:01:00Z",
        request_id: "req-launch",
        source_kinds: ["core_run"],
      },
      run_id: "run-launched",
      status: "accepted",
    });
    const { queryClient, wrapper } = createQueryHookHarness();
    queryClient.setQueryData(runListKey, createRunsCache());
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const view = renderHook(() => useLaunchRun(), { wrapper });
    let result: Awaited<ReturnType<typeof view.result.current.mutateAsync>>;
    await act(async () => {
      result = await view.result.current.mutateAsync({
        execution_intent: "Inspect policy drift",
      } as never);
    });

    expect(result!.run_id).toBe("run-launched");
    expect(postSpy).toHaveBeenCalledWith("/api/v1/control/runs", {
      body: {
        execution_intent: "Inspect policy drift",
      },
    });
    expect(
      (
        queryClient.getQueryData<{ runs: Array<{ run_id: string; status: string }> }>(
          runListKey,
        )?.runs ?? []
      )[0],
    ).toMatchObject({
      run_id: "run-launched",
      status: "running",
    });
    expect(queryClient.getQueryData(queryKeys.run("launch-pending-111"))).toBeUndefined();
    expect(queryClient.getQueryData(queryKeys.run("run-launched"))).toMatchObject({
      run: { run_id: "run-launched", status: "running" },
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.runsRoot(),
    });
  });

  it("restores the runs cache when natural-language launch fails", async () => {
    vi.spyOn(Date, "now").mockReturnValue(222);
    mockRuntimePostFailure(500, {
      code: "launch_failed",
      detail: "Launch failed",
      status: 500,
    });
    const { queryClient, wrapper } = createQueryHookHarness();
    const initialRuns = createRunsCache();
    queryClient.setQueryData(runListKey, initialRuns);

    const view = renderHook(() => useLaunchNlRun(), { wrapper });

    await act(async () => {
      await expect(
        view.result.current.mutateAsync({
          nl_request: "Run a sensitivity analysis",
        } as never),
      ).rejects.toMatchObject({
        code: "launch_failed",
        status: 500,
      });
    });

    expect(queryClient.getQueryData(runListKey)).toEqual(initialRuns);
    expect(
      queryClient.getQueryData(queryKeys.run("launch-nl-pending-222")),
    ).toBeUndefined();
  });

  it("invalidates control-plane caches for data mutations", async () => {
    const scenarios = [
      {
        endpoint: "/api/v1/control/data/resolve",
        hook: useResolveDataNeeds,
        input: { metric_query: "inflation" },
        invalidateKey: queryKeys.dataIndexStats(),
        response: { fetch_plans: [], meta: createMeta() },
      },
      {
        endpoint: "/api/v1/control/data/discover",
        hook: useDiscoverDataSources,
        input: { metric_query: "employment" },
        invalidateKey: queryKeys.dataIndexStats(),
        response: { candidates: [], meta: createMeta() },
      },
      {
        endpoint: "/api/v1/control/data/ingest",
        hook: useIngestData,
        input: { connector_id: "bigquery" },
        invalidateKey: queryKeys.cacheStatus(),
        response: { ingest_id: "ing-1", meta: createMeta() },
      },
    ] as const;

    for (const scenario of scenarios) {
      const { queryClient, wrapper } = createQueryHookHarness();
      const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
      const postSpy = mockRuntimePostSuccess(scenario.response);
      const view = renderHook(() => scenario.hook(), { wrapper });

      await act(async () => {
        await expect(
          view.result.current.mutateAsync(scenario.input as never),
        ).resolves.toEqual(scenario.response);
      });

      expect(postSpy).toHaveBeenCalledWith(scenario.endpoint, {
        body: scenario.input,
      });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: scenario.invalidateKey,
      });

      view.unmount();
      vi.restoreAllMocks();
    }
  });

  it("posts lex and preview mutations without cache side effects", async () => {
    const { wrapper } = createQueryHookHarness();
    const scenarios = [
      {
        endpoint: "/api/v1/control/lex/search",
        hook: useLexSearch,
        input: { query: "transport law" },
        response: {
          meta: createMeta(),
          query: "transport law",
          results: [],
          total: 0,
        },
      },
      {
        endpoint: "/api/v1/control/lex/trigger",
        hook: useLexTrigger,
        input: { output_dir: "data/lex" },
        response: { meta: createMeta(), pipeline_id: "pipe-1" },
      },
      {
        endpoint: "/api/v1/control/data/preview",
        hook: usePreviewFetchPlan,
        input: {
          fetch_plan: {
            connector_id: "bigquery",
            dataset_id: "macro",
            metric_id: "inflation",
            source_lane: "fastlane",
          },
        },
        response: {
          meta: createMeta(),
          preview: {
            completeness: 0.92,
            connector_id: "bigquery",
            coverage_ok: true,
            dataset_id: "macro",
            quality_min: 0.8,
            row_count: 2,
            sample_rows: [],
            schema: { value: "number" },
            status: "ok",
          },
        },
      },
    ] as const;

    for (const scenario of scenarios) {
      const postSpy = mockRuntimePostSuccess(scenario.response);
      const view = renderHook(() => scenario.hook(), { wrapper });

      await waitFor(async () => {
        await act(async () => {
          await expect(
            view.result.current.mutateAsync(scenario.input as never),
          ).resolves.toEqual(scenario.response);
        });
      });

      expect(postSpy).toHaveBeenCalledWith(scenario.endpoint, {
        body: scenario.input,
      });
      vi.restoreAllMocks();
    }
  });
});
