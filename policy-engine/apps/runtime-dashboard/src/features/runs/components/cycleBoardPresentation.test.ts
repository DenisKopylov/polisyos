import { cycleBoardProjectionPacketFixture } from "@/test/fixtures/depthNCycleBoard";

import { packetToVisibleCycleBoard } from "./cycleBoardPresentation";

function structuralRegion(
  visible: ReturnType<typeof packetToVisibleCycleBoard>,
) {
  return visible.rows.map((row) => ({
    acquisitionEconomics: row.acquisitionEconomics,
    acquisitionRoute: row.acquisitionRoute,
    evidenceClass: row.structuralEvidenceClass,
    lifecycleTerminality: row.lifecycleTerminality,
    missingLink: row.missingLink,
    movementRecords: row.movementRecords,
    rowId: row.rowId,
    searchTerminalKind: row.searchTerminalKind,
    weakestLinks: row.weakestLinks,
  }));
}

describe("Cycle Board presentation projection", () => {
  it("projects the complete owner order and typed gaps without defaults", () => {
    const packet = cycleBoardProjectionPacketFixture();
    const visible = packetToVisibleCycleBoard(packet);

    expect(visible.rows.map((row) => row.rowId)).toEqual(
      packet.payload.rows.map((row) => row.row_id),
    );
    expect(visible.coverage).toEqual(packet.payload.coverage);
    expect(visible.movementGap).toEqual(packet.payload.movement_gap);
    expect(visible.sources).toEqual(packet.composition_manifest);
    expect(visible.realizedDs4Disposition).toEqual(
      packet.payload.realized_ds4_disposition,
    );
    expect(visible.historicalProducerAvailability).toEqual(
      packet.payload.historical_producer_availability,
    );
    expect(visible).not.toHaveProperty("asOf");
    expect(visible).not.toHaveProperty("freshness");
    expect(visible).not.toHaveProperty("currentness");

    const first = visible.rows[0];
    expect(first?.lifecycleTerminality).toEqual(
      packet.payload.rows[0]?.lifecycle_terminality,
    );
    expect(first?.lifecycleTerminality).not.toHaveProperty("value");
    expect(first?.searchTerminalKind).toEqual(
      packet.payload.rows[0]?.search_terminal_kind,
    );
    expect(first?.structuralEvidenceClass).toEqual(
      packet.payload.rows[0]?.structural_evidence_class,
    );
    expect(first?.weakestLinks).toEqual(packet.payload.rows[0]?.weakest_links);
    expect(first?.acquisitionRoute).toEqual(
      packet.payload.rows[0]?.acquisition_route,
    );
    expect(first?.acquisitionEconomics).toEqual(
      packet.payload.rows[0]?.acquisition_economics,
    );
  });

  it("does not let adjacent historical counts mint structural progress", () => {
    const packet = cycleBoardProjectionPacketFixture();
    const changed = structuredClone(packet);
    changed.payload.historical_producer_availability.counts = {
      adjacent_observations: 3_700_000,
    };
    changed.payload.realized_ds4_disposition.counts = {
      nearby_rows: 99_999,
    };

    expect(structuralRegion(packetToVisibleCycleBoard(changed))).toEqual(
      structuralRegion(packetToVisibleCycleBoard(packet)),
    );
    expect(packetToVisibleCycleBoard(changed).coverage.exhaustive).toBe(false);
    expect(
      packetToVisibleCycleBoard(changed).movementGap.movement_records,
    ).toEqual([]);
  });

  it("keeps producer lifecycle truth independent from every search proxy", () => {
    const packet = cycleBoardProjectionPacketFixture();
    const changed = structuredClone(packet);
    const first = changed.payload.rows[0];
    if (!first) {
      throw new Error("fixture must carry its first capstone row");
    }
    first.search_terminal_kind = {
      availability: "available",
      source_ref: "artifact://mutated-search",
      value: "terminal_for_this_round",
    };
    first.weakest_links = {
      availability: "available",
      source_ref: "artifact://mutated-search",
      value: ["finished_at_present", "status_completed"],
    };

    const baseline = packetToVisibleCycleBoard(packet).rows[0];
    const mutated = packetToVisibleCycleBoard(changed).rows[0];
    expect(mutated?.lifecycleTerminality).toEqual(
      baseline?.lifecycleTerminality,
    );
    expect(mutated?.lifecycleTerminality).not.toHaveProperty("value");
    expect(mutated?.searchTerminalKind).not.toEqual(
      baseline?.searchTerminalKind,
    );
  });
});
