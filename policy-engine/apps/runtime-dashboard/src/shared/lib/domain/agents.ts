import {
  asArray,
  asNumber,
  asRecord,
  asString,
  toDisplayLabel,
} from "../parsing";
import type { AgentPipelineStep } from "@polisyos/runtime-api-client";

import {
  createInteractionState,
  type InteractionState,
} from "./statusOwnership";

export type AgentStepStatus = AgentPipelineStep["status"];
export type AgentCostOrigin = "reported" | "estimated" | "reuse" | "unknown";
export type AgentSettlementStatus =
  | "pending"
  | "committed"
  | "unknown"
  | "unmanaged";

export type AgentCostEventView = {
  eventId: string;
  eventIdentityPresent?: boolean;
  originEventId: string | null;
  costOrigin: AgentCostOrigin;
  controlJobAttempt: number | null;
  preAdmissionAttemptId: string | null;
  currentOwnerEligible: boolean;
  amount: string | null;
  costUsd: number | null;
  settlementStatus: AgentSettlementStatus;
  durability: "ledger" | "memory" | "none" | null;
  receipts: string[];
  payloadDigest: string | null;
  model: string | null;
  provider: string | null;
};

export type AgentCostCompleteness =
  | "not_observed"
  | "unknown"
  | "partial_unknown"
  | "complete";

export type AgentCostSummary = {
  costUsd: number | null;
  reportedCostUsd: number | null;
  estimatedCostUsd: number | null;
  costOriginCounts: Record<string, number>;
  settlementStatusCounts: Record<string, number>;
  costUnknown: boolean;
  costCompleteness: AgentCostCompleteness;
};

export type AgentUnattributedCostScalarView = {
  sourceKind:
    | "step_summary"
    | "attempt_summary"
    | "pipeline_summary"
    | "performance_summary_llm"
    | "performance_summary_variant_row";
  sourceField: "cost_usd" | "reported_cost_usd" | "estimated_cost_usd";
  claimedValueUsd: number;
  scope: "not_established";
  attempt: number | null;
  agent: string | null;
  model: string | null;
  modelVariantId: string | null;
  sourceIndex: number | null;
};

export type AgentStepView = {
  attempt: number;
  agent: string;
  agentLabel: string;
  action: string;
  actionLabel: string;
  status: AgentStepStatus;
  timestamp: string | null;
  summary: string | null;
  model: string | null;
  provider: string | null;
  modelVariantId: string | null;
  latencyMs: number | null;
  costUsd: number | null;
  costUnknown: boolean;
  ownerCostUnknown: boolean;
  costEvents: AgentCostEventView[];
  unattributedCostScalars: AgentUnattributedCostScalarView[];
  prompt: string | null;
  response: string | null;
  promptTokens: number | null;
  completionTokens: number | null;
  totalTokens: number | null;
  details: Record<string, unknown>;
  detailsCostScope: "not_established";
};

export type AgentAttemptView = {
  attempt: number;
  status: string;
  verdict: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  durationMs: number | null;
  costUsd: number | null;
  reportedCostUsd: number | null;
  estimatedCostUsd: number | null;
  costOriginCounts: Record<string, number>;
  settlementStatusCounts: Record<string, number>;
  unattributedCostScalars: AgentUnattributedCostScalarView[];
  steps: AgentStepView[];
  notes: string[];
};

export type RetrievalPhaseView = {
  phase: string;
  lane: string | null;
  durationMs: number;
  candidatesTotal: number;
  candidatesSelected: number;
  docsFetched: number;
};

export type RetrievalTelemetryModel = {
  mode: string;
  laneUsed: string;
  metadataDocsFetched: number;
  localIndexSizeBytes: number;
  localIndexDocsTotal: number;
  candidatesFiltered: number;
  candidatesPromoted: number;
  phases: RetrievalPhaseView[];
  notes: string[];
};

export type PreflightDiagnosticModel = {
  code: string;
  severity: string;
  message: string;
  path: string[];
  replanningHints: string[];
};

export type PreflightModel = {
  readyToRun: boolean;
  diagnostics: PreflightDiagnosticModel[];
  notes: string[];
};

export type EvaluatorScoresModel = {
  kpiScore: number;
  uncertaintyScore: number;
  constraintsScore: number;
  dataQualityScore: number;
  budgetScore: number;
  totalScore: number;
};

export type EvaluatorModel = {
  verdict: string | null;
  scores: EvaluatorScoresModel;
  reasons: string[];
  replanningHints: string[];
};

