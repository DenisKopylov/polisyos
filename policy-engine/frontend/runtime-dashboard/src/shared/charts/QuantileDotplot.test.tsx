import { render, screen } from "@testing-library/react";

import {
  buildQuantileDots,
  calculateQuantile,
  QuantileDotplot,
} from "@/shared/charts/QuantileDotplot";

describe("QuantileDotplot", () => {
  it("calculates interpolated quantiles", () => {
    expect(calculateQuantile([1, 2, 3, 4], 0.5)).toBe(2.5);
    expect(calculateQuantile([1, 2, 3, 4], 0.1)).toBeCloseTo(1.3);
  });

  it("builds equal-probability dots", () => {
    const dots = buildQuantileDots([1, 2, 3, 4, 5, 8, 13, 21, 34, 55], 20);
    expect(dots).toHaveLength(20);
    expect(dots.some((dot) => dot.isTail)).toBe(true);
  });

  it("renders accessible labels for sampled outcomes", () => {
    render(
      <QuantileDotplot
        label="VAT multiplier distribution"
        samples={[0.09, 0.11, 0.14, 0.18, 0.22, 0.23, 0.24, 0.25, 0.29, 0.37]}
      />,
    );

    expect(screen.getByRole("img")).toHaveAccessibleName(
      /vat multiplier distribution/i,
    );
    expect(screen.getByText(/p50/i)).toBeInTheDocument();
  });
});
