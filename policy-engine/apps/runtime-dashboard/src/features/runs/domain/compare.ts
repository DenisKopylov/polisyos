import type { RunTimelinePayload, RunErrorsPayload } from "@/api/validators";
import type { GovernanceIssueView } from "@/shared/lib/domain/governance";
import type { RunDetailSummary } from "@/features/runs/routes/useRunDetailSummary";

type ComparisonRow = {
  label: string;
  base: string;
  target: string;
  delta: string;
};

export type AuditTrailSeverity = "fail" | "warn" | "info";

export type AuditTrailEntry = {
  id: string;
  severity: AuditTrailSeverity;
  source: "governance" | "runtime" | "timeline";
  title: string;
  body: string;
  timestamp: string | null;
};

export type RunReportSnapshot = {
  artifactRefs: RunDetailSummary["artifactRefs"];
  auditTrail: AuditTrailEntry[];
  blockerCount: number;
  decisionConfidence: string | null;
  decisionHeadline: string;
  decisionScore: number;
  governanceIssues: GovernanceIssueView[];
  impactRows: RunDetailSummary["impactRows"];
  mainUncertainty: string;
  primaryVerdict: string | null;
  runId: string | null;
  status: string | null;
  strongestEvidence: {
    body: string;
    provenance: string;
    title: string;
  };
  transportStatus: string;
};

export type RunDeckSnapshot = {
  close: {
    commentWindow: string;
    downstreamDependencies: string[];
    nextAction: string;
  };
  cover: {
    eyebrow: string;
    subtitle: string;
    title: string;
  };
  evidence: {
    body: string;
    provenance: string;
    quote: string;
    title: string;
  };
  metrics: {
    cards: Array<{
      label: string;
      tone: "neutral" | "ok" | "warn";
      value: string;
    }>;
    title: string;
  };
  report: RunReportSnapshot;
  tradeoff: {
    hold: string[];
    ratify: string[];
    title: string;
  };
  verdict: {
    blockers: string;
    confidence: string;
    headline: string;
    status: string;
    verdict: string;
  };
};

function humanizeToken(value: string | null | undefined) {
  if (!value) {
    return "Unknown";
  }
  return value
    .replace(/[_-]+/g, " ")
    .trim()
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "Unknown";
  }
  return `${Math.round(value * 100)}%`;
}

function formatScore(value: number) {
  return value.toFixed(2);
}

function pickStrongestEvidence(summary: RunDetailSummary) {
  if (summary.selectedPromotion) {
    return {
      body: `${humanizeToken(summary.selectedPromotion.datasetId)} is queued on ${humanizeToken(summary.selectedPromotion.sourceLane)} with ${formatPercent(summary.selectedPromotion.confidence)} confidence.`,
      provenance: `${summary.selectedPromotion.connectorId} / ${summary.selectedPromotion.promotionId}`,
      title: "Promotion lane signal",
    };
  }

  if (summary.selectedPlan) {
    return {
      body: `${humanizeToken(summary.selectedPlan.datasetId)} maps ${summary.selectedPlan.matchedNeedIds.length} needs through ${humanizeToken(summary.selectedPlan.sourceLane)}.`,
      provenance: `${summary.selectedPlan.connectorId} / ${summary.selectedPlan.planId}`,
      title: "Evidence plan match",
    };
  }

  if (summary.selectedNeed) {
    return {
      body: `${humanizeToken(summary.selectedNeed.metric)} spans ${summary.selectedNeed.timeStart} to ${summary.selectedNeed.timeEnd} at ${humanizeToken(summary.selectedNeed.granularity)} resolution.`,
      provenance: `Need ${summary.selectedNeed.needId}`,
      title: "Run-scoped need",
    };
  }

  return {
    body: "Runtime has not attached a specific promotion, plan, or need to this run yet.",
    provenance: "Run context",
    title: "Evidence pending",
  };
}

function resolvePrimaryVerdict(summary: RunDetailSummary) {
  return (
    summary.decisionView?.verdict ??
    summary.pipeline?.evaluator?.verdict ??
    summary.run?.status ??
    null
  );
}

function resolveDecisionConfidence(summary: RunDetailSummary) {
  return summary.decisionView?.confidence ?? null;
}

function resolveMainUncertainty(
  summary: RunDetailSummary,
  auditTrail: AuditTrailEntry[],
) {
  const primaryIssue = summary.primaryIssue?.message?.trim();
  if (primaryIssue) {
    return primaryIssue;
  }

  const flaggedEntry = auditTrail.find(
    (entry) => entry.severity === "fail" || entry.severity === "warn",
  );
  if (flaggedEntry) {
    return `${flaggedEntry.title}: ${flaggedEntry.body}`;
  }

  return "No blocking uncertainty was returned by runtime diagnostics.";
}

