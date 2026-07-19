import type { ReactElement } from "react";
import { createElement } from "react";

/* ── Pattern definitions for colorblind-safe chart fills ── */

export const PATTERN_IDS = {
  diagonal: "chart-pattern-diagonal",
  dots: "chart-pattern-dots",
  crosshatch: "chart-pattern-crosshatch",
  horizontal: "chart-pattern-horizontal",
  vertical: "chart-pattern-vertical",
  zigzag: "chart-pattern-zigzag",
} as const;

type PatternDef = {
  id: string;
  size: number;
  children: ReactElement;
};

const patterns: PatternDef[] = [
  {
    id: PATTERN_IDS.diagonal,
    size: 8,
    children: createElement("path", {
      d: "M-1,1 l2,-2 M0,8 l8,-8 M7,9 l2,-2",
      stroke: "currentColor",
      strokeWidth: 1.5,
      opacity: 0.5,
    }),
  },
  {
    id: PATTERN_IDS.dots,
    size: 6,
    children: createElement("circle", {
      cx: 3,
      cy: 3,
      r: 1.2,
      fill: "currentColor",
      opacity: 0.5,
    }),
  },
  {
    id: PATTERN_IDS.crosshatch,
    size: 8,
    children: createElement("path", {
      d: "M0,0 l8,8 M8,0 l-8,8",
      stroke: "currentColor",
      strokeWidth: 1,
      opacity: 0.4,
    }),
  },
  {
    id: PATTERN_IDS.horizontal,
    size: 6,
    children: createElement("path", {
      d: "M0,3 l6,0",
      stroke: "currentColor",
      strokeWidth: 1.5,
      opacity: 0.4,
    }),
  },
  {
    id: PATTERN_IDS.vertical,
    size: 6,
    children: createElement("path", {
      d: "M3,0 l0,6",
      stroke: "currentColor",
      strokeWidth: 1.5,
      opacity: 0.4,
    }),
  },
  {
    id: PATTERN_IDS.zigzag,
    size: 10,
    children: createElement("path", {
      d: "M0,5 l2.5,-5 l2.5,5 l2.5,-5 l2.5,5",
      stroke: "currentColor",
      strokeWidth: 1.2,
      fill: "none",
      opacity: 0.4,
    }),
  },
];

export function ChartPatternDefs(): ReactElement {
  return createElement(
    "defs",
    null,
    ...patterns.map((p) =>
      createElement(
        "pattern",
        {
          key: p.id,
          id: p.id,
          patternUnits: "userSpaceOnUse",
          width: p.size,
          height: p.size,
        },
        p.children,
      ),
    ),
  );
}

export function patternFill(index: number): string {
  const ids = Object.values(PATTERN_IDS);
  return `url(#${ids[index % ids.length]})`;
}

/* ── ARIA description generators ── */

export function describeTimeSeries(
  label: string,
  pointCount: number,
  yRange: [number, number],
): string {
  return `Time series chart: ${label}. ${pointCount} data points ranging from ${yRange[0].toFixed(2)} to ${yRange[1].toFixed(2)}.`;
}

export function describeBarChart(
  title: string,
  barCount: number,
  maxLabel: string,
  maxValue: number,
): string {
  return `Bar chart: ${title}. ${barCount} categories. Highest: ${maxLabel} at ${maxValue.toFixed(2)}.`;
}

export function describeConfidenceInterval(
  estimate: number,
  lower: number,
  upper: number,
  level: number,
): string {
  const pct = Math.round(level * 100);
  return `Point estimate ${estimate.toFixed(3)} with ${pct}% confidence interval from ${lower.toFixed(3)} to ${upper.toFixed(3)}.`;
}

export function describeForestPlot(
  studies: Array<{ label: string; estimate: number }>,
  referencePoint: number | null,
): string {
  if (referencePoint === null) {
    return `Forest plot with ${studies.length} studies. Direction relative to a reference is unavailable.`;
  }

  const aboveReferenceCount = studies.filter(
    (study) => study.estimate > referencePoint,
  ).length;
  return `Forest plot with ${studies.length} studies. ${aboveReferenceCount} estimates are above the reference, ${studies.length - aboveReferenceCount} are at or below it.`;
}

/* ── Screen reader data table ── */

export type DataTableRow = { label: string; values: Record<string, string> };

export function ChartDataTable({
  caption,
  columns,
  rows,
}: {
  caption: string;
  columns: string[];
  rows: DataTableRow[];
}): ReactElement {
  return createElement(
    "table",
    { className: "sr-only", role: "table" },
    createElement("caption", null, caption),
    createElement(
      "thead",
      null,
      createElement(
        "tr",
        null,
        createElement("th", { scope: "col" }, "Label"),
        ...columns.map((col) =>
          createElement("th", { key: col, scope: "col" }, col),
        ),
      ),
    ),
    createElement(
      "tbody",
      null,
      ...rows.map((row) =>
        createElement(
          "tr",
          { key: row.label },
          createElement("th", { scope: "row" }, row.label),
          ...columns.map((col) =>
            createElement("td", { key: col }, row.values[col] ?? "-"),
          ),
        ),
      ),
    ),
  );
}
