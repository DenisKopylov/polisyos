import { cn } from "@/lib/utils";
import { Card } from "@/shared/ui/primitives";
import { ForestPlot, type EffectEstimate } from "@/shared/charts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type EffectComparisonForestProps = {
  baseEstimates: EffectEstimate[];
  targetEstimates: EffectEstimate[];
  baseLabel?: string;
  targetLabel?: string;
  className?: string;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EffectComparisonForest({
  baseEstimates,
  targetEstimates,
  baseLabel = "Base",
  targetLabel = "Target",
  className,
}: EffectComparisonForestProps) {
  return (
    <Card className={cn("space-y-4 p-4", className)}>
      <h4 className="text-sm font-semibold">Effect Size Comparison</h4>

      <div className="grid gap-4 lg:grid-cols-2">
        {baseEstimates.length > 0 && (
          <ForestPlot
            estimates={baseEstimates}
            title={baseLabel}
          />
        )}
        {targetEstimates.length > 0 && (
          <ForestPlot
            estimates={targetEstimates}
            title={targetLabel}
          />
        )}
      </div>

      {baseEstimates.length === 0 && targetEstimates.length === 0 && (
        <p className="text-muted text-xs">
          No effect estimates available for comparison.
        </p>
      )}
    </Card>
  );
}
