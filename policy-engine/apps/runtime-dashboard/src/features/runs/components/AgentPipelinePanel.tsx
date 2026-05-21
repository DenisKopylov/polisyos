import { useMemo, useState } from "react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { normalizeAgentPipeline } from "@/shared/lib/domain/agents";
import {
  formatBytes,
  formatCurrency,
  formatDate,
  formatDuration,
  formatNumber,
} from "@/shared/lib/utils";
import { Badge, EmptyState } from "@/shared/ui";
import { Quantity, untracedDecisionQuantity } from "@/shared/ui/quantity";

type AgentPipelinePanelProps = {
  payload: unknown;
};

function stepStatusKind(status: string): "ok" | "warn" | "fail" | "neutral" {
  if (status === "ok") {
    return "ok";
  }
  if (status === "warn") {
    return "warn";
  }
  if (status === "fail") {
    return "fail";
  }
  return "neutral";
}

function PipelineScoreQuantity({
  point,
  metricId,
  label,
}: {
  point: number | null | undefined;
  metricId: string;
  label: string;
}) {
  return (
    <Quantity
      value={untracedDecisionQuantity({
        point,
        metricId,
        label,
        reasonCode: "agent_pipeline_without_lineage",
      })}
      precision={3}
      variant="dense"
    />
  );
}

