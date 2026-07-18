import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import { Card } from "@polisyos/atlas-ui";
import { GradedErrorBar } from "@/shared/charts";
import { MethodologyBadge } from "@/shared/ui/compounds";

import type { CausalEdgeData } from "../types";

type EdgeDetailPanelProps = {
  edge: CausalEdgeData;
  onClose: () => void;
  className?: string;
};

export function EdgeDetailPanel({
  edge,
  onClose,
  className,
}: EdgeDetailPanelProps) {
  const { t } = useI18n();
  const statusConfig: Record<string, { label: string; color: string }> = {
    identified: {
      color: "var(--chart-primary)",
      label: t("causal.edgeStatus.identified"),
    },
    unidentified: {
      color: "var(--chart-alert)",
      label: t("causal.edgeStatus.unidentified"),
    },
    bounds_only: {
      color: "var(--color-confidence-medium)",
      label: t("causal.edgeStatus.boundsOnly"),
    },
  };
  const status = statusConfig[edge.status] ?? statusConfig.identified;

  return (
    <Card className={cn("w-80 space-y-4 overflow-y-auto", className)}>
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold">
            {edge.source} {"->"} {edge.target}
          </h3>
          <span
            className="inline-flex items-center rounded-lg px-2 py-0.5 text-xs font-semibold"
            style={{
              color: status.color,
              background: `color-mix(in srgb, ${status.color} 12%, transparent)`,
            }}
          >
            {status.label}
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-muted text-lg leading-none hover:text-inherit"
          aria-label={t("common.close")}
        >
          {"\u00D7"}
        </button>
      </div>

      {/* Effect estimate */}
      {edge.estimate != null && (
        <div className="space-y-2">
          <p className="text-muted text-xs font-semibold uppercase">
            {t("causal.edgeDetail.effectEstimate")}
          </p>
          <p className="font-mono text-2xl font-bold">
            {edge.estimate >= 0 ? "+" : ""}
            {edge.estimate.toFixed(4)}
          </p>
          {edge.ci && (
            <>
              <p className="text-muted text-xs">
                {t("causal.edgeDetail.confidenceInterval", {
                  level: edge.ci.level,
                  lower: edge.ci.lower.toFixed(4),
                  upper: edge.ci.upper.toFixed(4),
                })}
              </p>
              <GradedErrorBar
                estimate={edge.estimate}
                bands={[
                  {
                    level: 0.95,
                    lower: edge.ci.lower,
                    upper: edge.ci.upper,
                  },
                  {
                    level: 0.8,
                    lower: edge.ci.lower * 1.1,
                    upper: edge.ci.upper * 1.1,
                  },
                  {
                    level: 0.5,
                    lower: edge.ci.lower * 1.3,
                    upper: edge.ci.upper * 1.3,
                  },
                ]}
              />
            </>
          )}
        </div>
      )}

      {/* Methodology */}
      {edge.methodology && (
        <div>
          <p className="text-muted mb-1.5 text-xs font-semibold uppercase">
            {t("causal.edgeDetail.methodology")}
          </p>
          <MethodologyBadge methodology={edge.methodology} />
        </div>
      )}

      {/* Transport flag */}
      <div className="flex items-center gap-2 text-sm">
        <span
          className={cn(
            "size-2 rounded-full",
            edge.transportable
              ? "bg-[var(--chart-secondary)]"
              : "bg-[var(--chart-neutral)]",
          )}
        />
        <span>
          {edge.transportable
            ? t("causal.edgeDetail.transportable")
            : t("causal.edgeDetail.notTransportable")}
        </span>
      </div>

      {/* Literature support */}
      {edge.literatureCount != null && (
        <p className="text-muted text-sm">
          {t("causal.edgeDetail.literatureSources", {
            count: edge.literatureCount,
          })}
        </p>
      )}

      {/* Metadata */}
      {edge.meta && Object.keys(edge.meta).length > 0 && (
        <div>
          <p className="text-muted mb-1 text-xs font-semibold uppercase">
            {t("causal.edgeDetail.metadata")}
          </p>
          <div className="space-y-0.5">
            {Object.entries(edge.meta).map(([k, v]) => (
              <div key={k} className="flex justify-between text-sm">
                <span className="text-muted">{k}</span>
                <span className="font-medium">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
