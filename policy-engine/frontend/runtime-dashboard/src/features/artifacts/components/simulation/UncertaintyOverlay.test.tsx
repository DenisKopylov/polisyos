import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import UncertaintyOverlay from "@/features/artifacts/components/simulation/UncertaintyOverlay";
import { renderWithProviders } from "@/test/render";

describe("UncertaintyOverlay", () => {
  it("renders a toggle button and segmented method controls for short method lists", async () => {
    const user = userEvent.setup();
    const onMethodChange = vi.fn();
    const onToggle = vi.fn();

    renderWithProviders(
      <UncertaintyOverlay
        enabled
        onToggle={onToggle}
        methods={["auto", "bootstrap", "fan"]}
        selectedMethod="auto"
        onMethodChange={onMethodChange}
      />,
    );

    const toggleButton = screen.getByRole("button", {
      name: "Show uncertainty bounds",
    });
    expect(toggleButton).toHaveAttribute("aria-pressed", "true");

    await user.click(toggleButton);
    expect(onToggle).toHaveBeenCalledWith(false);

    await user.click(screen.getByRole("radio", { name: "bootstrap" }));
    expect(onMethodChange).toHaveBeenCalledWith("bootstrap");
  });
});
