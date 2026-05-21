import { useControlJobStatus } from "@/api/hooks/useControlJobStatus";
import type { components } from "@/api/types";
import {
  OperatorDiagnosticPanel,
  type OperatorDiagnosticView,
} from "@/shared/ui/OperatorDiagnosticPanel";
import { useOptionalI18n } from "@/shared/i18n/LocaleProvider";
import { Badge } from "@/shared/ui";
import type { BadgeKind } from "@/shared/ui/Badge";

type ControlFailureEnvelope = components["schemas"]["ControlFailureEnvelope"];
type ControlJobResponse = components["schemas"]["ControlJobResponse"];

type ControlFailurePanelProps = {
  failure?: ControlFailureEnvelope | null;
  job?: ControlJobResponse | null;
  jobId?: string | null;
};

type ScientistArtifactRef = {
  artifactId: string;
  direction: string | null;
  kind: string | null;
};

type ScientistWorkflowProgress = {
  currentEvent: string | null;
  currentNodeAlias: string | null;
  currentPhase: string | null;
  eventCount: number | null;
  latestArtifactRefs: ScientistArtifactRef[];
  updatedAt: string | null;
};

type ApprovalGateIssue = {
  name: string;
  code: string | null;
  status: string;
  layer: string;
  phase: string | null;
  message: string | null;
  nextAction: string | null;
  evidenceRef: string | null;
};

type HumanReviewCalibrationSummary = {
  agreementRate: number | null;
  overrideRate: number | null;
  reportRef: string | null;
  reviewerBurdenMinutes: number | null;
  signalCodes: string[];
  status: string | null;
  unresolvedDisagreementCount: number | null;
};

type PerformanceBudgetIssue = {
  budgetMs: number | null;
  classification: string | null;
  layer: string;
  nextAction: string | null;
  observedValueMs: number | null;
  phase: string;
  status: string;
};

type ApprovalReadiness = {
  approvalPacketRef: string | null;
  eligible: boolean | null;
  evidenceBundlePath: string | null;
  executionStatus: string | null;
  humanReviewCalibration: HumanReviewCalibrationSummary | null;
  missingOverride: boolean | null;
  nextAction: string | null;
  overrideDecisionRef: string | null;
  overridePacketRef: string | null;
  overrideStatus: string | null;
  performanceStatus: string | null;
  projectionAuthority: string | null;
  projectionSource: string | null;
  qualityStatus: string | null;
  reasons: string[];
  requiresOverride: boolean | null;
  runtimeState: string | null;
  scorecardRef: string | null;
  state: string | null;
  nextDiagnosticCommands: string[];
};

function stringFromUnknown(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function recordFromUnknown(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : null;
}

function numberFromUnknown(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function booleanFromUnknown(value: unknown): boolean | null {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["true", "yes", "1"].includes(normalized)) {
      return true;
    }
    if (["false", "no", "0"].includes(normalized)) {
      return false;
    }
  }
  return null;
}

function stringsFromUnknown(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => stringFromUnknown(item))
    .filter((item): item is string => item !== null);
}

