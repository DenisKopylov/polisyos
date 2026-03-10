import type {
  MutationFunction,
  MutationKey,
} from "@tanstack/react-query";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  classifyRuntimeApiError,
  RuntimeApiRequestError,
} from "@/api/http";
import { useMaybeNetworkStatus } from "@/shared/network";
import { useTelemetry } from "@/app/providers/TelemetryProvider";
import type { ToastInput } from "@/app/providers/ToastProvider";
import { useToast } from "@/app/providers/ToastProvider";
import { useLogger } from "@/shared/telemetry/logger";

type QueryKeyResolver<TData, TVariables, TContext> =
  | readonly unknown[]
  | ((args: {
      context: TContext | undefined;
      data: TData;
      variables: TVariables;
    }) => readonly unknown[] | undefined);

type ToastResolver<TPayload> =
  | ToastInput
  | false
  | ((payload: TPayload) => ToastInput | false);

type ControlPlaneMutationOptions<TData, TVariables, TContext> = {
  mutationId: string;
  mutationFn: MutationFunction<TData, TVariables>;
  mutationKey?: MutationKey;
  onMutate?: (variables: TVariables) => Promise<TContext> | TContext;
  onError?: (
    error: unknown,
    variables: TVariables,
    context: TContext | undefined,
  ) => void;
  onSuccess?: (
    data: TData,
    variables: TVariables,
    context: TContext | undefined,
  ) => void;
  blockWhenOffline?: boolean;
  onSettled?: (
    data: TData | undefined,
    error: unknown | null,
    variables: TVariables,
    context: TContext | undefined,
  ) => void;
  invalidate?: Array<QueryKeyResolver<TData, TVariables, TContext>>;
  successToast?: ToastResolver<TData>;
  errorToast?: ToastResolver<unknown>;
};

function resolveToast<TPayload>(
  input: ToastResolver<TPayload> | undefined,
  payload: TPayload,
) {
  if (!input) {
    return false;
  }
  return typeof input === "function" ? input(payload) : input;
}

export function useControlPlaneMutation<
  TData,
  TVariables,
  TContext = unknown,
>({
  errorToast,
  blockWhenOffline = false,
  invalidate = [],
  mutationFn,
  mutationId,
  mutationKey,
  onError,
  onMutate,
  onSettled,
  onSuccess,
  successToast,
}: ControlPlaneMutationOptions<TData, TVariables, TContext>) {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();
  const { track } = useTelemetry();
  const networkStatus = useMaybeNetworkStatus();
  const logger = useLogger({
    tags: {
      mutation: mutationId,
    },
  });

  return useMutation<TData, unknown, TVariables, TContext>({
    mutationFn: async (variables, context) => {
      if (blockWhenOffline && networkStatus && !networkStatus.online) {
        throw new RuntimeApiRequestError(
          null,
          0,
          "This action is unavailable while offline.",
        );
      }
      return mutationFn(variables, context);
    },
    mutationKey,
    onMutate: async (variables) => {
      logger.info({
        event: `mutation.${mutationId}.started`,
        message: `Started mutation ${mutationId}`,
      });
      track("mutation.started", {
        mutationId,
      });
      return onMutate ? await onMutate(variables) : (undefined as TContext);
    },
    onError: (error, variables, context) => {
      const errorKind = classifyRuntimeApiError(error);
      logger.warn({
        error,
        event: `mutation.${mutationId}.error`,
        message: `Mutation ${mutationId} failed`,
        tags: {
          errorKind,
        },
      });
      track("mutation.error", {
        errorKind,
        mutationId,
      });
      const toast = resolveToast(errorToast, error);
      if (toast) {
        pushToast({
          tone: "error",
          ...toast,
        });
      }
      onError?.(error, variables, context);
    },
    onSuccess: async (data, variables, context) => {
      logger.info({
        event: `mutation.${mutationId}.success`,
        message: `Mutation ${mutationId} succeeded`,
      });
      track("mutation.success", {
        mutationId,
      });
      const toast = resolveToast(successToast, data);
      if (toast) {
        pushToast({
          tone: "success",
          ...toast,
        });
      }
      onSuccess?.(data, variables, context);
      for (const invalidation of invalidate) {
        const queryKey =
          typeof invalidation === "function"
            ? invalidation({ context, data, variables })
            : invalidation;
        if (!queryKey) {
          continue;
        }
        await queryClient.invalidateQueries({ queryKey });
      }
    },
    onSettled: (data, error, variables, context) => {
      onSettled?.(data, error ?? null, variables, context);
    },
  });
}
