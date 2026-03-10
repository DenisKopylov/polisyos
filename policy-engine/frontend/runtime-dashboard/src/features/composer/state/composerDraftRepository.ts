import type {
  NaturalLanguageLaunchFormValues,
  WorkflowLaunchFormValues,
} from "@/features/composer/domain/forms";
import {
  deleteComposerDraftRecord,
  loadComposerDraftRecord,
  saveComposerDraftRecord,
} from "@/app/offline/offlineQueueRepository";

export type ComposerDraftMode = "nl" | "workflow";
export type ComposerDraftValues =
  | NaturalLanguageLaunchFormValues
  | WorkflowLaunchFormValues;
export type ComposerDraftRecord = {
  fromRunId: string | null;
  key: string;
  mode: ComposerDraftMode;
  updatedAt: number;
  values: ComposerDraftValues;
};

export function buildComposerDraftKey(
  mode: ComposerDraftMode,
  fromRunId: string | null,
) {
  return `${mode}:${fromRunId ?? "new"}`;
}

export async function loadComposerDraft(key: string) {
  return loadComposerDraftRecord<ComposerDraftRecord>(key);
}

export async function saveComposerDraft(draft: ComposerDraftRecord) {
  await saveComposerDraftRecord(draft);
}

export async function deleteComposerDraft(key: string) {
  await deleteComposerDraftRecord(key);
}
