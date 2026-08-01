import { createContext, type PropsWithChildren, useContext } from "react";

import type { ScenarioCapability } from "@polisyos/runtime-api-client";

export type CounterfactualMode = NonNullable<
  ScenarioCapability["supported_modes"]
>[number];

export type CounterfactualInteractionBridgeValue = {
  mode: CounterfactualMode;
  scenarioId: string | null;
  setMode: (mode: CounterfactualMode) => void;
  setScenarioId: (scenarioId: string | null) => void;
};

const COUNTERFACTUAL_MODE_MEMBERSHIP = {
  actual: true,
  actual_vs_scenario: true,
  scenario_only: true,
} as const satisfies Record<CounterfactualMode, true>;

export const COUNTERFACTUAL_MODES = Object.freeze(
  Object.keys(COUNTERFACTUAL_MODE_MEMBERSHIP) as CounterfactualMode[],
);

const CounterfactualInteractionContext =
  createContext<CounterfactualInteractionBridgeValue | null>(null);

export function CounterfactualInteractionBridgeProvider({
  children,
  value,
}: PropsWithChildren<{ value: CounterfactualInteractionBridgeValue }>) {
  return (
    <CounterfactualInteractionContext.Provider value={value}>
      {children}
    </CounterfactualInteractionContext.Provider>
  );
}

export function useMaybeCounterfactualInteraction() {
  return useContext(CounterfactualInteractionContext);
}

export function normalizeCounterfactualMode(
  value: string | null | undefined,
): CounterfactualMode {
  return value != null && Object.hasOwn(COUNTERFACTUAL_MODE_MEMBERSHIP, value)
    ? (value as CounterfactualMode)
    : "actual";
}