function arrayFromUnknown(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function hasSecretLikeRefSegment(value: string): boolean {
  return (
    /\bsk-(?:live|test|proj|[a-z0-9])/i.test(value) ||
    /(?:^|[/_.-])(access[_-]?token|api[_-]?key|bearer|credential|password|refresh[_-]?token|secret|signature|token)(?:$|[/_.:-])/i.test(
      value,
    )
  );
}

function sanitizedRefFromUnknown(value: unknown): string | null {
  const raw = stringFromUnknown(value);
  if (!raw) {
    return null;
  }
  const sanitized = raw.split(/[?#]/, 1)[0]?.trim();
  if (!sanitized || hasSecretLikeRefSegment(sanitized)) {
    return null;
  }
  return sanitized;
}

function firstSanitizedRef(...values: unknown[]): string | null {
  for (const value of values) {
    const ref = sanitizedRefFromUnknown(value);
    if (ref) {
      return ref;
    }
  }
  return null;
}

function scientistWorkflowFromJob(
  job: ControlJobResponse | null | undefined,
): ScientistWorkflowProgress | null {
  const progress = recordFromUnknown(job?.progress);
  const workflow = recordFromUnknown(progress?.scientist_workflow);
  if (!workflow) {
    return null;
  }
  const latestEvent = recordFromUnknown(workflow.latest_event);
  const rawRefs = Array.isArray(workflow.latest_artifact_refs)
    ? workflow.latest_artifact_refs
    : [];
  const latestArtifactRefs = rawRefs
    .map((item) => recordFromUnknown(item))
    .filter((item): item is Record<string, unknown> => item !== null)
    .map((item) => ({
      artifactId: stringFromUnknown(item.artifact_id),
      direction: stringFromUnknown(item.direction),
      kind: stringFromUnknown(item.kind),
    }))
    .filter((item): item is ScientistArtifactRef => item.artifactId !== null);

  return {
    currentEvent:
      stringFromUnknown(workflow.current_event) ??
      stringFromUnknown(latestEvent?.event),
    currentNodeAlias: stringFromUnknown(workflow.current_node_alias),
    currentPhase:
      stringFromUnknown(workflow.current_phase) ??
      stringFromUnknown(latestEvent?.phase),
    eventCount: numberFromUnknown(workflow.event_count),
    latestArtifactRefs,
    updatedAt: stringFromUnknown(workflow.updated_at),
  };
}

function evidencePathFromJob(
  job: components["schemas"]["ControlJobResponse"] | undefined,
  failure: ControlFailureEnvelope | null,
): string | null {
  const progress = job?.progress;
  const details =
    progress && typeof progress === "object" ? progress.details : undefined;
  const artifactRefs = failure?.artifact_refs;
  return (
    sanitizedRefFromUnknown(
      details && typeof details === "object"
        ? (details as Record<string, unknown>).evidence_bundle_path
        : null,
    ) ??
    sanitizedRefFromUnknown(
      progress && typeof progress === "object"
        ? progress.evidence_bundle_path
        : null,
    ) ??
    sanitizedRefFromUnknown(artifactRefs?.evidence_bundle_path) ??
    sanitizedRefFromUnknown(artifactRefs?.provider_preflight_ref)
  );
}

function qualityBadgeKind(status: string | null | undefined): BadgeKind {
  if (status === "fail") {
    return "fail";
  }
  if (status === "warn") {
    return "warn";
  }
  if (status === "pass") {
    return "ok";
  }
  return "neutral";
}

function approvalBadgeKind(readiness: ApprovalReadiness): BadgeKind {
  if (readiness.eligible === true || readiness.state === "approval_ready") {
    return "ok";
  }
  if (readiness.state?.includes("warn")) {
    return "warn";
  }
  if (readiness.state) {
    return "fail";
  }
  return "neutral";
}

function gateBadgeKind(status: string | null | undefined): BadgeKind {
  if (status === "fail") {
    return "fail";
  }
  if (status === "warn") {
    return "warn";
  }
  return "neutral";
}

function performanceIssueBadgeKind(
  status: string | null | undefined,
): BadgeKind {
  if (status === "fail" || status === "failed") {
    return "fail";
  }
  if (status === "over_budget" || status === "warn" || status === "warning") {
    return "warn";
  }
  return "neutral";
}

function calibrationBadgeKind(
  status: string | null | undefined,
  signalCodes: string[],
): BadgeKind {
  if (
    status === "fail" ||
    signalCodes.some((code) => code.includes("_fail_"))
  ) {
    return "fail";
  }
  if (status === "warn" || signalCodes.length > 0) {
    return "warn";
  }
  if (status === "pass") {
    return "ok";
  }
  return "neutral";
}

function formatMilliseconds(value: number | null): string {
  if (value === null) {
    return "unknown";
  }
  return `${Math.round(value)}ms`;
}

function formatPercent(value: number | null): string | null {
  if (value === null) {
    return null;
  }
  return `${Math.round(value * 100)}%`;
}

function formatMinutes(value: number | null): string | null {
  if (value === null) {
    return null;
  }
  return `${Math.round(value)}m`;
}

function shouldRenderQuality(job: ControlJobResponse | null | undefined) {
  return Boolean(
    job?.quality_status &&
    job.quality_status !== "pass" &&
    (job.state === "completed" || job.execution_status === "completed"),
  );
}

function performanceBudgetIssuesFromJob(
  job: ControlJobResponse | null | undefined,
): PerformanceBudgetIssue[] {
  const progress = recordFromUnknown(job?.progress);
  const scorecard = qualityScorecardFromJob(job);
  const scorecardCanaryBudget = recordFromUnknown(
    scorecard?.canary_performance_budget,
  );
  const scorecardRunSummary = recordFromUnknown(
    scorecard?.run_performance_summary,
  );
  const progressCanaryBudget = recordFromUnknown(
    progress?.canary_performance_budget,
  );
  const progressRunSummary = recordFromUnknown(
    progress?.run_performance_summary,
  );
  const progressResilience = recordFromUnknown(progress?.runtime_resilience);
  const sources = [
    scorecard?.performance_budget_issues,
    scorecardCanaryBudget?.phase_budgets,
    scorecardRunSummary?.phase_budgets,
    progressCanaryBudget?.phase_budgets,
    progressRunSummary?.phase_budgets,
    progressResilience?.operator_findings,
  ];
  const issues = new Map<string, PerformanceBudgetIssue>();

  for (const source of sources) {
    for (const rawIssue of arrayFromUnknown(source)) {
      const issue = performanceBudgetIssueFromUnknown(rawIssue);
      if (!issue) {
        continue;
      }
      issues.set(`${issue.layer}:${issue.phase}:${issue.status}`, issue);
    }
  }

  return Array.from(issues.values());
}

function performanceBudgetIssueFromUnknown(
  value: unknown,
): PerformanceBudgetIssue | null {
  const record = recordFromUnknown(value);
  if (!record) {
    return null;
  }
  const phase = stringFromUnknown(record.phase);
  if (!phase) {
    return null;
  }
  const observedValueMs =
    numberFromUnknown(record.observed_value_ms) ??
    numberFromUnknown(record.observed_duration_ms) ??
    numberFromUnknown(record.duration_ms);
  const budgetMs = numberFromUnknown(record.budget_ms);
  const rawStatus =
    stringFromUnknown(record.status) ??
    (observedValueMs !== null && budgetMs !== null && observedValueMs > budgetMs
      ? "over_budget"
      : null);
  const status = rawStatus?.toLowerCase() ?? "warn";
  const isBudgetIssue =
    ["over_budget", "warn", "warning", "fail", "failed"].includes(status) ||
    (observedValueMs !== null &&
      budgetMs !== null &&
      observedValueMs > budgetMs);
  if (!isBudgetIssue) {
    return null;
  }
  return {
    budgetMs,
    classification: stringFromUnknown(record.classification),
    layer: stringFromUnknown(record.layer) ?? "runtime",
    nextAction:
      stringFromUnknown(record.next_action) ??
      stringFromUnknown(record.nextAction) ??
      stringFromUnknown(record.message),
    observedValueMs,
    phase,
    status,
  };
}

function qualityScorecardFromJob(
  job: ControlJobResponse | null | undefined,
): Record<string, unknown> | null {
  const progress = recordFromUnknown(job?.progress);
  if (!progress) {
    return null;
  }
  const nestedScorecard =
    recordFromUnknown(progress.quality_scorecard) ??
    recordFromUnknown(progress.quality);
  if (nestedScorecard) {
    return nestedScorecard;
  }
  if (
    "approval_state" in progress ||
    "approval_eligibility" in progress ||
    "approval_packet_ref" in progress ||
    "override_evidence" in progress
  ) {
    return progress;
  }
  return null;
}

function humanReviewCalibrationFromScorecard(
  scorecard: Record<string, unknown>,
  evidenceRefs: Record<string, unknown> | null,
): HumanReviewCalibrationSummary | null {
  const rawCalibration =
    recordFromUnknown(scorecard.human_review_calibration) ??
    recordFromUnknown(scorecard.human_review_calibration_report) ??
    recordFromUnknown(scorecard.reviewer_calibration);
  const summary = recordFromUnknown(rawCalibration?.summary);
  const reviewerBurden = recordFromUnknown(rawCalibration?.reviewer_burden);
  const rawSignals = Array.isArray(rawCalibration?.quality_signals)
    ? rawCalibration.quality_signals
    : [];
  const signalCodes = rawSignals
    .map((signal) => recordFromUnknown(signal))
    .map((signal) => stringFromUnknown(signal?.code))
    .filter((code): code is string => code !== null);
  const reportRef = firstSanitizedRef(
    rawCalibration?.human_review_calibration_report_ref,
    rawCalibration?.report_ref,
    scorecard.human_review_calibration_report_ref,
    evidenceRefs?.human_review_calibration_report,
    evidenceRefs?.human_review_calibration_report_ref,
  );

  const calibration: HumanReviewCalibrationSummary = {
    agreementRate: numberFromUnknown(summary?.agreement_rate),
    overrideRate: numberFromUnknown(summary?.override_rate),
    reportRef,
    reviewerBurdenMinutes: numberFromUnknown(reviewerBurden?.total_minutes),
    signalCodes,
    status: stringFromUnknown(rawCalibration?.status),
    unresolvedDisagreementCount: numberFromUnknown(
      summary?.unresolved_disagreement_count,
    ),
  };
  if (
    calibration.status ||
    calibration.reportRef ||
    calibration.agreementRate !== null ||
    calibration.overrideRate !== null ||
    calibration.reviewerBurdenMinutes !== null ||
    calibration.unresolvedDisagreementCount !== null ||
    calibration.signalCodes.length > 0
  ) {
    return calibration;
  }
  return null;
}

function approvalReadinessFromJob(
  job: ControlJobResponse | null | undefined,
): ApprovalReadiness | null {
  const scorecard = qualityScorecardFromJob(job);
  const jobRecord = recordFromUnknown(job);
  const approvalProjection = recordFromUnknown(jobRecord?.approval_projection);
  const projectionSourceRecord = recordFromUnknown(
    jobRecord?.projection_source,
  );
  const topLevelCommands = stringsFromUnknown(
    jobRecord?.next_diagnostic_commands,
  );
  const authorityGaps = arrayFromUnknown(jobRecord?.unresolved_authority_gaps)
    .map((gap) => recordFromUnknown(gap))
    .filter((gap): gap is Record<string, unknown> => gap !== null);
  const hasTopLevelProjection =
    approvalProjection !== null ||
    projectionSourceRecord !== null ||
    stringFromUnknown(jobRecord?.authoritative_scorecard_ref) !== null ||
    authorityGaps.length > 0 ||
    topLevelCommands.length > 0;
  if (!scorecard && !hasTopLevelProjection) {
    return null;
  }
  const scorecardRecord = scorecard ?? {};
  const eligibility = recordFromUnknown(scorecardRecord.approval_eligibility);
  const evidenceRefs = recordFromUnknown(scorecardRecord.evidence_refs);
  const overrideEvidence = recordFromUnknown(scorecardRecord.override_evidence);
  const approvalPacket = recordFromUnknown(scorecardRecord.approval_packet);
  const approvalReady = booleanFromUnknown(scorecardRecord.approval_ready);
  const state =
    stringFromUnknown(approvalProjection?.state) ??
    stringFromUnknown(scorecardRecord.approval_state) ??
    stringFromUnknown(eligibility?.state) ??
    (approvalReady === true
      ? "approval_ready"
      : approvalReady === false
        ? "not_ready"
        : null);
  const eligible =
    booleanFromUnknown(approvalProjection?.eligible) ??
    booleanFromUnknown(eligibility?.eligible) ??
    approvalReady ??
    (state ? state === "approval_ready" : null);
  const gapCommands = authorityGaps
    .map((gap) => stringFromUnknown(gap.next_diagnostic_command))
    .filter((command): command is string => command !== null);
  const gapReasons = authorityGaps
    .map((gap) => stringFromUnknown(gap.code))
    .filter((code): code is string => code !== null);
  const projectionSource = stringFromUnknown(
    projectionSourceRecord?.source_surface,
  );
  const projectionAuthority =
    stringFromUnknown(projectionSourceRecord?.authority_level) ??
    stringFromUnknown(projectionSourceRecord?.projection_policy);
  const seriousProfile = ["governed", "production", "research"].includes(
    job?.effective_execution_profile ?? "",
  );
  const failedSeriousProjection =
    seriousProfile &&
    (job?.quality_status === "fail" ||
      (job?.blocking_quality_failures?.length ?? 0) > 0 ||
      authorityGaps.length > 0);
  const failClosedEligible = failedSeriousProjection ? false : eligible;
  const failClosedState =
    failedSeriousProjection && (!state || state === "approval_ready")
      ? "quality_failed"
      : state;
  const reasons = [
    ...(stringsFromUnknown(approvalProjection?.reasons).length > 0
      ? stringsFromUnknown(approvalProjection?.reasons)
      : stringsFromUnknown(eligibility?.reasons).length > 0
        ? stringsFromUnknown(eligibility?.reasons)
        : stringsFromUnknown(scorecardRecord.approval_reasons)),
    ...gapReasons,
  ];
  if (
    failedSeriousProjection &&
    job?.quality_status === "fail" &&
    reasons.length === 0
  ) {
    reasons.push("quality_not_passing");
  }

  const readiness: ApprovalReadiness = {
    approvalPacketRef: firstSanitizedRef(
      scorecardRecord.approval_packet_ref,
      approvalPacket?.ref,
      approvalPacket?.artifact_ref,
      approvalPacket?.packet_ref,
      evidenceRefs?.approval_packet,
      evidenceRefs?.approval_packet_ref,
    ),
    eligible: failClosedEligible,
    evidenceBundlePath: firstSanitizedRef(
      job?.quality_evidence_bundle_path,
      scorecardRecord.quality_evidence_bundle_path,
      scorecardRecord.evidence_bundle_path,
      evidenceRefs?.evidence_bundle,
      evidenceRefs?.quality_evidence_bundle,
    ),
    executionStatus:
      stringFromUnknown(eligibility?.execution_status) ??
      stringFromUnknown(scorecardRecord.execution_status) ??
      job?.execution_status ??
      job?.state ??
      null,
    humanReviewCalibration: humanReviewCalibrationFromScorecard(
      scorecardRecord,
      evidenceRefs,
    ),
    missingOverride: booleanFromUnknown(eligibility?.missing_override),
    nextAction:
      stringFromUnknown(scorecardRecord.approval_next_action) ??
      stringFromUnknown(eligibility?.next_action),
    overrideDecisionRef: firstSanitizedRef(
      overrideEvidence?.decision_ref,
      scorecardRecord.override_decision_ref,
      scorecardRecord.approval_override_ref,
      scorecardRecord.override_ref,
      evidenceRefs?.override_decision,
      evidenceRefs?.approval_override,
    ),
    overridePacketRef: firstSanitizedRef(
      overrideEvidence?.packet_ref,
      scorecardRecord.override_packet_ref,
      evidenceRefs?.override_packet,
    ),
    overrideStatus: stringFromUnknown(overrideEvidence?.status),
    performanceStatus:
      stringFromUnknown(eligibility?.performance_status) ??
      stringFromUnknown(scorecardRecord.performance_status),
    projectionAuthority,
    projectionSource,
    qualityStatus:
      stringFromUnknown(eligibility?.quality_status) ??
      stringFromUnknown(scorecardRecord.quality_status) ??
      job?.quality_status ??
      null,
    reasons: [...new Set(reasons)],
    requiresOverride: booleanFromUnknown(eligibility?.requires_override),
    runtimeState:
      stringFromUnknown(jobRecord?.runtime_state) ??
      job?.execution_status ??
      job?.state ??
      null,
    scorecardRef: firstSanitizedRef(
      jobRecord?.authoritative_scorecard_ref,
      job?.quality_scorecard_ref,
      scorecardRecord.quality_scorecard_ref,
      scorecardRecord.scorecard_ref,
      evidenceRefs?.quality_scorecard,
    ),
    state: failClosedState,
    nextDiagnosticCommands: [...new Set([...topLevelCommands, ...gapCommands])],
  };

  if (
    readiness.state ||
    readiness.eligible !== null ||
    readiness.approvalPacketRef ||
    readiness.overrideDecisionRef ||
    readiness.overridePacketRef
  ) {
    return readiness;
  }
  return null;
}

function shouldRenderApproval(
  job: ControlJobResponse | null | undefined,
  readiness: ApprovalReadiness | null,
) {
  return Boolean(
    readiness &&
    (job?.state === "completed" || job?.execution_status === "completed"),
  );
}

function approvalGateIssuesFromJob(
  job: ControlJobResponse | null | undefined,
): ApprovalGateIssue[] {
  const gates = job?.quality_gates ?? [];
  const gateIssues = gates
    .filter((gate) => gate.status === "fail" || gate.status === "warn")
    .map((gate) => ({
      name: gate.name,
      code: gate.code ?? null,
      status: gate.status,
      layer: gate.layer,
      phase: gate.phase ?? null,
      message: gate.message ?? null,
      nextAction: gate.next_action ?? null,
      evidenceRef: sanitizedRefFromUnknown(gate.evidence_ref),
    }));
  if (gateIssues.length > 0) {
    return gateIssues;
  }
  return (job?.blocking_quality_failures ?? []).map((failure) => ({
    name: failure.gate,
    code: failure.code ?? null,
    status: "fail",
    layer: failure.layer,
    phase: failure.phase ?? null,
    message: failure.message ?? null,
    nextAction: failure.next_action ?? null,
    evidenceRef: sanitizedRefFromUnknown(failure.evidence_ref),
  }));
}

function gateIssuesByLayer(issues: ApprovalGateIssue[]) {
  const groups = new Map<string, ApprovalGateIssue[]>();
  for (const issue of issues) {
    const layerIssues = groups.get(issue.layer) ?? [];
    layerIssues.push(issue);
    groups.set(issue.layer, layerIssues);
  }
  return Array.from(groups, ([layer, layerIssues]) => ({
    issues: layerIssues,
    layer,
  }));
}

function approvalNextAction(
  readiness: ApprovalReadiness,
  issues: ApprovalGateIssue[],
) {
  if (readiness.nextAction) {
    return readiness.nextAction;
  }
  const issueAction = issues.find(
    (issue) => issue.code === readiness.reasons[0],
  );
  if (issueAction?.nextAction) {
    return issueAction.nextAction;
  }
  if (issueAction?.message) {
    return issueAction.message;
  }
  const firstBlockingFailure = issues.find((issue) => issue.status === "fail");
  if (firstBlockingFailure?.nextAction) {
    return firstBlockingFailure.nextAction;
  }
  if (firstBlockingFailure?.message) {
    return firstBlockingFailure.message;
  }
  return null;
}

function operatorDiagnosticFromJob(
  job: ControlJobResponse | null | undefined,
  failure: ControlFailureEnvelope | null,
): OperatorDiagnosticView | null {
  if (failure?.operator_diagnostic) {
    return failure.operator_diagnostic;
  }
  if (job?.operator_diagnostic) {
    return job.operator_diagnostic;
  }
  const blockingFailure = job?.blocking_quality_failures?.find(
    (item) => item.operator_diagnostic,
  );
  if (blockingFailure?.operator_diagnostic) {
    return blockingFailure.operator_diagnostic;
  }
  const blockingGate = job?.quality_gates?.find(
    (item) => item.operator_diagnostic,
  );
  return blockingGate?.operator_diagnostic ?? null;
}

function shouldRenderScientistProgress(
  job: ControlJobResponse | null | undefined,
  progress: ScientistWorkflowProgress | null,
) {
  return Boolean(
    progress &&
    (job?.state === "pending" ||
      job?.state === "running" ||
      job?.execution_status === "running"),
  );
}

function ControlApprovalPanel({
  gateIssues,
  performanceIssues,
  readiness,
}: {
  gateIssues: ApprovalGateIssue[];
  performanceIssues: PerformanceBudgetIssue[];
  readiness: ApprovalReadiness;
}) {
  const { t } = useOptionalI18n();
  const groupedIssues = gateIssuesByLayer(gateIssues);
  const calibration = readiness.humanReviewCalibration;
  const nextAction =
    approvalNextAction(readiness, gateIssues) ??
    (readiness.missingOverride
      ? t("controlJob.approvalNeedsOverride")
      : t("controlJob.approvalNeedsReview"));
  return (
    <section
      aria-label={t("controlJob.approvalAriaLabel")}
      className="border-l-2 border-[var(--color-status-rejected)] bg-[color-mix(in_srgb,var(--color-status-rejected)_6%,transparent)] px-3 py-2 text-sm"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge kind={approvalBadgeKind(readiness)}>
          {t("controlJob.approvalBadge", {
            status: readiness.state ?? "unknown",
          })}
        </Badge>
        <Badge kind={readiness.eligible ? "ok" : "warn"}>
          {readiness.eligible
            ? t("controlJob.approvalReady")
            : t("controlJob.notApprovalReady")}
        </Badge>
        {readiness.requiresOverride ? (
          <Badge kind="warn">{t("controlJob.overrideRequired")}</Badge>
        ) : null}
        {calibration ? (
          <Badge
            kind={calibrationBadgeKind(
              calibration.status,
              calibration.signalCodes,
            )}
          >
            {t("controlJob.humanReviewBadge", {
              status: calibration.status ?? "unknown",
            })}
          </Badge>
        ) : null}
        {calibration?.agreementRate !== null &&
        calibration?.agreementRate !== undefined ? (
          <Badge kind="neutral">
            {t("controlJob.humanReviewAgreement", {
              value: formatPercent(calibration.agreementRate) ?? "",
            })}
          </Badge>
        ) : null}
        {calibration?.overrideRate !== null &&
        calibration?.overrideRate !== undefined ? (
          <Badge kind="neutral">
            {t("controlJob.humanReviewOverrideRate", {
              value: formatPercent(calibration.overrideRate) ?? "",
            })}
          </Badge>
        ) : null}
        {calibration?.reviewerBurdenMinutes !== null &&
        calibration?.reviewerBurdenMinutes !== undefined ? (
          <Badge kind="neutral">
            {t("controlJob.humanReviewBurden", {
              value: formatMinutes(calibration.reviewerBurdenMinutes) ?? "",
            })}
          </Badge>
        ) : null}
        {calibration?.unresolvedDisagreementCount !== null &&
        calibration?.unresolvedDisagreementCount !== undefined ? (
          <Badge kind="warn">
            {t("controlJob.humanReviewUnresolved", {
              count: String(calibration.unresolvedDisagreementCount),
            })}
          </Badge>
        ) : null}
      </div>
      <dl className="mt-2 grid gap-1 text-[13px] sm:grid-cols-2">
        {readiness.executionStatus ? (
          <div>
            <dt className="font-semibold text-[var(--slate)]">
              {t("controlJob.execution")}
            </dt>
            <dd>{readiness.executionStatus}</dd>
          </div>
        ) : null}
        {readiness.qualityStatus ? (
          <div>
            <dt className="font-semibold text-[var(--slate)]">
              {t("controlJob.quality")}
            </dt>
            <dd>{readiness.qualityStatus}</dd>
          </div>
        ) : null}
        {readiness.performanceStatus ? (
          <div>
            <dt className="font-semibold text-[var(--slate)]">
              {t("controlJob.performance")}
            </dt>
            <dd>{readiness.performanceStatus}</dd>
          </div>
        ) : null}
        {readiness.reasons.length > 0 ? (
          <div>
            <dt className="font-semibold text-[var(--slate)]">
              {t("controlJob.reason")}
            </dt>
            <dd className="flex flex-wrap gap-1 break-words">
              {readiness.reasons.map((reason) => (
                <span key={reason}>{reason}</span>
              ))}
            </dd>
          </div>
        ) : null}
      </dl>
      {readiness.projectionSource || readiness.projectionAuthority ? (
        <p className="mt-2 text-xs break-words text-[var(--slate)]">
          {t("controlJob.projectionSource", {
            source: readiness.projectionSource ?? "unknown",
            authority: readiness.projectionAuthority ?? "projection_only",
          })}
        </p>
      ) : null}
      {readiness.runtimeState ? (
        <p className="mt-1 text-xs break-words text-[var(--slate)]">
          {t("controlJob.runtimeState", {
            state: readiness.runtimeState,
          })}
        </p>
      ) : null}
      <p className="mt-2 font-medium">{nextAction}</p>
      {readiness.nextDiagnosticCommands.map((command) => (
        <p key={command} className="mt-1 font-mono text-xs break-all">
          {command}
        </p>
      ))}
      {groupedIssues.length > 0 ? (
        <div className="mt-3 space-y-2">
          <p className="text-xs font-semibold tracking-[0.05em] text-[var(--slate)] uppercase">
            {t("controlJob.gatesNeedingReview")}
          </p>
          {groupedIssues.map((group) => (
            <div key={group.layer} className="space-y-1">
              <p className="font-semibold text-[var(--slate)]">{group.layer}</p>
              <ul className="space-y-1">
                {group.issues.map((issue) => (
                  <li
                    key={`${group.layer}:${issue.name}:${issue.status}`}
                    className="border-border/60 rounded border bg-white/55 px-2 py-1"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge kind={gateBadgeKind(issue.status)}>
                        {issue.status}
                      </Badge>
                      <span className="font-medium break-words">
                        {issue.name}
                      </span>
                    </div>
                    {issue.phase || issue.evidenceRef ? (
                      <p className="mt-1 text-xs break-all text-[var(--slate)]">
                        {[issue.phase, issue.evidenceRef]
                          .filter(Boolean)
                          .join(" / ")}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : null}
      {performanceIssues.length > 0 ? (
        <div className="mt-3 space-y-2">
          <p className="text-xs font-semibold tracking-[0.05em] text-[var(--slate)] uppercase">
            {t("controlJob.performanceBudgetIssues")}
          </p>
          <ul className="space-y-1">
            {performanceIssues.map((issue) => (
              <li
                key={`${issue.layer}:${issue.phase}:${issue.status}`}
                className="border-border/60 rounded border bg-white/55 px-2 py-1"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge kind={performanceIssueBadgeKind(issue.status)}>
                    {issue.status}
                  </Badge>
                  <span className="font-medium break-words">{issue.phase}</span>
                </div>
                <p className="mt-1 text-xs break-words text-[var(--slate)]">
                  {[issue.layer, issue.classification]
                    .filter(Boolean)
                    .join(" / ")}
                </p>
                <p className="mt-1 text-xs text-[var(--slate)]">
                  {t("controlJob.observedBudget", {
                    budget: formatMilliseconds(issue.budgetMs),
                    observed: formatMilliseconds(issue.observedValueMs),
                  })}
                </p>
                {issue.nextAction ? (
                  <p className="mt-1 text-xs font-medium">{issue.nextAction}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {readiness.scorecardRef ? (
        <p className="mt-3 text-xs break-all text-[var(--slate)]">
          {t("controlJob.scorecardEvidence", {
            ref: readiness.scorecardRef,
          })}
        </p>
      ) : null}
      {readiness.evidenceBundlePath ? (
        <p className="mt-1 text-xs break-all text-[var(--slate)]">
          {t("controlJob.evidenceBundle", {
            path: readiness.evidenceBundlePath,
          })}
        </p>
      ) : null}
      {readiness.approvalPacketRef ? (
        <p className="mt-1 text-xs break-all text-[var(--slate)]">
          {t("controlJob.approvalPacket", {
            ref: readiness.approvalPacketRef,
          })}
        </p>
      ) : null}
      {readiness.overrideDecisionRef ? (
        <p className="mt-1 text-xs break-all text-[var(--slate)]">
          {t("controlJob.overrideEvidence", {
            ref: readiness.overrideDecisionRef,
          })}
        </p>
      ) : null}
      {readiness.overridePacketRef ? (
        <p className="mt-1 text-xs break-all text-[var(--slate)]">
          {t("controlJob.overridePacket", {
            ref: readiness.overridePacketRef,
          })}
        </p>
      ) : null}
      {readiness.overrideStatus ? (
        <p className="mt-1 text-xs text-[var(--slate)]">
          {t("controlJob.overrideStatus", {
            status: readiness.overrideStatus,
          })}
        </p>
      ) : null}
      {calibration?.reportRef ? (
        <p className="mt-1 text-xs break-all text-[var(--slate)]">
          {t("controlJob.humanReviewReport", {
            ref: calibration.reportRef,
          })}
        </p>
      ) : null}
    </section>
  );
}

function ControlScientistProgressPanel({
  progress,
}: {
  progress: ScientistWorkflowProgress;
}) {
  const { t } = useOptionalI18n();
  const primaryArtifact = progress.latestArtifactRefs[0];
  return (
    <section
      aria-label={t("controlJob.scientistAriaLabel")}
      className="border-l-2 border-[var(--color-transport-live)] bg-[color-mix(in_srgb,var(--color-transport-live)_8%,transparent)] px-3 py-2 text-sm"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge kind="info">{t("controlJob.scientistWorkflow")}</Badge>
        {progress.eventCount !== null ? (
          <Badge kind="neutral">
            {t("controlJob.scientistEvents", {
              count: String(progress.eventCount),
            })}
          </Badge>
        ) : null}
      </div>
      <dl className="mt-2 grid gap-1 text-[13px] sm:grid-cols-2">
        {progress.currentNodeAlias ? (
          <div>
            <dt className="font-semibold text-[var(--slate)]">
              {t("controlJob.node")}
            </dt>
            <dd>{progress.currentNodeAlias}</dd>
          </div>
        ) : null}
        {progress.currentEvent ? (
          <div>
            <dt className="font-semibold text-[var(--slate)]">
              {t("controlJob.event")}
            </dt>
            <dd>{progress.currentEvent}</dd>
          </div>
        ) : null}
        {progress.currentPhase ? (
          <div className="sm:col-span-2">
            <dt className="font-semibold text-[var(--slate)]">
              {t("controlJob.phase")}
            </dt>
            <dd className="break-words">{progress.currentPhase}</dd>
          </div>
        ) : null}
      </dl>
      {primaryArtifact ? (
        <p className="mt-2 text-xs break-all text-[var(--slate)]">
          {t("controlJob.latestArtifact", {
            ref: [
              primaryArtifact.direction,
              primaryArtifact.kind,
              primaryArtifact.artifactId,
            ]
              .filter(Boolean)
              .join(" / "),
          })}
        </p>
      ) : null}
      {progress.updatedAt ? (
        <p className="mt-1 text-xs text-[var(--slate)]">
          {t("controlJob.updatedAt", { timestamp: progress.updatedAt })}
        </p>
      ) : null}
    </section>
  );
}

function ControlQualityPanel({ job }: { job: ControlJobResponse }) {
  const { t } = useOptionalI18n();
  const failures = job.blocking_quality_failures ?? [];
  const gates = job.quality_gates ?? [];
  const primaryFailure = failures[0];
  const primaryGate =
    gates.find((gate) => gate.status === "fail") ??
    gates.find((gate) => gate.status === "warn") ??
    gates[0];
  const primaryCode = primaryFailure?.code ?? primaryGate?.code;
  const primaryPhase = primaryFailure?.phase ?? primaryGate?.phase;
  const nextAction = primaryFailure?.next_action ?? primaryGate?.next_action;
  const evidenceRef = sanitizedRefFromUnknown(
    primaryFailure?.evidence_ref ?? primaryGate?.evidence_ref,
  );
  const scorecardRef = sanitizedRefFromUnknown(job.quality_scorecard_ref);
  const evidenceBundlePath = sanitizedRefFromUnknown(
    job.quality_evidence_bundle_path,
  );
  return (
    <section
      aria-label={t("controlJob.qualityAriaLabel")}
      className="border-l-2 border-[var(--color-status-pending)] bg-[color-mix(in_srgb,var(--color-status-pending)_8%,transparent)] px-3 py-2 text-sm"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge kind={qualityBadgeKind(job.quality_status)}>
          {t("controlJob.qualityBadge", {
            status: job.quality_status ?? "",
          })}
        </Badge>
        <Badge kind="neutral">
          {t("controlJob.executionBadge", {
            status: job.execution_status ?? job.state,
          })}
        </Badge>
      </div>
      {primaryGate ? (
        <dl className="mt-2 grid gap-1 text-[13px] sm:grid-cols-2">
          {primaryCode ? (
            <div>
              <dt className="font-semibold text-[var(--slate)]">
                {t("controlJob.code")}
              </dt>
              <dd>{primaryCode}</dd>
            </div>
          ) : null}
          <div>
            <dt className="font-semibold text-[var(--slate)]">
              {t("controlJob.gate")}
            </dt>
            <dd>{primaryFailure?.gate ?? primaryGate.name}</dd>
          </div>
          <div>
            <dt className="font-semibold text-[var(--slate)]">
              {t("controlJob.layer")}
            </dt>
            <dd>{primaryFailure?.layer ?? primaryGate.layer}</dd>
          </div>
          {primaryPhase ? (
            <div>
              <dt className="font-semibold text-[var(--slate)]">
                {t("controlJob.phase")}
              </dt>
              <dd>{primaryPhase}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}
      <p className="mt-2">
        {primaryFailure?.message ??
          primaryGate?.message ??
          t("controlJob.qualityNeedsReview")}
      </p>
      {nextAction ? <p className="mt-2 font-medium">{nextAction}</p> : null}
      {evidenceRef ? (
        <p className="mt-2 text-xs break-all text-[var(--slate)]">
          {t("controlJob.evidence", { ref: evidenceRef })}
        </p>
      ) : null}
      {scorecardRef ? (
        <p className="mt-1 text-xs break-all text-[var(--slate)]">
          {t("controlJob.scorecardEvidence", { ref: scorecardRef })}
        </p>
      ) : null}
      {evidenceBundlePath ? (
        <p className="mt-1 text-xs break-all text-[var(--slate)]">
          {t("controlJob.evidenceBundle", { path: evidenceBundlePath })}
        </p>
      ) : null}
    </section>
  );
}

export function ControlFailurePanel({
  failure,
  job,
  jobId,
}: ControlFailurePanelProps) {
  const { t } = useOptionalI18n();
  const jobQuery = useControlJobStatus(failure || job ? null : jobId);
  const controlJob = job ?? jobQuery.data ?? null;
  const envelope = failure ?? controlJob?.failure ?? null;
  const operatorDiagnostic = operatorDiagnosticFromJob(controlJob, envelope);
  const renderQuality = shouldRenderQuality(controlJob);
  const approvalReadiness = approvalReadinessFromJob(controlJob);
  const renderApproval = shouldRenderApproval(controlJob, approvalReadiness);
  const gateIssues = approvalGateIssuesFromJob(controlJob);
  const performanceIssues = performanceBudgetIssuesFromJob(controlJob);
  const scientistProgress = scientistWorkflowFromJob(controlJob);
  const renderScientistProgress = shouldRenderScientistProgress(
    controlJob,
    scientistProgress,
  );
  if (
    !envelope &&
    !operatorDiagnostic &&
    !renderQuality &&
    !renderApproval &&
    !renderScientistProgress
  ) {
    return null;
  }

  const evidencePath = evidencePathFromJob(controlJob ?? undefined, envelope);
  return (
    <div className="space-y-2">
      {envelope ? (
        <section
          aria-label={t("controlJob.failureAriaLabel")}
          className="border-l-2 border-[var(--color-status-rejected)] bg-[color-mix(in_srgb,var(--color-status-rejected)_7%,transparent)] px-3 py-2 text-sm"
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge kind="fail">{envelope.code}</Badge>
            <Badge kind={envelope.retryable ? "warn" : "neutral"}>
              {envelope.retryable
                ? t("controlJob.retryable")
                : t("controlJob.notRetryable")}
            </Badge>
          </div>
          <dl className="mt-2 grid gap-1 text-[13px] sm:grid-cols-2">
            <div>
              <dt className="font-semibold text-[var(--slate)]">
                {t("controlJob.layer")}
              </dt>
              <dd>{envelope.layer}</dd>
            </div>
            {envelope.phase ? (
              <div>
                <dt className="font-semibold text-[var(--slate)]">
                  {t("controlJob.phase")}
                </dt>
                <dd>{envelope.phase}</dd>
              </div>
            ) : null}
            {envelope.model ? (
              <div>
                <dt className="font-semibold text-[var(--slate)]">
                  {t("controlJob.model")}
                </dt>
                <dd className="break-words">{envelope.model}</dd>
              </div>
            ) : null}
            {envelope.provider ? (
              <div>
                <dt className="font-semibold text-[var(--slate)]">
                  {t("controlJob.provider")}
                </dt>
                <dd>{envelope.provider}</dd>
              </div>
            ) : null}
          </dl>
          <p className="mt-2">{envelope.message}</p>
          {envelope.next_action ? (
            <p className="mt-2 font-medium">{envelope.next_action}</p>
          ) : null}
          {evidencePath ? (
            <p className="mt-2 text-xs break-all text-[var(--slate)]">
              {t("controlJob.evidence", { ref: evidencePath })}
            </p>
          ) : null}
        </section>
      ) : null}
      {operatorDiagnostic ? (
        <OperatorDiagnosticPanel diagnostic={operatorDiagnostic} />
      ) : null}
      {renderQuality && controlJob ? (
        <ControlQualityPanel job={controlJob} />
      ) : null}
      {renderApproval && approvalReadiness ? (
        <ControlApprovalPanel
          gateIssues={gateIssues}
          performanceIssues={performanceIssues}
          readiness={approvalReadiness}
        />
      ) : null}
      {renderScientistProgress && scientistProgress ? (
        <ControlScientistProgressPanel progress={scientistProgress} />
      ) : null}
    </div>
  );
}
