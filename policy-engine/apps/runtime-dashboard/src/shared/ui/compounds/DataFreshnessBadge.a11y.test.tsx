import { expectNoA11yViolations } from "@/test/a11y";

import { DataFreshnessBadge } from "./DataFreshnessBadge";

describe("DataFreshnessBadge accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <DataFreshnessBadge generatedAt="2026-04-23T10:00:00.000Z" />,
    );
  });
});
