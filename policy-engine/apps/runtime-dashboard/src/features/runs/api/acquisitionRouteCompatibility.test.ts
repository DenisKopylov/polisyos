import type {
  HistoricalProducerAvailabilityReadReceipt,
  MovementRecord,
} from "@polisyos/runtime-api-client";

import { packetToVisibleCycleBoard } from "@/features/runs/components/cycleBoardPresentation";
import { presentRunAcquisitionRoute } from "@/features/runs/domain/acquisitionRoutePresentation";
import { cycleBoardProjectionPacketFixture } from "@/test/fixtures/depthNCycleBoard";

import {
  narrowAcquisitionRouteCollection,
  narrowAcquisitionRouteDetail,
} from "./useAcquisitionRoutes";
import {
  type PaidInputAdmissionAcquisitionRouteV12,
  type PendingAcquisitionRouteV11,
  acquisitionDecisionRequestResponseSchema,
  acquisitionExecutionResponseSchema,
} from "./acquisitionRouteValidators";
import { narrowDepthNCycleBoardHeroProjection } from "./useDepthNCycleBoardProjection";

function pendingRoute(): PendingAcquisitionRouteV11 {
  return {
    authority_badge: "behavioral_fixture_not_production",
    authority_capability: "producer_missing",
    cell_id: "cell-1",
    cost_basis: { total_amount: 100 },
    execution_capability: "producer_missing",
    external_nonclosures: ["current_mandate_owner:producer_missing"],
    planner_record_id: "planner-1",
    planner_report_hash: "sha256:planner",
    qualification_predicate: "not_established",
    qualification_reason: "policy_admission_missing",
    qualification_status: "pending_epoch_activation",
    recommended_strategy: "targeted_primary_data_collection",
    replay_pins: {
      compiled_content_hash: "sha256:compiled-content",
      compiled_ref: "sha256:compiled",
      cost_basis_hash: "sha256:cost",
      design_problem_ref: "sha256:problem",
      source_job_id: "job-1",
      terminal_event_id: "event-1",
    },
    route_id: "sha256:route",
    route_projection_hash: "sha256:route",
    route_status: "costed_actionable",
    run_id: "run-a",
    schema_version: "AcquisitionRouteProjection@1.1",
    tenant_id: "tenant-1",
    world_growth: "not_established",
    admitted_observation_delta: null,
  };
}

function activeRoute() {
  return {
    ...pendingRoute(),
    admitted_observation_delta: 1,
    authority_badge: "native_owner_verified",
    qualification_predicate: "independently_reconciled",
    qualification_reason: "native_owner_readback",
    qualification_status: "activated",
    world_growth: "admitted_delta",
  };
}

function noGrowthRoute() {
  return {
    ...pendingRoute(),
    admitted_observation_delta: 0,
    authority_badge: "native_owner_verified",
    qualification_predicate: "independently_reconciled",
    qualification_reason: "native_owner_readback",
    qualification_status: "activated",
    world_growth: "no_growth",
  };
}