export type IterationLifecycleModel = {
  iteration: number;
  state: string;
  stopReason: string | null;
  lastVerdict: string | null;
  notes: string[];
};

export type ReproducibilityModel = {
  seed: number;
  planHash: string | null;
  registryHash: string | null;
  methodCatalogHash: string | null;
  dataSnapshotHash: string | null;
  inputBindingsHash: string | null;
  notes: string[];
};

export type PerformanceBudgetDisplayState = InteractionState;

export type PerformancePhaseBudgetView = {
  category: string;
  phase: string;
  durationMs: number;
  budgetMs: number | null;
  status: PerformanceBudgetDisplayState;
};

export type RunPerformanceSummaryModel = {
  variantsTotal: number;
  variantsCompleted: number;
  variantsFailed: number;
  llmLatencyMs: number;
  totalTokens: number;
  phaseBudgets: PerformancePhaseBudgetView[];
  overBudgetCount: number;
};

export type AgentPipelineModel = {
  runId: string;
  ownerControlJobAttempt: number | null;
  totalAttempts: number;
  latestVerdict: string | null;
  source: string | null;
  hasPromptData: boolean;
  costUsd: number | null;
  reportedCostUsd: number | null;
  estimatedCostUsd: number | null;
  costOriginCounts: Record<string, number>;
  settlementStatusCounts: Record<string, number>;
  attempts: AgentAttemptView[];
  unattributedCostEvents: AgentCostEventView[];
  unattributedCostScalars: AgentUnattributedCostScalarView[];
  retrieval: RetrievalTelemetryModel | null;
  preflight: PreflightModel | null;
  evaluator: EvaluatorModel | null;
  iterationLifecycle: IterationLifecycleModel | null;
  reproducibility: ReproducibilityModel | null;
  performanceSummary: RunPerformanceSummaryModel | null;
  notes: string[];
};

const AGENT_LABELS: Record<string, string> = {
  pi_agent: "PI Agent",
  data_need_extractor: "Data Need Extractor",
  source_resolver: "Source Resolver",
  executor: "Executor",
  promotion_lane: "Promotion Lane",
  drafter: "Drafter",
  formalizer: "Formalizer",
  critic: "Critic",
  reflexion: "Reflexion",
};

const AGENT_ORDER = [
  "pi_agent",
  "data_need_extractor",
  "source_resolver",
  "executor",
  "promotion_lane",
  "drafter",
  "formalizer",
  "critic",
  "reflexion",
];

function normalizeStatus(value: unknown): AgentStepStatus {
  const normalized = (asString(value) ?? "").toLowerCase();
  if (
    normalized === "ok" ||
    normalized === "warn" ||
    normalized === "fail" ||
    normalized === "info"
  ) {
    return normalized;
  }
  return "info";
}

function normalizeCostOrigin(value: unknown): AgentCostOrigin {
  const normalized = (asString(value) ?? "unknown").toLowerCase();
  if (
    normalized === "reported" ||
    normalized === "estimated" ||
    normalized === "reuse"
  ) {
    return normalized;
  }
  return "unknown";
}

function normalizeSettlementStatus(value: unknown): AgentSettlementStatus {
  const normalized = (asString(value) ?? "unknown").toLowerCase();
  if (
    normalized === "pending" ||
    normalized === "committed" ||
    normalized === "unmanaged"
  ) {
    return normalized;
  }
  return "unknown";
}

function isCurrentOwnerCostEvent(
  event: Pick<
    AgentCostEventView,
    "controlJobAttempt" | "preAdmissionAttemptId" | "durability"
  >,
  ownerAttempt: number | null,
): boolean {
  return (
    ownerAttempt !== null &&
    event.durability === "ledger" &&
    event.controlJobAttempt === ownerAttempt &&
    event.preAdmissionAttemptId === null
  );
}

