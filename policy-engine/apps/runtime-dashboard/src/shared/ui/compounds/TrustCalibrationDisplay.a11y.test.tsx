import { expectNoA11yViolations } from "@/test/a11y";

import { TrustCalibrationDisplay } from "./TrustCalibrationDisplay";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";

function quantity(metricId: string, point: number) {
  return untracedDecisionQuantity({ metricId, point });
}

describe("TrustCalibrationDisplay accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <TrustCalibrationDisplay
        methodology="DiD"
        historicalAccuracy={quantity("test.trust.accuracy", 0.82)}
        totalPastAnalyses={48}
        calibrationRecords={[
          {
            actualCoverage: quantity("test.coverage.actual.80", 0.78),
            expectedCoverage: quantity("test.coverage.expected.80", 0.8),
            level: quantity("test.coverage.level.80", 0.8),
          },
          {
            actualCoverage: quantity("test.coverage.actual.95", 0.93),
            expectedCoverage: quantity("test.coverage.expected.95", 0.95),
            level: quantity("test.coverage.level.95", 0.95),
          },
        ]}
        limitations={["Historical calibration is domain-specific."]}
        counterArguments={["The current cohort is smaller than usual."]}
      />,
    );
  });
});
