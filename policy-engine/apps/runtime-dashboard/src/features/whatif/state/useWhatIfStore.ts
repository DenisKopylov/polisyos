import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Scenario, ImpactMetric } from "../types";

type WhatIfState = {
  /** Current parameter overrides being explored. */
  currentParameters: Record<string, number>;
  /** Projected impact of current parameters (set by ImpactPreview callback). */
  currentImpact: ImpactMetric[];
  /** Base run ID for this what-if session. */
  baseRunId: string | null;
  /** Saved scenarios. */
  scenarios: Scenario[];

  // Actions
  setBaseRunId: (id: string) => void;
  setParameter: (key: string, value: number) => void;
  setParameters: (params: Record<string, number>) => void;
  resetParameters: (defaults: Record<string, number>) => void;
  setCurrentImpact: (impact: ImpactMetric[]) => void;
  saveScenario: (name: string) => void;
  deleteScenario: (id: string) => void;
  loadScenario: (id: string) => void;
  clear: () => void;
};

export const useWhatIfStore = create<WhatIfState>()(
  persist(
    (set, get) => ({
      currentParameters: {},
      currentImpact: [],
      baseRunId: null,
      scenarios: [],

      setBaseRunId: (id) => set({ baseRunId: id }),

      setParameter: (key, value) =>
        set((state) => ({
          currentParameters: { ...state.currentParameters, [key]: value },
        })),

      setParameters: (params) =>
        set((state) => ({
          currentParameters: { ...state.currentParameters, ...params },
        })),

      resetParameters: (defaults) =>
        set({ currentParameters: defaults, currentImpact: [] }),

      setCurrentImpact: (impact) => set({ currentImpact: impact }),

      saveScenario: (name) => {
        const state = get();
        const scenario: Scenario = {
          id: `scenario-${Date.now()}`,
          name,
          baseRunId: state.baseRunId ?? "",
          parameters: { ...state.currentParameters },
          metrics: [...state.currentImpact],
          createdAt: Date.now(),
        };
        set((prev) => ({
          scenarios: [...prev.scenarios, scenario],
        }));
      },

      deleteScenario: (id) =>
        set((state) => ({
          scenarios: state.scenarios.filter((s) => s.id !== id),
        })),

      loadScenario: (id) => {
        const scenario = get().scenarios.find((s) => s.id === id);
        if (scenario) {
          set({
            currentParameters: { ...scenario.parameters },
            currentImpact: scenario.metrics ?? [],
            baseRunId: scenario.baseRunId,
          });
        }
      },

      clear: () =>
        set({
          currentParameters: {},
          currentImpact: [],
          baseRunId: null,
        }),
    }),
    {
      name: "polisyos.runtime.whatif",
      version: 1,
      partialize: (state) => ({ scenarios: state.scenarios }),
    },
  ),
);