function normalizeCostEvent(
  raw: unknown,
  ownerAttempt: number | null,
  preserveUnattributedClaim = false,
): AgentCostEventView | null {
  const event = asRecord(raw);
  if (!event) {
    return null;
  }
  const costOrigin = normalizeCostOrigin(event.cost_origin);
  const amount = asString(event.amount);
  const costUsd =
    costOrigin === "unknown"
      ? null
      : (asNumber(event.cost_usd) ?? asNumber(amount));
  const durabilityValue = asString(event.durability);
  const durability =
    durabilityValue === "ledger" ||
    durabilityValue === "memory" ||
    durabilityValue === "none"
      ? durabilityValue
      : null;
  const controlJobAttempt = asNumber(event.control_job_attempt);
  const preAdmissionAttemptId = asString(event.pre_admission_attempt_id);
  const currentOwnerEligible = isCurrentOwnerCostEvent(
    { controlJobAttempt, preAdmissionAttemptId, durability },
    ownerAttempt,
  );
  const eventId = asString(event.event_id);
  return {
    eventId: eventId ?? "unidentified",
    eventIdentityPresent: eventId !== null && eventId.length > 0,
    originEventId: asString(event.origin_event_id),
    costOrigin,
    controlJobAttempt,
    preAdmissionAttemptId,
    currentOwnerEligible,
    amount,
    costUsd: currentOwnerEligible || preserveUnattributedClaim ? costUsd : null,
    settlementStatus: normalizeSettlementStatus(event.settlement_status),
    durability,
    receipts: asArray(event.receipts)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
    payloadDigest: asString(event.payload_digest),
    model: asString(event.model),
    provider: asString(event.provider),
  };
}

function normalizeCostEvents(
  raw: unknown,
  ownerAttempt: number | null,
  preserveUnattributedClaim = false,
): AgentCostEventView[] {
  return asArray(raw)
    .map((event) =>
      normalizeCostEvent(event, ownerAttempt, preserveUnattributedClaim),
    )
    .filter((event): event is AgentCostEventView => event !== null);
}

function normalizeUnattributedCostScalar(
  raw: unknown,
): AgentUnattributedCostScalarView | null {
  const scalar = asRecord(raw);
  if (!scalar || scalar.scope !== "not_established") {
    return null;
  }
  const sourceKind = scalar.source_kind;
  if (
    sourceKind !== "step_summary" &&
    sourceKind !== "attempt_summary" &&
    sourceKind !== "pipeline_summary" &&
    sourceKind !== "performance_summary_llm" &&
    sourceKind !== "performance_summary_variant_row"
  ) {
    return null;
  }
  const sourceField = scalar.source_field;
  if (
    sourceField !== "cost_usd" &&
    sourceField !== "reported_cost_usd" &&
    sourceField !== "estimated_cost_usd"
  ) {
    return null;
  }
  const claimedValueUsd = scalar.claimed_value_usd;
  if (
    typeof claimedValueUsd !== "number" ||
    !Number.isFinite(claimedValueUsd) ||
    claimedValueUsd < 0
  ) {
    return null;
  }
  return {
    sourceKind,
    sourceField,
    claimedValueUsd,
    scope: "not_established",
    attempt: asNumber(scalar.attempt),
    agent: asString(scalar.agent),
    model: asString(scalar.model),
    modelVariantId: asString(scalar.model_variant_id),
    sourceIndex: asNumber(scalar.source_index),
  };
}

function normalizeUnattributedCostScalars(
  raw: unknown,
): AgentUnattributedCostScalarView[] {
  return asArray(raw)
    .map(normalizeUnattributedCostScalar)
    .filter(
      (scalar): scalar is AgentUnattributedCostScalarView => scalar !== null,
    );
}

type AgentCostProducerProjection = Pick<
  AgentCostSummary,
  "costUsd" | "reportedCostUsd" | "estimatedCostUsd"
>;

/**
 * Mirrors the Core producer scalar projection for reconciliation only.
 *
 * This preserves producer zero subtotals and source event multiplicity. It is
 * deliberately separate from the origin-aware, identity-reduced UI summary.
 */
function projectProducerCostScalars(
  events: AgentCostEventView[],
  ownerAttempt: number | null,
): AgentCostProducerProjection {
  const currentOwnerEvents = events.filter((event) =>
    isCurrentOwnerCostEvent(event, ownerAttempt),
  );
  if (currentOwnerEvents.length === 0) {
    return {
      costUsd: null,
      reportedCostUsd: null,
      estimatedCostUsd: null,
    };
  }

  let totalCostUsd = 0;
  let reportedCostUsd = 0;
  let estimatedCostUsd = 0;
  let costIsUnknown = false;
  for (const event of currentOwnerEvents) {
    if (event.costOrigin === "reported" && event.costUsd !== null) {
      reportedCostUsd += event.costUsd;
    }
    if (event.costOrigin === "estimated" && event.costUsd !== null) {
      estimatedCostUsd += event.costUsd;
    }
    if (
      event.costOrigin === "unknown" ||
      event.settlementStatus === "pending" ||
      event.settlementStatus === "unknown" ||
      event.costUsd === null
    ) {
      costIsUnknown = true;
    } else if (
      event.costOrigin === "reported" ||
      event.costOrigin === "estimated" ||
      event.costOrigin === "reuse"
    ) {
      totalCostUsd += event.costUsd;
    }
  }

  return {
    costUsd: costIsUnknown ? null : totalCostUsd,
    reportedCostUsd,
    estimatedCostUsd,
  };
}

