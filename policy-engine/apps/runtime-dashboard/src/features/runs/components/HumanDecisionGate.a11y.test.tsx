import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { axe } from "vitest-axe";

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

describe("HumanDecisionGate accessibility", () => {
  it("has no violations while surfacing a typed producer refusal", async () => {
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
    );
    const view = renderWithProviders(
      <Routes>
        <Route path="/runs/:runId/case" element={<CaseWorkspacePage />} />
      </Routes>,
      {
        initialEntries: [
          `/runs/run-1/case?source_kind=agent_action_authority&source_ref=${encodeURIComponent(sourceRef)}`,
        ],
      },
    );

    await screen.findByTestId("human-decision-gate");
    expect((await axe(view.container)).violations).toHaveLength(0);
  });
});
