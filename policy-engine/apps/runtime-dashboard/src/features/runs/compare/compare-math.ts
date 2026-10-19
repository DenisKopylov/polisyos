import type {
  ComparabilityStatus,
  CompareRunsDelta,
  DeltaSignificance,
} from "./compare-types";

type SalienceInput = Pick<CompareRunsDelta, "decision_salience">;
type DistributionInput = {
  delta_distribution?: Pick<
    NonNullable<CompareRunsDelta["delta_distribution"]>,
    "mean_shift" | "median_shift" | "quantiles"
  >;
};

export function formatSignedNumber(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${value >= 0 ? "+" : ""}${value.toFixed(Math.abs(value) < 1 ? 3 : 2)}`;
}

export function saliencePercent(delta: SalienceInput) {
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

export function topDeltas<T extends SalienceInput>(
  deltas: readonly T[],
  limit = 6,
): T[] {
  return [...deltas]
    .sort((left, right) => right.decision_salience - left.decision_salience)
    .slice(0, limit);
}

export function hasDistribution(delta: DistributionInput) {
  const distribution = delta.delta_distribution;
  return Boolean(
    distribution?.mean_shift !== null ||
    distribution?.median_shift !== null ||
    Object.keys(distribution?.quantiles ?? {}).length > 0,
  );
}
