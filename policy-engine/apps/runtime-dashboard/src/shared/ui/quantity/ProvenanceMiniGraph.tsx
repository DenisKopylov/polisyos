import { GitBranch } from "lucide-react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

import {
  normalizeKind,
  summarizeLineageGraph,
  type ProvenanceSummaryKind,
} from "./lineage-summary";
import type {
  LineageCompactSummaryItem,
  LineageGraphView,
  LineageRef,
} from "./quantity.types";

type ProvenanceMiniGraphProps = {
  lineage?: LineageGraphView | null;
  fallback?: LineageRef;
  maxVisibleNodes?: number;
  className?: string;
};

const KIND_CLASS: Record<ProvenanceSummaryKind, string> = {
  source:
    "border-[color-mix(in_srgb,var(--color-status-approved)_30%,transparent)]",
  transform: "border-[color-mix(in_srgb,var(--color-info)_34%,transparent)]",
  model:
    "border-[color-mix(in_srgb,var(--color-status-pending)_38%,transparent)]",
  agent: "border-[color-mix(in_srgb,var(--color-accent)_38%,transparent)]",
  result:
    "border-[color-mix(in_srgb,var(--color-status-approved)_42%,transparent)]",
  artifact: "border-border",
  unknown: "border-border",
};

export function ProvenanceMiniGraph({
  lineage,
  fallback,
  maxVisibleNodes,
  className,
}: ProvenanceMiniGraphProps) {
  const { t } = useI18n();
  const syntheticLineage =
    lineage ??
    (fallback
      ? {
          id: fallback.id,
          status: fallback.status,
          freshness: fallback.freshness,
          compact_summary:
            fallback.compact_summary ?? summaryMapToCompact(fallback),
          exports: {
            openlineage: "",
            prov: "",
          },
        }
      : null);
  const summary = summarizeLineageGraph(syntheticLineage, { maxVisibleNodes });

  if (summary.nodes.length === /* policyos-quantity: layout */ 0) {
    return (
      <div
        className={cn(
          "border-border bg-surface/70 text-muted flex min-h-20 items-center gap-2 rounded-md border p-3 text-sm",
          className,
        )}
      >
        <GitBranch className="size-4" aria-hidden="true" />
        <span>{t("shared.ui.quantity.miniGraph.empty")}</span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "border-border bg-surface/80 w-full max-w-[320px] rounded-md border p-3",
        className,
      )}
      aria-label={t("shared.ui.quantity.miniGraph.ariaLabel")}
      role="group"
    >
      <div className="grid grid-cols-[1fr_auto] items-stretch gap-1.5">
        {summary.nodes.map((node, index) => (
          <div key={node.id} className="contents">
            <div
              className={cn(
                "min-w-0 rounded-md border bg-white/80 px-2 py-1.5",
                KIND_CLASS[node.kind],
              )}
            >
              <div className="text-muted truncate text-[10px] leading-4 font-semibold tracking-wide uppercase">
                {t(`shared.ui.quantity.kind.${node.kind}`)}
              </div>
              <div className="text-foreground truncate text-xs leading-4 font-medium">
                {node.label}
              </div>
            </div>
            <div className="flex w-5 items-center justify-center">
              {index <
              summary.nodes.length - /* policyos-quantity: layout */ 1 ? (
                <span
                  aria-hidden="true"
                  className="bg-border h-full min-h-9 w-px"
                />
              ) : null}
            </div>
          </div>
        ))}
      </div>
      {summary.hiddenTotal > /* policyos-quantity: layout */ 0 ? (
        <div className="text-muted mt-2 flex flex-wrap gap-1 text-[11px]">
          {Object.entries(summary.hiddenByKind).map(([kind, count]) =>
            count ? (
              <span key={kind} className="bg-muted/40 rounded px-1.5 py-0.5">
                {t("shared.ui.quantity.miniGraph.hidden", {
                  count,
                  kind: t(
                    `shared.ui.quantity.kind.${kind as ProvenanceSummaryKind}`,
                  ),
                })}
              </span>
            ) : null,
          )}
        </div>
      ) : null}
    </div>
  );
}

function summaryMapToCompact(lineage: LineageRef): LineageCompactSummaryItem[] {
  return Object.entries(lineage.summary ?? {}).map(([kind, label]) => ({
    kind: normalizeKind(kind),
    label,
  }));
}
