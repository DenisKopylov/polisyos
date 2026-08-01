import { expectNoA11yViolations } from "@/test/a11y";

import { Checkbox } from "@polisyos/atlas-ui";

describe("Checkbox accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <div className="flex items-center gap-3 text-sm font-medium">
        <Checkbox
          id="checkbox-allow-explore-fallback"
          aria-labelledby="checkbox-allow-explore-fallback-label"
          defaultChecked
        />
        <span id="checkbox-allow-explore-fallback-label">
          Allow explore fallback
        </span>
      </div>,
    );
  });
});
