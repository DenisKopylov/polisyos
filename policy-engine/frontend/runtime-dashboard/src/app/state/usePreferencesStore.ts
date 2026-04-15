import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Density = "compact" | "comfortable" | "spacious";

type PreferencesState = {
  density: Density;
  sidebarCollapsed: boolean;
  commandPaletteHintDismissed: boolean;
};

type PreferencesActions = {
  setDensity: (density: Density) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
  setCommandPaletteHintDismissed: (dismissed: boolean) => void;
  reset: () => void;
};

const INITIAL_STATE: PreferencesState = {
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
      setDensity: (density) => set({ density }),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
      toggleSidebar: () =>
        set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setCommandPaletteHintDismissed: (commandPaletteHintDismissed) =>
        set({ commandPaletteHintDismissed }),
      reset: () => set(INITIAL_STATE),
    }),
    {
      name: "polisyos.runtime.preferences",
      version: 1,
    },
  ),
);

export function readPreferencesFromStorage(): PreferencesState {
  try {
    const raw = window.localStorage.getItem("polisyos.runtime.preferences");
    if (!raw) return INITIAL_STATE;
    const parsed = JSON.parse(raw) as { state?: Partial<PreferencesState> };
    return { ...INITIAL_STATE, ...parsed.state };
  } catch {
    return INITIAL_STATE;
  }
}

export function resetPreferencesStore() {
  usePreferencesStore.getState().reset();
}
