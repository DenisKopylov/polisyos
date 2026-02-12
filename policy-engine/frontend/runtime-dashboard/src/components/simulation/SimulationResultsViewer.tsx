import { useMemo, useState } from "react";

import CalibrationReport from "./CalibrationReport";
import DistributionalPanel from "./DistributionalPanel";
import MetricsPanel from "./MetricsPanel";
import UncertaintyOverlay from "./UncertaintyOverlay";
import { normalizeSimulationPayload } from "../../lib/domain/simulation";

type SimulationResultsViewerProps = {
  artifactKind: string;
  preview: unknown;
};

export default function SimulationResultsViewer({ artifactKind, preview }: SimulationResultsViewerProps) {
  const model = useMemo(() => normalizeSimulationPayload(artifactKind, preview), [artifactKind, preview]);

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
      <div className="rounded-xl border border-dashed border-line bg-canvas/40 p-4">
        <h3 className="mb-1 text-lg font-semibold">Simulation Results Viewer</h3>
        <p className="text-sm text-muted">Payload is not JSON object or cannot be parsed.</p>
      </div>
    );
  }

  const hasOverlay =
    Object.keys(model.boundsByMetric).length > 0
    || model.envelope !== null
    || model.calibration?.uncertaintyMethod;

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-line bg-panel p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-lg font-semibold">Simulation Results</h3>
          <p className="text-sm text-muted">Source: {model.sourceKind}</p>
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
          <div className="mt-3 grid gap-2 md:grid-cols-4">
            <div className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
              <p className="text-xs uppercase text-muted">Point Estimate</p>
              <p className="font-semibold">{model.envelope.pointEstimate?.toFixed(6) ?? "-"}</p>
            </div>
            <div className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
              <p className="text-xs uppercase text-muted">CI Lower</p>
              <p className="font-semibold">{model.envelope.ciLower?.toFixed(6) ?? "-"}</p>
            </div>
            <div className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
              <p className="text-xs uppercase text-muted">CI Upper</p>
              <p className="font-semibold">{model.envelope.ciUpper?.toFixed(6) ?? "-"}</p>
            </div>
            <div className="rounded-lg border border-line bg-canvas/30 p-2 text-sm">
              <p className="text-xs uppercase text-muted">Source</p>
              <p className="font-semibold">{model.envelope.source ?? "-"}</p>
            </div>
          </div>
        ) : null}

        {model.notes.length > 0 ? (
          <ul className="mt-3 space-y-1 text-sm text-muted">
            {model.notes.map((note) => (
              <li key={note}>- {note}</li>
            ))}
          </ul>
        ) : null}
      </section>

      <MetricsPanel
        metrics={model.metrics}
        timeSeries={model.timeSeries}
        showUncertainty={showUncertainty && selectedMethod !== "none"}
      />
      <DistributionalPanel distributional={model.distributional} />
      <CalibrationReport calibration={model.calibration} />
    </div>
  );
}
