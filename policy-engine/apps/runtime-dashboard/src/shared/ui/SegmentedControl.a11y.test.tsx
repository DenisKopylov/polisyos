import { expectNoA11yViolations } from "@/test/a11y";

import { SegmentedControl } from "@polisyos/atlas-ui";

describe("SegmentedControl accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <SegmentedControl
        ariaLabel="Theme"
        value="system"
        onValueChange={() => undefined}
        options={[
          { label: "Light", value: "light" },
          { label: "Dark", value: "dark" },
          { label: "System", value: "system" },
        ]}
      />,
    );
  });
});
