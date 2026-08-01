import {
  createReplayEventEnvelope,
  parseReplayEventEnvelope,
  type ReplayEventEnvelope,
} from "@/app/surfaces/replayEvents";
import type { SurfaceId } from "@/app/surfaces/surfaceRegistry";
import type { SignedPublicDecisionPacket } from "@/features/runs/domain/publicationPacket";

export const OPERATOR_CRAFT_CHANGED_EVENT = "polisyos:operator-craft-changed";

const THRESHOLD_STORAGE_KEY = "polisyos.operatorCraft.threshold.v1";
const ANNOTATION_STORAGE_PREFIX = "polisyos.operatorCraft.annotations.v1:";
const EVIDENCE_WALLET_STORAGE_KEY = "polisyos.operatorCraft.wallet.v1";
const ONBOARDING_STORAGE_PREFIX = "polisyos.operatorCraft.onboarding.v1:";

const THRESHOLD_SCHEMA = "polisyos.operator_threshold.v1" as const;
const ANNOTATION_SCHEMA = "polisyos.operator_annotation.v1" as const;
const WALLET_SCHEMA = "polisyos.operator_evidence_wallet.v1" as const;
const ONBOARDING_SCHEMA = "polisyos.operator_reading_onboarding.v1" as const;

const DEFAULT_THRESHOLD = 0.6;
const FALLBACK_NOW = "1970-01-01T00:00:00.000Z";
const SURFACE_QUERY_SLUGS: Record<string, string> = {
  "runs.annotationSurface": "annotation-surface",
  "runs.evidenceWallet": "evidence-wallet",
  "runs.globalTrustDial": "global-trust-dial",
  "runs.readingOnboarding": "reading-onboarding",
};

export type OperatorCraftChangeKind =
  | "annotation"
  | "onboarding"
  | "threshold"
  | "wallet";

export type ReviewerThresholdProfile = {
  auditEvent: ReplayEventEnvelope | null;
  schema: typeof THRESHOLD_SCHEMA;
  threshold: number;
  updatedAt: string;
  updatedBy: string;
};

export type OperatorSnapshotRef = {
  packetHash: string;
  runId: string;
  signedId: string;
  surfaceId: SurfaceId;
  txAt: string;
  validAt: string;
};

export type OperatorAnnotationTargetKind =
  | "argument"
  | "coverage"
  | "explanation"
  | "glossary"
  | "model_card"
  | "threshold"
  | "verdict";

export type OperatorAnnotationTarget = {
  kind: OperatorAnnotationTargetKind;
  label: string;
  ref: string;
  surfaceId: SurfaceId;
};

export type ReviewerAnnotation = {
  auditEvent: ReplayEventEnvelope;
  body: string;
  createdAt: string;
  id: string;
  reviewerId: string;
  schema: typeof ANNOTATION_SCHEMA;
  snapshot: OperatorSnapshotRef;
  target: OperatorAnnotationTarget;
};

export type EvidenceWalletCandidateKind =
  | "artifact"
  | "coverage"
  | "explanation"
  | "model_card"
  | "threshold";

export type EvidenceWalletCandidate = {
  kind: EvidenceWalletCandidateKind;
  label: string;
  ref: string;
  sourceSurfaceId: SurfaceId;
  summary: string;
};

export type EvidenceWalletItem = {
  addedAt: string;
  auditEvent: ReplayEventEnvelope;
  id: string;
  kind: EvidenceWalletCandidateKind;
  label: string;
  note: string | null;
  ref: string;
  schema: typeof WALLET_SCHEMA;
  snapshot: OperatorSnapshotRef;
  sourceSurfaceId: SurfaceId;
  summary: string;
};

export type ReadingOnboardingStepId =
  | "annotate_snapshot"
  | "inspect_argument"
  | "inspect_glossary"
  | "narrate_provenance"
  | "read_decision"
  | "checklist_complete"
  | "save_evidence"
  | "set_threshold";

