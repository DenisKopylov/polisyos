import { expectNoA11yViolations } from "@/test/a11y";

import { Input } from "@polisyos/atlas-ui";

describe("Input accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <Input aria-label="Run query" placeholder="Search runs" />,
    );
  });
});
