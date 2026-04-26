import type {
  QuantityUncertainty,
  QuantityValue,
  TemporalRef,
  UnitRef,
} from "./quantity.types";

type UntracedQuantityInput = {
  point: number | null | undefined;
  metricId: string;
  label?: string | null;
  unit?: UnitRef;
  uncertainty?: QuantityUncertainty | null;
  time?: TemporalRef | null;
  reasonCode?: string;
  trackingIssue?: string;
};

const DEFAULT_UNTRACED_REASON = "legacy_ui_quantity_without_lineage";
const DEFAULT_TRACKING_ISSUE = "POLICYOS-QUANTITY-MIGRATION";

export function untracedDecisionQuantity({
  point,
  metricId,
  label,
  unit = { code: "1", system: "ucum", display: "value" },
  uncertainty = null,
  time = null,
  reasonCode = DEFAULT_UNTRACED_REASON,
  trackingIssue = DEFAULT_TRACKING_ISSUE,
}: UntracedQuantityInput): QuantityValue {
  return {
    point: typeof point === "number" && Number.isFinite(point) ? point : null,
    unit,
    metric_id: metricId,
    lineage: {
      id: "untraced",
      status: "untraced",
      freshness: "unknown",
      reason_code: reasonCode,
      tracking_issue: trackingIssue,
      compact_summary: [
        {
          kind: "result",
          label: label ?? metricId,
        },
      ],
    },
    uncertainty,
    time,
    quantity_class: "decision",
    label: label ?? metricId,
  };
}