export default function AgentPipelinePanel({
  payload,
}: AgentPipelinePanelProps) {
  const { t, label } = useI18n();
  const pipeline = useMemo(() => normalizeAgentPipeline(payload), [payload]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const modelSummary = useMemo(() => {
    const bucket = new Map<
      string,
      {
        key: string;
        model: string;
        provider: string | null;
        modelVariantId: string | null;
        steps: number;
        promptTokens: number;
        completionTokens: number;
        totalTokens: number;
        latencyMs: number;
        costUsd: number;
      }
    >();

    for (const attempt of pipeline.attempts) {
      for (const step of attempt.steps) {
        const model = step.model ?? "mock";
        const key = step.modelVariantId ?? model;
        const existing = bucket.get(key) ?? {
          key,
          model,
          provider: step.provider,
          modelVariantId: step.modelVariantId,
          steps: 0,
          promptTokens: 0,
          completionTokens: 0,
          totalTokens: 0,
          latencyMs: 0,
          costUsd: /* policyos-quantity: telemetry */ 0,
        };
        existing.steps += 1;
        existing.promptTokens += step.promptTokens ?? 0;
        existing.completionTokens += step.completionTokens ?? 0;
        existing.totalTokens +=
          step.totalTokens ??
          (step.promptTokens ?? 0) + (step.completionTokens ?? 0);
        existing.latencyMs += step.latencyMs ?? 0;
        existing.costUsd += step.costUsd ?? 0;
        if (!existing.provider && step.provider) {
          existing.provider = step.provider;
        }
        bucket.set(key, existing);
      }
    }

    return Array.from(bucket.values()).sort(
      (left, right) => right.totalTokens - left.totalTokens,
    );
  }, [pipeline.attempts]);

  const selectedStep = useMemo(() => {
    if (!selectedKey) {
      return null;
    }
    for (const attempt of pipeline.attempts) {
      const found = attempt.steps.find(
        (step) =>
          `${attempt.attempt}:${step.agent}:${step.action}:${step.timestamp ?? "na"}` ===
          selectedKey,
      );
      if (found) {
        return found;
      }
    }
    return null;
  }, [pipeline.attempts, selectedKey]);

  if (!pipeline.attempts.length) {
    return (
      <EmptyState
        title={t("panels.agentPipeline.unavailableTitle")}
        body={t("panels.agentPipeline.unavailableBody")}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-2 md:grid-cols-4">
        <div className="border-line rounded-xl border p-2 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("panels.agentPipeline.attempts")}
          </p>
          <p className="font-semibold">
            {formatNumber(pipeline.totalAttempts)}
          </p>
        </div>
        <div className="border-line rounded-xl border p-2 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("panels.agentPipeline.latestVerdict")}
          </p>
          <p className="font-semibold">
            {label(
              "evaluatorVerdicts",
              pipeline.latestVerdict,
              pipeline.latestVerdict ?? "-",
            )}
          </p>
        </div>
        <div className="border-line rounded-xl border p-2 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("panels.agentPipeline.source")}
          </p>
          <p className="font-semibold">{pipeline.source ?? "-"}</p>
        </div>
        <div className="border-line rounded-xl border p-2 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("panels.agentPipeline.promptData")}
          </p>
          <p className="font-semibold">
            {pipeline.hasPromptData ? t("common.yes") : t("common.no")}
          </p>
        </div>
      </div>

      {pipeline.notes.length ? (
        <div className="border-warning/30 bg-warning/5 text-warning rounded-xl border p-2 text-xs">
          {pipeline.notes.join(" · ")}
        </div>
      ) : null}

      {pipeline.performanceSummary ? (
        <section className="bg-panel/65 border-line rounded-xl border p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold">
              {t("panels.agentPipeline.performanceBudget")}
            </h4>
            <Badge
              kind={
                pipeline.performanceSummary.overBudgetCount > 0 ? "warn" : "ok"
              }
            >
              {pipeline.performanceSummary.overBudgetCount > 0
                ? t("panels.agentPipeline.overBudget", {
                    count: formatNumber(
                      pipeline.performanceSummary.overBudgetCount,
                    ),
                  })
                : t("panels.agentPipeline.withinBudget")}
            </Badge>
          </div>
          <div className="grid gap-2 md:grid-cols-4">
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-xs">
              <p className="text-muted uppercase">
                {t("panels.agentPipeline.variantsCompleted")}
              </p>
              <p className="text-sm font-semibold">
                {formatNumber(pipeline.performanceSummary.variantsCompleted)} /{" "}
                {formatNumber(pipeline.performanceSummary.variantsTotal)}
              </p>
            </div>
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-xs">
              <p className="text-muted uppercase">
                {t("panels.agentPipeline.failedVariants")}
              </p>
              <p className="text-sm font-semibold">
                {formatNumber(pipeline.performanceSummary.variantsFailed)}
              </p>
            </div>
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-xs">
              <p className="text-muted uppercase">
                {t("panels.agentPipeline.llmLatency")}
              </p>
              <p className="text-sm font-semibold">
                {formatDuration(pipeline.performanceSummary.llmLatencyMs)}
              </p>
            </div>
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-xs">
              <p className="text-muted uppercase">
                {t("panels.agentPipeline.totalTokens")}
              </p>
              <p className="text-sm font-semibold">
                {formatNumber(pipeline.performanceSummary.totalTokens)}
              </p>
            </div>
          </div>
          {pipeline.performanceSummary.phaseBudgets.length > 0 ? (
            <div className="mt-3 space-y-2">
              {pipeline.performanceSummary.phaseBudgets.map((row, idx) => (
                <div
                  key={`${row.phase}:${idx}`}
                  className={
                    row.status === "over_budget"
                      ? "border-warning/35 bg-warning/5 grid gap-2 rounded-lg border p-2 text-xs md:grid-cols-5"
                      : "bg-canvas/30 border-line grid gap-2 rounded-lg border p-2 text-xs md:grid-cols-5"
                  }
                >
                  <div className="md:col-span-2">
                    <p className="text-muted uppercase">
                      {t("panels.agentPipeline.phase")}
                    </p>
                    <p className="font-semibold break-words">{row.phase}</p>
                  </div>
                  <div>
                    <p className="text-muted uppercase">
                      {t("panels.agentPipeline.category")}
                    </p>
                    <p>{row.category}</p>
                  </div>
                  <div>
                    <p className="text-muted uppercase">
                      {t("panels.agentPipeline.observed")}
                    </p>
                    <p>{formatDuration(row.durationMs)}</p>
                  </div>
                  <div>
                    <p className="text-muted uppercase">
                      {t("panels.agentPipeline.budget")}
                    </p>
                    <p>{formatDuration(row.budgetMs)}</p>
                  </div>
                  <div className="md:col-span-5">
                    <Badge
                      kind={
                        row.status === "over_budget"
                          ? "warn"
                          : row.status === "within_budget"
                            ? "ok"
                            : "neutral"
                      }
                    >
                      {row.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {pipeline.retrieval ? (
        <section className="bg-panel/65 border-line rounded-xl border p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold">
              {t("panels.agentPipeline.retrievalTelemetry")}
            </h4>
            <p className="text-muted text-xs">
              {pipeline.retrieval.mode} /{" "}
              {label(
                "retrievalLane",
                pipeline.retrieval.laneUsed,
                pipeline.retrieval.laneUsed,
              )}
            </p>
          </div>
          <div className="grid gap-2 md:grid-cols-4">
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-xs">
              <p className="text-muted uppercase">
                {t("panels.agentPipeline.metadataDocs")}
              </p>
              <p className="text-sm font-semibold">
                {formatNumber(pipeline.retrieval.metadataDocsFetched)}
              </p>
            </div>
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-xs">
              <p className="text-muted uppercase">
                {t("panels.agentPipeline.indexSize")}
              </p>
              <p className="text-sm font-semibold">
                {formatBytes(pipeline.retrieval.localIndexSizeBytes)}
              </p>
            </div>
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-xs">
              <p className="text-muted uppercase">
                {t("panels.agentPipeline.indexDocs")}
              </p>
              <p className="text-sm font-semibold">
                {formatNumber(pipeline.retrieval.localIndexDocsTotal)}
              </p>
            </div>
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-xs">
              <p className="text-muted uppercase">
                {t("panels.agentPipeline.filteredPromoted")}
              </p>
              <p className="text-sm font-semibold">
                {formatNumber(pipeline.retrieval.candidatesFiltered)} /{" "}
                {formatNumber(pipeline.retrieval.candidatesPromoted)}
              </p>
            </div>
          </div>
          {pipeline.retrieval.phases.length > 0 ? (
            <div className="mt-3 space-y-2">
              {pipeline.retrieval.phases.map((phase) => (
                <div
                  key={`${phase.phase}:${phase.lane ?? "none"}`}
                  className="bg-canvas/20 border-line grid gap-2 rounded-lg border p-2 text-xs md:grid-cols-6"
                >
                  <div>
                    <p className="text-muted uppercase">
                      {t("panels.agentPipeline.phase")}
                    </p>
                    <p className="font-semibold">{phase.phase}</p>
                  </div>
                  <div>
                    <p className="text-muted uppercase">
                      {t("panels.agentPipeline.lane")}
                    </p>
                    <p>
                      {label("retrievalLane", phase.lane, phase.lane ?? "-")}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted uppercase">
                      {t("panels.agentPipeline.duration")}
                    </p>
                    <p>{formatDuration(phase.durationMs)}</p>
                  </div>
                  <div>
                    <p className="text-muted uppercase">
                      {t("panels.agentPipeline.candidates")}
                    </p>
                    <p>{formatNumber(phase.candidatesTotal)}</p>
                  </div>
                  <div>
                    <p className="text-muted uppercase">
                      {t("panels.agentPipeline.selected")}
                    </p>
                    <p>{formatNumber(phase.candidatesSelected)}</p>
                  </div>
                  <div>
                    <p className="text-muted uppercase">
                      {t("panels.agentPipeline.docsFetched")}
                    </p>
                    <p>{formatNumber(phase.docsFetched)}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          {pipeline.retrieval.notes.length > 0 ? (
            <p className="text-warning mt-2 text-xs">
              {pipeline.retrieval.notes.join(" · ")}
            </p>
          ) : null}
        </section>
      ) : null}

      {pipeline.preflight ? (
        <section className="bg-panel/65 border-line rounded-xl border p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold">
              {t("panels.agentPipeline.preflightDiagnostics")}
            </h4>
            <Badge kind={pipeline.preflight.readyToRun ? "ok" : "warn"}>
              {pipeline.preflight.readyToRun
                ? t("common.ready")
                : t("common.blocked")}
            </Badge>
          </div>
          <p className="text-muted text-xs">
            {t("panels.agentPipeline.diagnostics", {
              count: formatNumber(pipeline.preflight.diagnostics.length),
            })}
          </p>
          {pipeline.preflight.diagnostics.length > 0 ? (
            <div className="mt-2 space-y-2">
              {pipeline.preflight.diagnostics.map((diag, idx) => (
                <div
                  key={`${diag.code}:${idx}`}
                  className="bg-canvas/30 border-line rounded-lg border p-2 text-xs"
                >
                  <p className="font-semibold">
                    {diag.code} (
                    {label("governanceSeverity", diag.severity, diag.severity)})
                  </p>
                  <p>{diag.message}</p>
                  {diag.replanningHints.length > 0 ? (
                    <p className="text-muted mt-1">
                      {t("panels.agentPipeline.hints", {
                        hints: diag.replanningHints.join(" · "),
                      })}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {pipeline.evaluator ? (
        <section className="bg-panel/65 border-line rounded-xl border p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold">
              {t("panels.agentPipeline.evaluatorVerdict")}
            </h4>
            <Badge
              kind={pipeline.evaluator.verdict === "APPROVE" ? "ok" : "warn"}
            >
              {label(
                "evaluatorVerdicts",
                pipeline.evaluator.verdict,
                pipeline.evaluator.verdict ?? "-",
              )}
            </Badge>
          </div>
          <div className="grid gap-2 text-xs md:grid-cols-3">
            <div className="bg-canvas/30 border-line rounded-lg border p-2">
              <p className="text-muted uppercase">
                {t("panels.agentPipeline.totalScore")}
              </p>
              <p className="text-sm font-semibold">
                <PipelineScoreQuantity
                  point={pipeline.evaluator.scores.totalScore}
                  metricId="agent_pipeline_total_score"
                  label={t("panels.agentPipeline.totalScore")}
                />
              </p>
            </div>
            <div className="bg-canvas/30 border-line rounded-lg border p-2">
              <p className="text-muted uppercase">
                {t("panels.agentPipeline.kpiConstraints")}
              </p>
              <p className="text-sm font-semibold">
                <PipelineScoreQuantity
                  point={pipeline.evaluator.scores.kpiScore}
                  metricId="agent_pipeline_kpi_score"
                  label={t("panels.agentPipeline.kpiConstraints")}
                />{" "}
                /{" "}
                <PipelineScoreQuantity
                  point={pipeline.evaluator.scores.constraintsScore}
                  metricId="agent_pipeline_constraints_score"
                  label={t("panels.agentPipeline.kpiConstraints")}
                />
              </p>
            </div>
            <div className="bg-canvas/30 border-line rounded-lg border p-2">
              <p className="text-muted uppercase">
                {t("panels.agentPipeline.dataBudget")}
              </p>
              <p className="text-sm font-semibold">
                <PipelineScoreQuantity
                  point={pipeline.evaluator.scores.dataQualityScore}
                  metricId="agent_pipeline_data_quality_score"
                  label={t("panels.agentPipeline.dataBudget")}
                />{" "}
                /{" "}
                <PipelineScoreQuantity
                  point={pipeline.evaluator.scores.budgetScore}
                  metricId="agent_pipeline_budget_score"
                  label={t("panels.agentPipeline.dataBudget")}
                />
              </p>
            </div>
          </div>
          {pipeline.evaluator.reasons.length > 0 ? (
            <p className="text-muted mt-2 text-xs">
              {t("panels.agentPipeline.reasons", {
                reasons: pipeline.evaluator.reasons.join(" · "),
              })}
            </p>
          ) : null}
        </section>
      ) : null}

      {pipeline.iterationLifecycle || pipeline.reproducibility ? (
        <section className="bg-panel/65 border-line rounded-xl border p-3">
          <h4 className="mb-2 text-sm font-semibold">
            {t("panels.agentPipeline.iterationAndRepro")}
          </h4>
          <div className="grid gap-2 md:grid-cols-2">
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-xs">
              <p className="text-muted uppercase">
                {t("panels.agentPipeline.state")}
              </p>
              <p className="font-semibold">
                {label(
                  "workflowStates",
                  pipeline.iterationLifecycle?.state,
                  pipeline.iterationLifecycle?.state ?? "-",
                )}{" "}
                (
                {t("panels.agentPipeline.iteration", {
                  count: formatNumber(
                    pipeline.iterationLifecycle?.iteration ?? 1,
                  ),
                })}
                )
              </p>
              <p className="text-muted">
                {t("panels.agentPipeline.stop", {
                  reason: pipeline.iterationLifecycle?.stopReason ?? "-",
                })}
              </p>
            </div>
            <div className="bg-canvas/30 border-line rounded-lg border p-2 text-xs">
              <p className="text-muted uppercase">
                {t("panels.agentPipeline.seedPlanHash")}
              </p>
              <p className="font-semibold">
                {formatNumber(pipeline.reproducibility?.seed ?? 0)}
              </p>
              <p className="text-muted break-all">
                {pipeline.reproducibility?.planHash ?? "-"}
              </p>
            </div>
          </div>
        </section>
      ) : null}

      {modelSummary.length > 0 ? (
        <section className="bg-panel/65 border-line rounded-xl border p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold">
              {t("panels.agentPipeline.modelComparison")}
            </h4>
            <p className="text-muted text-xs">
              {t("panels.agentPipeline.variants", {
                count: formatNumber(modelSummary.length),
              })}
            </p>
          </div>
          <div className="space-y-2">
            {modelSummary.map((row) => (
              <div
                key={row.key}
                className="bg-canvas/30 border-line grid gap-2 rounded-lg border p-2 text-xs md:grid-cols-7"
              >
                <div>
                  <p className="text-muted text-[10px] uppercase">
                    {t("panels.agentPipeline.model")}
                  </p>
                  <p className="font-semibold">{row.model}</p>
                </div>
                <div>
                  <p className="text-muted text-[10px] uppercase">
                    {t("panels.agentPipeline.variant")}
                  </p>
                  <p>{row.modelVariantId ?? "-"}</p>
                </div>
                <div>
                  <p className="text-muted text-[10px] uppercase">
                    {t("panels.agentPipeline.provider")}
                  </p>
                  <p>{row.provider ?? "-"}</p>
                </div>
                <div>
                  <p className="text-muted text-[10px] uppercase">
                    {t("panels.agentPipeline.tokens")}
                  </p>
                  <p>{formatNumber(row.totalTokens)}</p>
                </div>
                <div>
                  <p className="text-muted text-[10px] uppercase">
                    {t("panels.agentPipeline.promptCompletion")}
                  </p>
                  <p>
                    {formatNumber(row.promptTokens)} /{" "}
                    {formatNumber(row.completionTokens)}
                  </p>
                </div>
                <div>
                  <p className="text-muted text-[10px] uppercase">
                    {t("panels.agentPipeline.latency")}
                  </p>
                  <p>{formatDuration(row.latencyMs)}</p>
                </div>
                <div>
                  <p className="text-muted text-[10px] uppercase">
                    {t("panels.agentPipeline.cost")}
                  </p>
                  <p>
                    {row.costUsd > 0
                      ? formatCurrency(row.costUsd, "USD", undefined, {
                          maximumFractionDigits: 6,
                        })
                      : "-"}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-[1.7fr_1fr]">
        <div className="space-y-3">
          {pipeline.attempts.map((attempt) => (
            <section
              key={attempt.attempt}
              className="bg-panel/70 border-line rounded-xl border p-3"
            >
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-semibold">
                    {t("panels.agentPipeline.attempt", {
                      attempt: attempt.attempt,
                    })}
                  </h4>
                  <Badge kind={stepStatusKind(attempt.status)}>
                    {attempt.status}
                  </Badge>
                  {attempt.verdict ? (
                    <span className="bg-canvas/60 border-line rounded-full border px-2 py-0.5 text-xs">
                      {label(
                        "evaluatorVerdicts",
                        attempt.verdict,
                        attempt.verdict,
                      )}
                    </span>
                  ) : null}
                </div>
                <p className="text-muted text-xs">
                  {formatDate(attempt.startedAt)} {"->"}{" "}
                  {formatDate(attempt.finishedAt)} ·{" "}
                  {formatDuration(attempt.durationMs)}
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                {attempt.steps.map((step) => {
                  const key = `${attempt.attempt}:${step.agent}:${step.action}:${step.timestamp ?? "na"}`;
                  const isSelected = key === selectedKey;
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setSelectedKey(key)}
                      className={
                        isSelected
                          ? "border-text/35 bg-text/5 rounded-xl border px-3 py-2 text-left"
                          : "border-line bg-panel rounded-xl border px-3 py-2 text-left"
                      }
                    >
                      <div className="mb-1 flex items-center gap-2">
                        <span className="text-xs font-semibold uppercase">
                          {step.agentLabel}
                        </span>
                        <Badge kind={stepStatusKind(step.status)}>
                          {step.status}
                        </Badge>
                      </div>
                      <p className="text-sm font-semibold">
                        {step.actionLabel}
                      </p>
                      <p className="text-muted text-xs">
                        {formatDate(step.timestamp)}
                      </p>
                    </button>
                  );
                })}
              </div>
            </section>
          ))}
        </div>

        <section className="bg-panel/85 border-line rounded-xl border p-3">
          {selectedStep ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <h4 className="text-sm font-semibold">
                  {selectedStep.agentLabel}
                </h4>
                <Badge kind={stepStatusKind(selectedStep.status)}>
                  {selectedStep.status}
                </Badge>
              </div>
              <div className="text-sm">
                <p className="text-muted text-xs uppercase">
                  {t("panels.agentPipeline.action")}
                </p>
                <p className="font-semibold">{selectedStep.actionLabel}</p>
              </div>
              <div className="text-sm">
                <p className="text-muted text-xs uppercase">
                  {t("panels.agentPipeline.summary")}
                </p>
                <p>{selectedStep.summary ?? "-"}</p>
              </div>
              <div className="grid gap-2 text-sm md:grid-cols-2">
                <div>
                  <p className="text-muted text-xs uppercase">
                    {t("panels.agentPipeline.model")}
                  </p>
                  <p>{selectedStep.model ?? "-"}</p>
                </div>
                <div>
                  <p className="text-muted text-xs uppercase">
                    {t("panels.agentPipeline.provider")}
                  </p>
                  <p>{selectedStep.provider ?? "-"}</p>
                </div>
                <div>
                  <p className="text-muted text-xs uppercase">
                    {t("panels.agentPipeline.variant")}
                  </p>
                  <p>{selectedStep.modelVariantId ?? "-"}</p>
                </div>
                <div>
                  <p className="text-muted text-xs uppercase">
                    {t("panels.agentPipeline.latency")}
                  </p>
                  <p>{formatDuration(selectedStep.latencyMs)}</p>
                </div>
                <div>
                  <p className="text-muted text-xs uppercase">
                    {t("panels.agentPipeline.promptTokens")}
                  </p>
                  <p>{formatNumber(selectedStep.promptTokens)}</p>
                </div>
                <div>
                  <p className="text-muted text-xs uppercase">
                    {t("panels.agentPipeline.completionTokens")}
                  </p>
                  <p>{formatNumber(selectedStep.completionTokens)}</p>
                </div>
                <div>
                  <p className="text-muted text-xs uppercase">
                    {t("panels.agentPipeline.cost")}
                  </p>
                  <p>
                    {selectedStep.costUsd != null
                      ? formatCurrency(selectedStep.costUsd, "USD", undefined, {
                          maximumFractionDigits: 6,
                        })
                      : "-"}
                  </p>
                </div>
              </div>
              {selectedStep.prompt ? (
                <div>
                  <p className="text-muted mb-1 text-xs uppercase">
                    {t("panels.agentPipeline.prompt")}
                  </p>
                  <pre className="bg-canvas/60 border-line max-h-44 overflow-auto rounded-lg border p-2 text-[11px] leading-relaxed">
                    {selectedStep.prompt}
                  </pre>
                </div>
              ) : null}
              {selectedStep.response ? (
                <div>
                  <p className="text-muted mb-1 text-xs uppercase">
                    {t("panels.agentPipeline.response")}
                  </p>
                  <pre className="bg-canvas/60 border-line max-h-44 overflow-auto rounded-lg border p-2 text-[11px] leading-relaxed">
                    {selectedStep.response}
                  </pre>
                </div>
              ) : null}
              <details className="bg-canvas/40 border-line rounded-lg border p-2 text-xs">
                <summary className="cursor-pointer font-semibold">
                  {t("panels.agentPipeline.rawDetails")}
                </summary>
                <pre className="mt-2 max-h-40 overflow-auto">
                  {JSON.stringify(selectedStep.details, null, 2)}
                </pre>
              </details>
            </div>
          ) : (
            <p className="text-muted text-sm">
              {t("panels.agentPipeline.selectStep")}
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
