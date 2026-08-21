import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { runAgentsQueryOptions, useRunAgents } from "@/api/hooks/useRunAgents";
import {
  runDetailsQueryOptions,
  useRunDetails,
} from "@/api/hooks/useRunDetails";
import { runErrorsQueryOptions, useRunErrors } from "@/api/hooks/useRunErrors";
import {
  runEvidenceContextQueryOptions,
  useRunEvidenceContext,
} from "@/api/hooks/useRunEvidenceContext";
import { runNodesQueryOptions, useRunNodes } from "@/api/hooks/useRunNodes";
import { runsQueryOptions, useRuns } from "@/api/hooks/useRuns";
import {
  runWorkflowQueryOptions,
  useRunWorkflow,
} from "@/api/hooks/useRunWorkflow";
import { createRuntimeApiError } from "@/api/http";
import { queryKeys } from "@/api/queryKeys";
import {
  RUN_ACTIVE_REFETCH_MS,
  RUN_ACTIVE_STALE_MS,
  RUN_BOOTSTRAP_REFETCH_MS,
  RUNS_DEFAULT_LIMIT,
  RUNS_SAMPLE_LIMIT,
  RUNS_SAMPLE_STALE_MS,
  RUN_TERMINAL_STALE_MS,
} from "@/shared/lib/constants";
import { createQueryHookWrapper } from "@/test/queryHook";
import { mockRuntimeGetSuccess } from "@/test/runtimeApi";

const runId = "R_core_api_001";
const meta = {
  generated_at: "2026-03-09T10:00:00Z",
  request_id: "req-1",
  source_kinds: ["core_run"],
};

const runsPayload = {
  meta,
  page: {
    count: 1,
    cursor: null,
    limit: RUNS_DEFAULT_LIMIT,
    next_cursor: null,
    total: 1,
  },
  runs: [
    {
      duration_ms: 1_000,
      root_artifact_count: 2,
      run_id: runId,
      run_terminality: "not_established",
      source_kind: "core_run",
      started_at: "2026-03-09T10:00:00Z",
      status: "running",
    },
  ],
};

const runDetailsPayload = {
  meta,
  run: {
    run_id: runId,
    source_kind: "core_run",
    started_at: "2026-03-09T10:00:00Z",
    status: "running",
  },
};

const runErrorsPayload = {
  meta,
  run_id: runId,
};

const runAgentsPayload = {
  meta,
  pipeline: {
    performance_summary: {
      llm: {
        latency_ms: 125_000,
      },
      phase_budgets: [
        {
          budget_ms: 10_000,
          duration_ms: 15_000,
          phase: "retrieval.materialize",
          status: "over_budget",
        },
      ],
    },
    run_id: runId,
    source_kind: "core_run",
    total_attempts: 1,
  },
};

const runNodesPayload = {
  meta,
  run_id: runId,
  source_kind: "core_run",
};

const runWorkflowPayload = {
  meta,
  workflow: {
    run_id: runId,
    source_kind: "core_run",
    summary: {
      edge_count: 0,
      fail_count: 0,
      max_depth: 0,
      node_count: 0,
      ok_count: 0,
      skip_count: 0,
    },
  },
};

const runEvidenceContextPayload = {
  meta,
  context: {
    run_id: runId,
    source_kind: "core_run",
  },
};

function useRunErrorsHook() {
  return useRunErrors(runId);
}

function useRunAgentsHook() {
  return useRunAgents(runId);
}

function useRunNodesHook() {
  return useRunNodes(runId);
}

function useRunWorkflowHook() {
  return useRunWorkflow(runId);
}

function useRunEvidenceContextHook() {
  return useRunEvidenceContext(runId);
}

