import {
  findRunEvidenceNeed,
  findRunEvidencePlan,
  findRunEvidencePromotion,
  normalizeRunEvidenceContext,
  resolveDefaultEvidenceFocus,
} from "@/lib/domain/evidence";

describe("evidence domain", () => {
  it("normalizes context payloads and resolves defaults", () => {
    const context = normalizeRunEvidenceContext({
      data_needs: [
        {
          matched_plan_ids: ["plan-1"],
          metric: "inflation",
          need_id: "need-1",
        },
      ],
      fetch_plans: [
        {
          connector_id: "world-bank",
          dataset_id: "dataset-1",
          matched_need_ids: ["need-1"],
          metric_id: "inflation",
          plan_id: "plan-1",
        },
      ],
      promotion_candidates: [
        {
          connector_id: "world-bank",
          dataset_id: "dataset-1",
          matched_plan_id: "plan-1",
          metric_id: "inflation",
          promotion_id: "promotion-1",
        },
      ],
      related_artifacts: [{ artifact_id: "artifact-1", media_type: "json" }],
      run_id: "run-1",
      source_kind: "natural_language",
      warnings: ["stale snapshot"],
    } as never);

    expect(context).toEqual({
      dataNeeds: [
        {
          geography: null,
          granularity: "annual",
          matchedPlanIds: ["plan-1"],
          metric: "inflation",
          needId: "need-1",
          notes: [],
          purpose: "policy_drafting",
          qualityMin: 0.6,
          timeEnd: null,
          timeStart: null,
        },
      ],
      dataSnapshotRef: null,
      evidenceBundleRef: null,
      executionPlanRef: null,
      fetchPlans: [
        {
          connectorId: "world-bank",
          datasetId: "dataset-1",
          dateEnd: null,
          dateStart: null,
          fallbackCount: 0,
          filters: {},
          granularity: null,
          matchedNeedIds: ["need-1"],
          metricId: "inflation",
          notes: [],
          planId: "plan-1",
          profileId: null,
          qualityMin: 0.6,
          sourceLane: "fastlane",
        },
      ],
      inputBindingsRef: null,
      promotionCandidates: [
        {
          confidence: 0,
          connectorId: "world-bank",
          createdAt: null,
          datasetId: "dataset-1",
          matchedPlanId: "plan-1",
          metadata: {},
          metricId: "inflation",
          profileId: null,
          promotionId: "promotion-1",
          signals: [],
          sourceLane: "explorelane",
          status: "pending",
        },
      ],
      relatedArtifacts: [{ artifact_id: "artifact-1", media_type: "json" }],
      runId: "run-1",
      sourceKind: "natural_language",
      warnings: ["stale snapshot"],
    });

    expect(findRunEvidenceNeed(context, "need-1")?.metric).toBe("inflation");
    expect(findRunEvidencePlan(context, "plan-1")?.connectorId).toBe(
      "world-bank",
    );
    expect(
      findRunEvidencePromotion(context, "promotion-1")?.matchedPlanId,
    ).toBe("plan-1");
    expect(resolveDefaultEvidenceFocus(context)).toBe("promotion");
  });

  it("returns null-safe defaults for missing context and identifiers", () => {
    expect(normalizeRunEvidenceContext(null)).toBeNull();
    expect(findRunEvidenceNeed(null, "need-1")).toBeNull();
    expect(findRunEvidenceNeed({ dataNeeds: [] } as never, null)).toBeNull();
    expect(findRunEvidencePlan({ fetchPlans: [] } as never, null)).toBeNull();
    expect(
      findRunEvidencePromotion({ promotionCandidates: [] } as never, null),
    ).toBeNull();
    expect(resolveDefaultEvidenceFocus(null)).toBe("overview");
    expect(
      resolveDefaultEvidenceFocus({
        dataNeeds: [{ needId: "need-1" }],
        fetchPlans: [],
        promotionCandidates: [],
      } as never),
    ).toBe("need");
    expect(
      resolveDefaultEvidenceFocus({
        dataNeeds: [],
        fetchPlans: [{ planId: "plan-1" }],
        promotionCandidates: [],
      } as never),
    ).toBe("plan");
  });
});
