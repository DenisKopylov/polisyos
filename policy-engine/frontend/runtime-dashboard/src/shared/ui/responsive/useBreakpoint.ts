import { useSyncExternalStore } from "react";

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

const BREAKPOINTS: [Breakpoint, number][] = [
  ["expanded", 1281],
  ["standard", 1024],
  ["compact", 768],
  ["tablet", 640],
  ["mobile", 0],
];

function getBreakpoint(): Breakpoint {
  if (typeof window === "undefined") return "standard";
  const width = window.innerWidth;
  for (const [name, min] of BREAKPOINTS) {
    if (width >= min) return name;
  }
  return "mobile";
}

function subscribe(callback: () => void) {
  const mql = window.matchMedia("(max-width: 639px)");
  const mql2 = window.matchMedia("(max-width: 767px)");
  const mql3 = window.matchMedia("(max-width: 1023px)");
  const mql4 = window.matchMedia("(max-width: 1280px)");

  const handler = () => callback();
  mql.addEventListener("change", handler);
  mql2.addEventListener("change", handler);
  mql3.addEventListener("change", handler);
  mql4.addEventListener("change", handler);

  return () => {
    mql.removeEventListener("change", handler);
    mql2.removeEventListener("change", handler);
    mql3.removeEventListener("change", handler);
    mql4.removeEventListener("change", handler);
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
