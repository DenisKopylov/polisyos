import { render, screen, within } from "@testing-library/react";
import type { StructuralRouteProjection } from "@polisyos/runtime-api-client";

import type {
  AdmittedDeltaAcquisitionRouteV11,
  NoGrowthAcquisitionRouteV11,
  PaidInputAdmissionAcquisitionRouteV12,
  PendingAcquisitionRouteV11,
} from "@/features/runs/api/acquisitionRouteValidators";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import { Button } from "@polisyos/atlas-ui";

import { AcquisitionRouteDetail } from "./AcquisitionRouteDetail";

const digest = (suffix: string) => `sha256:${suffix.repeat(64).slice(0, 64)}`;

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
  return {
    ...runRoute(),
    cost_basis: {
      currency: "USD",
      owner_declared_profile_ref: selection.owner_declared_profile_ref,
      record_content_hash: costBasisHash,
      record_ref: "sha256:historical-cost-basis",
      schema_version: "AcquisitionCostBasisRecord@1.1",
      total_amount: 1250,
    },
    prior_paid_input_admission: selection,
    replay_pins: {
      ...runRoute().replay_pins,
      cost_basis_hash: costBasisHash,
    },
    route_projection_hash: digest("q"),
    route_status: "paid_input_admission_only",
    schema_version: "AcquisitionRouteProjection@1.2",
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

  it("shows the exact prior paid input as admission-only with historical cost context", () => {
    render(
      <LocaleProvider>
        <AcquisitionRouteDetail
          action={<Button>Request current admission review</Button>}
          kind="run"
          route={paidInputAdmissionRoute()}
        />
      </LocaleProvider>,
    );

    const detail = screen.getByTestId("acquisition-route-detail");
    const admission = screen.getByTestId("prior-paid-input-admission");
    expect(admission).toHaveTextContent("prior-paid-action-1");
    expect(admission).toHaveTextContent("sha256:" + "a".repeat(64));
    expect(admission).toHaveTextContent("sha256:" + "c".repeat(64));
    expect(admission).toHaveTextContent("admission only");
    expect(admission).toHaveTextContent(
      "does not itself grant current action authority",
    );
    expect(admission).toHaveTextContent("claim an N5 result");
    expect(admission).toHaveTextContent("or permit publication");
    expect(detail).toHaveTextContent("Historical cost basis");
    expect(detail).toHaveTextContent(
      "Historical estimate · not a current offer",
    );
    expect(detail).toHaveTextContent("USD 1250");
    expect(detail).not.toHaveTextContent("USD 0");
    expect(
      within(detail).getByRole("button", {
        name: "Request current admission review",
      }),
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