function paidInputAdmissionSelection() {
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
  return {
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
}

function paidInputAdmissionRoute(): PaidInputAdmissionAcquisitionRouteV12 {
  const selection = paidInputAdmissionSelection();
  const prior = pendingRoute();
  const costBasisHash = "sha256:" + "c".repeat(64);
  return {
    ...prior,
    admitted_observation_delta: null,
    cost_basis: {
      currency: "USD",
      owner_declared_profile_ref: selection.owner_declared_profile_ref,
      record_content_hash: costBasisHash,
      record_ref: "sha256:historical-cost-basis",
      schema_version: "AcquisitionCostBasisRecord@1.1",
      total_amount: 1250,
    },
    prior_paid_input_admission: selection,
    replay_pins: { ...prior.replay_pins, cost_basis_hash: costBasisHash },
    route_projection_hash: "sha256:" + "q".repeat(64),
    route_status: "paid_input_admission_only",
    schema_version: "AcquisitionRouteProjection@1.2",
  };
}

function captured(packet: unknown) {
  return {
    packet,
    rawPacketBytes: new TextEncoder().encode(JSON.stringify(packet)),
  };
}

describe("current acquisition projection compatibility", () => {
  it.each([pendingRoute(), activeRoute(), noGrowthRoute()])(
    "preserves the whole actual route posture through list and detail: $qualification_status",
    (route) => {
      const detail = captured(route);
      const selected = narrowAcquisitionRouteDetail(
        "run-a",
        "sha256:route",
        detail,
      );
      expect(selected.packet).toEqual(route);
      expect(Array.from(selected.rawPacketBytes)).toEqual(
        Array.from(detail.rawPacketBytes),
      );
      const collection = captured({ routes: [route], run_id: "run-a" });
      const listed = narrowAcquisitionRouteCollection("run-a", collection);
      expect(listed.packet).toEqual(collection.packet);
      expect(Array.from(listed.rawPacketBytes)).toEqual(
        Array.from(collection.rawPacketBytes),
      );

      const visible = presentRunAcquisitionRoute(selected.packet);
      expect(visible.qualification.status).toBe(route.qualification_predicate);
      expect(visible.worldGrowth).toBe(
        route.qualification_status === "pending_epoch_activation"
          ? "not_established"
          : route.world_growth,
      );
      expect(visible.route.external_nonclosures).toEqual(
        route.external_nonclosures,
      );
      expect(visible.actionEligible).toBe(false);
      expect(visible).not.toHaveProperty("publishable");
    },
  );

  it("preserves a v1.0 pending packet without inventing its missing delta", () => {
    const { admitted_observation_delta: _delta, ...current } = pendingRoute();
    const legacy = {
      ...current,
      schema_version: "AcquisitionRouteProjection@1.0",
      world_growth: "no_growth",
    };
    const result = narrowAcquisitionRouteDetail(
      "run-a",
      "sha256:route",
      captured(legacy),
    );
    expect(result.packet).toEqual(legacy);
    expect(result.packet).not.toHaveProperty("admitted_observation_delta");
    expect(presentRunAcquisitionRoute(result.packet).worldGrowth).toBe(
      "not_established",
    );
  });

  it("downgrades the former pending no-growth default to unknown", () => {
    const legacy = {
      ...pendingRoute(),
      admitted_observation_delta: 0,
      schema_version: "AcquisitionRouteProjection@1.0",
      world_growth: "no_growth",
    };
    const result = narrowAcquisitionRouteDetail(
      "run-a",
      "sha256:route",
      captured(legacy),
    );
    expect(presentRunAcquisitionRoute(result.packet).worldGrowth).toBe(
      "not_established",
    );
  });

  it.each([
    {
      name: "omitted status and prior selection",
      route: (() => {
        const { route_status: _status, ...legacy } = pendingRoute();
        return legacy;
      })(),
    },
    {
      name: "null status and prior selection",
      route: {
        ...pendingRoute(),
        prior_paid_input_admission: null,
        route_status: null,
      },
    },
  ])("preserves the v1.1 $name wire form", ({ route }) => {
    const result = narrowAcquisitionRouteDetail(
      "run-a",
      "sha256:route",
      captured(route),
    );
    expect(result.packet.schema_version).toBe("AcquisitionRouteProjection@1.1");
    expect(presentRunAcquisitionRoute(result.packet).acquisitionMode).toBe(
      "costed_actionable",
    );
  });

  it.each(["omitted", "null"] as const)(
    "keeps the v1.1 %s route status ineligible even with otherwise-ready action inputs",
    (status) => {
      const costHash = "sha256:" + "d".repeat(64);
      const route = {
        ...pendingRoute(),
        authority_capability: "ready",
        cost_basis: {
          record_content_hash: costHash,
          schema_version: "AcquisitionCostBasisRecord@1.0",
          total_amount: 100,
        },
        execution_capability: "ready",
        replay_pins: {
          ...pendingRoute().replay_pins,
          cost_basis_hash: costHash,
        },
      } as unknown as Record<string, unknown>;
      if (status === "omitted") {
        delete route.route_status;
      } else {
        route.route_status = null;
      }

      const result = narrowAcquisitionRouteDetail(
        "run-a",
        "sha256:route",
        captured(route),
      );
      const visible = presentRunAcquisitionRoute(result.packet);

      expect(visible.costEstablished).toBe(true);
      expect(visible.actionEligible).toBe(false);
    },
  );

  it("preserves an exact v1.2 paid-input selection without promoting it to authority", () => {
    const route = paidInputAdmissionRoute();
    const detail = narrowAcquisitionRouteDetail(
      "run-a",
      route.route_id,
      captured(route),
    );
    const listed = narrowAcquisitionRouteCollection(
      "run-a",
      captured({ routes: [route], run_id: "run-a" }),
    );
    const visible = presentRunAcquisitionRoute(detail.packet);

    if (detail.packet.schema_version !== "AcquisitionRouteProjection@1.2") {
      throw new TypeError("expected v1.2 admission route");
    }
    const listedRoute = listed.packet.routes[0];
    if (listedRoute?.schema_version !== "AcquisitionRouteProjection@1.2") {
      throw new TypeError("expected listed v1.2 admission route");
    }
    expect(detail.packet.prior_paid_input_admission).toEqual(
      route.prior_paid_input_admission,
    );
    expect(listedRoute.prior_paid_input_admission).toEqual(
      route.prior_paid_input_admission,
    );
    expect(visible.acquisitionMode).toBe("paid_input_admission_only");
    expect(visible.actionEligible).toBe(false);
    expect(visible.route.authority_capability).toBe("producer_missing");
    expect(visible.route.execution_capability).toBe("producer_missing");
    expect(visible.costMeaning).toBe("historical_prior_paid_basis");
    expect(visible).not.toHaveProperty("publishable");
  });

  it.each([
    [
      "missing selection",
      (route: Record<string, unknown>) => {
        delete route.prior_paid_input_admission;
      },
    ],
    [
      "null selection",
      (route: Record<string, unknown>) => {
        route.prior_paid_input_admission = null;
      },
    ],
    [
      "missing mode",
      (route: Record<string, unknown>) => {
        delete route.route_status;
      },
    ],
    [
      "null mode",
      (route: Record<string, unknown>) => {
        route.route_status = null;
      },
    ],
    [
      "legacy mode",
      (route: Record<string, unknown>) => {
        route.route_status = "costed_actionable";
      },
    ],
    [
      "grafted attempt profile",
      (route: Record<string, unknown>) => {
        const selection = route.prior_paid_input_admission as Record<
          string,
          unknown
        >;
        selection.attempt_ref = {
          ...(selection.attempt_ref as Record<string, unknown>),
          kind: "runtime_quality.acquisition_route_loop_receipt",
        };
      },
    ],
    [
      "grafted owner profile",
      (route: Record<string, unknown>) => {
        const cost = route.cost_basis as Record<string, unknown>;
        cost.owner_declared_profile_ref = {
          ...paidInputAdmissionSelection().owner_declared_profile_ref,
          artifact_id: "sha256:" + "8".repeat(64),
        };
      },
    ],
    [
      "unrecognized selection field",
      (route: Record<string, unknown>) => {
        const selection = route.prior_paid_input_admission as Record<
          string,
          unknown
        >;
        selection.client_authority = true;
      },
    ],
  ])("rejects @1.2 %s", (_name, mutate) => {
    const route = structuredClone(
      paidInputAdmissionRoute(),
    ) as unknown as Record<string, unknown>;
    mutate(route);
    expect(() =>
      narrowAcquisitionRouteDetail("run-a", "sha256:route", captured(route)),
    ).toThrow();
  });

  it("parses current and legacy decision-request responses without treating an old default as zero", () => {
    const current = {
      authority_decision_ref: "sha256:decision",
      outcome: "decision_required",
      route_id: "sha256:route",
      run_id: "run-a",
      world_growth: "not_established",
    };
    expect(acquisitionDecisionRequestResponseSchema.parse(current)).toEqual(
      current,
    );
    expect(
      acquisitionDecisionRequestResponseSchema.parse({
        ...current,
        world_growth: "no_growth",
      }).world_growth,
    ).toBe("not_established");
    expect(() =>
      acquisitionDecisionRequestResponseSchema.parse({
        ...current,
        world_growth: "admitted_delta",
      }),
    ).toThrow();
  });

  it("parses current and legacy accepted-job responses but rejects a measured outcome", () => {
    const current = {
      authority_decision_ref: "sha256:decision",
      job_id: "job-1",
      receipt_phase: "requested",
      route_id: "sha256:route",
      run_id: "run-a",
      status: "accepted",
      world_growth: "not_established",
    };
    expect(acquisitionExecutionResponseSchema.parse(current)).toEqual(current);
    expect(
      acquisitionExecutionResponseSchema.parse({
        ...current,
        world_growth: "no_growth",
      }).world_growth,
    ).toBe("not_established");
    expect(() =>
      acquisitionExecutionResponseSchema.parse({
        ...current,
        world_growth: "admitted_delta",
      }),
    ).toThrow();
  });

  it.each([
    {
      name: "authorization refresh pending",
      status: "accepted",
      receipt_phase: "authorization_refreshed",
      kind: "runtime_quality.acquisition_candidate_experiment_phase_receipt",
    },
    {
      name: "in-flight execution",
      status: "accepted",
      receipt_phase: "executing",
      kind: "runtime_quality.acquisition_candidate_experiment_phase_receipt",
    },
    {
      name: "historical completed execution",
      status: "completed",
      receipt_phase: "terminal",
      kind: "runtime_quality.acquisition_route_loop_receipt",
    },
  ])(
    "preserves a profiled $name response",
    ({ status, receipt_phase, kind }) => {
      const response = {
        authority_decision_ref: "sha256:decision-b",
        job_id: "job-1",
        receipt_phase,
        route_id: "sha256:route",
        run_id: "run-a",
        selected_receipt_ref: {
          artifact_id: "sha256:" + "a".repeat(64),
          kind,
          media_type: "application/json",
          manifest_profile_sha256: "sha256:" + "b".repeat(64),
        },
        status,
        world_growth: "not_established",
      };
      expect(acquisitionExecutionResponseSchema.parse(response)).toEqual(
        response,
      );
    },
  );

  it.each([
    {
      status: "completed",
      receipt_phase: "authorization_refreshed",
    },
    { status: "accepted", receipt_phase: "terminal" },
  ])("rejects inconsistent execution status and phase %#", (overrides) => {
    expect(() =>
      acquisitionExecutionResponseSchema.parse({
        authority_decision_ref: "sha256:decision-b",
        job_id: "job-1",
        route_id: "sha256:route",
        run_id: "run-a",
        world_growth: "not_established",
        ...overrides,
      }),
    ).toThrow();
  });

  it.each([
    {
      kind: "runtime_quality.acquisition_candidate_experiment_phase_receipt",
      manifest_profile_sha256: undefined,
    },
    {
      kind: "runtime_quality.acquisition_route_loop_receipt",
      manifest_profile_sha256: "sha256:" + "b".repeat(64),
    },
  ])(
    "rejects an unprofiled or phase-incompatible selected receipt %#",
    (ref) => {
      expect(() =>
        acquisitionExecutionResponseSchema.parse({
          authority_decision_ref: "sha256:decision-b",
          job_id: "job-1",
          receipt_phase: "authorization_refreshed",
          route_id: "sha256:route",
          run_id: "run-a",
          selected_receipt_ref: {
            artifact_id: "sha256:" + "a".repeat(64),
            kind: ref.kind,
            media_type: "application/json",
            ...(ref.manifest_profile_sha256 === undefined
              ? {}
              : { manifest_profile_sha256: ref.manifest_profile_sha256 }),
          },
          status: "accepted",
          world_growth: "not_established",
        }),
      ).toThrow();
    },
  );

  it.each([
    "authorization_refreshed",
    "executing",
    "outcome_selected",
    "candidate_input_reentry_pending",
  ])("requires a selected receipt for %s", (receipt_phase) => {
    expect(() =>
      acquisitionExecutionResponseSchema.parse({
        authority_decision_ref: "sha256:decision-b",
        job_id: "job-1",
        receipt_phase,
        route_id: "sha256:route",
        run_id: "run-a",
        selected_receipt_ref: null,
        status: "accepted",
        world_growth: "not_established",
      }),
    ).toThrow();
  });

  it.each([
    {
      status: "accepted",
      receipt_phase: "requested",
    },
    {
      status: "completed",
      receipt_phase: "terminal",
    },
  ])(
    "treats null selected receipt as absent for legacy %s responses",
    (state) => {
      const parsed = acquisitionExecutionResponseSchema.parse({
        authority_decision_ref: "sha256:decision-a",
        job_id: "job-1",
        receipt_phase: state.receipt_phase,
        route_id: "sha256:route",
        run_id: "run-a",
        selected_receipt_ref: null,
        status: state.status,
        world_growth: "not_established",
      });
      expect(parsed.selected_receipt_ref).toBeNull();
    },
  );

  it.each([
    { ...activeRoute(), admitted_observation_delta: 0 },
    { ...activeRoute(), admitted_observation_delta: undefined },
    { ...activeRoute(), qualification_predicate: "not_established" },
    { ...noGrowthRoute(), admitted_observation_delta: null },
    { ...noGrowthRoute(), admitted_observation_delta: 1 },
    { ...activeRoute(), world_growth: "not_established" },
    { ...pendingRoute(), admitted_observation_delta: 0 },
    { ...pendingRoute(), admitted_observation_delta: 1 },
    { ...activeRoute(), authority_badge: "publishable" },
    { ...activeRoute(), publishable: true },
  ])("refuses an inconsistent or invented authority posture %#", (route) => {
    expect(() =>
      narrowAcquisitionRouteDetail("run-a", "sha256:route", captured(route)),
    ).toThrow();
  });

  it("preserves added Board read receipts and native movement records without grading them", () => {
    const original = cycleBoardProjectionPacketFixture();
    const readReceipt: HistoricalProducerAvailabilityReadReceipt = {
      coverage: "complete_selected_input",
      read_error: null,
      read_status: "read",
      selected_measurement_cell_count: 1,
      selector: "all_markdown_table_cells_with_ds3_measurement",
      source_content_hash:
        original.payload.historical_producer_availability.source_content_hash,
      source_ref: original.payload.historical_producer_availability.source_ref,
      status: "COMPLETE",
      table_row_denominator: 31,
      unresolved_by_construction: ["current_availability_not_measured"],
    };
    // This fixture checks lossless display, not native evidence admission.
    // It is deliberately partial, so it cannot be typed as a complete record.
    const movement = {
      movement: { new_cycle_index: 2, terminal_kind: "blocked" },
    } as unknown as MovementRecord;
    const packet = {
      ...original,
      payload: {
        ...original.payload,
        historical_producer_availability: {
          ...original.payload.historical_producer_availability,
          read_receipt: readReceipt,
        },
        rows: original.payload.rows.map((row, index) => ({
          ...row,
          movement_records: index === 0 ? [movement] : row.movement_records,
        })),
      },
    };
    const raw = captured(packet).rawPacketBytes;
    const narrowed = narrowDepthNCycleBoardHeroProjection(packet, raw);
    const visible = packetToVisibleCycleBoard(narrowed.packet);
    expect(narrowed.packet).toBe(packet);
    expect(narrowed.rawPacketBytes).toBe(raw);
    expect(visible.historicalProducerAvailability).toBe(
      packet.payload.historical_producer_availability,
    );
    expect(visible.rows[0]?.movementRecords).toEqual([movement]);
    expect(visible.rows[0]?.lifecycleTerminality).toBe(
      original.payload.rows[0]?.lifecycle_terminality,
    );
    expect(visible.rows[0]?.structuralEvidenceClass).toBe(
      original.payload.rows[0]?.structural_evidence_class,
    );
  });
});
