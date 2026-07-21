import { describe, it } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { CounterfactualBadge } from "./CounterfactualBadge";

describe("CounterfactualBadge accessibility", () => {
  it("has no WCAG AA axe violations", async () => {
    await expectNoA11yViolations(
      <CounterfactualBadge mode="actual_vs_scenario" status="computed" />,
    );
  });
});
