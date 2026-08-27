import { expectNoA11yViolations } from "@/test/a11y";

import { DisputeBadge } from "./DisputeBadge";
import { issueTrustPresentation } from "./trust-glyphs";

describe("DisputeBadge accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <DisputeBadge
        presentation={issueTrustPresentation({
          dispute_status: "under_review",
          freshness: "current",
          verification_status: "pending",
        })}
      />,
    );
  });
});
