import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/LocaleProvider";

import type { CausalNodeData } from "../types";
import { NODE_COLORS } from "../types";

type AdjustmentSetHighlightProps = {
  nodes: CausalNodeData[];
  adjustmentSet: string[];
  setType?: "backdoor" | "frontdoor" | "iv";
  className?: string;
};

export function AdjustmentSetHighlight({
  nodes,
  adjustmentSet,
  setType = "backdoor",
  className,
}: AdjustmentSetHighlightProps) {
  const { t } = useI18n();
  const setIds = new Set(adjustmentSet);
  const inSet = nodes.filter((n) => setIds.has(n.id));
  const setTypeLabels: Record<
    NonNullable<AdjustmentSetHighlightProps["setType"]>,
    string
  > = {
    backdoor: t("causal.adjustmentSet.backdoor"),
    frontdoor: t("causal.adjustmentSet.frontdoor"),
    iv: t("causal.adjustmentSet.iv"),
  };

  return (
    <div
      className={cn(
        "bg-surface/90 border-line rounded-xl border p-3 text-xs backdrop-blur-sm",
        className,
      )}
    >
      <p className="mb-2 font-semibold">
        {setTypeLabels[setType] ?? t("causal.adjustmentSet.title")}
      </p>

      {inSet.length === 0 ? (
        <p className="text-muted">{t("causal.adjustmentSet.empty")}</p>
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
        {t("causal.adjustmentSet.conditioningSummary", {
          count: inSet.length,
        })}
      </p>
    </div>
  );
}
