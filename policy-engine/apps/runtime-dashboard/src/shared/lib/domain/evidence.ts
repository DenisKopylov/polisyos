import type { RunEvidenceContextPayload } from "@/api/validators";

export type EvidenceArtifactRef = {
  artifact_id: string;
  kind?: string | null;
  media_type?: string | null;
  manifest_profile_sha256?: string | null;
};

export type ArtifactViewResponseIdentity = {
  artifact_id: string;
  kind?: string | null;
  media_type?: string | null;
  manifest_profile_sha256?: string | null;
};

const MANIFEST_PROFILE_SHA256 = /^sha256:[0-9a-f]{64}$/u;

export function artifactManifestProfileKey(
  artifactId: string,
  manifestProfileSha256?: string | null,
): string {
  return JSON.stringify([artifactId, manifestProfileSha256 ?? null]);
}

export function evidenceArtifactRefKey(ref: EvidenceArtifactRef): string {
  return JSON.stringify([
    ref.artifact_id,
    ref.kind ?? null,
    ref.media_type ?? null,
    ref.manifest_profile_sha256 ?? null,
  ]);
}

/**
 * Parse the single-value URL representation of a typed artifact reference.
 *
 * This identifies a requested view; it does not attest producer custody or
 * select a server manifest profile unless the profile component is non-null.
 */
export function parseEvidenceArtifactRefKey(
  value: string,
): EvidenceArtifactRef | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    return null;
  }
  if (!Array.isArray(parsed) || parsed.length !== 4) {
    return null;
  }
  const [artifactId, kind, mediaType, profile] = parsed as unknown[];
  if (
    typeof artifactId !== "string" ||
    artifactId.trim() === "" ||
    (kind !== null && (typeof kind !== "string" || kind.trim() === "")) ||
    (mediaType !== null &&
      (typeof mediaType !== "string" || mediaType.trim() === "")) ||
    (profile !== null &&
      (typeof profile !== "string" || !MANIFEST_PROFILE_SHA256.test(profile)))
  ) {
    return null;
  }
  return {
    artifact_id: artifactId,
    kind: kind as string | null,
    media_type: mediaType as string | null,
    manifest_profile_sha256: profile as string | null,
  };
}

/** Return whether a resolved API view agrees with every supplied ref field. */
export function artifactRefMatchesResolvedView(
  expected: EvidenceArtifactRef,
  actual: ArtifactViewResponseIdentity,
): boolean {
  return (
    expected.artifact_id === actual.artifact_id &&
    (expected.kind == null || expected.kind === actual.kind) &&
    (expected.media_type == null ||
      expected.media_type === actual.media_type) &&
    (expected.manifest_profile_sha256 == null ||
      expected.manifest_profile_sha256 === actual.manifest_profile_sha256)
  );
}

/** Compare two resolved views, treating an omitted profile as legacy null. */
export function sameResolvedArtifactView(
  left: ArtifactViewResponseIdentity,
  right: ArtifactViewResponseIdentity,
): boolean {
  return evidenceArtifactRefKey(left) === evidenceArtifactRefKey(right);
}

/** Normalize a legacy ID/profile call or preserve a supplied full typed ref. */
export function artifactRefForRequest(
  value: string | EvidenceArtifactRef | undefined,
  profileOverride?: string | null,
): EvidenceArtifactRef | undefined {
  if (value === undefined) {
    return undefined;
  }
  if (typeof value === "string") {
    return {
      artifact_id: value,
      manifest_profile_sha256: profileOverride ?? null,
    };
  }
  if (
    profileOverride !== undefined &&
    profileOverride !== (value.manifest_profile_sha256 ?? null)
  ) {
    throw new Error("artifact ref and profile selector disagree");
  }
  return value;
}

export function dedupeEvidenceArtifactRefs(
  refs: Array<EvidenceArtifactRef | null | undefined>,
): EvidenceArtifactRef[] {
  const seen = new Set<string>();
  const result: EvidenceArtifactRef[] = [];
  for (const ref of refs) {
    if (!ref?.artifact_id) {
      continue;
    }
    const key = evidenceArtifactRefKey(ref);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(ref);
  }
  return result;
}

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
  dataViewRequestRef: EvidenceArtifactRef | null;
  dataViewRequestProfileStatus: DataViewRequestProfileStatus;
  inputBindingsRef: EvidenceArtifactRef | null;
  fabricRetrievalTraceRef: EvidenceArtifactRef | null;
  materializationRefs: Record<string, EvidenceArtifactRef>;
  productionDataEvidenceContext: Record<string, unknown>;
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
export type DataViewRequestProfileStatus =
  EvidenceContextPayload["data_view_request_profile_status"];

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
    dataViewRequestRef: payload.data_view_request_ref ?? null,
    dataViewRequestProfileStatus:
      payload.data_view_request_profile_status ?? "not_established",
    inputBindingsRef: payload.input_bindings_ref ?? null,
    fabricRetrievalTraceRef: payload.fabric_retrieval_trace_ref ?? null,
    materializationRefs: payload.materialization_refs ?? {},
    productionDataEvidenceContext:
      payload.production_data_evidence_context ?? {},
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
