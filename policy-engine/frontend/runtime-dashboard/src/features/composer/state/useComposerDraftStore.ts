import { create } from "zustand";

import type { ComposerDraftRecord } from "@/features/composer/state/composerDraftRepository";

type ComposerDraftState = {
  clearDraft: (key: string) => void;
  drafts: Record<string, ComposerDraftRecord>;
  hydrateDraft: (draft: ComposerDraftRecord | null) => void;
  reset: () => void;
  upsertDraft: (draft: ComposerDraftRecord) => void;
};

export const useComposerDraftStore = create<ComposerDraftState>((set) => ({
  clearDraft: (key) => {
    set((state) => {
      const { [key]: _removed, ...nextDrafts } = state.drafts;
      return { drafts: nextDrafts };
    });
  },
  drafts: {},
  hydrateDraft: (draft) => {
    if (!draft) {
      return;
    }
    set((state) => ({
      drafts: {
        ...state.drafts,
        [draft.key]: draft,
      },
    }));
  },
  reset: () => {
    set({ drafts: {} });
  },
  upsertDraft: (draft) => {
    set((state) => ({
      drafts: {
        ...state.drafts,
        [draft.key]: draft,
      },
    }));
  },
}));
