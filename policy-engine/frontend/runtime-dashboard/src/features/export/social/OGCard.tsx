import { ShieldCheck } from "lucide-react";

import { cn } from "@/lib/utils";

import type { PublicShareSummary } from "./email-fixtures";

type OGCardProps = {
  summary: PublicShareSummary;
  className?: string;
};

const OG_BRAND_LABEL = "PolicyOS Runtime";
const OG_STATE_LABEL = "State";
const OG_TEMPORAL_SCOPE_LABEL = "Temporal scope";

export function OGCard({ summary, className }: OGCardProps) {
  const safeSummary = sanitizePublicShareSummary(summary);
  return (
    <article
      className={cn(
        "grid aspect-[1200/630] w-full max-w-[75rem] grid-rows-[auto_1fr_auto] gap-8 bg-[var(--paper)] p-12 text-[var(--ink)]",
        className,
      )}
      aria-label={`${safeSummary.kind} share preview for ${safeSummary.title}`}
      data-share-kind={safeSummary.kind}
    >
      <header className="flex items-center justify-between gap-8">
        <div>
          <p className="font-mono text-xs tracking-[0.22em] uppercase">
            {OG_BRAND_LABEL}
          </p>
          <p className="text-muted-foreground text-sm">
            {safeSummary.subtitle}
          </p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-[var(--line)] px-4 py-2 text-sm font-bold">
          <ShieldCheck className="size-4" aria-hidden="true" />
          {safeSummary.trustStatus}
        </span>
      </header>

      <main className="grid content-center gap-6">
        <p className="font-mono text-sm tracking-[0.18em] uppercase">
          {safeSummary.kind}
        </p>
        <h1 className="max-w-4xl text-6xl leading-tight font-extrabold">
          {safeSummary.title}
        </h1>
        {safeSummary.summary ? (
          <p className="text-muted-foreground max-w-3xl text-2xl leading-snug">
            {safeSummary.summary}
          </p>
        ) : null}
      </main>

      <footer className="grid grid-cols-[1fr_auto] items-end gap-8 border-t border-[var(--line)] pt-6">
        <dl className="grid grid-cols-3 gap-6">
          <div>
            <dt className="text-muted-foreground text-xs font-bold uppercase">
              {safeSummary.keyQuantity.label}
            </dt>
            <dd className="text-3xl font-extrabold tabular-nums">
              {safeSummary.keyQuantity.value}
              {safeSummary.keyQuantity.unit ? (
                <span className="text-muted-foreground ml-2 text-lg">
                  {safeSummary.keyQuantity.unit}
                </span>
              ) : null}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground text-xs font-bold uppercase">
              {OG_STATE_LABEL}
            </dt>
            <dd className="text-xl font-bold">{safeSummary.state}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground text-xs font-bold uppercase">
              {OG_TEMPORAL_SCOPE_LABEL}
            </dt>
            <dd className="font-mono text-sm">
              {formatTemporalScope(safeSummary.temporalScope)}
            </dd>
          </div>
        </dl>
        <p className="max-w-sm truncate text-right font-mono text-xs">
          {safeSummary.href}
        </p>
      </footer>
    </article>
  );
}

export function sanitizePublicShareSummary(
  summary: PublicShareSummary,
): PublicShareSummary {
  return {
    href: summary.href,
    keyQuantity: { ...summary.keyQuantity },
    kind: summary.kind,
    state: summary.state,
    subtitle: summary.subtitle,
    summary: summary.summary,
    temporalScope: { ...summary.temporalScope },
    title: summary.title,
    trustStatus: summary.trustStatus,
  };
}

export function formatTemporalScope(
  scope: PublicShareSummary["temporalScope"],
) {
  const parts = [
    scope.validAt ? `valid ${scope.validAt}` : null,
    scope.txAt ? `known ${scope.txAt}` : "known latest",
    scope.branch ? `branch ${scope.branch}` : null,
    scope.scenarioId ? `scenario ${scope.scenarioId}` : null,
  ].filter(Boolean);
  return parts.join("; ");
}
