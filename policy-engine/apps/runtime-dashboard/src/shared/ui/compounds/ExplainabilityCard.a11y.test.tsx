import { expectNoA11yViolations } from "@/test/a11y";

import { ExplainabilityCard } from "./ExplainabilityCard";

describe("ExplainabilityCard accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <ExplainabilityCard
        level="summary"
        verdict={{
          confidence: 0.84,
          status: "approved",
          summary: "The model explains the recommendation with stable factors.",
        }}
        methodology="DiD"
        keyFactors={[
          { direction: "positive", label: "Coverage", value: "+0.12" },
          { direction: "negative", label: "Cost", value: "-0.04" },
        ]}
        governance={{
          blockers: ["Requires human review"],
          failed: 1,
          passed: 5,
          warnings: 1,
        }}
        expandTo="deep"
      />,
    );
  });
});
