import type { RunFabricDecisionDataPayload } from "@/api/validators";

import type {
  LineageFreshness,
  QuantityClass,
  QuantityUncertainty,
  QuantityValue,
  TemporalRef,
  UnitRef,
  VerificationStatus,
} from "./quantity.types";

type FabricDecisionDataRow = NonNullable<
  RunFabricDecisionDataPayload["decision_data"]
>[number];

const DEFAULT_UNIT: UnitRef = { code: "1", system: "ucum", display: "value" };
const QUANTITY_CLASSES: QuantityClass[] = [
  "decision",
  "telemetry",
  "layout",
  "debug",
];
const LINEAGE_FRESHNESS: LineageFreshness[] = ["current", "stale", "unknown"];
const VERIFICATION_STATUSES: VerificationStatus[] = [
  "verified",
  "pending",
  "disputed",
  "untraced",
];

export function fabricDecisionDataToQuantityValue(
  row: FabricDecisionDataRow,
): QuantityValue | null {
  if (row.kind !== "quantity") {
    return null;
  }
  const value = row.value;
  const metricId =
    stringValue(value.metric_id) ??
    stringValue(row.metadata?.runtime_metric_id) ??
    stringValue(value.semantic_type) ??
    row.id;
  const label = stringValue(value.label) ?? metricId;
  const lineageStatus = verificationStatus(row.lineage.status);
  const freshness = fabricFreshness(row);
  const temporalScope = temporalRef(row.time);
  return {
    point: finitePoint(value.point),
    unit: unitRef(value.unit),
    metric_id: metricId,
    lineage: {
      id: row.lineage.id,
      status: lineageStatus,
      freshness,
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
      trust_metadata: {
        dispute_status: lineageStatus === "disputed" ? "disputed" : "none",
        freshness,
        hash: stringValue(row.lineage.hash),
        temporal_scope: temporalScope,
        verification_method: "fabric_trust_envelope",
        verification_status: lineageStatus,
        verified_by:
          stringValue(row.lineage.owner) ??
          stringValue(row.metadata?.owner) ??
          row.source_contract.id,
      },
    },
    uncertainty: uncertaintyRef(value.uncertainty),
    time: temporalScope,
    quantity_class: quantityClass(row.metadata?.quantity_class),
    label,
  };
}

export function fabricDecisionDataPayloadToQuantities(
  payload: RunFabricDecisionDataPayload,
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

function uncertaintyRef(value: unknown): QuantityUncertainty | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    ci_80: tupleNumber(value.ci_80),
    ci_95: tupleNumber(value.ci_95),
    disputed: value.disputed === true,
    identifiability:
      value.identifiability === "identified" ||
      value.identifiability === "estimated" ||
      value.identifiability === "assumed" ||
      value.identifiability === "unknown"
        ? value.identifiability
        : undefined,
    method: stringValue(value.method),
  };
}

function tupleNumber(value: unknown): [number, number] | null {
  if (!Array.isArray(value) || value.length !== 2) {
    return null;
  }
  const lower = finitePoint(value[0]);
  const upper = finitePoint(value[1]);
  return lower === null || upper === null ? null : [lower, upper];
}

function fabricFreshness(row: FabricDecisionDataRow): LineageFreshness {
  const metadataFreshness = stringValue(row.metadata?.freshness);
  if (
    metadataFreshness &&
    LINEAGE_FRESHNESS.includes(metadataFreshness as LineageFreshness)
  ) {
    return metadataFreshness as LineageFreshness;
  }
  if (row.gaps?.some((gap) => gap.reason_code === "stale_evidence")) {
    return "stale";
  }
  return row.lineage.status === "verified" ? "current" : "unknown";
}

function firstReasonCode(row: FabricDecisionDataRow): string | null {
  return (
    stringValue(row.lineage.reason_code) ??
    stringValue(row.quality.reason_code) ??
    stringValue(row.replay.reason_code) ??
    stringValue(row.gaps?.find((gap) => gap.reason_code)?.reason_code)
  );
}

function qualitySummary(row: FabricDecisionDataRow): string {
  const score =
    typeof row.quality.score === "number"
      ? row.quality.score.toFixed(3)
      : "n/a";
  return `${row.quality.status}:${score}`;
}

function quantityClass(value: unknown): QuantityClass {
  return QUANTITY_CLASSES.includes(value as QuantityClass)
    ? (value as QuantityClass)
    : "decision";
}

function verificationStatus(value: unknown): VerificationStatus {
  return VERIFICATION_STATUSES.includes(value as VerificationStatus)
    ? (value as VerificationStatus)
    : "pending";
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
