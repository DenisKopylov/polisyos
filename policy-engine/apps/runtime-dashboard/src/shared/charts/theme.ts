import { chartTheme } from "@/shared/ui/chartTheme";

export { chartTheme };

export const ciColors = {
  ci50: "var(--color-ci-50)",
  ci80: "var(--color-ci-80)",
  ci95: "var(--color-ci-95)",
  boundsFill: "var(--color-bounds-fill)",
  boundsStroke: "var(--color-bounds-stroke)",
} as const;

export const waterfallColors = {
  positive: "var(--color-waterfall-positive)",
  negative: "var(--color-waterfall-negative)",
  total: "var(--color-waterfall-total)",
} as const;

export const categoricalPalette = [
  chartTheme.primary,
  chartTheme.secondary,
  chartTheme.success,
  chartTheme.warning,
  chartTheme.alert,
  chartTheme.tertiary,
  chartTheme.neutral,
] as const;

export const chartDefaults = {
  fontFamily: "var(--font-sans)",
  fontSize: 12,
  tickFontSize: 11,
  labelFontSize: 13,
  strokeWidth: 2,
  dotRadius: 3,
  margin: { top: 12, right: 16, bottom: 8, left: 4 } as const,
} as const;
