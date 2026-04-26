import { useState, type ComponentProps } from "react";

import { useMaybeTrustView } from "@/app/providers/useTrustView";
import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

import { ConfidenceGauge } from "./ConfidenceGauge";
import { FanChart } from "./FanChart";
import { FrequencyDots } from "./FrequencyDots";
import { GradedErrorBar } from "./GradedErrorBar";
import { HypotheticalOutcomePlot } from "./HypotheticalOutcomePlot";
import { QuantileDotplot } from "./QuantileDotplot";
import { UncertaintyBand } from "./UncertaintyBand";
import {
  shouldRenderUncertaintyMethodLabel,
  uncertaintyMethodTrustLabel,
} from "./uncertainty-rendering";

type UncertaintyDisplayMode = "intuitive" | "statistical";
type CIBand = { lower: number; upper: number; level: number };

type LegacyUncertaintyDisplayProps = {
  estimate: number;
  confidence: number;
  bands: CIBand[];
  methodology?: string;
  unit?: string;
  effectDirection?: "positive" | "negative" | "neutral";
  frequencyFraming?: string;
  defaultMode?: UncertaintyDisplayMode;
  className?: string;
  type?: undefined;
};

type UncertaintyDisplayProps =
  | LegacyUncertaintyDisplayProps
  | ({ type: "band" } & ComponentProps<typeof UncertaintyBand>)
  | ({ type: "fan" } & ComponentProps<typeof FanChart>)
  | ({ type: "dotplot" } & ComponentProps<typeof QuantileDotplot>)
  | ({ type: "hops" } & ComponentProps<typeof HypotheticalOutcomePlot>);

function LegacyUncertaintyDisplay({
  estimate,
  confidence,
  bands,
  methodology,
  unit = "",
  effectDirection = "neutral",
  frequencyFraming,
  defaultMode = "intuitive",
  className,
}: LegacyUncertaintyDisplayProps) {
  const { t } = useI18n();
  const trustView = useMaybeTrustView();
  const [mode, setMode] = useState<UncertaintyDisplayMode>(defaultMode);
  const directionLabel =
    effectDirection === "positive"
      ? t("shared.uncertainty.direction.positive")
      : effectDirection === "negative"
        ? t("shared.uncertainty.direction.negative")
        : t("shared.uncertainty.direction.uncertain");

  const pct = Math.round(confidence * 100);
  const primaryBand = bands.find((band) => band.level >= 0.95) ?? bands.at(-1);
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
        "border-border bg-card group rounded-xl border p-5",
        className,
      )}
    >
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
              {methodology &&
              shouldRenderUncertaintyMethodLabel({
                focused: true,
                mode: trustView?.mode ?? "off",
              }) ? (
                <p
                  className={cn(
                    "text-muted-foreground text-xs",
                    trustView?.mode === "compact" &&
                      "opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100",
                  )}
                >
                  {t("shared.uncertainty.method", {
                    methodology: uncertaintyMethodTrustLabel(methodology),
                  })}
                </p>
              ) : null}
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
              ATE: {estimate.toFixed(4)}
              {unit}
              {primaryBand ? (
                <span className="text-muted-foreground text-sm font-normal">
                  {" "}
                  {t("shared.charts.common.confidenceIntervalBracketed", {
                    confidence: Math.round(primaryBand.level * 100),
                    lower: primaryBand.lower.toFixed(4),
                    upper: primaryBand.upper.toFixed(4),
                  })}
                </span>
              ) : null}
            </p>
            {methodology ? (
              <p className="text-muted-foreground text-xs">
                {t("shared.uncertainty.method", { methodology })}
              </p>
            ) : null}
          </div>
          <GradedErrorBar estimate={estimate} bands={bands} unit={unit} />
        </div>
      )}
    </div>
  );
}

export function UncertaintyDisplay(props: UncertaintyDisplayProps) {
  if (!("type" in props) || props.type === undefined) {
    return <LegacyUncertaintyDisplay {...props} />;
  }

  if (props.type === "band") {
    const { type: _type, ...bandProps } = props;
    return <UncertaintyBand {...bandProps} />;
  }
  if (props.type === "fan") {
    const { type: _type, ...fanProps } = props;
    return <FanChart {...fanProps} />;
  }
  if (props.type === "dotplot") {
    const { type: _type, ...dotplotProps } = props;
    return <QuantileDotplot {...dotplotProps} />;
  }

  const { type: _type, ...hopsProps } = props;
  return <HypotheticalOutcomePlot {...hopsProps} />;
}
