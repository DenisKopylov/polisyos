import { expectNoA11yViolations } from "@/test/a11y";

import { Switch } from "./Switch";

describe("Switch accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium">Live updates</span>
        <Switch aria-label="Live updates" defaultChecked />
      </div>,
    );
  });
});
