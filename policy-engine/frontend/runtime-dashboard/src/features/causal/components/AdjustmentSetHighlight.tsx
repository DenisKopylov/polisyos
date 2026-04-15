import { cn } from "@/lib/utils";

import type { CausalNodeData } from "../types";
import { NODE_COLORS } from "../types";

type AdjustmentSetHighlightProps = {
  nodes: CausalNodeData[];
  adjustmentSet: string[];
  setType?: "backdoor" | "frontdoor" | "iv";
  className?: string;
};

const SET_TYPE_LABELS: Record<string, string> = {
  backdoor: "Backdoor adjustment set",
  frontdoor: "Frontdoor adjustment set",
  iv: "Instrumental variable set",
};

export function AdjustmentSetHighlight({
  nodes,
  adjustmentSet,
  setType = "backdoor",
  className,
}: AdjustmentSetHighlightProps) {
  const setIds = new Set(adjustmentSet);
  const inSet = nodes.filter((n) => setIds.has(n.id));

  return (
    <div
      className={cn(
        "bg-surface/90 border-line rounded-xl border p-3 text-xs backdrop-blur-sm",
        className,
      )}
    >
      <p className="mb-2 font-semibold">
        {SET_TYPE_LABELS[setType] ?? "Adjustment set"}
      </p>

      {inSet.length === 0 ? (
        <p className="text-muted">No adjustment set selected.</p>
      ) : (
        <div className="space-y-1">
          {inSet.map((node) => (
            <div key={node.id} className="flex items-center gap-2">
              <span
                className="inline-block size-2.5 rounded-sm"
                style={{ background: NODE_COLORS[node.kind] }}
              />
              <span className="font-medium">{node.label}</span>
              <span className="text-muted capitalize">({node.kind})</span>
            </div>
          ))}
        </div>
      )}

      <p className="text-muted mt-2">
        Conditioning on {inSet.length} variable{inSet.length !== 1 ? "s" : ""}{" "}
        blocks all non-causal paths.
      </p>
    </div>
  );
}