function buildDeckMetrics(report: RunReportSnapshot) {
  const impactCard =
    report.impactRows?.[0]?.display ??
    `${report.blockerCount > 0 ? "-" : "+"}${Math.round(report.decisionScore * 100)} bps`;

  return [
    {
      label: "Decision score",
      tone: report.decisionScore >= 0.7 ? ("ok" as const) : ("warn" as const),
      value: formatScore(report.decisionScore),
    },
    {
      label: "Blocker state",
      tone: report.blockerCount === 0 ? ("ok" as const) : ("warn" as const),
      value: String(report.blockerCount),
    },
    {
      label: "Impact delta",
      tone: "neutral" as const,
      value: impactCard,
    },
    {
      label: "Artifact continuity",
      tone: "neutral" as const,
      value: String(report.artifactRefs.length),
    },
  ];
}

function buildDownstreamDependencies(summary: RunDetailSummary) {
  const dependencies = [
    ...summary.artifactRefs.slice(0, 2).map((ref) => humanizeToken(ref.kind)),
    summary.selectedPromotion
      ? `${humanizeToken(summary.selectedPromotion.status)} promotion review`
      : null,
    summary.transportStatus ? humanizeToken(summary.transportStatus) : null,
  ].filter((value): value is string => Boolean(value));

  return dependencies.length > 0
    ? dependencies
    : ["No downstream dependency string was returned for this run."];
}

function severityRank(
  severity: GovernanceIssueView["severity"],
): AuditTrailSeverity {
  if (severity === "blocker") {
    return "fail";
  }
  if (severity === "warning") {
    return "warn";
  }
  return "info";
}

function stringifyDelta(baseValue: number, targetValue: number) {
  const delta = targetValue - baseValue;
  return `${delta >= 0 ? "+" : ""}${delta}`;
}

export function buildRunComparison(
  baseSummary: RunDetailSummary,
  targetSummary: RunDetailSummary,
): ComparisonRow[] {
  return [
    {
      label: "Decision score",
      base: baseSummary.decisionScore.toFixed(2),
      target: targetSummary.decisionScore.toFixed(2),
      delta: `${targetSummary.decisionScore >= baseSummary.decisionScore ? "+" : ""}${(targetSummary.decisionScore - baseSummary.decisionScore).toFixed(2)}`,
    },
    {
      label: "Governance blockers",
      base: String(baseSummary.blockerCount),
      target: String(targetSummary.blockerCount),
      delta: stringifyDelta(
        baseSummary.blockerCount,
        targetSummary.blockerCount,
      ),
    },
    {
      label: "Artifact refs",
      base: String(baseSummary.artifactRefs.length),
      target: String(targetSummary.artifactRefs.length),
      delta: stringifyDelta(
        baseSummary.artifactRefs.length,
        targetSummary.artifactRefs.length,
      ),
    },
    {
      label: "Evidence plans",
      base: String(baseSummary.evidenceContext?.fetchPlans.length ?? 0),
      target: String(targetSummary.evidenceContext?.fetchPlans.length ?? 0),
      delta: stringifyDelta(
        baseSummary.evidenceContext?.fetchPlans.length ?? 0,
        targetSummary.evidenceContext?.fetchPlans.length ?? 0,
      ),
    },
    {
      label: "Promotion candidates",
      base: String(
        baseSummary.evidenceContext?.promotionCandidates.length ?? 0,
      ),
      target: String(
        targetSummary.evidenceContext?.promotionCandidates.length ?? 0,
      ),
      delta: stringifyDelta(
        baseSummary.evidenceContext?.promotionCandidates.length ?? 0,
        targetSummary.evidenceContext?.promotionCandidates.length ?? 0,
      ),
    },
  ];
}

