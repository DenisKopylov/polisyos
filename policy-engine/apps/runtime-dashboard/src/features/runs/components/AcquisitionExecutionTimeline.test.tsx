/* eslint-disable testing-library/no-container, testing-library/no-node-access */
import { render, screen, within } from "@testing-library/react";
import type { AcquisitionGrowthPayload } from "@polisyos/runtime-api-client";

import type { ControlJobResponse } from "@/api/hooks/useControlJobStatus";
import type { HumanDecisionCreateReceipt } from "@/api/validators";
import {
  acquisitionRouteProjectionSchema,
  type AcquisitionDecisionRequestResponseCurrent,
  type AcquisitionExecutionResponseCurrent,
  type AcquisitionRouteProjection,
  type NoGrowthAcquisitionRouteV11,
  type PendingAcquisitionRouteV11,
} from "@/features/runs/api/acquisitionRouteValidators";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { AcquisitionExecutionTimeline } from "./AcquisitionExecutionTimeline";
import { decodeAcquisitionTimelineMachineFacts } from "./acquisitionRouteExport";

const digest = (suffix: string) => `sha256:${suffix.repeat(64).slice(0, 64)}`;

function parsePendingRoute(value: unknown): PendingAcquisitionRouteV11 {
  const parsed = acquisitionRouteProjectionSchema.parse(value);
  if (
    parsed.schema_version !== "AcquisitionRouteProjection@1.1" ||
    parsed.world_growth !== "not_established"
  ) {
    throw new Error("pending route fixture must satisfy the v1.1 schema");
  }
  return parsed;
}

function parseNoGrowthRoute(value: unknown): NoGrowthAcquisitionRouteV11 {
  const parsed = acquisitionRouteProjectionSchema.parse(value);
  if (
    parsed.schema_version !== "AcquisitionRouteProjection@1.1" ||
    parsed.qualification_status !== "activated" ||
    parsed.world_growth !== "no_growth"
  ) {
    throw new Error("selected-zero route fixture must satisfy the v1.1 schema");
  }
  return parsed;
}

function route(): PendingAcquisitionRouteV11 {
  return parsePendingRoute({
    authority_badge: "behavioral_fixture_not_production",
    authority_capability: "ready",
    cell_id: "cell-1",
    cost_basis: {
      record_content_hash: digest("c"),
      schema_version: "AcquisitionCostBasisRecord@1.0",
      total_amount: 1250,
    },
    execution_capability: "ready",
    external_nonclosures: [
      "fresh_positive_production_route:absent/unallocated",
    ],
    planner_record_id: "acquisition-plan-1",
    planner_report_hash: digest("p"),
    qualification_predicate: "not_established",
    qualification_reason: "policy_admission_missing",
    qualification_status: "pending_epoch_activation",
    recommended_strategy: "targeted_primary_data_collection",
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
  });
}

function noGrowthRoute(): NoGrowthAcquisitionRouteV11 {
  return parseNoGrowthRoute({
    ...route(),
    admitted_observation_delta: 0,
    authority_badge: "native_owner_verified",
    qualification_predicate: "independently_reconciled",
    qualification_reason: "native_owner_readback",
    qualification_status: "activated",
    world_growth: "no_growth",
  });
}

function decision(
  selectedRoute: AcquisitionRouteProjection = route(),
): AcquisitionDecisionRequestResponseCurrent {
  return {
    authority_decision_ref: digest("e"),
    human_decision_request: { required_role: "budget_owner" },
    outcome: "decision_required",
    route_id: selectedRoute.route_id,
    run_id: selectedRoute.run_id,
    world_growth: "not_established",
  };
}

function humanDecision(): HumanDecisionCreateReceipt {
  return {
    durable_event_id: "event-human-1",
    record: { action: "approve" },
    record_digest: digest("h"),
    record_ref: digest("h"),
    reservation_id: "reservation-1",
    reservation_version: 1,
    run_id: "run-1",
  };
}

function execution(
  selectedRoute: AcquisitionRouteProjection = route(),
  selectedDecision: AcquisitionDecisionRequestResponseCurrent = decision(
    selectedRoute,
  ),
): AcquisitionExecutionResponseCurrent {
  return {
    authority_decision_ref: selectedDecision.authority_decision_ref,
    job_id: "acquisition-job-1",
    receipt_phase: "requested",
    route_id: selectedRoute.route_id,
    run_id: selectedRoute.run_id,
    status: "accepted",
    world_growth: "not_established",
  };
}

