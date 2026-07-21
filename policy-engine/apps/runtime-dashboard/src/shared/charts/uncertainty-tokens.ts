import type { IdentifiabilityState } from "./types";

export type UncertaintyPalette = "default" | "disputed";
export type UncertaintyPatternKind =
  | "none"
  | "diagonal-lines"
  | "dots"
  | "crosshatch";

export const uncertaintyTokens = {
  pointEstimate: "var(--color-uncertainty-point-estimate)",
  confidenceInterval: "var(--color-uncertainty-confidence-interval)",
  counterfactualInterval: "var(--color-uncertainty-counterfactual-interval)",
  disputed: "var(--color-uncertainty-disputed)",
  identified: {
    fill: "solid",
    pattern: "none",
  },
  estimated: {
    fill: "var(--slate)",
    pattern: "diagonal-lines",
  },
  assumed: {
    fill: "transparent",
    pattern: "dots",
  },
  unknown: {
    fill: "transparent",
    pattern: "crosshatch",
  },
} as const;

export function resolveUncertaintyPaletteColor(
  palette: UncertaintyPalette = "default",
) {
  return palette === "disputed"
    ? uncertaintyTokens.disputed
    : uncertaintyTokens.pointEstimate;
}

export function resolveUncertaintyIntervalColor(
  palette: UncertaintyPalette = "default",
) {
  return palette === "disputed"
    ? uncertaintyTokens.disputed
    : uncertaintyTokens.confidenceInterval;
}

export function resolveCounterfactualColor(
  palette: UncertaintyPalette = "default",
) {
  return palette === "disputed"
    ? uncertaintyTokens.disputed
    : uncertaintyTokens.counterfactualInterval;
}

export function resolveUncertaintyBandOpacity(level: number) {
  if (level <= 0.5) {
    return 0.26;
  }
  if (level <= 0.8) {
    return 0.18;
  }
  return 0.1;
}

export function resolveIdentifiabilityPattern(
  state: IdentifiabilityState = "unknown",
): UncertaintyPatternKind {
  if (state === "estimated") {
    return uncertaintyTokens.estimated.pattern;
  }
  if (state === "assumed") {
    return uncertaintyTokens.assumed.pattern;
  }
  if (state === "identified") {
    return uncertaintyTokens.identified.pattern;
  }
  return uncertaintyTokens.unknown.pattern;
}
