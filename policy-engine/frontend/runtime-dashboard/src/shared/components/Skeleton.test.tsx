import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import {
  MetricsSkeleton,
  PageSkeleton,
  PanelSkeleton,
  SkeletonBlock,
} from "./Skeleton";

describe("shared Skeleton surfaces", () => {
  it("renders standalone blocks and page-level placeholders", () => {
    renderWithProviders(
      <div>
        <SkeletonBlock className="custom-block" />
        <PageSkeleton />
        <PanelSkeleton rows={2} />
        <MetricsSkeleton count={3} />
      </div>,
    );

    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
    expect(screen.getAllByTestId("skeleton-block")[0]).toHaveClass(
      "custom-block",
    );
    expect(screen.getAllByTestId("skeleton-block")).toHaveLength(18);
  });

  it("applies default row and metric counts", () => {
    renderWithProviders(
      <div>
        <PanelSkeleton />
        <MetricsSkeleton />
      </div>,
    );

    expect(screen.getAllByTestId("skeleton-block")).toHaveLength(18);
  });
});
