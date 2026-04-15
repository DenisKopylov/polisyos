import { useMemo } from "react";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart as RechartsRadarChart,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts";

import { cn } from "@/lib/utils";
import { categoricalPalette, chartTheme, chartDefaults } from "./theme";
import { ChartDataTable } from "./accessibility";
import type { RadarDimension, RadarSeries } from "./types";

type RadarChartProps = {
  dimensions: RadarDimension[];
  series: RadarSeries[];
  title?: string;
  height?: number;
  className?: string;
};

export function RadarChart({
  dimensions,
  series,
  title,
  height = 360,
  className,
}: RadarChartProps) {
  const data = useMemo(
    () =>
      dimensions.map((dim) => {
        const row: Record<string, string | number> = {
          dimension: dim.label,
          fullMark: dim.fullMark ?? 100,
        };
        for (const s of series) {
          row[s.id] = s.values[dim.key] ?? 0;
        }
        return row;
      }),
    [dimensions, series],
  );

  const tableRows = useMemo(
    () =>
      dimensions.map((dim) => ({
        label: dim.label,
        values: Object.fromEntries(
          series.map((s) => [s.label, String(s.values[dim.key] ?? 0)]),
        ),
      })),
    [dimensions, series],
  );

  const ariaDescription = `Radar chart${title ? `: ${title}` : ""}. ${dimensions.length} dimensions, ${series.length} series.`;

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
        <RechartsRadarChart data={data} cx="50%" cy="50%" outerRadius="72%">
          <PolarGrid stroke={chartTheme.grid} />
          <PolarAngleAxis
            dataKey="dimension"
            tick={{ fontSize: chartDefaults.tickFontSize, fill: chartTheme.axis }}
          />
          <PolarRadiusAxis
            tick={{ fontSize: chartDefaults.tickFontSize }}
            stroke={chartTheme.grid}
          />
          <Tooltip
            contentStyle={{
              borderRadius: 12,
              border: `1px solid var(--line)`,
              background: "var(--panel)",
              fontSize: chartDefaults.fontSize,
            }}
          />
          {series.length > 1 && <Legend />}
          {series.map((s, i) => (
            <Radar
              key={s.id}
              name={s.label}
              dataKey={s.id}
              stroke={categoricalPalette[i % categoricalPalette.length]}
              fill={categoricalPalette[i % categoricalPalette.length]}
              fillOpacity={0.15}
              strokeWidth={2}
            />
          ))}
        </RechartsRadarChart>
      </ResponsiveContainer>
      <ChartDataTable
        caption={title ?? "Radar chart data"}
        columns={series.map((s) => s.label)}
        rows={tableRows}
      />
    </figure>
  );
}
