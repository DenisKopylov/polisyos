import type {
  FabricDecisionData,
  FabricDecisionDataResponse,
  QuantityValue,
  TemporalRef,
  UnitRef,
} from "./quantity.types";

const DEFAULT_UNIT: UnitRef = { code: "1", system: "ucum", display: "value" };

export function fabricDecisionDataToQuantityValue(
  row: FabricDecisionData,
): QuantityValue | null {
  if (row.kind !== "quantity") {
    return null;
  }
  const value = recordValue(row.value);
  const metricId =
    stringValue(value.metric_id) ??
    stringValue(row.metadata?.runtime_metric_id) ??
    stringValue(value.semantic_type) ??
    row.id;
  const label = stringValue(value.label) ?? metricId;
  const lineageStatus = row.lineage.status;
  const temporalScope = temporalRef(row.time);
  return {
    point: finitePoint(value.point),
    unit: unitRef(value.unit),
    metric_id: metricId,
    lineage: {
      id: row.lineage.id,
      status: lineageStatus,
      freshness: "unknown",
      hash: stringValue(row.lineage.hash),
      reason_code: firstReasonCode(row),
      tracking_issue: stringValue(row.lineage.tracking_issue),
      summary: {
        access: `${row.access.classification}/${row.access.redaction}`,
        quality: qualitySummary(row),
        replay: row.replay.status,
        source_contract: `${row.source_contract.id}@${row.source_contract.version}`,
      },
      compact_summary: [
        {
          kind: "source",
          id: row.source_contract.id,
          label: row.source_contract.id,
        },
        {
          kind: "result",
          id: metricId,
          label,
        },
      ],
    },
    uncertainty: null,
    time: temporalScope,
    quantity_class: "decision",
    label,
  };
}

export function fabricDecisionDataPayloadToQuantities(
  payload: FabricDecisionDataResponse,
): QuantityValue[] {
  return (payload.decision_data ?? []).flatMap((row) => {
    const quantity = fabricDecisionDataToQuantityValue(row);
    return quantity ? [quantity] : [];
  });
}

function finitePoint(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function unitRef(value: unknown): UnitRef {
  if (!isRecord(value)) {
    return DEFAULT_UNIT;
  }
  return {
    code: stringValue(value.code) ?? DEFAULT_UNIT.code,
    system: stringValue(value.system) ?? DEFAULT_UNIT.system,
    display: stringValue(value.display) ?? DEFAULT_UNIT.display,
  };
}

function temporalRef(value: unknown): TemporalRef | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    branch: stringValue(value.branch),
    scenario_id: stringValue(value.scenario_id),
    snapshot_id: stringValue(value.snapshot_id),
    tx_at: stringValue(value.tx_at),
    valid_at: stringValue(value.valid_at),
  };
}

function firstReasonCode(row: FabricDecisionData): string | null {
  return (
    stringValue(row.lineage.reason_code) ??
    stringValue(row.quality.reason_code) ??
    stringValue(row.replay.reason_code) ??
    stringValue(row.gaps?.find((gap) => gap.reason_code)?.reason_code)
  );
}

function qualitySummary(row: FabricDecisionData): string {
  const score =
    typeof row.quality.score === "number"
      ? row.quality.score.toFixed(3)
      : "n/a";
  return `${row.quality.status}:${score}`;
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function recordValue(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}
