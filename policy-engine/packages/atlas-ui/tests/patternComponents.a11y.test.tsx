import { render } from "@testing-library/react";
import { axe } from "vitest-axe";

import { DetailLayout, FilterPanel } from "../src/index";

describe("pattern component accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    const { container } = render(
      <DetailLayout
        header={<h2>Decision detail</h2>}
        sidebar={<nav aria-label="Decision sections">Summary</nav>}
        content={
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
          </FilterPanel>
        }
        footer={<button type="button">Close</button>}
      />,
    );

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