const READING_ONBOARDING_STEP_IDS = [
  "annotate_snapshot",
  "inspect_argument",
  "inspect_glossary",
  "narrate_provenance",
  "read_decision",
  "checklist_complete",
  "save_evidence",
  "set_threshold",
] as const satisfies readonly ReadingOnboardingStepId[];

export type ReadingOnboardingState = {
  auditEvents: ReplayEventEnvelope[];
  completedAt: string | null;
  completedStepIds: ReadingOnboardingStepId[];
  firstCompletionAt: string | null;
  runId: string;
  schema: typeof ONBOARDING_SCHEMA;
  startedAt: string;
  timeToCompletionSeconds: number | null;
};

export type ReadingOnboardingStep = {
  completed: boolean;
  evidenceRef: string;
  id: ReadingOnboardingStepId;
  requiredSurfaceId: SurfaceId;
};

export type ReadingOnboardingSnapshot = {
  canComplete: boolean;
  completedCount: number;
  progress: number;
  state: ReadingOnboardingState;
  steps: ReadingOnboardingStep[];
  timeToCompletionSeconds: number | null;
  totalCount: number;
};

export type ThresholdImpact = {
  hiddenClaims: Array<{
    label: string;
    score: SignedPublicDecisionPacket["confidenceLadder"][number]["score"];
    targetRef: string;
  }>;
  hiddenCount: number;
  remainingShare: number;
  threshold: number;
  totalClaims: number;
  visibleCount: number;
};

export type OperatorCraftSnapshot = {
  annotationTargets: OperatorAnnotationTarget[];
  annotations: ReviewerAnnotation[];
  onboarding: ReadingOnboardingSnapshot;
  thresholdImpact: ThresholdImpact;
  thresholdProfile: ReviewerThresholdProfile;
  walletCandidates: EvidenceWalletCandidate[];
  walletItems: EvidenceWalletItem[];
};

type StoredAnnotations = {
  records: ReviewerAnnotation[];
  schema: "polisyos.operator_annotations_store.v1";
};

type StoredWallet = {
  items: EvidenceWalletItem[];
  schema: "polisyos.operator_wallet_store.v1";
};

function clamp(value: number, min = 0, max = 1) {
  return Math.max(min, Math.min(max, value));
}

function rounded(value: number) {
  return Number(clamp(value).toFixed(2));
}

function nowIso(now?: string) {
  return now ?? new Date().toISOString();
}

