import { onlineManager } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type {
  AcquisitionDecisionRequestResponse,
  AcquisitionExecutionResponse,
  AcquisitionRouteProjection,
} from "@polisyos/runtime-api-client";
import { MemoryRouter } from "react-router-dom";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

const mocks = vi.hoisted(() => ({
  clearGate: vi.fn(),
  createDecision: vi.fn(),
  download: vi.fn(),
  execute: vi.fn(),
  fetchEvidence: vi.fn(),
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
  fetchHumanDecisionEvidence: (...args: unknown[]) =>
    mocks.fetchEvidence(...args),
  useCreateHumanDecision: () => ({ mutateAsync: mocks.createDecision }),
  useHumanDecisionGate: (...args: unknown[]) =>
    mocks.useHumanDecisionGate(...args),
  withoutHumanDecisionOwnedQuery: () => "",
}));

vi.mock("@/features/runs/domain/humanDecisionPresentation", () => ({
  buildHumanDecisionMutation: () => ({
    action: "approve",
    decision_mode: "ordinary",
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

function runRoute(
  overrides: Partial<AcquisitionRouteProjection> = {},
): AcquisitionRouteProjection {
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
    schema_version: "AcquisitionRouteProjection@1.0",
    tenant_id: "tenant-1",
    world_growth: "no_growth",
    ...overrides,
  };
}

function requestedDecision(): AcquisitionDecisionRequestResponse {
  return {
    authority_decision_ref: digest("e"),
    human_decision_request: { required_role: "budget_owner" },
    outcome: "decision_required",
    route_id: runRoute().route_id,
    run_id: "run-1",
    world_growth: "no_growth",
  };
}

function acceptedExecution(): AcquisitionExecutionResponse {
  return {
    authority_decision_ref: requestedDecision().authority_decision_ref,
    job_id: "acquisition-job-1",
    receipt_phase: "requested",
    route_id: runRoute().route_id,
    run_id: "run-1",
    status: "accepted",
    world_growth: "no_growth",
  };
}

function routeCapture(route = runRoute()) {
  return { packet: route, rawPacketBytes: new TextEncoder().encode("{}") };
}

function renderFlow(route = runRoute()) {
  mocks.useAcquisitionRoute.mockReturnValue({
    data: routeCapture(route),
    refetch: mocks.refetchRoute,
  });
  return render(
    <LocaleProvider>
      <MemoryRouter initialEntries={["/runs/run-1/case?paper=kept"]}>
        <AcquisitionApprovalFlow canMutate route={route} />
      </MemoryRouter>
    </LocaleProvider>,
  );
}

describe("AcquisitionApprovalFlow", () => {
  beforeEach(() => {
    onlineManager.setOnline(true);
    Object.values(mocks).forEach((mock) => mock.mockReset());
    mocks.refetchRoute.mockResolvedValue({ data: routeCapture() });
    mocks.refetchGrowth.mockResolvedValue({ data: undefined });
    mocks.requestDecision.mockResolvedValue(requestedDecision());
    mocks.createDecision.mockResolvedValue({
      durable_event_id: "human-event-1",
      record: { action: "approve" },
      record_digest: digest("h"),
      record_ref: digest("h"),
      reservation_id: "reservation-1",
      reservation_version: 1,
      run_id: "run-1",
    });
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
        source_kind: "agent_action_authority",
        source_ref: requestedDecision().authority_decision_ref,
      },
    });
  });

  afterEach(() => {
    onlineManager.setOnline(true);
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
    const reordered = Object.fromEntries(
      Object.entries(original).reverse(),
    ) as AcquisitionRouteProjection;
    reordered.replay_pins = Object.fromEntries(
      Object.entries(original.replay_pins).reverse(),
    ) as AcquisitionRouteProjection["replay_pins"];
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
    let release: ((value: AcquisitionExecutionResponse) => void) | undefined;
    mocks.execute.mockImplementation(
      () =>
        new Promise<AcquisitionExecutionResponse>((resolve) => {
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
