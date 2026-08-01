import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useMaybeTemporalCursor } from "@/shared/ui/temporal/TemporalRuntimeBridge";
import { CounterfactualInteractionBridgeProvider } from "@/shared/ui/counterfactual/CounterfactualInteractionBridge";
import {
  compareScenarioScopes,
  normalizeScenarioScope,
  readScenarioScopeFromLocation,
  replaceScenarioScopeInCurrentUrl,
  type CounterfactualMode,
  type ScenarioScope,
} from "./scenario-scope";

type CounterfactualContextValue = {
  scope: ScenarioScope;
  scenarioId: string | null;
  mode: CounterfactualMode;
  setScenarioId: (
    scenarioId: string | null,
    options?: { replaceUrl?: boolean },
  ) => void;
  setMode: (
    mode: CounterfactualMode,
    options?: { replaceUrl?: boolean },
  ) => void;
  commitScope: (
    scope: ScenarioScope | null,
    options?: { replaceUrl?: boolean },
  ) => void;
  resetScope: (options?: { replaceUrl?: boolean }) => void;
};

const CounterfactualContext = createContext<CounterfactualContextValue | null>(
  null,
);

export function CounterfactualProvider({ children }: PropsWithChildren) {
  const temporalCursor = useMaybeTemporalCursor();
  const [scope, setScope] = useState<ScenarioScope>(() => readInitialScope());
  const scopeRef = useRef(scope);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const syncFromUrl = () => {
      const nextScope = readScenarioScopeFromLocation(window.location);
      scopeRef.current = nextScope;
      setScope(nextScope);
    };
    window.addEventListener("popstate", syncFromUrl);
    return () => window.removeEventListener("popstate", syncFromUrl);
  }, []);

  const commitScope = useCallback(
    (
      nextScope: ScenarioScope | null,
      options: { replaceUrl?: boolean } = {},
    ) => {
      const normalized = normalizeScenarioScope(nextScope);
      scopeRef.current = normalized;
      setScope((current) =>
        compareScenarioScopes(current, normalized) ? current : normalized,
      );
      if (temporalCursor) {
        temporalCursor.commitScope(
          {
            ...(temporalCursor.committedScope ?? {}),
            scenarioId: normalized.scenarioId ?? null,
          },
          { replaceUrl: false },
        );
      }
      if (options.replaceUrl ?? true) {
        replaceScenarioScopeInCurrentUrl(normalized);
      }
    },
    [temporalCursor],
  );

  const setScenarioId = useCallback(
    (scenarioId: string | null, options: { replaceUrl?: boolean } = {}) => {
      commitScope({ ...scopeRef.current, scenarioId }, options);
    },
    [commitScope],
  );

  const setMode = useCallback(
    (mode: CounterfactualMode, options: { replaceUrl?: boolean } = {}) => {
      commitScope({ ...scopeRef.current, mode }, options);
    },
    [commitScope],
  );

  const resetScope = useCallback(
    (options: { replaceUrl?: boolean } = {}) => {
      commitScope({ mode: "actual", scenarioId: null }, options);
    },
    [commitScope],
  );

  const value = useMemo<CounterfactualContextValue>(() => {
    const normalized = normalizeScenarioScope(scope);
    return {
      commitScope,
      mode: normalized.mode ?? "actual",
      resetScope,
      scenarioId: normalized.scenarioId ?? null,
      scope: normalized,
      setMode,
      setScenarioId,
    };
  }, [commitScope, resetScope, scope, setMode, setScenarioId]);

  return (
    <CounterfactualContext.Provider value={value}>
      <CounterfactualInteractionBridgeProvider value={value}>
        {children}
      </CounterfactualInteractionBridgeProvider>
    </CounterfactualContext.Provider>
  );
}

export function useCounterfactual() {
  const context = useContext(CounterfactualContext);
  if (!context) {
    throw new Error(
      "useCounterfactual must be used within CounterfactualProvider",
    );
  }
  return context;
}

export function useMaybeCounterfactual() {
  return useContext(CounterfactualContext);
}

function readInitialScope() {
  if (typeof window === "undefined") {
    return normalizeScenarioScope(null);
  }
  return readScenarioScopeFromLocation(window.location);
}
