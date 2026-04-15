import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { Badge, Card } from "@/shared/ui/primitives";
import type { BadgeKind } from "@/shared/ui/Badge";

export type BlockingType = string;

export type SuggestedExperiment = {
  id: string;
  description: string;
  rationale?: string;
  feasibility?: "low" | "medium" | "high";
};

type NegativeCertificateCardProps = {
  blockingType: BlockingType;
  reason: string;
  detail?: ReactNode;
  assumptions?: string[];
  suggestedExperiments?: SuggestedExperiment[];
  className?: string;
};

const BLOCKING_LABELS: Record<string, { label: string; kind: BadgeKind }> = {
  identification_failure: { label: "Not Identified", kind: "fail" },
  data_insufficient: { label: "Insufficient Data", kind: "fail" },
  assumption_violation: { label: "Assumption Violated", kind: "fail" },
  bounds_only: { label: "Bounds Only", kind: "warn" },
  transport_failure: { label: "Transport Failed", kind: "warn" },
};

const FEASIBILITY_KIND: Record<string, BadgeKind> = {
  high: "ok",
  medium: "warn",
  low: "fail",
};

export function NegativeCertificateCard({
  blockingType,
  reason,
  detail,
  assumptions = [],
  suggestedExperiments = [],
  className,
}: NegativeCertificateCardProps) {
  const blocking = BLOCKING_LABELS[blockingType] ?? {
    label: blockingType,
    kind: "fail" as const,
  };

  return (
    <Card
      className={cn(
        "space-y-4 border-[var(--color-status-rejected)]/20",
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h3 className="text-lg font-semibold">
            Why a precise answer is unavailable
          </h3>
          <p className="text-muted text-sm leading-relaxed">{reason}</p>
        </div>
        <Badge kind={blocking.kind}>{blocking.label}</Badge>
      </div>

      {detail && (
        <div className="border-line bg-surface/70 rounded-2xl border p-3 text-sm">
          {detail}
        </div>
      )}

      {assumptions.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
            Violated assumptions
          </p>
          <ul className="space-y-1 text-sm">
            {assumptions.map((a) => (
              <li key={a} className="flex items-start gap-2">
                <span className="mt-1 text-[var(--color-status-rejected)]">
                  {"\u2717"}
                </span>
                <span>{a}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {suggestedExperiments.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
            Suggested experiments
          </p>
          <div className="space-y-2">
            {suggestedExperiments.map((exp) => (
              <article
                key={exp.id}
                className="border-line bg-surface/70 rounded-2xl border p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium">{exp.description}</p>
                  {exp.feasibility && (
                    <Badge kind={FEASIBILITY_KIND[exp.feasibility] ?? "neutral"}>
                      {exp.feasibility}
                    </Badge>
                  )}
                </div>
                {exp.rationale && (
                  <p className="text-muted mt-1 text-xs">{exp.rationale}</p>
                )}
              </article>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
