import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SmallMultiples, type SmallMultipleDatum } from "./SmallMultiples";

const regions = Array.from({ length: 8 }, (_, index) => `Region ${index + 1}`);
const sectors = Array.from({ length: 12 }, (_, index) => `Sector ${index + 1}`);

const data: SmallMultipleDatum[] = regions.flatMap((region, rowIndex) =>
  sectors.map((sector, columnIndex) => ({
    region,
    sector,
    status: "verified",
    value: rowIndex * 12 + columnIndex,
  })),
);

describe("SmallMultiples", () => {
  it("renders 8 regions by 12 sectors with stable axes", () => {
    render(
      <SmallMultiples
        data={data}
        selectedRegion="Region 4"
        valueDomain={[0, 120]}
        valueLabel="impact"
      />,
    );

    expect(screen.getByRole("grid")).toHaveAttribute("aria-rowcount", "8");
    expect(screen.getByRole("grid")).toHaveAttribute("aria-colcount", "12");
    expect(screen.getAllByRole("gridcell")).toHaveLength(96);
    expect(screen.getByText("120")).toBeInTheDocument();
  });

  it("supports keyboard traversal and selection through grid cells", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<SmallMultiples data={data} onSelect={onSelect} />);

    await user.tab();
    await user.keyboard("{Enter}");

    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ region: "Region 1", sector: "Sector 1" }),
    );
  });
});
