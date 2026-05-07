import { openDB } from "idb";

export const OFFLINE_DB_NAME = "runtime-dashboard-offline";
export const OFFLINE_DB_VERSION = 1;
export const OFFLINE_MUTATION_QUEUE_STORE = "offline-mutation-queue";
export const COMPOSER_DRAFTS_STORE = "composer-drafts";

export function openOfflineDb() {
  return openDB(OFFLINE_DB_NAME, OFFLINE_DB_VERSION, {
    upgrade(database) {
      if (!database.objectStoreNames.contains(OFFLINE_MUTATION_QUEUE_STORE)) {
        const queueStore = database.createObjectStore(
          OFFLINE_MUTATION_QUEUE_STORE,
          {
            keyPath: "entityKey",
          },
        );
        queueStore.createIndex("status", "status");
        queueStore.createIndex("updatedAt", "updatedAt");
      }

      if (!database.objectStoreNames.contains(COMPOSER_DRAFTS_STORE)) {
        database.createObjectStore(COMPOSER_DRAFTS_STORE, {
          keyPath: "key",
        });
      }
    },
  });
}
