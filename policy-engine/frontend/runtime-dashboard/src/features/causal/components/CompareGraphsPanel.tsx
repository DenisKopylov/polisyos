import { useMemo, useState } from "react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

import type { CausalNodeData, CausalEdgeData, LayoutAlgorithm } from "../types";
import { CausalGraphCanvas } from "./CausalGraphCanvas";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type CompareMode = "overlay" | "side_by_side" | "diff";

type GraphSnapshot = {
  id: string;
  label: string;
  nodes: CausalNodeData[];
  edges: CausalEdgeData[];
};

type CompareGraphsPanelProps = {
  graphA: GraphSnapshot;
  graphB: GraphSnapshot;
  layout?: LayoutAlgorithm;
  className?: string;
};

// ---------------------------------------------------------------------------
// Diff computation
// ---------------------------------------------------------------------------

type DiffResult = {
  addedNodes: string[];
  removedNodes: string[];
  addedEdges: string[];
  removedEdges: string[];
  changedEdges: Array<{
    id: string;
    field: string;
    from: string;
    to: string;
  }>;
};

function computeGraphDiff(a: GraphSnapshot, b: GraphSnapshot): DiffResult {
  const aNodeIds = new Set(a.nodes.map((n) => n.id));
  const bNodeIds = new Set(b.nodes.map((n) => n.id));
  const aEdgeIds = new Set(a.edges.map((e) => e.id));
  const bEdgeIds = new Set(b.edges.map((e) => e.id));

  const aEdgeMap = new Map(a.edges.map((e) => [e.id, e]));
  const bEdgeMap = new Map(b.edges.map((e) => [e.id, e]));

  const changedEdges: DiffResult["changedEdges"] = [];
  for (const id of aEdgeIds) {
    if (bEdgeIds.has(id)) {
      const ea = aEdgeMap.get(id)!;
      const eb = bEdgeMap.get(id)!;
      if (ea.status !== eb.status) {
        changedEdges.push({
          id,
          field: "status",
          from: ea.status,
          to: eb.status,
        });
      }
      if (ea.estimate !== eb.estimate) {
        changedEdges.push({
          id,
          field: "estimate",
          from: String(ea.estimate ?? "—"),
          to: String(eb.estimate ?? "—"),
        });
      }
    }
  }

  return {
    addedNodes: [...bNodeIds].filter((id) => !aNodeIds.has(id)),
    removedNodes: [...aNodeIds].filter((id) => !bNodeIds.has(id)),
    addedEdges: [...bEdgeIds].filter((id) => !aEdgeIds.has(id)),
    removedEdges: [...aEdgeIds].filter((id) => !bEdgeIds.has(id)),
    changedEdges,
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CompareGraphsPanel({
  graphA,
  graphB,
  layout: initialLayout = "hierarchical",
  className,
}: CompareGraphsPanelProps) {
  const { t } = useI18n();
  const [mode, setMode] = useState<CompareMode>("side_by_side");
  const [layout] = useState<LayoutAlgorithm>(initialLayout);

  const diff = useMemo(
    () => computeGraphDiff(graphA, graphB),
    [graphA, graphB],
  );

  const totalChanges =
    diff.addedNodes.length +
    diff.removedNodes.length +
    diff.addedEdges.length +
    diff.removedEdges.length +
    diff.changedEdges.length;

  return (
    <div className={cn("space-y-4", className)}>
      {/* Controls */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">
          {t("causal.compare.compareLabel")} {graphA.label}{" "}
          {t("causal.compare.versus")} {graphB.label}
        </h3>
        <div className="bg-surface flex gap-1 rounded-lg p-0.5">
          {(["side_by_side", "overlay", "diff"] as const).map((m) => (
            <button
              key={m}
              type="button"
              className={cn(
                "rounded-md px-2.5 py-1 text-xs transition-colors",
                mode === m
                  ? "bg-paper text-foreground shadow-sm"
                  : "text-muted hover:text-foreground",
              )}
              onClick={() => setMode(m)}
            >
              {m === "side_by_side"
                ? t("causal.compare.sideBySide")
                : m === "overlay"
                  ? t("causal.compare.overlay")
                  : t("causal.compare.diff")}
            </button>
          ))}
        </div>
      </div>

      {/* Diff summary */}
      {totalChanges > 0 && (
        <div className="bg-surface border-line flex flex-wrap gap-3 rounded-lg border p-2 text-xs">
          {diff.addedNodes.length > 0 && (
            <span className="text-[var(--chart-success)]">
              +{t("causal.compare.nodes", { count: diff.addedNodes.length })}
            </span>
          )}
          {diff.removedNodes.length > 0 && (
            <span className="text-[var(--chart-alert)]">
              -{t("causal.compare.nodes", { count: diff.removedNodes.length })}
            </span>
          )}
          {diff.addedEdges.length > 0 && (
            <span className="text-[var(--chart-success)]">
              +{t("causal.compare.edges", { count: diff.addedEdges.length })}
            </span>
          )}
          {diff.removedEdges.length > 0 && (
            <span className="text-[var(--chart-alert)]">
              -{t("causal.compare.edges", { count: diff.removedEdges.length })}
            </span>
          )}
          {diff.changedEdges.length > 0 && (
            <span className="text-[var(--chart-warning)]">
              ~
              {t("causal.compare.modified", {
                count: diff.changedEdges.length,
              })}
            </span>
          )}
        </div>
      )}

      {/* Visualization */}
      {mode === "side_by_side" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="border-line min-h-[300px] rounded-xl border">
            <p className="border-line border-b p-2 text-xs font-semibold">
              {graphA.label}
            </p>
            <CausalGraphCanvas
              nodes={graphA.nodes}
              edges={graphA.edges}
              className="min-h-[260px] border-0"
              layoutAlgorithm={layout}
              showControls={false}
            />
          </div>
          <div className="border-line min-h-[300px] rounded-xl border">
            <p className="border-line border-b p-2 text-xs font-semibold">
              {graphB.label}
            </p>
            <CausalGraphCanvas
              nodes={graphB.nodes}
              edges={graphB.edges}
              className="min-h-[260px] border-0"
              layoutAlgorithm={layout}
              showControls={false}
            />
          </div>
        </div>
      )}

      {mode === "overlay" && (
        <div className="border-line relative min-h-[400px] rounded-xl border">
          <div className="absolute inset-0 opacity-60">
            <CausalGraphCanvas
              nodes={graphA.nodes}
              edges={graphA.edges}
              className="min-h-[400px] border-0"
              layoutAlgorithm={layout}
              showControls={false}
            />
          </div>
          <div
            className="absolute inset-0 opacity-60"
            style={{ mixBlendMode: "multiply" }}
          >
            <CausalGraphCanvas
              nodes={graphB.nodes}
              edges={graphB.edges}
              className="min-h-[400px] border-0"
              layoutAlgorithm={layout}
              showControls={false}
            />
          </div>
          <div className="absolute bottom-2 left-2 flex gap-3 text-xs">
            <span className="flex items-center gap-1">
              <span className="inline-block size-2.5 rounded-full bg-[var(--chart-primary)]" />
              {graphA.label}
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block size-2.5 rounded-full bg-[var(--chart-secondary)]" />
              {graphB.label}
            </span>
          </div>
        </div>
      )}

      {mode === "diff" && (
        <div className="space-y-3">
          {totalChanges === 0 ? (
            <p className="text-muted p-4 text-center text-sm">
              {t("causal.compare.identical")}
            </p>
          ) : (
            <div className="space-y-2">
              {diff.changedEdges.map((c) => (
                <div
                  key={`${c.id}-${c.field}`}
                  className="border-line rounded-lg border p-2 text-xs"
                  style={{
                    borderLeftWidth: 3,
                    borderLeftColor: "var(--chart-warning)",
                  }}
                >
                  <span className="font-semibold">
                    {t("causal.compare.edge")} {c.id}
                  </span>
                  <span className="text-muted"> · {c.field}: </span>
                  <span className="text-[var(--chart-alert)] line-through">
                    {c.from}
                  </span>
                  {" → "}
                  <span className="text-[var(--chart-success)]">{c.to}</span>
                </div>
              ))}
              {diff.addedNodes.map((id) => (
                <div
                  key={id}
                  className="border-line rounded-lg border p-2 text-xs"
                  style={{
                    borderLeftWidth: 3,
                    borderLeftColor: "var(--chart-success)",
                  }}
                >
                  <span className="text-[var(--chart-success)]">+</span>{" "}
                  {t("causal.compare.node")}{" "}
                  <span className="font-semibold">{id}</span>
                </div>
              ))}
              {diff.removedNodes.map((id) => (
                <div
                  key={id}
                  className="border-line rounded-lg border p-2 text-xs"
                  style={{
                    borderLeftWidth: 3,
                    borderLeftColor: "var(--chart-alert)",
                  }}
                >
                  <span className="text-[var(--chart-alert)]">-</span>{" "}
                  {t("causal.compare.node")}{" "}
                  <span className="font-semibold">{id}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
