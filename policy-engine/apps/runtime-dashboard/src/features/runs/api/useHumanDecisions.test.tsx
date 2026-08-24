import { waitFor } from "@testing-library/react";
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

const digest = (character: string) => `sha256:${character.repeat(64)}`;
const sourceRef = digest("a");

describe("useHumanDecisions", () => {
  it("issues one exact source-bound gate request from the authorized workspace", async () => {
    const gateUrls: URL[] = [];
    server.use(
      http.get("*/api/v1/runs/:runId/case-inspection", () =>
        HttpResponse.json(runPaperPacketFixture()),
      ),
      http.get("*/api/v1/runs/:runId/human-decision-gate", ({ request }) => {
        gateUrls.push(new URL(request.url));
        return HttpResponse.json({
          status: "producer_missing",
          reason_codes: ["DS9-DECISION-PRODUCER-MISSING"],
          source_kind: "agent_action_authority",
          source_ref: sourceRef,
        });
      }),
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

    await waitFor(() => expect(gateUrls).toHaveLength(1));
    expect(gateUrls[0].pathname).toBe("/api/v1/runs/run-1/human-decision-gate");
    expect(gateUrls[0].searchParams.get("source_kind")).toBe(
      "agent_action_authority",
    );
    expect(gateUrls[0].searchParams.get("source_ref")).toBe(sourceRef);
  });
});
