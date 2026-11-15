import { onlineManager } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type {
  AcquisitionDecisionRequestResponseCurrent,
  AcquisitionExecutionResponseCurrent,
  AcquisitionRouteProjection,
  PaidInputAdmissionAcquisitionRouteV12,
  PendingAcquisitionRouteV11,
} from "@/features/runs/api/acquisitionRouteValidators";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import {
  EpochSemanticsProvider,
  type EpochSemantics,
} from "@/shared/ui/temporal/TimeSemanticsLabel";

const mocks = vi.hoisted(() => ({
  clearGate: vi.fn(),
  createDecision: vi.fn(),
  download: vi.fn(),
  execute: vi.fn(),
  fetchEvidence: vi.fn(),
  recoverPending: vi.fn(),
  recoveryPosture: vi.fn(),
  refetchGrowth: vi.fn(),
  refetchRoute: vi.fn(),
  requestDecision: vi.fn(),
  revalidateGate: vi.fn(),
  useControlJobStatus: vi.fn(),
  useAcquisitionRoute: vi.fn(),
  useHumanDecisionGate: vi.fn(),
}));

vi.mock("@/api/hooks/useControlJobStatus", () => ({
  useControlJobStatus: (...args: unknown[]) =>
    mocks.useControlJobStatus(...args),
}));

vi.mock("@/features/runs/api/useAcquisitionRoutes", () => ({
  executeAcquisitionRoute: (...args: unknown[]) => mocks.execute(...args),
  requestAcquisitionDecision: (...args: unknown[]) =>
    mocks.requestDecision(...args),
  useAcquisitionGrowth: () => ({
    data: undefined,
    refetch: mocks.refetchGrowth,
  }),
  useAcquisitionRoute: (...args: unknown[]) =>
    mocks.useAcquisitionRoute(...args),
}));

vi.mock("@/features/runs/api/useHumanDecisions", () => ({
  HumanDecisionRecoveryAttemptError: class HumanDecisionRecoveryAttemptError extends Error {
    readonly code: string;
    readonly status: number;

    constructor(code: string, status: number, message = code) {
      super(message);
      this.name = "HumanDecisionRecoveryAttemptError";
      this.code = code;
      this.status = status;
    }
  },
  fetchHumanDecisionEvidence: (...args: unknown[]) =>
    mocks.fetchEvidence(...args),
  useCreateHumanDecision: () => ({
    mutateAsync: mocks.createDecision,
    recoverPending: mocks.recoverPending,
    recoveryPosture: mocks.recoveryPosture(),
  }),
  useHumanDecisionGate: (...args: unknown[]) =>
    mocks.useHumanDecisionGate(...args),
  withoutHumanDecisionOwnedQuery: () => "",
}));

vi.mock("@/features/runs/domain/humanDecisionPresentation", () => ({
  buildHumanDecisionMutation: () => ({
    action: "approve",
    action_kind: "data_request",
    decision_mode: "ordinary",
    source_kind: "agent_action_authority",
    source_ref: requestedDecision().authority_decision_ref,
  }),
}));

vi.mock("@/features/runs/components/HumanDecisionGate", () => ({
  HumanDecisionGate: ({
    onSubmit,
  }: {
    onSubmit: (input: object) => Promise<void>;
  }) => (
    <button
      type="button"
      onClick={() =>
        void onSubmit({
          accountabilityStatement: "I accept accountability",
          action: "approve",
          blockingReason: "",
          decisionMode: "ordinary",
          dissentStatement: "",
          overrideReason: "",
        }).catch(() => undefined)
      }
    >
      Approve through DS9
    </button>
  ),
}));

vi.mock("./acquisitionRouteExport", () => ({
  downloadAcquisitionRoutePacket: (...args: unknown[]) =>
    mocks.download(...args),
}));

import { AcquisitionApprovalFlow } from "./AcquisitionApprovalFlow";

