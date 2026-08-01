import { expectNoA11yViolations } from "@/test/a11y";

import { DecisionCard } from "./DecisionCard";

describe("DecisionCard accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <DecisionCard
        title="Decision packet"
        subtitle="Generated from policy run"
        verdict="Approved"
        confidence="High confidence"
        summary="The intervention is ready for operator review."
        diagnostics={[{ kind: "ok", label: "Governance pass" }]}
        meta={[{ label: "Duration", value: "12 min" }]}
      />,
    );
  });
});
