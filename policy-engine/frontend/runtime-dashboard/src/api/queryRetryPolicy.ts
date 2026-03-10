import { classifyRuntimeApiError } from "@/api/http";

export function shouldRetryQueryError(failureCount: number, error: unknown) {
  const errorKind = classifyRuntimeApiError(error);
  if (errorKind === "network" || errorKind === "transient") {
    return failureCount < 3;
  }
  return false;
}

export function queryRetryDelay(attempt: number) {
  return Math.min(750 * 2 ** attempt, 5_000);
}
