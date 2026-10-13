import { render, screen, within } from "@testing-library/react";
import type { StructuralRouteProjection } from "@polisyos/runtime-api-client";

import type {
  AdmittedDeltaAcquisitionRouteV11,
  NoGrowthAcquisitionRouteV11,
  PendingAcquisitionRouteV11,
} from "@/features/runs/api/acquisitionRouteValidators";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import { Button } from "@polisyos/atlas-ui";

import { AcquisitionRouteDetail } from "./AcquisitionRouteDetail";

function runRoute(): PendingAcquisitionRouteV11 {
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
    schema_version: "AcquisitionRouteProjection@1.1",
    tenant_id: "tenant-1",
    world_growth: "not_established",
    admitted_observation_delta: null,
  };
}

function noGrowthRoute(): NoGrowthAcquisitionRouteV11 {
  return {
    ...runRoute(),
    admitted_observation_delta: 0,
    authority_badge: "native_owner_verified",
    qualification_predicate: "independently_reconciled",
    qualification_reason: "native_owner_readback",
    qualification_status: "activated",
    world_growth: "no_growth",
  };
}

function admittedDeltaRoute(): AdmittedDeltaAcquisitionRouteV11 {
  return {
    ...runRoute(),
    admitted_observation_delta: 1,
    authority_badge: "native_owner_verified",
    qualification_predicate: "independently_reconciled",
    qualification_reason: "native_owner_readback",
    qualification_status: "activated",
    world_growth: "admitted_delta",
  };
}

describe("AcquisitionRouteDetail", () => {
  it("keeps a structural owner refusal non-actionable despite forged data hints", () => {
    const ownerProjection = {
      action_eligibility: "not_applicable",
      gap_class: "structural_gap",
      missing_link: "grounding_relation_missing",
      route_class: "not_a_data_gap",
      route_id: "capstone:first_vertical",
      witness_kind: "estimand_binding_refusal",
    } satisfies StructuralRouteProjection;
    const route = {
      ...ownerProjection,
      available_catalog_rows: 99,
      cost: 1,
    };
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

  it("shows a candidate non-data split refusal without enabling acquisition", () => {
    const ownerProjection = {
      action_eligibility: "blocked",
      gap_class: "not_established",
      missing_link: "split_required",
      route_class: "candidate_non_data:legal_mandate,normative_authorization",
      route_id: "candidate:compound-authorization",
      witness_kind: "split_required",
    } satisfies StructuralRouteProjection;
    const route = {
      ...ownerProjection,
      available_catalog_rows: 1_000_000,
      cost: 1,
    };
    render(
      <LocaleProvider>
        <AcquisitionRouteDetail kind="structural" route={route} />
      </LocaleProvider>,
    );

    const detail = screen.getByTestId(
      "acquisition-structural-route-candidate:compound-authorization",
    );
    expect(detail).toHaveTextContent(
      "candidate_non_data:legal_mandate,normative_authorization",
    );
    expect(detail).toHaveTextContent("not_established");
    expect(detail).toHaveTextContent("blocked");
    expect(within(detail).getAllByText("split_required")).toHaveLength(2);
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
    expect(detail).toHaveTextContent("Update not established");
    expect(detail).toHaveTextContent("costed_actionable");
    expect(
      within(detail).getByRole("button", { name: "Review acquisition" }),
    ).toBeInTheDocument();
  });

  it.each([
    {
      expectedLabel: "Update not established",
      route: runRoute(),
      rawOutcome: "not_established",
    },
    {
      expectedLabel: "No membership added to the selected active epoch",
      route: noGrowthRoute(),
      rawOutcome: "no_growth",
    },
    {
      expectedLabel: "Membership added to the selected active epoch",
      route: admittedDeltaRoute(),
      rawOutcome: "admitted_delta",
    },
  ])(
    "shows operator meaning for the selected world-growth outcome: $rawOutcome",
    ({ expectedLabel, rawOutcome, route }) => {
      render(
        <LocaleProvider>
          <AcquisitionRouteDetail kind="run" route={route} />
        </LocaleProvider>,
      );

      const status = screen.getByTestId("acquisition-route-world-growth");
      expect(status).toHaveTextContent(expectedLabel);
      expect(status).not.toHaveTextContent(rawOutcome);
    },
  );

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
