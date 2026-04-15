import { useState } from "react";

import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";
import { ConfidenceGauge } from "./ConfidenceGauge";
import { GradedErrorBar } from "./GradedErrorBar";
import { FrequencyDots } from "./FrequencyDots";

type UncertaintyDisplayMode = "intuitive" | "statistical";

type CIBand = { lower: number; upper: number; level: number };

type UncertaintyDisplayProps = {
  estimate: number;
  confidence: number;
  bands: CIBand[];
  methodology?: string;
  unit?: string;
  effectDirection?: "positive" | "negative" | "neutral";
  frequencyFraming?: string;
  defaultMode?: UncertaintyDisplayMode;
  className?: string;
};

export function UncertaintyDisplay({
  estimate,
  confidence,
  bands,
  methodology,
  unit = "",
  effectDirection = "neutral",
  frequencyFraming,
  defaultMode = "intuitive",
  className,
}: UncertaintyDisplayProps) {
  const { t } = useI18n();
  const [mode, setMode] = useState<UncertaintyDisplayMode>(defaultMode);

  const directionLabel =
    effectDirection === "positive"
      ? t("shared.uncertainty.direction.positive")
      : effectDirection === "negative"
        ? t("shared.uncertainty.direction.negative")
        : t("shared.uncertainty.direction.uncertain");

  const pct = Math.round(confidence * 100);
  const primaryBand = bands.find((b) => b.level >= 0.95) ?? bands.at(-1);

  const defaultFraming = primaryBand
    ? t("shared.uncertainty.defaultFraming.range", {
        confidence: pct,
        lower: `${primaryBand.lower.toFixed(2)}${unit}`,
        upper: `${primaryBand.upper.toFixed(2)}${unit}`,
      })
    : t("shared.uncertainty.defaultFraming.confidenceOnly", {
        confidence: pct,
      });

  return (
    <div
      className={cn(
        "border-border bg-card rounded-xl border p-5",
        className,
      )}
    >
      {/* Mode toggle */}
      <div className="mb-4 flex items-center justify-between">
        <h4 className="text-foreground text-sm font-semibold">
          {t("shared.uncertainty.title")}
        </h4>
        <div className="bg-muted inline-flex rounded-lg p-0.5">
          <button
            type="button"
            className={cn(
              "rounded-md px-3 py-1 text-xs font-medium transition-colors",
              mode === "intuitive"
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
            onClick={() => setMode("intuitive")}
          >
            {t("shared.uncertainty.mode.intuitive")}
          </button>
          <button
            type="button"
            className={cn(
              "rounded-md px-3 py-1 text-xs font-medium transition-colors",
              mode === "statistical"
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
            onClick={() => setMode("statistical")}
          >
            {t("shared.uncertainty.mode.statistical")}
          </button>
        </div>
      </div>

      {mode === "intuitive" ? (
        <div className="space-y-4">
          <div className="flex items-start gap-4">
            <ConfidenceGauge
              value={confidence}
              label={t("shared.uncertainty.confidence")}
            />
            <div className="flex-1 space-y-2">
              <p className="text-foreground text-lg font-semibold">
                {t("shared.uncertainty.policyEffect")}{" "}
                <span
                  className={cn(
                    effectDirection === "positive" && "text-success",
                    effectDirection === "negative" && "text-destructive",
                  )}
                >
                  {directionLabel}
                </span>
              </p>
              <p className="text-muted-foreground text-sm leading-relaxed">
                {frequencyFraming ?? defaultFraming}
              </p>
            </div>
          </div>
          <FrequencyDots
            highlighted={pct}
            label={frequencyFraming ?? defaultFraming}
            size="sm"
          />
        </div>
      ) : (
        <div className="space-y-4">
          <div className="space-y-1">
            <p className="text-foreground text-lg font-semibold">
              ATE: {estimate.toFixed(4)}{unit}
              {primaryBand && (
                <span className="text-muted-foreground text-sm font-normal">
                  {" "}
                  [{Math.round(primaryBand.level * 100)}% CI:{" "}
                  {primaryBand.lower.toFixed(4)}, {primaryBand.upper.toFixed(4)}
                  ]
                </span>
              )}
            </p>
            {methodology && (
              <p className="text-muted-foreground text-xs">
                {t("shared.uncertainty.method", { methodology })}
              </p>
            )}
          </div>
          <GradedErrorBar
            estimate={estimate}
            bands={bands}
            unit={unit}
          />
        </div>
      )}
    </div>
  );
}
