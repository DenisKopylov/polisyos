import { render, screen } from "@testing-library/react";

import { TemporalCapabilityBanner } from "./TemporalCapabilityBanner";

describe("TemporalCapabilityBanner", () => {
  it("uses one neutral capability-gap presentation", () => {
    render(
      <TemporalCapabilityBanner title="Unavailable" body="No owner fact" />,
    );
    expect(screen.getByRole("status").className).not.toMatch(/warning/u);
  });
});
