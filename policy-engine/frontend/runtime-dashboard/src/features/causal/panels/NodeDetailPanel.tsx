import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";
import { Card } from "@/shared/ui/primitives";
import { ConfidenceGauge, GradedErrorBar } from "@/shared/charts";

import type { CausalNodeData, CausalEdgeData } from "../types";
import { NODE_COLORS } from "../types";

type NodeDetailPanelProps = {
  node: CausalNodeData;
  edges: CausalEdgeData[];
  onClose: () => void;
  className?: string;
};

export function NodeDetailPanel({
  node,
  edges,
  onClose,
  className,
}: NodeDetailPanelProps) {
  const { t } = useI18n();
  const incoming = edges.filter((e) => e.target === node.id);
  const outgoing = edges.filter((e) => e.source === node.id);

  return (
    <Card className={cn("w-80 space-y-4 overflow-y-auto", className)}>
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold">{node.label}</h3>
          <span
            className="inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-xs font-semibold capitalize"
            style={{
              color: NODE_COLORS[node.kind],
              background: `color-mix(in srgb, ${NODE_COLORS[node.kind]} 12%, transparent)`,
            }}
          >
            {node.kind}
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

      {/* Description */}
      {node.description && (
        <p className="text-muted text-sm">{node.description}</p>
      )}

      {/* Effect estimate */}
      {node.estimate != null && node.ci && (
        <div className="space-y-2">
          <p className="text-muted text-xs font-semibold uppercase">
            {t("causal.nodeDetail.effectEstimate")}
          </p>
          <div className="flex items-center gap-4">
            <ConfidenceGauge
              value={Math.min(Math.abs(node.estimate), 1)}
              label={t("causal.nodeDetail.effect")}
              size={64}
            />
            <div>
              <p className="font-mono text-lg font-bold">
                {node.estimate >= 0 ? "+" : ""}
                {node.estimate.toFixed(4)}
              </p>
              <p className="text-muted text-xs">
                {t("causal.nodeDetail.confidenceInterval", {
                  level: node.ci.level,
                  lower: node.ci.lower.toFixed(4),
                  upper: node.ci.upper.toFixed(4),
                })}
              </p>
            </div>
          </div>
          <GradedErrorBar
            estimate={node.estimate}
            bands={[
              {
                level: 0.95,
                lower: node.ci.lower,
                upper: node.ci.upper,
              },
              {
                level: 0.8,
                lower: node.ci.lower * 1.1,
                upper: node.ci.upper * 1.1,
              },
              {
                level: 0.5,
                lower: node.ci.lower * 1.3,
                upper: node.ci.upper * 1.3,
              },
            ]}
          />
        </div>
      )}

      {/* Data availability */}
      <div className="flex items-center gap-2 text-sm">
        <span
          className={cn(
            "size-2 rounded-full",
            node.dataAvailable !== false
              ? "bg-[var(--chart-success)]"
              : "bg-[var(--chart-warning)]",
          )}
        />
        <span>
          {node.dataAvailable !== false
            ? t("causal.nodeDetail.dataAvailable")
            : t("causal.nodeDetail.dataUnavailable")}
        </span>
      </div>

      {/* Evidence count */}
      {node.evidenceCount != null && (
        <p className="text-muted text-sm">
          {t("causal.nodeDetail.evidenceSources", {
            count: node.evidenceCount,
          })}
        </p>
      )}

      {/* Connections */}
      <div>
        <p className="text-muted mb-1 text-xs font-semibold uppercase">
          {t("causal.nodeDetail.connections")}
        </p>
        {incoming.length > 0 && (
          <div className="mb-2">
            <p className="text-muted text-xs">
              {t("causal.nodeDetail.incoming", { count: incoming.length })}
            </p>
            <ul className="mt-0.5 space-y-0.5">
              {incoming.map((e) => (
                <li key={e.id} className="flex items-center gap-1.5 text-sm">
                  <span className="text-muted">{"\u2190"}</span>
                  <span className="font-medium">{e.source}</span>
                  <span className="text-muted text-xs capitalize">
                    ({e.status})
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {outgoing.length > 0 && (
          <div>
            <p className="text-muted text-xs">
              {t("causal.nodeDetail.outgoing", { count: outgoing.length })}
            </p>
            <ul className="mt-0.5 space-y-0.5">
              {outgoing.map((e) => (
                <li key={e.id} className="flex items-center gap-1.5 text-sm">
                  <span className="text-muted">{"\u2192"}</span>
                  <span className="font-medium">{e.target}</span>
                  <span className="text-muted text-xs capitalize">
                    ({e.status})
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Metadata */}
      {node.meta && Object.keys(node.meta).length > 0 && (
        <div>
          <p className="text-muted mb-1 text-xs font-semibold uppercase">
            {t("causal.nodeDetail.metadata")}
          </p>
          <div className="space-y-0.5">
            {Object.entries(node.meta).map(([k, v]) => (
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
