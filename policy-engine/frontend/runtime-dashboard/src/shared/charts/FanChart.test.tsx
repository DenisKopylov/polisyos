import { render, screen } from "@testing-library/react";

import { FanChart } from "@/shared/charts/FanChart";

describe("FanChart", () => {
  it("renders fan labels and as-of marker", () => {
    render(
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
});
