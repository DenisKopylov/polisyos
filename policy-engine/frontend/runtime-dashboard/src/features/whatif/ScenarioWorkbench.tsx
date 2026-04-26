import { useMemo } from "react";

import { useCounterfactualMetrics } from "@/api/hooks/useCounterfactualMetrics";
import { useRunScenarios } from "@/api/hooks/useScenarioCapabilities";
import { useMaybeCounterfactual } from "@/app/providers/useCounterfactual";
import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";
import {
  CounterfactualMetricChart,
  CounterfactualModeSwitch,
  ScenarioManifestPanel,
  ScenarioPicker,
} from "@/shared/ui/counterfactual";
import { CounterfactualQuantity } from "@/shared/ui/quantity";

import type { ImpactMetric, ParameterSpec } from "./types";
import { WhatIfPanel } from "./components/WhatIfPanel";
import { ScenarioInterventionEditor } from "./ScenarioInterventionEditor";
import { ScenarioValidationPanel } from "./ScenarioValidationPanel";

type ScenarioWorkbenchProps = {
  runId: string;
  parameters?: ParameterSpec[];
  onParametersChange?: (
    params: Record<string, number>,
  ) => Promise<ImpactMetric[]> | ImpactMetric[];
  className?: string;
};

export function ScenarioWorkbench({
  runId,
  parameters = [],
  onParametersChange,
  className,
}: ScenarioWorkbenchProps) {
  const { t } = useI18n();
  const counterfactual = useMaybeCounterfactual();
  const scenariosQuery = useRunScenarios(runId);
  const scenarios = scenariosQuery.data?.scenarios ?? [];
  const selectedScenario =
    scenarios.find((scenario) => scenario.id === counterfactual?.scenarioId) ??
    scenarios[0] ??
    null;
  const selectedScenarioId =
    counterfactual?.scenarioId ?? selectedScenario?.id ?? null;
  const metricsQuery = useCounterfactualMetrics(runId, {
    scenarioScope: {
      scenarioId: selectedScenarioId,
      mode: counterfactual?.mode ?? "actual",
    },
    enabled: Boolean(selectedScenarioId),
  });
  const metrics = useMemo(
    () => Object.values(metricsQuery.data?.metrics ?? {}),
    [metricsQuery.data?.metrics],
  );
  const unsupportedReasons =
    scenarios.length === 0 && !scenariosQuery.isLoading
      ? [t("shared.ui.counterfactual.noScenarioSupport")]
      : [];

  return (
    <section className={cn("space-y-4", className)}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">
            {t("shared.ui.counterfactual.workbench")}
          </h2>
          <p className="text-muted text-sm">
            {t("shared.ui.counterfactual.workbenchSubtitle")}
          </p>
        </div>
        <CounterfactualModeSwitch />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.2fr)]">
        <div className="space-y-4">
          <ScenarioPicker
            disabledReason={unsupportedReasons[0]}
            scenarios={scenarios}
            value={selectedScenarioId}
          />
          {selectedScenario ? (
            <>
              <ScenarioManifestPanel scenario={selectedScenario} />
              {selectedScenario.interventions.map((intervention) => (
                <ScenarioInterventionEditor
                  key={`${intervention.field}:${intervention.operator}`}
                  intervention={intervention}
                />
              ))}
            </>
          ) : null}
          <ScenarioValidationPanel
            scenario={selectedScenario}
            unsupportedReasons={unsupportedReasons}
          />
        </div>

        <div className="space-y-3">
          <h3 className="text-sm font-semibold">
            {t("shared.ui.counterfactual.metrics")}
          </h3>
          {metricsQuery.isLoading ? (
            <p className="text-muted text-sm">
              {t("shared.ui.counterfactual.loadingMetrics")}
            </p>
          ) : null}
          {!metricsQuery.isLoading && metrics.length === 0 ? (
            <p className="text-muted text-sm">
              {t("shared.ui.counterfactual.noMetrics")}
            </p>
          ) : null}
          <div className="grid gap-2">
            {metrics.map((metric) => (
              <div
                key={metric.metric_id}
                className="border-border space-y-2 rounded-md border p-2"
              >
                <CounterfactualMetricChart
                  metric={metric}
                  assumptions={selectedScenario?.assumptions ?? []}
                />
                <CounterfactualQuantity value={metric} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {parameters.length ? (
        <WhatIfPanel
          baseRunId={runId}
          parameters={parameters}
          onParametersChange={onParametersChange}
        />
      ) : null}
    </section>
  );
}
