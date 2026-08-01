import { expectNoA11yViolations } from "@/test/a11y";

import { Select } from "@polisyos/atlas-ui";

describe("Select accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <Select aria-label="Status" defaultValue="completed">
        <option value="completed">Completed</option>
        <option value="running">Running</option>
      </Select>,
    );
  });
});
