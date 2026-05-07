import {
  type PropsWithChildren,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { usePreferencesStore } from "@/app/state/usePreferencesStore";

import {
  TrustViewContext,
  type TrustInspectorSubject,
  type TrustViewMode,
} from "./useTrustView";

const TRUST_VIEW_STORAGE_KEY = "polisyos.runtime.trust-view";
const TRUST_VIEW_PARAM = "trust";
const TRUST_VIEW_MODES: TrustViewMode[] = ["off", "compact", "expanded"];

export function TrustViewProvider({ children }: PropsWithChildren) {
  const density = usePreferencesStore((state) => state.density);
  const [mode, setModeState] = useState<TrustViewMode>(() => readInitialMode());
  const [inspectorSubject, setInspectorSubject] =
    useState<TrustInspectorSubject | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const syncFromUrl = () => {
      setModeState(readModeFromLocation(window.location) ?? readStoredMode());
    };
    window.addEventListener("popstate", syncFromUrl);
    return () => window.removeEventListener("popstate", syncFromUrl);
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }
    document.documentElement.dataset.trustView = mode;
    document.documentElement.dataset.trustViewDensity = density;
  }, [density, mode]);

  const setMode = useCallback(
    (nextMode: TrustViewMode, options: { replaceUrl?: boolean } = {}) => {
      const normalized = normalizeTrustViewMode(nextMode);
      setModeState(normalized);
      writeStoredMode(normalized);
      if (options.replaceUrl ?? true) {
        replaceTrustViewInCurrentUrl(normalized);
      }
      if (normalized === "off") {
        setInspectorSubject(null);
      }
    },
    [],
  );

  const cycleMode = useCallback(() => {
    const index = TRUST_VIEW_MODES.indexOf(mode);
    setMode(TRUST_VIEW_MODES[(index + 1) % TRUST_VIEW_MODES.length] ?? "off");
  }, [mode, setMode]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handleShortcut = (event: KeyboardEvent) => {
      if (
        event.shiftKey &&
        (event.metaKey || event.ctrlKey) &&
        event.key.toLowerCase() === "t"
      ) {
        event.preventDefault();
        cycleMode();
      }
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [cycleMode]);

  const openInspector = useCallback((subject: TrustInspectorSubject) => {
    setInspectorSubject(subject);
  }, []);

  const closeInspector = useCallback(() => {
    setInspectorSubject(null);
  }, []);

  const value = useMemo(
    () => ({
      closeInspector,
      cycleMode,
      density,
      inspectorSubject,
      mode,
      openInspector,
      setMode,
    }),
    [
      closeInspector,
      cycleMode,
      density,
      inspectorSubject,
      mode,
      openInspector,
      setMode,
    ],
  );

  return (
    <TrustViewContext.Provider value={value}>
      {children}
    </TrustViewContext.Provider>
  );
}

export function normalizeTrustViewMode(value: unknown): TrustViewMode {
  return value === "compact" || value === "expanded" ? value : "off";
}

function readInitialMode(): TrustViewMode {
  if (typeof window === "undefined") {
    return "off";
  }
  return readModeFromLocation(window.location) ?? readStoredMode();
}

function readModeFromLocation(location: Location): TrustViewMode | null {
  const params = new URLSearchParams(location.search);
  const raw = params.get(TRUST_VIEW_PARAM);
  if (raw === null) {
    return null;
  }
  return normalizeTrustViewMode(raw);
}

function readStoredMode(): TrustViewMode {
  try {
    return normalizeTrustViewMode(
      window.localStorage.getItem(TRUST_VIEW_STORAGE_KEY),
    );
  } catch {
    return "off";
  }
}

function writeStoredMode(mode: TrustViewMode) {
  try {
    window.localStorage.setItem(TRUST_VIEW_STORAGE_KEY, mode);
  } catch {
    // Storage can be unavailable in private contexts; URL state still works.
  }
}

function replaceTrustViewInCurrentUrl(mode: TrustViewMode) {
  if (typeof window === "undefined") {
    return;
  }
  const url = new URL(window.location.href);
  if (mode === "off") {
    url.searchParams.delete(TRUST_VIEW_PARAM);
  } else {
    url.searchParams.set(TRUST_VIEW_PARAM, mode);
  }
  window.history.replaceState(window.history.state, "", url);
}
