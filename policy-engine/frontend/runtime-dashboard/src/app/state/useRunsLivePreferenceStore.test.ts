import {
  readRunsLiveDisabledPreference,
  resetRunsLivePreferenceStore,
  RUNS_LIVE_PREFERENCE_STORAGE_KEY,
  useRunsLivePreferenceStore,
} from "@/app/state/useRunsLivePreferenceStore";

describe("useRunsLivePreferenceStore", () => {
  beforeEach(() => {
    window.localStorage.clear();
    resetRunsLivePreferenceStore();
  });

  it("persists the live updates preference to localStorage", () => {
    useRunsLivePreferenceStore.getState().setDisableLive(true);

    expect(window.localStorage.getItem(RUNS_LIVE_PREFERENCE_STORAGE_KEY)).toContain(
      "\"disableLive\":true",
    );
    expect(readRunsLiveDisabledPreference()).toBe(true);
  });

  it("reads legacy boolean values from localStorage", () => {
    window.localStorage.setItem(RUNS_LIVE_PREFERENCE_STORAGE_KEY, "true");
    expect(readRunsLiveDisabledPreference()).toBe(true);

    window.localStorage.setItem(RUNS_LIVE_PREFERENCE_STORAGE_KEY, "false");
    expect(readRunsLiveDisabledPreference()).toBe(false);
  });
});
