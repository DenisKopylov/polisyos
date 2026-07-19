import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { buildSignedPublicDecisionPacket } from "@/features/runs/domain/publicationPacket";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";

import PublicDecisionViewerPage from "./PublicDecisionViewerPage";

const testDecisionScore = () =>
  untracedDecisionQuantity({ metricId: "test.decision_score", point: 0.74 });

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) =>
      params?.reason ? `${key}:${params.reason}` : key,
  }),
}));

const projectionMaskingCases = [
  ["missing", "missing evidence label"],
  ["stale", "stale evidence label"],
  ["conflicting", "conflicting evidence label"],
  ["reissued", "reissued evidence label"],
  ["withdrawn", "withdrawn evidence label"],
  ["non_authoritative", "non-authoritative evidence label"],
  ["projection_only", "projection-only evidence label"],
] as const;

describe("PublicDecisionViewerPage", () => {
  it("renders a verified signed public decision without API context", async () => {
    const packet = buildSignedPublicDecisionPacket({
      decisionScore: testDecisionScore(),
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

  it("renders projection-only publishable claims as blocked in the public viewer", async () => {
    const packet = buildSignedPublicDecisionPacket({
      decisionScore: testDecisionScore(),
      policyDesignCaseProjection: {
        authority_role: "projection_only",
        labels: [
          {
            authority_role: "projection_only",
            label: "publishable",
            state: "publishable",
          },
        ],
        may_not_be_used_for: ["scorecard_authority"],
        primary_state: "publishable",
        projection_policy: "reads_policy_design_case_only",
        states: ["publishable", "projection_only"],
      },
      runId: "public-run-projection",
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

    const semantics = await screen.findByTestId(
      "publication-projection-semantics",
    );

    expect(semantics).toHaveTextContent("blocked");
    expect(semantics).toHaveTextContent("projection_only");
    expect(semantics).not.toHaveTextContent("publishable");
  });

  it.each(projectionMaskingCases)(
    "renders %s masking labels as blocked in the public viewer",
    async (caseId, label) => {
      const packet = buildSignedPublicDecisionPacket({
        decisionScore: testDecisionScore(),
        policyDesignCaseProjection: {
          authority_role: "projection_only",
          labels: [
            {
              authority_role: "projection_only",
              label,
              state: "projection_only",
            },
          ],
          may_not_be_used_for: ["scorecard_authority"],
          primary_state: "projection_only",
          projection_policy: "reads_policy_design_case_only",
          states: ["projection_only"],
        },
        runId: `public-run-projection-${caseId}`,
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

      const semantics = await screen.findByTestId(
        "publication-projection-semantics",
      );

      expect(semantics).toHaveTextContent("blocked");
      expect(semantics).toHaveTextContent("projection_only");
      expect(semantics).not.toHaveTextContent("publishable");
    },
  );

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
