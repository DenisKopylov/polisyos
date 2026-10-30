import type { CSSProperties } from "react";
import { useMemo } from "react";

import { useArtifactContent } from "@/api/hooks/useArtifactContent";
import { useGovernanceDebug } from "@/api/hooks/useGovernanceDebug";
import { isRuntimeApiNotFound } from "@/api/http";
import type { RunDetailsView } from "@/api/validators";
import { useRunAgents } from "@/api/hooks/useRunAgents";
import { useRunDetails } from "@/api/hooks/useRunDetails";
import { useRunEvidenceContext } from "@/api/hooks/useRunEvidenceContext";
import { resolveArtifactPreviewPayload } from "@/features/artifacts";
import {
  LEGACY_RUN_DETAIL_TAB_MAP,
  RUN_DETAIL_TABS,
} from "@/features/runs/domain/runDetailTabs";
import {
  dedupeEvidenceArtifactRefs,
  type EvidenceArtifactRef,
  findRunEvidenceNeed,
  findRunEvidencePlan,
  findRunEvidencePromotion,
  normalizeRunEvidenceContext,
} from "@/shared/lib/domain/evidence";
import { parseDecisionCardPayload } from "@/shared/lib/domain/decision";
import { normalizeGovernanceIssues } from "@/shared/lib/domain/governance";
import { formatNumber } from "@/shared/lib/utils";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";
import type { QuantityValueOutput } from "@polisyos/runtime-api-client";

function isDecisionArtifact(
  ref: EvidenceArtifactRef | null | undefined,
): boolean {
  const kind = ref?.kind ?? "";
  return kind.includes("decision");
}

/** Resolve the typed Core identity carried by the strict run-details response. */
export function coreRunIdFromDetails(
  run: RunDetailsView | null | undefined,
): string | undefined {
  const runId = run?.run_id;
  return run?.source_kind === "core_run" &&
    typeof runId === "string" &&
    runId.trim().length > 0
    ? runId
    : undefined;
}

export function buildEvidenceHref(
  runId: string,
  focus: "need" | "plan" | "promotion" | "artifact" | "overview",
  extra?: Record<string, string | null | undefined>,
) {
  const params = new URLSearchParams({ runId, focus });
  for (const [key, value] of Object.entries(extra ?? {})) {
    if (value) {
      params.set(key, value);
    }
  }
  return `/evidence?${params.toString()}`;
}

export function getDecisionHeadline(
  verdict: string | null | undefined,
  _blockerCount: number,
  t: (path: string) => string,
) {
  return verdict?.trim() || t("common.unknown");
}

export function resolveRunDecisionScoreQuantity(input: {
  confidence: string | null | undefined;
  generatedAt?: string | null;
  point?: number | null;
  runId: string;
}): QuantityValueOutput {
  const candidatePoint =
    typeof input.point === "number" && Number.isFinite(input.point)
      ? input.point
      : null;
  const point =
    candidatePoint === null ? null : Math.max(0, Math.min(1, candidatePoint));
  return untracedDecisionQuantity({
    label: "Run decision score",
    metricId: "run.decision_score",
    point,
    reasonCode: "run_summary_without_runtime_quantity",
    time: { valid_at: input.generatedAt ?? null },
    trackingIssue: "ATLAS-DS4-C06",
    unit: { code: "1", display: "ratio", system: "ucum" },
  });
}

