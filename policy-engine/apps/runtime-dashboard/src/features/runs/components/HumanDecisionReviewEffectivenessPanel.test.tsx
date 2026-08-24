import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";

import CaseWorkspacePage from "@/features/runs/routes/CaseWorkspacePage";
import { runPaperPacketFixture } from "@/test/fixtures/runPaper";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/msw/server";

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

const sourceRef = `sha256:${"a".repeat(64)}`;

describe("HumanDecisionReviewEffectivenessPanel", () => {
  it("allow without record is incomplete", async () => {
    let reads = 0;
    server.use(
      http.get("*/api/v1/runs/:runId/case-inspection", () =>
        HttpResponse.json(runPaperPacketFixture()),
      ),
      http.get("*/api/v1/runs/:runId/human-decision-gate", () =>
        HttpResponse.json({
          status: "producer_missing",
          reason_codes: ["DS9-DECISION-PRODUCER-MISSING"],
          source_kind: "agent_action_authority",
          source_ref: sourceRef,
        }),
      ),
      http.get(
        "*/api/v1/runs/:runId/human-decisions/review-effectiveness",
        () => {
          reads += 1;
          return HttpResponse.json({
            status: "incomplete",
            reason_codes: ["DS9-AUTHZ-ALLOW-NOT-SUCCESS"],
            coverage: {
              total_events: 2,
              parsed_events: 2,
              schema_valid_events: 2,
              malformed_events: 0,
              retained_events: 2,
              joined_record_events: 0,
            },
            advisory_posture: "insufficient_basis",
          });
        },
      ),
    );

    renderWithProviders(
      <Routes>
        <Route path="/runs/:runId/case" element={<CaseWorkspacePage />} />
      </Routes>,
      {
        initialEntries: [
          `/runs/run-1/case?source_kind=agent_action_authority&source_ref=${encodeURIComponent(sourceRef)}`,
        ],
      },
    );

    await waitFor(() => expect(reads).toBe(1));
    const panel = await screen.findByTestId(
      "human-decision-review-effectiveness",
    );
    expect(panel).toHaveTextContent("incomplete");
    expect(panel).toHaveTextContent("DS9-AUTHZ-ALLOW-NOT-SUCCESS");
    expect(within(panel).queryByText(/^effective$/i)).not.toBeInTheDocument();
  });
});
