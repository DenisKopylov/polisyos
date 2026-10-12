import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type ControlPreAdmissionAttemptResponse =
  components["schemas"]["ControlPreAdmissionAttemptResponse"];

export async function fetchControlPreAdmissionAttemptStatus(
  attemptId: string,
): Promise<ControlPreAdmissionAttemptResponse | null> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/admission-attempts/{attempt_id}",
    { params: { path: { attempt_id: attemptId } } },
  );
  if (response.status === 404) return null;
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to fetch control pre-admission attempt history",
    );
  }
  return data as ControlPreAdmissionAttemptResponse;
}

export async function fetchControlPreAdmissionAttemptByIdempotencyKey(
  idempotencyKey: string,
): Promise<ControlPreAdmissionAttemptResponse | null> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/admission-attempts/by-idempotency-key",
    { headers: { "Idempotency-Key": idempotencyKey } },
  );
  if (response.status === 404) return null;
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to recover control pre-admission attempt by request key",
    );
  }
  return data as ControlPreAdmissionAttemptResponse;
}

export function useControlPreAdmissionAttemptStatus(
  attemptId: string | null | undefined,
) {
  return useQuery({
    queryKey: queryKeys.controlPreAdmissionAttempt(attemptId ?? ""),
    queryFn: () => fetchControlPreAdmissionAttemptStatus(attemptId!),
    enabled: Boolean(attemptId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "started" || status === "settled" ? 1000 : false;
    },
  });
}
