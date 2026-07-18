import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import { Card } from "@polisyos/atlas-ui";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/ui/Tooltip";

export type GovernancePassStatus = "pass" | "fail" | "warning" | "skip";

export type GovernancePass = {
  id: string;
  label: string;
  status: GovernancePassStatus;
  detail?: string;
  durationMs?: number;
};

type GovernancePassGridProps = {
  passes: GovernancePass[];
  title?: string;
  className?: string;
};

const STATUS_COLOR: Record<GovernancePassStatus, string> = {
  pass: "bg-[var(--color-status-approved)]",
  fail: "bg-[var(--color-status-rejected)]",
  warning: "bg-[var(--color-status-pending)]",
  skip: "bg-[var(--line)]",
};

export function GovernancePassGrid({
  passes,
  title,
  className,
}: GovernancePassGridProps) {
  const { t } = useI18n();
  const statusLabel: Record<GovernancePassStatus, string> = {
    pass: t("shared.ui.governancePassGrid.status.pass"),
    fail: t("shared.ui.governancePassGrid.status.fail"),
    warning: t("shared.ui.governancePassGrid.status.warning"),
    skip: t("shared.ui.governancePassGrid.status.skip"),
  };
  const resolvedTitle = title ?? t("shared.ui.governancePassGrid.title");
  const counts = {
    pass: passes.filter((p) => p.status === "pass").length,
    fail: passes.filter((p) => p.status === "fail").length,
    warning: passes.filter((p) => p.status === "warning").length,
    skip: passes.filter((p) => p.status === "skip").length,
  };

  return (
    <Card className={cn("space-y-3", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">{resolvedTitle}</h3>
        <div className="flex gap-3 text-xs font-medium">
          {counts.pass > 0 && (
            <span className="text-[var(--color-status-approved)]">
              {t("shared.ui.governancePassGrid.countPassed", {
                count: counts.pass,
              })}
            </span>
          )}
          {counts.fail > 0 && (
            <span className="text-[var(--color-status-rejected)]">
              {t("shared.ui.governancePassGrid.countFailed", {
                count: counts.fail,
              })}
            </span>
          )}
          {counts.warning > 0 && (
            <span className="text-[var(--color-status-pending)]">
              {t("shared.ui.governancePassGrid.countWarnings", {
                count: counts.warning,
              })}
            </span>
          )}
          {counts.skip > 0 && (
            <span className="text-muted">
              {t("shared.ui.governancePassGrid.countSkipped", {
                count: counts.skip,
              })}
            </span>
          )}
        </div>
      </div>

      <TooltipProvider delayDuration={200}>
        <div className="grid grid-cols-5 gap-2 sm:grid-cols-10">
          {passes.map((pass) => (
            <Tooltip key={pass.id}>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className={cn(
                    "focus-visible:ring-ring flex aspect-square items-center justify-center rounded-xl transition-transform hover:scale-110 focus-visible:ring-2",
                    STATUS_COLOR[pass.status],
                    pass.status === "skip" ? "opacity-40" : "opacity-85",
                  )}
                  aria-label={t("shared.ui.governancePassGrid.itemLabel", {
                    label: pass.label,
                    status: statusLabel[pass.status],
                  })}
                >
                  <span className="text-[10px] font-bold text-white/90">
                    {pass.status === "pass"
                      ? "\u2713"
                      : pass.status === "fail"
                        ? "\u2717"
                        : pass.status === "warning"
                          ? "!"
                          : "\u2014"}
                  </span>
                </button>
              </TooltipTrigger>
              <TooltipContent side="top">
                <p className="font-semibold">{pass.label}</p>
                <p className="text-muted-foreground text-xs">
                  {pass.durationMs != null
                    ? t("shared.ui.governancePassGrid.statusWithDuration", {
                        durationMs: pass.durationMs,
                        status: statusLabel[pass.status],
                      })
                    : statusLabel[pass.status]}
                </p>
                {pass.detail && (
                  <p className="text-muted-foreground mt-1 max-w-48 text-xs">
                    {pass.detail}
                  </p>
                )}
              </TooltipContent>
            </Tooltip>
          ))}
        </div>
      </TooltipProvider>
    </Card>
  );
}
