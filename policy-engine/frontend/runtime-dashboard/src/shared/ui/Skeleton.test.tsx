import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { MetricsSkeleton, PageSkeleton, PanelSkeleton } from "./Skeleton";

describe("Skeleton surfaces", () => {
  it("renders page and panel loading placeholders", () => {
    renderWithProviders(
      <div>
        <PageSkeleton />
        <PanelSkeleton rows={3} />
        <MetricsSkeleton count={2} />
      </div>,
    );

    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
    expect(document.querySelectorAll("[aria-hidden='true']")).toHaveLength(15);
  });
});
