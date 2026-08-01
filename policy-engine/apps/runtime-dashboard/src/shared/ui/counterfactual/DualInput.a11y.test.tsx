import { describe, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { DualInput } from "./DualInput";

describe("DualInput accessibility", () => {
  it("has no WCAG AA axe violations", async () => {
    await expectNoA11yViolations(
      <DualInput
        baselineValue={10}
        label="Policy cost"
        onScenarioChange={vi.fn()}
        scenarioValue={12}
      />,
    );
  });
});
