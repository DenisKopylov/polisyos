import { openDB } from "idb";

export const OFFLINE_DB_NAME = "runtime-dashboard-offline";
export const OFFLINE_DB_VERSION = 3;
export const COMPOSER_DRAFTS_STORE = "composer-drafts";
export const CONTROL_PRE_ADMISSION_RECOVERY_STORE =
  "control-pre-admission-recovery";

export function openOfflineDb() {
  return openDB(OFFLINE_DB_NAME, OFFLINE_DB_VERSION, {
    upgrade(database) {
      if (database.objectStoreNames.contains("offline-mutation-queue")) {
        database.deleteObjectStore("offline-mutation-queue");
      }

      if (!database.objectStoreNames.contains(COMPOSER_DRAFTS_STORE)) {
        database.createObjectStore(COMPOSER_DRAFTS_STORE, {
          keyPath: "key",
        });
      }

      if (
        !database.objectStoreNames.contains(
          CONTROL_PRE_ADMISSION_RECOVERY_STORE,
        )
      ) {
        database.createObjectStore(CONTROL_PRE_ADMISSION_RECOVERY_STORE, {
          keyPath: "scopeKey",
        });
      }
    },
  });
}
