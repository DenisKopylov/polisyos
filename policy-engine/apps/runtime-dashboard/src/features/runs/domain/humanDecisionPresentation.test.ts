import { createElement } from "react";
import { screen } from "@testing-library/react";
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
const gate = {
  status: "available",
  reason_codes: [],
  source_kind: "agent_action_authority",
  source_ref: sourceRef,
  decision_request: {
    case_id: "case.fixture",
    delegation_contract_ref: "pdc://s7/contract",
    decision_rights_matrix_ref: "pdc://s7/rights",
    required_role: "data_steward",
    available_actions: ["approve", "reject", "request_evidence"],
    decidable_until: "2026-08-24T12:30:00Z",
    five_rights_requirements: {
      right_decision: "data_request",
      right_person: "data_steward",
      right_information: "evidence://opened",
      right_format_channel: "reviewer_console",
      right_time: "before TTL",
    },
  },
  mandate: {
    mandate_record_ref: "mandate://fixture",
    operation_id: "data_request",
    valid_until: "2026-08-24T12:30:00Z",
  },
  exposure: {
    required_artifact_digests: [digest("e")],
    completed_artifact_digests: [digest("e")],
  },
};

describe("humanDecisionPresentation", () => {
  it("keeps contract rights mandate evidence TTL and actions in pre-action order", async () => {
    server.use(
      http.get("*/api/v1/runs/:runId/case-inspection", () =>
        HttpResponse.json(runPaperPacketFixture()),
      ),
      http.get("*/api/v1/runs/:runId/human-decision-gate", () =>
        HttpResponse.json(gate),
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
        `/runs/run-1/case?source_kind=agent_action_authority&source_ref=${encodeURIComponent(sourceRef)}`,
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
    expect(text.indexOf(digest("e"))).toBeGreaterThan(-1);
    expect(text.indexOf(digest("e"))).toBeLessThan(actionIndex);
    expect(text.indexOf("2026-08-24T12:30:00Z")).toBeGreaterThan(-1);
    expect(text.indexOf("2026-08-24T12:30:00Z")).toBeLessThan(actionIndex);
  });
});
