import { describe, it } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { CounterfactualMetricChart } from "./CounterfactualMetricChart";
import { counterfactualMetric, scenario } from "./counterfactualTestData";

describe("CounterfactualMetricChart accessibility", () => {
  it("has no WCAG AA axe violations", async () => {
    await expectNoA11yViolations(
      <CounterfactualMetricChart
        assumptions={scenario.assumptions}
        metric={counterfactualMetric}
      />,
    );
  });
});
