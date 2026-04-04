import type { QueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/api/queryKeys";

export function invalidateRunsRootQueries(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: queryKeys.runsRoot() });
}

export function invalidateRunQueries(queryClient: QueryClient, runId: string) {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: queryKeys.run(runId) }),
    queryClient.invalidateQueries({ queryKey: queryKeys.runTimeline(runId) }),
    queryClient.invalidateQueries({
      queryKey: queryKeys.runGovernanceDebug(runId),
    }),
    queryClient.invalidateQueries({
      queryKey: queryKeys.runEvidenceContext(runId),
    }),
    queryClient.invalidateQueries({ queryKey: queryKeys.runWorkflow(runId) }),
    queryClient.invalidateQueries({ queryKey: queryKeys.runAgents(runId) }),
  ]);
}
