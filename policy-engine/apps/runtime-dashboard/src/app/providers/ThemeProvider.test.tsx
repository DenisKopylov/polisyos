import type { PropsWithChildren } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { useFeatureFlagMock } = vi.hoisted(() => ({
  useFeatureFlagMock: vi.fn(),
}));

vi.mock("@/app/providers/FeatureFlagProvider", () => ({
  FeatureFlagProvider: ({ children }: PropsWithChildren) => children,
  useFeatureFlag: (...args: unknown[]) => useFeatureFlagMock(...args),
}));

import { ThemeProvider, useTheme } from "@/app/providers/ThemeProvider";

function ThemeHarness() {
  const { resolvedTheme, setTheme, theme, toggleTheme } = useTheme();

  return (
    <div>
      <p data-testid="theme-selection">{theme}</p>
      <p data-testid="theme-resolved">{resolvedTheme}</p>
      <button type="button" onClick={() => setTheme("system")}>
        set-system
      </button>
      <button type="button" onClick={toggleTheme}>
        header-toggle
      </button>
      <button type="button" onClick={toggleTheme}>
        palette-toggle
      </button>
    </div>
  );
}

function getThemeColorMeta() {
  // Theme color lives in document.head and has no user-facing Testing Library query.
  return document.querySelector('meta[name="theme-color"]');
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    useFeatureFlagMock.mockReset();
    useFeatureFlagMock.mockReturnValue(true);
    window.localStorage.removeItem("polisyos.runtime.theme");
  });

  it("toggles between explicit light and dark while preserving the system option", async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ThemeHarness />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("theme-selection")).toHaveTextContent("system");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(getThemeColorMeta()).toHaveAttribute("content", "#120f0e");

    await user.click(screen.getByRole("button", { name: "palette-toggle" }));
    expect(screen.getByTestId("theme-selection")).toHaveTextContent("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(getThemeColorMeta()).toHaveAttribute("content", "#fbf8f2");

    await user.click(screen.getByRole("button", { name: "header-toggle" }));
    expect(screen.getByTestId("theme-selection")).toHaveTextContent("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");

    await user.click(screen.getByRole("button", { name: "set-system" }));
    expect(screen.getByTestId("theme-selection")).toHaveTextContent("system");
    expect(document.documentElement.style.colorScheme).toBe("");
  });

  it("pins the UI to light mode when dark mode is disabled", async () => {
    useFeatureFlagMock.mockReturnValue(false);
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ThemeHarness />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("theme-selection")).toHaveTextContent("light");
    expect(screen.getByTestId("theme-resolved")).toHaveTextContent("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(getThemeColorMeta()).toHaveAttribute("content", "#fbf8f2");

    await user.click(screen.getByRole("button", { name: "header-toggle" }));

    expect(screen.getByTestId("theme-selection")).toHaveTextContent("light");
    expect(window.localStorage.getItem("polisyos.runtime.theme")).toBe("light");
  });
});
