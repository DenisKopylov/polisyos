import type { ScenarioListPayload } from "@/api/validators";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import {
  formatQuantityValue,
  type QuantityFormatOptions,
} from "@/shared/ui/quantity/quantity-format";
import type {
  CounterfactualMetric,
  QuantityValue,
} from "@/shared/ui/quantity/quantity.types";

import { AssumptionPill } from "./AssumptionPill";
import { counterfactualTokens } from "./counterfactual-colors";

type ScenarioAssumption = NonNullable<
  ScenarioListPayload["scenarios"]
>[number]["assumptions"][number];

type CounterfactualMetricChartProps = {
  metric: CounterfactualMetric;
  assumptions?: ScenarioAssumption[];
  format?: QuantityFormatOptions["format"];
  className?: string;
};

type ChartRow = {
  key: "actual" | "scenario" | "delta";
  labelKey: string;
  quantity: QuantityValue;
  className: string;
};

export function CounterfactualMetricChart({
  metric,
  assumptions = [],
  format = "decimal",
  className,
}: CounterfactualMetricChartProps) {
  const { t, locale } = useI18n();
  const rows: ChartRow[] = [
    {
      key: "actual",
      labelKey: "shared.ui.counterfactual.actual",
      quantity: metric.actual,
      className: "bg-[color-mix(in_srgb,var(--foreground)_34%,transparent)]",
    },
    {
      key: "scenario",
      labelKey: "shared.ui.counterfactual.scenario",
      quantity: metric.counterfactual,
      className: counterfactualTokens.scenario.className,
    },
    {
      key: "delta",
      labelKey: "shared.ui.counterfactual.delta",
      quantity: metric.delta,
      className: counterfactualTokens.delta.className,
    },
  ];
  const domain = resolveDomain(rows.map((row) => row.quantity));

  return (
    <figure
      className={cn("space-y-2", className)}
      aria-label={t("shared.ui.counterfactual.chartAria", {
        label: metric.label,
        scenarioId: metric.scenario_ref.id,
      })}
      data-testid="counterfactual-metric-chart"
    >
      <div className="space-y-1.5">
        {rows.map((row) => (
          <MetricChartRow
            key={row.key}
            row={row}
            domain={domain}
            format={format}
            locale={locale}
            label={t(row.labelKey)}
            renderInterval={(interval) =>
              t("shared.ui.counterfactual.ci95", { interval })
            }
          />
        ))}
      </div>
      {assumptions.length ? (
        <figcaption className="flex flex-wrap gap-1.5">
          {assumptions.map((assumption) => (
            <AssumptionPill key={assumption.id} assumption={assumption} />
          ))}
        </figcaption>
      ) : null}
    </figure>
  );
}

function MetricChartRow({
  row,
  domain,
  format,
  locale,
  label,
  renderInterval,
}: {
  row: ChartRow;
  domain: number;
  format: QuantityFormatOptions["format"];
  locale: string;
  label: string;
  renderInterval: (interval: string) => string;
}) {
  const formatted = formatQuantityValue(row.quantity, { format, locale });
  const width = Math.max(
    2,
    Math.min(100, (Math.abs(row.quantity.point ?? 0) / domain) * 100),
  );
  const interval = row.quantity.uncertainty?.ci_95;
  const intervalLabel = interval
    ? `${interval[0].toLocaleString(locale)}-${interval[1].toLocaleString(locale)}`
    : null;

  return (
    <div
      className="grid grid-cols-[5.5rem_minmax(0,1fr)_max-content] items-center gap-2 text-xs"
      data-counterfactual-series={row.key}
    >
      <span className="text-muted font-semibold">{label}</span>
      <div className="bg-muted/30 relative h-2 overflow-hidden rounded-full">
        <span
          className={cn(
            "absolute inset-y-0 left-0 rounded-full",
            row.className,
          )}
          style={{ width: `${width}%` }}
        />
      </div>
      <span className="tabular-nums">{formatted.text}</span>
      {intervalLabel ? (
        <span className="text-muted col-start-2 text-[11px]">
          {renderInterval(intervalLabel)}
        </span>
      ) : null}
    </div>
  );
}

function resolveDomain(quantities: QuantityValue[]) {
  const candidates = quantities.flatMap((quantity) => {
    const values = [Math.abs(quantity.point ?? 0)];
    const ci = quantity.uncertainty?.ci_95;
    if (ci) {
      values.push(Math.abs(ci[0]), Math.abs(ci[1]));
    }
    return values;
  });
  return Math.max(1, ...candidates);
}
