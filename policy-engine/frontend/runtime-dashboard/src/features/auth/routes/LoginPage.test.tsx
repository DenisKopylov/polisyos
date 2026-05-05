import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

vi.mock("@/shared/i18n/LocaleProvider", async () => {
  const actual = await vi.importActual<typeof import("@/shared/i18n/LocaleProvider")>(
    "@/shared/i18n/LocaleProvider",
  );
  return {
    ...actual,
    useI18n: () => ({
      t: (key: string, payload?: Record<string, unknown>) =>
        payload ? `${key}:${JSON.stringify(payload)}` : key,
    }),
  };
});

import LoginPage from "@/features/auth/routes/LoginPage";

function renderLoginPage(
  initialEntry = "/login?next=%2Fruns%2Frun-1%2Foverview",
) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  it("renders the requested next route and retries local login flows", async () => {
    const user = userEvent.setup();
    const assignMock = vi.fn();
    const originalLocation = window.location;

    Object.defineProperty(window, "location", {
      configurable: true,
      value: { assign: assignMock } satisfies Partial<Location>,
    });

    try {
      renderLoginPage();

      expect(screen.getByTestId("login-page")).toBeInTheDocument();
      expect(
        screen.getByText(
          'pages.login.nextRoute:{"next":"/runs/run-1/overview"}',
        ),
      ).toBeInTheDocument();

      await user.click(
        screen.getByRole("button", { name: "pages.login.retry" }),
      );
      expect(assignMock).toHaveBeenCalledWith("/runs/run-1/overview");
    } finally {
      Object.defineProperty(window, "location", {
        configurable: true,
        value: originalLocation,
      });
    }
  });
});
