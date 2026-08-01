import { describe, it } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { CounterfactualDelta } from "./CounterfactualDelta";
import { counterfactualMetric } from "./counterfactualTestData";

describe("CounterfactualDelta accessibility", () => {
  it("has no WCAG AA axe violations", async () => {
    await expectNoA11yViolations(
      <CounterfactualDelta value={counterfactualMetric.delta} />,
    );
  });
});