function legacyCostScalars(
  record: Record<string, unknown>,
  sourceKind: AgentUnattributedCostScalarView["sourceKind"],
  projectedValues: AgentCostProducerProjection,
): AgentUnattributedCostScalarView[] {
  const sourceFields = [
    "cost_usd",
    "reported_cost_usd",
    "estimated_cost_usd",
  ] as const;
  return sourceFields.flatMap((sourceField) => {
    const claimedValueUsd = record[sourceField];
    if (
      typeof claimedValueUsd !== "number" ||
      !Number.isFinite(claimedValueUsd) ||
      claimedValueUsd < 0
    ) {
      return [];
    }
    const projectedValue =
      sourceField === "cost_usd"
        ? projectedValues.costUsd
        : sourceField === "reported_cost_usd"
          ? projectedValues.reportedCostUsd
          : projectedValues.estimatedCostUsd;
    if (claimedValueUsd === projectedValue) {
      return [];
    }
    return [
      {
        sourceKind,
        sourceField,
        claimedValueUsd,
        scope: "not_established" as const,
        attempt: asNumber(record.attempt),
        agent: asString(record.agent),
        model: asString(record.model),
        modelVariantId: asString(record.model_variant_id),
        sourceIndex: null,
      },
    ];
  });
}

function parseOwnerControlJobAttempt(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 1) {
    return null;
  }
  return value;
}

function hasEligibleCurrentAttemptEvents(
  events: AgentCostEventView[],
  ownerAttempt: number | null,
): boolean {
  return events.some((event) => isCurrentOwnerCostEvent(event, ownerAttempt));
}

function hasCostEventIdentity(event: AgentCostEventView): boolean {
  return event.eventIdentityPresent !== false && event.eventId.length > 0;
}

function sameCostEventObservation(
  left: AgentCostEventView,
  right: AgentCostEventView,
): boolean {
  return (
    left.eventId === right.eventId &&
    left.originEventId === right.originEventId &&
    left.costOrigin === right.costOrigin &&
    left.controlJobAttempt === right.controlJobAttempt &&
    left.preAdmissionAttemptId === right.preAdmissionAttemptId &&
    left.currentOwnerEligible === right.currentOwnerEligible &&
    left.amount === right.amount &&
    left.costUsd === right.costUsd &&
    left.settlementStatus === right.settlementStatus &&
    left.durability === right.durability &&
    left.receipts.length === right.receipts.length &&
    left.receipts.every(
      (receipt, index) => receipt === right.receipts[index],
    ) &&
    left.payloadDigest === right.payloadDigest &&
    left.model === right.model &&
    left.provider === right.provider
  );
}

function uniqueCostEventObservations(events: AgentCostEventView[]): {
  events: AgentCostEventView[];
  unresolvedIdentity: boolean;
} {
  const eventsById = new Map<string, AgentCostEventView>();
  const conflictingEventIds = new Set<string>();
  let unresolvedIdentity = false;

  for (const event of events) {
    if (!hasCostEventIdentity(event)) {
      unresolvedIdentity = true;
      continue;
    }
    if (conflictingEventIds.has(event.eventId)) {
      continue;
    }
    const existing = eventsById.get(event.eventId);
    if (!existing) {
      eventsById.set(event.eventId, event);
      continue;
    }
    if (sameCostEventObservation(existing, event)) {
      continue;
    }

    // One producer identity cannot support two different payloads. Exclude
    // every row for that identity and retain only uncontested event subtotals.
    eventsById.delete(event.eventId);
    conflictingEventIds.add(event.eventId);
    unresolvedIdentity = true;
  }

  return {
    events: Array.from(eventsById.values()),
    unresolvedIdentity,
  };
}

