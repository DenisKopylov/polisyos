import { create } from "zustand";
import { persist } from "zustand/middleware";

import {
  normalizeAuthorshipHighlightMode,
  type AuthorshipHighlightMode,
} from "@/shared/ui/authored-text";
import {
  densityScale,
  type DensityScaleKey,
} from "@/shared/ui/tokens/designTokens";

export type Density = DensityScaleKey;

export const PREFERENCES_STORAGE_KEY = "polisyos.runtime.preferences";

function isDensity(value: unknown): value is Density {
  return typeof value === "string" && value in densityScale;
}

export function normalizeDensity(value: unknown): Density {
  if (value === "spacious") {
    return "comfortable";
  }
  return isDensity(value) ? value : "comfortable";
}

type PreferencesState = {
  authorshipHighlightMode: AuthorshipHighlightMode;
  density: Density;
  sidebarCollapsed: boolean;
  commandPaletteHintDismissed: boolean;
};

type PreferencesActions = {
  setAuthorshipHighlightMode: (
    authorshipHighlightMode: AuthorshipHighlightMode,
  ) => void;
  setDensity: (density: Density) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
  setCommandPaletteHintDismissed: (dismissed: boolean) => void;
  reset: () => void;
};

const INITIAL_STATE: PreferencesState = {
  authorshipHighlightMode: "subtle",
  density: "comfortable",
  sidebarCollapsed: false,
  commandPaletteHintDismissed: false,
};

export const usePreferencesStore = create<
  PreferencesState & PreferencesActions
>()(
  persist(
    (set) => ({
      ...INITIAL_STATE,
      setAuthorshipHighlightMode: (authorshipHighlightMode) =>
        set({ authorshipHighlightMode }),
      setDensity: (density) => set({ density }),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
      toggleSidebar: () =>
        set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setCommandPaletteHintDismissed: (commandPaletteHintDismissed) =>
        set({ commandPaletteHintDismissed }),
      reset: () => set(INITIAL_STATE),
    }),
    {
      migrate: (persistedState) => {
        const persisted = persistedState as
          | { state?: Partial<PreferencesState> }
          | undefined;
        const state = persisted?.state ?? persistedState;

        return {
          ...INITIAL_STATE,
          ...(state as Partial<PreferencesState> | undefined),
          authorshipHighlightMode: normalizeAuthorshipHighlightMode(
            (state as Partial<PreferencesState> | undefined)
              ?.authorshipHighlightMode,
          ),
          density: normalizeDensity(
            (state as Partial<PreferencesState> | undefined)?.density,
          ),
        };
      },
      name: PREFERENCES_STORAGE_KEY,
      version: 3,
    },
  ),
);

export function readPreferencesFromStorage(): PreferencesState {
  try {
    const raw = window.localStorage.getItem(PREFERENCES_STORAGE_KEY);
    if (!raw) return INITIAL_STATE;
    const parsed = JSON.parse(raw) as { state?: Partial<PreferencesState> };
    return {
      ...INITIAL_STATE,
      ...parsed.state,
      authorshipHighlightMode: normalizeAuthorshipHighlightMode(
        parsed.state?.authorshipHighlightMode,
      ),
      density: normalizeDensity(parsed.state?.density),
    };
  } catch {
    return INITIAL_STATE;
  }
}

export function resetPreferencesStore() {
  usePreferencesStore.getState().reset();
}
