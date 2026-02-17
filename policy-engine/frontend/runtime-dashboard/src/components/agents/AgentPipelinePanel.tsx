import { useMemo, useState } from "react";

import { normalizeAgentPipeline } from "../../lib/domain/agents";
import { formatBytes, formatDate, formatDuration } from "../../lib/utils";
import StatusBadge from "../shared/StatusBadge";
import EmptyState from "../shared/EmptyState";

type AgentPipelinePanelProps = {
  payload: unknown;
};

function stepStatusKind(status: string): "ok" | "warn" | "fail" | "unknown" {
  if (status === "ok") {
    return "ok";
  }
  if (status === "warn") {
    return "warn";
  }
  if (status === "fail") {
    return "fail";
  }
  return "unknown";
}

export default function AgentPipelinePanel({ payload }: AgentPipelinePanelProps) {
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
          costUsd: 0,
        };
        existing.steps += 1;
        existing.promptTokens += step.promptTokens ?? 0;
        existing.completionTokens += step.completionTokens ?? 0;
        existing.totalTokens += step.totalTokens ?? (step.promptTokens ?? 0) + (step.completionTokens ?? 0);
        existing.latencyMs += step.latencyMs ?? 0;
        existing.costUsd += step.costUsd ?? 0;
        if (!existing.provider && step.provider) {
          existing.provider = step.provider;
        }
        bucket.set(key, existing);
      }
    }

    return Array.from(bucket.values()).sort((left, right) => right.totalTokens - left.totalTokens);
  }, [pipeline.attempts]);

  const selectedStep = useMemo(() => {
    if (!selectedKey) {
      return null;
    }
    for (const attempt of pipeline.attempts) {
      const found = attempt.steps.find(
        (step) => `${attempt.attempt}:${step.agent}:${step.action}:${step.timestamp ?? "na"}` === selectedKey,
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
        title="Agent pipeline unavailable"
        body="No agent-attempt data was extracted for this run."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-2 md:grid-cols-4">
        <div className="rounded-xl border border-line p-2 text-sm">
          <p className="text-xs uppercase text-muted">Attempts</p>
          <p className="font-semibold">{pipeline.totalAttempts}</p>
        </div>
        <div className="rounded-xl border border-line p-2 text-sm">
          <p className="text-xs uppercase text-muted">Latest verdict</p>
          <p className="font-semibold">{pipeline.latestVerdict ?? "-"}</p>
        </div>
        <div className="rounded-xl border border-line p-2 text-sm">
          <p className="text-xs uppercase text-muted">Source</p>
          <p className="font-semibold">{pipeline.source ?? "-"}</p>
        </div>
        <div className="rounded-xl border border-line p-2 text-sm">
          <p className="text-xs uppercase text-muted">Prompt data</p>
          <p className="font-semibold">{pipeline.hasPromptData ? "yes" : "no"}</p>
        </div>
      </div>

      {pipeline.notes.length ? (
        <div className="rounded-xl border border-warning/30 bg-warning/5 p-2 text-xs text-warning">
          {pipeline.notes.join(" · ")}
        </div>
      ) : null}

      {pipeline.retrieval ? (
        <section className="rounded-xl border border-line bg-panel/65 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold">Retrieval telemetry</h4>
            <p className="text-xs text-muted">
              {pipeline.retrieval.mode} / {pipeline.retrieval.laneUsed}
            </p>
          </div>
          <div className="grid gap-2 md:grid-cols-4">
            <div className="rounded-lg border border-line bg-canvas/30 p-2 text-xs">
              <p className="uppercase text-muted">Metadata docs</p>
              <p className="text-sm font-semibold">
                {pipeline.retrieval.metadataDocsFetched.toLocaleString()}
              </p>
            </div>
            <div className="rounded-lg border border-line bg-canvas/30 p-2 text-xs">
              <p className="uppercase text-muted">Index size</p>
              <p className="text-sm font-semibold">
                {formatBytes(pipeline.retrieval.localIndexSizeBytes)}
              </p>
            </div>
            <div className="rounded-lg border border-line bg-canvas/30 p-2 text-xs">
              <p className="uppercase text-muted">Index docs</p>
              <p className="text-sm font-semibold">
                {pipeline.retrieval.localIndexDocsTotal.toLocaleString()}
              </p>
            </div>
            <div className="rounded-lg border border-line bg-canvas/30 p-2 text-xs">
              <p className="uppercase text-muted">Filtered / promoted</p>
              <p className="text-sm font-semibold">
                {pipeline.retrieval.candidatesFiltered} / {pipeline.retrieval.candidatesPromoted}
              </p>
            </div>
          </div>
          {pipeline.retrieval.phases.length > 0 ? (
            <div className="mt-3 space-y-2">
              {pipeline.retrieval.phases.map((phase) => (
                <div
                  key={`${phase.phase}:${phase.lane ?? "none"}`}
                  className="grid gap-2 rounded-lg border border-line bg-canvas/20 p-2 text-xs md:grid-cols-6"
                >
                  <div>
                    <p className="uppercase text-muted">Phase</p>
                    <p className="font-semibold">{phase.phase}</p>
                  </div>
                  <div>
                    <p className="uppercase text-muted">Lane</p>
                    <p>{phase.lane ?? "-"}</p>
                  </div>
                  <div>
                    <p className="uppercase text-muted">Duration</p>
                    <p>{formatDuration(phase.durationMs)}</p>
                  </div>
                  <div>
                    <p className="uppercase text-muted">Candidates</p>
                    <p>{phase.candidatesTotal.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="uppercase text-muted">Selected</p>
                    <p>{phase.candidatesSelected.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="uppercase text-muted">Docs fetched</p>
                    <p>{phase.docsFetched.toLocaleString()}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          {pipeline.retrieval.notes.length > 0 ? (
            <p className="mt-2 text-xs text-warning">{pipeline.retrieval.notes.join(" · ")}</p>
          ) : null}
        </section>
      ) : null}

      {pipeline.preflight ? (
        <section className="rounded-xl border border-line bg-panel/65 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold">Preflight diagnostics</h4>
            <StatusBadge
              label={pipeline.preflight.readyToRun ? "ready" : "blocked"}
              kind={pipeline.preflight.readyToRun ? "ok" : "warn"}
            />
          </div>
          <p className="text-xs text-muted">
            diagnostics: {pipeline.preflight.diagnostics.length}
          </p>
          {pipeline.preflight.diagnostics.length > 0 ? (
            <div className="mt-2 space-y-2">
              {pipeline.preflight.diagnostics.map((diag, idx) => (
                <div key={`${diag.code}:${idx}`} className="rounded-lg border border-line bg-canvas/30 p-2 text-xs">
                  <p className="font-semibold">
                    {diag.code} ({diag.severity})
                  </p>
                  <p>{diag.message}</p>
                  {diag.replanningHints.length > 0 ? (
                    <p className="mt-1 text-muted">Hints: {diag.replanningHints.join(" · ")}</p>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {pipeline.evaluator ? (
        <section className="rounded-xl border border-line bg-panel/65 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold">Evaluator verdict</h4>
            <StatusBadge
              label={pipeline.evaluator.verdict ?? "-"}
              kind={pipeline.evaluator.verdict === "APPROVE" ? "ok" : "warn"}
            />
          </div>
          <div className="grid gap-2 text-xs md:grid-cols-3">
            <div className="rounded-lg border border-line bg-canvas/30 p-2">
              <p className="uppercase text-muted">Total score</p>
              <p className="text-sm font-semibold">{pipeline.evaluator.scores.totalScore.toFixed(3)}</p>
            </div>
            <div className="rounded-lg border border-line bg-canvas/30 p-2">
              <p className="uppercase text-muted">KPI / Constraints</p>
              <p className="text-sm font-semibold">
                {pipeline.evaluator.scores.kpiScore.toFixed(3)} / {pipeline.evaluator.scores.constraintsScore.toFixed(3)}
              </p>
            </div>
            <div className="rounded-lg border border-line bg-canvas/30 p-2">
              <p className="uppercase text-muted">Data / Budget</p>
              <p className="text-sm font-semibold">
                {pipeline.evaluator.scores.dataQualityScore.toFixed(3)} / {pipeline.evaluator.scores.budgetScore.toFixed(3)}
              </p>
            </div>
          </div>
          {pipeline.evaluator.reasons.length > 0 ? (
            <p className="mt-2 text-xs text-muted">Reasons: {pipeline.evaluator.reasons.join(" · ")}</p>
          ) : null}
        </section>
      ) : null}

      {pipeline.iterationLifecycle || pipeline.reproducibility ? (
        <section className="rounded-xl border border-line bg-panel/65 p-3">
          <h4 className="mb-2 text-sm font-semibold">Iteration and reproducibility</h4>
          <div className="grid gap-2 md:grid-cols-2">
            <div className="rounded-lg border border-line bg-canvas/30 p-2 text-xs">
              <p className="uppercase text-muted">State</p>
              <p className="font-semibold">
                {pipeline.iterationLifecycle?.state ?? "-"} (iter {pipeline.iterationLifecycle?.iteration ?? 1})
              </p>
              <p className="text-muted">Stop: {pipeline.iterationLifecycle?.stopReason ?? "-"}</p>
            </div>
            <div className="rounded-lg border border-line bg-canvas/30 p-2 text-xs">
              <p className="uppercase text-muted">Seed / Plan hash</p>
              <p className="font-semibold">{pipeline.reproducibility?.seed ?? 0}</p>
              <p className="break-all text-muted">{pipeline.reproducibility?.planHash ?? "-"}</p>
            </div>
          </div>
        </section>
      ) : null}

      {modelSummary.length > 0 ? (
        <section className="rounded-xl border border-line bg-panel/65 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold">Model comparison</h4>
            <p className="text-xs text-muted">{modelSummary.length} variants</p>
          </div>
          <div className="space-y-2">
            {modelSummary.map((row) => (
              <div
                key={row.key}
                className="grid gap-2 rounded-lg border border-line bg-canvas/30 p-2 text-xs md:grid-cols-7"
              >
                <div>
                  <p className="text-[10px] uppercase text-muted">Model</p>
                  <p className="font-semibold">{row.model}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase text-muted">Variant</p>
                  <p>{row.modelVariantId ?? "-"}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase text-muted">Provider</p>
                  <p>{row.provider ?? "-"}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase text-muted">Tokens</p>
                  <p>{row.totalTokens.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase text-muted">Prompt/Comp</p>
                  <p>
                    {row.promptTokens.toLocaleString()} / {row.completionTokens.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase text-muted">Latency</p>
                  <p>{formatDuration(row.latencyMs)}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase text-muted">Cost</p>
                  <p>{row.costUsd > 0 ? `$${row.costUsd.toFixed(6)}` : "-"}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-[1.7fr_1fr]">
        <div className="space-y-3">
          {pipeline.attempts.map((attempt) => (
            <section key={attempt.attempt} className="rounded-xl border border-line bg-panel/70 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-semibold">Attempt {attempt.attempt}</h4>
                  <StatusBadge label={attempt.status} kind={stepStatusKind(attempt.status)} />
                  {attempt.verdict ? (
                    <span className="rounded-full border border-line bg-canvas/60 px-2 py-0.5 text-xs">
                      {attempt.verdict}
                    </span>
                  ) : null}
                </div>
                <p className="text-xs text-muted">
                  {formatDate(attempt.startedAt)} → {formatDate(attempt.finishedAt)} · {formatDuration(attempt.durationMs)}
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
                          ? "rounded-xl border border-text/35 bg-text/5 px-3 py-2 text-left"
                          : "rounded-xl border border-line bg-panel px-3 py-2 text-left"
                      }
                    >
                      <div className="mb-1 flex items-center gap-2">
                        <span className="text-xs font-semibold uppercase">{step.agentLabel}</span>
                        <StatusBadge label={step.status} kind={stepStatusKind(step.status)} />
                      </div>
                      <p className="text-sm font-semibold">{step.actionLabel}</p>
                      <p className="text-xs text-muted">{formatDate(step.timestamp)}</p>
                    </button>
                  );
                })}
              </div>
            </section>
          ))}
        </div>

        <aside className="rounded-xl border border-line bg-panel/85 p-3">
          {selectedStep ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <h4 className="text-sm font-semibold">{selectedStep.agentLabel}</h4>
                <StatusBadge label={selectedStep.status} kind={stepStatusKind(selectedStep.status)} />
              </div>
              <div className="text-sm">
                <p className="text-xs uppercase text-muted">Action</p>
                <p className="font-semibold">{selectedStep.actionLabel}</p>
              </div>
              <div className="text-sm">
                <p className="text-xs uppercase text-muted">Summary</p>
                <p>{selectedStep.summary ?? "-"}</p>
              </div>
              <div className="grid gap-2 text-sm md:grid-cols-2">
                <div>
                  <p className="text-xs uppercase text-muted">Model</p>
                  <p>{selectedStep.model ?? "-"}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-muted">Provider</p>
                  <p>{selectedStep.provider ?? "-"}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-muted">Model variant</p>
                  <p>{selectedStep.modelVariantId ?? "-"}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-muted">Latency</p>
                  <p>{formatDuration(selectedStep.latencyMs)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-muted">Prompt tokens</p>
                  <p>{selectedStep.promptTokens ?? "-"}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-muted">Completion tokens</p>
                  <p>{selectedStep.completionTokens ?? "-"}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-muted">Cost</p>
                  <p>{selectedStep.costUsd != null ? `$${selectedStep.costUsd.toFixed(6)}` : "-"}</p>
                </div>
              </div>
              {selectedStep.prompt ? (
                <div>
                  <p className="mb-1 text-xs uppercase text-muted">Prompt</p>
                  <pre className="max-h-44 overflow-auto rounded-lg border border-line bg-canvas/60 p-2 text-[11px] leading-relaxed">
                    {selectedStep.prompt}
                  </pre>
                </div>
              ) : null}
              {selectedStep.response ? (
                <div>
                  <p className="mb-1 text-xs uppercase text-muted">Response</p>
                  <pre className="max-h-44 overflow-auto rounded-lg border border-line bg-canvas/60 p-2 text-[11px] leading-relaxed">
                    {selectedStep.response}
                  </pre>
                </div>
              ) : null}
              <details className="rounded-lg border border-line bg-canvas/40 p-2 text-xs">
                <summary className="cursor-pointer font-semibold">Raw details</summary>
                <pre className="mt-2 max-h-40 overflow-auto">{JSON.stringify(selectedStep.details, null, 2)}</pre>
              </details>
            </div>
          ) : (
            <p className="text-sm text-muted">Select an agent step to inspect prompt/response and metadata.</p>
          )}
        </aside>
      </div>
    </div>
  );
}
