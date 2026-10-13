import { onlineManager } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useDiscoverDataSources } from "@/api/hooks/useDiscoverDataSources";
import { useIngestData } from "@/api/hooks/useIngestData";
import { useLaunchNlRun } from "@/api/hooks/useLaunchNlRun";
import {
  fetchControlPreAdmissionAttemptByIdempotencyKey,
  useControlPreAdmissionAttemptStatus,
} from "@/api/hooks/useControlPreAdmissionAttemptStatus";
import { useLaunchRun } from "@/api/hooks/useLaunchRun";
import { useLexSearch } from "@/api/hooks/useLexSearch";
import { useLexTrigger } from "@/api/hooks/useLexTrigger";
import { usePreviewFetchPlan } from "@/api/hooks/usePreviewFetchPlan";
import {
  useResolveDataNeeds,
  type DataResolveRequest,
} from "@/api/hooks/useResolveDataNeeds";
import { queryKeys } from "@/api/queryKeys";
import { controlPreAdmissionRecoveryRepository } from "@/api/controlPreAdmissionRecovery";

vi.mock("@/api/controlPreAdmissionRecovery", () => {
  const records = new Map<string, { idempotencyKey: string }>();
  let nextKey = 0;
  return {
    controlPreAdmissionRecoveryRepository: {
      claim: vi.fn(
        async (_scope: unknown, request: unknown, requestedKey?: string) => {
          const intent = JSON.stringify(request);
          const existing = records.get(intent);
          if (existing) return existing;
          const record = {
            idempotencyKey: requestedKey ?? `test-launch-key-${++nextKey}`,
          };
          records.set(intent, record);
          return record;
        },
      ),
      rememberAttemptId: vi.fn(async () => undefined),
      releaseKnownNoAttempt: vi.fn(async () => true),
    },
  };
});
vi.mock("@/api/hooks/useControlPreAdmissionRecovery", () => ({
  useControlPreAdmissionRecovery: () => ({ data: null, error: null }),
}));

import { runtimeApiClient } from "@/api/client";
import { useCreateHumanDecision } from "@/features/runs/api/useHumanDecisions";
import { controlPreAdmissionAttemptFixture } from "@/test/fixtures/controlPreAdmissionAttempt";
import { createQueryHookHarness } from "@/test/queryHook";
import {
  mockRuntimeGetSuccess,
  mockRuntimePostFailure,
  mockRuntimePostSuccess,
} from "@/test/runtimeApi";

const runListKey = queryKeys.runs({ limit: 24 });
const recoveryScope = {
  tenantId: "tenant-test",
  cellId: "cell-test",
  userId: "actor-test",
};

function useLaunchNlRunForRecoveryScope() {
  return useLaunchNlRun(recoveryScope);
}

