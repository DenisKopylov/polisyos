import { cn } from "@/lib/utils";
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
  const accuracyPct = Math.round(historicalAccuracy * 100);

  return (
    <Card className={cn("space-y-5", className)}>
      <h3 className="text-lg font-semibold">Trust Calibration</h3>

      {/* Historical accuracy summary */}
      <div className="flex flex-wrap items-center gap-6">
        <ConfidenceGauge
          value={historicalAccuracy}
          label="Historical accuracy"
          size={96}
        />
        <div className="space-y-1">
          <p className="text-sm">
            In past analyses with{" "}
            <span className="font-semibold">{methodology}</span>, predictions
            were within the 95% CI in{" "}
            <span className="font-bold">{accuracyPct}%</span> of cases.
          </p>
          <p className="text-muted text-xs">
            Based on {totalPastAnalyses} historical analyses.
          </p>
        </div>
      </div>

      {/* Calibration table */}
      {calibrationRecords.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
            Calibration check
          </p>
          <div className="space-y-2">
            {calibrationRecords.map((rec, index) => {
              const gap = Math.abs(rec.actualCoverage - rec.expectedCoverage);
              const wellCalibrated = gap < 0.05;
              return (
                <div key={`${rec.level}-${index}`} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium">
                      {Math.round(rec.level * 100)}% CI
                    </span>
                    <span
                      className={cn(
                        "font-semibold",
                        wellCalibrated
                          ? "text-[var(--color-status-approved)]"
                          : "text-[var(--color-status-pending)]",
                      )}
                    >
                      Actual: {Math.round(rec.actualCoverage * 100)}%
                    </span>
                  </div>
                  <AnimatedProgress
                    value={rec.actualCoverage * 100}
                    colorByConfidence
                    height={6}
                    label={`${Math.round(rec.level * 100)}% CI`}
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
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
            Known limitations
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
        <div className="bg-[color-mix(in_srgb,var(--color-status-rejected)_6%,transparent)] rounded-2xl p-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-status-rejected)]">
            Why you should NOT trust this
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
