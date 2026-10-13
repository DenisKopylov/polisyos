import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "../queryKeys";
import {
  controlPreAdmissionRecoveryRepository,
  type ControlPreAdmissionRecoveryScope,
} from "../controlPreAdmissionRecovery";
import type { ControlPreAdmissionAttemptResponse } from "../validators";
import {
  fetchControlPreAdmissionAttemptByIdempotencyKey,
  fetchControlPreAdmissionAttemptStatus,
} from "./useControlPreAdmissionAttemptStatus";

export type ControlPreAdmissionRecoveryResponse =
  ControlPreAdmissionAttemptResponse;
export type ControlPreAdmissionRecoveryData = Readonly<{
  record: NonNullable<
    Awaited<ReturnType<typeof controlPreAdmissionRecoveryRepository.read>>
  >;
  attempt: ControlPreAdmissionRecoveryResponse | null;
}>;

export function useControlPreAdmissionRecovery(
  scope: ControlPreAdmissionRecoveryScope | null,
) {
  return useQuery({
    queryKey: queryKeys.controlPreAdmissionRecovery(scope),
    enabled: scope !== null,
    queryFn: async (): Promise<ControlPreAdmissionRecoveryData | null> => {
      if (scope === null) return null;
      const record = await controlPreAdmissionRecoveryRepository.read(scope);
      if (record === null) return null;
      if (
        record.idempotencyKey === null &&
        record.attemptId === null &&
        record.status === null
      ) {
        return null;
      }
      let attempt = record.attemptId
        ? await fetchControlPreAdmissionAttemptStatus(record.attemptId)
        : null;
      if (!attempt && record.idempotencyKey) {
        attempt = await fetchControlPreAdmissionAttemptByIdempotencyKey(
          record.idempotencyKey,
        );
      }
      const updatedRecord = attempt
        ? await controlPreAdmissionRecoveryRepository.observe(scope, attempt)
        : record;
      return { record: updatedRecord, attempt };
    },
    refetchInterval: (query) =>
      query.state.data?.record.idempotencyKey ? 2_000 : false,
    retry: false,
    refetchOnMount: "always",
    staleTime: 0,
  });
}
