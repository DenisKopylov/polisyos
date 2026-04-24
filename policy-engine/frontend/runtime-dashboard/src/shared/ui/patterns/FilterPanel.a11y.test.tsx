import { expectNoA11yViolations } from "@/test/a11y";

import { FilterPanel } from "./FilterPanel";

describe("FilterPanel accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <FilterPanel
        title="Filters"
        description="Refine the visible evidence rows."
        actions={<button type="button">Reset</button>}
      >
        <label>
          Status
          <select>
            <option>All</option>
          </select>
        </label>
      </FilterPanel>,
    );
  });
});
