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
import { narrowDepthNCycleBoardHeroProjection } from "./useDepthNCycleBoardProjection";

function pendingRoute() {
  return {
    admitted_observation_delta: 0,
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
    schema_version: "AcquisitionRouteProjection@1.0",
    tenant_id: "tenant-1",
    world_growth: "no_growth",
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

function captured(packet: unknown) {
  return {
    packet,
    rawPacketBytes: new TextEncoder().encode(JSON.stringify(packet)),
  };
}

describe("current acquisition projection compatibility", () => {
  it.each([pendingRoute(), activeRoute()])(
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
      expect(visible.route.external_nonclosures).toEqual(
        route.external_nonclosures,
      );
      expect(visible.actionEligible).toBe(false);
      expect(visible).not.toHaveProperty("publishable");
    },
  );

  it("preserves the older negative representation without inventing its missing delta", () => {
    const { admitted_observation_delta: _delta, ...legacy } = pendingRoute();
    const result = narrowAcquisitionRouteDetail(
      "run-a",
      "sha256:route",
      captured(legacy),
    );
    expect(result.packet).toEqual(legacy);
    expect(result.packet).not.toHaveProperty("admitted_observation_delta");
  });

  it.each([
    { ...activeRoute(), admitted_observation_delta: 0 },
    { ...activeRoute(), admitted_observation_delta: undefined },
    { ...activeRoute(), qualification_predicate: "not_established" },
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
