import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  approvePromotionRequest,
  rejectPromotionRequest,
} from "@/api/hooks/usePromotionDecision";
import { isRuntimeApiRequestError } from "@/api/http";
import { queryKeys } from "@/api/queryKeys";
import { useTelemetry } from "@/app/providers/TelemetryProvider";
import {
  deleteOfflineQueueItem,
  listOfflineQueueItems,
  type OfflinePromotionDecisionPayload,
  type OfflineQueueItem,
  type OfflineQueueItemKind,
  updateOfflineQueueItem,
  upsertOfflineQueueItem,
} from "@/app/offline/offlineQueueRepository";
import { useNetworkStatus } from "@/shared/network";
import { useLogger } from "@/shared/telemetry/logger";

export const OFFLINE_QUEUE_SYNC_TAG = "runtime-dashboard-offline-queue";

type OfflineQueueContextValue = {
  enqueuePromotionDecision: (
    kind: OfflineQueueItemKind,
    payload: OfflinePromotionDecisionPayload,
  ) => Promise<OfflineQueueItem>;
  flushQueue: () => Promise<void>;
  isFlushing: boolean;
  items: OfflineQueueItem[];
};

const OfflineQueueContext = createContext<OfflineQueueContextValue | null>(null);

function isPermanentQueueFailure(error: unknown) {
  if (!isRuntimeApiRequestError(error)) {
    return false;
  }

  return (
    error.status >= 400 &&
    error.status < 500 &&
    error.status !== 408 &&
    error.status !== 429
  );
}

function shouldRetryQueueItem(error: unknown) {
  return !isPermanentQueueFailure(error);
}

type SyncCapableServiceWorkerRegistration = ServiceWorkerRegistration & {
  sync?: {
    register: (tag: string) => Promise<void>;
  };
};

function getQueueErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function getQueueErrorStatus(error: unknown) {
  return isRuntimeApiRequestError(error) ? error.status : 0;
}

async function requestQueuedMutation(item: OfflineQueueItem) {
  if (item.kind === "promotion.approve") {
    await approvePromotionRequest(item.payload);
    return;
  }
  await rejectPromotionRequest(item.payload);
}

