import type { DecisionCardViewModel } from "@/shared/lib/domain/decision";
import type { RunEvidenceContext } from "@/shared/lib/domain/evidence";
import type { GovernanceIssueView } from "@/shared/lib/domain/governance";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";
import type { QuantityValueOutput } from "@polisyos/runtime-api-client";

import type { DisputeRecord } from "./disputes";

export type StakeholderLens =
  | "operator"
  | "regulator"
  | "appellant"
  | "data_scientist"
  | "public_viewer";

export type ApprovalBlockKind =
  | "fairness"
  | "harm"
  | "objection"
  | "embargo"
  | "slow_review"
  | "revocation";

export type ReadinessSectionId =
  | "objections"
  | "fairness"
  | "harm"
  | "provenance"
  | "uncertainty"
  | "identifiability"
  | "revocation";

export type ReadinessSeverity = "block" | "warn" | "pass";

export type ReviewAttentionSection = {
  acknowledgedAt: string | null;
  dwellSeconds: number;
  events: Array<{
    at: string;
    event: "opened" | "acknowledged";
    replayRef: string;
  }>;
  openedAt: string | null;
};

export type ReviewAttentionState = {
  sections: Record<ReadinessSectionId, ReviewAttentionSection>;
  version: 1;
};

export type LensProjection = {
  collapsedSections: string[];
  decisionHash: string;
  emphasis: string[];
  lens: StakeholderLens;
  riskOrder: ApprovalBlockKind[];
  terminology: Record<string, string>;
};

export type ApprovalBlock = {
  auditRef: string;
  detailKey: string;
  id: string;
  kind: ApprovalBlockKind;
  severity: "block";
  targetRef: string;
};

export type FairnessAuditGroup = {
  calibrationDelta: number;
  ciLower: number;
  ciUpper: number;
  disparateImpactRatio: number;
  groupId: string;
  groupLabel: string;
  isProtected: boolean;
  primaryDelta: QuantityValueOutput;
  referenceShare: number;
  selectionShare: number;
  status: ReadinessSeverity;
};

export type FairnessAuditView = {
  blocked: boolean;
  evidenceAvailable: boolean;
  groups: FairnessAuditGroup[];
  sentinel: {
    auditRef: string;
    groupLabel: string;
    ratio: number;
    threshold: number;
  } | null;
  threshold: number;
  worstGroup: FairnessAuditGroup | null;
};

export type HarmAssessmentRow = {
  expectedHarm: string;
  id: string;
  likelihood: "low" | "medium" | "high";
  mitigation: string;
  residualRisk: "low" | "medium" | "high";
  required: boolean;
  status: ReadinessSeverity;
};

export type HarmAssessmentView = {
  blocked: boolean;
  euAiAct: {
    humanOversight: ReadinessSeverity;
    redressPath: ReadinessSeverity;
    riskClass: "minimal" | "limited" | "high";
    transparency: ReadinessSeverity;
  };
  rows: HarmAssessmentRow[];
};

export type EmbargoMask = {
  auditRef: string;
  reasonCode: string;
  skeletonRef: string;
  status: "active" | "unlock_pending" | "clear";
  unlockAt: string | null;
};

export type EmbargoOverlayView = {
  blocked: boolean;
  masks: EmbargoMask[];
};

export type SlowReviewRequirement = {
  acknowledged: boolean;
  auditRef: string;
  blocked: boolean;
  dwellSeconds: number;
  id: ReadinessSectionId;
  minimumDwellSeconds: number;
  opened: boolean;
};

export type SlowReviewView = {
  blocked: boolean;
  completed: number;
  requirements: SlowReviewRequirement[];
  total: number;
};

export type RevocationLedgerEntry = {
  knownAt: string;
  policyRef: string;
  reason: string;
  relation: "predecessor" | "current" | "successor";
  status: "active" | "revoked" | "superseded" | "replacement";
  validAt: string;
};

