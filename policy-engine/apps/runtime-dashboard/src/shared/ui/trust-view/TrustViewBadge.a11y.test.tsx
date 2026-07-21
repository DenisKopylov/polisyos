import { expectNoA11yViolations } from "@/test/a11y";

import { TrustViewBadge } from "./TrustViewBadge";

describe("TrustViewBadge accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <TrustViewBadge
        metadata={{
          dispute_status: "none",
          freshness: "current",
          verification_status: "pending",
        }}
      />,
    );
  });
});