export function buildAuditTrail({
  errors,
  governanceIssues,
  timelineEvents,
}: {
  errors: RunErrorsPayload["errors"];
  governanceIssues: GovernanceIssueView[];
  timelineEvents: RunTimelinePayload["timeline"]["events"];
}): AuditTrailEntry[] {
  const governanceEntries = governanceIssues.map((issue, index) => ({
    id: `issue-${issue.code}-${index}`,
    severity: severityRank(issue.severity),
    source: "governance" as const,
    title: issue.message,
    body: issue.passId ?? issue.code,
    timestamp: null,
  }));

  const errorEntries = (errors ?? []).map((error, index) => ({
    id: `error-${error.code}-${index}`,
    severity: "fail" as const,
    source: "runtime" as const,
    title: error.message,
    body: error.node_alias
      ? `${error.source} · ${error.node_alias}`
      : error.source,
    timestamp: error.timestamp ?? null,
  }));

  const timelineEntries = (timelineEvents ?? []).map((event) => ({
    id: `timeline-${event.index}-${event.event}`,
    severity: "info" as const,
    source: "timeline" as const,
    title: event.event,
    body: event.phase,
    timestamp: event.timestamp ?? null,
  }));

  return [...errorEntries, ...governanceEntries, ...timelineEntries].sort(
    (left, right) => {
      if (!left.timestamp && !right.timestamp) {
        return 0;
      }
      if (!left.timestamp) {
        return 1;
      }
      if (!right.timestamp) {
        return -1;
      }
      return right.timestamp.localeCompare(left.timestamp);
    },
  );
}

export function buildRunReportSnapshot(
  summary: RunDetailSummary,
  auditTrail: AuditTrailEntry[],
): RunReportSnapshot {
  const strongestEvidence = pickStrongestEvidence(summary);

  return {
    artifactRefs: summary.artifactRefs,
    auditTrail,
    blockerCount: summary.blockerCount,
    decisionConfidence: resolveDecisionConfidence(summary),
    decisionHeadline: summary.decisionHeadline,
    decisionScore: summary.decisionScore,
    governanceIssues: summary.governanceIssues,
    impactRows: summary.impactRows ?? [],
    mainUncertainty: resolveMainUncertainty(summary, auditTrail),
    primaryVerdict: resolvePrimaryVerdict(summary),
    runId: summary.run?.run_id ?? null,
    status: summary.run?.status ?? null,
    strongestEvidence,
    transportStatus: summary.transportStatus,
  };
}

export function buildRunDeckSnapshot(
  summary: RunDetailSummary,
  report: RunReportSnapshot,
): RunDeckSnapshot {
  const evidencePlanCount = summary.evidenceContext?.fetchPlans.length ?? 0;
  const promotionCount =
    summary.evidenceContext?.promotionCandidates.length ?? 0;
  const verdictLabel = humanizeToken(report.primaryVerdict);
  const confidenceLabel = humanizeToken(report.decisionConfidence);
  const blockersLabel =
    report.blockerCount === 0
      ? "No active blockers in governance review."
      : `${report.blockerCount} blockers still need operator attention.`;

  return {
    close: {
      commentWindow:
        report.blockerCount === 0
          ? "Open a stakeholder comment window before ratification closes."
          : "Keep the comment window open until blockers are resolved or ratified with conditions.",
      downstreamDependencies: buildDownstreamDependencies(summary),
      nextAction:
        report.blockerCount === 0
          ? "Ratify the run packet and circulate the deck."
          : "Hold the run packet and route blockers to review owners.",
    },
    cover: {
      eyebrow: "Runtime-integrated deck",
      subtitle: `${humanizeToken(summary.run?.source_kind)} run packet · ${humanizeToken(report.status)}`,
      title: report.runId
        ? `Atlas decision deck for ${report.runId}`
        : "Atlas decision deck",
    },
    evidence: {
      body: `Evidence bundle includes ${evidencePlanCount} plans, ${promotionCount} promotion candidates, and ${report.artifactRefs.length} linked artifacts.`,
      provenance: report.strongestEvidence.provenance,
      quote: report.strongestEvidence.body,
      title: report.strongestEvidence.title,
    },
    metrics: {
      cards: buildDeckMetrics(report),
      title: "Rollout impact and operating posture",
    },
    report,
    tradeoff: {
      hold: [
        blockersLabel,
        `Main uncertainty: ${report.mainUncertainty}`,
        `Transport posture remains ${humanizeToken(report.transportStatus)}.`,
      ],
      ratify: [
        `Decision score is ${formatScore(report.decisionScore)} with ${confidenceLabel} confidence.`,
        `${evidencePlanCount} evidence plans and ${promotionCount} promotion candidates are already in context.`,
        `Artifact continuity is preserved across ${report.artifactRefs.length} refs.`,
      ],
      title: "Ratify now versus hold for review",
    },
    verdict: {
      blockers: blockersLabel,
      confidence: confidenceLabel,
      headline: report.decisionHeadline,
      status: humanizeToken(report.status),
      verdict: verdictLabel,
    },
  };
}
