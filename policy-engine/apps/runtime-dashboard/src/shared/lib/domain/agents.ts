import {
  asArray,
  asNumber,
  asRecord,
  asString,
  toDisplayLabel,
} from "../parsing";

export type AgentStepStatus = "ok" | "warn" | "fail" | "info";

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
  prompt: string | null;
  response: string | null;
  promptTokens: number | null;
  completionTokens: number | null;
  totalTokens: number | null;
  details: Record<string, unknown>;
};

export type AgentAttemptView = {
  attempt: number;
  status: string;
  verdict: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  durationMs: number | null;
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

export type PerformanceBudgetStatus =
  | "over_budget"
  | "within_budget"
  | "unknown";

export type PerformancePhaseBudgetView = {
  category: string;
  phase: string;
  durationMs: number;
  budgetMs: number | null;
  status: PerformanceBudgetStatus;
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
  totalAttempts: number;
  latestVerdict: string | null;
  source: string | null;
  hasPromptData: boolean;
  attempts: AgentAttemptView[];
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

function normalizePerformanceStatus(raw: unknown): PerformanceBudgetStatus {
  const status = (asString(raw) ?? "").toLowerCase();
  if (status === "over_budget" || status === "within_budget") {
    return status;
  }
  return "unknown";
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
    status: normalizePerformanceStatus(row.status),
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
    (row) => row.status === "over_budget",
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

function normalizeStep(raw: unknown): AgentStepView | null {
  const step = asRecord(raw);
  if (!step) {
    return null;
  }

  const agent = normalizeAgent(step.agent);
  const action = asString(step.action) ?? "unknown";
  const tokenUsage = asRecord(step.token_usage);

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
    costUsd: asNumber(step.cost_usd),
    prompt: asString(step.prompt),
    response: asString(step.response),
    promptTokens: asNumber(tokenUsage?.prompt_tokens),
    completionTokens: asNumber(tokenUsage?.completion_tokens),
    totalTokens: asNumber(tokenUsage?.total_tokens),
    details: asRecord(step.details) ?? {},
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

function normalizeAttempt(raw: unknown): AgentAttemptView | null {
  const attempt = asRecord(raw);
  if (!attempt) {
    return null;
  }

  const steps = asArray(attempt.steps)
    .map((item) => normalizeStep(item))
    .filter((item): item is AgentStepView => item !== null)
    .sort(sortSteps);

  return {
    attempt: Math.max(1, asNumber(attempt.attempt) ?? 1),
    status: asString(attempt.status) ?? "unknown",
    verdict: asString(attempt.verdict),
    startedAt: asString(attempt.started_at),
    finishedAt: asString(attempt.finished_at),
    durationMs: asNumber(attempt.duration_ms),
    steps,
    notes: asArray(attempt.notes)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
  };
}

export function normalizeAgentPipeline(payload: unknown): AgentPipelineModel {
  const pipeline = asRecord(payload) ?? {};
  const attempts = asArray(pipeline.attempts)
    .map((item) => normalizeAttempt(item))
    .filter((item): item is AgentAttemptView => item !== null)
    .sort((left, right) => left.attempt - right.attempt);

  const hasPromptData = attempts.some((attempt) =>
    attempt.steps.some((step) => Boolean(step.prompt || step.response)),
  );

  return {
    runId: asString(pipeline.run_id) ?? "unknown",
    totalAttempts: asNumber(pipeline.total_attempts) ?? attempts.length,
    latestVerdict: asString(pipeline.latest_verdict),
    source: asString(pipeline.source),
    hasPromptData,
    attempts,
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
