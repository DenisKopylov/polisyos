import { useMemo } from "react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import { Quantity } from "@/shared/ui/quantity";
import { Card } from "@polisyos/atlas-ui";
import { WaterfallChart, type WaterfallStep } from "@/shared/charts";
import type { QuantityValueOutput } from "@polisyos/runtime-api-client";

export type AttributionStep = {
  label: string;
  value: number;
  detail?: string;
};

type AttributionWaterfallProps = {
  baseValue: QuantityValueOutput;
  baseLabel?: string;
  contributions: AttributionStep[];
  totalLabel?: string;
  title?: string;
  onStepClick?: (step: AttributionStep) => void;
  className?: string;
};

export function AttributionWaterfall({
  baseValue,
  baseLabel,
  contributions,
  totalLabel,
  title,
  onStepClick,
  className,
}: AttributionWaterfallProps) {
  const { t } = useI18n();
  const resolvedBaseLabel =
    baseLabel || t("shared.ui.attributionWaterfall.baseLabel");
  const resolvedTotalLabel =
    totalLabel || t("shared.ui.attributionWaterfall.totalLabel");
  const resolvedTitle = title ?? t("shared.ui.attributionWaterfall.title");
  const basePoint =
    typeof baseValue.point === "number" && Number.isFinite(baseValue.point)
      ? baseValue.point
      : null;
  const finalValue =
    basePoint === null
      ? null
      : basePoint + contributions.reduce((sum, c) => sum + c.value, 0);

  const steps: WaterfallStep[] = [
    ...(basePoint === null
      ? []
      : [{ label: resolvedBaseLabel, value: basePoint, isTotal: true }]),
    ...contributions.map((c) => ({ label: c.label, value: c.value })),
    ...(finalValue === null
      ? []
      : [{ label: resolvedTotalLabel, value: finalValue, isTotal: true }]),
  ];

  const sorted = useMemo(
    () =>
      [...contributions].sort((a, b) => Math.abs(b.value) - Math.abs(a.value)),
    [contributions],
  );

  return (
    <Card className={cn("space-y-4", className)}>
      <h3 className="text-lg font-semibold">{resolvedTitle}</h3>

      <WaterfallChart steps={steps} height={280} />

      {/* Detailed breakdown */}
      <div className="border-line rounded-2xl border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-line border-b">
              <th className="text-muted px-4 py-2 text-start text-xs font-medium uppercase">
                {t("shared.ui.attributionWaterfall.columns.factor")}
              </th>
              <th className="text-muted px-4 py-2 text-end text-xs font-medium uppercase">
                {t("shared.ui.attributionWaterfall.columns.contribution")}
              </th>
              <th className="text-muted hidden px-4 py-2 text-start text-xs font-medium uppercase md:table-cell">
                {t("shared.ui.attributionWaterfall.columns.detail")}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-line bg-surface/50 border-b">
              <td className="px-4 py-2.5 font-semibold">{resolvedBaseLabel}</td>
              <td className="px-4 py-2.5 text-end font-mono font-semibold">
                <span data-quantity-metric-id={baseValue.metric_id}>
                  <Quantity value={baseValue} variant="dense" />
                </span>
              </td>
              <td className="hidden px-4 py-2.5 md:table-cell" />
            </tr>
            {sorted.map((c) => (
              <tr
                key={c.label}
                className={cn(
                  "border-line border-b last:border-0",
                  onStepClick && "hover:bg-surface/50 cursor-pointer",
                )}
                onClick={onStepClick ? () => onStepClick(c) : undefined}
              >
                <td className="px-4 py-2.5 font-medium">{c.label}</td>
                <td
                  className={cn(
                    "px-4 py-2.5 text-end font-mono font-semibold",
                    c.value > 0
                      ? "text-[var(--color-status-approved)]"
                      : c.value < 0
                        ? "text-[var(--color-status-rejected)]"
                        : "text-muted",
                  )}
                >
                  {c.value >= 0 ? "+" : ""}
                  {c.value.toFixed(4)}
                </td>
                <td className="text-muted hidden px-4 py-2.5 text-sm md:table-cell">
                  {c.detail}
                </td>
              </tr>
            ))}
            {finalValue !== null ? (
              <tr className="bg-surface/50">
                <td className="px-4 py-2.5 font-bold">{resolvedTotalLabel}</td>
                <td className="px-4 py-2.5 text-end font-mono font-bold">
                  {finalValue.toFixed(4)}
                </td>
                <td className="hidden px-4 py-2.5 md:table-cell" />
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
