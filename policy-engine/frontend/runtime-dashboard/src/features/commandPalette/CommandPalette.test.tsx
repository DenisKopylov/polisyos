import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const {
  cycleDensityMock,
  navigateMock,
  toggleThemeMock,
  useGlobalShortcutMock,
} = vi.hoisted(() => ({
  cycleDensityMock: vi.fn(),
  navigateMock: vi.fn(),
  toggleThemeMock: vi.fn(),
  useGlobalShortcutMock: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock("@/shared/ui/Command", () => ({
  CommandDialog: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CommandInput: ({ placeholder }: { placeholder?: string }) => (
    <input aria-label={placeholder} />
  ),
  CommandList: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CommandEmpty: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CommandGroup: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CommandItem: ({
    children,
    onSelect,
  }: {
    children: React.ReactNode;
    onSelect?: () => void;
  }) => (
    <button type="button" onClick={onSelect}>
      {children}
    </button>
  ),
  CommandSeparator: () => <hr />,
  CommandShortcut: ({ children }: { children: React.ReactNode }) => (
    <span>{children}</span>
  ),
}));

vi.mock("@/app/providers/ThemeProvider", () => ({
  useTheme: () => ({
    resolvedTheme: "dark",
    toggleTheme: toggleThemeMock,
  }),
}));

vi.mock("@/app/providers/DensityProvider", () => ({
  useDensity: () => ({
    cycleDensity: cycleDensityMock,
    density: "comfortable",
  }),
}));

vi.mock("@/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock("@/lib/hooks", () => ({
  useGlobalShortcut: (...args: unknown[]) => useGlobalShortcutMock(...args),
}));

import { CommandPalette } from "./CommandPalette";

describe("CommandPalette", () => {
  beforeEach(() => {
    cycleDensityMock.mockReset();
    navigateMock.mockReset();
    toggleThemeMock.mockReset();
    useGlobalShortcutMock.mockReset();
  });

  it("routes theme toggles through the theme provider", async () => {
    const user = userEvent.setup();
    render(<CommandPalette />);

    await user.click(
      screen.getByRole("button", { name: /commandPalette\.toggleTheme/i }),
    );

    expect(toggleThemeMock).toHaveBeenCalledTimes(1);
  });

  it("routes density cycling through the density provider", async () => {
    const user = userEvent.setup();
    render(<CommandPalette />);

    await user.click(
      screen.getByRole("button", { name: /commandPalette\.cycleDensity/i }),
    );

    expect(cycleDensityMock).toHaveBeenCalledTimes(1);
  });
});
