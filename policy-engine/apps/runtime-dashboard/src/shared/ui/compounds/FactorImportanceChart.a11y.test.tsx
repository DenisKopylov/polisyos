import { expectNoA11yViolations } from "@/test/a11y";

import { FactorImportanceChart } from "./FactorImportanceChart";

describe("FactorImportanceChart accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <FactorImportanceChart
        factors={[
          { direction: "positive", importance: 0.32, label: "Eligibility" },
          { direction: "negative", importance: -0.18, label: "Delay" },
        ]}
      />,
    );
  });
});
