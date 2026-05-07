import type {
  ComparabilityStatus,
  DeltaQuantity,
  DeltaSignificance,
} from "./compare-types";

export function formatSignedNumber(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${value >= 0 ? "+" : ""}${value.toFixed(Math.abs(value) < 1 ? 3 : 2)}`;
}

export function saliencePercent(delta: DeltaQuantity) {
  return Math.round(
    Math.max(0, Math.min(delta.decision_salience ?? 0, 1)) * 100,
  );
}

export function significanceLabel(value: DeltaSignificance) {
  return value.replace(/_/g, " ");
}

export function comparabilityLabel(value: ComparabilityStatus) {
  if (value === "compatible") {
    return "Comparable";
  }
  if (value === "warning") {
    return "Comparable with warnings";
  }
  return "Blocked";
}

export function comparabilityTone(value: ComparabilityStatus) {
  if (value === "compatible") {
    return "ok" as const;
  }
  if (value === "warning") {
    return "warn" as const;
  }
  return "fail" as const;
}

export function significanceTone(value: DeltaSignificance) {
  if (value === "improved") {
    return "ok" as const;
  }
  if (value === "worsened") {
    return "fail" as const;
  }
  if (value === "uncertain" || value === "mixed") {
    return "warn" as const;
  }
  return "neutral" as const;
}

export function topDeltas(deltas: readonly DeltaQuantity[], limit = 6) {
  return [...deltas]
    .sort((left, right) => right.decision_salience - left.decision_salience)
    .slice(0, limit);
}

export function hasDistribution(delta: DeltaQuantity) {
  const distribution = delta.delta_distribution;
  return Boolean(
    distribution?.mean_shift !== null ||
    distribution?.median_shift !== null ||
    Object.keys(distribution?.quantiles ?? {}).length > 0,
  );
}
