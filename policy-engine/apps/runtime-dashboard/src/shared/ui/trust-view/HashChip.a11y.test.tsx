import { expectNoA11yViolations } from "@/test/a11y";

import { HashChip } from "./HashChip";

describe("HashChip accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <HashChip
        hash="sha256:abcdef0123456789abcdef0123456789"
        label="Decision evidence"
        subjectId="lineage-1"
      />,
    );
  });
});
