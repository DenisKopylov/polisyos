import { expectNoA11yViolations } from "@/test/a11y";

import { ReasoningChainDisplay } from "./ReasoningChainDisplay";

describe("ReasoningChainDisplay accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <ReasoningChainDisplay
        steps={[
          {
            detail: "The operator asked for a policy comparison.",
            durationMs: 400,
            id: "question",
            summary: "Compare two interventions.",
            title: "Policy question",
            type: "question",
          },
          {
            durationMs: 900,
            id: "conclusion",
            summary: "Intervention A dominates on the primary metric.",
            title: "Recommendation",
            type: "conclusion",
          },
        ]}
      />,
    );
  });
});
