import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import { GuidedTour } from "./GuidedTour";
import { ALL_TOURS } from "./tours";
import type { TourDefinition } from "./types";

const STORAGE_KEY = "polisyos.runtime.onboarding";

type OnboardingState = {
  completedTours: string[];
  dismissedTours: string[];
};

function loadState(): OnboardingState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { completedTours: [], dismissedTours: [] };
    return JSON.parse(raw) as OnboardingState;
  } catch {
    return { completedTours: [], dismissedTours: [] };
  }
}

function saveState(state: OnboardingState) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

type OnboardingContextValue = {
  /** Start a specific tour by ID. */
  startTour: (tourId: string) => void;
  /** Whether a tour has been completed. */
  isTourCompleted: (tourId: string) => boolean;
  /** Whether any tour is currently active. */
  isActive: boolean;
  /** Reset all onboarding state. */
  resetAll: () => void;
};

const OnboardingContext = createContext<OnboardingContextValue | null>(null);

export function OnboardingProvider({ children }: PropsWithChildren) {
  const [state, setState] = useState(loadState);
  const [activeTour, setActiveTour] = useState<TourDefinition | null>(null);

  const startTour = useCallback(
    (tourId: string) => {
      const completed = new Set(state.completedTours);
      const dismissed = new Set(state.dismissedTours);
      if (completed.has(tourId) || dismissed.has(tourId)) return;

      const tour = ALL_TOURS.find((t) => t.id === tourId);
      if (tour) setActiveTour(tour);
    },
    [state],
  );

  const handleComplete = useCallback(() => {
    if (!activeTour) return;
    const next = {
      ...state,
      completedTours: [...state.completedTours, activeTour.id],
    };
    setState(next);
    saveState(next);
    setActiveTour(null);
  }, [activeTour, state]);

  const handleDismiss = useCallback(() => {
    if (!activeTour) return;
    const next = {
      ...state,
      dismissedTours: [...state.dismissedTours, activeTour.id],
    };
    setState(next);
    saveState(next);
    setActiveTour(null);
  }, [activeTour, state]);

  const isTourCompleted = useCallback(
    (tourId: string) => state.completedTours.includes(tourId),
    [state.completedTours],
  );

  const resetAll = useCallback(() => {
    const next = { completedTours: [], dismissedTours: [] };
    setState(next);
    saveState(next);
    setActiveTour(null);
  }, []);

  const value = useMemo<OnboardingContextValue>(
    () => ({
      isActive: activeTour !== null,
      isTourCompleted,
      resetAll,
      startTour,
    }),
    [activeTour, isTourCompleted, resetAll, startTour],
  );

  return (
    <OnboardingContext.Provider value={value}>
      {children}
      {activeTour && (
        <GuidedTour
          tour={activeTour}
          onComplete={handleComplete}
          onDismiss={handleDismiss}
        />
      )}
    </OnboardingContext.Provider>
  );
}

export function useOnboarding() {
  const ctx = useContext(OnboardingContext);
  if (!ctx) {
    throw new Error("useOnboarding must be used within OnboardingProvider");
  }
  return ctx;
}
