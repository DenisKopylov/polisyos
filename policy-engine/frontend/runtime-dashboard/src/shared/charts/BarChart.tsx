import { useMemo } from "react";
import {
  Bar,
  BarChart as RechartsBarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cn } from "@/lib/utils";
import { chartTheme, categoricalPalette, chartDefaults } from "./theme";
import {
  ChartPatternDefs,
  describeBarChart,
  ChartDataTable,
} from "./accessibility";
import type { DataPoint } from "./types";

type BarChartProps = {
  data: DataPoint[];
  title?: string;
  layout?: "vertical" | "horizontal";
  colorByValue?: boolean;
  positiveColor?: string;
  negativeColor?: string;
  height?: number;
  className?: string;
};

export function BarChart({
  data,
  title,
  layout = "vertical",
  colorByValue = false,
  positiveColor = chartTheme.success,
  negativeColor = chartTheme.alert,
  height = 320,
  className,
}: BarChartProps) {
  const ariaDescription = useMemo(() => {
    if (!data.length) return "";
    const max = data.reduce((a, b) => (b.value > a.value ? b : a), data[0]);
    return describeBarChart(
      title ?? "Bar chart",
      data.length,
      max.label,
      max.value,
    );
  }, [data, title]);

  const tableRows = useMemo(
    () =>
      data.map((d) => ({
        label: d.label,
        values: { Value: d.value.toFixed(3) },
      })),
    [data],
  );

  const isHorizontal = layout === "horizontal";

  return (
    <figure
      className={cn("border-border bg-card rounded-xl border p-4", className)}
      role="img"
      aria-label={ariaDescription}
    >
      {title && (
        <figcaption className="text-foreground mb-3 text-sm font-semibold">
          {title}
        </figcaption>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <RechartsBarChart
          data={data}
          layout={isHorizontal ? "vertical" : "horizontal"}
          margin={chartDefaults.margin}
        >
          <defs>
            <ChartPatternDefs />
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
          {isHorizontal ? (
            <>
              <XAxis type="number" tick={{ fontSize: chartDefaults.tickFontSize }} stroke={chartTheme.axis} />
              <YAxis
                type="category"
                dataKey="label"
                tick={{ fontSize: chartDefaults.tickFontSize }}
                stroke={chartTheme.axis}
                width={120}
              />
            </>
          ) : (
            <>
              <XAxis
                dataKey="label"
                tick={{ fontSize: chartDefaults.tickFontSize }}
                stroke={chartTheme.axis}
              />
              <YAxis tick={{ fontSize: chartDefaults.tickFontSize }} stroke={chartTheme.axis} />
            </>
          )}
          <Tooltip
            contentStyle={{
              borderRadius: 12,
              border: `1px solid var(--line)`,
              background: "var(--panel)",
              fontSize: chartDefaults.fontSize,
            }}
          />
          <Bar
            dataKey="value"
            radius={[4, 4, 0, 0]}
            maxBarSize={48}
            name={title ?? "Value"}
          >
            {data.map((d, i) => (
              <Cell
                key={d.label}
                fill={
                  colorByValue
                    ? d.value >= 0
                      ? positiveColor
                      : negativeColor
                    : categoricalPalette[i % categoricalPalette.length]
                }
              />
            ))}
          </Bar>
        </RechartsBarChart>
      </ResponsiveContainer>
      <ChartDataTable
        caption={title ?? "Bar chart data"}
        columns={["Value"]}
        rows={tableRows}
      />
    </figure>
  );
}
