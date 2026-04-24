import { render, screen } from "@testing-library/react";

import { UncertaintyBand } from "@/shared/charts/UncertaintyBand";

describe("UncertaintyBand", () => {
  it("renders scalar intervals through the graded error bar wrapper", () => {
    render(
      <UncertaintyBand
        estimate={0.23}
        bands={[{ lower: 0.09, upper: 0.37, level: 0.95 }]}
        label="GDP effect"
      />,
    );

    expect(screen.getAllByText("GDP effect").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("img")[0]).toHaveAccessibleName(
      /point estimate 0\.230/i,
    );
  });

  it("renders requested series bands and disputed state", () => {
    render(
      <UncertaintyBand
        label="Employment outlook"
        disputed
        data={[
          {
            x: "Q1",
            y: 10,
            ci80Lower: 8,
            ci80Upper: 12,
            ci95Lower: 7,
            ci95Upper: 13,
          },
          {
            x: "Q2",
            y: 11,
            ci80Lower: 9,
            ci80Upper: 13,
            ci95Lower: 8,
            ci95Upper: 14,
          },
        ]}
        lower={0.1}
        upper={0.9}
      />,
    );

    expect(screen.getByText("Employment outlook")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /disputed/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("80% band")).toBeInTheDocument();
  });
});
