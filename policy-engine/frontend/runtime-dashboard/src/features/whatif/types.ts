// ---------------------------------------------------------------------------
// What-If Analysis domain types
// ---------------------------------------------------------------------------

/** Parameter specification (mirrors backend PolicySpec.ParameterSpec). */
export type ParameterSpec = {
  key: string;
  label: string;
  description?: string;
  min: number;
  max: number;
  step?: number;
  defaultValue: number;
  unit?: string;
  /** 0 = low sensitivity, 1 = high sensitivity. */
  sensitivityPriority: number;
  /** Sensitivity zone boundaries where outcome changes rapidly. */
  sensitivityZones?: { start: number; end: number }[];
};

/** Impact on a single outcome metric from a parameter change. */
export type ImpactMetric = {
  key: string;
  label: string;
  baseValue: number;
  projectedValue: number;
  unit?: string;
  higherIsBetter?: boolean;
  ci?: { lower: number; upper: number };
};

/** A saved scenario (parameter snapshot + optional computed metrics). */
export type Scenario = {
  id: string;
  name: string;
  baseRunId: string;
  parameters: Record<string, number>;
  metrics?: ImpactMetric[];
  createdAt: number;
};
