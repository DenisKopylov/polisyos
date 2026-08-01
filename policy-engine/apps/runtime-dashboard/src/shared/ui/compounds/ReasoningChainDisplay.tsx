import { useState } from "react";

import { Glyph } from "@/shared/brand/Glyph";
import type { GlyphName } from "@/shared/brand/glyph-vocabulary";
import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Badge, Card } from "@polisyos/atlas-ui";

const CANDIDATE_REASONING_LABEL = "Candidate reasoning";

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
  { glyph: GlyphName; label: string; color: string }
> = {
  question: {
    glyph: "evidence",
    label: "User question",
    color: "var(--color-chart-primary)",
  },
  interpretation: {
    glyph: "identifiability",
    label: "Interpreted query",
    color: "var(--color-chart-secondary)",
  },
  retrieval: {
    glyph: "provenance",
    label: "Data retrieved",
    color: "var(--color-chart-tertiary)",
  },
  analysis: {
    glyph: "counterfactual",
    label: "Causal analysis",
    color: "var(--color-confidence-medium)",
  },
  conclusion: {
    glyph: "evidence",
    label: "Conclusion",
    color: "var(--color-chart-primary)",
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
  const detailId = `reasoning-step-${step.id.replace(/[^a-zA-Z0-9_-]/g, "-")}-details`;

  return (
    <div className="flex gap-3">
      {/* Timeline rail */}
      <div className="flex flex-col items-center">
        <div
          className="flex size-8 shrink-0 items-center justify-center rounded-full border-2 text-sm"
          style={{ borderColor: config.color }}
        >
          <Glyph decorative name={config.glyph} size={16} />
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
            aria-controls={detailId}
            aria-expanded={isExpanded}
            aria-label={`${isExpanded ? "Hide" : "Show"} details for ${step.title}`}
            className="text-muted mt-1 text-xs underline decoration-dotted underline-offset-2 hover:text-inherit"
          >
            {isExpanded ? "Hide details" : "Show details"}
          </button>
        )}

        {isExpanded && hasDetail ? (
          <div id={detailId}>
            {step.detail ? (
              <div className="bg-surface border-line mt-2 rounded-xl border p-3 text-sm whitespace-pre-wrap">
                {step.detail}
              </div>
            ) : null}

            {step.metadata ? (
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
            ) : null}
          </div>
        ) : null}
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

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const expandableStepIds = steps
    .filter((step) => step.detail || step.metadata)
    .map((step) => step.id);
  const allExpanded =
    expandableStepIds.length > 0 &&
    expandableStepIds.every((id) => expanded.has(id));

  const expandAll = () => {
    setExpanded(new Set(expandableStepIds));
  };

  const collapseAll = () => {
    setExpanded(new Set());
  };

  const totalDuration = steps.reduce((sum, s) => sum + (s.durationMs ?? 0), 0);

  return (
    <Card
      className={cn(
        "space-y-4 border-dashed border-[var(--teal)]/45",
        className,
      )}
      data-authority-posture="candidate"
      data-testid="reasoning-chain"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">{title}</h3>
        <div className="flex items-center gap-3">
          <Badge kind="outline">{CANDIDATE_REASONING_LABEL}</Badge>
          {totalDuration > 0 && (
            <span className="text-muted text-xs">
              {t("shared.ui.reasoningChain.totalDuration", {
                duration: formatDuration(totalDuration),
              })}
            </span>
          )}
          {expandableStepIds.length > 0 ? (
            <button
              type="button"
              aria-expanded={allExpanded}
              aria-label={`${allExpanded ? "Collapse" : "Expand"} all reasoning details`}
              onClick={allExpanded ? collapseAll : expandAll}
              className="text-xs font-medium text-[var(--color-chart-primary)] hover:underline"
            >
              {allExpanded ? "Collapse all" : "Expand all"}
            </button>
          ) : null}
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