const digest = (suffix: string) => `sha256:${suffix.repeat(64).slice(0, 64)}`;

function epoch(status: "current" | "revalidation_required"): EpochSemantics {
  const requiresRevalidation = status === "revalidation_required";
  return {
    asOf: requiresRevalidation
      ? "2026-08-29T13:00:00Z"
      : "2026-08-29T12:00:00Z",
    asOfReason: null,
    currentEpochRef: digest(requiresRevalidation ? "b" : "a"),
    epochRefs: [digest("a"), ...(requiresRevalidation ? [digest("b")] : [])],
    kind: "admitted",
    projectionSemanticHash: digest(requiresRevalidation ? "d" : "c"),
    revalidationRequired: requiresRevalidation,
    status,
    validityStatus: requiresRevalidation ? "review_required" : "active",
  };
}

function runRoute(
  overrides: Partial<PendingAcquisitionRouteV11> = {},
): PendingAcquisitionRouteV11 {
  return {
    authority_badge: "behavioral_fixture_not_production",
    authority_capability: "ready",
    cell_id: "cell-1",
    cost_basis: {
      record_content_hash: digest("c"),
      schema_version: "AcquisitionCostBasisRecord@1.0",
      total_amount: 1250,
    },
    execution_capability: "ready",
    external_nonclosures: [],
    planner_record_id: "plan-1",
    planner_report_hash: digest("p"),
    qualification_predicate: "not_established",
    qualification_reason: "policy_admission_missing",
    qualification_status: "pending_epoch_activation",
    recommended_strategy: "survey",
    replay_pins: {
      compiled_content_hash: digest("a"),
      compiled_ref: digest("b"),
      cost_basis_hash: digest("c"),
      design_problem_ref: digest("d"),
      source_job_id: "source-job-1",
      terminal_event_id: "terminal-event-1",
    },
    route_id: digest("r"),
    route_projection_hash: digest("r"),
    route_status: "costed_actionable",
    run_id: "run-1",
    schema_version: "AcquisitionRouteProjection@1.1",
    tenant_id: "tenant-1",
    world_growth: "not_established",
    admitted_observation_delta: null,
    ...overrides,
  };
}

function paidInputAdmissionRoute(): PaidInputAdmissionAcquisitionRouteV12 {
  const ref = (
    suffix: string,
    kind: string,
    mediaType = "application/json",
  ) => ({
    artifact_id: `sha256:${suffix.repeat(64).slice(0, 64)}`,
    kind,
    media_type: mediaType,
    manifest_profile_sha256: `sha256:${suffix.repeat(64).slice(0, 64)}`,
  });
  const selection = {
    schema_version: "NativePaidInputAdmissionSelection@1.0" as const,
    original_action_job_id: "prior-paid-action-1",
    attempt_ref: ref("a", "runtime_quality.acquisition_world_growth_attempt"),
    executing_phase_ref: ref(
      "b",
      "runtime_quality.acquisition_route_phase_receipt",
    ),
    terminal_ref: ref("c", "runtime_quality.acquisition_route_loop_receipt"),
    deferral_ref: ref("d", "runtime_quality.acquisition_world_growth_deferral"),
    negative_receipt_ref: ref(
      "e",
      "epoch.production_receipt",
      "application/vnd.polisyos.epoch-production-receipt+json",
    ),
    prepared_epoch_ref: ref(
      "f",
      "epoch.prepared",
      "application/vnd.polisyos.epoch+json",
    ),
    owner_declared_profile_ref: ref(
      "6",
      "runtime.quality.native_derivation_leaf_cost_profile",
    ),
  };
  const costBasisHash = digest("c");
  const standard = runRoute();
  return {
    ...standard,
    cost_basis: {
      currency: "USD",
      owner_declared_profile_ref: selection.owner_declared_profile_ref,
      record_content_hash: costBasisHash,
      record_ref: "sha256:historical-cost-basis",
      schema_version: "AcquisitionCostBasisRecord@1.1",
      total_amount: 1250,
    },
    prior_paid_input_admission: selection,
    replay_pins: { ...standard.replay_pins, cost_basis_hash: costBasisHash },
    route_projection_hash: digest("q"),
    route_status: "paid_input_admission_only",
    schema_version: "AcquisitionRouteProjection@1.2",
  };
}

