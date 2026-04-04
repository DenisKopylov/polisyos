import { RUNS_SAMPLE_LIMIT } from "@/lib/constants";
import {
  runsQueryOptions,
  useRuns,
  useSuspenseRuns,
} from "@/api/hooks/useRuns";

export function runsSampleQueryOptions() {
  return runsQueryOptions({ limit: RUNS_SAMPLE_LIMIT });
}

export function useRunsSample() {
  return useRuns({ limit: RUNS_SAMPLE_LIMIT });
}

export function useSuspenseRunsSample() {
  return useSuspenseRuns({ limit: RUNS_SAMPLE_LIMIT });
}
