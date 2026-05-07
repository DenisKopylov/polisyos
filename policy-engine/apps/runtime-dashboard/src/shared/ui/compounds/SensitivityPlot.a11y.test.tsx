import { expectNoA11yViolations } from "@/test/a11y";

import { SensitivityPlot } from "./SensitivityPlot";

describe("SensitivityPlot accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <SensitivityPlot
        breakdownGamma={1.4}
        points={[
          { gamma: 1, lowerBound: 0.1, upperBound: 0.24 },
          { gamma: 1.5, lowerBound: 0.04, upperBound: 0.3 },
          { gamma: 2, lowerBound: -0.02, upperBound: 0.36 },
        ]}
      />,
    );
  });
});
