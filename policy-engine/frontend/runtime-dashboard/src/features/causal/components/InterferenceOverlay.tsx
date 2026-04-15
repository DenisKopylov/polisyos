import { cn } from "@/lib/utils";

import type { CausalNodeData, CausalEdgeData } from "../types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type InterferencePattern = {
  sourceNodeId: string;
  affectedNodeIds: string[];
  mechanism: "spillover" | "peer_effect" | "general_equilibrium" | "network";
  strength: number;
  description?: string;
};

type InterferenceOverlayProps = {
  nodes: CausalNodeData[];
  edges: CausalEdgeData[];
  patterns: InterferencePattern[];
  className?: string;
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MECHANISM_COLOR: Record<InterferencePattern["mechanism"], string> = {
  spillover: "var(--chart-warning)",
  peer_effect: "var(--chart-secondary)",
  general_equilibrium: "var(--chart-alert)",
  network: "var(--chart-tertiary)",
};

const MECHANISM_LABEL: Record<InterferencePattern["mechanism"], string> = {
  spillover: "Spillover",
  peer_effect: "Peer effect",
  general_equilibrium: "General equilibrium",
  network: "Network effect",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function InterferenceOverlay({
  nodes,
  patterns,
  className,
}: InterferenceOverlayProps) {
  if (patterns.length === 0) {
    return (
      <div
        className={cn(
          "bg-surface/90 border-line rounded-xl border p-3 text-xs backdrop-blur-sm",
          className,
        )}
      >
        <p className="mb-1 font-semibold">Interference Pattern</p>
        <p className="text-muted">No interference patterns detected.</p>
      </div>
    );
  }

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  return (
    <div
      className={cn(
        "bg-surface/90 border-line rounded-xl border p-3 text-xs backdrop-blur-sm",
        className,
      )}
    >
      <p className="mb-2 font-semibold">
        Interference Patterns{" "}
        <span className="text-muted font-normal">({patterns.length})</span>
      </p>

      {/* Legend */}
      <div className="mb-3 flex flex-wrap gap-3">
        {(Object.keys(MECHANISM_LABEL) as InterferencePattern["mechanism"][])
          .filter((m) => patterns.some((p) => p.mechanism === m))
          .map((mechanism) => (
            <div key={mechanism} className="flex items-center gap-1.5">
              <span
                className="inline-block size-2.5 rounded-full"
                style={{ background: MECHANISM_COLOR[mechanism] }}
              />
              <span>{MECHANISM_LABEL[mechanism]}</span>
            </div>
          ))}
      </div>

      {/* Pattern list */}
      <div className="space-y-2">
        {patterns.map((pattern, i) => {
          const sourceNode = nodeMap.get(pattern.sourceNodeId);
          const affected = pattern.affectedNodeIds
            .map((id) => nodeMap.get(id)?.label ?? id)
            .join(", ");

          return (
            <div
              key={i}
              className="border-line rounded-lg border p-2"
              style={{
                borderLeftWidth: 3,
                borderLeftColor: MECHANISM_COLOR[pattern.mechanism],
              }}
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold">
                  {sourceNode?.label ?? pattern.sourceNodeId}
                </span>
                <span
                  className="rounded-md px-1.5 py-0.5 text-[10px] font-bold"
                  style={{
                    background: MECHANISM_COLOR[pattern.mechanism],
                    color: "var(--paper)",
                  }}
                >
                  {MECHANISM_LABEL[pattern.mechanism]}
                </span>
              </div>
              <p className="text-muted mt-0.5">
                Affects: {affected}
                {" · "}
                Strength: {(pattern.strength * 100).toFixed(0)}%
              </p>
              {pattern.description && (
                <p className="text-muted mt-0.5 italic">
                  {pattern.description}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