function storage() {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function readJson<T>(
  key: string,
  guard: (value: unknown) => value is T,
  fallback: T,
) {
  const store = storage();
  if (!store) {
    return fallback;
  }
  const raw = store.getItem(key);
  if (!raw) {
    return fallback;
  }
  try {
    const parsed = JSON.parse(raw) as unknown;
    return guard(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown) {
  const store = storage();
  if (!store) {
    return;
  }
  store.setItem(key, JSON.stringify(value));
}

function emitOperatorCraftChanged(kind: OperatorCraftChangeKind) {
  if (typeof globalThis.dispatchEvent !== "function") {
    return;
  }
  globalThis.dispatchEvent(
    new CustomEvent(OPERATOR_CRAFT_CHANGED_EVENT, {
      detail: { kind },
    }),
  );
}

function normalizeForHash(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => normalizeForHash(item)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(
        ([key, nested]) => `${JSON.stringify(key)}:${normalizeForHash(nested)}`,
      )
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function stableHash(value: unknown) {
  const source = normalizeForHash(value);
  let hash = 0x811c9dc5;
  for (let index = 0; index < source.length; index += 1) {
    hash ^= source.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function routeForSurface(runId: string, surfaceId: SurfaceId) {
  const surfaceSlug =
    SURFACE_QUERY_SLUGS[surfaceId] ?? surfaceId.replace(/^runs\./u, "");
  return {
    fullPath: `/runs/${runId}/overview?surface=${surfaceSlug}`,
    path: `/runs/${runId}/overview`,
    routeId: `surface.${surfaceId}`,
  };
}

function snapshotRef(input: {
  packet: SignedPublicDecisionPacket;
  runId: string;
  surfaceId: SurfaceId;
  txAt: string;
}): OperatorSnapshotRef {
  return {
    packetHash: input.packet.packetHash,
    runId: input.runId,
    signedId: input.packet.signedId,
    surfaceId: input.surfaceId,
    txAt: input.txAt,
    validAt: input.packet.decision.generatedAt ?? input.txAt,
  };
}

function defaultThresholdProfile(now = FALLBACK_NOW): ReviewerThresholdProfile {
  return {
    auditEvent: null,
    schema: THRESHOLD_SCHEMA,
    threshold: DEFAULT_THRESHOLD,
    updatedAt: now,
    updatedBy: "local-reviewer",
  };
}

function isThresholdProfile(value: unknown): value is ReviewerThresholdProfile {
  return (
    isRecord(value) &&
    value.schema === THRESHOLD_SCHEMA &&
    typeof value.threshold === "number" &&
    typeof value.updatedAt === "string" &&
    typeof value.updatedBy === "string"
  );
}

function isAnnotation(value: unknown): value is ReviewerAnnotation {
  return (
    isRecord(value) &&
    value.schema === ANNOTATION_SCHEMA &&
    typeof value.id === "string" &&
    typeof value.body === "string" &&
    typeof value.createdAt === "string" &&
    typeof value.reviewerId === "string" &&
    isRecord(value.snapshot) &&
    isRecord(value.target)
  );
}

function isStoredAnnotations(value: unknown): value is StoredAnnotations {
  return (
    isRecord(value) &&
    value.schema === "polisyos.operator_annotations_store.v1" &&
    Array.isArray(value.records) &&
    value.records.every(isAnnotation)
  );
}

function isWalletItem(value: unknown): value is EvidenceWalletItem {
  return (
    isRecord(value) &&
    value.schema === WALLET_SCHEMA &&
    typeof value.id === "string" &&
    typeof value.ref === "string" &&
    typeof value.addedAt === "string" &&
    isRecord(value.snapshot)
  );
}

function isStoredWallet(value: unknown): value is StoredWallet {
  return (
    isRecord(value) &&
    value.schema === "polisyos.operator_wallet_store.v1" &&
    Array.isArray(value.items) &&
    value.items.every(isWalletItem)
  );
}

function isReadingOnboardingStepId(
  value: unknown,
): value is ReadingOnboardingStepId {
  return (
    typeof value === "string" &&
    (READING_ONBOARDING_STEP_IDS as readonly string[]).includes(value)
  );
}

function annotationKey(runId: string) {
  return `${ANNOTATION_STORAGE_PREFIX}${runId}`;
}

function onboardingKey(runId: string) {
  return `${ONBOARDING_STORAGE_PREFIX}${runId}`;
}

function defaultReadingOnboardingState(runId: string): ReadingOnboardingState {
  return {
    auditEvents: [],
    completedAt: null,
    completedStepIds: [],
    firstCompletionAt: null,
    runId,
    schema: ONBOARDING_SCHEMA,
    startedAt: FALLBACK_NOW,
    timeToCompletionSeconds: null,
  };
}

function normalizeReadingOnboardingState(
  value: unknown,
  runId: string,
): ReadingOnboardingState | null {
  if (
    !isRecord(value) ||
    value.schema !== ONBOARDING_SCHEMA ||
    typeof value.runId !== "string" ||
    typeof value.startedAt !== "string" ||
    !Array.isArray(value.completedStepIds)
  ) {
    return null;
  }
  return {
    auditEvents: Array.isArray(value.auditEvents)
      ? value.auditEvents
          .map((event) => parseReplayEventEnvelope(event))
          .filter((event): event is ReplayEventEnvelope => Boolean(event))
      : [],
    completedAt:
      typeof value.completedAt === "string" ? value.completedAt : null,
    completedStepIds: Array.from(
      new Set(value.completedStepIds.filter(isReadingOnboardingStepId)),
    ),
    firstCompletionAt:
      typeof value.firstCompletionAt === "string"
        ? value.firstCompletionAt
        : null,
    runId: value.runId || runId,
    schema: ONBOARDING_SCHEMA,
    startedAt: value.startedAt,
    timeToCompletionSeconds:
      typeof value.timeToCompletionSeconds === "number"
        ? value.timeToCompletionSeconds
        : null,
  };
}

export function readReviewerThresholdProfile() {
  return readJson(
    THRESHOLD_STORAGE_KEY,
    isThresholdProfile,
    defaultThresholdProfile(),
  );
}

export function setReviewerThreshold(input: {
  next: number;
  now?: string;
  packet?: SignedPublicDecisionPacket;
  reviewerId?: string;
  runId?: string;
  sequence?: number;
}) {
  const previous = readReviewerThresholdProfile();
  const nextThreshold = rounded(input.next);
  const occurredAt = nowIso(input.now);
  const runId = input.runId ?? input.packet?.decision.runId ?? "workspace";
  const route = routeForSurface(runId, "runs.globalTrustDial");
  const auditEvent = createReplayEventEnvelope({
    actor: {
      id: input.reviewerId ?? "local-reviewer",
      lens: "operator",
      role: "reviewer",
    },
    context: {
      runId,
      temporalScope: {
        txAt: occurredAt,
        validAt: input.packet?.decision.generatedAt ?? occurredAt,
      },
    },
    kind: "threshold.changed",
    occurredAt,
    payload: {
      next: nextThreshold,
      packetHash: input.packet?.packetHash,
      previous: previous.threshold,
    },
    route,
    sequence: input.sequence ?? 0,
    surfaceId: "runs.globalTrustDial",
  });
  const profile = {
    auditEvent,
    schema: THRESHOLD_SCHEMA,
    threshold: nextThreshold,
    updatedAt: occurredAt,
    updatedBy: input.reviewerId ?? "local-reviewer",
  } satisfies ReviewerThresholdProfile;
  writeJson(THRESHOLD_STORAGE_KEY, profile);
  emitOperatorCraftChanged("threshold");
  return profile;
}

export function readReviewerAnnotations(runId: string) {
  return readJson<StoredAnnotations>(
    annotationKey(runId),
    isStoredAnnotations,
    {
      records: [],
      schema: "polisyos.operator_annotations_store.v1",
    },
  ).records;
}

export function createReviewerAnnotation(input: {
  body: string;
  existingCount?: number;
  now?: string;
  packet: SignedPublicDecisionPacket;
  reviewerId?: string;
  runId: string;
  target: OperatorAnnotationTarget;
}) {
  const createdAt = nowIso(input.now);
  const body = input.body.trim();
  const snapshot = snapshotRef({
    packet: input.packet,
    runId: input.runId,
    surfaceId: input.target.surfaceId,
    txAt: createdAt,
  });
  const route = routeForSurface(input.runId, "runs.annotationSurface");
  const id = `annotation:${stableHash({
    body,
    createdAt,
    packetHash: input.packet.packetHash,
    targetRef: input.target.ref,
  })}`;
  const auditEvent = createReplayEventEnvelope({
    actor: {
      id: input.reviewerId ?? "local-reviewer",
      lens: "operator",
      role: "reviewer",
    },
    context: {
      runId: input.runId,
      temporalScope: {
        txAt: createdAt,
        validAt: snapshot.validAt,
      },
    },
    kind: "annotation.created",
    occurredAt: createdAt,
    payload: {
      annotationId: id,
      packetHash: input.packet.packetHash,
      targetKind: input.target.kind,
      targetRef: input.target.ref,
    },
    route,
    sequence: input.existingCount ?? 0,
    surfaceId: "runs.annotationSurface",
  });
  return {
    auditEvent,
    body,
    createdAt,
    id,
    reviewerId: input.reviewerId ?? "local-reviewer",
    schema: ANNOTATION_SCHEMA,
    snapshot,
    target: input.target,
  } satisfies ReviewerAnnotation;
}

export function saveReviewerAnnotation(annotation: ReviewerAnnotation) {
  const current = readReviewerAnnotations(annotation.snapshot.runId);
  const next = current.some((record) => record.id === annotation.id)
    ? current
    : [...current, annotation];
  writeJson(annotationKey(annotation.snapshot.runId), {
    records: next,
    schema: "polisyos.operator_annotations_store.v1",
  } satisfies StoredAnnotations);
  emitOperatorCraftChanged("annotation");
  return next;
}

export function readEvidenceWallet() {
  return readJson<StoredWallet>(EVIDENCE_WALLET_STORAGE_KEY, isStoredWallet, {
    items: [],
    schema: "polisyos.operator_wallet_store.v1",
  }).items;
}

export function createEvidenceWalletItem(input: {
  candidate: EvidenceWalletCandidate;
  existingCount?: number;
  note?: string | null;
  now?: string;
  packet: SignedPublicDecisionPacket;
  reviewerId?: string;
  runId: string;
}) {
  const addedAt = nowIso(input.now);
  const snapshot = snapshotRef({
    packet: input.packet,
    runId: input.runId,
    surfaceId: input.candidate.sourceSurfaceId,
    txAt: addedAt,
  });
  const route = routeForSurface(input.runId, "runs.evidenceWallet");
  const id = `wallet:${stableHash({
    packetHash: input.packet.packetHash,
    ref: input.candidate.ref,
    runId: input.runId,
  })}`;
  const auditEvent = createReplayEventEnvelope({
    actor: {
      id: input.reviewerId ?? "local-reviewer",
      lens: "operator",
      role: "reviewer",
    },
    context: {
      runId: input.runId,
      temporalScope: {
        txAt: addedAt,
        validAt: snapshot.validAt,
      },
    },
    kind: "evidence.saved",
    occurredAt: addedAt,
    payload: {
      evidenceRef: input.candidate.ref,
      kind: input.candidate.kind,
      packetHash: input.packet.packetHash,
      walletItemId: id,
    },
    route,
    sequence: input.existingCount ?? 0,
    surfaceId: "runs.evidenceWallet",
  });
  return {
    addedAt,
    auditEvent,
    id,
    kind: input.candidate.kind,
    label: input.candidate.label,
    note: input.note?.trim() || null,
    ref: input.candidate.ref,
    schema: WALLET_SCHEMA,
    snapshot,
    sourceSurfaceId: input.candidate.sourceSurfaceId,
    summary: input.candidate.summary,
  } satisfies EvidenceWalletItem;
}

export function saveEvidenceWalletItem(item: EvidenceWalletItem) {
  const current = readEvidenceWallet();
  const next = current.some((record) => record.id === item.id)
    ? current
    : [...current, item];
  writeJson(EVIDENCE_WALLET_STORAGE_KEY, {
    items: next,
    schema: "polisyos.operator_wallet_store.v1",
  } satisfies StoredWallet);
  emitOperatorCraftChanged("wallet");
  return next;
}

export function readReadingOnboardingState(runId: string) {
  const fallback = defaultReadingOnboardingState(runId);
  const store = storage();
  if (!store) {
    return fallback;
  }
  const raw = store.getItem(onboardingKey(runId));
  if (!raw) {
    return fallback;
  }
  try {
    return (
      normalizeReadingOnboardingState(JSON.parse(raw) as unknown, runId) ??
      fallback
    );
  } catch {
    return fallback;
  }
}

export function startReadingOnboarding(input: { now?: string; runId: string }) {
  const current = readReadingOnboardingState(input.runId);
  if (current.startedAt !== FALLBACK_NOW) {
    return current;
  }
  const next = {
    ...current,
    startedAt: nowIso(input.now),
  };
  writeJson(onboardingKey(input.runId), next);
  emitOperatorCraftChanged("onboarding");
  return next;
}

function createOnboardingStepEvent(input: {
  now: string;
  packet?: SignedPublicDecisionPacket;
  reviewerId?: string;
  runId: string;
  sequence: number;
  stepId: ReadingOnboardingStepId;
}) {
  return createReplayEventEnvelope({
    actor: {
      id: input.reviewerId ?? "local-reviewer",
      lens: "operator",
      role: "reviewer",
    },
    context: {
      runId: input.runId,
      temporalScope: {
        txAt: input.now,
        validAt: input.packet?.decision.generatedAt ?? input.now,
      },
    },
    kind: "onboarding.step.completed",
    occurredAt: input.now,
    payload: {
      packetHash: input.packet?.packetHash,
      stepId: input.stepId,
    },
    route: routeForSurface(input.runId, "runs.readingOnboarding"),
    sequence: input.sequence,
    surfaceId: "runs.readingOnboarding",
  });
}

function hasCompletedRequiredOnboardingSteps(state: ReadingOnboardingState) {
  return ONBOARDING_STEP_ORDER.filter(
    (step) => step.id !== "checklist_complete",
  )
    .map((step) => step.id)
    .every((stepId) => state.completedStepIds.includes(stepId));
}

export function completeReadingOnboardingStep(input: {
  now?: string;
  packet?: SignedPublicDecisionPacket;
  reviewerId?: string;
  runId: string;
  stepId: ReadingOnboardingStepId;
}) {
  const occurredAt = nowIso(input.now);
  const current = startReadingOnboarding({
    now: occurredAt,
    runId: input.runId,
  });
  if (
    input.stepId === "checklist_complete" &&
    !hasCompletedRequiredOnboardingSteps(current)
  ) {
    return current;
  }
  const alreadyCompleted = current.completedStepIds.includes(input.stepId);
  const completedStepIds = alreadyCompleted
    ? current.completedStepIds
    : [...current.completedStepIds, input.stepId];
  const auditEvents = alreadyCompleted
    ? current.auditEvents
    : [
        ...current.auditEvents,
        createOnboardingStepEvent({
          now: occurredAt,
          packet: input.packet,
          reviewerId: input.reviewerId,
          runId: input.runId,
          sequence: current.auditEvents.length,
          stepId: input.stepId,
        }),
      ];
  const next = {
    ...current,
    auditEvents,
    completedStepIds,
  };
  writeJson(onboardingKey(input.runId), next);
  emitOperatorCraftChanged("onboarding");
  return next;
}

export function completeReadingOnboardingRun(input: {
  now?: string;
  packet?: SignedPublicDecisionPacket;
  reviewerId?: string;
  runId: string;
}) {
  const occurredAt = nowIso(input.now);
  const current = startReadingOnboarding({
    now: occurredAt,
    runId: input.runId,
  });
  if (!hasCompletedRequiredOnboardingSteps(current)) {
    return current;
  }
  const withChecklistCompletion = completeReadingOnboardingStep({
    now: occurredAt,
    packet: input.packet,
    reviewerId: input.reviewerId,
    runId: input.runId,
    stepId: "checklist_complete",
  });
  const startedAt = Date.parse(withChecklistCompletion.startedAt);
  const completedAt = Date.parse(occurredAt);
  const seconds =
    Number.isFinite(startedAt) && Number.isFinite(completedAt)
      ? Math.max(0, Math.round((completedAt - startedAt) / 1000))
      : null;
  const next = {
    ...withChecklistCompletion,
    completedAt: occurredAt,
    firstCompletionAt: withChecklistCompletion.firstCompletionAt ?? occurredAt,
    timeToCompletionSeconds:
      withChecklistCompletion.timeToCompletionSeconds ?? seconds,
  } satisfies ReadingOnboardingState;
  writeJson(onboardingKey(input.runId), next);
  emitOperatorCraftChanged("onboarding");
  return next;
}

export function buildThresholdImpact(input: {
  packet: SignedPublicDecisionPacket;
  threshold: number;
}): ThresholdImpact {
  const threshold = rounded(input.threshold);
  const claims = input.packet.confidenceLadder;
  const hiddenClaims = claims
    .filter(
      (claim) =>
        typeof claim.score.point === "number" && claim.score.point < threshold,
    )
    .map((claim) => ({
      label: claim.label,
      score: claim.score,
      targetRef: claim.targetRef,
    }));
  const visibleCount = Math.max(0, claims.length - hiddenClaims.length);
  return {
    hiddenClaims,
    hiddenCount: hiddenClaims.length,
    remainingShare: claims.length ? visibleCount / claims.length : 1,
    threshold,
    totalClaims: claims.length,
    visibleCount,
  };
}

export function buildAnnotationTargets(
  packet: SignedPublicDecisionPacket,
): OperatorAnnotationTarget[] {
  const targets: OperatorAnnotationTarget[] = [
    {
      kind: "verdict",
      label: packet.decision.headline,
      ref: packet.decision.runId,
      surfaceId: "runs.confidenceLadder",
    },
    ...packet.argumentMap.nodes.slice(0, 4).map((node) => ({
      kind: "argument" as const,
      label: node.label,
      ref: node.id,
      surfaceId: "runs.argumentMap" as const,
    })),
    ...packet.deterministicExplanations.slice(0, 3).map((explanation) => ({
      kind: "explanation" as const,
      label: explanation.label,
      ref: explanation.subjectRef,
      surfaceId: "runs.comprehensionLayer" as const,
    })),
    {
      kind: "coverage",
      label: packet.coverageCaveat.summary,
      ref: `coverage:${packet.coverageCaveat.caveatState.label}`,
      surfaceId: "runs.coverageMap",
    },
    {
      kind: "threshold",
      label: packet.thresholdContract.policyRef,
      ref: packet.thresholdContract.policyRef,
      surfaceId: "runs.thresholdContract",
    },
    {
      kind: "model_card",
      label: packet.modelCard.title,
      ref: packet.modelCard.modelId,
      surfaceId: "runs.modelCard",
    },
  ];

  return targets;
}

export function buildEvidenceWalletCandidates(
  packet: SignedPublicDecisionPacket,
): EvidenceWalletCandidate[] {
  const modelRefs = packet.modelCard.references.slice(0, 4).map((ref) => ({
    kind: "artifact" as const,
    label: ref.label,
    ref: ref.locator,
    sourceSurfaceId: "runs.modelCard" as const,
    summary: `${ref.type} reference from citation-grade model card.`,
  }));
  const explanations = packet.deterministicExplanations
    .slice(0, 3)
    .map((explanation) => ({
      kind: "explanation" as const,
      label: explanation.label,
      ref: explanation.subjectRef,
      sourceSurfaceId: "runs.comprehensionLayer" as const,
      summary: explanation.narrative,
    }));
  const coverage = packet.coverageCaveat.regions.slice(0, 3).map((region) => ({
    kind: "coverage" as const,
    label: region.label,
    ref: `coverage:${region.label}`,
    sourceSurfaceId: "runs.coverageMap" as const,
    summary: region.caveat,
  }));
  const seen = new Set<string>();
  return [...modelRefs, ...explanations, ...coverage].filter((candidate) => {
    if (seen.has(candidate.ref)) {
      return false;
    }
    seen.add(candidate.ref);
    return true;
  });
}

const ONBOARDING_STEP_ORDER: Array<{
  evidenceRef: string;
  id: ReadingOnboardingStepId;
  requiredSurfaceId: SurfaceId;
}> = [
  {
    evidenceRef: "decision.summary",
    id: "read_decision",
    requiredSurfaceId: "runs.overview",
  },
  {
    evidenceRef: "argument.map",
    id: "inspect_argument",
    requiredSurfaceId: "runs.argumentMap",
  },
  {
    evidenceRef: "derivation.path",
    id: "narrate_provenance",
    requiredSurfaceId: "runs.comprehensionLayer",
  },
  {
    evidenceRef: "glossary.lens",
    id: "inspect_glossary",
    requiredSurfaceId: "runs.glossaryLens",
  },
  {
    evidenceRef: "threshold.profile",
    id: "set_threshold",
    requiredSurfaceId: "runs.globalTrustDial",
  },
  {
    evidenceRef: "evidence.wallet",
    id: "save_evidence",
    requiredSurfaceId: "runs.evidenceWallet",
  },
  {
    evidenceRef: "annotation.snapshot",
    id: "annotate_snapshot",
    requiredSurfaceId: "runs.annotationSurface",
  },
  {
    evidenceRef: "onboarding.checklist_complete",
    id: "checklist_complete",
    requiredSurfaceId: "runs.readingOnboarding",
  },
];

export function buildReadingOnboardingSnapshot(input: {
  annotations: ReviewerAnnotation[];
  now?: string;
  packet: SignedPublicDecisionPacket;
  state: ReadingOnboardingState;
  thresholdProfile: ReviewerThresholdProfile;
  walletItems: EvidenceWalletItem[];
}): ReadingOnboardingSnapshot {
  const completed = new Set<ReadingOnboardingStepId>(
    input.state.completedStepIds,
  );
  const steps = ONBOARDING_STEP_ORDER.map((step) => ({
    ...step,
    completed: completed.has(step.id),
  }));
  const completedCount = steps.filter((step) => step.completed).length;
  const canComplete = steps
    .filter((step) => step.id !== "checklist_complete")
    .every((step) => step.completed);
  return {
    canComplete,
    completedCount,
    progress: steps.length ? completedCount / steps.length : 1,
    state: input.state,
    steps,
    timeToCompletionSeconds: input.state.timeToCompletionSeconds,
    totalCount: steps.length,
  };
}

export function buildOperatorCraftSnapshot(input: {
  annotations?: ReviewerAnnotation[];
  now?: string;
  onboardingState?: ReadingOnboardingState;
  packet: SignedPublicDecisionPacket;
  runId: string;
  thresholdProfile?: ReviewerThresholdProfile;
  walletItems?: EvidenceWalletItem[];
}): OperatorCraftSnapshot {
  const thresholdProfile =
    input.thresholdProfile ?? readReviewerThresholdProfile();
  const annotations = input.annotations ?? readReviewerAnnotations(input.runId);
  const walletItems = input.walletItems ?? readEvidenceWallet();
  const state =
    input.onboardingState ?? readReadingOnboardingState(input.runId);

  return {
    annotationTargets: buildAnnotationTargets(input.packet),
    annotations: annotations.filter(
      (annotation) =>
        annotation.snapshot.runId === input.runId &&
        annotation.snapshot.packetHash === input.packet.packetHash,
    ),
    onboarding: buildReadingOnboardingSnapshot({
      annotations,
      now: input.now,
      packet: input.packet,
      state,
      thresholdProfile,
      walletItems,
    }),
    thresholdImpact: buildThresholdImpact({
      packet: input.packet,
      threshold: thresholdProfile.threshold,
    }),
    thresholdProfile,
    walletCandidates: buildEvidenceWalletCandidates(input.packet),
    walletItems: walletItems.filter(
      (item) =>
        item.snapshot.runId === input.runId &&
        item.snapshot.packetHash === input.packet.packetHash,
    ),
  };
}