describe("run query hooks", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads the runs list and keeps sample queries on the longer stale window", async () => {
    const getSpy = mockRuntimeGetSuccess(runsPayload);
    const filters = { limit: RUNS_SAMPLE_LIMIT };
    const { result } = renderHook(() => useRuns(filters), {
      wrapper: createQueryHookWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data?.runs).toHaveLength(1);
    });

    expect(result.current.data?.runs[0]?.run_id).toBe(runId);
    expect(getSpy).toHaveBeenCalledWith("/api/v1/runs", {
      params: {
        query: {
          cursor: null,
          from_ts: null,
          limit: RUNS_SAMPLE_LIMIT,
          q: null,
          status: null,
          to_ts: null,
        },
      },
    });

    expect(runsQueryOptions(filters).queryKey).toEqual(queryKeys.runs(filters));
    expect(runsQueryOptions(filters).staleTime).toBe(RUNS_SAMPLE_STALE_MS);
    expect(
      runsQueryOptions({ cursor: "cursor-2", limit: RUNS_SAMPLE_LIMIT })
        .staleTime,
    ).toBe(30_000);
  });

  it("includes the query filter in the request and cache key", async () => {
    const getSpy = mockRuntimeGetSuccess(runsPayload);
    const filters = { limit: 25, q: "policy", status: "completed" };
    const { result } = renderHook(() => useRuns(filters), {
      wrapper: createQueryHookWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data?.runs).toHaveLength(1);
    });

    expect(getSpy).toHaveBeenCalledWith("/api/v1/runs", {
      params: {
        query: {
          cursor: null,
          from_ts: null,
          limit: 25,
          q: "policy",
          status: "completed",
          to_ts: null,
        },
      },
    });
    expect(runsQueryOptions(filters).queryKey).toEqual(queryKeys.runs(filters));
  });

  it("loads run details and derives retry/refetch policy from run state", async () => {
    mockRuntimeGetSuccess(runDetailsPayload);
    const { result } = renderHook(() => useRunDetails(runId), {
      wrapper: createQueryHookWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data?.run.run_id).toBe(runId);
    });

    const options = runDetailsQueryOptions(runId);
    const notFoundError = createRuntimeApiError(
      new Response(
        JSON.stringify({
          code: "not_found",
          detail: "Run not found",
          status: 404,
        }),
        { status: 404 },
      ),
      {
        code: "not_found",
        detail: "Run not found",
        status: 404,
      },
      "Missing run",
    );

    expect(options.queryKey).toEqual(queryKeys.run(runId));
    expect(
      options.staleTime({
        state: {
          data: {
            run: {
              status: "running",
            },
          },
        },
      }),
    ).toBe(RUN_ACTIVE_STALE_MS);
    expect(
      options.staleTime({
        state: {
          data: {
            run: {
              finished_at: "2026-03-09T10:05:00Z",
              status: "completed",
            },
          },
        },
      }),
    ).toBe(RUN_TERMINAL_STALE_MS);
    expect(options.retry(0, notFoundError)).toBe(true);
    expect(options.retry(6, notFoundError)).toBe(false);
    expect(options.retry(0, new Error("boom"))).toBe(false);
    expect(
      options.refetchInterval({
        state: {
          error: notFoundError,
        },
      }),
    ).toBe(RUN_BOOTSTRAP_REFETCH_MS);
    expect(
      options.refetchInterval({
        state: {
          data: {
            run: {
              status: "running",
            },
          },
        },
      }),
    ).toBe(RUN_ACTIVE_REFETCH_MS);
    expect(
      options.refetchInterval({
        state: {
          data: {
            run: {
              finished_at: "2026-03-09T10:05:00Z",
              status: "completed",
            },
          },
        },
      }),
    ).toBe(false);
    expect(
      runDetailsQueryOptions(runId, { liveTransport: true }).refetchInterval({
        state: {
          data: {
            run: {
              status: "running",
            },
          },
        },
      }),
    ).toBe(false);
  });

  it("polls until producer finished_at instead of guessing terminality from status text", () => {
    const options = runDetailsQueryOptions(runId);
    const opaqueStatusOnly = {
      state: {
        data: {
          run: {
            status: "completed_future",
          },
        },
      },
    };
    const producerFinished = {
      state: {
        data: {
          run: {
            finished_at: "2026-03-09T10:05:00Z",
            status: "awaiting_external_attestation",
          },
        },
      },
    };

    expect(options.staleTime(opaqueStatusOnly)).toBe(RUN_ACTIVE_STALE_MS);
    expect(options.refetchInterval(opaqueStatusOnly)).toBe(
      RUN_ACTIVE_REFETCH_MS,
    );
    expect(options.staleTime(producerFinished)).toBe(RUN_TERMINAL_STALE_MS);
    expect(options.refetchInterval(producerFinished)).toBe(false);
  });

  it("normalizes secondary run detail tabs into stable arrays", async () => {
    const scenarios = [
      {
        endpoint: "/api/v1/debug/runs/{run_id}/errors",
        hook: useRunErrorsHook,
        queryOptions: runErrorsQueryOptions(runId),
        assertData: (data: { errors: unknown[] }) => {
          expect(data.errors).toEqual([]);
        },
        payload: runErrorsPayload,
      },
      {
        endpoint: "/api/v1/runs/{run_id}/agents",
        hook: useRunAgentsHook,
        queryOptions: runAgentsQueryOptions(runId),
        assertData: (data: {
          pipeline: {
            attempts: unknown[];
            performance_summary?: {
              phase_budgets?: Array<{ phase?: string }>;
            };
          };
        }) => {
          expect(data.pipeline.attempts).toEqual([]);
          expect(
            data.pipeline.performance_summary?.phase_budgets?.[0]?.phase,
          ).toBe("retrieval.materialize");
        },
        payload: runAgentsPayload,
      },
      {
        endpoint: "/api/v1/runs/{run_id}/nodes",
        hook: useRunNodesHook,
        queryOptions: runNodesQueryOptions(runId),
        assertData: (data: { nodes: unknown[] }) => {
          expect(data.nodes).toEqual([]);
        },
        payload: runNodesPayload,
      },
      {
        endpoint: "/api/v1/runs/{run_id}/workflow",
        hook: useRunWorkflowHook,
        queryOptions: runWorkflowQueryOptions(runId),
        assertData: (data: {
          workflow: { edges: unknown[]; nodes: unknown[]; notes: unknown[] };
        }) => {
          expect(data.workflow.nodes).toEqual([]);
          expect(data.workflow.edges).toEqual([]);
          expect(data.workflow.notes).toEqual([]);
        },
        payload: runWorkflowPayload,
      },
      {
        endpoint: "/api/v1/runs/{run_id}/evidence-context",
        hook: useRunEvidenceContextHook,
        queryOptions: runEvidenceContextQueryOptions(runId),
        assertData: (data: {
          context: {
            data_needs: unknown[];
            fetch_plans: unknown[];
            promotion_candidates: unknown[];
            related_artifacts: unknown[];
            warnings: unknown[];
          };
        }) => {
          expect(data.context.related_artifacts).toEqual([]);
          expect(data.context.data_needs).toEqual([]);
          expect(data.context.fetch_plans).toEqual([]);
          expect(data.context.promotion_candidates).toEqual([]);
          expect(data.context.warnings).toEqual([]);
        },
        payload: runEvidenceContextPayload,
      },
    ] as const;

    for (const scenario of scenarios) {
      const getSpy = mockRuntimeGetSuccess(scenario.payload);
      const { result, unmount } = renderHook(() => scenario.hook(), {
        wrapper: createQueryHookWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      scenario.assertData(result.current.data as never);
      expect(getSpy.mock.calls[0]?.[0]).toBe(scenario.endpoint);
      expect(scenario.queryOptions.queryKey[2]).toBe(runId);

      unmount();
      vi.restoreAllMocks();
    }
  });
});
