import { expectNoA11yViolations } from "@/test/a11y";

import { AuthorBadge } from "./AuthorBadge";

describe("AuthorBadge accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <AuthorBadge
        author="citation"
        reviewedByHuman
        sourceHref="#evidence-bundle"
        sourceRef="Evidence bundle EB-42"
      />,
    );
  });
});