function requestedDecision(): AcquisitionDecisionRequestResponseCurrent {
  return {
    authority_decision_ref: digest("e"),
    human_decision_request: { required_role: "budget_owner" },
    outcome: "decision_required",
    route_id: runRoute().route_id,
    run_id: "run-1",
    world_growth: "not_established",
  };
}

function acceptedExecution(): AcquisitionExecutionResponseCurrent {
  return {
    authority_decision_ref: requestedDecision().authority_decision_ref,
    job_id: "acquisition-job-1",
    receipt_phase: "requested",
    route_id: runRoute().route_id,
    run_id: "run-1",
    status: "accepted",
    world_growth: "not_established",
  };
}

function recoveredHumanDecisionResult(
  kind: "recovered_committed" | "recovered_expired" = "recovered_committed",
) {
  const receipt = {
    durable_event_id: "human-event-1",
    record: { action: "approve" },
    record_digest: digest("h"),
    record_ref: digest("h"),
    reservation_id: "reservation-1",
    reservation_version: 1,
    run_id: "run-1",
  };
  return {
    kind,
    receipt,
    recovery: {
      authority_purpose: "historical_human_decision_custody_only",
      binding_rule: "policyos.runtime.human_decision_submission_binding.v2",
      binding_sha256: digest("b"),
      cell_id: null,
      durable_event_id: "human-event-1",
      operational_authority: false,
      record_digest: digest("h"),
      record_ref: {
        artifact_id: digest("h"),
        kind: "runtime_quality.agent_action_human_decision",
        manifest_profile_sha256: digest("p"),
        media_type: "application/json",
      },
      record_valid_until: "2030-01-01T00:00:00Z",
      reservation_id: "reservation-1",
      reservation_state: kind === "recovered_expired" ? "expired" : "committed",
      reservation_version: 1,
      run_id: "run-1",
      schema_version: "policyos.runtime.human_decision_recovery.v1",
      status: "committed",
      tenant_id: "tenant-1",
    },
  };
}

function routeCapture(route: AcquisitionRouteProjection = runRoute()) {
  return { packet: route, rawPacketBytes: new TextEncoder().encode("{}") };
}

function flowTree(
  route: AcquisitionRouteProjection,
  epochSemantics?: EpochSemantics,
) {
  const content = (
    <MemoryRouter initialEntries={["/runs/run-1/case?paper=kept"]}>
      <AcquisitionApprovalFlow canMutate route={route} />
    </MemoryRouter>
  );
  return (
    <LocaleProvider>
      {epochSemantics ? (
        <EpochSemanticsProvider value={epochSemantics}>
          {content}
        </EpochSemanticsProvider>
      ) : (
        content
      )}
    </LocaleProvider>
  );
}

function renderFlow(
  route: AcquisitionRouteProjection = runRoute(),
  epochSemantics?: EpochSemantics,
) {
  mocks.useAcquisitionRoute.mockReturnValue({
    data: routeCapture(route),
    refetch: mocks.refetchRoute,
  });
  return render(flowTree(route, epochSemantics));
}

