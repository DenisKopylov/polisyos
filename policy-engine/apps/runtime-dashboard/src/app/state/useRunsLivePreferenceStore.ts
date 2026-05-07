import { create } from "zustand";
import {
  createJSONStorage,
  persist,
  type StateStorage,
} from "zustand/middleware";

type RunsLivePreferenceState = {
  disableLive: boolean;
  setDisableLive: (disableLive: boolean) => void;
};

export const RUNS_LIVE_PREFERENCE_STORAGE_KEY = "polisyos.runtime.disableLive";

const runsLivePreferenceStorage: StateStorage = {
  getItem: (name) => {
    if (typeof window === "undefined") {
      return null;
    }
    const raw = window.localStorage.getItem(name);
    if (raw === "true" || raw === "false") {
      return JSON.stringify({
        state: { disableLive: raw === "true" },
        version: 0,
      });
    }
    return raw;
  },
  removeItem: (name) => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.removeItem(name);
  },
  setItem: (name, value) => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(name, value);
  },
};

export const useRunsLivePreferenceStore = create<RunsLivePreferenceState>()(
  persist(
    (set) => ({
      disableLive: false,
      setDisableLive: (disableLive) => {
        set({ disableLive });
      },
    }),
    {
      name: RUNS_LIVE_PREFERENCE_STORAGE_KEY,
      storage: createJSONStorage(() => runsLivePreferenceStorage),
    },
  ),
);

export function readRunsLiveDisabledPreference() {
  if (typeof window === "undefined") {
    return false;
  }

  const raw = window.localStorage.getItem(RUNS_LIVE_PREFERENCE_STORAGE_KEY);
  if (raw === "true") {
    return true;
  }
  if (raw === "false") {
    return false;
  }

  try {
    const parsed = JSON.parse(raw ?? "null") as {
      state?: { disableLive?: boolean };
    } | null;
    return parsed?.state?.disableLive === true;
  } catch {
    return false;
  }
}

export function resetRunsLivePreferenceStore() {
  useRunsLivePreferenceStore.setState({ disableLive: false });
}