function summarizeCurrentCostEvents(
  currentAttemptEvents: AgentCostEventView[],
  unknownClaim: boolean,
): AgentCostSummary {
  let unresolved = unknownClaim;
  let reported: number | null = null;
  let estimated: number | null = null;
  const costOriginCounts: Record<string, number> = {};
  const settlementStatusCounts: Record<string, number> = {};

  for (const event of currentAttemptEvents) {
    costOriginCounts[event.costOrigin] =
      (costOriginCounts[event.costOrigin] ?? 0) + 1;
    settlementStatusCounts[event.settlementStatus] =
      (settlementStatusCounts[event.settlementStatus] ?? 0) + 1;
    if (
      event.costOrigin === "unknown" ||
      event.costOrigin === "reuse" ||
      event.settlementStatus === "unknown" ||
      event.settlementStatus === "pending" ||
      event.costUsd === null
    ) {
      // A reuse event can expose the original provider amount. It does not
      // establish the incremental cost of the reuse operation itself.
      unresolved = true;
      continue;
    }
    if (event.costOrigin === "reported") {
      reported = (reported ?? 0) + event.costUsd;
    } else if (event.costOrigin === "estimated") {
      estimated = (estimated ?? 0) + event.costUsd;
    }
  }

  const hasObservedOriginAmount = reported !== null || estimated !== null;
  const costCompleteness: AgentCostCompleteness = unresolved
    ? hasObservedOriginAmount
      ? "partial_unknown"
      : "unknown"
    : currentAttemptEvents.length > 0
      ? "complete"
      : "not_observed";
  const onlyReportedOrigin =
    !unresolved && reported !== null && estimated === null;

  return {
    // The legacy generic field remains populated only when it can mean a
    // complete reported amount; estimates and reuse amounts are never folded
    // into a single unlabeled total.
    costUsd: onlyReportedOrigin ? reported : null,
    reportedCostUsd: reported,
    estimatedCostUsd: estimated,
    costOriginCounts,
    settlementStatusCounts,
    costUnknown: unresolved,
    costCompleteness,
  };
}

function summarizeCostEvents(
  events: AgentCostEventView[],
  ownerAttempt: number | null,
  unknownClaim = false,
): AgentCostSummary {
  const currentOwnerEvents = events.filter((event) =>
    hasEligibleCurrentAttemptEvents([event], ownerAttempt),
  );
  const resolved = uniqueCostEventObservations(currentOwnerEvents);
  const currentAttemptEvents = resolved.events;
  const unattributedClaim = unknownClaim || resolved.unresolvedIdentity;
  return summarizeCurrentCostEvents(currentAttemptEvents, unattributedClaim);
}

/**
 * Summarizes normalized events for one UI consumer using the durable owner attempt.
 *
 * Reported and estimated amounts remain separate. Reuse amounts remain in event
 * lineage and are not treated as incremental spend; unresolved claims stay open.
 */
export function summarizeAgentCostEvents(
  events: AgentCostEventView[],
  ownerAttempt: number | null,
  ownerUnknownClaim = false,
): AgentCostSummary {
  return summarizeCostEvents(events, ownerAttempt, ownerUnknownClaim);
}

function normalizeAgent(value: unknown): string {
  const normalized = (asString(value) ?? "unknown").toLowerCase();
  if (normalized === "pi" || normalized === "pi_decompose") {
    return "pi_agent";
  }
  if (normalized === "data_need_extract") {
    return "data_need_extractor";
  }
  if (normalized === "formalize") {
    return "formalizer";
  }
  if (normalized === "critic_review") {
    return "critic";
  }
  return normalized;
}

function normalizeRetrievalPhase(raw: unknown): RetrievalPhaseView | null {
  const row = asRecord(raw);
  if (!row) {
    return null;
  }
  const phase = asString(row.phase);
  if (!phase) {
    return null;
  }
  return {
    phase,
    lane: asString(row.lane),
    durationMs: Math.max(0, asNumber(row.duration_ms) ?? 0),
    candidatesTotal: Math.max(0, asNumber(row.candidates_total) ?? 0),
    candidatesSelected: Math.max(0, asNumber(row.candidates_selected) ?? 0),
    docsFetched: Math.max(0, asNumber(row.docs_fetched) ?? 0),
  };
}

function normalizeRetrievalTelemetry(
  raw: unknown,
): RetrievalTelemetryModel | null {
  const telemetry = asRecord(raw);
  if (!telemetry) {
    return null;
  }
  return {
    mode: asString(telemetry.mode) ?? "hybrid",
    laneUsed: asString(telemetry.lane_used) ?? "none",
    metadataDocsFetched: Math.max(
      0,
      asNumber(telemetry.metadata_docs_fetched) ?? 0,
    ),
    localIndexSizeBytes: Math.max(
      0,
      asNumber(telemetry.local_index_size_bytes) ?? 0,
    ),
    localIndexDocsTotal: Math.max(
      0,
      asNumber(telemetry.local_index_docs_total) ?? 0,
    ),
    candidatesFiltered: Math.max(
      0,
      asNumber(telemetry.candidates_filtered) ?? 0,
    ),
    candidatesPromoted: Math.max(
      0,
      asNumber(telemetry.candidates_promoted) ?? 0,
    ),
    phases: asArray(telemetry.phases)
      .map((item) => normalizeRetrievalPhase(item))
      .filter((item): item is RetrievalPhaseView => item !== null),
    notes: asArray(telemetry.notes)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
  };
}

