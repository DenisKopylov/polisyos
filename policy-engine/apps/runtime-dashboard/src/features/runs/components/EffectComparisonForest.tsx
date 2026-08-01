import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Card } from "@polisyos/atlas-ui";
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
  baseLabel,
  targetLabel,
  className,
}: EffectComparisonForestProps) {
  const { t } = useI18n();
  const resolvedBaseLabel = baseLabel ?? t("pages.runs.compare.columns.base");
  const resolvedTargetLabel =
    targetLabel ?? t("pages.runs.compare.columns.target");

  return (
    <Card className={cn("space-y-4 p-4", className)}>
      <h4 className="text-sm font-semibold">
        {t("pages.runs.compare.visual.effectSizeComparison")}
      </h4>

      <div className="grid gap-4 lg:grid-cols-2">
        {baseEstimates.length > 0 && (
          <ForestPlot estimates={baseEstimates} title={resolvedBaseLabel} />
        )}
        {targetEstimates.length > 0 && (
          <ForestPlot estimates={targetEstimates} title={resolvedTargetLabel} />
        )}
      </div>

      {baseEstimates.length === 0 && targetEstimates.length === 0 && (
        <p className="text-muted text-xs">
          {t("pages.runs.compare.visual.noEffectEstimates")}
        </p>
      )}
    </Card>
  );
}
