import { createElement } from "react";
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";

import CaseWorkspacePage from "@/features/runs/routes/CaseWorkspacePage";
import { runPaperPacketFixture } from "@/test/fixtures/runPaper";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/msw/server";
import {
  availableHumanDecisionGate,
  humanDecisionEvidenceDigest,
  humanDecisionReviewEffectivenessFixture,
  humanDecisionSourceRef,
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
const gate = availableHumanDecisionGate();

describe("humanDecisionPresentation", () => {
  it("keeps contract rights mandate evidence TTL and actions in pre-action order", async () => {
    server.use(
      http.get("*/api/v1/runs/:runId/case-inspection", () =>
        HttpResponse.json(runPaperPacketFixture()),
      ),
      http.get("*/api/v1/runs/:runId/human-decision-gate", () =>
        HttpResponse.json(gate),
      ),
      http.get(
        "*/api/v1/runs/:runId/human-decisions/review-effectiveness",
        () => HttpResponse.json(humanDecisionReviewEffectivenessFixture()),
      ),
    );
    const ui = createElement(
      Routes,
      null,
      createElement(Route, {
        path: "/runs/:runId/case",
        element: createElement(CaseWorkspacePage),
      }),
    );
    renderWithProviders(ui, {
      initialEntries: [
        `/runs/run-1/case?source_kind=agent_action_authority&source_ref=${encodeURIComponent(sourceRef)}&action_kind=data_request`,
      ],
    });

    const region = await screen.findByTestId("human-decision-gate");
    const text = region.textContent ?? "";
    const spine = [
      "pdc://s7/contract",
      "pdc://s7/rights",
      "mandate://fixture",
      "approve",
    ].map((token) => text.indexOf(token));
    for (const [index, position] of spine.entries()) {
      expect(position).toBeGreaterThan(index === 0 ? -1 : spine[index - 1]);
    }
    const actionIndex = spine.at(-1) ?? -1;
    expect(text.indexOf(humanDecisionEvidenceDigest)).toBeGreaterThan(-1);
    expect(text.indexOf(humanDecisionEvidenceDigest)).toBeLessThan(actionIndex);
    expect(text.indexOf("2026-08-24T12:30:00Z")).toBeGreaterThan(-1);
    expect(text.indexOf("2026-08-24T12:30:00Z")).toBeLessThan(actionIndex);
  });
});
