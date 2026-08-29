import type {
  AcquisitionBacklogProjection,
  AcquisitionGrowthPayload,
  AcquisitionRouteProjection,
  StructuralRouteProjection,
} from "@polisyos/runtime-api-client";

export type AcquisitionGrowthPacket = Readonly<{
  absence_reason?: null;
  as_of: string;
  authoritative_for: readonly string[];
  availability: "available";
  export_replay_contract: "policyos.runtime.export_replay_binding.v1";
  freshness: Readonly<{
    basis: "source_timestamp" | "filesystem_mtime" | "request_observation";
    observed_at: string;
    source_as_of?: string | null;
    state: "observed";
  }>;
  intended_audience: "REVIEWER" | "EXPERT" | "MACHINE";
  may_not_use_for: readonly string[];
  packet_schema_version: "policyos.runtime.governed_projection_packet.v1";
  payload: AcquisitionGrowthPayload;
  projection_hash: string;
  projection_id: "acquisition-growth";
  projection_rule_version: "policyos.runtime.governed_projection.v1";
  replay_address: string;
  source: Readonly<{
    artifact_content_hash: string;
    declared_content_hash?: string | null;
    related_artifact_bindings: readonly Readonly<{
      binding_name: string;
      owner_semantic_hash: string;
      relation: "semantic_projection";
      relative_path: string;
      resolved_artifact_content_hash: string;
      semantic_hash_rule_version: string;
    }>[];
    relative_path: string;
    validation: Readonly<{
      bound_artifact_content_hash: string;
      bound_dependency_aggregate_identity: string;
      bound_dependency_count: number;
      issue_codes: readonly string[];
      semantic_projection_hash?: string | null;
      semantic_projection_hash_rule_version?: string | null;
      status: "passed" | "failed" | "not_run";
      validator_id: string;
      validator_version: string;
    }>;
  }>;
  source_dependency_hash: string;
  source_rule_version?: string | null;
  source_schema_version?: string | null;
  stable_address: string;
}>;

export type AcquisitionBacklogOrder =
  | "server_rank"
  | "route_demand"
  | "variable_id";

export type VisibleBacklogRow = Readonly<
  AcquisitionBacklogProjection & { serverRank: number }
>;

export type VisibleAcquisitionBacklog = Readonly<{
  demandOneCount: number;
  demandTwoCount: number;
  hasNonzeroPriorityGradient: boolean;
  localOrderOverride: boolean;
  order: AcquisitionBacklogOrder;
  rows: readonly VisibleBacklogRow[];
  totalCount: number;
  voiEstablished: false;
  zeroConfidenceCount: number;
  zeroScoreCount: number;
}>;

export type VisibleConnectorAcquisitionScorecard = Readonly<{
  carrierDisposition: string;
  connectorId: string;
  executionTier: string;
  health: "degraded" | "observed_healthy" | "not_established";
  raw: Readonly<Record<string, unknown>>;
  tierDecayFindings: readonly string[];
}>;

export type VisibleAcquisitionGrowth = Readonly<{
  backlog: VisibleAcquisitionBacklog;
  connector: VisibleConnectorAcquisitionScorecard;
  history: AcquisitionGrowthPayload["n13b_history"];
  packet: AcquisitionGrowthPacket;
  structuralRoutes: readonly StructuralRouteProjection[];
  summary: AcquisitionGrowthPayload["summary"];
}>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function recordText(record: Readonly<Record<string, unknown>>, key: string) {
  const value = record[key];
  return typeof value === "string" && value.length > 0
    ? value
    : "not_established";
}

function recordStrings(
  record: Readonly<Record<string, unknown>>,
  key: string,
): readonly string[] {
  const value = record[key];
  return Array.isArray(value) &&
    value.every((member) => typeof member === "string")
    ? value
    : [];
}

