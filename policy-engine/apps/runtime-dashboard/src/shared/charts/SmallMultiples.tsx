import { useMemo } from "react";

import type { VerificationMetadata } from "@polisyos/runtime-api-client";
import { cn } from "@/shared/lib/utils";

import { categoricalSwatch } from "./categorical-palettes";

export type SmallMultipleDatum = {
  region: string;
  sector: string;
  value: number;
  label?: string;
  verification?: Pick<
    VerificationMetadata,
    "freshness" | "verification_status"
  > | null;
};

export type SmallMultiplesProps = {
  data: SmallMultipleDatum[];
  selectedRegion?: string | null;
  selectedSector?: string | null;
  valueDomain?: readonly [number, number];
  valueLabel?: string;
  className?: string;
  onSelect?: (datum: SmallMultipleDatum) => void;
};

const EMPTY_STATE_LABEL = "No comparison data available.";

export function SmallMultiples({
  data,
  selectedRegion,
  selectedSector,
  valueDomain,
  valueLabel = "value",
  className,
  onSelect,
}: SmallMultiplesProps) {
  const model = useMemo(
    () => buildSmallMultiplesModel(data, valueDomain),
    [data, valueDomain],
  );

  if (data.length === 0) {
    return (
      <p className="text-muted-foreground text-sm" role="status">
        {EMPTY_STATE_LABEL}
      </p>
    );
  }

  return (
    <section
      className={cn("small-multiples", className)}
      aria-label={`${valueLabel} small multiples`}
    >
      <div className="small-multiples-axis" aria-hidden="true">
        <span>{formatAxis(model.min)}</span>
        <span>{formatAxis(model.max)}</span>
      </div>
      <div
        className="small-multiples-grid"
        role="grid"
        aria-rowcount={model.regions.length}
        aria-colcount={model.sectors.length}
      >
        {model.regions.map((region, rowIndex) =>
          model.sectors.map((sector, columnIndex) => {
            const datum = model.byKey.get(keyFor(region, sector));
            const selected =
              region === selectedRegion || sector === selectedSector;
            const swatch = categoricalSwatch(columnIndex, 12);
            return (
              <button
                key={keyFor(region, sector)}
                type="button"
                className={cn(
                  "small-multiple-cell",
                  selected && "small-multiple-cell-selected",
                )}
                role="gridcell"
                aria-colindex={columnIndex + 1}
                aria-label={`${region}, ${sector}, ${datum ? formatAxis(datum.value) : "missing"} ${valueLabel}`}
                aria-rowindex={rowIndex + 1}
                data-pattern={swatch.pattern}
                data-region={region}
                data-sector={sector}
                data-verification-status={
                  datum?.verification?.verification_status
                }
                data-freshness={datum?.verification?.freshness}
                onClick={() => {
                  if (datum) {
                    onSelect?.(datum);
                  }
                }}
              >
                <span className="small-multiple-heading">
                  <span>{region}</span>
                  <span>{sector}</span>
                </span>
                <svg
                  className="small-multiple-chart"
                  viewBox="0 0 120 48"
                  role="img"
                  aria-hidden="true"
                >
                  <line
                    x1="8"
                    x2="112"
                    y1="36"
                    y2="36"
                    stroke="var(--chart-grid)"
                    strokeWidth="1"
                  />
                  {datum ? (
                    <rect
                      data-chart-series={swatch.name}
                      x="8"
                      y="20"
                      width={Math.max(
                        2,
                        normalizeValue(datum.value, model.min, model.max) * 104,
                      )}
                      height="12"
                      rx="2"
                      fill={swatch.color}
                    />
                  ) : null}
                </svg>
                <span className="small-multiple-value">
                  {datum ? formatAxis(datum.value) : "-"}
                </span>
              </button>
            );
          }),
        )}
      </div>
    </section>
  );
}

export function buildSmallMultiplesModel(
  data: SmallMultipleDatum[],
  valueDomain?: readonly [number, number],
) {
  const regions = Array.from(new Set(data.map((datum) => datum.region))).sort();
  const sectors = Array.from(new Set(data.map((datum) => datum.sector))).sort();
  const values = data.map((datum) => datum.value);
  const min = valueDomain?.[0] ?? Math.min(...values, 0);
  const max = valueDomain?.[1] ?? Math.max(...values, 1);
  const byKey = new Map(
    data.map((datum) => [keyFor(datum.region, datum.sector), datum]),
  );
  return { byKey, max, min, regions, sectors };
}

function keyFor(region: string, sector: string) {
  return `${region}\u0000${sector}`;
}

function normalizeValue(value: number, min: number, max: number) {
  if (max <= min) {
    return 1;
  }
  return Math.min(1, Math.max(0, (value - min) / (max - min)));
}

function formatAxis(value: number) {
  return new Intl.NumberFormat("en", {
    maximumFractionDigits: 2,
    notation: Math.abs(value) >= 1000 ? "compact" : "standard",
  }).format(value);
}
