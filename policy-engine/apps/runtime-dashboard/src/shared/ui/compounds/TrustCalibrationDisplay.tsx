import type {
  QuantityUncertainty,
  QuantityValueOutput,
} from "@polisyos/runtime-api-client";

import { Glyph } from "@/shared/brand/Glyph";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import { Quantity } from "@/shared/ui/quantity";
import { Card } from "@polisyos/atlas-ui";

import { MethodologyBadge } from "./MethodologyBadge";

const LEVEL_LABEL = "Level";
const EXPECTED_LABEL = "Expected";

export type CalibrationRecord = {
  level: QuantityValueOutput;
  expectedCoverage: QuantityValueOutput;
  actualCoverage: QuantityValueOutput;
};

type TrustCalibrationDisplayProps = {
  methodology: QuantityUncertainty["method"];
  historicalAccuracy: QuantityValueOutput;
  totalPastAnalyses: number;
  calibrationRecords?: CalibrationRecord[];
  limitations?: string[];
  counterArguments?: string[];
  className?: string;
};

function Percentage({ value }: { value: QuantityValueOutput }) {
  return (
    <Quantity
      format="percent"
      provenanceMode="off"
      value={value}
      variant="dense"
    />
  );
}

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

  return (
    <Card className={cn("space-y-5", className)}>
      <h3 className="text-lg font-semibold">
        {t("shared.ui.trustCalibrationDisplay.title")}
      </h3>

      <div className="flex flex-wrap items-center gap-4">
        <div>
          <p className="text-muted text-xs font-semibold uppercase">
            {t("shared.ui.trustCalibrationDisplay.historicalAccuracyLabel")}
          </p>
          <div className="mt-1">
            <Percentage value={historicalAccuracy} />
          </div>
        </div>
        <div className="space-y-2">
          <MethodologyBadge methodology={methodology} />
          <p className="text-muted text-xs">
            {t("shared.ui.trustCalibrationDisplay.basedOn", {
              count: totalPastAnalyses,
            })}
          </p>
        </div>
      </div>

      {calibrationRecords.length > 0 ? (
        <div>
          <p className="text-muted mb-2 text-xs font-semibold tracking-wide uppercase">
            {t("shared.ui.trustCalibrationDisplay.calibrationCheck")}
          </p>
          <div className="space-y-2">
            {calibrationRecords.map((record, index) => (
              <dl
                key={`${record.level.metric_id ?? "level"}-${index}`}
                className="border-line grid gap-3 rounded-xl border p-3 sm:grid-cols-3"
              >
                <div>
                  <dt className="text-muted text-xs font-semibold uppercase">
                    {LEVEL_LABEL}
                  </dt>
                  <dd className="mt-1">
                    <Percentage value={record.level} />
                  </dd>
                </div>
                <div>
                  <dt className="text-muted text-xs font-semibold uppercase">
                    {EXPECTED_LABEL}
                  </dt>
                  <dd className="mt-1">
                    <Percentage value={record.expectedCoverage} />
                  </dd>
                </div>
                <div>
                  <dt className="text-muted text-xs font-semibold uppercase">
                    {t("shared.ui.counterfactual.actual")}
                  </dt>
                  <dd className="mt-1">
                    <Percentage value={record.actualCoverage} />
                  </dd>
                </div>
              </dl>
            ))}
          </div>
        </div>
      ) : null}

      {limitations.length > 0 ? (
        <div>
          <p className="text-muted mb-2 text-xs font-semibold tracking-wide uppercase">
            {t("shared.ui.trustCalibrationDisplay.knownLimitations")}
          </p>
          <ul className="space-y-1 text-sm">
            {limitations.map((limitation, index) => (
              <li
                key={`${limitation}-${index}`}
                className="flex items-start gap-2"
              >
                <Glyph
                  className="text-muted mt-0.5 shrink-0"
                  decorative
                  name="evidence"
                  size={12}
                />
                <span>{limitation}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {counterArguments.length > 0 ? (
        <div className="border-line rounded-2xl border p-4">
          <p className="mb-2 text-xs font-semibold tracking-wide uppercase">
            {t("shared.ui.trustCalibrationDisplay.counterArguments")}
          </p>
          <ul className="space-y-1 text-sm">
            {counterArguments.map((argument, index) => (
              <li
                key={`${argument}-${index}`}
                className="flex items-start gap-2"
              >
                <Glyph
                  className="text-muted shrink-0"
                  decorative
                  name="counterfactual"
                  size={12}
                />
                <span>{argument}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Card>
  );
}
