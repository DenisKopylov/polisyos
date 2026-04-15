import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const {
  navigateMock,
  setDensityMock,
  toggleThemeMock,
  useGlobalShortcutMock,
} = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  setDensityMock: vi.fn(),
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
    toggleTheme: toggleThemeMock,
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

vi.mock("@/app/state/usePreferencesStore", () => ({
  usePreferencesStore: (selector: (state: {
    density: "comfortable";
    setDensity: typeof setDensityMock;
  }) => unknown) =>
    selector({
      density: "comfortable",
      setDensity: setDensityMock,
    }),
}));

import { CommandPalette } from "./CommandPalette";

describe("CommandPalette", () => {
  beforeEach(() => {
    navigateMock.mockReset();
    setDensityMock.mockReset();
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
});
