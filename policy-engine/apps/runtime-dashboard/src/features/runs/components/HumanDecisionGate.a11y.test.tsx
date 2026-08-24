import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { axe } from "vitest-axe";

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

describe("HumanDecisionGate accessibility", () => {
  it("has no violations while surfacing a typed producer refusal", async () => {
    server.use(
      http.get("*/api/v1/runs/:runId/case-inspection", () =>
        HttpResponse.json(runPaperPacketFixture()),
      ),
      http.get("*/api/v1/runs/:runId/human-decision-gate", () =>
        HttpResponse.json(producerMissingHumanDecisionGate()),
      ),
      http.get(
        "*/api/v1/runs/:runId/human-decisions/review-effectiveness",
        () => HttpResponse.json(humanDecisionReviewEffectivenessFixture()),
      ),
    );
    const view = renderWithProviders(
      <Routes>
        <Route path="/runs/:runId/case" element={<CaseWorkspacePage />} />
      </Routes>,
      {
        initialEntries: [
          `/runs/run-1/case?source_kind=agent_action_authority&source_ref=${encodeURIComponent(sourceRef)}&action_kind=data_request`,
        ],
      },
    );

    await screen.findByTestId("human-decision-gate");
    const result = await axe(view.container);
    expect(
      result.violations.map((violation) => ({
        id: violation.id,
        nodes: violation.nodes.map((node) => node.target),
      })),
    ).toEqual([]);
  });
});