function normalizePreflight(raw: unknown): PreflightModel | null {
  const payload = asRecord(raw);
  if (!payload) {
    return null;
  }
  return {
    readyToRun: Boolean(payload.ready_to_run),
    diagnostics: asArray(payload.diagnostics)
      .map((item) => asRecord(item))
      .filter((item): item is Record<string, unknown> => item !== null)
      .map((item) => ({
        code: asString(item.code) ?? "unknown",
        severity: asString(item.severity) ?? "error",
        message: asString(item.message) ?? "",
        path: asArray(item.path)
          .map((entry) => asString(entry))
          .filter((entry): entry is string => entry !== null),
        replanningHints: asArray(item.replanning_hints)
          .map((entry) => asString(entry))
          .filter((entry): entry is string => entry !== null),
      })),
    notes: asArray(payload.notes)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
  };
}

function normalizeEvaluator(raw: unknown): EvaluatorModel | null {
  const payload = asRecord(raw);
  if (!payload) {
    return null;
  }
  const scores = asRecord(payload.scores);
  return {
    verdict: asString(payload.verdict),
    scores: {
      kpiScore: asNumber(scores?.kpi_score) ?? 0,
      uncertaintyScore: asNumber(scores?.uncertainty_score) ?? 0,
      constraintsScore: asNumber(scores?.constraints_score) ?? 0,
      dataQualityScore: asNumber(scores?.data_quality_score) ?? 0,
      budgetScore: asNumber(scores?.budget_score) ?? 0,
      totalScore: asNumber(scores?.total_score) ?? 0,
    },
    reasons: asArray(payload.reasons)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
    replanningHints: asArray(payload.replanning_hints)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
  };
}

function normalizeIterationLifecycle(
  raw: unknown,
): IterationLifecycleModel | null {
  const payload = asRecord(raw);
  if (!payload) {
    return null;
  }
  return {
    iteration: Math.max(1, asNumber(payload.iteration) ?? 1),
    state: asString(payload.state) ?? "unknown",
    stopReason: asString(payload.stop_reason),
    lastVerdict: asString(payload.last_verdict),
    notes: asArray(payload.notes)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
  };
}

function normalizeReproducibility(raw: unknown): ReproducibilityModel | null {
  const payload = asRecord(raw);
  if (!payload) {
    return null;
  }
  return {
    seed: Math.max(0, asNumber(payload.seed) ?? 0),
    planHash: asString(payload.plan_hash),
    registryHash: asString(payload.registry_hash),
    methodCatalogHash: asString(payload.method_catalog_hash),
    dataSnapshotHash: asString(payload.data_snapshot_hash),
    inputBindingsHash: asString(payload.input_bindings_hash),
    notes: asArray(payload.notes)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
  };
}

export function createPerformanceBudgetDisplayState(
  raw: unknown,
): PerformanceBudgetDisplayState {
  const status = (asString(raw) ?? "unknown").toLowerCase() || "unknown";
  return createInteractionState(status, "diagnostic_display");
}

function normalizePerformancePhaseBudget(
  raw: unknown,
): PerformancePhaseBudgetView | null {
  const row = asRecord(raw);
  if (!row) {
    return null;
  }
  const phase = asString(row.phase);
  if (!phase) {
    return null;
  }
  return {
    budgetMs: asNumber(row.budget_ms),
    category: asString(row.category) ?? "runtime",
    durationMs: Math.max(0, asNumber(row.duration_ms) ?? 0),
    phase,
    status: createPerformanceBudgetDisplayState(row.status),
  };
}

