import type { QuantityUncertainty } from "@polisyos/runtime-api-client";

export type DataPoint = {
  label: string;
  value: number;
};

export type UncertaintyQuantiles = {
  p10?: number;
  p25?: number;
  p50?: number;
  p75?: number;
  p90?: number;
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

export type SeriesPoint = TimeSeriesDataPoint;

export type ConfidenceInterval = {
  lower: number;
  upper: number;
  level: number;
};

export type QuantileSeriesPoint = {
  x: number | string;
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
};

export type QuantileSeries = QuantileSeriesPoint;

export type DisputeSummary = {
  who: string;
  why: string;
  asOf?: string;
  source?: string;
};

export type SampleRealizationPoint = {
  x: number | string;
  y: number;
};

export type SampleRealization = {
  id: string;
  label?: string;
  points: SampleRealizationPoint[];
};

export type EffectEstimate = {
  id: string;
  label: string;
  estimate: number;
  ci: ConfidenceInterval;
  weight?: number;
  identifiability?: IdentifiabilityState;
  disputed?: boolean;
  disputes?: DisputeSummary[];
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

export type IdentifiabilityState = QuantityUncertainty["identifiability"];