export type RevocationLedgerView = {
  blocked: boolean;
  chain: RevocationLedgerEntry[];
  currentStatus: "active" | "revoked" | "superseded";
  impactedRuns: string[];
};

export type PublicSectorReadinessSnapshot = {
  approvalReady: boolean;
  auditTrail: Array<{
    at: string;
    event: string;
    ref: string;
  }>;
  blocks: ApprovalBlock[];
  decisionHash: string;
  embargo: EmbargoOverlayView;
  fairness: FairnessAuditView;
  harm: HarmAssessmentView;
  lens: LensProjection;
  objections: {
    blocked: boolean;
    open: DisputeRecord[];
    total: number;
  };
  revocation: RevocationLedgerView;
  slowReview: SlowReviewView;
};

export const PUBLIC_READINESS_CHANGED_EVENT =
  "polisyos:atlas:public-readiness-changed";

export const STAKEHOLDER_LENSES: StakeholderLens[] = [
  "operator",
  "regulator",
  "appellant",
  "data_scientist",
  "public_viewer",
];

export const READINESS_SECTIONS: ReadinessSectionId[] = [
  "objections",
  "fairness",
  "harm",
  "provenance",
  "uncertainty",
  "identifiability",
  "revocation",
];

const FAIRNESS_THRESHOLD = 0.8;
const MINIMUM_DWELL_SECONDS: Record<ReadinessSectionId, number> = {
  fairness: 8,
  harm: 10,
  identifiability: 8,
  objections: 6,
  provenance: 6,
  revocation: 6,
  uncertainty: 8,
};

function clamp(value: number, min = 0, max = 1) {
  return Math.max(min, Math.min(max, value));
}

function stableJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(stableJson).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, nested]) => `${JSON.stringify(key)}:${stableJson(nested)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function stableHash(value: unknown) {
  const source = stableJson(value);
  let hash = 5381;
  for (let index = 0; index < source.length; index += 1) {
    hash = (hash * 33) ^ source.charCodeAt(index);
  }
  return `ast:${(hash >>> 0).toString(16).padStart(8, "0")}`;
}

function issueText(issue: GovernanceIssueView) {
  return `${issue.code} ${issue.message} ${issue.passId ?? ""}`.toLowerCase();
}

function issuesMatching(issues: GovernanceIssueView[], pattern: RegExp) {
  return issues.filter((issue) => pattern.test(issueText(issue)));
}

function isBlockingIssue(issue: GovernanceIssueView) {
  return issue.severity === "blocker" || issue.severity === "warning";
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : null;
}

function safePublicRef(value: string | null | undefined, fallback: string) {
  const source = value?.trim() || fallback;
  const masked = source
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "redacted_email")
    .replace(/\b\d{3,}\b/g, "redacted_number")
    .replace(/[^A-Za-z0-9:._/-]+/g, "_")
    .slice(0, 96);
  return masked.length > 0 ? masked : fallback;
}

function buildDecisionHash(input: {
  decisionView: DecisionCardViewModel | null | undefined;
  evidenceContext?: RunEvidenceContext | null;
  governanceIssues: GovernanceIssueView[];
}) {
  return stableHash({
    evidenceRefs: [
      input.evidenceContext?.evidenceBundleRef?.artifact_id,
      input.evidenceContext?.dataSnapshotRef?.artifact_id,
      input.evidenceContext?.inputBindingsRef?.artifact_id,
    ],
    issues: input.governanceIssues.map((issue) => ({
      code: issue.code,
      passId: issue.passId,
      severity: issue.severity,
    })),
    metrics: input.decisionView?.keyMetrics.map((metric) => ({
      ciLower: metric.ciLower,
      ciUpper: metric.ciUpper,
      name: metric.name,
      value: metric.value,
    })),
    runId: input.decisionView?.runId,
    verdict: input.decisionView?.verdict,
  });
}

export function buildLensProjection(input: {
  decisionHash: string;
  lens: StakeholderLens;
}): LensProjection {
  const base = {
    decisionHash: input.decisionHash,
    lens: input.lens,
  };
  if (input.lens === "regulator") {
    return {
      ...base,
      collapsedSections: ["operatorSummary"],
      emphasis: ["euAiAct", "auditTrail", "fairness", "revocation"],
      riskOrder: [
        "embargo",
        "fairness",
        "harm",
        "objection",
        "revocation",
        "slow_review",
      ],
      terminology: {
        objection: "formal objection",
        packet: "administrative decision record",
      },
    };
  }
  if (input.lens === "appellant") {
    return {
      ...base,
      collapsedSections: ["modelInternals"],
      emphasis: ["redressPath", "objections", "fairness", "harm"],
      riskOrder: [
        "objection",
        "fairness",
        "harm",
        "embargo",
        "revocation",
        "slow_review",
      ],
      terminology: {
        objection: "appeal ground",
        packet: "decision explanation",
      },
    };
  }
  if (input.lens === "data_scientist") {
    return {
      ...base,
      collapsedSections: ["publicSummary"],
      emphasis: ["identifiability", "uncertainty", "calibration", "provenance"],
      riskOrder: [
        "fairness",
        "embargo",
        "harm",
        "revocation",
        "objection",
        "slow_review",
      ],
      terminology: {
        objection: "review challenge",
        packet: "decision AST projection",
      },
    };
  }
  if (input.lens === "public_viewer") {
    return {
      ...base,
      collapsedSections: ["privateEvidence", "operatorTelemetry"],
      emphasis: ["publicNotice", "redressPath", "embargo", "revocation"],
      riskOrder: [
        "embargo",
        "revocation",
        "fairness",
        "harm",
        "objection",
        "slow_review",
      ],
      terminology: {
        objection: "public objection",
        packet: "public decision record",
      },
    };
  }
  return {
    ...base,
    collapsedSections: ["legalAppendix"],
    emphasis: ["approvalBlockers", "slowReview", "objections", "sentinel"],
    riskOrder: [
      "objection",
      "fairness",
      "harm",
      "embargo",
      "slow_review",
      "revocation",
    ],
    terminology: {
      objection: "objection",
      packet: "decision packet",
    },
  };
}

export function buildFairnessAuditView(input: {
  decisionView: DecisionCardViewModel | null | undefined;
  governanceIssues: GovernanceIssueView[];
}): FairnessAuditView {
  const fairnessIssues = issuesMatching(
    input.governanceIssues,
    /fair|bias|disparate|protected|equal/i,
  );
  const rows =
    input.decisionView?.distributional?.breakdowns.flatMap(
      (breakdown) => breakdown.rows,
    ) ?? [];
  const evidenceAvailable = rows.length > 0 || fairnessIssues.length > 0;
  const sourceRows = rows.length
    ? rows.map((row, index) => ({
        ...row,
        primaryDelta: untracedDecisionQuantity({
          label: `${row.cohortLabel} primary delta`,
          metricId: `fairness.primary_delta.${index + 1}`,
          point: row.primaryDelta,
          reasonCode: "fairness_projection_without_runtime_quantity",
          time: { valid_at: input.decisionView?.generatedAt ?? null },
          trackingIssue: "ATLAS-DS4-C06",
          unit: { code: "1", display: "ratio", system: "ucum" },
        }),
      }))
    : fairnessIssues.length
      ? fairnessIssues.map((issue) => ({
          cohortLabel: issue.passId ?? issue.code,
          direction: "negative",
          isVulnerable: true,
          populationShare: 0.25,
          primaryDelta: untracedDecisionQuantity({
            label: "Fairness issue fallback delta",
            metricId: "fairness.primary_delta.issue_fallback",
            point: -0.12,
            reasonCode: "governance_issue_without_fairness_quantity",
            trackingIssue: "ATLAS-DS4-C06",
            unit: { code: "1", display: "ratio", system: "ucum" },
          }),
        }))
      : [
          {
            cohortLabel: "Fairness evidence missing",
            direction: "negative",
            isVulnerable: true,
            populationShare: 1,
            primaryDelta: untracedDecisionQuantity({
              label: "Missing fairness evidence delta",
              metricId: "fairness.primary_delta.missing_evidence",
              point: -0.5,
              reasonCode: "missing_fairness_evidence",
              trackingIssue: "ATLAS-DS4-C06",
              unit: { code: "1", display: "ratio", system: "ucum" },
            }),
          },
        ];
  const selectionShares = sourceRows.map((row) => {
    const point =
      typeof row.primaryDelta.point === "number"
        ? row.primaryDelta.point
        : null;
    return point === null ? 0.5 : clamp(0.5 + point, 0.02, 0.98);
  });
  const referenceShare = Math.max(...selectionShares, 0.5);
  const groups = sourceRows.map<FairnessAuditGroup>((row, index) => {
    const primaryDeltaPoint =
      typeof row.primaryDelta.point === "number"
        ? row.primaryDelta.point
        : null;
    const selectionShare = selectionShares[index] ?? 0.5;
    const disparateImpactRatio = selectionShare / referenceShare;
    const issueOverride = fairnessIssues.some(isBlockingIssue);
    const status =
      !evidenceAvailable ||
      disparateImpactRatio < FAIRNESS_THRESHOLD ||
      issueOverride
        ? "block"
        : disparateImpactRatio < 0.9
          ? "warn"
          : "pass";
    return {
      calibrationDelta:
        Math.abs(primaryDeltaPoint ?? Number.NaN) *
        (row.isVulnerable ? 1.4 : 1),
      ciLower: clamp(disparateImpactRatio - (row.isVulnerable ? 0.11 : 0.07)),
      ciUpper: clamp(disparateImpactRatio + 0.08),
      disparateImpactRatio,
      groupId: `fairness:${index + 1}`,
      groupLabel: row.cohortLabel,
      isProtected: row.isVulnerable || issueOverride,
      primaryDelta: row.primaryDelta,
      referenceShare,
      selectionShare,
      status,
    };
  });
  const worstGroup =
    [...groups].sort(
      (left, right) =>
        statusScore(right.status) - statusScore(left.status) ||
        left.disparateImpactRatio - right.disparateImpactRatio,
    )[0] ?? null;
  const blocked = Boolean(worstGroup && worstGroup.status === "block");

  return {
    blocked,
    evidenceAvailable,
    groups,
    sentinel:
      blocked && worstGroup
        ? {
            auditRef: `fairness:${input.decisionView?.runId ?? "run"}:${worstGroup.groupId}`,
            groupLabel: worstGroup.groupLabel,
            ratio: worstGroup.disparateImpactRatio,
            threshold: FAIRNESS_THRESHOLD,
          }
        : null,
    threshold: FAIRNESS_THRESHOLD,
    worstGroup,
  };
}

function statusScore(status: ReadinessSeverity) {
  if (status === "block") {
    return 2;
  }
  if (status === "warn") {
    return 1;
  }
  return 0;
}

export function buildHarmAssessmentView(input: {
  decisionView: DecisionCardViewModel | null | undefined;
  governanceIssues: GovernanceIssueView[];
  reviewState: ReviewAttentionState;
}): HarmAssessmentView {
  const harmIssues = issuesMatching(
    input.governanceIssues,
    /harm|safety|injury|oversight|redress|transparen|ai act|high.risk/i,
  );
  const harmAcknowledged = Boolean(
    input.reviewState.sections.harm.acknowledgedAt,
  );
  const highRisk =
    input.decisionView?.verdict === "APPROVE" ||
    harmIssues.some(isBlockingIssue);
  const issueBlocking = harmIssues.some(
    (issue) => issue.severity === "blocker",
  );
  const rows: HarmAssessmentRow[] = [
    {
      expectedHarm: "phase34.harm.expected.disparateDenial",
      id: "expected-harm",
      likelihood: highRisk ? "medium" : "low",
      mitigation: "phase34.harm.mitigation.humanOversight",
      required: true,
      residualRisk: harmAcknowledged && !issueBlocking ? "medium" : "high",
      status: harmAcknowledged && !issueBlocking ? "warn" : "block",
    },
    {
      expectedHarm: "phase34.harm.expected.noRedress",
      id: "redress",
      likelihood: highRisk ? "high" : "medium",
      mitigation: "phase34.harm.mitigation.redress",
      required: true,
      residualRisk: harmAcknowledged && !issueBlocking ? "low" : "high",
      status: harmAcknowledged && !issueBlocking ? "pass" : "block",
    },
    {
      expectedHarm: "phase34.harm.expected.opacity",
      id: "transparency",
      likelihood: "medium",
      mitigation: "phase34.harm.mitigation.transparency",
      required: true,
      residualRisk: harmAcknowledged ? "low" : "medium",
      status: harmAcknowledged ? "pass" : "block",
    },
  ];
  const blocked = rows.some((row) => row.required && row.status === "block");

  return {
    blocked,
    euAiAct: {
      humanOversight: harmAcknowledged && !issueBlocking ? "pass" : "block",
      redressPath: harmAcknowledged ? "pass" : "block",
      riskClass: highRisk ? "high" : "limited",
      transparency: harmAcknowledged ? "pass" : "block",
    },
    rows,
  };
}

export function buildEmbargoOverlayView(input: {
  evidenceContext?: RunEvidenceContext | null;
  governanceIssues: GovernanceIssueView[];
  now?: string;
  runId: string;
}): EmbargoOverlayView {
  const embargoIssues = issuesMatching(
    input.governanceIssues,
    /embargo|blackout|private|restricted|confidential|mask/i,
  );
  const nowMs = Date.parse(input.now ?? new Date().toISOString());
  const warningMasks =
    input.evidenceContext?.warnings.filter((warning) =>
      /embargo|blackout|private|restricted|confidential|mask/i.test(warning),
    ) ?? [];
  const statusForIssue = (
    issue: GovernanceIssueView,
  ): EmbargoMask["status"] => {
    const unlockAt = stringValue(issue.raw.unlock_at);
    const unlockMs = unlockAt ? Date.parse(unlockAt) : Number.NaN;
    if (
      unlockAt &&
      Number.isFinite(unlockMs) &&
      Number.isFinite(nowMs) &&
      unlockMs <= nowMs
    ) {
      return "clear";
    }
    return isBlockingIssue(issue) ? "active" : "unlock_pending";
  };
  const masks: EmbargoMask[] = [
    ...embargoIssues.map((issue, index) => ({
      auditRef: `embargo:${input.runId}:issue-${index + 1}`,
      reasonCode: safePublicRef(issue.code, `reason:${index + 1}`),
      skeletonRef: safePublicRef(
        issue.path ?? issue.passId,
        `skeleton:${index + 1}`,
      ),
      status: statusForIssue(issue),
      unlockAt: stringValue(issue.raw.unlock_at),
    })),
    ...warningMasks.map((_warning, index) => ({
      auditRef: `embargo:${input.runId}:warning-${index + 1}`,
      reasonCode: `warning_mask_${index + 1}`,
      skeletonRef: `warning-skeleton:${index + 1}`,
      status: "active" as const,
      unlockAt: null,
    })),
  ];

  return {
    blocked: masks.some((mask) => mask.status === "active"),
    masks,
  };
}

export function createDefaultReviewAttentionState(): ReviewAttentionState {
  return {
    sections: READINESS_SECTIONS.reduce(
      (acc, id) => ({
        ...acc,
        [id]: {
          acknowledgedAt: null,
          dwellSeconds: 0,
          events: [],
          openedAt: null,
        },
      }),
      {} as Record<ReadinessSectionId, ReviewAttentionSection>,
    ),
    version: 1,
  };
}

export function reviewAttentionStorageKey(runId: string) {
  return `polisyos:atlas:review-attention:${runId}`;
}

function isReviewAttentionState(value: unknown): value is ReviewAttentionState {
  if (!value || typeof value !== "object") {
    return false;
  }
  const record = value as Partial<ReviewAttentionState>;
  return (
    record.version === 1 &&
    Boolean(record.sections) &&
    READINESS_SECTIONS.every((id) => {
      const section = record.sections?.[id];
      return (
        Boolean(section) &&
        (section?.openedAt === null || typeof section?.openedAt === "string") &&
        (section?.acknowledgedAt === null ||
          typeof section?.acknowledgedAt === "string")
      );
    })
  );
}

export function readStoredReviewAttention(runId: string): ReviewAttentionState {
  if (typeof window === "undefined") {
    return createDefaultReviewAttentionState();
  }
  try {
    const raw = window.localStorage.getItem(reviewAttentionStorageKey(runId));
    if (!raw) {
      return createDefaultReviewAttentionState();
    }
    const parsed = JSON.parse(raw) as unknown;
    return isReviewAttentionState(parsed)
      ? parsed
      : createDefaultReviewAttentionState();
  } catch {
    return createDefaultReviewAttentionState();
  }
}

export function writeStoredReviewAttention(
  runId: string,
  state: ReviewAttentionState,
) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(
      reviewAttentionStorageKey(runId),
      stableJson(state),
    );
    window.dispatchEvent(
      new CustomEvent(PUBLIC_READINESS_CHANGED_EVENT, {
        detail: { runId },
      }),
    );
  } catch {
    // Local attention persistence is best-effort until the review API is present.
  }
}

export function markReviewSectionOpened(input: {
  at: string;
  runId: string;
  sectionId: ReadinessSectionId;
  state: ReviewAttentionState;
}): ReviewAttentionState {
  const section = input.state.sections[input.sectionId];
  if (section.openedAt) {
    return input.state;
  }
  return {
    ...input.state,
    sections: {
      ...input.state.sections,
      [input.sectionId]: {
        ...section,
        events: [
          ...section.events,
          {
            at: input.at,
            event: "opened",
            replayRef: `review:${input.runId}:${input.sectionId}:opened:${input.at}`,
          },
        ],
        openedAt: input.at,
      },
    },
  };
}

export function acknowledgeReviewSection(input: {
  at: string;
  runId: string;
  sectionId: ReadinessSectionId;
  state: ReviewAttentionState;
}): ReviewAttentionState {
  const section = input.state.sections[input.sectionId];
  if (!section.openedAt || section.acknowledgedAt) {
    return input.state;
  }
  const dwellSeconds = Math.max(
    section.dwellSeconds,
    secondsBetween(section.openedAt, input.at),
  );
  return {
    ...input.state,
    sections: {
      ...input.state.sections,
      [input.sectionId]: {
        ...section,
        acknowledgedAt: input.at,
        dwellSeconds,
        events: [
          ...section.events,
          {
            at: input.at,
            event: "acknowledged",
            replayRef: `review:${input.runId}:${input.sectionId}:acknowledged:${input.at}`,
          },
        ],
      },
    },
  };
}

function secondsBetween(start: string, end: string) {
  const startMs = Date.parse(start);
  const endMs = Date.parse(end);
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) {
    return 0;
  }
  return Math.max(0, Math.floor((endMs - startMs) / 1000));
}

export function buildSlowReviewView(input: {
  now: string;
  reviewState: ReviewAttentionState;
  runId: string;
}): SlowReviewView {
  const requirements = READINESS_SECTIONS.map<SlowReviewRequirement>((id) => {
    const section = input.reviewState.sections[id];
    const dwellSeconds = section.openedAt
      ? Math.max(
          section.dwellSeconds,
          secondsBetween(section.openedAt, section.acknowledgedAt ?? input.now),
        )
      : 0;
    const minimumDwellSeconds = MINIMUM_DWELL_SECONDS[id];
    const acknowledged = Boolean(section.acknowledgedAt);
    const opened = Boolean(section.openedAt);
    const blocked =
      !opened || !acknowledged || dwellSeconds < minimumDwellSeconds;
    return {
      acknowledged,
      auditRef: `review:${input.runId}:${id}`,
      blocked,
      dwellSeconds,
      id,
      minimumDwellSeconds,
      opened,
    };
  });
  const completed = requirements.filter(
    (requirement) => !requirement.blocked,
  ).length;

  return {
    blocked: completed < requirements.length,
    completed,
    requirements,
    total: requirements.length,
  };
}

export function buildRevocationLedgerView(input: {
  decisionView: DecisionCardViewModel | null | undefined;
  governanceIssues: GovernanceIssueView[];
  runId: string;
}): RevocationLedgerView {
  const revocationIssues = issuesMatching(
    input.governanceIssues,
    /revok|supersed|replac|withdraw|retir|void/i,
  );
  const blocking = revocationIssues.some(isBlockingIssue);
  const primaryIssue = revocationIssues[0];
  const raw = primaryIssue?.raw ?? {};
  const generatedAt =
    input.decisionView?.generatedAt ?? "1970-01-01T00:00:00.000Z";
  const knownAt =
    stringValue(raw.known_at) ??
    stringValue(raw.timestamp) ??
    stringValue(raw.created_at) ??
    generatedAt;
  const validAt = stringValue(raw.valid_at) ?? generatedAt;
  const policyRef = safePublicRef(
    stringValue(raw.policy_ref) ??
      stringValue(raw.policy_version) ??
      `policy:${input.decisionView?.runId ?? input.runId}`,
    `policy:${input.runId}`,
  );
  const predecessorRef = safePublicRef(
    stringValue(raw.predecessor_policy) ?? `${policyRef}:predecessor`,
    `${policyRef}:predecessor`,
  );
  const successorRef = safePublicRef(
    stringValue(raw.successor_policy) ?? `${policyRef}:successor`,
    `${policyRef}:successor`,
  );
  const currentStatus: RevocationLedgerView["currentStatus"] =
    primaryIssue && /revok|withdraw|retir|void/i.test(issueText(primaryIssue))
      ? "revoked"
      : blocking
        ? "superseded"
        : "active";
  const impactedRunsRaw = Array.isArray(raw.impacted_runs)
    ? raw.impacted_runs
    : [];
  const impactedRuns = impactedRunsRaw
    .map((item, index) => safePublicRef(stringValue(item), `run:${index + 1}`))
    .filter((item) => item.length > 0);

  return {
    blocked: blocking,
    chain: [
      {
        knownAt,
        policyRef: predecessorRef,
        reason: "phase34.revocation.reason.predecessor",
        relation: "predecessor",
        status: blocking ? "revoked" : "active",
        validAt,
      },
      {
        knownAt,
        policyRef,
        reason:
          currentStatus === "revoked"
            ? "phase34.revocation.reason.revoked"
            : blocking
              ? "phase34.revocation.reason.superseded"
              : "phase34.revocation.reason.current",
        relation: "current",
        status: currentStatus,
        validAt,
      },
      {
        knownAt,
        policyRef: successorRef,
        reason: blocking
          ? "phase34.revocation.reason.replacement"
          : "phase34.revocation.reason.none",
        relation: "successor",
        status: blocking ? "replacement" : "active",
        validAt,
      },
    ],
    currentStatus,
    impactedRuns: blocking
      ? impactedRuns.length > 0
        ? impactedRuns
        : [input.runId]
      : [],
  };
}

function block(input: {
  detailKey: string;
  kind: ApprovalBlockKind;
  runId: string;
  targetRef: string;
}): ApprovalBlock {
  return {
    auditRef: `approval-block:${input.runId}:${input.kind}:${input.targetRef}`,
    detailKey: input.detailKey,
    id: `${input.kind}:${input.targetRef}`,
    kind: input.kind,
    severity: "block",
    targetRef: input.targetRef,
  };
}

export function buildPublicSectorReadinessSnapshot(input: {
  decisionView: DecisionCardViewModel | null | undefined;
  disputes?: DisputeRecord[];
  evidenceContext?: RunEvidenceContext | null;
  governanceIssues?: GovernanceIssueView[];
  lens?: StakeholderLens;
  now?: string;
  reviewState?: ReviewAttentionState;
  runId: string;
}): PublicSectorReadinessSnapshot {
  const governanceIssues = input.governanceIssues ?? [];
  const reviewState = input.reviewState ?? createDefaultReviewAttentionState();
  const now = input.now ?? new Date().toISOString();
  const decisionHash = buildDecisionHash({
    decisionView: input.decisionView,
    evidenceContext: input.evidenceContext,
    governanceIssues,
  });
  const fairness = buildFairnessAuditView({
    decisionView: input.decisionView,
    governanceIssues,
  });
  const harm = buildHarmAssessmentView({
    decisionView: input.decisionView,
    governanceIssues,
    reviewState,
  });
  const embargo = buildEmbargoOverlayView({
    evidenceContext: input.evidenceContext,
    governanceIssues,
    now,
    runId: input.runId,
  });
  const slowReview = buildSlowReviewView({
    now,
    reviewState,
    runId: input.runId,
  });
  const revocation = buildRevocationLedgerView({
    decisionView: input.decisionView,
    governanceIssues,
    runId: input.runId,
  });
  const openDisputes = (input.disputes ?? []).filter(
    (dispute) => dispute.status.label === "open",
  );
  const blocks = [
    ...(fairness.blocked && fairness.sentinel
      ? [
          block({
            detailKey: "phase34.blockers.fairness",
            kind: "fairness",
            runId: input.runId,
            targetRef: fairness.sentinel.groupLabel,
          }),
        ]
      : []),
    ...(harm.blocked
      ? [
          block({
            detailKey: "phase34.blockers.harm",
            kind: "harm",
            runId: input.runId,
            targetRef: harm.euAiAct.riskClass,
          }),
        ]
      : []),
    ...(openDisputes.length > 0
      ? [
          block({
            detailKey: "phase34.blockers.objection",
            kind: "objection",
            runId: input.runId,
            targetRef: openDisputes[0]?.id ?? "open-objection",
          }),
        ]
      : []),
    ...(embargo.blocked
      ? [
          block({
            detailKey: "phase34.blockers.embargo",
            kind: "embargo",
            runId: input.runId,
            targetRef: embargo.masks[0]?.reasonCode ?? "embargo",
          }),
        ]
      : []),
    ...(slowReview.blocked
      ? [
          block({
            detailKey: "phase34.blockers.slowReview",
            kind: "slow_review",
            runId: input.runId,
            targetRef: `${slowReview.completed}/${slowReview.total}`,
          }),
        ]
      : []),
    ...(revocation.blocked
      ? [
          block({
            detailKey: "phase34.blockers.revocation",
            kind: "revocation",
            runId: input.runId,
            targetRef: revocation.currentStatus,
          }),
        ]
      : []),
  ];

  return {
    approvalReady: blocks.length === 0,
    auditTrail: [
      ...blocks.map((item) => ({
        at: now,
        event: `approval.blocked.${item.kind}`,
        ref: item.auditRef,
      })),
      ...Object.values(reviewState.sections).flatMap((section) =>
        section.events.map((event) => ({
          at: event.at,
          event: `review.${event.event}`,
          ref: event.replayRef,
        })),
      ),
    ],
    blocks,
    decisionHash,
    embargo,
    fairness,
    harm,
    lens: buildLensProjection({
      decisionHash,
      lens: input.lens ?? "operator",
    }),
    objections: {
      blocked: openDisputes.length > 0,
      open: openDisputes,
      total: input.disputes?.length ?? 0,
    },
    revocation,
    slowReview,
  };
}
