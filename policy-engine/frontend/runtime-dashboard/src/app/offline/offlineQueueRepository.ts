import {
  COMPOSER_DRAFTS_STORE,
  OFFLINE_MUTATION_QUEUE_STORE,
  openOfflineDb,
} from "@/app/offline/db";

export type OfflineQueueItemKind = "promotion.approve" | "promotion.reject";
export type OfflineQueueItemStatus = "failed" | "queued" | "retrying";
export type OfflinePromotionDecisionPayload = {
  promotionId: string;
  reason?: string;
  runId?: string;
};
export type OfflineQueueItem = {
  attempts: number;
  createdAt: number;
  entityKey: string;
  kind: OfflineQueueItemKind;
  lastError: string | null;
  lastStatus: number | null;
  nextAttemptAt: number | null;
  payload: OfflinePromotionDecisionPayload;
  status: OfflineQueueItemStatus;
  updatedAt: number;
};

function buildEntityKey(payload: OfflinePromotionDecisionPayload) {
  return `promotion:${payload.promotionId}`;
}

export async function listOfflineQueueItems() {
  const database = await openOfflineDb();
  const items = (await database.getAll(
    OFFLINE_MUTATION_QUEUE_STORE,
  )) as OfflineQueueItem[];
  return items.sort((left, right) => left.createdAt - right.createdAt);
}

export async function upsertOfflineQueueItem(
  kind: OfflineQueueItemKind,
  payload: OfflinePromotionDecisionPayload,
) {
  const database = await openOfflineDb();
  const now = Date.now();
  const entityKey = buildEntityKey(payload);
  const previous = await database.get(OFFLINE_MUTATION_QUEUE_STORE, entityKey);
  const nextItem: OfflineQueueItem = {
    attempts: previous?.attempts ?? 0,
    createdAt: previous?.createdAt ?? now,
    entityKey,
    kind,
    lastError: null,
    lastStatus: null,
    nextAttemptAt: now,
    payload,
    status: "queued",
    updatedAt: now,
  };

  await database.put(OFFLINE_MUTATION_QUEUE_STORE, nextItem);
  return nextItem;
}

export async function deleteOfflineQueueItem(entityKey: string) {
  const database = await openOfflineDb();
  await database.delete(OFFLINE_MUTATION_QUEUE_STORE, entityKey);
}

export async function updateOfflineQueueItem(item: OfflineQueueItem) {
  const database = await openOfflineDb();
  await database.put(OFFLINE_MUTATION_QUEUE_STORE, item);
  return item;
}

export async function clearOfflineQueue() {
  const database = await openOfflineDb();
  await database.clear(OFFLINE_MUTATION_QUEUE_STORE);
}

export async function loadComposerDraftRecord(key: string) {
  const database = await openOfflineDb();
  return await database.get(COMPOSER_DRAFTS_STORE, key);
}

export async function saveComposerDraftRecord(draft: { key: string }) {
  const database = await openOfflineDb();
  await database.put(COMPOSER_DRAFTS_STORE, draft);
}

export async function deleteComposerDraftRecord(key: string) {
  const database = await openOfflineDb();
  await database.delete(COMPOSER_DRAFTS_STORE, key);
}
