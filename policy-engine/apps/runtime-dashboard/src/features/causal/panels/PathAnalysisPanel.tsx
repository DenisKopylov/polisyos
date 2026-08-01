import { useMemo, type CSSProperties } from "react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import { Card } from "@polisyos/atlas-ui";

import type { CausalNodeData, CausalEdgeData } from "../types";
import { NODE_COLORS } from "../types";

export type CausalPath = {
  id: string;
  label: string;
  type: "direct" | "indirect" | "backdoor" | "frontdoor";
  nodeIds: string[];
  edgeIds: string[];
  totalEffect?: number;
  blocked?: boolean;
};

type PathAnalysisPanelProps = {
  nodes: CausalNodeData[];
  edges: CausalEdgeData[];
  paths: CausalPath[];
  selectedPathId?: string | null;
  onPathSelect?: (pathId: string | null) => void;
  onClose: () => void;
  className?: string;
};

const PATH_TYPE_CONFIG: Record<CausalPath["type"], { color: string }> = {
  direct: { color: "var(--chart-primary)" },
  indirect: { color: "var(--chart-secondary)" },
  backdoor: { color: "var(--chart-alert)" },
  frontdoor: { color: "var(--chart-success)" },
};

function sumPathEffects(
  paths: CausalPath[],
  type: CausalPath["type"],
): number | undefined {
  const matching = paths.filter((path) => path.type === type);
  if (
    matching.length === 0 ||
    matching.some((path) => path.totalEffect == null)
  ) {
    return undefined;
  }
  return matching.reduce((sum, path) => sum + (path.totalEffect as number), 0);
}

export function PathAnalysisPanel({
  nodes,
  edges,
  paths,
  selectedPathId,
  onPathSelect,
  onClose,
  className,
}: PathAnalysisPanelProps) {
  const { t } = useI18n();
  const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const edgeMap = useMemo(() => new Map(edges.map((e) => [e.id, e])), [edges]);
  const pathTypeLabels: Record<CausalPath["type"], string> = {
    direct: t("causal.pathAnalysis.direct"),
    indirect: t("causal.pathAnalysis.indirect"),
    backdoor: t("causal.pathAnalysis.backdoor"),
    frontdoor: t("causal.pathAnalysis.frontdoor"),
  };

  const directTotal = sumPathEffects(paths, "direct");
  const indirectTotal = sumPathEffects(paths, "indirect");
  const total =
    directTotal != null && indirectTotal != null
      ? directTotal + indirectTotal
      : undefined;
  const formatEffect = (value: number | undefined) =>
    value == null ? t("common.unknown") : value.toFixed(4);

  return (
    <Card className={cn("w-80 space-y-4 overflow-y-auto", className)}>
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-lg font-semibold">
          {t("causal.pathAnalysis.title")}
        </h3>
        <button
          type="button"
          onClick={onClose}
          className="text-muted text-lg leading-none hover:text-inherit"
          aria-label={t("common.close")}
        >
          {"\u00D7"}
        </button>
      </div>

      {/* Effect decomposition */}
      <div className="border-line rounded-xl border p-3">
        <p className="text-muted mb-2 text-xs font-semibold uppercase">
          {t("causal.pathAnalysis.effectDecomposition")}
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <p className="text-muted text-xs">
              {t("causal.pathAnalysis.direct")}
            </p>
            <p className="font-mono text-lg font-bold text-[var(--chart-primary)]">
              {formatEffect(directTotal)}
            </p>
          </div>
          <div>
            <p className="text-muted text-xs">
              {t("causal.pathAnalysis.indirect")}
            </p>
            <p className="font-mono text-lg font-bold text-[var(--chart-secondary)]">
              {formatEffect(indirectTotal)}
            </p>
          </div>
          <div className="col-span-2">
            <p className="text-muted text-xs">
              {t("causal.pathAnalysis.total")}
            </p>
            <p className="font-mono text-lg font-bold">
              {formatEffect(total)}
            </p>
          </div>
        </div>
      </div>

      {/* Path list */}
      <div className="space-y-2">
        <p className="text-muted text-xs font-semibold uppercase">
          {t("causal.pathAnalysis.pathCount", { count: paths.length })}
        </p>

        {paths.map((path) => {
          const config = PATH_TYPE_CONFIG[path.type];
          const isSelected = selectedPathId === path.id;

          return (
            <button
              key={path.id}
              type="button"
              className={cn(
                "border-line w-full rounded-xl border p-3 text-start transition-colors",
                isSelected ? "ring-2" : "hover:bg-surface/80",
              )}
              style={
                isSelected
                  ? ({
                      "--tw-ring-color": config.color,
                    } as CSSProperties)
                  : undefined
              }
              onClick={() => onPathSelect?.(isSelected ? null : path.id)}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span
                    className="inline-block size-2 rounded-full"
                    style={{ background: config.color }}
                  />
                  <span className="text-xs font-semibold">
                    {pathTypeLabels[path.type]}
                  </span>
                  {path.blocked && (
                    <span className="text-muted text-xs">
                      {t("causal.pathAnalysis.blocked")}
                    </span>
                  )}
                </div>
                {path.totalEffect != null && (
                  <span
                    className="font-mono text-xs font-bold"
                    style={{ color: config.color }}
                  >
                    {path.totalEffect >= 0 ? "+" : ""}
                    {path.totalEffect.toFixed(4)}
                  </span>
                )}
              </div>

              {/* Node chain */}
              <div className="mt-1.5 flex flex-wrap items-center gap-1 text-xs">
                {path.nodeIds.map((nid, i) => {
                  const node = nodeMap.get(nid);
                  return (
                    <span key={nid} className="flex items-center gap-1">
                      {i > 0 && <span className="text-muted">{"\u2192"}</span>}
                      <span
                        className="font-medium"
                        style={{
                          color: node ? NODE_COLORS[node.kind] : undefined,
                        }}
                      >
                        {node?.label ?? nid}
                      </span>
                    </span>
                  );
                })}
              </div>
            </button>
          );
        })}
      </div>
    </Card>
  );
}
