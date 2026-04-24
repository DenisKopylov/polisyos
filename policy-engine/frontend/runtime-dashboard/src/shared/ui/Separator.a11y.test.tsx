import { expectNoA11yViolations } from "@/test/a11y";

import { Separator } from "./Separator";

describe("Separator accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <div className="space-y-3">
        <div>Overview</div>
        <Separator aria-label="Section divider" decorative={false} />
        <div>Governance</div>
      </div>,
    );
  });
});
