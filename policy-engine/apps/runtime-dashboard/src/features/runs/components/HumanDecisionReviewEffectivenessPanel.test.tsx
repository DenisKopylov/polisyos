import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";

import CaseWorkspacePage from "@/features/runs/routes/CaseWorkspacePage";
import { runPaperPacketFixture } from "@/test/fixtures/runPaper";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/msw/server";
import {
  humanDecisionReviewEffectivenessFixture,
  humanDecisionSourceRef,
  producerMissingHumanDecisionGate,
} from "@/test/fixtures/humanDecision";

vi.mock("@/app/authz/AuthzProvider", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/app/authz/AuthzProvider")>();
  return {
    ...actual,
    useAuthzDecision: () => ({
      can: (permission: string) =>
        ["runs.review", "runs.human_decisions.create"].includes(permission),
      kind: "verified",
    }),
  };
});

const sourceRef = humanDecisionSourceRef;

describe("HumanDecisionReviewEffectivenessPanel", () => {
  it("allow without record is incomplete", async () => {
    let reads = 0;
    server.use(
      http.get("*/api/v1/runs/:runId/case-inspection", () =>
        HttpResponse.json(runPaperPacketFixture()),
      ),
      http.get("*/api/v1/runs/:runId/human-decision-gate", () =>
        HttpResponse.json(producerMissingHumanDecisionGate()),
      ),
      http.get(
        "*/api/v1/runs/:runId/human-decisions/review-effectiveness",
        () => {
          reads += 1;
          return HttpResponse.json(humanDecisionReviewEffectivenessFixture());
        },
      ),
    );

    renderWithProviders(
      <Routes>
        <Route path="/runs/:runId/case" element={<CaseWorkspacePage />} />
      </Routes>,
      {
        initialEntries: [
          `/runs/run-1/case?source_kind=agent_action_authority&source_ref=${encodeURIComponent(sourceRef)}&action_kind=data_request`,
        ],
      },
    );

    await waitFor(() => expect(reads).toBe(1));
    const panel = await screen.findByTestId(
      "human-decision-review-effectiveness",
    );
    expect(panel).toHaveTextContent("incomplete");
    expect(panel).toHaveTextContent(
      "human_decision_review_coverage_incomplete",
    );
    expect(within(panel).queryByText(/^effective$/i)).not.toBeInTheDocument();
  });
});
