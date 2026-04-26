import type {
  CompareCandidatesPayload,
  CompareRunsPayload,
} from "@/api/validators";

export type PolicyDiffPayload = CompareRunsPayload;
export type ComparisonFrame = CompareRunsPayload["comparison_frame"];
export type ComparabilityReport = CompareRunsPayload["comparability"];
export type DeltaQuantity = NonNullable<CompareRunsPayload["deltas"]>[number];
export type CompareCandidate = NonNullable<
  CompareCandidatesPayload["candidates"]
>[number];

export type DeltaSignificance = DeltaQuantity["significance"];
export type ComparabilityStatus = ComparabilityReport["status"];
