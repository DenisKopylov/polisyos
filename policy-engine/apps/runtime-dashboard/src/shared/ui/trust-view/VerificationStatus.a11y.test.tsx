import { expectNoA11yViolations } from "@/test/a11y";

import { VerificationStatus } from "./VerificationStatus";
import { issueTrustPresentation } from "./trust-glyphs";

describe("VerificationStatus accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <VerificationStatus
        presentation={issueTrustPresentation({
          dispute_status: "none",
          freshness: "current",
          hash: "sha256:content-bound",
          verification_method: "content_hash",
          verification_status: "verified",
          verified_by: "runtime-verifier",
        })}
      />,
    );
  });
});
