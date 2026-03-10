import { expectNoA11yViolations } from "@/test/a11y";

import { Select } from "./Select";

describe("Select accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <label className="block">
        <span>Status</span>
        <Select aria-label="Status" defaultValue="completed">
          <option value="completed">Completed</option>
          <option value="running">Running</option>
        </Select>
      </label>,
    );
  });
});
