import { asArray, asNumber, asRecord, asString, toDisplayLabel } from "../parsing";

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
  latencyMs: number | null;
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

export type AgentPipelineModel = {
  runId: string;
  totalAttempts: number;
  latestVerdict: string | null;
  source: string | null;
  hasPromptData: boolean;
  attempts: AgentAttemptView[];
  notes: string[];
};

const AGENT_LABELS: Record<string, string> = {
  pi_agent: "PI Agent",
  drafter: "Drafter",
  formalizer: "Formalizer",
  critic: "Critic",
  reflexion: "Reflexion",
};

const AGENT_ORDER = ["pi_agent", "drafter", "formalizer", "critic", "reflexion"];

function normalizeStatus(value: unknown): AgentStepStatus {
  const normalized = (asString(value) ?? "").toLowerCase();
  if (normalized === "ok" || normalized === "warn" || normalized === "fail" || normalized === "info") {
    return normalized;
  }
  return "info";
}

function normalizeAgent(value: unknown): string {
  const normalized = (asString(value) ?? "unknown").toLowerCase();
  if (normalized === "pi" || normalized === "pi_decompose") {
    return "pi_agent";
  }
  if (normalized === "formalize") {
    return "formalizer";
  }
  if (normalized === "critic_review") {
    return "critic";
  }
  return normalized;
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
    latencyMs: asNumber(step.latency_ms),
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
  const leftTs = left.timestamp ? Date.parse(left.timestamp) : Number.POSITIVE_INFINITY;
  const rightTs = right.timestamp ? Date.parse(right.timestamp) : Number.POSITIVE_INFINITY;
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
    notes: asArray(pipeline.notes)
      .map((item) => asString(item))
      .filter((item): item is string => item !== null),
  };
}
