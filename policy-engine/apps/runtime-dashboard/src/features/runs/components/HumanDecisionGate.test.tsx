import { onlineManager } from "@tanstack/react-query";
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";

import CaseWorkspacePage from "@/features/runs/routes/CaseWorkspacePage";
import { buildHumanDecisionFacts } from "@/features/runs/domain/humanDecisionPresentation";
import { humanDecisionGateResponseSchema } from "@/api/validators";
import { runPaperPacketFixture } from "@/test/fixtures/runPaper";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/msw/server";
import {
  availableHumanDecisionGate,
  humanDecisionDigest,
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

const digest = humanDecisionDigest;
const sourceRef = humanDecisionSourceRef;
const appealHref =
  "/runs/run-1/case?appeal_case_id=case.fixture" +
  `&source_kind=agent_action_authority&source_ref=${encodeURIComponent(sourceRef)}`;
const available = availableHumanDecisionGate();

function renderGate(body: Record<string, unknown>) {
  server.use(
    http.get("*/api/v1/runs/:runId/case-inspection", () =>
      HttpResponse.json(runPaperPacketFixture()),
    ),
    http.get("*/api/v1/runs/:runId/human-decision-gate", () =>
      HttpResponse.json(body),
    ),
    http.get("*/api/v1/runs/:runId/human-decisions/review-effectiveness", () =>
      HttpResponse.json(humanDecisionReviewEffectivenessFixture()),
    ),
  );
  return renderWithProviders(
    <Routes>
      <Route path="/runs/:runId/case" element={<CaseWorkspacePage />} />
    </Routes>,
    {
      initialEntries: [
        `/runs/run-1/case?source_kind=agent_action_authority&source_ref=${encodeURIComponent(sourceRef)}&action_kind=data_request`,
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
    expect(gate).toHaveTextContent(
      "The server revalidates the exact intersection of every signed deadline immediately before action.",
    );
  });

  it("renders every parsed packet fact in its DOM roster", async () => {
    renderGate(available);
    await screen.findByTestId("human-decision-gate");
    const rows = screen.getAllByTestId("human-decision-fact");
    const rendered = rows.map((row) => ({
      path: row.dataset.humanDecisionPath,
      value: within(row).getByRole("definition").textContent,
    }));

    expect(rendered).toEqual(
      buildHumanDecisionFacts(humanDecisionGateResponseSchema.parse(available)),
    );
  });

  it("preserves repeated evidence obligations by occurrence", async () => {
    const repeated = structuredClone(available);
    const evidenceDigest = repeated.exposure.required_artifact_digests[1]!;
    repeated.decision_request!.five_rights_binding.required_information_refs = [
      evidenceDigest,
      evidenceDigest,
    ];
    repeated.exposure.required_artifact_digests.push(evidenceDigest);
    repeated.exposure.completed_artifact_digests =
      repeated.exposure.completed_artifact_digests.slice(0, 2);
    repeated.status = "blocked";
    repeated.reasons = [
      {
        code: "DS9-EVIDENCE-EXPOSURE-INCOMPLETE",
        message: "One repeated evidence delivery remains incomplete.",
        status: "blocked",
      },
    ];
    repeated.reason_codes = ["DS9-EVIDENCE-EXPOSURE-INCOMPLETE"];
    repeated.submission = null;

    renderGate(repeated);
    const evidence = await screen.findByRole("region", {
      name: /evidence exposure/i,
    });
    expect(within(evidence).getAllByText("opened")).toHaveLength(2);
    expect(
      within(evidence).getAllByRole("button", { name: /open evidence/i }),
    ).toHaveLength(1);
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
      reasons: [
        {
          code: "DS9-RUBBER-STAMP",
          message: "Evidence was not opened.",
          status: "blocked",
        },
        {
          code: "DS9-MANDATE-NOT-SHOWN",
          message: "Mandate was not shown.",
          status: "blocked",
        },
        {
          code: "DS9-EVIDENCE-NOT-OPENED",
          message: "Required evidence is unopened.",
          status: "blocked",
        },
      ],
      submission: null,
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
      reasons: [
        { code: "DS9-WRONG-ROLE", message: "Wrong role.", status: "blocked" },
        {
          code: "DS9-DECISION-TTL-EXPIRED",
          message: "TTL expired.",
          status: "blocked",
        },
        {
          code: "DS9-AUTHORITY-CROSS-USE",
          message: "Authority cross-use.",
          status: "blocked",
        },
      ],
      submission: null,
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
    expect(
      await screen.findByTestId("human-decision-gate"),
    ).toBeInTheDocument();
    act(() => onlineManager.setOnline(false));

    await waitFor(() =>
      expect(
        screen.queryByTestId("human-decision-gate"),
      ).not.toBeInTheDocument(),
    );
    expect(posts).toBe(0);

    act(() => onlineManager.setOnline(true));
    expect(
      await screen.findByTestId("human-decision-gate"),
    ).toBeInTheDocument();
    expect(posts).toBe(0);
  });

  it("removes captured authority and MACHINE bytes on an offline transition", async () => {
    renderGate(available);
    expect(
      await screen.findByTestId("human-decision-gate"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("human-decision-machine-export"),
    ).toBeInTheDocument();

    act(() => onlineManager.setOnline(false));

    await waitFor(() =>
      expect(
        screen.queryByTestId("human-decision-gate"),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.queryByTestId("human-decision-machine-export"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /approve/i }),
    ).not.toBeInTheDocument();
  });

  it("removes the actionable gate after a content-bound durable receipt", async () => {
    let posts = 0;
    server.use(
      http.post("*/api/v1/runs/:runId/human-decisions", () => {
        posts += 1;
        return HttpResponse.json(
          {
            durable_event_id: "event-1",
            record: {},
            record_digest: digest("4"),
            record_ref: digest("4"),
            reservation_id: "reservation-1",
            reservation_version: 1,
            run_id: "run-1",
          },
          { status: 201 },
        );
      }),
    );
    renderGate(available);
    const gate = await screen.findByTestId("human-decision-gate");
    await userEvent.type(
      within(gate).getByLabelText(/accountability statement/i),
      "I accept accountability.",
    );
    await userEvent.type(
      within(gate).getByLabelText(/dissent/i),
      "No disconfirming evidence remains.",
    );

    await userEvent.click(
      within(gate).getByRole("button", { name: /approve/i }),
    );

    await waitFor(() => expect(posts).toBe(1));
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: /approve/i }),
      ).not.toBeInTheDocument(),
    );
  });
});
