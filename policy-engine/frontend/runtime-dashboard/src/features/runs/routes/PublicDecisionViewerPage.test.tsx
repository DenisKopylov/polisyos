import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { buildSignedPublicDecisionPacket } from "@/features/runs/domain/publicationPacket";

import PublicDecisionViewerPage from "./PublicDecisionViewerPage";

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) =>
      params?.reason ? `${key}:${params.reason}` : key,
  }),
}));

describe("PublicDecisionViewerPage", () => {
  it("renders a verified signed public decision without API context", async () => {
    const packet = buildSignedPublicDecisionPacket({
      decisionScore: 0.74,
      runId: "public-run",
    });

    render(
      <MemoryRouter initialEntries={[packet.publicUrlPath]}>
        <Routes>
          <Route
            path="/public/decisions/:signedId"
            element={<PublicDecisionViewerPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByTestId("publication-packet-panel"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("signed-public-summary")).toBeInTheDocument();
    expect(screen.getByTestId("argument-map-panel")).toBeInTheDocument();
    expect(screen.getByTestId("citation-model-card-panel")).toBeInTheDocument();
    expect(screen.getByTestId("coverage-caveat-panel")).toBeInTheDocument();
    expect(screen.getByTestId("threshold-contract-panel")).toBeInTheDocument();
    expect(screen.getByText("phase35.viewer.verified")).toBeInTheDocument();
  });

  it("rejects invalid signed ids", () => {
    render(
      <MemoryRouter initialEntries={["/public/decisions/not-valid"]}>
        <Routes>
          <Route
            path="/public/decisions/:signedId"
            element={<PublicDecisionViewerPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("public-decision-invalid")).toBeInTheDocument();
    expect(screen.getByText("phase35.viewer.invalid")).toBeInTheDocument();
  });
});
