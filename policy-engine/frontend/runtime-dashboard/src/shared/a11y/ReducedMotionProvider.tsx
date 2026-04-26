import {
  createContext,
  type PropsWithChildren,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { MotionConfig } from "motion/react";

import { trackReducedMotionActive } from "@/shared/telemetry/extendedEvents";

export type ReducedMotionPreference = "reduce" | "no-preference";

type ReducedMotionContextValue = {
  prefersReducedMotion: boolean;
  preference: ReducedMotionPreference;
  shouldAnimate: boolean;
};

const ReducedMotionContext = createContext<ReducedMotionContextValue | null>(
  null,
);

function subscribeToMediaQuery(
  mediaQuery: MediaQueryList,
  listener: () => void,
) {
  mediaQuery.addEventListener("change", listener);
  return () => mediaQuery.removeEventListener("change", listener);
}

function readReducedMotionState() {
  if (typeof window === "undefined") {
    return {
      preference: "no-preference" as const,
      prefersReducedMotion: false,
      shouldAnimate: true,
    };
  }

  const prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches;

  return {
    preference: prefersReducedMotion
      ? ("reduce" as const)
      : ("no-preference" as const),
    prefersReducedMotion,
    shouldAnimate: !prefersReducedMotion,
  };
}

export function ReducedMotionProvider({ children }: PropsWithChildren) {
  const [state, setState] = useState(readReducedMotionState);
  const previousReducedMotionRef = useRef(state.prefersReducedMotion);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setState(readReducedMotionState());

    sync();

    return subscribeToMediaQuery(mediaQuery, sync);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.reducedMotion = state.preference;
  }, [state.preference]);

  useEffect(() => {
    if (state.prefersReducedMotion && !previousReducedMotionRef.current) {
      trackReducedMotionActive();
    }
    previousReducedMotionRef.current = state.prefersReducedMotion;
  }, [state.prefersReducedMotion]);

  const value = useMemo<ReducedMotionContextValue>(
    () => ({
      preference: state.preference,
      prefersReducedMotion: state.prefersReducedMotion,
      shouldAnimate: state.shouldAnimate,
    }),
    [state.preference, state.prefersReducedMotion, state.shouldAnimate],
  );

  return (
    <ReducedMotionContext.Provider value={value}>
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
    </ReducedMotionContext.Provider>
  );
}

export function useReducedMotionPreference() {
  const context = useContext(ReducedMotionContext);
  if (!context) {
    throw new Error(
      "useReducedMotionPreference must be used within ReducedMotionProvider",
    );
  }
  return context;
}

export function useMaybeReducedMotionPreference() {
  return useContext(ReducedMotionContext) ?? readReducedMotionState();
}
