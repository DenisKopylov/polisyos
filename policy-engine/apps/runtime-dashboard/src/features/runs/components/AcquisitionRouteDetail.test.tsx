import { render, screen, within } from "@testing-library/react";
import type {
  AcquisitionRouteProjection,
  StructuralRouteProjection,
} from "@polisyos/runtime-api-client";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import { Button } from "@polisyos/atlas-ui";

import { AcquisitionRouteDetail } from "./AcquisitionRouteDetail";

function runRoute(): AcquisitionRouteProjection {
  return {
    authority_badge: "behavioral_fixture_not_production",
    authority_capability: "ready",
    cell_id: "cell-1",
    cost_basis: {
      currency: "USD",
      total_amount: 1250,
    },
    execution_capability: "ready",
    external_nonclosures: [
      "fresh_positive_production_route:absent/unallocated",
    ],
    planner_record_id: "acquisition-plan-1",
    planner_report_hash: "sha256:planner",
    qualification_predicate: "not_established",
    qualification_reason: "policy_admission_missing",
    qualification_status: "pending_epoch_activation",
    recommended_strategy: "targeted_primary_data_collection",
    replay_pins: {
      compiled_content_hash: "sha256:compiled-content",
      compiled_ref: "sha256:compiled",
      cost_basis_hash: "sha256:cost",
      design_problem_ref: "sha256:design-problem",
      source_job_id: "source-job-1",
      terminal_event_id: "terminal-event-1",
    },
    route_id: "sha256:route",
    route_projection_hash: "sha256:route",
    route_status: "costed_actionable",
    run_id: "run-1",
    schema_version: "AcquisitionRouteProjection@1.0",
    tenant_id: "tenant-1",
    world_growth: "no_growth",
  };
}

describe("AcquisitionRouteDetail", () => {
  it("keeps a structural owner refusal non-actionable despite forged data hints", () => {
    const route = {
      action_eligibility: "not_applicable",
      available_catalog_rows: 99,
      cost: 1,
      gap_class: "structural_gap",
      missing_link: "grounding_relation_missing",
      route_class: "not_a_data_gap",
      route_id: "capstone:first_vertical",
      witness_kind: "estimand_binding_refusal",
    } as unknown as StructuralRouteProjection;
    render(
      <LocaleProvider>
        <AcquisitionRouteDetail kind="structural" route={route} />
      </LocaleProvider>,
    );

    const detail = screen.getByTestId(
      "acquisition-structural-route-capstone:first_vertical",
    );
    expect(detail).toHaveTextContent("structural_gap");
    expect(detail).toHaveTextContent("not_a_data_gap");
    expect(detail).toHaveTextContent("not_applicable");
    expect(within(detail).queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows typed requirement, costed plan, strategy, VOI absence and status", () => {
    render(
      <LocaleProvider>
        <AcquisitionRouteDetail
          action={<Button>Review acquisition</Button>}
          kind="run"
          route={runRoute()}
        />
      </LocaleProvider>,
    );

    const detail = screen.getByTestId("acquisition-route-detail");
    expect(detail).toHaveTextContent("sha256:design-problem");
    expect(detail).toHaveTextContent("1250");
    expect(detail).toHaveTextContent("targeted_primary_data_collection");
    expect(detail).toHaveTextContent("not_established");
    expect(detail).toHaveTextContent("costed_actionable");
    expect(
      within(detail).getByRole("button", { name: "Review acquisition" }),
    ).toBeInTheDocument();
  });

  it("hides the action when either production capability is missing", () => {
    render(
      <LocaleProvider>
        <AcquisitionRouteDetail
          action={<Button>Review acquisition</Button>}
          kind="run"
          route={{ ...runRoute(), execution_capability: "producer_missing" }}
        />
      </LocaleProvider>,
    );

    expect(
      screen.queryByRole("button", { name: "Review acquisition" }),
    ).not.toBeInTheDocument();
  });
});
