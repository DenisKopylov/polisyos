import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { useMaybeAuthz } from "@/app/authz/AuthzProvider";
import { useFeatureFlag } from "@/app/providers/FeatureFlagProvider";

export type InterfaceMode = "clerk" | "analyst";

const INTERFACE_MODE_STORAGE_KEY = "polisyos.runtime.interface-mode";

type InterfaceModeContextValue = {
  isAnalyst: boolean;
  isClerk: boolean;
  mode: InterfaceMode;
  setMode: (mode: InterfaceMode) => void;
};

const InterfaceModeContext = createContext<InterfaceModeContextValue | null>(
  null,
);

function isInterfaceMode(
  value: string | null | undefined,
): value is InterfaceMode {
  return value === "clerk" || value === "analyst";
}

function readStoredMode(): InterfaceMode | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(INTERFACE_MODE_STORAGE_KEY);
  return isInterfaceMode(raw) ? raw : null;
}

export function InterfaceModeProvider({ children }: PropsWithChildren) {
  const clerkModeEnabled = useFeatureFlag("enableClerkMode");
  const authz = useMaybeAuthz();
  const canUseAnalyst = authz?.can("mode.analyst") ?? true;

  const [mode, setModeState] = useState<InterfaceMode>(() => {
    if (!clerkModeEnabled) return "analyst";
    const stored = readStoredMode();
    if (stored)
      return stored === "analyst" && !canUseAnalyst ? "clerk" : stored;
    return canUseAnalyst ? "analyst" : "clerk";
  });

  const setMode = useCallback(
    (nextMode: InterfaceMode) => {
      if (!clerkModeEnabled) return;
      if (nextMode === "analyst" && !canUseAnalyst) return;
      setModeState(nextMode);
    },
    [canUseAnalyst, clerkModeEnabled],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(INTERFACE_MODE_STORAGE_KEY, mode);
  }, [mode]);

  useEffect(() => {
    setModeState((prev) => {
      if (!clerkModeEnabled) return "analyst";
      if (prev === "analyst" && !canUseAnalyst) return "clerk";
      return prev;
    });
  }, [canUseAnalyst, clerkModeEnabled]);

  const value = useMemo<InterfaceModeContextValue>(
    () => ({
      isAnalyst: mode === "analyst",
      isClerk: mode === "clerk",
      mode,
      setMode,
    }),
    [mode, setMode],
  );

  return (
    <InterfaceModeContext.Provider value={value}>
      {children}
    </InterfaceModeContext.Provider>
  );
}

export function useInterfaceMode() {
  const context = useContext(InterfaceModeContext);
  if (!context) {
    throw new Error(
      "useInterfaceMode must be used within an InterfaceModeProvider",
    );
  }
  return context;
}

export function useIsClerkMode() {
  return useInterfaceMode().isClerk;
}

export function useIsAnalystMode() {
  return useInterfaceMode().isAnalyst;
}
