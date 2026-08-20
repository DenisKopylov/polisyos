import type { CycleBoardProjectionPacket } from "@polisyos/runtime-api-client";

/**
 * Project the server-owned Cycle Board packet into presentation names only.
 *
 * This function deliberately performs no sorting, defaulting, terminality
 * inference, evidence classification, or freshness aggregation.
 */
export function packetToVisibleCycleBoard(packet: CycleBoardProjectionPacket) {
  return {
    coverage: packet.payload.coverage,
    historicalProducerAvailability:
      packet.payload.historical_producer_availability,
    movementGap: packet.payload.movement_gap,
    packet: {
      compositionManifestHash: packet.composition_manifest_hash,
      intendedAudiences: packet.intended_audiences,
      packetSchemaVersion: packet.packet_schema_version,
      projectionHash: packet.projection_hash,
      projectionId: packet.projection_id,
      projectionObservedAt: packet.projection_observed_at,
      projectionRuleVersion: packet.projection_rule_version,
      replayAddress: packet.replay_address,
      sourceDependencyHash: packet.source_dependency_hash,
      stableAddress: packet.stable_address,
    },
    realizedDs4Disposition: packet.payload.realized_ds4_disposition,
    rows: packet.payload.rows.map((row) => ({
      acquisitionEconomics: row.acquisition_economics,
      acquisitionRoute: row.acquisition_route,
      cohort: row.cohort,
      designProblem: row.design_problem,
      domainRole: row.domain_role,
      explanationCode: row.explanation_code,
      explanationInputs: row.explanation_inputs,
      generationCycleRunId: row.generation_cycle_run_id,
      lifecycleTerminality: row.lifecycle_terminality,
      missingLink: row.missing_link,
      movementRecords: row.movement_records,
      responsibleSlices: row.responsible_slices,
      rowId: row.row_id,
      searchTerminalKind: row.search_terminal_kind,
      stageTraceHref: row.stage_trace_href,
      structuralEvidenceClass: row.structural_evidence_class,
      surfaceReadiness: row.surface_readiness,
      weakestLinks: row.weakest_links,
    })),
    sources: packet.composition_manifest,
  } as const;
}

export type VisibleCycleBoard = ReturnType<typeof packetToVisibleCycleBoard>;
