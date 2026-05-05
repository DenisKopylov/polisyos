import { useCallback, useMemo } from "react";

import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Slider } from "@/shared/ui/Slider";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/ui/Tooltip";

import type { ParameterSpec } from "../types";

type ParameterSliderProps = {
  spec: ParameterSpec;
  value: number;
  onChange: (key: string, value: number) => void;
  className?: string;
};

/**
 * Build a CSS gradient for the slider track that shows sensitivity zones.
 *
 * Green = stable, yellow = moderate, red = sensitive.
 */
function buildSensitivityGradient(spec: ParameterSpec): string | undefined {
  if (!spec.sensitivityZones || spec.sensitivityZones.length === 0) {
    // Fall back to a uniform gradient based on overall sensitivity priority
    if (spec.sensitivityPriority <= 0.3) return undefined; // low — use default
    const hue = spec.sensitivityPriority > 0.7 ? 0 : 45; // red or amber
    return `linear-gradient(90deg, hsl(130 40% 85%), hsl(${hue} 60% 85%))`;
  }

  const range = spec.max - spec.min || 1;
  const stops: string[] = ["hsl(130 40% 85%) 0%"];

  for (const zone of spec.sensitivityZones) {
    const startPct = ((zone.start - spec.min) / range) * 100;
    const endPct = ((zone.end - spec.min) / range) * 100;
    stops.push(`hsl(130 40% 85%) ${Math.max(0, startPct - 2)}%`);
    stops.push(`hsl(0 60% 85%) ${startPct}%`);
    stops.push(`hsl(0 60% 85%) ${endPct}%`);
    stops.push(`hsl(130 40% 85%) ${Math.min(100, endPct + 2)}%`);
  }

  stops.push("hsl(130 40% 85%) 100%");
  return `linear-gradient(90deg, ${stops.join(", ")})`;
}

export function ParameterSlider({
  spec,
  value,
  onChange,
  className,
}: ParameterSliderProps) {
  const { t } = useI18n();
  const step = spec.step ?? (spec.max - spec.min) / 100;
  const pct = ((value - spec.min) / (spec.max - spec.min || 1)) * 100;
  const isDefault = value === spec.defaultValue;

  const gradient = useMemo(() => buildSensitivityGradient(spec), [spec]);

  const handleChange = useCallback(
    (vals: number[]) => {
      onChange(spec.key, vals[0]);
    },
    [spec.key, onChange],
  );

  const handleReset = useCallback(() => {
    onChange(spec.key, spec.defaultValue);
  }, [spec.key, spec.defaultValue, onChange]);

  const sensitivityLabel =
    spec.sensitivityPriority >= 0.7
      ? t("whatIf.sensitivityZone.high")
      : spec.sensitivityPriority >= 0.4
        ? t("whatIf.sensitivityZone.medium")
        : t("whatIf.sensitivityZone.low");

  return (
    <div className={cn("space-y-2", className)}>
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">{spec.label}</span>
          {spec.description && (
            <TooltipProvider delayDuration={200}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="text-muted cursor-help text-xs">
                    {"\u24D8"}
                  </span>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-60">
                  <p className="text-xs">{spec.description}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
          {/* Sensitivity badge */}
          <span
            className={cn(
              "rounded-md px-1.5 py-0.5 text-[10px] font-semibold",
              spec.sensitivityPriority >= 0.7
                ? "bg-[var(--chart-alert)]/10 text-[var(--chart-alert)]"
                : spec.sensitivityPriority >= 0.4
                  ? "bg-[var(--chart-warning)]/10 text-[var(--chart-warning)]"
                  : "bg-[var(--chart-success)]/10 text-[var(--chart-success)]",
            )}
          >
            {sensitivityLabel}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-bold">
            {value.toFixed(step < 1 ? 2 : 0)}
            {spec.unit && (
              <span className="text-muted text-xs">{spec.unit}</span>
            )}
          </span>
          {!isDefault && (
            <button
              type="button"
              onClick={handleReset}
              className="text-muted text-xs underline decoration-dotted underline-offset-2 hover:text-inherit"
              aria-label={t("whatIf.resetToDefault")}
            >
              {t("whatIf.parameterSlider.reset")}
            </button>
          )}
        </div>
      </div>

      {/* Slider */}
      <Slider
        value={[value]}
        min={spec.min}
        max={spec.max}
        step={step}
        onValueChange={handleChange}
        trackGradient={gradient}
        aria-label={`${spec.label}: ${value}`}
      />

      {/* Range labels */}
      <div className="text-muted flex justify-between text-[10px]">
        <span>
          {spec.min}
          {spec.unit ?? ""}
        </span>
        {!isDefault && (
          <span className="text-muted/50">
            {t("whatIf.parameterSlider.defaultValue", {
              value: `${spec.defaultValue}${spec.unit ?? ""}`,
            })}
          </span>
        )}
        <span>
          {spec.max}
          {spec.unit ?? ""}
        </span>
      </div>
    </div>
  );
}
