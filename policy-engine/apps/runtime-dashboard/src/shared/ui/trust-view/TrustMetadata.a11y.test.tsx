import { expectNoA11yViolations } from "@/test/a11y";

import { TrustMetadata } from "./TrustMetadata";

describe("TrustMetadata accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <TrustMetadata
        metadata={{
          dispute_status: "none",
          freshness: "current",
          hash: "sha256:abcdef0123456789abcdef0123456789",
          verification_status: "verified",
          verified_by: "runtime-verifier",
        }}
        mode="expanded"
        subjectId="lineage-1"
      />,
    );
  });
});
