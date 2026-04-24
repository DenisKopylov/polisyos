import { useState, useCallback } from "react";

import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/LocaleProvider";
import { Card } from "@/shared/ui/primitives";

export type ReasoningStepType =
  | "question"
  | "interpretation"
  | "retrieval"
  | "analysis"
  | "conclusion";

export type ReasoningStep = {
  id: string;
  type: ReasoningStepType;
  title: string;
  summary: string;
  detail?: string;
  durationMs?: number;
  metadata?: Record<string, string>;
};

type ReasoningChainDisplayProps = {
  steps: ReasoningStep[];
  title?: string;
  className?: string;
};

const STEP_CONFIG: Record<
  ReasoningStepType,
  { icon: string; label: string; color: string }
> = {
  question: {
    icon: "\u2753",
    label: "User question",
    color: "var(--color-chart-primary)",
  },
  interpretation: {
    icon: "\uD83D\uDD0D",
    label: "Interpreted query",
    color: "var(--color-chart-secondary)",
  },
  retrieval: {
    icon: "\uD83D\uDCC2",
    label: "Data retrieved",
    color: "var(--color-chart-tertiary)",
  },
  analysis: {
    icon: "\u2699\uFE0F",
    label: "Causal analysis",
    color: "var(--color-confidence-medium)",
  },
  conclusion: {
    icon: "\u2705",
    label: "Conclusion",
    color: "var(--color-status-approved)",
  },
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function StepNode({
  step,
  isLast,
  isExpanded,
  onToggle,
}: {
  step: ReasoningStep;
  isLast: boolean;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const config = STEP_CONFIG[step.type];
  const hasDetail = Boolean(step.detail || step.metadata);

  return (
    <div className="flex gap-3">
      {/* Timeline rail */}
      <div className="flex flex-col items-center">
        <div
          className="flex size-8 shrink-0 items-center justify-center rounded-full border-2 text-sm"
          style={{ borderColor: config.color }}
          aria-hidden="true"
        >
          {config.icon}
        </div>
        {!isLast && (
          <div
            className="w-0.5 grow"
            style={{ backgroundColor: config.color, opacity: 0.3 }}
          />
        )}
      </div>

      {/* Content */}
      <div className={cn("pb-5", isLast && "pb-0", "min-w-0 flex-1")}>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className="text-xs font-semibold tracking-wide uppercase"
            style={{ color: config.color }}
          >
            {config.label}
          </span>
          {step.durationMs != null && (
            <span className="text-muted text-xs">
              {formatDuration(step.durationMs)}
            </span>
          )}
        </div>

        <p className="mt-0.5 text-sm font-semibold">{step.title}</p>
        <p className="text-muted mt-0.5 text-sm">{step.summary}</p>

        {hasDetail && (
          <button
            type="button"
            onClick={onToggle}
            className="text-muted mt-1 text-xs underline decoration-dotted underline-offset-2 hover:text-inherit"
          >
            {isExpanded ? "Hide details" : "Show details"}
          </button>
        )}

        {isExpanded && step.detail && (
          <div className="bg-surface border-line mt-2 rounded-xl border p-3 text-sm whitespace-pre-wrap">
            {step.detail}
          </div>
        )}

        {isExpanded && step.metadata && (
          <div className="mt-2 flex flex-wrap gap-2">
            {Object.entries(step.metadata).map(([key, value]) => (
              <span
                key={key}
                className="bg-surface border-line rounded-lg border px-2 py-1 text-xs"
              >
                <span className="text-muted">{key}:</span>{" "}
                <span className="font-medium">{value}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function ReasoningChainDisplay({
  steps,
  title = "AI Reasoning Chain",
  className,
}: ReasoningChainDisplayProps) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = useCallback((id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const expandAll = useCallback(() => {
    setExpanded(new Set(steps.map((s) => s.id)));
  }, [steps]);

  const collapseAll = useCallback(() => {
    setExpanded(new Set());
  }, []);

  const totalDuration = steps.reduce((sum, s) => sum + (s.durationMs ?? 0), 0);

  return (
    <Card className={cn("space-y-4", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">{title}</h3>
        <div className="flex items-center gap-3">
          {totalDuration > 0 && (
            <span className="text-muted text-xs">
              {t("shared.ui.reasoningChain.totalDuration", {
                duration: formatDuration(totalDuration),
              })}
            </span>
          )}
          <button
            type="button"
            onClick={expanded.size > 0 ? collapseAll : expandAll}
            className="text-xs font-medium text-[var(--color-chart-primary)] hover:underline"
          >
            {expanded.size > 0 ? "Collapse all" : "Expand all"}
          </button>
        </div>
      </div>

      <div>
        {steps.map((step, i) => (
          <StepNode
            key={step.id}
            step={step}
            isLast={i === steps.length - 1}
            isExpanded={expanded.has(step.id)}
            onToggle={() => toggle(step.id)}
          />
        ))}
      </div>
    </Card>
  );
}
