import type { PropsWithChildren } from "react";
import { Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";

import {
  useSuspenseDataIndexStats,
} from "@/api/hooks/useDataIndexStats";
import {
  useSuspenseDataPromotionCandidates,
} from "@/api/hooks/useDataPromotionCandidates";
import { useSuspenseGovernanceDebug } from "@/api/hooks/useGovernanceDebug";
import { useSuspenseHealth } from "@/api/hooks/useHealth";
import { useSuspenseLexGraphStats } from "@/api/hooks/useLexGraphStats";
import { useSuspenseRunAgents } from "@/api/hooks/useRunAgents";
import { useSuspenseRunErrors } from "@/api/hooks/useRunErrors";
import { useSuspenseRunLineage } from "@/api/hooks/useRunLineage";
import { useSuspenseRunNodes } from "@/api/hooks/useRunNodes";
import { useSuspenseRunTimeline } from "@/api/hooks/useRunTimeline";
import { useSuspenseRunWorkflow } from "@/api/hooks/useRunWorkflow";
import { queryKeys } from "@/api/queryKeys";

function createSuspenseWrapper(
  queryKey: readonly unknown[],
  data: unknown,
) {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        gcTime: Infinity,
        retry: false,
        staleTime: Infinity,
      },
    },
  });
  client.setQueryData(queryKey, data);

  function Wrapper({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={client}>
        <Suspense fallback={<div>loading</div>}>{children}</Suspense>
      </QueryClientProvider>
    );
  }

  return Wrapper;
}

describe("suspense query hooks", () => {
  it("reads prefetched payloads through suspense wrappers", () => {
    const runId = "R_suspense_001";
    const outputDir = "data/lex";
    const scenarios = [
      {
        hook: () => useSuspenseHealth(),
        payload: { status: "ok" },
        queryKey: queryKeys.health(),
      },
      {
        hook: () => useSuspenseDataIndexStats(),
        payload: { datasets_total: 12 },
        queryKey: queryKeys.dataIndexStats(),
      },
      {
        hook: () => useSuspenseDataPromotionCandidates(),
        payload: { candidates: [{ promotion_id: "promo-1" }] },
        queryKey: queryKeys.dataPromotionCandidates(),
      },
      {
        hook: () => useSuspenseGovernanceDebug(runId),
        payload: { debug: { run_id: runId, notes: [] } },
        queryKey: queryKeys.runGovernanceDebug(runId),
      },
      {
        hook: () => useSuspenseLexGraphStats(outputDir),
        payload: { output_dir: outputDir, nodes_total: 42 },
        queryKey: queryKeys.lexGraphStats(outputDir),
      },
      {
        hook: () => useSuspenseRunAgents(runId),
        payload: { pipeline: { attempts: [] }, run_id: runId },
        queryKey: queryKeys.runAgents(runId),
      },
      {
        hook: () => useSuspenseRunErrors(runId),
        payload: { errors: [], run_id: runId },
        queryKey: queryKeys.runErrors(runId),
      },
      {
        hook: () => useSuspenseRunLineage(runId),
        payload: { lineage: { nodes: [], edges: [] }, run_id: runId },
        queryKey: queryKeys.runLineage(runId),
      },
      {
        hook: () => useSuspenseRunNodes(runId),
        payload: { nodes: [], run_id: runId },
        queryKey: queryKeys.runNodes(runId),
      },
      {
        hook: () => useSuspenseRunTimeline(runId),
        payload: { timeline: { events: [], notes: [] }, run_id: runId },
        queryKey: queryKeys.runTimeline(runId),
      },
      {
        hook: () => useSuspenseRunWorkflow(runId),
        payload: {
          run_id: runId,
          workflow: { edges: [], nodes: [], notes: [] },
        },
        queryKey: queryKeys.runWorkflow(runId),
      },
    ] as const;

    for (const scenario of scenarios) {
      const { result, unmount } = renderHook(scenario.hook, {
        wrapper: createSuspenseWrapper(scenario.queryKey, scenario.payload),
      });

      expect(result.current.data).toEqual(scenario.payload);
      unmount();
    }
  });
});