function job(
  state: ControlJobResponse["state"] = "completed",
  receiptPhase = "terminal",
): ControlJobResponse {
  return {
    effective_execution_profile: "production",
    job_id: "acquisition-job-1",
    kind: "acquisition",
    meta: { request_id: "request-1" },
    progress: {
      receipt_phase: receiptPhase,
      terminal_receipt_ref: digest("t"),
    },
    run_id: "run-1",
    state,
  } satisfies ControlJobResponse;
}

function history(
  overrides: Partial<AcquisitionGrowthPayload["n13b_history"]> = {},
): AcquisitionGrowthPayload["n13b_history"] {
  return {
    admission: "not_reached",
    attempt_count: 1,
    epoch_qualification: {
      appointment_state: "unappointed",
      appointment_would_establish:
        "authority to qualify native semantic production, append its history head and permit overlay activation",
      appointment_would_not_establish: [
        "gap shape",
        "passport validity",
        "positive delta",
        "re-entry",
      ],
      authority_owner_ref: null,
      authority_role: "semantic epoch policy-admission qualifier",
      code: "policy_admission_missing",
      epoch_state: "pending_epoch_activation",
      status: "not_established",
    },
    execution_phase: "terminal",
    overlay_epoch_count: 0,
    quarantine: "raw_terminal",
    quarantine_count: 1,
    raw_response_count: 1,
    reentry: "not_established",
    response_admitted_count: 0,
    terminal_count: 1,
    world_growth: "not_established",
    ...overrides,
  };
}

function projectedN13bNoGrowthHistory(): AcquisitionGrowthPayload["n13b_history"] {
  return history({
    attempt_count: 5,
    quarantine_count: 5,
    raw_response_count: 2,
    reentry: "deeper_terminal",
    terminal_count: 5,
    world_growth: "no_growth",
  });
}

type N13bHistory = AcquisitionGrowthPayload["n13b_history"];
type RouteControl = Readonly<{
  name: string;
  route: PendingAcquisitionRouteV11 | NoGrowthAcquisitionRouteV11;
  expected: Pick<
    PendingAcquisitionRouteV11 | NoGrowthAcquisitionRouteV11,
    | "admitted_observation_delta"
    | "authority_badge"
    | "qualification_predicate"
    | "qualification_reason"
    | "qualification_status"
    | "world_growth"
  >;
}>;
type HistoryControl = Readonly<{
  name: string;
  history: N13bHistory;
  disposition: string;
  expected: Readonly<
    Pick<
      N13bHistory,
      | "admission"
      | "attempt_count"
      | "execution_phase"
      | "overlay_epoch_count"
      | "quarantine"
      | "quarantine_count"
      | "raw_response_count"
      | "reentry"
      | "response_admitted_count"
      | "terminal_count"
      | "world_growth"
    >
  > & {
    epoch_qualification: Pick<
      N13bHistory["epoch_qualification"],
      "appointment_state" | "authority_owner_ref" | "code" | "status"
    >;
  };
}>;

const routeControls = [
  {
    name: "pending-route-unknown",
    route: route(),
    expected: {
      admitted_observation_delta: null,
      authority_badge: "behavioral_fixture_not_production",
      qualification_predicate: "not_established",
      qualification_reason: "policy_admission_missing",
      qualification_status: "pending_epoch_activation",
      world_growth: "not_established",
    },
  },
  {
    name: "selected-zero-route-no-growth",
    route: noGrowthRoute(),
    expected: {
      admitted_observation_delta: 0,
      authority_badge: "native_owner_verified",
      qualification_predicate: "independently_reconciled",
      qualification_reason: "native_owner_readback",
      qualification_status: "activated",
      world_growth: "no_growth",
    },
  },
] satisfies readonly RouteControl[];

