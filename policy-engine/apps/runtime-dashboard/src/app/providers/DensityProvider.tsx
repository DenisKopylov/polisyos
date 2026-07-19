import {
  createContext,
  startTransition,
  useContext,
  useEffect,
  useMemo,
  type PropsWithChildren,
} from "react";
import { densityModeDescriptors } from "@polisyos/atlas-ui";

import {
  usePreferencesStore,
  type Density,
} from "../state/usePreferencesStore";
import { trackDensityChange } from "@/shared/telemetry/extendedEvents";

export const SUPPORTED_DENSITIES = [
  densityModeDescriptors.comfortable.attribute,
  densityModeDescriptors.compact.attribute,
  densityModeDescriptors.condensed.attribute,
] as const satisfies readonly Density[];

const DENSITY_ATTR = "data-density";

type DensityContextValue = {
  cycleDensity: () => void;
  density: Density;
  setDensity: (density: Density) => void;
};

const DensityContext = createContext<DensityContextValue | null>(null);

function nextDensity(current: Density): Density {
  const currentIndex = SUPPORTED_DENSITIES.indexOf(current);
  return SUPPORTED_DENSITIES[(currentIndex + 1) % SUPPORTED_DENSITIES.length];
}

export function DensityProvider({ children }: PropsWithChildren) {
  const density = usePreferencesStore((state) => state.density);
  const setDensityState = usePreferencesStore((state) => state.setDensity);

  useEffect(() => {
    document.documentElement.setAttribute(
      DENSITY_ATTR,
      densityModeDescriptors[density].attribute,
    );
    trackDensityChange(density);
  }, [density]);

  const value = useMemo<DensityContextValue>(
    () => ({
      cycleDensity: () =>
        startTransition(() => {
          setDensityState(nextDensity(density));
        }),
      density,
      setDensity: (nextDensityValue) =>
        startTransition(() => {
          setDensityState(nextDensityValue);
        }),
    }),
    [density, setDensityState],
  );

  return (
    <DensityContext.Provider value={value}>{children}</DensityContext.Provider>
  );
}

export function useDensity() {
  const context = useContext(DensityContext);
  if (!context) {
    throw new Error("useDensity must be used within DensityProvider");
  }
  return context;
}
