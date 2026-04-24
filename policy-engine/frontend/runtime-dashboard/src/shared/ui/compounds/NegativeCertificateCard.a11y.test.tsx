import { expectNoA11yViolations } from "@/test/a11y";

import { NegativeCertificateCard } from "./NegativeCertificateCard";

describe("NegativeCertificateCard accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <NegativeCertificateCard
        blockingType="identification_failure"
        reason="The policy effect is not identifiable with the attached evidence."
        assumptions={["Parallel trends violated"]}
        suggestedExperiments={[
          {
            description: "Collect matched comparison observations.",
            feasibility: "medium",
            id: "exp_1",
            rationale: "Improves overlap.",
          },
        ]}
      />,
    );
  });
});
