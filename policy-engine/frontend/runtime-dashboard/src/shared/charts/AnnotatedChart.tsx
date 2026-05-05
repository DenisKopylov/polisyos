import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cn } from "@/shared/lib/utils";
import { chartTheme, ciColors, chartDefaults } from "./theme";
import { ChartDataTable } from "./accessibility";
import type { TimeSeriesDataPoint } from "./types";

export type ChartAnnotation = {
  x: string | number;
  label: string;
  type: "event" | "insight" | "warning";
  detail?: string;
};

type AnnotatedChartProps = {
  data: TimeSeriesDataPoint[];
  annotations?: ChartAnnotation[];
  yKey?: string;
  xKey?: string;
  confidenceBand?: { upper: string; lower: string };
  title?: string;
  height?: number;
  className?: string;
};

const ANNOTATION_COLORS: Record<ChartAnnotation["type"], string> = {
  event: chartTheme.secondary,
  insight: chartTheme.success,
  warning: chartTheme.warning,
};

const ANNOTATION_ICONS: Record<ChartAnnotation["type"], string> = {
  event: "\u25C6",
  insight: "\u2605",
  warning: "\u26A0",
};

function AnnotationMarker({
  x,
  annotation,
  viewBox,
}: {
  x: number;
  annotation: ChartAnnotation;
  viewBox?: { x: number; y: number; width: number; height: number };
}) {
  const color = ANNOTATION_COLORS[annotation.type];
  const icon = ANNOTATION_ICONS[annotation.type];
  const y = viewBox?.y ?? 0;

  return (
    <g>
      <circle cx={x} cy={y + 12} r={8} fill={color} fillOpacity={0.15} />
      <text x={x} y={y + 16} textAnchor="middle" fontSize={10} fill={color}>
        {icon}
      </text>
      <text
        x={x}
        y={y + 30}
        textAnchor="middle"
        fontSize={chartDefaults.tickFontSize}
        fill={color}
        fontWeight={600}
      >
        {annotation.label.length > 20
          ? `${annotation.label.slice(0, 19)}\u2026`
          : annotation.label}
      </text>
    </g>
  );
}

export function AnnotatedChart({
  data,
  annotations = [],
  yKey = "y",
  xKey = "x",
  confidenceBand,
  title = "Annotated Chart",
  height = 320,
  className,
}: AnnotatedChartProps) {
  const tableRows = useMemo(
    () =>
      data.map((d) => ({
        label: String(d[xKey as keyof typeof d] ?? ""),
        values: {
          Value: String((d as Record<string, unknown>)[yKey] ?? ""),
          ...(confidenceBand
            ? {
                Upper: String(
                  (d as Record<string, unknown>)[confidenceBand.upper] ?? "",
                ),
                Lower: String(
                  (d as Record<string, unknown>)[confidenceBand.lower] ?? "",
                ),
              }
            : {}),
        },
      })),
    [data, xKey, yKey, confidenceBand],
  );

  const tableColumns = confidenceBand ? ["Value", "Upper", "Lower"] : ["Value"];

  return (
    <div className={cn("space-y-3", className)}>
      {title && <h3 className="text-lg font-semibold">{title}</h3>}

      <div
        role="img"
        aria-label={`${title}: ${data.length} data points with ${annotations.length} annotations`}
      >
        <ResponsiveContainer width="100%" height={height}>
          <ComposedChart
            data={data}
            margin={{ top: 40, right: 16, bottom: 8, left: 4 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={chartTheme.grid}
              vertical={false}
            />
            <XAxis
              dataKey={xKey}
              tick={{
                fontSize: chartDefaults.tickFontSize,
                fill: chartTheme.axis,
              }}
              stroke={chartTheme.axis}
            />
            <YAxis
              tick={{
                fontSize: chartDefaults.tickFontSize,
                fill: chartTheme.axis,
              }}
              stroke={chartTheme.axis}
            />
            <Tooltip
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--line)",
                borderRadius: 12,
                fontSize: 12,
              }}
            />

            {/* Confidence band */}
            {confidenceBand && (
              <Area
                dataKey={confidenceBand.upper}
                stroke="none"
                fill={ciColors.ci80}
                fillOpacity={1}
                isAnimationActive={false}
              />
            )}
            {confidenceBand && (
              <Area
                dataKey={confidenceBand.lower}
                stroke="none"
                fill="var(--surface)"
                fillOpacity={1}
                isAnimationActive={false}
              />
            )}

            {/* Main line */}
            <Line
              dataKey={yKey}
              stroke={chartTheme.primary}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />

            {/* Annotation reference lines */}
            {annotations.map((ann) => (
              <ReferenceLine
                key={`${ann.x}-${ann.label}`}
                x={ann.x}
                stroke={ANNOTATION_COLORS[ann.type]}
                strokeDasharray="4 3"
                strokeWidth={1.5}
                label={({ viewBox }) => (
                  <AnnotationMarker
                    x={viewBox?.x ?? 0}
                    annotation={ann}
                    viewBox={
                      viewBox as {
                        x: number;
                        y: number;
                        width: number;
                        height: number;
                      }
                    }
                  />
                )}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Annotation legend */}
      {annotations.length > 0 && (
        <div className="flex flex-wrap gap-3 text-xs">
          {annotations.map((ann) => (
            <div
              key={`${ann.x}-${ann.label}`}
              className="flex items-center gap-1.5"
            >
              <span style={{ color: ANNOTATION_COLORS[ann.type] }}>
                {ANNOTATION_ICONS[ann.type]}
              </span>
              <span className="font-medium">{ann.label}</span>
              {ann.detail && <span className="text-muted">— {ann.detail}</span>}
            </div>
          ))}
        </div>
      )}

      <ChartDataTable caption={title} columns={tableColumns} rows={tableRows} />
    </div>
  );
}
