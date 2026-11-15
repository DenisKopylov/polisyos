import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
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
  type HumanDecisionMutationRequest,
  useCreateHumanDecision,
} from "./useHumanDecisions";
import { createTestQueryClient } from "@/test/queryClient";

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
const exposureRef = humanDecisionDigest("1");
const selectedDecisionBody = {
  accountability_statement: "I accept accountability for this decision.",
  action: "approve",
  action_kind: "data_request",
  basis_digest: humanDecisionDigest("b"),
  basis_ref: humanDecisionDigest("b"),
  blocking_reason: null,
  decision_mode: "ordinary",
  decision_request_digest: humanDecisionDigest("c"),
  decision_request_ref: humanDecisionDigest("c"),
  dissent_statement: "I considered the disconfirming evidence.",
  override_reason: null,
  presentation_contract_ref: humanDecisionDigest("d"),
  principal_binding_ref: humanDecisionDigest("e"),
  reviewer_separation_ref: humanDecisionDigest("f"),
  source_kind: "agent_action_authority",
  source_ref: humanDecisionSourceRef,
} satisfies HumanDecisionMutationRequest;

const humanDecisionRecordFixture = () => ({
  accountability_statement: selectedDecisionBody.accountability_statement,
  actor_ref: "actor-fixture",
  basis_digest: selectedDecisionBody.basis_digest,
  basis_ref: selectedDecisionBody.basis_ref,
  blocking_reason: selectedDecisionBody.blocking_reason,
  binding_sha256: humanDecisionDigest("2"),
  decision_action_exercised: "approve",
  decision_mode: "ordinary",
  decision_request_digest: selectedDecisionBody.decision_request_digest,
  dissent_statement: selectedDecisionBody.dissent_statement,
  exposure_session_ref: exposureRef,
  exposure_session_digest: exposureRef,
  human_decision_request_ref: selectedDecisionBody.decision_request_ref,
  override_reason: selectedDecisionBody.override_reason,
  presentation_contract_ref: selectedDecisionBody.presentation_contract_ref,
  presentation_contract_digest: selectedDecisionBody.presentation_contract_ref,
  principal_binding_ref: selectedDecisionBody.principal_binding_ref,
  principal_binding_digest: selectedDecisionBody.principal_binding_ref,
  reservation_id: "reservation-1",
  reservation_version: 1,
  reviewer_separation_ref: selectedDecisionBody.reviewer_separation_ref,
  reviewer_separation_digest: selectedDecisionBody.reviewer_separation_ref,
  run_id: "run-1",
  source_kind: "agent_action_authority",
  source_ref: humanDecisionSourceRef,
  source_digest: humanDecisionSourceRef,
  tenant_id: "tenant-fixture",
});

function custodyNonreceipt() {
  return new HttpResponse(
    JSON.stringify({
      code: "human_decision_custody_nonreceipt",
      detail: "The durable record receipt was not returned.",
      status: 503,
      title: "Human-decision custody receipt unavailable",
    }),
    {
      headers: { "Content-Type": "application/problem+json" },
      status: 503,
    },
  );
}

function recoveryPending() {
  return {
    authority_purpose: "historical_human_decision_custody_only",
    binding_rule: "policyos.runtime.human_decision_submission_binding.v2",
    binding_sha256: humanDecisionDigest("2"),
    cell_id: null,
    operational_authority: false,
    reservation_id: "reservation-1",
    reservation_version: 1,
    run_id: "run-1",
    schema_version: "policyos.runtime.human_decision_recovery.v1",
    status: "pending",
    tenant_id: "tenant-fixture",
  };
}

function recoveryCommitted(
  reservationState: "committed" | "expired" = "committed",
) {
  const recordDigest = humanDecisionDigest("9");
  return {
    authority_purpose: "historical_human_decision_custody_only",
    binding_rule: "policyos.runtime.human_decision_submission_binding.v2",
    binding_sha256: humanDecisionDigest("2"),
    cell_id: null,
    durable_event_id: "event-recovered-1",
    operational_authority: false,
    record_digest: recordDigest,
    record_ref: {
      artifact_id: recordDigest,
      kind: "runtime_quality.agent_action_human_decision",
      manifest_profile_sha256: humanDecisionDigest("7"),
      media_type: "application/json",
    },
    record_valid_until: "2030-01-01T00:00:00Z",
    reservation_id: "reservation-1",
    reservation_state: reservationState,
    reservation_version: 1,
    run_id: "run-1",
    schema_version: "policyos.runtime.human_decision_recovery.v1",
    status: "committed",
    tenant_id: "tenant-fixture",
  };
}

