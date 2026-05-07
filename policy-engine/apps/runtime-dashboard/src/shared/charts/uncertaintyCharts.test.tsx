import { screen } from "@testing-library/react";

import { FanChart } from "@/shared/charts/FanChart";
import { QuantileDotplot } from "@/shared/charts/QuantileDotplot";
import { UncertaintyBand } from "@/shared/charts/UncertaintyBand";
import { renderWithProviders } from "@/test/render";

describe("uncertainty charts", () => {
  it("renders scalar uncertainty bands through the shared wrapper", () => {
    renderWithProviders(
      <UncertaintyBand
        estimate={0.23}
        bands={[{ lower: 0.09, upper: 0.37, level: 0.95 }]}
        label="GDP effect"
        unit="%"
      />,
    );

    expect(screen.getAllByRole("img")[0]).toHaveAccessibleName(
      /point estimate 0\.230/i,
    );
    expect(screen.getAllByText("GDP effect").length).toBeGreaterThan(0);
  });

  it("renders a fan chart with an as-of marker", () => {
    renderWithProviders(
      <FanChart
        label="Employment rate forecast"
        asOfIndex={1}
        data={[
          { x: "Now", p10: 51, p25: 52, p50: 53, p75: 54, p90: 55 },
          { x: "+6m", p10: 50, p25: 51, p50: 53, p75: 55, p90: 56 },
          { x: "+12m", p10: 49, p25: 51, p50: 54, p75: 56, p90: 58 },
        ]}
      />,
    );

    expect(screen.getByText("Employment rate forecast")).toBeInTheDocument();
    expect(screen.getByText("AS OF")).toBeInTheDocument();
  });

  it("renders dotplot labels from sampled outcomes", () => {
    renderWithProviders(
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
