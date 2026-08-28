import type { AcquisitionBacklogProjection } from "@polisyos/runtime-api-client";

import {
  presentAcquisitionBacklog,
  presentConnectorAcquisitionScorecard,
} from "./acquisitionRoutePresentation";

function backlogRows(): AcquisitionBacklogProjection[] {
  return Array.from({ length: 15 }, (_, index) => ({
    authority_boundary: "ranking_only_not_voi",
    binding_confidence: 0,
    classification_basis:
      index === 7 ? "independently_reconciled" : "not_established",
    gap_class: index === 7 ? "data_gap" : "not_established",
    rank: index + 1,
    ranking_method: "interim_binding_confidence_x_route_demand",
    ranking_score: 0,
    route_demand: index < 3 ? 2 : 1,
    variable_id: index === 7 ? "government.balance" : `variable.${index + 1}`,
    voi_owner_fit: "metric_residual_granularity_not_supported",
    voi_owner_integration: "routed_to_gy_n13b",
    voi_owner_ref:
      "polisyos.runtime.quality.acquisition_planner.plan_evidence_acquisition",
  }));
}

describe("acquisition route presentation", () => {
  it("derives the complete zero-score basis instead of trusting source ordinals", () => {
    const rows = backlogRows();
    const visible = presentAcquisitionBacklog(rows);

    expect(visible.totalCount).toBe(15);
    expect(visible.zeroConfidenceCount).toBe(15);
    expect(visible.zeroScoreCount).toBe(15);
    expect(visible.demandTwoCount).toBe(3);
    expect(visible.demandOneCount).toBe(12);
    expect(visible.hasNonzeroPriorityGradient).toBe(false);
    expect(visible.voiEstablished).toBe(false);

    const changedRows = rows.map((row) => ({ ...row }));
    const changed = changedRows[7];
    if (!changed) {
      throw new Error("fixture must contain the reconciled row");
    }
    changed.ranking_score = 0.25;
    const recomputed = presentAcquisitionBacklog(changedRows);
    expect(recomputed.zeroScoreCount).toBe(14);
    expect(recomputed.hasNonzeroPriorityGradient).toBe(true);
  });

  it("marks a declared transport tier as degraded when measured decay exists", () => {
    const healthyLooking = {
      carrier_disposition: "carrier_current_source_profile_mismatch",
      connector_id: "worldbank.wdi",
      execution_tier: "transport_ready",
      tier_decay_findings: [
        "execution_tier_decay:transport_ready:carrier_current_source_profile_mismatch",
      ],
    };

    expect(presentConnectorAcquisitionScorecard(healthyLooking).health).toBe(
      "degraded",
    );
    expect(
      presentConnectorAcquisitionScorecard({
        ...healthyLooking,
        carrier_disposition: "carrier_current",
        tier_decay_findings: [],
      }).health,
    ).toBe("observed_healthy");
  });

  it("keeps server rank immutable under a visible local ordering override", () => {
    const rows = backlogRows();
    const local = presentAcquisitionBacklog(rows, "variable_id");

    expect(local.localOrderOverride).toBe(true);
    expect(local.rows.map((row) => row.variable_id)).toEqual(
      [...rows].map((row) => row.variable_id).sort(),
    );
    expect(
      local.rows.find((row) => row.variable_id === "government.balance")
        ?.serverRank,
    ).toBe(8);
  });
});
