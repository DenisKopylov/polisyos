import { expectNoA11yViolations } from "@/test/a11y";

import { DisputeBadge } from "./DisputeBadge";

describe("DisputeBadge accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(<DisputeBadge status="under_review" />);
  });
});