function normalizeRunPerformanceSummary(
  raw: unknown,
): RunPerformanceSummaryModel | null {
  const payload = asRecord(raw);
  if (!payload) {
    return null;
  }
  const variants = asRecord(payload.variants);
  const llm = asRecord(payload.llm);
  const phaseBudgets = asArray(payload.phase_budgets)
    .map((item) => normalizePerformancePhaseBudget(item))
    .filter((item): item is PerformancePhaseBudgetView => item !== null);
  const overBudgetCount = phaseBudgets.filter(
    (row) => row.status.label === "over_budget",
  ).length;

  return {
    variantsTotal: Math.max(0, asNumber(variants?.total) ?? 0),
    variantsCompleted: Math.max(0, asNumber(variants?.completed) ?? 0),
    variantsFailed: Math.max(0, asNumber(variants?.failed) ?? 0),
    llmLatencyMs: Math.max(0, asNumber(llm?.latency_ms) ?? 0),
    totalTokens: Math.max(0, asNumber(llm?.total_tokens) ?? 0),
    phaseBudgets,
    overBudgetCount,
  };
}

function normalizeStep(
  raw: unknown,
  ownerAttempt: number | null,
): AgentStepView | null {
  const step = asRecord(raw);
  if (!step) {
    return null;
  }

  const agent = normalizeAgent(step.agent);
  const action = asString(step.action) ?? "unknown";
  const tokenUsage = asRecord(step.token_usage);
  const costEvents = normalizeCostEvents(step.cost_events, ownerAttempt);
  const explicitUnattributedCostScalars = normalizeUnattributedCostScalars(
    step.unattributed_cost_scalars,
  );
  const ownerCostSummary = summarizeCostEvents(costEvents, ownerAttempt);
  const producerCostProjection = projectProducerCostScalars(
    costEvents,
    ownerAttempt,
  );
  const unattributedCostScalars =
    explicitUnattributedCostScalars.length > 0
      ? explicitUnattributedCostScalars
      : legacyCostScalars(step, "step_summary", producerCostProjection);
  const hasOnlyUnscopedEvents =
    costEvents.length > 0 &&
    !costEvents.some((event) => isCurrentOwnerCostEvent(event, ownerAttempt));

  return {
    attempt: Math.max(1, asNumber(step.attempt) ?? 1),
    agent,
    agentLabel: AGENT_LABELS[agent] ?? toDisplayLabel(agent),
    action,
    actionLabel: toDisplayLabel(action),
    status: normalizeStatus(step.status),
    timestamp: asString(step.timestamp),
    summary: asString(step.summary),
    model: asString(step.model),
    provider: asString(step.provider),
    modelVariantId: asString(step.model_variant_id),
    latencyMs: asNumber(step.latency_ms),
    costUsd: ownerCostSummary.costUsd,
    costUnknown:
      ownerCostSummary.costUnknown ||
      hasOnlyUnscopedEvents ||
      unattributedCostScalars.length > 0,
    ownerCostUnknown: ownerCostSummary.costUnknown,
    costEvents,
    unattributedCostScalars,
    prompt: asString(step.prompt),
    response: asString(step.response),
    promptTokens: asNumber(tokenUsage?.prompt_tokens),
    completionTokens: asNumber(tokenUsage?.completion_tokens),
    totalTokens: asNumber(tokenUsage?.total_tokens),
    details: asRecord(step.details) ?? {},
    detailsCostScope: "not_established",
  };
}

function agentRank(agent: string): number {
  const idx = AGENT_ORDER.indexOf(agent);
  return idx >= 0 ? idx : AGENT_ORDER.length + 1;
}

function sortSteps(left: AgentStepView, right: AgentStepView): number {
  const leftTs = left.timestamp
    ? Date.parse(left.timestamp)
    : Number.POSITIVE_INFINITY;
  const rightTs = right.timestamp
    ? Date.parse(right.timestamp)
    : Number.POSITIVE_INFINITY;
  if (leftTs !== rightTs) {
    return leftTs - rightTs;
  }
  const rank = agentRank(left.agent) - agentRank(right.agent);
  if (rank !== 0) {
    return rank;
  }
  return left.action.localeCompare(right.action);
}

