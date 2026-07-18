import { axe } from "vitest-axe";

import { renderWithProviders } from "@/test/render";

import { Button } from "@polisyos/atlas-ui";

describe("Button accessibility", () => {
  it("has no detectable accessibility violations as a link action", async () => {
    const { container } = renderWithProviders(
      <Button to="/runs" variant="ghost">
        Open runs
      </Button>,
    );

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
