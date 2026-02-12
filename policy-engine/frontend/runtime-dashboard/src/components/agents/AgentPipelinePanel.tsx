import { useMemo, useState } from "react";

import { normalizeAgentPipeline } from "../../lib/domain/agents";
import { formatDate, formatDuration } from "../../lib/utils";
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
