/* eslint-disable testing-library/no-container, testing-library/no-node-access */
import { render, screen, within } from "@testing-library/react";
import type {
  AcquisitionDecisionRequestResponse,
  AcquisitionExecutionResponse,
  AcquisitionGrowthPayload,
  AcquisitionRouteProjection,
} from "@polisyos/runtime-api-client";

import type { ControlJobResponse } from "@/api/hooks/useControlJobStatus";
import type { HumanDecisionCreateReceipt } from "@/api/validators";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { AcquisitionExecutionTimeline } from "./AcquisitionExecutionTimeline";
import { decodeAcquisitionTimelineMachineFacts } from "./acquisitionRouteExport";

const digest = (suffix: string) => `sha256:${suffix.repeat(64).slice(0, 64)}`;

function route(): AcquisitionRouteProjection {
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
    schema_version: "AcquisitionRouteProjection@1.0",
    tenant_id: "tenant-1",
    world_growth: "no_growth",
  };
}

function decision(): AcquisitionDecisionRequestResponse {
  return {
    authority_decision_ref: digest("e"),
    human_decision_request: { required_role: "budget_owner" },
    outcome: "decision_required",
    route_id: route().route_id,
    run_id: "run-1",
    world_growth: "no_growth",
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

function execution(): AcquisitionExecutionResponse {
  return {
    authority_decision_ref: decision().authority_decision_ref,
    job_id: "acquisition-job-1",
    receipt_phase: "requested",
    route_id: route().route_id,
    run_id: "run-1",
    status: "accepted",
    world_growth: "no_growth",
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
    world_growth: "no_growth",
    ...overrides,
  };
}

describe("AcquisitionExecutionTimeline", () => {
  it("renders refusal, cost, approval, execution and no-growth as one ordered motion", () => {
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
    expect(timeline).toHaveTextContent("quarantined_no_growth");
    expect(timeline).toHaveTextContent("policy_admission_missing");
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
