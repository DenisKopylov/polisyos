import { describe, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { DualSelector } from "./DualSelector";

describe("DualSelector accessibility", () => {
  it("has no WCAG AA axe violations", async () => {
    await expectNoA11yViolations(
      <DualSelector
        baselineValue="baseline"
        label="Policy regime"
        onScenarioChange={vi.fn()}
        options={[
          { label: "Baseline", value: "baseline" },
          { label: "Scenario", value: "scenario" },
        ]}
        scenarioValue="scenario"
      />,
    );
  });
});
