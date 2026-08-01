import { expectNoA11yViolations } from "@/test/a11y";

import { ExplainabilityCard } from "./ExplainabilityCard";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";

describe("ExplainabilityCard accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <ExplainabilityCard
        level="summary"
        verdict={{
          confidence: untracedDecisionQuantity({
            metricId: "test.explainability.confidence",
            point: 0.84,
          }),
          decisionGrade: "approved",
          summary: "The model explains the recommendation with stable factors.",
        }}
        methodology="DiD"
        keyFactors={[
          { direction: "positive", label: "Coverage", value: "+0.12" },
          { direction: "negative", label: "Cost", value: "-0.04" },
        ]}
        governance={{
          blockers: [
            {
              code: "human_review_required",
              message: "Requires human review",
              severity: "blocking",
            },
          ],
          failed: 1,
          passed: 5,
          warnings: 1,
        }}
        expandTo="deep"
      />,
    );
  });
});
