import type {
  CompareCandidatesPayload,
  CompareRunsPayload,
} from "@/api/validators";
import type { QuantityValue } from "@/shared/ui/quantity/quantity.types";

export type PolicyDiffPayload = CompareRunsPayload;
export type ComparisonFrame = CompareRunsPayload["comparison_frame"];
export type ComparabilityReport = CompareRunsPayload["comparability"];
export type CompareRunsDelta = NonNullable<
  CompareRunsPayload["deltas"]
>[number];
export type DeltaQuantity = Omit<
  CompareRunsDelta,
  "a" | "b" | "delta_absolute" | "delta_relative"
> & {
  a?: QuantityValue | null;
  b?: QuantityValue | null;
  delta_absolute?: QuantityValue | null;
  delta_relative?: QuantityValue | null;
};
export type CompareCandidate = NonNullable<
  CompareCandidatesPayload["candidates"]
>[number];

export type DeltaSignificance = DeltaQuantity["significance"];
export type ComparabilityStatus = ComparabilityReport["status"];
