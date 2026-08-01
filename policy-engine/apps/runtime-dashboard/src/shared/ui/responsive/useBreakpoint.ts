import { useSyncExternalStore } from "react";
import { breakpointProjection } from "@polisyos/atlas-ui";

/**
 * 5-tier breakpoint system aligned with USWDS mobile-first strategy.
 *
 * | Tier   | Range          | Layout                           |
 * |--------|----------------|----------------------------------|
 * | mobile | < 640px        | Bottom nav, single column        |
 * | tablet | 640–767px      | Single column wide, drawer       |
 * | compact| 768–1023px     | Compact grid, narrow sidebar     |
 * | standard| 1024–1280px   | Full sidebar, 3-column grid      |
 * | expanded| > 1280px      | Full layout + extra panel space  |
 */
export type Breakpoint =
  | "mobile"
  | "tablet"
  | "compact"
  | "standard"
  | "expanded";

function getBreakpoint(): Breakpoint {
  if (typeof window === "undefined") return "standard";
  const width = window.innerWidth;
  const { compactMin, expandedMin, mobileMax, standardMin, tabletMin } =
    breakpointProjection.runtime;
  if (width >= expandedMin) return "expanded";
  if (width >= standardMin) return "standard";
  if (width >= compactMin) return "compact";
  if (width >= tabletMin) return "tablet";
  if (width <= mobileMax) return "mobile";
  return "mobile";
}

function subscribe(callback: () => void) {
  const { compactMin, expandedMin, mobileMax, standardMin } =
    breakpointProjection.runtime;
  const mediaQueries = [
    window.matchMedia(`(max-width: ${mobileMax}px)`),
    window.matchMedia(`(max-width: ${compactMin - 1}px)`),
    window.matchMedia(`(max-width: ${standardMin - 1}px)`),
    window.matchMedia(`(max-width: ${expandedMin - 1}px)`),
  ];

  const handler = () => callback();
  for (const mediaQuery of mediaQueries) {
    mediaQuery.addEventListener("change", handler);
  }

  return () => {
    for (const mediaQuery of mediaQueries) {
      mediaQuery.removeEventListener("change", handler);
    }
  };
}

const getServerSnapshot = () => "standard" as Breakpoint;

export function useBreakpoint(): Breakpoint {
  return useSyncExternalStore(subscribe, getBreakpoint, getServerSnapshot);
}

export function useIsMobile(): boolean {
  const bp = useBreakpoint();
  return bp === "mobile";
}
