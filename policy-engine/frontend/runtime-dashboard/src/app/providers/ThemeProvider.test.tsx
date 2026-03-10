/* eslint-disable testing-library/prefer-screen-queries */
import userEvent from "@testing-library/user-event";

import { useTheme } from "@/app/providers/ThemeProvider";
import { renderWithProviders } from "@/test/render";

function ThemeHarness() {
  const { resolvedTheme, theme, toggleTheme } = useTheme();

  return (
    <div>
      <p data-testid="theme-selection">{theme}</p>
      <p data-testid="theme-resolved">{resolvedTheme}</p>
      <button type="button" onClick={toggleTheme}>
        toggle
      </button>
    </div>
  );
}

describe("ThemeProvider", () => {
  it("cycles through system, dark, and light themes and applies data-theme", async () => {
    window.localStorage.removeItem("polisyos.runtime.theme");
    const user = userEvent.setup();
    const view = renderWithProviders(<ThemeHarness />);

    expect(view.getByTestId("theme-selection")).toHaveTextContent("system");
    expect(document.documentElement.dataset.theme).toBe("dark");

    await user.click(view.getByRole("button", { name: "toggle" }));
    expect(view.getByTestId("theme-selection")).toHaveTextContent("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");

    await user.click(view.getByRole("button", { name: "toggle" }));
    expect(view.getByTestId("theme-selection")).toHaveTextContent("light");
    expect(document.documentElement.dataset.theme).toBe("light");

    await user.click(view.getByRole("button", { name: "toggle" }));
    expect(view.getByTestId("theme-selection")).toHaveTextContent("system");
  });
});
