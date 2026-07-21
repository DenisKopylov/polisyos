import { expectNoA11yViolations } from "@/test/a11y";

import { VerificationStatus } from "./VerificationStatus";

describe("VerificationStatus accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <VerificationStatus
        metadata={{
          dispute_status: "none",
          freshness: "current",
          verification_status: "verified",
        }}
      />,
    );
  });
});
