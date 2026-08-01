import { describe, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { DualSlider } from "./DualSlider";

describe("DualSlider accessibility", () => {
  it("has no WCAG AA axe violations", async () => {
    await expectNoA11yViolations(
      <DualSlider
        baselineValue={10}
        label="Policy cost"
        max={20}
        min={0}
        onScenarioChange={vi.fn()}
        scenarioValue={12}
      />,
    );
  });
});
