import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const { useRunDetailsMock, useRunsMock } = vi.hoisted(() => ({
  useRunDetailsMock: vi.fn(),
  useRunsMock: vi.fn(),
}));

vi.mock("@/api/hooks/useRuns", () => ({
  useRuns: (...args: unknown[]) => useRunsMock(...args),
}));

vi.mock("@/api/hooks/useRunDetails", () => ({
  useRunDetails: (...args: unknown[]) => useRunDetailsMock(...args),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    label: (
      _namespace: string,
      value: string | null | undefined,
      fallback: string,
    ) => fallback ?? value ?? "",
    locale: "en",
    t: (key: string) => key,
  }),
}));

import { ClerkHistoryList } from "./ClerkHistoryList";
import ClerkRunSummaryPage from "../routes/ClerkRunSummaryPage";

describe("Clerk run status surfaces", () => {
  it("Clerk run surfaces render unseen RunSummary status verbatim and neutral", () => {
    useRunsMock.mockReturnValue({
      data: {
        runs: [
          {
            run_id: "run-unseen",
            started_at: "2026-03-10T10:00:00Z",
            status: "blocked_by_external_owner",
          },
          {
            run_id: "run-known-shaped",
            started_at: "2026-03-10T10:00:01Z",
            status: "completed",
          },
        ],
      },
      isLoading: false,
    });
    const history = render(
      <MemoryRouter>
        <ClerkHistoryList />
      </MemoryRouter>,
    );

    expect(screen.getByText("blocked_by_external_owner")).toHaveClass(
      "bg-white/65",
      "text-muted",
    );
    expect(screen.getByText("completed")).toHaveClass(
      "bg-white/65",
      "text-muted",
    );
    history.unmount();

    useRunDetailsMock.mockReturnValue({
      data: {
        run: {
          duration_ms: 1_000,
          run_id: "run-summary",
          started_at: "2026-03-10T10:00:00Z",
          status: "awaiting_external_attestation",
        },
      },
      isError: false,
      isLoading: false,
    });
    render(
      <MemoryRouter initialEntries={["/runs/run-summary"]}>
        <Routes>
          <Route path="/runs/:runId" element={<ClerkRunSummaryPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("awaiting_external_attestation")).toHaveClass(
      "bg-white/65",
      "text-muted",
    );
  });
});
