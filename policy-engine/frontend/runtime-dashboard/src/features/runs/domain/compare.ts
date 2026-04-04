import type { RunTimelinePayload, RunErrorsPayload } from "@/api/validators";
import type { GovernanceIssueView } from "@/lib/domain/governance";
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
) {
  return {
    runId: summary.run?.run_id ?? null,
    status: summary.run?.status ?? null,
    decisionHeadline: summary.decisionHeadline,
    decisionScore: summary.decisionScore,
    blockerCount: summary.blockerCount,
    transportStatus: summary.transportStatus,
    artifactRefs: summary.artifactRefs,
    governanceIssues: summary.governanceIssues,
    evidence: summary.evidenceContext,
    auditTrail,
  };
}
