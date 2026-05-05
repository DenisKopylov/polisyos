import { useMemo, useState } from "react";

import CalibrationReport from "@/features/artifacts/components/simulation/CalibrationReport";
import DistributionalPanel from "@/features/artifacts/components/simulation/DistributionalPanel";
import MetricsPanel from "@/features/artifacts/components/simulation/MetricsPanel";
import UncertaintyOverlay from "@/features/artifacts/components/simulation/UncertaintyOverlay";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { normalizeSimulationPayload } from "@/shared/lib/domain/simulation";
import { UncertaintyBand } from "@/shared/charts";

type SimulationResultsViewerProps = {
  artifactKind: string;
  preview: unknown;
};

export default function SimulationResultsViewer({
  artifactKind,
  preview,
}: SimulationResultsViewerProps) {
  const { t } = useI18n();
  const model = useMemo(
    () => normalizeSimulationPayload(artifactKind, preview),
    [artifactKind, preview],
  );

  const uncertaintyMethods = useMemo(() => {
    if (!model) {
      return ["auto"];
    }
    const candidates = new Set<string>(["auto"]);
    if (model.calibration?.uncertaintyMethod) {
      candidates.add(model.calibration.uncertaintyMethod);
    }
    if (model.envelope?.propagationMethod) {
      candidates.add(model.envelope.propagationMethod);
    }
    return Array.from(candidates);
  }, [model]);

  const [showUncertainty, setShowUncertainty] = useState(true);
  const [selectedMethod, setSelectedMethod] = useState("auto");

  if (!model) {
    return (
      <div className="bg-canvas/40 border-line rounded-xl border border-dashed p-4">
        <h3 className="mb-1 text-lg font-semibold">
          {t("pages.artifacts.simulation.viewer.title")}
        </h3>
        <p className="text-muted text-sm">
          {t("pages.artifacts.simulation.viewer.invalidPayload")}
        </p>
      </div>
    );
  }

  const hasOverlay =
    Object.keys(model.boundsByMetric).length > 0 ||
    model.envelope !== null ||
    model.calibration?.uncertaintyMethod;

  return (
    <div className="space-y-4">
      <section className="border-line bg-panel rounded-xl border p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-lg font-semibold">
            {t("pages.artifacts.simulation.viewer.resultsTitle")}
          </h3>
          <p className="text-muted text-sm">
            {t("pages.artifacts.simulation.viewer.source", {
              source: model.sourceKind,
            })}
          </p>
        </div>

        {hasOverlay ? (
          <div className="mt-3">
            <UncertaintyOverlay
              enabled={showUncertainty}
              onToggle={setShowUncertainty}
              methods={uncertaintyMethods}
              selectedMethod={selectedMethod}
              onMethodChange={setSelectedMethod}
            />
          </div>
        ) : null}

        {model.envelope ? (
          <div className="border-line bg-canvas/30 mt-3 space-y-3 rounded-xl border p-3">
            {model.envelope.pointEstimate !== null &&
            model.envelope.ciLower !== null &&
            model.envelope.ciUpper !== null ? (
              <UncertaintyBand
                estimate={model.envelope.pointEstimate}
                bands={[
                  {
                    lower: model.envelope.ciLower,
                    upper: model.envelope.ciUpper,
                    level: model.envelope.ciLevel ?? 0.95,
                  },
                ]}
                label="Simulation envelope"
                identifiability="estimated"
                height={82}
              />
            ) : null}
            <div className="grid gap-2 md:grid-cols-3">
              <div className="bg-surface/60 border-line rounded-lg border p-2 text-sm">
                <p className="text-muted text-xs uppercase">
                  {t("pages.artifacts.simulation.viewer.pointEstimate")}
                </p>
                <p className="font-semibold">
                  {model.envelope.pointEstimate?.toFixed(6) ?? "-"}
                </p>
              </div>
              <div className="bg-surface/60 border-line rounded-lg border p-2 text-sm">
                <p className="text-muted text-xs uppercase">
                  {t("pages.artifacts.simulation.viewer.sourceLabel")}
                </p>
                <p className="font-semibold">{model.envelope.source ?? "-"}</p>
              </div>
              <div className="bg-surface/60 border-line rounded-lg border p-2 text-sm">
                <p className="text-muted text-xs uppercase">
                  {t("pages.artifacts.simulation.viewer.method")}
                </p>
                <p className="font-semibold">
                  {model.envelope.propagationMethod ?? "-"}
                </p>
              </div>
            </div>
          </div>
        ) : null}

        {model.notes.length > 0 ? (
          <ul className="text-muted mt-3 space-y-1 text-sm">
            {model.notes.map((note) => (
              <li key={note}>- {note}</li>
            ))}
          </ul>
        ) : null}
      </section>

      <MetricsPanel
        metrics={model.metrics}
        metricComparisons={model.metricComparisons}
        metricValidationFamilyAdjustment={
          model.metricValidationFamilyAdjustment
        }
        timeSeries={model.timeSeries}
        showUncertainty={showUncertainty && selectedMethod !== "none"}
      />
      <DistributionalPanel distributional={model.distributional} />
      <CalibrationReport calibration={model.calibration} />
    </div>
  );
}
