import { useCallback, useRef } from "react";

import { useLaunchNlRun } from "@/api/hooks/useLaunchNlRun";
import { useLlmProfiles } from "@/api/hooks/useLlmProfiles";
import { getSseRealtimeTransport } from "@/app/realtime/sseTransport";
import type { RealtimeSubscription } from "@/app/realtime/types";
import {
  buildNaturalLanguageLaunchRequest,
  type NaturalLanguageLaunchFormValues,
} from "@/features/composer";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { buildClerkFormDefaults } from "../domain/clerkDefaults";
import {
  hasProducerFinishedAt,
  useChatStore,
} from "../state/useChatStore";

export function useClerkNlRun() {
  const { locale } = useI18n();
  const launchMutation = useLaunchNlRun();
  const profilesQuery = useLlmProfiles();
  const store = useChatStore();
  const sseRef = useRef<RealtimeSubscription | null>(null);

  const defaultModelId = profilesQuery.data?.profiles?.[0]?.model_id ?? null;

  const submit = useCallback(
    async (question: string, domainHint?: string) => {
      store.addUserMessage(question);

      const systemMsgId = `sys_${Date.now()}`;
      store.addSystemMessage({
        id: systemMsgId,
        content: "",
        timestamp: Date.now(),
      });
      store.setStreaming(true);

      const defaults = buildClerkFormDefaults(defaultModelId);
      const formValues: NaturalLanguageLaunchFormValues = {
        ...defaults,
        nlRequest: question,
        domainHint: domainHint || "",
      };

      const body = buildNaturalLanguageLaunchRequest(formValues, {
        locale,
        preflightEnabled: true,
        autoMaterializationEnabled: true,
        maxParallelConstraint: 1,
        maxIterationsConstraint: 10,
      });

      try {
        const result = await launchMutation.mutateAsync(body);

        if (result.status !== "accepted" || !result.run_id) {
          store.updateSystemMessage(systemMsgId, {
            content: result.message ?? "Launch rejected",
            controlJobId: result.job_id,
            error: result.message,
          });
          store.setStreaming(false);
          return;
        }

        const runId = result.run_id;
        store.setCurrentRunId(runId);
        store.updateSystemMessage(systemMsgId, {
          runId,
          content: "",
        });

        // Subscribe to SSE for live updates
        sseRef.current?.close();
        const transport = getSseRealtimeTransport();
        sseRef.current = transport.subscribe(
          { channel: "runs.byId", runId },
          {
            onMessage: (event) => {
              try {
                const payload = JSON.parse(event.data) as {
                  status?: string;
                  finished_at?: string;
                };
                const messageUpdate: {
                  runFinishedAt?: string;
                  runStatus?: string;
                } = {};
                if (typeof payload.status === "string") {
                  messageUpdate.runStatus = payload.status;
                }
                const runIsFinished = hasProducerFinishedAt(
                  payload.finished_at,
                );
                if (runIsFinished) {
                  messageUpdate.runFinishedAt = payload.finished_at;
                }
                if (Object.keys(messageUpdate).length > 0) {
                  store.updateSystemMessage(systemMsgId, messageUpdate);
                }

                if (runIsFinished) {
                  store.setStreaming(false);
                  store.setCurrentRunId(null);
                  sseRef.current?.close();
                  sseRef.current = null;
                }
              } catch {
                // ignore parse errors
              }
            },
            onError: () => {
              store.setStreaming(false);
            },
          },
        );
      } catch (err) {
        store.updateSystemMessage(systemMsgId, {
          content:
            err instanceof Error ? err.message : "Failed to launch analysis",
          error: err instanceof Error ? err.message : "Unknown error",
        });
        store.setStreaming(false);
      }
    },
    [defaultModelId, launchMutation, locale, store],
  );

  return {
    submit,
    isLoading: launchMutation.isPending || store.isStreaming,
    defaultModelId,
  };
}
