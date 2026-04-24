import { expectNoA11yViolations } from "@/test/a11y";

import { Textarea } from "./Textarea";

describe("Textarea accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <Textarea
        aria-label="Operator brief"
        placeholder="Describe the intervention and expected outcome"
      />,
    );
  });
});
