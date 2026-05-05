import {
  BadgeCheck,
  CircleHelp,
  FlaskConical,
  TriangleAlert,
} from "lucide-react";

import type { ScenarioListPayload } from "@/api/validators";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

type ScenarioAssumption = NonNullable<
  ScenarioListPayload["scenarios"]
>[number]["assumptions"][number];

type AssumptionPillProps = {
  assumption: ScenarioAssumption;
  className?: string;
};

export function AssumptionPill({ assumption, className }: AssumptionPillProps) {
  const { t } = useI18n();
  const Icon =
    assumption.status === "observed_evidence"
      ? BadgeCheck
      : assumption.status === "disputed"
        ? TriangleAlert
        : assumption.status === "model_assumption"
          ? FlaskConical
          : CircleHelp;
  return (
    <span
      className={cn(
        "border-border bg-muted/20 inline-flex min-h-6 items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-semibold",
        assumption.status === "disputed" &&
          "border-[color-mix(in_srgb,var(--color-status-rejected)_30%,transparent)]",
        className,
      )}
      data-assumption-id={assumption.id}
      data-assumption-status={assumption.status}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      <span>{assumption.label}</span>
      <span className="text-muted">
        {t(`shared.ui.counterfactual.assumptionStatus.${assumption.status}`)}
      </span>
    </span>
  );
}
