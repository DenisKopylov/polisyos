import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import { Card } from "@/shared/ui/primitives";
import { AnimatedProgress, ConfidenceGauge } from "@/shared/charts";

export type CalibrationRecord = {
  level: number;
  expectedCoverage: number;
  actualCoverage: number;
};

type TrustCalibrationDisplayProps = {
  methodology: string;
  historicalAccuracy: number;
  totalPastAnalyses: number;
  calibrationRecords?: CalibrationRecord[];
  limitations?: string[];
  counterArguments?: string[];
  className?: string;
};

export function TrustCalibrationDisplay({
  methodology,
  historicalAccuracy,
  totalPastAnalyses,
  calibrationRecords = [],
  limitations = [],
  counterArguments = [],
  className,
}: TrustCalibrationDisplayProps) {
  const { t } = useI18n();
  const accuracyPct = Math.round(historicalAccuracy * 100);

  return (
    <Card className={cn("space-y-5", className)}>
      <h3 className="text-lg font-semibold">
        {t("shared.ui.trustCalibrationDisplay.title")}
      </h3>

      {/* Historical accuracy summary */}
      <div className="flex flex-wrap items-center gap-6">
        <ConfidenceGauge
          value={historicalAccuracy}
          label={t("shared.ui.trustCalibrationDisplay.historicalAccuracyLabel")}
          size={96}
        />
        <div className="space-y-1">
          <p className="text-sm">
            {t("shared.ui.trustCalibrationDisplay.summary", {
              accuracy: `${accuracyPct}%`,
              methodology,
            })}
          </p>
          <p className="text-muted text-xs">
            {t("shared.ui.trustCalibrationDisplay.basedOn", {
              count: totalPastAnalyses,
            })}
          </p>
        </div>
      </div>

      {/* Calibration table */}
      {calibrationRecords.length > 0 && (
        <div>
          <p className="text-muted mb-2 text-xs font-semibold tracking-wide uppercase">
            {t("shared.ui.trustCalibrationDisplay.calibrationCheck")}
          </p>
          <div className="space-y-2">
            {calibrationRecords.map((rec, index) => {
              const gap = Math.abs(rec.actualCoverage - rec.expectedCoverage);
              const wellCalibrated = gap < 0.05;
              return (
                <div key={`${rec.level}-${index}`} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium">
                      {t("shared.ui.trustCalibrationDisplay.intervalLabel", {
                        level: Math.round(rec.level * 100),
                      })}
                    </span>
                    <span
                      className={cn(
                        "font-semibold",
                        wellCalibrated
                          ? "text-[var(--color-status-approved)]"
                          : "text-[var(--color-status-pending)]",
                      )}
                    >
                      {t("shared.ui.trustCalibrationDisplay.actual", {
                        actual: `${Math.round(rec.actualCoverage * 100)}%`,
                      })}
                    </span>
                  </div>
                  <AnimatedProgress
                    value={rec.actualCoverage * 100}
                    colorByConfidence
                    height={6}
                    label={t(
                      "shared.ui.trustCalibrationDisplay.intervalLabel",
                      {
                        level: Math.round(rec.level * 100),
                      },
                    )}
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Limitations */}
      {limitations.length > 0 && (
        <div>
          <p className="text-muted mb-2 text-xs font-semibold tracking-wide uppercase">
            {t("shared.ui.trustCalibrationDisplay.knownLimitations")}
          </p>
          <ul className="space-y-1 text-sm">
            {limitations.map((lim, index) => (
              <li key={`${lim}-${index}`} className="flex items-start gap-2">
                <span className="text-muted mt-0.5">{"\u26A0"}</span>
                <span>{lim}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Counter-arguments */}
      {counterArguments.length > 0 && (
        <div className="rounded-2xl bg-[color-mix(in_srgb,var(--color-status-rejected)_6%,transparent)] p-4">
          <p className="mb-2 text-xs font-semibold tracking-wide text-[var(--color-status-rejected)] uppercase">
            {t("shared.ui.trustCalibrationDisplay.counterArguments")}
          </p>
          <ul className="space-y-1 text-sm">
            {counterArguments.map((arg, index) => (
              <li key={`${arg}-${index}`} className="flex items-start gap-2">
                <span className="text-[var(--color-status-rejected)]">
                  {"\u2717"}
                </span>
                <span>{arg}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
