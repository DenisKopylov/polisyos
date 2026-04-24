import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  DensityProvider,
  useDensity,
  SUPPORTED_DENSITIES,
} from "@/app/providers/DensityProvider";
import {
  PREFERENCES_STORAGE_KEY,
  resetPreferencesStore,
} from "@/app/state/usePreferencesStore";

function DensityHarness() {
  const { cycleDensity, density, setDensity } = useDensity();

  return (
    <div>
      <p data-testid="density-selection">{density}</p>
      <button type="button" onClick={cycleDensity}>
        cycle-density
      </button>
      <button type="button" onClick={() => setDensity("condensed")}>
        set-condensed
      </button>
    </div>
  );
}

describe("DensityProvider", () => {
  beforeEach(() => {
    window.localStorage.removeItem(PREFERENCES_STORAGE_KEY);
    resetPreferencesStore();
    document.documentElement.removeAttribute("data-density");
  });

  it("defaults to comfortable density and writes the dataset attribute", () => {
    render(
      <DensityProvider>
        <DensityHarness />
      </DensityProvider>,
    );

    expect(screen.getByTestId("density-selection")).toHaveTextContent(
      "comfortable",
    );
    expect(document.documentElement.dataset.density).toBe("comfortable");
  });

  it("cycles through comfortable, compact, and condensed densities", async () => {
    const user = userEvent.setup();
    render(
      <DensityProvider>
        <DensityHarness />
      </DensityProvider>,
    );

    for (const expected of [...SUPPORTED_DENSITIES.slice(1), "comfortable"]) {
      await user.click(screen.getByRole("button", { name: "cycle-density" }));
      expect(screen.getByTestId("density-selection")).toHaveTextContent(
        expected,
      );
      expect(document.documentElement.dataset.density).toBe(expected);
    }
  });

  it("persists an explicit density selection", async () => {
    const user = userEvent.setup();
    render(
      <DensityProvider>
        <DensityHarness />
      </DensityProvider>,
    );

    await user.click(screen.getByRole("button", { name: "set-condensed" }));

    const persisted = JSON.parse(
      window.localStorage.getItem(PREFERENCES_STORAGE_KEY) ?? "{}",
    ) as { state?: { density?: string } };

    expect(document.documentElement.dataset.density).toBe("condensed");
    expect(persisted.state?.density).toBe("condensed");
  });
});
