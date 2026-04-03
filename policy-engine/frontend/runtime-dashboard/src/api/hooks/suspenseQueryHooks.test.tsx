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

function useHealthSuspenseFixture() {
  return useSuspenseHealth();
}

function useDataIndexStatsSuspenseFixture() {
  return useSuspenseDataIndexStats();
}

function useDataPromotionCandidatesSuspenseFixture() {
  return useSuspenseDataPromotionCandidates();
}

function useGovernanceDebugSuspenseFixture(runId: string) {
  return useSuspenseGovernanceDebug(runId);
}

function useLexGraphStatsSuspenseFixture(outputDir: string) {
  return useSuspenseLexGraphStats(outputDir);
}

function useRunAgentsSuspenseFixture(runId: string) {
  return useSuspenseRunAgents(runId);
}

function useRunErrorsSuspenseFixture(runId: string) {
  return useSuspenseRunErrors(runId);
}

function useRunLineageSuspenseFixture(runId: string) {
  return useSuspenseRunLineage(runId);
}

function useRunNodesSuspenseFixture(runId: string) {
  return useSuspenseRunNodes(runId);
}

function useRunTimelineSuspenseFixture(runId: string) {
  return useSuspenseRunTimeline(runId);
}

function useRunWorkflowSuspenseFixture(runId: string) {
  return useSuspenseRunWorkflow(runId);
}

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

type SuspenseScenario = {
  useHook: () => { data: unknown };
  payload: unknown;
  queryKey: readonly unknown[];
};

describe("suspense query hooks", () => {
  it("reads prefetched payloads through suspense wrappers", () => {
    const runId = "R_suspense_001";
    const outputDir = "data/lex";
    const scenarios: SuspenseScenario[] = [
      {
        useHook: useHealthSuspenseFixture,
        payload: { status: "ok" },
        queryKey: queryKeys.health(),
      },
      {
        useHook: useDataIndexStatsSuspenseFixture,
        payload: { datasets_total: 12 },
        queryKey: queryKeys.dataIndexStats(),
      },
      {
        useHook: useDataPromotionCandidatesSuspenseFixture,
        payload: { candidates: [{ promotion_id: "promo-1" }] },
        queryKey: queryKeys.dataPromotionCandidates(),
      },
      {
        useHook: () => useGovernanceDebugSuspenseFixture(runId),
        payload: { debug: { run_id: runId, notes: [] } },
        queryKey: queryKeys.runGovernanceDebug(runId),
      },
      {
        useHook: () => useLexGraphStatsSuspenseFixture(outputDir),
        payload: { output_dir: outputDir, nodes_total: 42 },
        queryKey: queryKeys.lexGraphStats(outputDir),
      },
      {
        useHook: () => useRunAgentsSuspenseFixture(runId),
        payload: { pipeline: { attempts: [] }, run_id: runId },
        queryKey: queryKeys.runAgents(runId),
      },
      {
        useHook: () => useRunErrorsSuspenseFixture(runId),
        payload: { errors: [], run_id: runId },
        queryKey: queryKeys.runErrors(runId),
      },
      {
        useHook: () => useRunLineageSuspenseFixture(runId),
        payload: { lineage: { nodes: [], edges: [] }, run_id: runId },
        queryKey: queryKeys.runLineage(runId),
      },
      {
        useHook: () => useRunNodesSuspenseFixture(runId),
        payload: { nodes: [], run_id: runId },
        queryKey: queryKeys.runNodes(runId),
      },
      {
        useHook: () => useRunTimelineSuspenseFixture(runId),
        payload: { timeline: { events: [], notes: [] }, run_id: runId },
        queryKey: queryKeys.runTimeline(runId),
      },
      {
        useHook: () => useRunWorkflowSuspenseFixture(runId),
        payload: {
          run_id: runId,
          workflow: { edges: [], nodes: [], notes: [] },
        },
        queryKey: queryKeys.runWorkflow(runId),
      },
    ];

    for (const scenario of scenarios) {
      const { result, unmount } = renderHook(scenario.useHook, {
        wrapper: createSuspenseWrapper(scenario.queryKey, scenario.payload),
      });

      expect(result.current.data).toEqual(scenario.payload);
      unmount();
    }
  });
});
