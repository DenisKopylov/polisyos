import type { RunEvidenceContextPayload } from "../../api/validators";

export type EvidenceArtifactRef = {
  artifact_id: string;
  kind?: string;
  media_type?: string;
};

export type RunEvidenceNeed = {
  needId: string;
  metric: string;
  geography: string | null;
  timeStart: string | null;
  timeEnd: string | null;
  granularity: string;
  qualityMin: number;
  purpose: string;
  matchedPlanIds: string[];
  notes: string[];
};

export type RunEvidencePlan = {
  planId: string;
  metricId: string;
  connectorId: string;
  datasetId: string;
  profileId: string | null;
  sourceLane: string;
  qualityMin: number;
  filters: Record<string, string[]>;
  dateStart: string | null;
  dateEnd: string | null;
  granularity: string | null;
  fallbackCount: number;
  matchedNeedIds: string[];
  notes: string[];
};

export type RunEvidencePromotion = {
  promotionId: string;
  metricId: string;
  connectorId: string;
  datasetId: string;
  profileId: string | null;
  sourceLane: string;
  confidence: number;
  status: string;
  createdAt: string | null;
  signals: string[];
  matchedPlanId: string | null;
  metadata: Record<string, unknown>;
};

export type RunEvidenceContext = {
  runId: string;
  sourceKind: string;
  executionPlanRef: EvidenceArtifactRef | null;
  evidenceBundleRef: EvidenceArtifactRef | null;
  dataSnapshotRef: EvidenceArtifactRef | null;
  inputBindingsRef: EvidenceArtifactRef | null;
  relatedArtifacts: EvidenceArtifactRef[];
  dataNeeds: RunEvidenceNeed[];
  fetchPlans: RunEvidencePlan[];
  promotionCandidates: RunEvidencePromotion[];
  warnings: string[];
};

export type EvidenceFocus =
  | "overview"
  | "need"
  | "plan"
  | "promotion"
  | "artifact";

type EvidenceContextPayload = RunEvidenceContextPayload["context"];

export function normalizeRunEvidenceContext(
  payload: EvidenceContextPayload | null | undefined,
): RunEvidenceContext | null {
  if (!payload) {
    return null;
  }

  return {
    runId: payload.run_id,
    sourceKind: payload.source_kind,
    executionPlanRef: payload.execution_plan_ref ?? null,
    evidenceBundleRef: payload.evidence_bundle_ref ?? null,
    dataSnapshotRef: payload.data_snapshot_ref ?? null,
    inputBindingsRef: payload.input_bindings_ref ?? null,
    relatedArtifacts: payload.related_artifacts ?? [],
    dataNeeds: (payload.data_needs ?? []).map((item) => ({
      needId: item.need_id,
      metric: item.metric,
      geography: item.geography ?? null,
      timeStart: item.time_start ?? null,
      timeEnd: item.time_end ?? null,
      granularity: item.granularity ?? "annual",
      qualityMin: item.quality_min ?? 0.6,
      purpose: item.purpose ?? "policy_drafting",
      matchedPlanIds: item.matched_plan_ids ?? [],
      notes: item.notes ?? [],
    })),
    fetchPlans: (payload.fetch_plans ?? []).map((item) => ({
      planId: item.plan_id,
      metricId: item.metric_id,
      connectorId: item.connector_id,
      datasetId: item.dataset_id,
      profileId: item.profile_id ?? null,
      sourceLane: item.source_lane ?? "fastlane",
      qualityMin: item.quality_min ?? 0.6,
      filters: item.filters ?? {},
      dateStart: item.date_start ?? null,
      dateEnd: item.date_end ?? null,
      granularity: item.granularity ?? null,
      fallbackCount: item.fallback_count ?? 0,
      matchedNeedIds: item.matched_need_ids ?? [],
      notes: item.notes ?? [],
    })),
    promotionCandidates: (payload.promotion_candidates ?? []).map((item) => ({
      promotionId: item.promotion_id,
      metricId: item.metric_id,
      connectorId: item.connector_id,
      datasetId: item.dataset_id,
      profileId: item.profile_id ?? null,
      sourceLane: item.source_lane ?? "explorelane",
      confidence: item.confidence ?? 0,
      status: item.status ?? "pending",
      createdAt: item.created_at ?? null,
      signals: item.signals ?? [],
      matchedPlanId: item.matched_plan_id ?? null,
      metadata: item.metadata ?? {},
    })),
    warnings: payload.warnings ?? [],
  };
}

export function findRunEvidenceNeed(
  context: RunEvidenceContext | null,
  needId: string | null,
) {
  if (!context || !needId) {
    return null;
  }
  return context.dataNeeds.find((item) => item.needId === needId) ?? null;
}

export function findRunEvidencePlan(
  context: RunEvidenceContext | null,
  planId: string | null,
) {
  if (!context || !planId) {
    return null;
  }
  return context.fetchPlans.find((item) => item.planId === planId) ?? null;
}

export function findRunEvidencePromotion(
  context: RunEvidenceContext | null,
  promotionId: string | null,
) {
  if (!context || !promotionId) {
    return null;
  }
  return (
    context.promotionCandidates.find(
      (item) => item.promotionId === promotionId,
    ) ?? null
  );
}

export function resolveDefaultEvidenceFocus(
  context: RunEvidenceContext | null,
): EvidenceFocus {
  if (!context) {
    return "overview";
  }
  if (context.promotionCandidates.length > 0) {
    return "promotion";
  }
  if (context.fetchPlans.length > 0) {
    return "plan";
  }
  if (context.dataNeeds.length > 0) {
    return "need";
  }
  return "overview";
}
