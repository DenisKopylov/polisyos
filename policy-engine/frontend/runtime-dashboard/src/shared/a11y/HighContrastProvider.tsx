import {
  createContext,
  type PropsWithChildren,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { trackHighContrastEnabled } from "@/shared/telemetry/extendedEvents";

export type ContrastPreference = "more" | "no-preference";

type HighContrastContextValue = {
  forcedColorsActive: boolean;
  isHighContrast: boolean;
  preference: ContrastPreference;
};

const HighContrastContext = createContext<HighContrastContextValue | null>(
  null,
);

function subscribeToMediaQuery(
  mediaQuery: MediaQueryList,
  listener: () => void,
) {
  mediaQuery.addEventListener("change", listener);
  return () => mediaQuery.removeEventListener("change", listener);
}

function readHighContrastState() {
  if (typeof window === "undefined") {
    return {
      forcedColorsActive: false,
      isHighContrast: false,
      preference: "no-preference" as const,
    };
  }

  const prefersMore = window.matchMedia("(prefers-contrast: more)").matches;
  const forcedColorsActive = window.matchMedia(
    "(forced-colors: active)",
  ).matches;
  const isHighContrast = prefersMore || forcedColorsActive;

  return {
    forcedColorsActive,
    isHighContrast,
    preference: isHighContrast ? ("more" as const) : ("no-preference" as const),
  };
}

export function HighContrastProvider({ children }: PropsWithChildren) {
  const [state, setState] = useState(readHighContrastState);
  const previousHighContrastRef = useRef(state.isHighContrast);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const prefersContrastQuery = window.matchMedia("(prefers-contrast: more)");
    const forcedColorsQuery = window.matchMedia("(forced-colors: active)");
    const sync = () => setState(readHighContrastState());

    sync();

    const unsubscribePrefersContrast = subscribeToMediaQuery(
      prefersContrastQuery,
      sync,
    );
    const unsubscribeForcedColors = subscribeToMediaQuery(
      forcedColorsQuery,
      sync,
    );

    return () => {
      unsubscribePrefersContrast();
      unsubscribeForcedColors();
    };
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.contrast = state.preference;
    root.dataset.forcedColors = state.forcedColorsActive ? "active" : "none";
  }, [state.forcedColorsActive, state.preference]);

  useEffect(() => {
    if (state.isHighContrast && !previousHighContrastRef.current) {
      trackHighContrastEnabled();
    }
    previousHighContrastRef.current = state.isHighContrast;
  }, [state.isHighContrast]);

  const value = useMemo<HighContrastContextValue>(
    () => ({
      forcedColorsActive: state.forcedColorsActive,
      isHighContrast: state.isHighContrast,
      preference: state.preference,
    }),
    [state.forcedColorsActive, state.isHighContrast, state.preference],
  );

  return (
    <HighContrastContext.Provider value={value}>
      {children}
    </HighContrastContext.Provider>
  );
}

export function useHighContrast() {
  const context = useContext(HighContrastContext);
  if (!context) {
    throw new Error("useHighContrast must be used within HighContrastProvider");
  }
  return context;
}
