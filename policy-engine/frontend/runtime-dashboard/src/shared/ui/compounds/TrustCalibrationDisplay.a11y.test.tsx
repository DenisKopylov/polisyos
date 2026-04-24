import { expectNoA11yViolations } from "@/test/a11y";

import { TrustCalibrationDisplay } from "./TrustCalibrationDisplay";

describe("TrustCalibrationDisplay accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <TrustCalibrationDisplay
        methodology="DiD"
        historicalAccuracy={0.82}
        totalPastAnalyses={48}
        calibrationRecords={[
          { actualCoverage: 0.78, expectedCoverage: 0.8, level: 0.8 },
          { actualCoverage: 0.93, expectedCoverage: 0.95, level: 0.95 },
        ]}
        limitations={["Historical calibration is domain-specific."]}
        counterArguments={["The current cohort is smaller than usual."]}
      />,
    );
  });
});