function createMeta() {
  return {
    generated_at: "2026-03-10T10:00:00Z",
    request_id: "req-mutation",
    source_kinds: ["core_run"],
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function idempotencyKeyFromPostCall(call: unknown): string | null {
  if (!Array.isArray(call)) return null;
  const options = call[1];
  if (!isRecord(options)) return null;
  const params = options.params;
  if (!isRecord(params) || !isRecord(params.header)) return null;
  const key = params.header["Idempotency-Key"];
  return typeof key === "string" ? key : null;
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

function snapshotLocalStorage(): Record<string, string | null> {
  const snapshot: Record<string, string | null> = {};
  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index);
    if (key !== null) {
      snapshot[key] = window.localStorage.getItem(key);
    }
  }
  return snapshot;
}

describe("mutation hooks", () => {
  afterEach(() => {
    onlineManager.setOnline(true);
    vi.restoreAllMocks();
  });

  it("rejects human decisions offline without network, cache authority, or queue bytes", async () => {
    const fetchSpy = vi.spyOn(window, "fetch");
    const { queryClient, wrapper } = createQueryHookHarness();
    const view = renderHook(() => useCreateHumanDecision("run-offline"), {
      wrapper,
    });
    const beforeStorage = snapshotLocalStorage();
    onlineManager.setOnline(false);

    await act(async () => {
      await expect(
        view.result.current.mutateAsync({
          body: {} as never,
          exposureSessionRef: "sha256:" + "1".repeat(64),
          runId: "run-offline",
        }),
      ).rejects.toMatchObject({ code: "DS9-OFFLINE-REVALIDATION" });
    });

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(
      queryClient.getQueryData(["runtime", "run", "run-offline"]),
    ).toBeUndefined();
    expect(snapshotLocalStorage()).toEqual(beforeStorage);
  });

  it("invalidates workflow launches without inserting synthetic run records", async () => {
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
    expect(queryClient.getQueryData(runListKey)).toEqual(createRunsCache());
    expect(
      queryClient.getQueryData(queryKeys.run("run-launched")),
    ).toBeUndefined();
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.runsRoot(),
    });
  });

  it("passes a stable caller idempotency key and returns the server attempt ID", async () => {
    const responseBody = {
      effective_execution_profile: "research",
      job_id: "job-pre-admission",
      message: "accepted",
      meta: createMeta(),
      run_id: "run-pre-admission",
      status: "accepted",
    };
    const postSpy = vi.spyOn(runtimeApiClient, "POST").mockResolvedValue({
      data: responseBody,
      error: undefined,
      response: new Response(JSON.stringify(responseBody), {
        headers: {
          "Content-Type": "application/json",
          "X-Control-Admission-Attempt-ID": "a".repeat(32),
        },
        status: 200,
      }),
    } as never);
    const { wrapper } = createQueryHookHarness();
    const view = renderHook(() => useLaunchNlRun(recoveryScope), { wrapper });

    let result: Awaited<ReturnType<typeof view.result.current.mutateAsync>>;
    await act(async () => {
      result = await view.result.current.mutateAsync({
        nl_request: "Run a bounded policy simulation",
        idempotencyKey: "stable-launch-key",
      } as never);
    });

    expect(result!.pre_admission_attempt_id).toBe("a".repeat(32));
    expect(postSpy).toHaveBeenCalledWith("/api/v1/control/runs/nl", {
      body: { nl_request: "Run a bounded policy simulation" },
      params: { header: { "Idempotency-Key": "stable-launch-key" } },
    });
  });

  it("reuses a generated exact-intent key after an ambiguous request failure", async () => {
    const responseBody = {
      effective_execution_profile: "research",
      job_id: "job-pre-admission-retry",
      message: "accepted",
      meta: createMeta(),
      run_id: "run-pre-admission-retry",
      status: "accepted",
    };
    const postSpy = vi
      .spyOn(runtimeApiClient, "POST")
      .mockRejectedValueOnce(new TypeError("connection reset after dispatch"))
      .mockResolvedValueOnce({
        data: responseBody,
        error: undefined,
        response: new Response(JSON.stringify(responseBody), {
          headers: {
            "Content-Type": "application/json",
            "X-Control-Admission-Attempt-ID": "d".repeat(32),
          },
          status: 200,
        }),
      } as never);
    const { wrapper } = createQueryHookHarness();
    const view = renderHook(() => useLaunchNlRun(recoveryScope), { wrapper });
    const input = {
      nl_request: "Recover this exact natural-language launch",
    } as never;

    await act(async () => {
      await expect(view.result.current.mutateAsync(input)).rejects.toThrow(
        "connection reset after dispatch",
      );
    });
    let result: Awaited<ReturnType<typeof view.result.current.mutateAsync>>;
    await act(async () => {
      result = await view.result.current.mutateAsync(input);
    });

    const firstHeader = idempotencyKeyFromPostCall(postSpy.mock.calls[0]);
    const secondHeader = idempotencyKeyFromPostCall(postSpy.mock.calls[1]);
    expect(firstHeader).toMatch(/^test-launch-key-\d+$/);
    expect(firstHeader).toBe(secondHeader);
    expect(result!.pre_admission_attempt_id).toBe("d".repeat(32));
  });

  it("releases a launch key only for the explicit no-attempt response", async () => {
    const postSpy = vi.spyOn(runtimeApiClient, "POST").mockResolvedValue({
      data: undefined,
      error: { detail: "invalid profile" },
      response: new Response(JSON.stringify({ detail: "invalid profile" }), {
        headers: { "X-Control-Pre-Admission-Outcome": "not_created" },
        status: 422,
      }),
    } as never);
    const { wrapper } = createQueryHookHarness();
    const view = renderHook(() => useLaunchNlRun(recoveryScope), { wrapper });
    const body = { nl_request: "Correct this invalid launch" };

    await act(async () => {
      await expect(
        view.result.current.mutateAsync({
          ...body,
          idempotencyKey: "stable-no-attempt-key",
        } as never),
      ).rejects.toThrow();
    });

    expect(postSpy).toHaveBeenCalledTimes(1);
    expect(
      controlPreAdmissionRecoveryRepository.releaseKnownNoAttempt,
    ).toHaveBeenCalledWith(recoveryScope, body, "stable-no-attempt-key");
  });

  it("fetches fresh actor-scoped pre-admission history by its opaque ID", async () => {
    const attempt = controlPreAdmissionAttemptFixture({
      attemptId: "b".repeat(32),
      runId: "run-history",
      status: "started",
    });
    const getSpy = mockRuntimeGetSuccess(attempt);
    const { wrapper } = createQueryHookHarness();
    const view = renderHook(
      () => useControlPreAdmissionAttemptStatus("b".repeat(32)),
      { wrapper },
    );

    await waitFor(() =>
      expect(view.result.current.data?.status).toBe("started"),
    );
    expect(getSpy).toHaveBeenCalledWith(
      "/api/v1/control/admission-attempts/{attempt_id}",
      { params: { path: { attempt_id: "b".repeat(32) } } },
    );
  });

  it("looks up current attempt history by the opaque request key header", async () => {
    const attempt = controlPreAdmissionAttemptFixture({
      attemptId: "e".repeat(32),
      runId: "run-key-history",
      status: "settled",
    });
    const getSpy = mockRuntimeGetSuccess(attempt);

    await expect(
      fetchControlPreAdmissionAttemptByIdempotencyKey("opaque-key-r215"),
    ).resolves.toMatchObject({ attempt_id: "e".repeat(32), status: "settled" });
    expect(getSpy).toHaveBeenCalledWith(
      "/api/v1/control/admission-attempts/by-idempotency-key",
      { params: { header: { "Idempotency-Key": "opaque-key-r215" } } },
    );
  });

  it("launch hooks never insert accepted or rejected interaction state into run caches", async () => {
    const scenarios = [
      {
        hook: useLaunchRun,
        input: { execution_intent: "Inspect policy drift" },
        response: {
          effective_execution_profile: "dev",
          job_id: "job-accepted",
          message: "accepted",
          meta: createMeta(),
          run_id: "run-accepted",
          status: "accepted",
        },
      },
      {
        hook: useLaunchNlRunForRecoveryScope,
        input: { nl_request: "Run a sensitivity analysis" },
        response: {
          effective_execution_profile: "dev",
          job_id: "job-rejected",
          message: "rejected",
          meta: createMeta(),
          run_id: "run-rejected",
          status: "rejected",
        },
      },
    ] as const;

    for (const scenario of scenarios) {
      const postSpy = mockRuntimePostSuccess(scenario.response);
      const { queryClient, wrapper } = createQueryHookHarness();
      const initialRuns = createRunsCache();
      queryClient.setQueryData(runListKey, initialRuns);
      const view = renderHook(() => scenario.hook(), { wrapper });

      await act(async () => {
        await expect(
          view.result.current.mutateAsync(scenario.input as never),
        ).resolves.toEqual(scenario.response);
      });

      expect(queryClient.getQueryData(runListKey)).toEqual(initialRuns);
      expect(
        queryClient.getQueryData(queryKeys.run(scenario.response.run_id)),
      ).toBeUndefined();

      view.unmount();
      postSpy.mockRestore();
    }
  });

  it("restores the runs cache when natural-language launch fails", async () => {
    mockRuntimePostFailure(500, {
      code: "launch_failed",
      detail: "Launch failed",
      status: 500,
    });
    const { queryClient, wrapper } = createQueryHookHarness();
    const initialRuns = createRunsCache();
    queryClient.setQueryData(runListKey, initialRuns);

    const view = renderHook(() => useLaunchNlRun(recoveryScope), { wrapper });

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

  it("preserves an explicit catalog profile and leaves an unset profile absent in the POST body", async () => {
    const response = {
      candidates: [],
      fetch_plans: [],
      meta: createMeta(),
      mode: "hybrid",
      warnings: [],
    };
    const postSpy = mockRuntimePostSuccess(response);
    const { wrapper } = createQueryHookHarness();
    const view = renderHook(() => useResolveDataNeeds(), { wrapper });
    const request: DataResolveRequest = {
      allow_explore_fallback: true,
      data_needs: [
        {
          geography: null,
          granularity: "annual",
          metric: "inflation",
          purpose: "data_intelligence_ui",
          quality_min: 0.6,
          time_end: null,
          time_start: null,
        },
      ],
      mode: "hybrid",
    };
    const selectedProfile: DataResolveRequest["catalog_run_profile"] =
      "prod_core_blocking";
    // @ts-expect-error The generated request contract excludes unknown profiles.
    const unsupportedProfile: DataResolveRequest["catalog_run_profile"] =
      "prod_unbounded";
    void unsupportedProfile;

    await act(async () => {
      await view.result.current.mutateAsync({
        ...request,
        catalog_run_profile: selectedProfile,
      });
    });
    await act(async () => {
      await view.result.current.mutateAsync(request);
    });

    expect(postSpy).toHaveBeenNthCalledWith(1, "/api/v1/control/data/resolve", {
      body: {
        ...request,
        catalog_run_profile: "prod_core_blocking",
      },
    });
    expect(postSpy).toHaveBeenNthCalledWith(2, "/api/v1/control/data/resolve", {
      body: request,
    });
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
          search_mode: "text",
          total: 0,
          vector_refusal_code: null,
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
