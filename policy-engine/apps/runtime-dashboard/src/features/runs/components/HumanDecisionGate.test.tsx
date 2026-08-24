import { onlineManager } from "@tanstack/react-query";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
const appealHref =
  "/runs/run-1/case?appeal_case_id=case.fixture" +
  `&source_kind=agent_action_authority&source_ref=${encodeURIComponent(sourceRef)}`;
const available = {
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
  contestability: {
    case_id: "case.fixture",
    source_ref: sourceRef,
    href: appealHref,
  },
};

function renderGate(body: Record<string, unknown>) {
  server.use(
    http.get("*/api/v1/runs/:runId/case-inspection", () =>
      HttpResponse.json(runPaperPacketFixture()),
    ),
    http.get("*/api/v1/runs/:runId/human-decision-gate", () =>
      HttpResponse.json(body),
    ),
  );
  return renderWithProviders(
    <Routes>
      <Route path="/runs/:runId/case" element={<CaseWorkspacePage />} />
    </Routes>,
    {
      initialEntries: [
        `/runs/run-1/case?source_kind=agent_action_authority&source_ref=${encodeURIComponent(sourceRef)}`,
      ],
    },
  );
}

describe("HumanDecisionGate", () => {
  afterEach(() => {
    onlineManager.setOnline(true);
  });

  it("shows mandate evidence rights and TTL before actions", async () => {
    renderGate(available);
    const gate = await screen.findByTestId("human-decision-gate");
    for (const value of [
      "mandate://fixture",
      "evidence://opened",
      "data_steward",
      "reviewer_console",
      "2026-08-24T12:30:00Z",
    ]) {
      expect(gate).toHaveTextContent(value);
    }
    expect(
      within(gate).getByRole("button", { name: /approve/i }),
    ).toBeEnabled();
  });

  it("surfaces rubber-stamp blocked reason without mutation", async () => {
    let posts = 0;
    server.use(
      http.post("*/api/v1/runs/:runId/human-decisions", () => {
        posts += 1;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    renderGate({
      ...available,
      status: "blocked",
      reason_codes: [
        "DS9-RUBBER-STAMP",
        "DS9-MANDATE-NOT-SHOWN",
        "DS9-EVIDENCE-NOT-OPENED",
      ],
      decision_request: {
        ...available.decision_request,
        available_actions: [],
      },
    });
    const gate = await screen.findByTestId("human-decision-gate");
    for (const code of [
      "DS9-RUBBER-STAMP",
      "DS9-MANDATE-NOT-SHOWN",
      "DS9-EVIDENCE-NOT-OPENED",
    ]) {
      expect(gate).toHaveTextContent(code);
    }
    expect(
      within(gate).queryByRole("button", { name: /approve/i }),
    ).not.toBeInTheDocument();
    expect(posts).toBe(0);
  });

  it("renders wrong-role expired-TTL and cross-authority reasons", async () => {
    renderGate({
      ...available,
      status: "blocked",
      reason_codes: [
        "DS9-WRONG-ROLE",
        "DS9-DECISION-TTL-EXPIRED",
        "DS9-AUTHORITY-CROSS-USE",
      ],
    });
    const gate = await screen.findByTestId("human-decision-gate");
    for (const code of [
      "DS9-WRONG-ROLE",
      "DS9-DECISION-TTL-EXPIRED",
      "DS9-AUTHORITY-CROSS-USE",
    ]) {
      expect(gate).toHaveTextContent(code);
    }
  });

  it("omits contestability control without case and source binding", async () => {
    const bound = renderGate(available);
    expect(
      await screen.findByRole("link", { name: /appeal here/i }),
    ).toHaveAttribute("href", appealHref);
    bound.unmount();

    for (const contestability of [
      null,
      { source_ref: sourceRef, href: appealHref },
      { case_id: "case.fixture", href: appealHref },
      {
        case_id: "case.fixture",
        source_ref: sourceRef,
        href: "/runs/run-1/case?source_kind=agent_action_authority",
      },
    ]) {
      const partial = renderGate({ ...available, contestability });
      await screen.findByTestId("human-decision-gate");
      expect(
        screen.queryByRole("link", { name: /appeal here/i }),
      ).not.toBeInTheDocument();
      partial.unmount();
    }
  });

  it("stale/offline submit requires online revalidation", async () => {
    let posts = 0;
    server.use(
      http.post("*/api/v1/runs/:runId/human-decisions", () => {
        posts += 1;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    renderGate(available);
    const gate = await screen.findByTestId("human-decision-gate");
    const approve = within(gate).getByRole("button", { name: /approve/i });
    onlineManager.setOnline(false);

    await userEvent.setup().click(approve);

    await waitFor(() =>
      expect(gate).toHaveTextContent("DS9-OFFLINE-REVALIDATION"),
    );
    expect(posts).toBe(0);
  });
});
