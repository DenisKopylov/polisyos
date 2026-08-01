import { describe, it } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { AssumptionPill } from "./AssumptionPill";
import { scenario } from "./counterfactualTestData";

describe("AssumptionPill accessibility", () => {
  it("has no WCAG AA axe violations", async () => {
    await expectNoA11yViolations(
      <AssumptionPill assumption={scenario.assumptions[0]} />,
    );
  });
});
