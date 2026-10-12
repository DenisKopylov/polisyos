import { useQueryClient } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import {
  controlPreAdmissionRecoveryRepository,
  type ControlPreAdmissionRecoveryScope,
} from "../controlPreAdmissionRecovery";
import { useControlPreAdmissionRecovery } from "./useControlPreAdmissionRecovery";
import type { components } from "../types";
import { useControlPlaneMutation } from "../useControlPlaneMutation";

export type NaturalLanguageRunRequest =
  components["schemas"]["NaturalLanguageRunRequest"];
export type NaturalLanguageRunLaunchRequest = NaturalLanguageRunRequest & {
  /** Reuse only to replay this exact immutable launch intent. */
  idempotencyKey?: string;
};
export type RunLaunchResponse = components["schemas"]["RunLaunchResponse"];
export type RunLaunchWithAdmissionAttempt = RunLaunchResponse & {
  pre_admission_attempt_id?: string;
};

async function launchNlRun(
  input: NaturalLanguageRunLaunchRequest,
): Promise<RunLaunchWithAdmissionAttempt> {
  const { idempotencyKey, ...body } = input;
  const { data, error, response } = await runtimeApiClient.POST(
    "/api/v1/control/runs/nl",
    {
      body,
      headers: idempotencyKey
        ? { "Idempotency-Key": idempotencyKey }
        : undefined,
    },
  );
  if (error || !response.ok || !data) {
    const launchError = createRuntimeApiError(
      response,
      error,
      "Failed to launch natural-language run",
    );
    const errorPayload =
      typeof error === "object" && error !== null
        ? (error as { pre_admission_attempt_id?: unknown })
        : null;
    const attemptId =
      response.headers.get("X-Control-Admission-Attempt-ID") ??
      (typeof errorPayload?.pre_admission_attempt_id === "string"
        ? errorPayload.pre_admission_attempt_id
        : null);
    if (attemptId !== null) {
      Object.assign(launchError, { preAdmissionAttemptId: attemptId });
    } else if (
      response.headers.get("X-Control-Pre-Admission-Outcome") === "not_created"
    ) {
      Object.assign(launchError, { preAdmissionNoAttempt: true });
    }
    throw launchError;
  }
  const attemptId = response.headers.get("X-Control-Admission-Attempt-ID");
  return {
    ...(data as RunLaunchResponse),
    ...(attemptId ? { pre_admission_attempt_id: attemptId } : {}),
  };
}

export function useLaunchNlRun(scope: ControlPreAdmissionRecoveryScope | null) {
  const queryClient = useQueryClient();
  const recovery = useControlPreAdmissionRecovery(scope);
  const mutation = useControlPlaneMutation({
    blockWhenOffline: true,
    errorToast: {
      title: "Natural-language launch failed",
      description: "Existing run data remains unchanged.",
      tone: "error",
    },
    mutationId: "runs.launch.nl",
    mutationFn: async (input) => {
      const { idempotencyKey, ...body } = input;
      const record = await controlPreAdmissionRecoveryRepository.claim(
        scope,
        body,
        idempotencyKey,
      );
      if (record.idempotencyKey === null) {
        throw new Error("control_pre_admission_recovery_key_missing");
      }
      const stableIdempotencyKey = record.idempotencyKey;
      const recoveryQueryKey = queryKeys.controlPreAdmissionRecovery(scope);
      try {
        const result = await launchNlRun({
          ...body,
          idempotencyKey: stableIdempotencyKey,
        });
        if (result.pre_admission_attempt_id) {
          await controlPreAdmissionRecoveryRepository.rememberAttemptId(
            scope,
            result.pre_admission_attempt_id,
          );
        }
        return result;
      } catch (error) {
        const attemptId =
          typeof error === "object" &&
          error !== null &&
          "preAdmissionAttemptId" in error &&
          typeof (error as { preAdmissionAttemptId?: unknown })
            .preAdmissionAttemptId === "string"
            ? (error as { preAdmissionAttemptId: string }).preAdmissionAttemptId
            : null;
        if (attemptId) {
          await controlPreAdmissionRecoveryRepository.rememberAttemptId(
            scope,
            attemptId,
          );
        } else if (
          typeof error === "object" &&
          error !== null &&
          "preAdmissionNoAttempt" in error &&
          (error as { preAdmissionNoAttempt?: unknown })
            .preAdmissionNoAttempt === true
        ) {
          await controlPreAdmissionRecoveryRepository.releaseKnownNoAttempt(
            scope,
            body,
            stableIdempotencyKey,
          );
        }
        throw error;
      } finally {
        void queryClient.invalidateQueries({ queryKey: recoveryQueryKey });
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.runsRoot() });
    },
    successToast: (data) => ({
      title:
        data.status === "accepted"
          ? "Scenario launch accepted"
          : "Scenario launch rejected",
      description: data.message,
      tone: data.status === "accepted" ? "success" : "warning",
    }),
  });
  return { ...mutation, recovery };
}
