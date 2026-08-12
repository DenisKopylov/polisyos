import { COMPOSER_DRAFTS_STORE, openOfflineDb } from "@/app/offline/db";

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