function normalizeAttempt(
  raw: unknown,
  ownerAttempt: number | null,
): AgentAttemptView | null {
  const attempt = asRecord(raw);
  if (!attempt) {
    return null;
  }

  const attemptNumber = asNumber(attempt.attempt) ?? 1;
  const sourceOrderSteps = asArray(attempt.steps)
    .map((item) => normalizeStep(item, ownerAttempt))
    .filter((item): item is AgentStepView => item !== null);
  const producerCostProjection = projectProducerCostScalars(
    sourceOrderSteps.flatMap((step) => step.costEvents),
    ownerAttempt,
  );
  const steps = sourceOrderSteps.sort(sortSteps);
  const costEvents = steps.flatMap((step) => step.costEvents);
  const explicitUnattributedCostScalars = normalizeUnattributedCostScalars(
    attempt.unattributed_cost_scalars,
  );
  const costSummary = summarizeCostEvents(costEvents, ownerAttempt);
  const unattributedCostScalars =
    explicitUnattributedCostScalars.length > 0
      ? explicitUnattributedCostScalars
      : [
          ...steps.flatMap((step) => step.unattributedCostScalars),
          ...legacyCostScalars(
            attempt,
            "attempt_summary",
            producerCostProjection,
          ),
        ];

  return {
    attempt: Math.max(1, asNumber(attempt.attempt) ?? 1),
    status: asString(attempt.status) ?? "unknown",
    verdict: asString(attempt.verdict),
    startedAt: asString(attempt.started_at),
    finishedAt: asString(attempt.finished_at),
    durationMs: asNumber(attempt.duration_ms),
    costUsd: costSummary.costUsd,
    reportedCostUsd: costSummary.reportedCostUsd,
    estimatedCostUsd: costSummary.estimatedCostUsd,
    costOriginCounts: costSummary.costOriginCounts,
    settlementStatusCounts: costSummary.settlementStatusCounts,
    unattributedCostScalars,
    steps,
    notes: asArray(attempt.notes)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
  };
}

export function normalizeAgentPipeline(payload: unknown): AgentPipelineModel {
  const pipeline = asRecord(payload) ?? {};
  const ownerControlJobAttempt = parseOwnerControlJobAttempt(
    pipeline.owner_control_job_attempt,
  );
  const producerCostEvents = asArray(pipeline.attempts).flatMap(
    (rawAttempt) => {
      const attempt = asRecord(rawAttempt);
      return asArray(attempt?.steps).flatMap((rawStep) => {
        const step = asRecord(rawStep);
        return normalizeCostEvents(step?.cost_events, ownerControlJobAttempt);
      });
    },
  );
  const producerCostProjection = projectProducerCostScalars(
    producerCostEvents,
    ownerControlJobAttempt,
  );
  const attempts = asArray(pipeline.attempts)
    .map((item) => normalizeAttempt(item, ownerControlJobAttempt))
    .filter((item): item is AgentAttemptView => item !== null)
    .sort((left, right) => left.attempt - right.attempt);

  const hasPromptData = attempts.some((attempt) =>
    attempt.steps.some((step) => Boolean(step.prompt || step.response)),
  );
  const unattributedCostEvents = normalizeCostEvents(
    pipeline.unattributed_cost_events,
    null,
    true,
  );
  const explicitUnattributedCostScalars = normalizeUnattributedCostScalars(
    pipeline.unattributed_cost_scalars,
  );
  // Unassigned rows are rendered separately and are not current-attempt totals.
  const costEvents = attempts.flatMap((attempt) =>
    attempt.steps.flatMap((step) => step.costEvents),
  );
  const costSummary = summarizeCostEvents(costEvents, ownerControlJobAttempt);
  const unattributedCostScalars =
    explicitUnattributedCostScalars.length > 0
      ? explicitUnattributedCostScalars
      : [
          ...attempts.flatMap((attempt) => attempt.unattributedCostScalars),
          ...legacyCostScalars(
            pipeline,
            "pipeline_summary",
            producerCostProjection,
          ),
        ];

  return {
    runId: asString(pipeline.run_id) ?? "unknown",
    ownerControlJobAttempt,
    totalAttempts: asNumber(pipeline.total_attempts) ?? attempts.length,
    latestVerdict: asString(pipeline.latest_verdict),
    source: asString(pipeline.source),
    hasPromptData,
    costUsd: costSummary.costUsd,
    reportedCostUsd: costSummary.reportedCostUsd,
    estimatedCostUsd: costSummary.estimatedCostUsd,
    costOriginCounts: costSummary.costOriginCounts,
    settlementStatusCounts: costSummary.settlementStatusCounts,
    attempts,
    unattributedCostEvents,
    unattributedCostScalars,
    retrieval: normalizeRetrievalTelemetry(pipeline.retrieval),
    preflight: normalizePreflight(pipeline.preflight),
    evaluator: normalizeEvaluator(pipeline.evaluator),
    iterationLifecycle: normalizeIterationLifecycle(
      pipeline.iteration_lifecycle,
    ),
    reproducibility: normalizeReproducibility(pipeline.reproducibility),
    performanceSummary: normalizeRunPerformanceSummary(
      pipeline.performance_summary,
    ),
    notes: asArray(pipeline.notes)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
  };
}
