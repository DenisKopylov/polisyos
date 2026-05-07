import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cn } from "@/shared/lib/utils";
import { chartTheme, ciColors, chartDefaults } from "./theme";
import {
  ChartPatternDefs,
  describeTimeSeries,
  ChartDataTable,
} from "./accessibility";
import type { TimeSeriesDataPoint } from "./types";

type AreaChartSeries = {
  dataKey: string;
  label: string;
  color?: string;
  dashed?: boolean;
};

type AreaChartProps = {
  data: TimeSeriesDataPoint[];
  series: AreaChartSeries[];
  xKey?: string;
  title?: string;
  showConfidenceBands?: boolean;
  confidenceDataKeys?: {
    ci50?: [string, string];
    ci80?: [string, string];
    ci95?: [string, string];
  };
  height?: number;
  className?: string;
};

export function AreaChart({
  data,
  series,
  xKey = "x",
  title,
  showConfidenceBands = false,
  confidenceDataKeys,
  height = 320,
  className,
}: AreaChartProps) {
  const ariaDescription = useMemo(() => {
    if (!data.length || !series.length) return "";
    const yVals = data.map((d) => d.y).filter((v) => v != null);
    const range: [number, number] = [Math.min(...yVals), Math.max(...yVals)];
    return describeTimeSeries(title ?? series[0].label, data.length, range);
  }, [data, series, title]);

  const tableRows = useMemo(
    () =>
      data.slice(0, 20).map((d) => ({
        label: String(d[xKey as keyof TimeSeriesDataPoint] ?? d.x),
        values: Object.fromEntries(
          series.map((s) => [
            s.label,
            String((d as Record<string, unknown>)[s.dataKey] ?? "-"),
          ]),
        ),
      })),
    [data, series, xKey],
  );

  const ci = confidenceDataKeys;

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
        <ComposedChart data={data} margin={chartDefaults.margin}>
          <defs>
            <ChartPatternDefs />
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
          <XAxis
            dataKey={xKey}
            tick={{ fontSize: chartDefaults.tickFontSize }}
            stroke={chartTheme.axis}
          />
          <YAxis
            tick={{ fontSize: chartDefaults.tickFontSize }}
            stroke={chartTheme.axis}
          />
          <Tooltip
            contentStyle={{
              borderRadius: 12,
              border: `1px solid var(--line)`,
              background: "var(--panel)",
              fontSize: chartDefaults.fontSize,
            }}
          />
          <Legend />

          {showConfidenceBands && ci?.ci95 && (
            <Area
              type="monotone"
              dataKey={ci.ci95[1]}
              stroke="none"
              fill={ciColors.ci95}
              fillOpacity={1}
              name="95% CI"
              legendType="none"
            />
          )}
          {showConfidenceBands && ci?.ci95 && (
            <Area
              type="monotone"
              dataKey={ci.ci95[0]}
              stroke="none"
              fill="var(--card)"
              fillOpacity={1}
              legendType="none"
            />
          )}
          {showConfidenceBands && ci?.ci80 && (
            <Area
              type="monotone"
              dataKey={ci.ci80[1]}
              stroke="none"
              fill={ciColors.ci80}
              fillOpacity={1}
              name="80% CI"
              legendType="none"
            />
          )}
          {showConfidenceBands && ci?.ci80 && (
            <Area
              type="monotone"
              dataKey={ci.ci80[0]}
              stroke="none"
              fill="var(--card)"
              fillOpacity={1}
              legendType="none"
            />
          )}
          {showConfidenceBands && ci?.ci50 && (
            <Area
              type="monotone"
              dataKey={ci.ci50[1]}
              stroke="none"
              fill={ciColors.ci50}
              fillOpacity={1}
              name="50% CI"
              legendType="none"
            />
          )}
          {showConfidenceBands && ci?.ci50 && (
            <Area
              type="monotone"
              dataKey={ci.ci50[0]}
              stroke="none"
              fill="var(--card)"
              fillOpacity={1}
              legendType="none"
            />
          )}

          {series.map((s, i) => (
            <Line
              key={s.dataKey}
              type="monotone"
              dataKey={s.dataKey}
              stroke={s.color ?? chartTheme.primary}
              strokeWidth={chartDefaults.strokeWidth}
              strokeDasharray={s.dashed ? "6 3" : undefined}
              dot={false}
              name={s.label}
              activeDot={{ r: 4, strokeWidth: 0 }}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
      <ChartDataTable
        caption={title ?? "Area chart data"}
        columns={series.map((s) => s.label)}
        rows={tableRows}
      />
    </figure>
  );
}
