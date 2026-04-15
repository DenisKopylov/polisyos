import { useEffect, useCallback, useMemo } from "react";

import { cn } from "@/lib/utils";
import { Button, Card } from "@/shared/ui/primitives";

import type { ParameterSpec, ImpactMetric } from "../types";
import { useWhatIfStore } from "../state/useWhatIfStore";
import { ParameterSlider } from "./ParameterSlider";
import { ImpactPreview } from "./ImpactPreview";
import { ScenarioSnapshot } from "./ScenarioSnapshot";

type WhatIfPanelProps = {
  /** Run ID for the base run. */
  baseRunId: string;
  /** Parameter specifications from the policy spec. */
  parameters: ParameterSpec[];
  /**
   * Callback invoked when parameters change.
   * Should return projected impact metrics (can be async for server-side).
   */
  onParametersChange?: (
    params: Record<string, number>,
  ) => Promise<ImpactMetric[]> | ImpactMetric[];
  /** Navigate to comparison view for a saved scenario. */
  onCompareScenario?: (scenarioId: string) => void;
  /** Open full run with these parameters. */
  onLaunchRun?: (params: Record<string, number>) => void;
  className?: string;
};

export function WhatIfPanel({
  baseRunId,
  parameters,
  onParametersChange,
  onCompareScenario,
  onLaunchRun,
  className,
}: WhatIfPanelProps) {
  const {
    currentParameters,
    currentImpact,
    setBaseRunId,
    setParameter,
    resetParameters,
    setCurrentImpact,
  } = useWhatIfStore();

  // Sort parameters: high sensitivity first
  const sortedParams = useMemo(
    () =>
      [...parameters].sort(
        (a, b) => b.sensitivityPriority - a.sensitivityPriority,
      ),
    [parameters],
  );

  // Initialize on mount
  useEffect(() => {
    setBaseRunId(baseRunId);
    // Only set defaults if no current params exist
    if (Object.keys(currentParameters).length === 0) {
      const defaults: Record<string, number> = {};
      for (const p of parameters) defaults[p.key] = p.defaultValue;
      resetParameters(defaults);
    }
  }, [baseRunId, currentParameters, parameters, resetParameters, setBaseRunId]);

  // Compute impact when parameters change
  useEffect(() => {
    if (!onParametersChange || Object.keys(currentParameters).length === 0) return;

    let cancelled = false;
    const run = () => {
      void Promise.resolve(onParametersChange(currentParameters)).then(
        (result) => {
          if (!cancelled) {
            setCurrentImpact(result);
          }
        },
      );
    };

    // Debounce: wait 150ms after last change
    const timer = setTimeout(run, 150);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [currentParameters, onParametersChange, setCurrentImpact]);

  const handleParameterChange = useCallback(
    (key: string, value: number) => {
      setParameter(key, value);
    },
    [setParameter],
  );

  const handleReset = useCallback(() => {
    const defaults: Record<string, number> = {};
    for (const p of parameters) defaults[p.key] = p.defaultValue;
    resetParameters(defaults);
  }, [parameters, resetParameters]);

  const hasChanges = useMemo(
    () =>
      parameters.some(
        (p) => (currentParameters[p.key] ?? p.defaultValue) !== p.defaultValue,
      ),
    [parameters, currentParameters],
  );

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header */}
      <Card className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold">What-If Analysis</h3>
            <p className="text-muted text-sm">
              Explore how parameter changes affect outcomes
            </p>
          </div>
          <div className="flex gap-2">
            {hasChanges && (
              <Button type="button" variant="ghost" onClick={handleReset}>
                Reset all
              </Button>
            )}
            {hasChanges && onLaunchRun && (
              <Button
                type="button"
                variant="primary"
                onClick={() => onLaunchRun(currentParameters)}
              >
                Launch with these parameters
              </Button>
            )}
          </div>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Left: Parameters */}
        <Card className="space-y-5">
          <h4 className="text-sm font-semibold">
            Parameters ({parameters.length})
          </h4>
          {sortedParams.map((spec) => (
            <ParameterSlider
              key={spec.key}
              spec={spec}
              value={currentParameters[spec.key] ?? spec.defaultValue}
              onChange={handleParameterChange}
            />
          ))}
        </Card>

        {/* Right: Impact + Scenarios */}
        <div className="space-y-4">
          <ImpactPreview metrics={currentImpact} />
          <ScenarioSnapshot onCompare={onCompareScenario} />
        </div>
      </div>
    </div>
  );
}
