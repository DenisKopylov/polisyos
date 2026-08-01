import type { ReactNode } from "react";
import { AlertTriangle, Clock3, GitBranch, UserRound } from "lucide-react";

import type { ScenarioManifest } from "@polisyos/runtime-api-client";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

import { AssumptionPill } from "./AssumptionPill";
import { CounterfactualBadge } from "./CounterfactualBadge";

type ScenarioManifestPresentation = Pick<
  ScenarioManifest,
  | "assumptions"
  | "author"
  | "baseline_run_id"
  | "computed_at"
  | "known_limitations"
  | "model_family"
  | "policy_question"
  | "stale_reasons"
  | "status"
>;

type ScenarioManifestPanelProps = {
  scenario: ScenarioManifestPresentation;
  className?: string;
};

export function ScenarioManifestPanel({
  scenario,
  className,
}: ScenarioManifestPanelProps) {
  const { t } = useI18n();
  return (
    <section
      className={cn("border-border space-y-3 rounded-md border p-3", className)}
      aria-label={t("shared.ui.counterfactual.manifest")}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">{scenario.policy_question}</h3>
          <p className="text-muted text-xs">
            {t("shared.ui.counterfactual.baselineRun", {
              runId: scenario.baseline_run_id,
            })}
          </p>
        </div>
        <CounterfactualBadge
          mode="actual_vs_scenario"
          status={scenario.status}
        />
      </div>

      <dl className="grid gap-2 text-xs sm:grid-cols-3">
        <InfoItem
          icon={<UserRound className="size-3.5" aria-hidden="true" />}
          label={t("shared.ui.counterfactual.author")}
          value={scenario.author}
        />
        <InfoItem
          icon={<GitBranch className="size-3.5" aria-hidden="true" />}
          label={t("shared.ui.counterfactual.model")}
          value={scenario.model_family}
        />
        <InfoItem
          icon={<Clock3 className="size-3.5" aria-hidden="true" />}
          label={t("shared.ui.counterfactual.computedAt")}
          value={formatInstant(scenario.computed_at, t("common.unknown"))}
        />
      </dl>

      <div className="space-y-1.5">
        <p className="text-xs font-semibold">
          {t("shared.ui.counterfactual.assumptions")}
        </p>
        <div className="flex flex-wrap gap-1.5">
          {scenario.assumptions.map((assumption) => (
            <AssumptionPill key={assumption.id} assumption={assumption} />
          ))}
        </div>
      </div>

      {scenario.stale_reasons?.length ? (
        <div className="flex gap-2 rounded-md border border-[color-mix(in_srgb,var(--color-status-pending)_34%,transparent)] p-2 text-xs">
          <AlertTriangle className="size-4 shrink-0 text-[var(--color-status-pending)]" />
          <div>
            <p className="font-semibold">
              {t("shared.ui.counterfactual.staleReasons")}
            </p>
            <p className="text-muted">{scenario.stale_reasons.join(", ")}</p>
          </div>
        </div>
      ) : null}

      {scenario.known_limitations?.length ? (
        <div className="space-y-1 text-xs">
          <p className="font-semibold">
            {t("shared.ui.counterfactual.knownLimitations")}
          </p>
          <ul className="text-muted list-inside list-disc">
            {scenario.known_limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function InfoItem({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="bg-muted/20 rounded-md p-2">
      <dt className="text-muted flex items-center gap-2">
        {icon}
        {label}
      </dt>
      <dd className="mt-0.5 font-medium">{value}</dd>
    </div>
  );
}

function formatInstant(value: string | null | undefined, fallback: string) {
  if (!value) {
    return fallback;
  }
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) {
    return fallback;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(instant);
}
