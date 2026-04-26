import { cn } from "@/lib/utils";

type TemporalLegendProps = {
  observedLabel?: string;
  simulatedLabel?: string;
  className?: string;
};

const DEFAULT_LABELS = {
  observed: "Observed",
  simulated: "Simulated",
};

export function TemporalLegend({
  className,
  observedLabel = DEFAULT_LABELS.observed,
  simulatedLabel = DEFAULT_LABELS.simulated,
}: TemporalLegendProps) {
  return (
    <div
      className={cn(
        "text-muted flex items-center gap-3 text-[11px] font-semibold",
        className,
      )}
    >
      <span className="inline-flex items-center gap-1.5">
        <span className="h-0.5 w-5 rounded-full bg-[var(--chart-primary)]" />
        <span>{observedLabel}</span>
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-0 w-5 border-t border-dashed border-[var(--chart-primary)]" />
        <span>{simulatedLabel}</span>
      </span>
    </div>
  );
}