export function presentConnectorAcquisitionScorecard(
  carrierLiveness: AcquisitionGrowthPayload["carrier_liveness"],
): VisibleConnectorAcquisitionScorecard {
  const raw = isRecord(carrierLiveness) ? carrierLiveness : {};
  const carrierDisposition = recordText(raw, "carrier_disposition");
  const connectorId = recordText(raw, "connector_id");
  const executionTier = recordText(raw, "execution_tier");
  const tierDecayFindings = recordStrings(raw, "tier_decay_findings");
  const health =
    connectorId === "not_established" || executionTier === "not_established"
      ? "not_established"
      : tierDecayFindings.length > 0 || carrierDisposition !== "carrier_current"
        ? "degraded"
        : "observed_healthy";
  return Object.freeze({
    carrierDisposition,
    connectorId,
    executionTier,
    health,
    raw: Object.freeze({ ...raw }),
    tierDecayFindings: Object.freeze([...tierDecayFindings]),
  });
}

function orderedBacklog(
  rows: readonly VisibleBacklogRow[],
  order: AcquisitionBacklogOrder,
) {
  const copy = [...rows];
  if (order === "route_demand") {
    return copy.sort(
      (left, right) =>
        right.route_demand - left.route_demand ||
        left.variable_id.localeCompare(right.variable_id),
    );
  }
  if (order === "variable_id") {
    return copy.sort((left, right) =>
      left.variable_id.localeCompare(right.variable_id),
    );
  }
  return copy.sort((left, right) => left.serverRank - right.serverRank);
}

export function presentAcquisitionBacklog(
  backlog: readonly AcquisitionBacklogProjection[],
  order: AcquisitionBacklogOrder = "server_rank",
): VisibleAcquisitionBacklog {
  const rows = backlog.map((row) =>
    Object.freeze({ ...row, serverRank: row.rank }),
  );
  const zeroConfidenceCount = rows.filter(
    (row) => row.binding_confidence === 0,
  ).length;
  const zeroScoreCount = rows.filter((row) => row.ranking_score === 0).length;
  return Object.freeze({
    demandOneCount: rows.filter((row) => row.route_demand === 1).length,
    demandTwoCount: rows.filter((row) => row.route_demand === 2).length,
    hasNonzeroPriorityGradient: rows.some((row) => row.ranking_score !== 0),
    localOrderOverride: order !== "server_rank",
    order,
    rows: Object.freeze(orderedBacklog(rows, order)),
    totalCount: rows.length,
    voiEstablished: false,
    zeroConfidenceCount,
    zeroScoreCount,
  });
}

export function presentAcquisitionGrowth(
  packet: AcquisitionGrowthPacket,
  order: AcquisitionBacklogOrder = "server_rank",
): VisibleAcquisitionGrowth {
  return Object.freeze({
    backlog: presentAcquisitionBacklog(packet.payload.backlog, order),
    connector: presentConnectorAcquisitionScorecard(
      packet.payload.carrier_liveness,
    ),
    history: packet.payload.n13b_history,
    packet,
    structuralRoutes: Object.freeze([...packet.payload.structural_routes]),
    summary: packet.payload.summary,
  });
}

export type VisibleRunAcquisitionRoute = Readonly<{
  actionEligible: boolean;
  authorityBadge: AcquisitionRouteProjection["authority_badge"];
  cost: Readonly<Record<string, unknown>>;
  costAvailability: "available";
  qualification: Readonly<{
    code: AcquisitionRouteProjection["qualification_reason"];
    epochState: AcquisitionRouteProjection["qualification_status"];
    status: AcquisitionRouteProjection["qualification_predicate"];
  }>;
  route: AcquisitionRouteProjection;
  strategy: string;
  voiAvailability: "not_established";
}>;

export function presentRunAcquisitionRoute(
  route: AcquisitionRouteProjection,
): VisibleRunAcquisitionRoute {
  return Object.freeze({
    actionEligible:
      route.route_status === "costed_actionable" &&
      route.authority_capability === "ready" &&
      route.execution_capability === "ready",
    authorityBadge: route.authority_badge,
    cost: Object.freeze({ ...route.cost_basis }),
    costAvailability: "available",
    qualification: Object.freeze({
      code: route.qualification_reason,
      epochState: route.qualification_status,
      status: route.qualification_predicate,
    }),
    route,
    strategy: route.recommended_strategy,
    voiAvailability: "not_established",
  });
}
