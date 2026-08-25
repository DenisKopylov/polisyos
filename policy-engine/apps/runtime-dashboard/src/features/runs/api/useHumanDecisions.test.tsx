import { waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";

import CaseWorkspacePage from "@/features/runs/routes/CaseWorkspacePage";
import { runPaperPacketFixture } from "@/test/fixtures/runPaper";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/msw/server";
import {
  humanDecisionReviewEffectivenessFixture,
  humanDecisionDigest,
  humanDecisionSourceRef,
  producerMissingHumanDecisionGate,
  availableHumanDecisionGate,
} from "@/test/fixtures/humanDecision";
import {
  createHumanDecision,
  fetchHumanDecisionEvidence,
  fetchHumanDecisionGate,
  fetchReviewEffectiveness,
} from "./useHumanDecisions";

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

describe("useHumanDecisions", () => {
  it("keeps the unconsumed create-record payload opaque at the dashboard boundary", async () => {
    type CreateReceipt = Awaited<ReturnType<typeof createHumanDecision>>;

    expectTypeOf<CreateReceipt["record"]>().toBeUnknown();
    server.use(
      http.post("*/api/v1/runs/:runId/human-decisions", () =>
        HttpResponse.json(
          {
            durable_event_id: "event-opaque",
            record: {},
            record_digest: humanDecisionDigest("4"),
            record_ref: humanDecisionDigest("4"),
            reservation_id: "reservation-opaque",
            reservation_version: 1,
            run_id: "run-1",
          },
          { status: 201 },
        ),
      ),
    );

    const receipt = await createHumanDecision({
      body: {} as never,
      exposureSessionRef: humanDecisionDigest("1"),
      runId: "run-1",
    });
    expect(receipt.record).toEqual({});
  });

  it("issues one exact source-bound gate request from the authorized workspace", async () => {
    const gateUrls: URL[] = [];
    server.use(
      http.get("*/api/v1/runs/:runId/case-inspection", () =>
        HttpResponse.json(runPaperPacketFixture()),
      ),
      http.get("*/api/v1/runs/:runId/human-decision-gate", ({ request }) => {
        gateUrls.push(new URL(request.url));
        return HttpResponse.json(producerMissingHumanDecisionGate());
      }),
      http.get(
        "*/api/v1/runs/:runId/human-decisions/review-effectiveness",
        () => HttpResponse.json(humanDecisionReviewEffectivenessFixture()),
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

    await waitFor(() => expect(gateUrls).toHaveLength(1));
    expect(gateUrls[0].pathname).toBe("/api/v1/runs/run-1/human-decision-gate");
    expect(gateUrls[0].searchParams.get("source_kind")).toBe(
      "agent_action_authority",
    );
    expect(gateUrls[0].searchParams.get("source_ref")).toBe(sourceRef);
  });

  it.each([
    ["different PA2 action", { action_kind: "search" }],
    ["different signed basis", { basis_digest: humanDecisionDigest("8") }],
  ])("rejects an internally valid gate for a %s", async (_case, changed) => {
    const packet = availableHumanDecisionGate();
    const fetchImpl = async () =>
      new Response(JSON.stringify(packet), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });

    await expect(
      fetchHumanDecisionGate(
        "run-1",
        {
          action_kind: "data_request",
          basis_digest: packet.continuation!.basis_digest,
          source_kind: "agent_action_authority",
          source_ref: humanDecisionSourceRef,
          ...changed,
        },
        fetchImpl,
      ),
    ).rejects.toThrow("not bound to the requested run");
  });

  it("accepts only exact content-bound evidence response bytes", async () => {
    const digest =
      "sha256:2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824";
    const session = humanDecisionDigest("1");
    const response = (body: string, returnedSession = session) =>
      new Response(body, {
        headers: {
          "Cache-Control": "no-store",
          "Content-Encoding": "identity",
          ETag: `"${digest}"`,
          "X-Content-Type-Options": "nosniff",
          "X-PolicyOS-Exposure-Session": returnedSession,
        },
        status: 200,
      });

    const verified = await fetchHumanDecisionEvidence(
      "run-1",
      digest,
      session,
      async () => response("hello"),
    );
    expect(new TextDecoder().decode(verified.bytes)).toBe("hello");
    expect(verified.mediaType).toBe("text/plain;charset=UTF-8");
    await expect(
      fetchHumanDecisionEvidence("run-1", digest, session, async () =>
        response("altered"),
      ),
    ).rejects.toThrow("exact CAS digest");
    await expect(
      fetchHumanDecisionEvidence("run-1", digest, session, async () =>
        response("hello", humanDecisionDigest("2")),
      ),
    ).rejects.toThrow("exact custody binding");
  });

  it("rejects a cross-run review-effectiveness report", async () => {
    server.use(
      http.get(
        "*/api/v1/runs/:runId/human-decisions/review-effectiveness",
        () =>
          HttpResponse.json(
            humanDecisionReviewEffectivenessFixture({ run_id: "run-other" }),
          ),
      ),
    );

    await expect(fetchReviewEffectiveness("run-1")).rejects.toThrow(
      "bound to another run",
    );
  });

  it.each([
    ["cross-run", { run_id: "run-other" }],
    ["unbound digest", { record_digest: humanDecisionDigest("5") }],
  ])("rejects a %s create receipt", async (_case, changed) => {
    server.use(
      http.post("*/api/v1/runs/:runId/human-decisions", () =>
        HttpResponse.json(
          {
            durable_event_id: "event-1",
            record: {},
            record_digest: humanDecisionDigest("4"),
            record_ref: humanDecisionDigest("4"),
            reservation_id: "reservation-1",
            reservation_version: 1,
            run_id: "run-1",
            ...changed,
          },
          { status: 201 },
        ),
      ),
    );

    await expect(
      createHumanDecision({
        body: {} as never,
        exposureSessionRef: humanDecisionDigest("1"),
        runId: "run-1",
      }),
    ).rejects.toThrow();
  });
});