export function useRunDetailSummary(
  runId: string | undefined,
  t: (path: string) => string,
  options?: { liveTransport?: boolean },
) {
  const runDetailsQuery = useRunDetails(runId, {
    liveTransport: options?.liveTransport,
    resolveCurrentAlias: true,
  });
  const cachedRun = runDetailsQuery.data?.run;
  const resolvingCurrentAlias =
    typeof cachedRun?.run_id === "string" &&
    cachedRun.run_id !== runId &&
    runDetailsQuery.isFetching;
  const run =
    runDetailsQuery.isError || resolvingCurrentAlias ? undefined : cachedRun;
  const coreRunId = coreRunIdFromDetails(run);
  const runBootstrapPending =
    runDetailsQuery.isLoading ||
    resolvingCurrentAlias ||
    isRuntimeApiNotFound(runDetailsQuery.error);
  const runReady = Boolean(coreRunId);

  const agentsQuery = useRunAgents(coreRunId, runReady);
  const governanceQuery = useGovernanceDebug(coreRunId, runReady);
  const evidenceContextQuery = useRunEvidenceContext(coreRunId, runReady);

  const pipeline = agentsQuery.data?.pipeline;
  const governance = governanceQuery.data?.debug;
  const evidenceContext = useMemo(
    () => normalizeRunEvidenceContext(evidenceContextQuery.data?.context),
    [evidenceContextQuery.data],
  );
  const governanceIssues = useMemo(
    () => normalizeGovernanceIssues(governance?.issues),
    [governance?.issues],
  );
  const governanceSummary = useMemo(() => {
    if (!governance) {
      return null;
    }
    return {
      blocker: governance.issue_summary?.blocker_count ?? 0,
      info: governance.issue_summary?.info_count ?? 0,
      unknown: governance.issue_summary?.unknown_count ?? 0,
      warning: governance.issue_summary?.warning_count ?? 0,
    };
  }, [governance]);

  const artifactRefs = useMemo(
    () =>
      dedupeEvidenceArtifactRefs([
        pipeline?.decision_packet_ref ?? null,
        pipeline?.execution_plan_ref ?? null,
        pipeline?.preflight?.report_ref ?? null,
        pipeline?.evaluator?.report_ref ?? null,
        pipeline?.reproducibility?.manifest_ref ?? null,
        governance?.report_ref ?? null,
        evidenceContext?.executionPlanRef ?? null,
        evidenceContext?.evidenceBundleRef ?? null,
        evidenceContext?.dataSnapshotRef ?? null,
        evidenceContext?.inputBindingsRef ?? null,
        ...(evidenceContext?.relatedArtifacts ?? []),
        ...(run?.root_artifacts ?? []),
      ]),
    [evidenceContext, governance?.report_ref, pipeline, run?.root_artifacts],
  );

  const primaryDecisionArtifactRef = useMemo(() => {
    const refs = [
      pipeline?.decision_packet_ref ?? null,
      ...(run?.root_artifacts ?? []),
      ...(evidenceContext?.relatedArtifacts ?? []),
    ];
    return refs.find((ref) => isDecisionArtifact(ref)) ?? null;
  }, [
    evidenceContext?.relatedArtifacts,
    pipeline?.decision_packet_ref,
    run?.root_artifacts,
  ]);
  const primaryDecisionArtifactId =
    primaryDecisionArtifactRef?.artifact_id ?? null;

  const decisionArtifactQuery = useArtifactContent(
    primaryDecisionArtifactRef ?? undefined,
    {
      enabled: Boolean(primaryDecisionArtifactRef),
      maxBytes: 256 * 1024,
    },
  );
  const decisionArtifact = decisionArtifactQuery.data?.artifact ?? null;
  const decisionView = parseDecisionCardPayload(
    resolveArtifactPreviewPayload(decisionArtifact),
  );

  const blockerCount = governanceSummary?.blocker ?? 0;
  const selectedNeed = findRunEvidenceNeed(
    evidenceContext,
    evidenceContext?.dataNeeds[0]?.needId ?? null,
  );
  const selectedPlan = findRunEvidencePlan(
    evidenceContext,
    evidenceContext?.fetchPlans[0]?.planId ?? null,
  );
  const selectedPromotion = findRunEvidencePromotion(
    evidenceContext,
    evidenceContext?.promotionCandidates[0]?.promotionId ?? null,
  );
  const decisionScoreRaw = pipeline?.evaluator?.scores?.total_score ?? null;
  const decisionScore = resolveRunDecisionScoreQuantity({
    confidence: decisionView?.confidence,
    generatedAt: decisionView?.generatedAt,
    point: decisionScoreRaw,
    runId: coreRunId ?? decisionView?.runId ?? "unknown-run",
  });
  const decisionScoreStyle =
    typeof decisionScore.point === "number"
      ? ({
          "--score-angle": `${Math.max(
            32,
            Math.round(32 + decisionScore.point * 300),
          )}deg`,
        } as CSSProperties)
      : ({} as CSSProperties);

  const decisionHeadline = getDecisionHeadline(
    decisionView?.verdict ?? null,
    blockerCount,
    t,
  );
  const transportStatus = String(
    governance?.transport_summary?.status ?? "not_available",
  );
  const primaryIssue = governanceIssues[0];
  const impactRows = decisionView?.distributional?.breakdowns?.[0]?.rows?.length
    ? decisionView.distributional.breakdowns[0].rows.slice(0, 5).map((row) => ({
        label: row.cohortLabel,
        value: row.primaryDelta,
        display: `${row.primaryDelta >= 0 ? "+" : ""}${formatNumber(
          row.primaryDelta,
          {
            maximumFractionDigits: 2,
          },
        )}`,
      }))
    : decisionView?.keyMetrics.length
      ? decisionView.keyMetrics.slice(0, 5).map((metric) => ({
          label: metric.name,
          value: metric.value,
          display: `${metric.formatted}${metric.unit}`,
        }))
      : [];

  return {
    agentsQuery,
    artifactRefs,
    blockerCount,
    coreRunId,
    decisionArtifact,
    decisionArtifactQuery,
    decisionHeadline,
    decisionScore,
    decisionScoreStyle,
    decisionView,
    evidenceContext,
    evidenceContextQuery,
    governance,
    governanceIssues,
    governanceQuery,
    governanceSummary,
    impactRows,
    liveTransport: Boolean(options?.liveTransport),
    pipeline,
    primaryDecisionArtifactId,
    primaryDecisionArtifactRef,
    primaryIssue,
    run,
    runBootstrapPending,
    runDetailsQuery,
    runReady,
    selectedNeed,
    selectedPlan,
    selectedPromotion,
    transportStatus,
  };
}

export type RunInspectorSummary = ReturnType<typeof useRunDetailSummary>;
export type RunDetailSummary = RunInspectorSummary;

export { LEGACY_RUN_DETAIL_TAB_MAP, RUN_DETAIL_TABS };
