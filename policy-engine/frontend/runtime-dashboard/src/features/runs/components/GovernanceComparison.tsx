import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Card } from "@/shared/ui/primitives";
import { Badge } from "@/shared/ui/Badge";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type GovernanceComparisonItem = {
  passId: string;
  label: string;
  baseStatus: "pass" | "fail" | "warning" | "skip";
  targetStatus: "pass" | "fail" | "warning" | "skip";
};

type GovernanceComparisonProps = {
  items: GovernanceComparisonItem[];
  baseLabel?: string;
  targetLabel?: string;
  className?: string;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_BADGE_KIND: Record<string, "ok" | "fail" | "warn" | "neutral"> = {
  pass: "ok",
  fail: "fail",
  warning: "warn",
  skip: "neutral",
};

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
  const statusLabel: Record<GovernanceComparisonItem["baseStatus"], string> = {
    pass: t("shared.ui.governancePassGrid.status.pass"),
    fail: t("shared.ui.governancePassGrid.status.fail"),
    warning: t("shared.ui.governancePassGrid.status.warning"),
    skip: t("shared.ui.governancePassGrid.status.skip"),
  };
  const changed = items.filter((i) => i.baseStatus !== i.targetStatus);
  const unchanged = items.filter((i) => i.baseStatus === i.targetStatus);

  return (
    <Card className={cn("space-y-3 p-4", className)}>
      <h4 className="text-sm font-semibold">
        {t("pages.runs.compare.visual.governanceComparison")}
      </h4>

      {items.length === 0 ? (
        <p className="text-muted text-xs">
          {t("pages.runs.compare.visual.noGovernancePasses")}
        </p>
      ) : (
        <>
          {/* Table header */}
          <div className="text-muted grid grid-cols-3 gap-2 text-xs font-semibold">
            <span>{t("pages.runs.compare.visual.passColumn")}</span>
            <span className="text-center">{resolvedBaseLabel}</span>
            <span className="text-center">{resolvedTargetLabel}</span>
          </div>

          {/* Changed first */}
          {changed.map((item) => (
            <div
              key={item.passId}
              className="border-line grid grid-cols-3 items-center gap-2 rounded-lg border p-2"
              style={{
                borderLeftWidth: 3,
                borderLeftColor: "var(--chart-warning)",
              }}
            >
              <span className="text-xs font-medium">{item.label}</span>
              <span className="text-center">
                <Badge kind={STATUS_BADGE_KIND[item.baseStatus] ?? "neutral"}>
                  {statusLabel[item.baseStatus]}
                </Badge>
              </span>
              <span className="text-center">
                <Badge kind={STATUS_BADGE_KIND[item.targetStatus] ?? "neutral"}>
                  {statusLabel[item.targetStatus]}
                </Badge>
              </span>
            </div>
          ))}

          {/* Unchanged */}
          {unchanged.length > 0 && (
            <details className="text-xs">
              <summary className="text-muted cursor-pointer">
                {t("pages.runs.compare.visual.unchangedPasses", {
                  count: unchanged.length,
                })}
              </summary>
              <div className="mt-1.5 space-y-1">
                {unchanged.map((item) => (
                  <div
                    key={item.passId}
                    className="text-muted grid grid-cols-3 items-center gap-2 px-2 py-1"
                  >
                    <span>{item.label}</span>
                    <span className="text-center">
                      <Badge
                        kind={STATUS_BADGE_KIND[item.baseStatus] ?? "neutral"}
                      >
                        {statusLabel[item.baseStatus]}
                      </Badge>
                    </span>
                    <span className="text-center">—</span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </>
      )}
    </Card>
  );
}
