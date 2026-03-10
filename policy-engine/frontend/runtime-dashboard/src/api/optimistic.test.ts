import { QueryClient } from "@tanstack/react-query";

import {
  applyOptimisticRunToCache,
  buildLaunchedRunSummary,
  createOptimisticRun,
  replaceOptimisticRunInCache,
} from "@/api/optimistic";
import { queryKeys } from "@/api/queryKeys";

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}

describe("optimistic run cache", () => {
  it("inserts an optimistic run into cached run lists", () => {
    const queryClient = createQueryClient();
    queryClient.setQueryData(queryKeys.runs({ limit: 24 }), {
      meta: {
        request_id: "req-1",
        generated_at: new Date().toISOString(),
        source_kinds: ["core_run"],
      },
      page: {
        limit: 24,
        cursor: null,
        next_cursor: null,
        count: 1,
        total: 1,
      },
      runs: [
        {
          run_id: "run-1",
          source_kind: "core_run",
          status: "completed",
          started_at: new Date().toISOString(),
          finished_at: null,
          duration_ms: 1200,
          tenant_id: null,
          has_trace: true,
          root_artifact_count: 1,
          has_workflow_report: true,
          warnings: [],
          cell_id: null,
        },
      ],
    });

    const optimisticRun = createOptimisticRun("launch-pending-1");
    applyOptimisticRunToCache(queryClient, optimisticRun);

    const cached = queryClient.getQueryData<{
      runs: Array<{ run_id: string }>;
    }>(queryKeys.runs({ limit: 24 }));
    expect(cached?.runs[0]?.run_id).toBe("launch-pending-1");
  });

  it("replaces the optimistic run after launch succeeds", () => {
    const queryClient = createQueryClient();
    const optimisticRun = createOptimisticRun("launch-pending-2");
    queryClient.setQueryData(queryKeys.runs({ limit: 24 }), {
      meta: {
        request_id: "req-2",
        generated_at: new Date().toISOString(),
        source_kinds: ["core_run"],
      },
      page: {
        limit: 24,
        cursor: null,
        next_cursor: null,
        count: 1,
        total: 1,
      },
      runs: [optimisticRun],
    });

    replaceOptimisticRunInCache(
      queryClient,
      optimisticRun.run_id,
      buildLaunchedRunSummary(
        {
          message: "accepted",
          meta: {
            request_id: "req-launch",
            generated_at: new Date().toISOString(),
            source_kinds: ["core_run"],
          },
          run_id: "run-accepted",
          status: "accepted",
        },
        optimisticRun.started_at ?? new Date().toISOString(),
      ),
    );

    const cached = queryClient.getQueryData<{
      runs: Array<{ run_id: string; status: string }>;
    }>(queryKeys.runs({ limit: 24 }));
    expect(cached?.runs[0]?.run_id).toBe("run-accepted");
    expect(cached?.runs[0]?.status).toBe("running");
  });
});
