import { useEffect, type PropsWithChildren } from "react";

import { usePreferencesStore, type Density } from "../state/usePreferencesStore";

const DENSITY_ATTR = "data-density";

const densityTokens: Record<Density, Record<string, string>> = {
  compact: {
    "--density-space": "4px",
    "--density-text": "0.8125rem",
    "--density-row-height": "32px",
    "--density-cell-py": "4px",
    "--density-cell-px": "8px",
  },
  comfortable: {
    "--density-space": "8px",
    "--density-text": "0.875rem",
    "--density-row-height": "40px",
    "--density-cell-py": "8px",
    "--density-cell-px": "12px",
  },
  spacious: {
    "--density-space": "12px",
    "--density-text": "0.9375rem",
    "--density-row-height": "48px",
    "--density-cell-py": "12px",
    "--density-cell-px": "16px",
  },
};

export function DensityProvider({ children }: PropsWithChildren) {
  const density = usePreferencesStore((s) => s.density);

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute(DENSITY_ATTR, density);

    const tokens = densityTokens[density];
    for (const [prop, value] of Object.entries(tokens)) {
      root.style.setProperty(prop, value);
    }
    // No cleanup — density tokens are global and overwritten on change.
    // Removing them on unmount causes a FOUC in React StrictMode double-mount.
  }, [density]);

  return <>{children}</>;
}