describe("AcquisitionApprovalFlow", () => {
  beforeEach(() => {
    onlineManager.setOnline(true);
    Object.values(mocks).forEach((mock) => mock.mockReset());
    mocks.refetchRoute.mockResolvedValue({ data: routeCapture() });
    mocks.refetchGrowth.mockResolvedValue({ data: undefined });
    mocks.requestDecision.mockResolvedValue(requestedDecision());
    mocks.createDecision.mockResolvedValue({
      kind: "created",
      receipt: {
        durable_event_id: "human-event-1",
        record: { action: "approve" },
        record_digest: digest("h"),
        record_ref: digest("h"),
        reservation_id: "reservation-1",
        reservation_version: 1,
        run_id: "run-1",
      },
    });
    mocks.recoveryPosture.mockReturnValue(null);
    mocks.execute.mockResolvedValue(acceptedExecution());
    mocks.useControlJobStatus.mockReturnValue({ data: undefined });
    mocks.useHumanDecisionGate.mockReturnValue({
      clear: mocks.clearGate,
      data: {
        packet: { continuation: { source_kind: "agent_action_authority" } },
      },
      hasSelector: true,
      isError: false,
      isLoading: false,
      revalidate: mocks.revalidateGate,
    });
    mocks.revalidateGate.mockResolvedValue({
      packet: {
        continuation: { source_kind: "agent_action_authority" },
        exposure: { exposure_session_ref: digest("x") },
        run_id: "run-1",
        source_kind: "agent_action_authority",
        source_ref: requestedDecision().authority_decision_ref,
      },
    });
  });

  afterEach(() => {
    onlineManager.setOnline(true);
  });

  it("renders its own epoch disclosure and reacts to revalidation", () => {
    const route = runRoute();
    const { rerender } = renderFlow(route, epoch("current"));
    const flow = screen.getByTestId("acquisition-approval-flow");
    const semantics = within(flow).getByTestId(
      "acquisition-approval-time-semantics",
    );
    expect(
      within(semantics).getByTestId("time-semantics-as-of"),
    ).toHaveTextContent("2026-08-29T12:00:00Z");
    expect(
      within(semantics).getByTestId("time-semantics-epoch-status"),
    ).toHaveTextContent("current");
    expect(
      within(semantics).getByTestId("time-semantics-validity"),
    ).toHaveTextContent("active");

    rerender(flowTree(route, epoch("revalidation_required")));
    const moved = within(
      screen.getByTestId("acquisition-approval-time-semantics"),
    );
    expect(moved.getByTestId("time-semantics-as-of")).toHaveTextContent(
      "2026-08-29T13:00:00Z",
    );
    expect(moved.getByTestId("time-semantics-epoch-status")).toHaveTextContent(
      "revalidation required",
    );
    expect(moved.getByTestId("time-semantics-validity")).toHaveTextContent(
      "review_required",
    );
    expect(moved.getByTestId("time-semantics-revalidation")).toHaveTextContent(
      "required",
    );

    rerender(flowTree(route));
    const unknown = within(
      screen.getByTestId("acquisition-approval-time-semantics"),
    );
    expect(
      unknown.getByTestId("time-semantics-epoch-status"),
    ).toHaveTextContent("not established");
    expect(unknown.getByTestId("time-semantics-epoch")).toHaveTextContent(
      "Epoch not established",
    );
    expect(unknown.getByTestId("time-semantics-validity")).toHaveTextContent(
      "not established",
    );
  });

  it("turns the refusal path into accountable approval and one fresh execution", async () => {
    renderFlow();
    const user = userEvent.setup();

    await user.click(
      screen.getByRole("button", { name: "Request accountable review" }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Approve through DS9" }),
    );

    await waitFor(() => expect(mocks.execute).toHaveBeenCalledTimes(1));
    expect(mocks.requestDecision).toHaveBeenCalledTimes(1);
    expect(mocks.createDecision).toHaveBeenCalledTimes(1);
    expect(mocks.refetchRoute).toHaveBeenCalledTimes(2);
    const executeBody = mocks.execute.mock.calls[0]?.[2];
    expect(executeBody).toMatchObject({
      human_decision_record_ref: digest("h"),
      planner_report_hash: digest("p"),
      route_projection_hash: digest("r"),
    });
    expect(
      screen.getByTestId("acquisition-execution-timeline"),
    ).toHaveTextContent("requested");
  });

  it("recovers a pending decision without resubmitting before current gate checks", async () => {
    const pending = {
      binding_rule: "policyos.runtime.human_decision_submission_binding.v2",
      binding_sha256: digest("b"),
      reservation_id: "reservation-1",
      reservation_version: 1,
      status: "pending",
    };
    mocks.createDecision.mockResolvedValueOnce({
      kind: "recovery_pending",
      recovery: pending,
    });
    mocks.recoveryPosture.mockReturnValue({
      kind: "recovery_pending",
      recovery: pending,
    });
    mocks.recoverPending.mockImplementation(async () => {
      mocks.recoveryPosture.mockReturnValue(null);
      return recoveredHumanDecisionResult();
    });
    renderFlow();
    const user = userEvent.setup();

    await user.click(
      screen.getByRole("button", { name: "Request accountable review" }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Approve through DS9" }),
    );

    expect(mocks.createDecision).toHaveBeenCalledTimes(1);
    expect(mocks.execute).not.toHaveBeenCalled();
    expect(
      screen.getByTestId("human-decision-submission-status"),
    ).toHaveTextContent("The original submission remains pending.");
    await user.click(
      screen.getByRole("button", { name: "Check this submission" }),
    );

    await waitFor(() => expect(mocks.execute).toHaveBeenCalledTimes(1));
    expect(mocks.createDecision).toHaveBeenCalledTimes(1);
    expect(mocks.recoverPending).toHaveBeenCalledTimes(1);
    expect(mocks.revalidateGate).toHaveBeenCalledTimes(2);
    expect(mocks.execute.mock.calls[0]?.[2]).toMatchObject({
      human_decision_record_ref: digest("h"),
    });
  });

  it("never executes an expired recovered record", async () => {
    mocks.createDecision.mockResolvedValueOnce(
      recoveredHumanDecisionResult("recovered_expired"),
    );
    renderFlow();
    const user = userEvent.setup();

    await user.click(
      screen.getByRole("button", { name: "Request accountable review" }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Approve through DS9" }),
    );

    expect(mocks.execute).not.toHaveBeenCalled();
    expect(
      screen.getByTestId("human-decision-submission-status"),
    ).toHaveTextContent(
      "The committed record was recovered, but its validity has expired.",
    );
    const timeline = within(
      screen.getByTestId("acquisition-execution-timeline"),
    );
    expect(timeline.getByText("custody_expired")).toBeInTheDocument();
    expect(
      timeline.getAllByText(
        "Expired historical custody only; no current approval.",
      ).length,
    ).toBeGreaterThan(0);
    expect(mocks.clearGate).toHaveBeenCalled();
  });

  it("does not carry a pending approval recovery into another run", async () => {
    const pending = {
      binding_rule: "policyos.runtime.human_decision_submission_binding.v2",
      binding_sha256: digest("b"),
      reservation_id: "reservation-1",
      reservation_version: 1,
      status: "pending",
    };
    let resolveRecovery:
      | ((result: ReturnType<typeof recoveredHumanDecisionResult>) => void)
      | undefined;
    mocks.createDecision.mockResolvedValueOnce({
      kind: "recovery_pending",
      recovery: pending,
    });
    mocks.recoveryPosture.mockReturnValue({
      kind: "recovery_pending",
      recovery: pending,
    });
    mocks.recoverPending.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRecovery = resolve;
        }),
    );
    const firstRun = runRoute();
    const { rerender } = renderFlow(firstRun);
    const user = userEvent.setup();

    await user.click(
      screen.getByRole("button", { name: "Request accountable review" }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Approve through DS9" }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Check this submission" }),
    );
    await waitFor(() => expect(mocks.recoverPending).toHaveBeenCalledTimes(1));

    mocks.recoveryPosture.mockReturnValue(null);
    rerender(flowTree(runRoute({ run_id: "run-2" })));
    await waitFor(() =>
      expect(
        screen.queryByTestId("human-decision-submission-status"),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: "Request accountable review" }),
    ).toBeDisabled();
    resolveRecovery?.(recoveredHumanDecisionResult());

    await waitFor(() => expect(mocks.execute).not.toHaveBeenCalled());
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Request accountable review" }),
      ).toBeEnabled(),
    );
    expect(mocks.createDecision).toHaveBeenCalledTimes(1);
    expect(mocks.createDecision.mock.calls[0]?.[0].runId).toBe("run-1");
    expect(
      screen.queryByTestId("human-decision-submission-status"),
    ).not.toBeInTheDocument();
  });

  it.each(["omitted", "null"] as const)(
    "does not offer review when the legacy route status is %s",
    (status) => {
      const route = { ...runRoute() } as unknown as Record<string, unknown>;
      if (status === "omitted") {
        delete route.route_status;
      } else {
        route.route_status = null;
      }

      renderFlow(route as unknown as AcquisitionRouteProjection);

      expect(
        screen.queryByRole("button", { name: "Request accountable review" }),
      ).not.toBeInTheDocument();
      expect(screen.getByTestId("acquisition-route-detail")).toHaveTextContent(
        "not established",
      );
      expect(screen.getByTestId("acquisition-route-detail")).toHaveTextContent(
        "1250",
      );
      expect(mocks.requestDecision).not.toHaveBeenCalled();
      expect(mocks.execute).not.toHaveBeenCalled();
    },
  );

  it("re-admits a prior paid input through current review and the hash-bound DS9 action", async () => {
    const route = paidInputAdmissionRoute();
    mocks.refetchRoute.mockResolvedValue({ data: routeCapture(route) });
    renderFlow(route);
    const user = userEvent.setup();

    const review = screen.getByRole("button", {
      name: "Request current admission review",
    });
    expect(review).toBeEnabled();
    expect(screen.getByTestId("prior-paid-input-admission")).toHaveTextContent(
      "prior-paid-action-1",
    );
    expect(screen.getByTestId("prior-paid-input-admission")).toHaveTextContent(
      "does not itself grant current action authority",
    );
    await user.click(review);

    await waitFor(() => expect(mocks.requestDecision).toHaveBeenCalledTimes(1));
    const decisionBody = mocks.requestDecision.mock.calls[0]?.[2];
    expect(decisionBody).toMatchObject({
      idempotency_key: route.route_projection_hash,
      route_projection_hash: route.route_projection_hash,
    });
    expect(decisionBody).not.toHaveProperty("prior_paid_input_admission");
    expect(decisionBody).not.toHaveProperty("action_mode");
    expect(mocks.execute).not.toHaveBeenCalled();
    expect(mocks.useHumanDecisionGate).toHaveBeenLastCalledWith(
      route.run_id,
      expect.stringContaining("source_kind=agent_action_authority"),
    );

    await user.click(
      await screen.findByRole("button", { name: "Approve through DS9" }),
    );
    await waitFor(() => expect(mocks.execute).toHaveBeenCalledTimes(1));
    const executionBody = mocks.execute.mock.calls[0]?.[2];
    expect(executionBody).toMatchObject({
      human_decision_record_ref: digest("h"),
      idempotency_key: `${route.route_projection_hash}:${digest("h")}`,
      route_projection_hash: route.route_projection_hash,
    });
    expect(executionBody).not.toHaveProperty("prior_paid_input_admission");
  });

  it("fails DS15-OFFLINE-AUTHORITY before any decision or execution fetch", async () => {
    onlineManager.setOnline(false);
    renderFlow();

    await userEvent
      .setup()
      .click(
        screen.getByRole("button", { name: "Request accountable review" }),
      );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "DS15-OFFLINE-AUTHORITY",
    );
    expect(mocks.requestDecision).not.toHaveBeenCalled();
    expect(mocks.execute).not.toHaveBeenCalled();
  });

  it("rejects stale decision replay when the owner route changes before execute", async () => {
    mocks.refetchRoute
      .mockResolvedValueOnce({ data: routeCapture() })
      .mockResolvedValueOnce({
        data: routeCapture(
          runRoute({
            cost_basis: {
              ...runRoute().cost_basis,
              total_amount: 1251,
            },
          }),
        ),
      });
    renderFlow();
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: "Request accountable review" }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Approve through DS9" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "DS15-STALE-DECISION-REPLAY",
    );
    expect(mocks.execute).not.toHaveBeenCalled();
  });

  it("does not misclassify reordered JSON object keys as a stale route", async () => {
    const original = runRoute();
    const reordered: PendingAcquisitionRouteV11 = {
      admitted_observation_delta: original.admitted_observation_delta,
      world_growth: original.world_growth,
      tenant_id: original.tenant_id,
      schema_version: original.schema_version,
      run_id: original.run_id,
      route_status: original.route_status,
      route_projection_hash: original.route_projection_hash,
      route_id: original.route_id,
      replay_pins: {
        terminal_event_id: original.replay_pins.terminal_event_id,
        source_job_id: original.replay_pins.source_job_id,
        design_problem_ref: original.replay_pins.design_problem_ref,
        cost_basis_hash: original.replay_pins.cost_basis_hash,
        compiled_ref: original.replay_pins.compiled_ref,
        compiled_content_hash: original.replay_pins.compiled_content_hash,
      },
      recommended_strategy: original.recommended_strategy,
      qualification_status: original.qualification_status,
      qualification_reason: original.qualification_reason,
      qualification_predicate: original.qualification_predicate,
      planner_report_hash: original.planner_report_hash,
      planner_record_id: original.planner_record_id,
      external_nonclosures: original.external_nonclosures,
      execution_capability: original.execution_capability,
      cost_basis: original.cost_basis,
      cell_id: original.cell_id,
      authority_capability: original.authority_capability,
      authority_badge: original.authority_badge,
    };
    mocks.refetchRoute.mockResolvedValue({ data: routeCapture(reordered) });
    renderFlow(original);
    const user = userEvent.setup();

    await user.click(
      screen.getByRole("button", { name: "Request accountable review" }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Approve through DS9" }),
    );

    await waitFor(() => expect(mocks.execute).toHaveBeenCalledTimes(1));
  });

  it("prevents double execution while one approval is in flight", async () => {
    let release:
      | ((value: AcquisitionExecutionResponseCurrent) => void)
      | undefined;
    mocks.execute.mockImplementation(
      () =>
        new Promise<AcquisitionExecutionResponseCurrent>((resolve) => {
          release = resolve;
        }),
    );
    renderFlow();
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: "Request accountable review" }),
    );
    const approve = await screen.findByRole("button", {
      name: "Approve through DS9",
    });
    await Promise.all([user.click(approve), user.click(approve)]);
    await waitFor(() => expect(mocks.execute).toHaveBeenCalledTimes(1));
    release?.(acceptedExecution());
  });

  it.each([
    ["missing", {}],
    [
      "default-zero",
      {
        record_content_hash: digest("c"),
        schema_version: "AcquisitionCostBasisRecord@1.0",
        total_amount: 0,
      },
    ],
    [
      "unverified",
      {
        record_content_hash: digest("u"),
        schema_version: "AcquisitionCostBasisRecord@1.0",
        total_amount: 1250,
      },
    ],
  ])("stops a %s cost before review", (_name, costBasis) => {
    renderFlow(runRoute({ cost_basis: costBasis }));

    expect(
      screen.getByRole("button", { name: "Request accountable review" }),
    ).toBeDisabled();
    expect(screen.getByTestId("acquisition-cost-refusal")).toHaveTextContent(
      "not_established",
    );
  });
});
