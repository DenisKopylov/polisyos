import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { useAuthzDecision } from "@/app/authz/AuthzProvider";
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
  const authzDecision = useAuthzDecision();
  const canUseAnalyst =
    authzDecision.kind === "verified" && authzDecision.can("mode.analyst");

  const [preferredMode, setPreferredMode] =
    useState<InterfaceMode | null>(readStoredMode);
  const mode: InterfaceMode = !clerkModeEnabled
    ? "analyst"
    : preferredMode === "clerk"
      ? "clerk"
      : canUseAnalyst
        ? "analyst"
        : "clerk";

  const setMode = useCallback(
    (nextMode: InterfaceMode) => {
      if (!clerkModeEnabled) return;
      if (nextMode === "analyst" && !canUseAnalyst) return;
      setPreferredMode(nextMode);
    },
    [canUseAnalyst, clerkModeEnabled],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (preferredMode) {
      window.localStorage.setItem(INTERFACE_MODE_STORAGE_KEY, preferredMode);
    }
  }, [preferredMode]);

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
