/* ── Types ── */
export type {
  DataPoint,
  TimeSeriesDataPoint,
  ConfidenceInterval,
  EffectEstimate,
  WaterfallStep,
  ParallelAxis,
  ParallelRow,
  SpecificationPoint,
  RadarDimension,
  RadarSeries,
  ConfidenceLevel,
} from "./types";
export { classifyConfidence, confidenceColor } from "./types";

/* ── Theme ── */
export {
  chartTheme,
  ciColors,
  confidenceColors,
  waterfallColors,
  categoricalPalette,
  chartDefaults,
} from "./theme";

/* ── Accessibility ── */
export {
  PATTERN_IDS,
  ChartPatternDefs,
  patternFill,
  describeTimeSeries,
  describeBarChart,
  describeConfidenceInterval,
  describeForestPlot,
  ChartDataTable,
} from "./accessibility";

/* ── Standard charts ── */
export { AreaChart } from "./AreaChart";
export { BarChart } from "./BarChart";
export { WaterfallChart } from "./WaterfallChart";
export { RadarChart } from "./RadarChart";

/* ── Analytical charts ── */
export { SpecificationCurveChart } from "./SpecificationCurveChart";
export { ForestPlot } from "./ForestPlot";
export { ParallelCoordinatesChart } from "./ParallelCoordinatesChart";

/* ── Method-specific causal visualizations ── */
export { DiDVisualization } from "./DiDVisualization";
export type { DiDGroup } from "./DiDVisualization";
export { SyntheticControlViz } from "./SyntheticControlViz";
export type { SCTimePoint } from "./SyntheticControlViz";
export { RDDVisualization } from "./RDDVisualization";
export type { RDDDataPoint } from "./RDDVisualization";
export { BSTSVisualization } from "./BSTSVisualization";
export type { BSTSTimePoint } from "./BSTSVisualization";
export { MetaLearnerViz } from "./MetaLearnerViz";
export type { CATEEstimate, CATEDistributionBin } from "./MetaLearnerViz";

/* ── Confidence & uncertainty ── */
export { ConfidenceGauge } from "./ConfidenceGauge";
export { GradedErrorBar } from "./GradedErrorBar";
export { UncertaintyDisplay } from "./UncertaintyDisplay";
export { FrequencyDots } from "./FrequencyDots";
export { ConfidenceDial } from "./ConfidenceDial";

/* ── Annotated ── */
export { AnnotatedChart } from "./AnnotatedChart";
export type { ChartAnnotation } from "./AnnotatedChart";

/* ── Animated primitives ── */
export { AnimatedNumber } from "./AnimatedNumber";
export { AnimatedProgress } from "./AnimatedProgress";
