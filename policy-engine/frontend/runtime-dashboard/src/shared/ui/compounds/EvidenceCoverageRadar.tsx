import { cn } from "@/lib/utils";
import { Card } from "@/shared/ui/primitives";
import { RadarChart, type RadarDimension, type RadarSeries } from "@/shared/charts";

export type EvidenceCoverage = {
  academic: number;
  dataset: number;
  legal: number;
  transport: number;
};

type EvidenceCoverageRadarProps = {
  coverage: EvidenceCoverage;
  benchmark?: EvidenceCoverage;
  title?: string;
  className?: string;
};

const DIMENSIONS: RadarDimension[] = [
  { key: "academic", label: "Academic", fullMark: 100 },
  { key: "dataset", label: "Dataset", fullMark: 100 },
  { key: "legal", label: "Legal", fullMark: 100 },
  { key: "transport", label: "Transport", fullMark: 100 },
];

function toPercent(coverage: EvidenceCoverage): Record<string, number> {
  return {
    academic: Math.round(coverage.academic * 100),
    dataset: Math.round(coverage.dataset * 100),
    legal: Math.round(coverage.legal * 100),
    transport: Math.round(coverage.transport * 100),
  };
}

export function EvidenceCoverageRadar({
  coverage,
  benchmark,
  title = "Evidence Coverage (4D)",
  className,
}: EvidenceCoverageRadarProps) {
  const series: RadarSeries[] = [
    { id: "current", label: "Current", values: toPercent(coverage) },
  ];
  if (benchmark) {
    series.push({
      id: "benchmark",
      label: "Benchmark",
      values: toPercent(benchmark),
    });
  }

  const overall =
    (coverage.academic + coverage.dataset + coverage.legal + coverage.transport) /
    4;

  return (
    <Card className={cn("space-y-3", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">{title}</h3>
        <span className="text-muted text-xs font-medium">
          Overall: {Math.round(overall * 100)}%
        </span>
      </div>

      <RadarChart
        dimensions={DIMENSIONS}
        series={series}
        height={300}
        className="border-0 p-0"
      />

      {/* Legend table */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {DIMENSIONS.map((dim) => {
          const val = coverage[dim.key as keyof EvidenceCoverage];
          return (
            <div
              key={dim.key}
              className="border-line rounded-xl border p-2 text-center"
            >
              <p className="text-muted text-xs uppercase">{dim.label}</p>
              <p className="mt-1 text-lg font-bold">
                {Math.round(val * 100)}%
              </p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