const historyControls = [
  {
    name: "raw-terminal-history-unknown",
    history: history(),
    disposition: "not_established:not_established",
    expected: {
      admission: "not_reached",
      attempt_count: 1,
      execution_phase: "terminal",
      overlay_epoch_count: 0,
      quarantine: "raw_terminal",
      quarantine_count: 1,
      raw_response_count: 1,
      reentry: "not_established",
      response_admitted_count: 0,
      terminal_count: 1,
      world_growth: "not_established",
      epoch_qualification: {
        appointment_state: "unappointed",
        authority_owner_ref: null,
        code: "policy_admission_missing",
        status: "not_established",
      },
    },
  },
  {
    name: "raw-terminal-global-history-no-growth",
    history: projectedN13bNoGrowthHistory(),
    disposition: "quarantined_no_growth",
    expected: {
      admission: "not_reached",
      attempt_count: 5,
      execution_phase: "terminal",
      overlay_epoch_count: 0,
      quarantine: "raw_terminal",
      quarantine_count: 5,
      raw_response_count: 2,
      reentry: "deeper_terminal",
      response_admitted_count: 0,
      terminal_count: 5,
      world_growth: "no_growth",
      epoch_qualification: {
        appointment_state: "unappointed",
        authority_owner_ref: null,
        code: "policy_admission_missing",
        status: "not_established",
      },
    },
  },
] satisfies readonly HistoryControl[];

const routeHistoryMatrix = routeControls.flatMap((routeControl) =>
  historyControls.map((historyControl) => ({
    caseName: `${routeControl.name} × ${historyControl.name}`,
    routeControl,
    historyControl,
  })),
);

