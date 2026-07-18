import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  HelpCircle,
} from "lucide-react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Badge } from "@polisyos/atlas-ui";

import { saliencePercent, significanceTone, topDeltas } from "./compare-math";
import type { DeltaQuantity } from "./compare-types";

type CausalDeltaStripProps = {
  deltas: DeltaQuantity[];
  activeMetricId?: string | null;
  onSelectMetric?: (metricId: string) => void;
};

export function CausalDeltaStrip({
  activeMetricId,
  deltas,
  onSelectMetric,
}: CausalDeltaStripProps) {
  const { t } = useI18n();
  const visible = topDeltas(deltas, 7);
  return (
    <nav
      className="border-line bg-surface/70 rounded-[var(--radius-panel)] border p-2"
      aria-label={t("pages.runs.policyDiff.rankedDeltasLabel")}
    >
      <p className="text-muted px-2 pb-2 text-center text-[11px] font-semibold uppercase">
        {t("pages.runs.policyDiff.causalDeltas")}
      </p>
      <ol className="space-y-2">
        {visible.map((delta) => {
          const Icon = iconFor(delta.significance);
          const active = activeMetricId === delta.metric_id;
          return (
            <li key={delta.metric_id}>
              <button
                type="button"
                className={[
                  "border-line focus-visible:ring-ring w-full rounded-lg border px-2 py-2 text-left transition-colors focus-visible:ring-2 focus-visible:outline-none",
                  active ? "bg-accent/15" : "hover:bg-muted/30",
                ].join(" ")}
                onClick={() => onSelectMetric?.(delta.metric_id)}
                aria-current={active ? "true" : undefined}
              >
                <div className="flex items-center justify-between gap-2">
                  <Icon className="size-4 shrink-0" aria-hidden="true" />
                  <Badge
                    kind={significanceTone(delta.significance)}
                    className="px-2 py-1"
                  >
                    {saliencePercent(delta)}%
                  </Badge>
                </div>
                <p className="mt-2 line-clamp-2 text-xs font-semibold">
                  {delta.label}
                </p>
                <p className="text-muted mt-1 text-[11px]">
                  {t(
                    `pages.runs.policyDiff.significance.${delta.significance}`,
                  )}
                </p>
              </button>
            </li>
          );
        })}
      </ol>
      {deltas.length > visible.length ? (
        <p className="text-muted px-2 pt-2 text-center text-xs">
          +{deltas.length - visible.length} {t("pages.runs.policyDiff.more")}
        </p>
      ) : null}
    </nav>
  );
}

function iconFor(significance: DeltaQuantity["significance"]) {
  if (significance === "improved") {
    return ArrowUpRight;
  }
  if (significance === "worsened") {
    return ArrowDownRight;
  }
  if (significance === "mixed") {
    return ArrowRight;
  }
  return HelpCircle;
}