export function OfflineQueueProvider({ children }: PropsWithChildren) {
  const { online } = useNetworkStatus();
  const { track } = useTelemetry();
  const logger = useLogger({
    tags: {
      area: "offline-queue",
    },
  });
  const queryClient = useQueryClient();
  const [items, setItems] = useState<OfflineQueueItem[]>([]);
  const [isFlushing, setIsFlushing] = useState(false);
  const flushingRef = useRef(false);

  const refreshItems = useCallback(async () => {
    setItems(await listOfflineQueueItems());
  }, []);

  const invalidatePromotionCaches = useCallback(() => {
    void queryClient.invalidateQueries({
      queryKey: queryKeys.dataPromotionCandidates(),
    });
    void queryClient.invalidateQueries({ queryKey: queryKeys.dataIndexStats() });
  }, [queryClient]);

  const requestBackgroundSync = useCallback(async () => {
    if (
      typeof window === "undefined" ||
      !("serviceWorker" in navigator) ||
      !("SyncManager" in window)
    ) {
      return;
    }

    try {
      const registration = await navigator.serviceWorker.ready;
      await (registration as SyncCapableServiceWorkerRegistration).sync?.register(
        OFFLINE_QUEUE_SYNC_TAG,
      );
    } catch {
      // Best-effort only.
    }
  }, []);

  const enqueuePromotionDecision = useCallback(
    async (
      kind: OfflineQueueItemKind,
      payload: OfflinePromotionDecisionPayload,
    ) => {
      const item = await upsertOfflineQueueItem(kind, payload);
      logger.info({
        event: "offline.queue.enqueued",
        message: `Queued offline mutation ${kind}`,
        tags: {
          entityKey: item.entityKey,
          kind,
        },
      });
      track("offline.queue.enqueued", {
        entityKey: item.entityKey,
        kind: item.kind,
      });
      await refreshItems();
      await requestBackgroundSync();
      return item;
    },
    [refreshItems, requestBackgroundSync, track],
  );

  const flushQueue = useCallback(async () => {
    if (flushingRef.current || !online) {
      return;
    }

    flushingRef.current = true;
    setIsFlushing(true);

    try {
      const queuedItems = (await listOfflineQueueItems()).filter(
        (item) =>
          item.status !== "failed" &&
          (item.nextAttemptAt == null || item.nextAttemptAt <= Date.now()),
      );

      for (const item of queuedItems) {
        try {
          await requestQueuedMutation(item);
          await deleteOfflineQueueItem(item.entityKey);
          invalidatePromotionCaches();
          logger.info({
            event: "offline.queue.flushed",
            message: `Flushed offline mutation ${item.kind}`,
            tags: {
              entityKey: item.entityKey,
              kind: item.kind,
            },
          });
          track("offline.queue.flushed", {
            entityKey: item.entityKey,
            kind: item.kind,
          });
        } catch (error) {
          const attempts = item.attempts + 1;

          if (shouldRetryQueueItem(error)) {
            const delayMs = Math.min(60_000, 1_000 * 2 ** attempts);
            logger.warn({
              error,
              event: "offline.queue.retry_scheduled",
              message: `Retry scheduled for ${item.kind}`,
              tags: {
                delayMs,
                entityKey: item.entityKey,
                kind: item.kind,
              },
            });
            await updateOfflineQueueItem({
              ...item,
              attempts,
              lastError: getQueueErrorMessage(error),
              lastStatus: getQueueErrorStatus(error),
              nextAttemptAt: Date.now() + delayMs,
              status: "retrying",
              updatedAt: Date.now(),
            });
            track("offline.queue.retry_scheduled", {
              delayMs,
              entityKey: item.entityKey,
              kind: item.kind,
            });
            continue;
          }

          logger.error({
            error,
            event: "offline.queue.failed",
            message: `Offline mutation permanently failed for ${item.kind}`,
            tags: {
              entityKey: item.entityKey,
              kind: item.kind,
              status: getQueueErrorStatus(error),
            },
          });
          await updateOfflineQueueItem({
            ...item,
            attempts,
            lastError: getQueueErrorMessage(error),
            lastStatus: getQueueErrorStatus(error),
            nextAttemptAt: null,
            status: "failed",
            updatedAt: Date.now(),
          });
          invalidatePromotionCaches();
          track("offline.queue.failed", {
            entityKey: item.entityKey,
            kind: item.kind,
            status: getQueueErrorStatus(error),
          });
        }
      }
    } finally {
      await refreshItems();
      flushingRef.current = false;
      setIsFlushing(false);
    }
  }, [invalidatePromotionCaches, logger, online, refreshItems, track]);

  useEffect(() => {
    void refreshItems();
  }, [refreshItems]);

  useEffect(() => {
    if (!online) {
      return;
    }
    void flushQueue();
  }, [flushQueue, online]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void flushQueue();
      }
    };

    const handleWorkerMessage = (event: MessageEvent<{ type?: string }>) => {
      if (event.data?.type === "offline-queue:flush") {
        void flushQueue();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    navigator.serviceWorker?.addEventListener?.("message", handleWorkerMessage);

    return () => {
      document.removeEventListener(
        "visibilitychange",
        handleVisibilityChange,
      );
      navigator.serviceWorker?.removeEventListener?.(
        "message",
        handleWorkerMessage,
      );
    };
  }, [flushQueue]);

  const value = useMemo<OfflineQueueContextValue>(
    () => ({
      enqueuePromotionDecision,
      flushQueue,
      isFlushing,
      items,
    }),
    [enqueuePromotionDecision, flushQueue, isFlushing, items],
  );

  return (
    <OfflineQueueContext.Provider value={value}>
      {children}
    </OfflineQueueContext.Provider>
  );
}

export function useOfflineQueue() {
  const context = useContext(OfflineQueueContext);
  if (!context) {
    throw new Error(
      "useOfflineQueue must be used within an OfflineQueueProvider",
    );
  }
  return context;
}
