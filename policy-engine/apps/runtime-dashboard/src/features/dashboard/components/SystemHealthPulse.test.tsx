import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import {
  createSystemHealthDisplayState,
  SystemHealthPulse,
} from "./SystemHealthPulse";

describe("SystemHealthPulse", () => {
  it("keeps telemetry health labels outside authority slots", () => {
    renderWithProviders(
      <SystemHealthPulse
        checks={[
          {
            id: "runtime",
            label: "Runtime",
            status: createSystemHealthDisplayState("healthy"),
          },
        ]}
      />,
    );

    expect(screen.getByTestId("system-health-overall")).toHaveAttribute(
      "data-authority-purpose",
      "telemetry",
    );
    expect(screen.getByRole("group", { name: "Runtime" })).toHaveAttribute(
      "data-health-state",
      "healthy",
    );
  });
});