describe("useHumanDecisions", () => {
  it("keeps the unconsumed create-record payload opaque at the dashboard boundary", async () => {
    type CreateReceipt = Extract<
      Awaited<ReturnType<typeof createHumanDecision>>,
      { kind: "created" }
    >["receipt"];

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

    const result = await createHumanDecision({
      body: {} as never,
      exposureSessionRef: exposureRef,
      runId: "run-1",
    });
    expect(result.kind).toBe("created");
    if (result.kind !== "created") {
      throw new Error("Expected the original submission to be created");
    }
    expect(result.receipt.record).toEqual({});
  });

  it("recovers only the exact custody nonreceipt with the saved body and exposure", async () => {
    const calls = { create: 0, recovery: 0 };
    server.use(
      http.post("*/api/v1/runs/:runId/human-decisions", async ({ request }) => {
        calls.create += 1;
        expect(await request.json()).toEqual(selectedDecisionBody);
        expect(request.headers.get("X-PolicyOS-Human-Decision-Exposure")).toBe(
          exposureRef,
        );
        return custodyNonreceipt();
      }),
      http.post(
        "*/api/v1/runs/:runId/human-decisions/recovery",
        async ({ request }) => {
          calls.recovery += 1;
          expect(await request.json()).toEqual(selectedDecisionBody);
          expect(
            request.headers.get("X-PolicyOS-Human-Decision-Exposure"),
          ).toBe(exposureRef);
          return HttpResponse.json(recoveryPending());
        },
      ),
    );

    const result = await createHumanDecision({
      body: selectedDecisionBody,
      exposureSessionRef: exposureRef,
      runId: "run-1",
    });

    expect(result.kind).toBe("recovery_pending");
    expect(calls).toEqual({ create: 1, recovery: 1 });
  });

  it("does not start recovery for another 503 problem code", async () => {
    let recoveryCalls = 0;
    server.use(
      http.post("*/api/v1/runs/:runId/human-decisions", () =>
        HttpResponse.json(
          {
            code: "upstream_unavailable",
            detail: "The decision service is unavailable.",
            status: 503,
            title: "Unavailable",
          },
          {
            headers: { "Content-Type": "application/problem+json" },
            status: 503,
          },
        ),
      ),
      http.post("*/api/v1/runs/:runId/human-decisions/recovery", () => {
        recoveryCalls += 1;
        return HttpResponse.json(recoveryPending());
      }),
    );

    await expect(
      createHumanDecision({
        body: selectedDecisionBody,
        exposureSessionRef: exposureRef,
        runId: "run-1",
      }),
    ).rejects.toMatchObject({ code: "upstream_unavailable", status: 503 });
    expect(recoveryCalls).toBe(0);
  });

  it("keeps malformed recovery statuses from becoming a recovered submission", async () => {
    server.use(
      http.post("*/api/v1/runs/:runId/human-decisions", () =>
        custodyNonreceipt(),
      ),
      http.post("*/api/v1/runs/:runId/human-decisions/recovery", () =>
        HttpResponse.json({ ...recoveryPending(), status: "waiting" }),
      ),
    );

    await expect(
      createHumanDecision({
        body: selectedDecisionBody,
        exposureSessionRef: exposureRef,
        runId: "run-1",
      }),
    ).rejects.toMatchObject({
      code: "human_decision_recovery_response_invalid",
      status: 409,
    });
  });

  it.each([
    ["committed", "recovered_committed"],
    ["expired", "recovered_expired"],
  ] as const)(
    "reads the selected record before classifying recovered %s custody",
    async (reservationState, expectedKind) => {
      const record = humanDecisionRecordFixture();
      const recovery = recoveryCommitted(reservationState);
      let createCalls = 0;
      let recoveryCalls = 0;
      let selectedRecordRef: string | null = null;
      let selectedProfile: string | null = null;
      let selectedRunId: string | null = null;
      server.use(
        http.post("*/api/v1/runs/:runId/human-decisions", () => {
          createCalls += 1;
          return custodyNonreceipt();
        }),
        http.post("*/api/v1/runs/:runId/human-decisions/recovery", () => {
          recoveryCalls += 1;
          return HttpResponse.json(recovery);
        }),
        http.get("*/api/v1/runs/:runId/human-decisions", ({ request }) => {
          selectedRunId = new URL(request.url).pathname.split("/")[4] ?? null;
          selectedRecordRef = new URL(request.url).searchParams.get(
            "record_ref",
          );
          selectedProfile = new URL(request.url).searchParams.get(
            "manifest_profile_sha256",
          );
          return HttpResponse.json(record);
        }),
      );

      const result = await createHumanDecision({
        body: selectedDecisionBody,
        exposureSessionRef: exposureRef,
        runId: "run-1",
      });

      expect(result.kind).toBe(expectedKind);
      expect(selectedRecordRef).toBe(recovery.record_digest);
      expect(selectedProfile).toBe(recovery.record_ref.manifest_profile_sha256);
      expect(selectedRunId).toBe("run-1");
      expect({ createCalls, recoveryCalls }).toEqual({
        createCalls: 1,
        recoveryCalls: 1,
      });
      const recoveredRecord =
        result.kind === "recovered_committed"
          ? result.receipt.record
          : undefined;
      expect(recoveredRecord).toEqual(
        expectedKind === "recovered_committed" ? record : undefined,
      );
    },
  );

  it("rejects a selected record that differs from the recovered submission", async () => {
    let createCalls = 0;
    server.use(
      http.post("*/api/v1/runs/:runId/human-decisions", () => {
        createCalls += 1;
        return custodyNonreceipt();
      }),
      http.post("*/api/v1/runs/:runId/human-decisions/recovery", () =>
        HttpResponse.json(recoveryCommitted()),
      ),
      http.get("*/api/v1/runs/:runId/human-decisions", () =>
        HttpResponse.json({
          ...humanDecisionRecordFixture(),
          decision_action_exercised: "reject",
        }),
      ),
    );

    await expect(
      createHumanDecision({
        body: selectedDecisionBody,
        exposureSessionRef: exposureRef,
        runId: "run-1",
      }),
    ).rejects.toMatchObject({
      code: "human_decision_recovery_record_mismatch",
      status: 409,
    });
    expect(createCalls).toBe(1);
  });

  it.each([
    [
      "tenant",
      (record: ReturnType<typeof humanDecisionRecordFixture>) => ({
        ...record,
        tenant_id: "tenant-other",
      }),
    ],
    [
      "exposure",
      (record: ReturnType<typeof humanDecisionRecordFixture>) => ({
        ...record,
        exposure_session_digest: humanDecisionDigest("8"),
        exposure_session_ref: humanDecisionDigest("8"),
      }),
    ],
    [
      "reservation",
      (record: ReturnType<typeof humanDecisionRecordFixture>) => ({
        ...record,
        reservation_id: "reservation-other",
      }),
    ],
    [
      "saved request body",
      (record: ReturnType<typeof humanDecisionRecordFixture>) => ({
        ...record,
        accountability_statement: "A different decision was submitted.",
      }),
    ],
  ])(
    "rejects a recovered record with a mismatched %s",
    async (_name, alter) => {
      server.use(
        http.post("*/api/v1/runs/:runId/human-decisions", () =>
          custodyNonreceipt(),
        ),
        http.post("*/api/v1/runs/:runId/human-decisions/recovery", () =>
          HttpResponse.json(recoveryCommitted()),
        ),
        http.get("*/api/v1/runs/:runId/human-decisions", () =>
          HttpResponse.json(alter(humanDecisionRecordFixture())),
        ),
      );

      await expect(
        createHumanDecision({
          body: selectedDecisionBody,
          exposureSessionRef: exposureRef,
          runId: "run-1",
        }),
      ).rejects.toMatchObject({
        code: "human_decision_recovery_record_mismatch",
        status: 409,
      });
    },
  );

  it("keeps a pending submission in recovery-only mode", async () => {
    const queryClient = createTestQueryClient();
    let createCalls = 0;
    let recoveryCalls = 0;
    server.use(
      http.post("*/api/v1/runs/:runId/human-decisions", () => {
        createCalls += 1;
        return custodyNonreceipt();
      }),
      http.post("*/api/v1/runs/:runId/human-decisions/recovery", () => {
        recoveryCalls += 1;
        return HttpResponse.json(recoveryPending());
      }),
    );
    const { result } = renderHook(() => useCreateHumanDecision("run-1"), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>
          {children}
        </QueryClientProvider>
      ),
    });
    const input = {
      body: selectedDecisionBody,
      exposureSessionRef: exposureRef,
      runId: "run-1",
    };

    const initial: {
      value?: Awaited<ReturnType<typeof result.current.mutateAsync>>;
    } = {};
    await act(async () => {
      initial.value = await result.current.mutateAsync(input);
    });
    expect(initial.value).toMatchObject({ kind: "recovery_pending" });
    await expect(result.current.mutateAsync(input)).rejects.toMatchObject({
      code: "human_decision_recovery_pending",
    });
    const retry: {
      value?: Awaited<ReturnType<typeof result.current.recoverPending>>;
    } = {};
    await act(async () => {
      retry.value = await result.current.recoverPending();
    });
    expect(retry.value).toMatchObject({ kind: "recovery_pending" });
    expect({ createCalls, recoveryCalls }).toEqual({
      createCalls: 1,
      recoveryCalls: 2,
    });
  });

  it("clears a pending receipt when the hook is reused for another run", async () => {
    const queryClient = createTestQueryClient();
    let recoveryCalls = 0;
    server.use(
      http.post("*/api/v1/runs/:runId/human-decisions", () =>
        custodyNonreceipt(),
      ),
      http.post("*/api/v1/runs/:runId/human-decisions/recovery", () => {
        recoveryCalls += 1;
        return HttpResponse.json(recoveryPending());
      }),
    );
    const { result, rerender } = renderHook(
      ({ runId }: { runId: string }) => useCreateHumanDecision(runId),
      {
        initialProps: { runId: "run-1" },
        wrapper: ({ children }) => (
          <QueryClientProvider client={queryClient}>
            {children}
          </QueryClientProvider>
        ),
      },
    );

    await act(async () => {
      await result.current.mutateAsync({
        body: selectedDecisionBody,
        exposureSessionRef: exposureRef,
        runId: "run-1",
      });
    });
    expect(result.current.recoveryPosture?.kind).toBe("recovery_pending");

    rerender({ runId: "run-2" });

    await waitFor(() => expect(result.current.recoveryPosture).toBeNull());
    await expect(result.current.recoverPending()).rejects.toMatchObject({
      code: "human_decision_recovery_not_pending",
    });
    expect(recoveryCalls).toBe(1);
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
