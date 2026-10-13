import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import {
  controlPreAdmissionAttemptResponseSchema,
  type ControlPreAdmissionAttemptResponse,
} from "../validators";

export type { ControlPreAdmissionAttemptResponse } from "../validators";

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
  return controlPreAdmissionAttemptResponseSchema.parse(data);
}

export async function fetchControlPreAdmissionAttemptByIdempotencyKey(
  idempotencyKey: string,
): Promise<ControlPreAdmissionAttemptResponse | null> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/admission-attempts/by-idempotency-key",
    { params: { header: { "Idempotency-Key": idempotencyKey } } },
  );
  if (response.status === 404) return null;
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to recover control pre-admission attempt by request key",
    );
  }
  return controlPreAdmissionAttemptResponseSchema.parse(data);
}

export function useControlPreAdmissionAttemptStatus(
  attemptId: string | null | undefined,
) {
  return useQuery({
    queryKey: queryKeys.controlPreAdmissionAttempt(attemptId ?? ""),
    queryFn: () =>
      attemptId
        ? fetchControlPreAdmissionAttemptStatus(attemptId)
        : Promise.resolve(null),
    enabled: Boolean(attemptId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "started" || status === "settled" ? 1000 : false;
    },
  });
}
