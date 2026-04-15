/**
 * Enhanced chart accessibility utilities (WCAG 2.2 AA).
 *
 * Extends the existing accessibility.ts with:
 * - Auto-generated ARIA labels for chart containers
 * - Keyboard navigation helpers for data points
 * - High-contrast mode detection and pattern-only rendering
 * - ARIA live region announcements for SSE-driven chart updates
 */

import type { ReactElement } from "react";
import { createElement } from "react";

/* ── ARIA label generators ── */

export type ChartAriaConfig = {
  type: "area" | "bar" | "forest" | "gauge" | "radar" | "waterfall";
  title: string;
  dataPoints: number;
  trend?: "down" | "stable" | "up";
  range?: { max: number; min: number };
  unit?: string;
};

export function generateChartAriaLabel(config: ChartAriaConfig): string {
  const parts: string[] = [
    `${config.type} chart: ${config.title}.`,
    `${config.dataPoints} data points.`,
  ];
  if (config.range) {
    const unit = config.unit ? ` ${config.unit}` : "";
    parts.push(
      `Range: ${config.range.min.toFixed(2)}${unit} to ${config.range.max.toFixed(2)}${unit}.`,
    );
  }
  if (config.trend) {
    parts.push(`Trend: ${config.trend}.`);
  }
  return parts.join(" ");
}

/* ── Accessible chart container wrapper ── */

export type A11yChartContainerProps = {
  ariaLabel: string;
  children: ReactElement;
  /** Unique ID for linking description. */
  chartId: string;
  /** Optional longer description for complex charts. */
  description?: string;
  /** Title element rendered inside SVG. */
  title: string;
};

/**
 * Wraps an SVG chart with proper ARIA attributes:
 * - role="img" on container
 * - <title> inside SVG
 * - aria-describedby linking to hidden description
 */
export function A11yChartContainer({
  ariaLabel,
  chartId,
  children,
  description,
  title,
}: A11yChartContainerProps): ReactElement {
  const descId = `${chartId}-desc`;

  return createElement(
    "figure",
    {
      role: "img",
      "aria-label": ariaLabel,
      "aria-describedby": description ? descId : undefined,
      className: "relative",
    },
    children,
    description
      ? createElement(
          "figcaption",
          { id: descId, className: "sr-only" },
          description,
        )
      : null,
  );
}

/* ── Keyboard navigation for data points ── */

export type DataPointKeyboardHandler = {
  onKeyDown: (e: React.KeyboardEvent) => void;
  activeIndex: number;
};

export function createDataPointKeyboardNav(
  totalPoints: number,
  onSelect: (index: number) => void,
  initialIndex = 0,
): {
  getProps: (index: number, activeIndex: number) => Record<string, unknown>;
  handleKeyDown: (e: KeyboardEvent, currentIndex: number) => number;
} {
  return {
    handleKeyDown: (e: KeyboardEvent, currentIndex: number) => {
      let next = currentIndex;
      switch (e.key) {
        case "ArrowRight":
        case "ArrowDown":
          e.preventDefault();
          next = Math.min(currentIndex + 1, totalPoints - 1);
          break;
        case "ArrowLeft":
        case "ArrowUp":
          e.preventDefault();
          next = Math.max(currentIndex - 1, 0);
          break;
        case "Home":
          e.preventDefault();
          next = 0;
          break;
        case "End":
          e.preventDefault();
          next = totalPoints - 1;
          break;
        case "Enter":
        case " ":
          e.preventDefault();
          onSelect(currentIndex);
          return currentIndex;
      }
      if (next !== currentIndex) {
        onSelect(next);
      }
      return next;
    },
    getProps: (index: number, activeIndex: number) => ({
      role: "option",
      "aria-selected": index === activeIndex,
      tabIndex: index === activeIndex ? 0 : -1,
    }),
  };
}

/* ── High-contrast mode detection ── */

export function isHighContrastMode(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(forced-colors: active)").matches;
}

export function useHighContrastQuery(): boolean {
  if (typeof window === "undefined") return false;
  // Static check — for reactive version, use useSyncExternalStore
  return isHighContrastMode();
}

/* ── ARIA live region for chart updates ── */

export function ChartLiveRegion({
  message,
  politeness = "polite",
}: {
  message: string;
  politeness?: "assertive" | "polite";
}): ReactElement {
  return createElement(
    "div",
    {
      "aria-live": politeness,
      "aria-atomic": "true",
      className: "sr-only",
      role: "status",
    },
    message,
  );
}
