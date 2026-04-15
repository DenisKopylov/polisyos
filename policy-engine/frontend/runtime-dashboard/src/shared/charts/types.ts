export type DataPoint = {
  label: string;
  value: number;
};

export type TimeSeriesDataPoint = {
  x: number | string;
  y: number;
  y0?: number;
  ci50Lower?: number;
  ci50Upper?: number;
  ci80Lower?: number;
  ci80Upper?: number;
  ci95Lower?: number;
  ci95Upper?: number;
};

export type ConfidenceInterval = {
  lower: number;
  upper: number;
  level: number;
};

export type EffectEstimate = {
  id: string;
  label: string;
  estimate: number;
  ci: ConfidenceInterval;
  weight?: number;
};

export type WaterfallStep = {
  label: string;
  value: number;
  isTotal?: boolean;
};

export type ParallelAxis = {
  key: string;
  label: string;
  domain?: [number, number];
};

export type ParallelRow = { id: string } & Record<string, number | string>;

export type SpecificationPoint = {
  id: string;
  estimate: number;
  ci: ConfidenceInterval;
  isMain?: boolean;
  controls?: string[];
};

export type RadarDimension = {
  key: string;
  label: string;
  fullMark?: number;
};

export type RadarSeries = {
  id: string;
  label: string;
  values: Record<string, number>;
};

export type ConfidenceLevel = "high" | "medium" | "low";

export function classifyConfidence(value: number): ConfidenceLevel {
  if (value >= 0.8) return "high";
  if (value >= 0.5) return "medium";
  return "low";
}

export function confidenceColor(level: ConfidenceLevel): string {
  return `var(--color-confidence-${level})`;
}
