import { expectNoA11yViolations } from "@/test/a11y";

import { ToggleButton } from "@polisyos/atlas-ui";

describe("ToggleButton accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <ToggleButton
        label="Reading view"
        pressed
        onPressedChange={() => undefined}
      />,
    );
  });
});
