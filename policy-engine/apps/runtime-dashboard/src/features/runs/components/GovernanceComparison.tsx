import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  presentDecisionGradeLabel,
  type DecisionGradePresentation,
} from "@/shared/ui/compounds/decisionGradePresentation";
import { Card, Badge } from "@polisyos/atlas-ui";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type GovernanceComparisonItem = {
  baseDecisionGrade: unknown;
  passId: string;
  label: string;
  targetDecisionGrade: unknown;
};

type GovernanceComparisonProps = {
  items: GovernanceComparisonItem[];
  baseLabel?: string;
  targetLabel?: string;
  className?: string;
};

function DecisionGradeBadge({
  presentation,
}: {
  presentation: DecisionGradePresentation;
}) {
  const { t } = useI18n();
  const label = presentation.ownerLabel ?? t("common.unavailable");

  return (
    <Badge
      kind="neutral"
      data-decision-grade-presentation={presentation.classification}
      data-kind="neutral"
      data-owner-grade={presentation.ownerLabel ?? ""}
    >
      {label}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function GovernanceComparison({
  items,
  baseLabel,
  targetLabel,
  className,
}: GovernanceComparisonProps) {
  const { t } = useI18n();
  const resolvedBaseLabel = baseLabel ?? t("pages.runs.compare.columns.base");
  const resolvedTargetLabel =
    targetLabel ?? t("pages.runs.compare.columns.target");
  const comparisonLabel = t("pages.runs.compare.visual.governanceComparison");
  const presentedItems = items.map((item) => ({
    ...item,
    basePresentation: presentDecisionGradeLabel(item.baseDecisionGrade),
    targetPresentation: presentDecisionGradeLabel(item.targetDecisionGrade),
  }));
  const changed = presentedItems.filter(
    (item) =>
      item.basePresentation.ownerLabel !== item.targetPresentation.ownerLabel,
  );
  const unchanged = presentedItems.filter(
    (item) =>
      item.basePresentation.ownerLabel === item.targetPresentation.ownerLabel,
  );

  return (
    <Card className={cn("space-y-3 p-4", className)}>
      <h4 className="text-sm font-semibold">{comparisonLabel}</h4>

      {items.length === 0 ? (
        <p className="text-muted text-xs">
          {t("pages.runs.compare.visual.noGovernancePasses")}
        </p>
      ) : (
        <div aria-label={comparisonLabel} className="space-y-2" role="table">
          <div role="rowgroup">
            <div
              className="text-muted grid grid-cols-3 gap-2 text-xs font-semibold"
              role="row"
            >
              <span role="columnheader">
                {t("pages.runs.compare.visual.passColumn")}
              </span>
              <span className="text-center" role="columnheader">
                {resolvedBaseLabel}
              </span>
              <span className="text-center" role="columnheader">
                {resolvedTargetLabel}
              </span>
            </div>

            {changed.map((item) => (
              <div
                key={item.passId}
                className="border-line grid grid-cols-3 items-center gap-2 rounded-lg border p-2"
                role="row"
                style={{
                  borderLeftWidth: 3,
                  borderLeftColor: "var(--chart-warning)",
                }}
              >
                <span className="text-xs font-medium" role="cell">
                  {item.label}
                </span>
                <span className="text-center" role="cell">
                  <DecisionGradeBadge presentation={item.basePresentation} />
                </span>
                <span className="text-center" role="cell">
                  <DecisionGradeBadge presentation={item.targetPresentation} />
                </span>
              </div>
            ))}
          </div>

          {unchanged.length > 0 && (
            <details className="text-xs">
              <summary className="text-muted cursor-pointer">
                {t("pages.runs.compare.visual.unchangedPasses", {
                  count: unchanged.length,
                })}
              </summary>
              <div className="mt-1.5 space-y-1" role="rowgroup">
                {unchanged.map((item) => (
                  <div
                    key={item.passId}
                    className="text-muted grid grid-cols-3 items-center gap-2 px-2 py-1"
                    role="row"
                  >
                    <span role="cell">{item.label}</span>
                    <span className="text-center" role="cell">
                      <DecisionGradeBadge
                        presentation={item.basePresentation}
                      />
                    </span>
                    <span className="text-center" role="cell">
                      <DecisionGradeBadge
                        presentation={item.targetPresentation}
                      />
                    </span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </Card>
  );
}
