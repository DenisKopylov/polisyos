import { useCompareRuns } from "@/api/hooks/useCompareRuns";

export function useDiffData(
  runAId: string | undefined,
  runBId: string | undefined,
) {
  return useCompareRuns(runAId, runBId);
}
