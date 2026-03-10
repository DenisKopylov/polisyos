import { axe } from "vitest-axe";

import { renderWithProviders } from "@/test/render";

import { EmptyState } from "./EmptyState";

describe("EmptyState accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    const { container } = renderWithProviders(
      <EmptyState
        title="No data"
        body="This area is empty until the next run completes."
      />,
    );

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