describe("AcquisitionExecutionTimeline", () => {
  it("renders refusal, cost, approval, execution and raw-terminal unknown history without claiming no growth", () => {
    render(
      <LocaleProvider>
        <AcquisitionExecutionTimeline
          decision={decision()}
          execution={execution()}
          growthHistory={history()}
          humanDecision={humanDecision()}
          job={job()}
          route={route()}
        />
      </LocaleProvider>,
    );

    const timeline = screen.getByTestId("acquisition-execution-timeline");
    const facts = within(timeline).getAllByTestId("acquisition-timeline-fact");
    expect(facts.map((fact) => fact.dataset.acquisitionPhase)).toEqual([
      "refusal_with_path",
      "decision_required",
      "approved",
      "executing",
      "terminal",
      "world_history",
    ]);
    expect(timeline).toHaveTextContent("behavioral_fixture_not_production");
    expect(timeline).toHaveTextContent("1250");
    expect(timeline).toHaveTextContent("not_established:not_established");
    expect(timeline).not.toHaveTextContent("quarantined_no_growth");
    expect(timeline).toHaveTextContent("policy_admission_missing");
    expect(timeline).toHaveTextContent(
      "raw_terminal · not_established · not_established · policy_admission_missing",
    );
    expect(timeline).toHaveTextContent(
      "semantic epoch policy-admission qualifier · unappointed",
    );
    expect(timeline).toHaveTextContent("permit overlay activation");
    expect(timeline).not.toHaveTextContent("active_epoch");
    expect(
      within(timeline).getByRole("link", { name: digest("t") }),
    ).toBeInTheDocument();
    expect(facts.at(-1)).toHaveAttribute(
      "data-acquisition-scope",
      "global_n13b_history",
    );
  });

  it("pins the complete two-route by two-history control denominator", () => {
    expect(routeControls).toHaveLength(2);
    expect(historyControls).toHaveLength(2);
    expect(routeHistoryMatrix).toHaveLength(
      routeControls.length * historyControls.length,
    );
    expect(
      routeHistoryMatrix
        .map(
          ({ routeControl, historyControl }) =>
            `${routeControl.name}/${historyControl.name}`,
        )
        .sort(),
    ).toEqual(
      [
        "pending-route-unknown/raw-terminal-history-unknown",
        "pending-route-unknown/raw-terminal-global-history-no-growth",
        "selected-zero-route-no-growth/raw-terminal-history-unknown",
        "selected-zero-route-no-growth/raw-terminal-global-history-no-growth",
      ].sort(),
    );
  });

  it.each(routeHistoryMatrix)(
    "$caseName preserves selected route and global history as separate facts",
    ({ routeControl, historyControl }) => {
      const selectedDecision = decision(routeControl.route);
      render(
        <LocaleProvider>
          <AcquisitionExecutionTimeline
            decision={selectedDecision}
            execution={execution(routeControl.route, selectedDecision)}
            growthHistory={historyControl.history}
            humanDecision={humanDecision()}
            job={job()}
            route={routeControl.route}
          />
        </LocaleProvider>,
      );

      const timeline = screen.getByTestId("acquisition-execution-timeline");
      const facts = within(timeline).getAllByTestId(
        "acquisition-timeline-fact",
      );
      const routeFact = facts.find(
        (fact) => fact.dataset.acquisitionPhase === "refusal_with_path",
      );
      const historyFact = facts.find(
        (fact) => fact.dataset.acquisitionPhase === "world_history",
      );
      if (!routeFact || !historyFact) {
        throw new Error(
          "timeline must render both selected route and history facts",
        );
      }
      expect(routeFact).toHaveAttribute("data-acquisition-scope", "run_route");
      expect(historyFact).toHaveAttribute(
        "data-acquisition-scope",
        "global_n13b_history",
      );
      expect(timeline).toHaveTextContent(routeControl.expected.authority_badge);
      expect(routeFact).toHaveTextContent(
        `${routeControl.expected.qualification_status} · ${routeControl.expected.qualification_predicate} · ${routeControl.expected.qualification_reason}`,
      );
      expect(historyFact).toHaveTextContent(historyControl.disposition);
      expect(historyFact).toHaveTextContent(
        `${historyControl.expected.quarantine} · ${historyControl.expected.world_growth} · ${historyControl.expected.reentry} · ${historyControl.expected.epoch_qualification.code}`,
      );

      const machineFacts = decodeAcquisitionTimelineMachineFacts(timeline);
      const routeMachineFact = machineFacts.find(
        (fact) => fact.phase === "refusal_with_path",
      );
      const historyMachineFact = machineFacts.find(
        (fact) => fact.phase === "world_history",
      );
      if (!routeMachineFact || !historyMachineFact) {
        throw new Error(
          "timeline must serialize both independent machine facts",
        );
      }
      expect(routeMachineFact.value).toEqual(routeControl.route);
      expect(routeMachineFact.value).toMatchObject(routeControl.expected);
      expect(historyMachineFact.value).toEqual(historyControl.history);
      expect(historyMachineFact.value).toMatchObject(historyControl.expected);
    },
  );

  it("moves real execution state from requested to re-entry pending", () => {
    const props = {
      decision: decision(),
      execution: execution(),
      growthHistory: history(),
      humanDecision: humanDecision(),
      route: route(),
    };
    const { rerender } = render(
      <LocaleProvider>
        <AcquisitionExecutionTimeline
          {...props}
          job={job("running", "requested")}
        />
      </LocaleProvider>,
    );
    expect(screen.getByTestId("acquisition-job-phase")).toHaveTextContent(
      "requested",
    );

    rerender(
      <LocaleProvider>
        <AcquisitionExecutionTimeline
          {...props}
          job={job("running", "world_committed_reentry_pending")}
        />
      </LocaleProvider>,
    );
    expect(screen.getByTestId("acquisition-job-phase")).toHaveTextContent(
      "world_committed_reentry_pending",
    );
  });

  it("fails DS15-SAME-CASE-MISMATCH when a real receipt moves to another run", () => {
    const crossRun = { ...execution(), run_id: "run-2" };
    expect(() =>
      render(
        <LocaleProvider>
          <AcquisitionExecutionTimeline
            decision={decision()}
            execution={crossRun}
            humanDecision={humanDecision()}
            route={route()}
          />
        </LocaleProvider>,
      ),
    ).toThrow(/DS15-SAME-CASE-MISMATCH/);
  });

  it("fails DS15-MACHINE-PARITY when a rendered raw fact moves after capture", () => {
    const packet = route();
    const wire = new TextEncoder().encode(JSON.stringify(packet));
    const { container } = render(
      <LocaleProvider>
        <AcquisitionExecutionTimeline route={packet} />
      </LocaleProvider>,
    );
    expect(decodeAcquisitionTimelineMachineFacts(container)[0]?.value).toEqual(
      JSON.parse(new TextDecoder().decode(wire)),
    );

    const rendered = container.querySelector<HTMLElement>(
      '[data-acquisition-machine-fact="refusal_with_path"]',
    );
    if (!rendered) throw new Error("missing route machine fact");
    rendered.textContent = JSON.stringify({
      ...packet,
      qualification_predicate: "established",
    });

    expect(
      decodeAcquisitionTimelineMachineFacts(container)[0]?.value,
    ).not.toEqual(JSON.parse(new TextDecoder().decode(wire)));
  });
});
