import { AlertTriangle, FlaskConical, GitCompareArrows } from "lucide-react";

import type { CounterfactualMode } from "@/app/providers/scenario-scope";
import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

import { counterfactualTokens } from "./counterfactual-colors";

type CounterfactualBadgeProps = {
  mode?: CounterfactualMode;
  status?: "draft" | "computed" | "stale" | "failed";
  className?: string;
};

export function CounterfactualBadge({
  mode = "actual",
  status,
  className,
}: CounterfactualBadgeProps) {
  const { t } = useI18n();
  const stale = status === "stale" || status === "failed";
  const Icon = stale
    ? AlertTriangle
    : mode === "actual_vs_scenario"
      ? GitCompareArrows
      : FlaskConical;
  return (
    <span
      className={cn(
        "inline-flex min-h-6 items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-semibold",
        stale
          ? counterfactualTokens.stale.className
          : counterfactualTokens.scenario.className,
        mode === "actual" && !status && counterfactualTokens.actual.className,
        className,
      )}
      data-counterfactual-mode={mode}
      data-scenario-status={status ?? "none"}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {status
        ? t(`shared.ui.counterfactual.status.${status}`)
        : t(`shared.ui.counterfactual.mode.${mode}`)}
    </span>
  );
}
