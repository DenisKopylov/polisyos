import { useEffect, useMemo, useState, type SubmitEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { useSuspenseArtifactContent } from "@/api/hooks/useArtifactContent";
import { useSuspenseGovernanceDebug } from "@/api/hooks/useGovernanceDebug";
import { useSuspenseRunEvidenceContext } from "@/api/hooks/useRunEvidenceContext";
import { useSuspenseRunTimeline } from "@/api/hooks/useRunTimeline";
import {
  useCreateRunPredictiveCalibration,
  useRunPredictiveCalibration,
  type PredictiveCalibrationRequest,
} from "@/api/hooks/useRunPredictiveCalibration";
import type { RunArtifactRef, RunDetailsView } from "@/api/validators";
import { isRuntimeApiNotFound } from "@/api/http";
import { usePermission } from "@/app/authz/AuthzProvider";
import { buildArtifactHref } from "@/features/artifacts";
import { useFeatureFlag } from "@/app/providers/FeatureFlagProvider";
import { useRunInspector } from "@/features/runs/context/RunInspectorContext";
import { normalizeGenericCycleSimulation } from "../../domain/genericCycleSimulation";
import { MetricCard } from "@/features/runs/components/MetricCard";
import { ScenarioWorkbench } from "@/features/whatif";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  evidenceArtifactRefKey,
  type EvidenceArtifactRef,
  findRunEvidenceNeed,
  findRunEvidencePlan,
  findRunEvidencePromotion,
  normalizeRunEvidenceContext,
} from "@/shared/lib/domain/evidence";
import { coreRunIdFromDetails } from "@/features/runs/routes/useRunDetailSummary";
import { normalizeGovernanceIssues } from "@/shared/lib/domain/governance";
import {
  formatDate,
  formatDuration,
  formatNumber,
  formatPercent,
} from "@/shared/lib/utils";
import { FeatureAsyncBoundary } from "@/shared/components/FeatureAsyncBoundary";
import {
  markUiMilestone,
  measureUiLatency,
} from "@/shared/telemetry/performance";
import { Badge, Card, EmptyState, PanelSkeleton } from "@polisyos/atlas-ui";
import { AuthoredText } from "@/shared/ui/authored-text";
import { Quantity, untracedDecisionQuantity } from "@/shared/ui/quantity";
import { presentDecisionGradeLabel } from "@/shared/ui/compounds/decisionGradePresentation";
import {
  authorityStatusBadgeProps,
  issueOpaqueAuthorityStatusPresentation,
} from "@/shared/ui/AuthorityStatusPresentation";
import { RunExplainabilityPanel } from "@/features/runs/components/RunExplainabilityPanel";
import { RunOverviewProfileLineage } from "./RunOverviewProfileLineage";

function DecisionPanelContent({
  artifactRef,
}: {
  artifactRef: EvidenceArtifactRef;
}) {
  const artifactId = artifactRef.artifact_id;
  const { t, label } = useI18n();
  const summary = useRunInspector();
  const evaluatorGrade = presentDecisionGradeLabel(
    summary.pipeline?.evaluator?.verdict ?? summary.decisionView?.verdict,
  );
  const decisionArtifactQuery = useSuspenseArtifactContent(artifactRef, {
    maxBytes: 256 * 1024,
  });
  const decisionArtifact = decisionArtifactQuery.data.artifact;
  const artifactMatchesRef =
    decisionArtifact.artifact_id === artifactRef.artifact_id &&
    (artifactRef.kind == null || decisionArtifact.kind === artifactRef.kind) &&
    (artifactRef.media_type == null ||
      decisionArtifact.media_type === artifactRef.media_type) &&
    (artifactRef.manifest_profile_sha256 == null ||
      decisionArtifact.manifest_profile_sha256 ===
        artifactRef.manifest_profile_sha256);

  useEffect(() => {
    if (!artifactMatchesRef) {
      return;
    }
    markUiMilestone("runs.overview.decision.ready", {
      routeId: "runs.detail.overview",
      surface: "overview",
    });
    measureUiLatency({
      context: {
        routeId: "runs.detail.overview",
        surface: "overview",
      },
      endMark: "runs.overview.decision.ready",
      metric: "time_to_decision_ms",
    });
  }, [artifactMatchesRef]);

  if (!artifactMatchesRef) {
    return (
      <p role="alert" data-testid="overview-artifact-profile-mismatch">
        {t("pages.runs.artifactProfileMismatch")}
      </p>
    );
  }
  const pipelineDecisionRef = summary.pipeline?.decision_packet_ref;
  const isDecisionPacket =
    (pipelineDecisionRef !== null &&
      pipelineDecisionRef !== undefined &&
      evidenceArtifactRefKey(pipelineDecisionRef) ===
        evidenceArtifactRefKey(artifactRef)) ||
    decisionArtifact.kind === "scientist.decision_packet";
  const readingViewHref = isDecisionPacket
    ? buildArtifactHref(artifactId, {
        tab: "content",
        view: "reading",
        artifactRef,
      })
    : null;

  if (summary.decisionView) {
    return (
      <div className="space-y-4">
        {readingViewHref ? (
          <div className="flex justify-end">
            <Link
              to={readingViewHref}
              data-testid="overview-reading-view-link"
              className="text-accent text-xs font-semibold underline"
            >
              {t("common.readingView")}
            </Link>
          </div>
        ) : null}
        <AuthoredText
          author="drafter"
          timestamp={
            summary.decisionView.generatedAt ??
            summary.run?.finished_at ??
            summary.run?.started_at ??
            undefined
          }
        >
          {summary.decisionView.policySummary}
        </AuthoredText>
        <div className="grid gap-3 md:grid-cols-2">
          <MetricCard
            label={t("pages.runs.evaluator")}
            value={
              <span
                data-testid="overview-evaluator-grade"
                data-decision-grade-presentation={evaluatorGrade.classification}
                data-owner-decision-grade={
                  evaluatorGrade.ownerLabel ?? undefined
                }
              >
                {evaluatorGrade.ownerLabel ?? t("common.unknown")}
              </span>
            }
          />
          <MetricCard
            label={t("pages.runs.score", {
              score: formatNumber(summary.decisionScore.point, {
                maximumFractionDigits: 2,
              }),
            })}
            value={
              <Quantity
                value={summary.decisionScore}
                format="percent"
                precision={0}
                data-testid="overview-summary-decision-score"
              />
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface/75 border-line rounded-2xl border p-4">
      {readingViewHref ? (
        <div className="mb-3 flex justify-end">
          <Link
            to={readingViewHref}
            data-testid="overview-reading-view-link"
            className="text-accent text-xs font-semibold underline"
          >
            {t("common.readingView")}
          </Link>
        </div>
      ) : null}
      <p className="font-semibold">
        {label("artifactKinds", decisionArtifact.kind, decisionArtifact.kind)}
      </p>
      <p className="text-muted mt-2 text-sm">
        {formatDuration(summary.run?.duration_ms)} · {decisionArtifact.mode}
      </p>
    </div>
  );
}

function GovernancePanelContent({ runId }: { runId: string }) {
  const { t } = useI18n();
  const governanceQuery = useSuspenseGovernanceDebug(runId);
  const governance = governanceQuery.data.debug;
  const governanceIssues = normalizeGovernanceIssues(governance.issues);
  const blockerCount = governance.issue_summary?.blocker_count ?? 0;
  const transportStatus = String(
    governance.transport_summary?.status ?? "not_available",
  );
  const blockerCountQuantity = untracedDecisionQuantity({
    point: blockerCount,
    metricId: "overview_governance_blocker_count",
    label: t("pages.runs.governance"),
    unit: { code: "{blocker}", system: "ucum", display: "blockers" },
  });

  return (
    <>
      <div className="grid gap-3 md:grid-cols-2">
        <MetricCard
          label={t("pages.runs.governance")}
          value={<Quantity value={blockerCountQuantity} />}
        />
        <MetricCard label={t("pages.runs.transport")} value={transportStatus} />
      </div>
      <div className="space-y-2">
        {governanceIssues.slice(0, 4).map((issue) => (
          <div
            key={`${issue.code}-${issue.passId ?? "pass"}`}
            className="bg-surface/75 border-line rounded-2xl border p-4"
          >
            <div className="flex items-center justify-between gap-3">
              <strong>{issue.message}</strong>
              <Badge
                {...authorityStatusBadgeProps(
                  issueOpaqueAuthorityStatusPresentation(issue.severity),
                )}
                data-owner-severity={issue.severity ?? undefined}
                data-presentation="owner-label-neutral"
                data-testid={`overview-governance-severity-${issue.code}`}
              >
                {issue.severity ?? t("common.unknown")}
              </Badge>
            </div>
            <p className="text-muted mt-2 text-xs">
              {issue.passId ?? issue.code}
            </p>
          </div>
        ))}
        {governanceIssues.length === 0 ? (
          <EmptyState
            title={t("pages.runs.governanceEmptyTitle")}
            body={t("pages.runs.governanceEmptyBody")}
          />
        ) : null}
      </div>
    </>
  );
}

function EvidencePanelContent({ runId }: { runId: string }) {
  const { t, label } = useI18n();
  const evidenceContextQuery = useSuspenseRunEvidenceContext(runId);
  const evidenceContext = normalizeRunEvidenceContext(
    evidenceContextQuery.data.context,
  );

  const selectedNeed = evidenceContext
    ? findRunEvidenceNeed(
        evidenceContext,
        evidenceContext.dataNeeds[0]?.needId ?? null,
      )
    : null;
  const selectedPlan = evidenceContext
    ? findRunEvidencePlan(
        evidenceContext,
        evidenceContext.fetchPlans[0]?.planId ?? null,
      )
    : null;
  const selectedPromotion = evidenceContext
    ? findRunEvidencePromotion(
        evidenceContext,
        evidenceContext.promotionCandidates[0]?.promotionId ?? null,
      )
    : null;

  return (
    <>
      <div className="grid gap-3 md:grid-cols-3">
        <MetricCard
          label={t("pages.runs.evidenceNeeds")}
          value={formatNumber(evidenceContext?.dataNeeds.length ?? 0)}
        />
        <MetricCard
          label={t("pages.runs.fetchPlans")}
          value={formatNumber(evidenceContext?.fetchPlans.length ?? 0)}
        />
        <MetricCard
          label={t("pages.runs.promotionCandidates")}
          value={formatNumber(evidenceContext?.promotionCandidates.length ?? 0)}
        />
      </div>
      <div className="space-y-3">
        {selectedNeed && (
          <div className="bg-surface/75 border-line rounded-2xl border p-4">
            <strong>{selectedNeed.metric}</strong>
            <p className="text-muted mt-2 text-sm">
              {selectedNeed.geography ?? "-"} · {selectedNeed.timeStart ?? "-"}{" "}
              - {selectedNeed.timeEnd ?? "-"}
            </p>
          </div>
        )}
        {selectedPlan && (
          <div className="bg-surface/75 border-line rounded-2xl border p-4">
            <strong>
              {selectedPlan.connectorId} / {selectedPlan.datasetId}
            </strong>
            <p className="text-muted mt-2 text-sm">{selectedPlan.metricId}</p>
          </div>
        )}
        {selectedPromotion && (
          <div className="bg-surface/75 border-line rounded-2xl border p-4">
            <strong>{selectedPromotion.metricId}</strong>
            <p className="text-muted mt-2 text-sm">
              {t("pages.runs.promotionMeta", {
                lane: label(
                  "retrievalLane",
                  selectedPromotion.sourceLane,
                  selectedPromotion.sourceLane,
                ),
                confidence: formatPercent(selectedPromotion.confidence, {
                  maximumFractionDigits: 1,
                }),
                status: selectedPromotion.status,
              })}
            </p>
          </div>
        )}
      </div>
    </>
  );
}

function TimelinePanelContent({ runId }: { runId: string }) {
  const { t } = useI18n();
  const timelineQuery = useSuspenseRunTimeline(runId);
  const timelineEvents = timelineQuery.data.timeline.events ?? [];

  if (timelineEvents.length === 0) {
    return (
      <EmptyState
        title={t("pages.runs.overviewTimelineEmptyTitle")}
        body={t("pages.runs.overviewTimelineEmptyBody")}
      />
    );
  }

  return (
    <div className="space-y-3">
      {timelineEvents.slice(0, 5).map((event) => (
        <div
          key={`${event.index}-${event.event}`}
          className="bg-surface/75 border-line rounded-2xl border p-4"
        >
          <div className="flex items-center justify-between gap-3">
            <strong>{event.event}</strong>
            <span className="text-muted text-xs">
              {formatDate(event.timestamp)}
            </span>
          </div>
          <p className="text-muted mt-2 text-sm">{event.phase}</p>
        </div>
      ))}
    </div>
  );
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function textList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function leafTerminalKindRows(value: unknown): Array<[string, string]> {
  const terminalKinds = asRecord(value);
  if (terminalKinds === null) {
    return [];
  }
  return Object.entries(terminalKinds).map(
    ([nodeRef, kind]): [string, string] => [nodeRef, String(kind)],
  );
}

function isArtifactRef(value: unknown, kind: string): boolean {
  const ref = asRecord(value);
  const profile = ref?.manifest_profile_sha256;
  return (
    ref !== null &&
    typeof ref.artifact_id === "string" &&
    /^sha256:[0-9a-f]{64}$/.test(ref.artifact_id) &&
    ref.kind === kind &&
    ref.media_type === "application/json" &&
    (profile == null ||
      (typeof profile === "string" && /^sha256:[0-9a-f]{64}$/.test(profile)))
  );
}

function sameCoreArtifactRefView(left: unknown, right: unknown): boolean {
  const l = asRecord(left);
  const r = asRecord(right);
  return (
    l !== null &&
    r !== null &&
    isArtifactRef(l, "runtime.quality.n4_candidate_scenario_source") &&
    isArtifactRef(r, "runtime.quality.n4_candidate_scenario_source") &&
    l.artifact_id === r.artifact_id &&
    l.kind === r.kind &&
    l.media_type === r.media_type &&
    (l.manifest_profile_sha256 ?? null) === (r.manifest_profile_sha256 ?? null)
  );
}

function hasContinuationCandidate(
  value: unknown,
  candidateId: string,
): boolean {
  const c = asRecord(value);
  const rows = c?.current_candidate_occurrences;
  return (
    typeof c?.continued_cycle_index === "number" &&
    Array.isArray(rows) &&
    rows.some((value) => {
      const row = asRecord(value);
      return (
        row !== null &&
        row.candidate_id === candidateId &&
        row.cycle_index === c.continued_cycle_index
      );
    })
  );
}

function CandidateSimulationPanel({ run }: { run: RunDetailsView }) {
  const { t } = useI18n();
  const projection = run.candidate_simulation;
  const values = projection?.n5_observations ?? [];
  const checkpoint = projection?.recursive_cycle_checkpoint ?? null;
  const failedBranches = checkpoint?.failed_branches ?? [];
  const acquisitionHistory = projection?.acquisition_history ?? [];
  const checkpointKnown = checkpoint !== null;
  if (projection == null) {
    return null;
  }
  const projectionKnown = projection.run_id === run.run_id;
  return (
    <Card className="space-y-4" data-testid="overview-candidate-simulation">
      <h4>{t("pages.runs.candidateSimulation.title")}</h4>
      <p className="text-muted text-sm">
        {t("pages.runs.candidateSimulation.authority")}
      </p>
      {!projectionKnown || projection.artifact_status !== "resolved" ? (
        <p data-testid="overview-simulation-refused">
          {typeof projection.limitation_code === "string"
            ? projection.limitation_code
            : t("pages.runs.candidateSimulation.refused")}
        </p>
      ) : null}
      {projectionKnown && typeof projection.limitation_code === "string" ? (
        <p data-testid="overview-simulation-limitation">
          {projection.limitation_code}
        </p>
      ) : null}
      {acquisitionHistory.length > 0 ||
      typeof projection.acquisition_history_limitation_code === "string" ? (
        <div
          className="space-y-2 border-t pt-3"
          data-testid="overview-acquisition-history"
        >
          <h5>{t("pages.runs.candidateSimulation.acquisitionHistoryTitle")}</h5>
          <p className="text-muted text-sm">
            {t("pages.runs.candidateSimulation.acquisitionHistoryAuthority")}
          </p>
          {typeof projection.acquisition_history_limitation_code ===
          "string" ? (
            <p data-testid="overview-acquisition-history-limitation">
              {projection.acquisition_history_limitation_code}
            </p>
          ) : null}
          {acquisitionHistory.map((value, index) => {
            const row = asRecord(value);
            const reentry = row && asRecord(row.reentry_receipt_ref);
            const newSource = row && asRecord(row.new_candidate_source_ref);
            const originSource = row && asRecord(row.origin_source_ref);
            const continuation = row && asRecord(row.continuation);
            const sameCandidate =
              row?.old_candidate_id != null &&
              row.old_candidate_id === row.new_candidate_id;
            const lineageMetadataPresent =
              row?.schema_version != null ||
              row?.reentry_receipt_schema_version != null ||
              row?.continuation_join_status != null ||
              row?.origin_source_binding_status != null;
            const expectedOriginMatches = sameCoreArtifactRefView(
              row?.origin_source_ref,
              row?.expected_origin_source_ref,
            );
            const lineageMetadataValid =
              row == null
                ? false
                : !lineageMetadataPresent
                  ? row.expected_origin_source_ref == null
                  : row.schema_version ===
                      "policyos.runtime.run_candidate_simulation_acquisition_history.v2" &&
                    (sameCandidate
                      ? row.origin_source_binding_status ===
                          "verified_same_candidate_root" &&
                        expectedOriginMatches
                      : row.origin_source_binding_status ===
                          (row.origin_source_ref == null
                            ? "not_supplied"
                            : "observed_only") &&
                        row.expected_origin_source_ref == null) &&
                    (row.reentry_receipt_schema_version ===
                    "policyos.runtime.acquisition_overlay_reentry.v3"
                      ? row.continuation_join_status ===
                          "v3_occurrence_joined" && continuation != null
                      : row.reentry_receipt_schema_version != null &&
                        row.continuation_join_status ===
                          "legacy_occurrence_unbound" &&
                        continuation == null);
            const commonKnown =
              projectionKnown &&
              projection.artifact_status === "resolved" &&
              row !== null &&
              isArtifactRef(
                row.route_receipt_ref,
                "runtime_quality.acquisition_route_loop_receipt",
              ) &&
              typeof row.route_id === "string" &&
              Number.isInteger(row.action_generation) &&
              row.currentness_status === "not_established" &&
              row.authority_purpose === "candidate_observation_only" &&
              row.publication_authority === false;
            const reentryKnown =
              row?.terminal_outcome === "reentry_completed" &&
              isArtifactRef(
                row.reentry_receipt_ref,
                "runtime_quality.acquisition_overlay_reentry_receipt",
              ) &&
              typeof row.old_candidate_id === "string" &&
              typeof row.new_candidate_id === "string" &&
              lineageMetadataValid &&
              isArtifactRef(
                row.new_candidate_source_ref,
                "runtime.quality.n4_candidate_scenario_source",
              ) &&
              (row.origin_source_ref == null ||
                isArtifactRef(
                  row.origin_source_ref,
                  "runtime.quality.n4_candidate_scenario_source",
                )) &&
              (row.expected_origin_source_ref == null ||
                isArtifactRef(
                  row.expected_origin_source_ref,
                  "runtime.quality.n4_candidate_scenario_source",
                )) &&
              (sameCandidate || row.expected_origin_source_ref == null) &&
              (continuation == null ||
                (sameCoreArtifactRefView(
                  row.new_candidate_source_ref,
                  continuation.selected_n4_source_ref,
                ) &&
                  typeof row.new_candidate_id === "string" &&
                  hasContinuationCandidate(
                    continuation,
                    row.new_candidate_id,
                  )));
            const expectedQuarantineOriginStatus =
              row?.origin_source_ref == null ? "not_supplied" : "observed_only";
            const quarantineKnown =
              row?.terminal_outcome === "quarantined_no_growth" &&
              row.reentry_receipt_ref == null &&
              row.old_candidate_id == null &&
              row.new_candidate_id == null &&
              row.new_candidate_source_ref == null &&
              row.expected_origin_source_ref == null &&
              (row.origin_source_ref == null ||
                isArtifactRef(
                  row.origin_source_ref,
                  "runtime.quality.n4_candidate_scenario_source",
                )) &&
              (lineageMetadataPresent
                ? row.schema_version ===
                    "policyos.runtime.run_candidate_simulation_acquisition_history.v2" &&
                  row.reentry_receipt_schema_version == null &&
                  row.continuation_join_status === "not_applicable" &&
                  row.origin_source_binding_status ===
                    expectedQuarantineOriginStatus
                : row.continuation_join_status == null &&
                  row.origin_source_binding_status == null);
            const legacyLimited =
              !lineageMetadataPresent ||
              row?.continuation_join_status === "legacy_occurrence_unbound";
            const verifiedRoot =
              row?.origin_source_binding_status ===
                "verified_same_candidate_root" && expectedOriginMatches;
            if (!commonKnown || (!reentryKnown && !quarantineKnown)) {
              return (
                <p
                  key={index}
                  data-testid="overview-acquisition-history-refused"
                >
                  {t(
                    "pages.runs.candidateSimulation.acquisitionHistoryRefused",
                  )}
                </p>
              );
            }
            return (
              <div key={index} className="space-y-1 border-t pt-2">
                <p>
                  {t("pages.runs.candidateSimulation.acquisitionRoute", {
                    route: String(row.route_id),
                    generation: String(row.action_generation),
                  })}
                </p>
                <p>
                  {t("pages.runs.candidateSimulation.acquisitionOutcome", {
                    outcome: String(row.terminal_outcome),
                  })}
                </p>
                <p>
                  {t("pages.runs.candidateSimulation.acquisitionCurrentness", {
                    status: String(row.currentness_status),
                  })}
                </p>
                {legacyLimited ? (
                  <p data-testid="overview-acquisition-history-limited">
                    {t(
                      "pages.runs.candidateSimulation.acquisitionHistoryLimited",
                    )}
                  </p>
                ) : null}
                {reentryKnown ? (
                  <>
                    {row.continuation_join_status != null ? (
                      <p>
                        {t(
                          "pages.runs.candidateSimulation.acquisitionJoinStatus",
                          { status: String(row.continuation_join_status) },
                        )}
                      </p>
                    ) : null}
                    <p>
                      {t(
                        "pages.runs.candidateSimulation.acquisitionOldCandidate",
                        {
                          candidate: String(row.old_candidate_id),
                        },
                      )}
                    </p>
                    <p>
                      {t(
                        "pages.runs.candidateSimulation.acquisitionNewCandidate",
                        {
                          candidate: String(row.new_candidate_id),
                        },
                      )}
                    </p>
                    <p className="text-xs break-all">
                      {t("pages.runs.candidateSimulation.acquisitionSource", {
                        ref: String(newSource?.artifact_id),
                      })}
                    </p>
                    <p className="text-xs break-all">
                      {t(
                        "pages.runs.candidateSimulation.acquisitionOriginObserved",
                        {
                          ref:
                            typeof originSource?.artifact_id === "string"
                              ? originSource.artifact_id
                              : t(
                                  "pages.runs.candidateSimulation.acquisitionOriginUnlinked",
                                ),
                        },
                      )}
                    </p>
                    {verifiedRoot ? (
                      <p className="text-xs break-all">
                        {t(
                          "pages.runs.candidateSimulation.acquisitionOriginVerified",
                          {
                            ref: String(
                              asRecord(row.expected_origin_source_ref)
                                ?.artifact_id,
                            ),
                          },
                        )}
                      </p>
                    ) : null}
                  </>
                ) : null}
                {quarantineKnown && originSource ? (
                  <p className="text-xs break-all">
                    {t(
                      "pages.runs.candidateSimulation.acquisitionOriginObserved",
                      { ref: String(originSource.artifact_id) },
                    )}
                  </p>
                ) : null}
                <p className="text-xs break-all">
                  {t("pages.runs.candidateSimulation.acquisitionReceipt", {
                    ref: String(asRecord(row.route_receipt_ref)?.artifact_id),
                  })}
                </p>
                {reentry ? (
                  <p className="text-xs break-all">
                    {t(
                      "pages.runs.candidateSimulation.acquisitionReentryReceipt",
                      {
                        ref: String(reentry.artifact_id),
                      },
                    )}
                  </p>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}
      {values.map((value, index) => {
        const observation = asRecord(value);
        if (
          !projectionKnown ||
          projection.artifact_status !== "resolved" ||
          !observation ||
          typeof observation.node_ref !== "string" ||
          typeof observation.design_problem_ref !== "string" ||
          ![
            "joint_simulated",
            "simulation_pending_n5",
            "simulation_blocked",
          ].includes(String(observation.status))
        ) {
          return (
            <p key={index} data-testid="overview-simulation-refused">
              {t("pages.runs.candidateSimulation.refused")}
            </p>
          );
        }
        const n5Ref = asRecord(observation.simulation_result_ref);
        return (
          <div key={index} className="space-y-2 border-t pt-3">
            <strong>
              {typeof observation.candidate_id === "string"
                ? observation.candidate_id
                : observation.node_ref}
            </strong>
            <p data-testid="overview-simulation-status">
              {typeof observation.status === "string"
                ? observation.status
                : t("pages.runs.candidateSimulation.notEstablished")}
            </p>
            <p>{observation.design_problem_ref}</p>
            <ul>
              {textList(observation.authority_blockers).map((blocker) => (
                <li key={blocker}>{blocker}</li>
              ))}
            </ul>
            {typeof observation.world_model_record_content_hash === "string" ? (
              <p className="text-xs break-all">
                {t("pages.runs.candidateSimulation.worldModel", {
                  ref: observation.world_model_record_content_hash,
                })}
              </p>
            ) : null}
            {n5Ref && typeof n5Ref.artifact_id === "string" ? (
              <p
                className="text-xs break-all"
                data-testid="overview-simulation-ref"
              >
                {n5Ref.artifact_id}
              </p>
            ) : null}
            {textList(observation.atom_ids).length > 0 ? (
              <p>{textList(observation.atom_ids).join(", ")}</p>
            ) : null}
            {textList(observation.selected_outcomes).length > 0 ? (
              <p>{textList(observation.selected_outcomes).join(", ")}</p>
            ) : null}
          </div>
        );
      })}
      {checkpointKnown && checkpoint ? (
        <div data-testid="overview-recursive-checkpoint" className="space-y-2">
          <h5>{t("pages.runs.candidateSimulation.checkpointTitle")}</h5>
          <p>{t("pages.runs.candidateSimulation.checkpointBody")}</p>
          <p>
            {t("pages.runs.candidateSimulation.frontier", {
              refs: textList(checkpoint.pending_frontier).join(", "),
            })}
          </p>
          {typeof checkpoint.budget_stop_node_ref === "string" ? (
            <p>{checkpoint.budget_stop_node_ref}</p>
          ) : null}
          <p>
            {t("pages.runs.candidateSimulation.completed", {
              refs: textList(checkpoint.completed_design_refs).join(", "),
            })}
          </p>
          <p>
            {t("pages.runs.candidateSimulation.rootN9", {
              status: String(
                checkpoint.root_n9_status ??
                  t("pages.runs.candidateSimulation.notEstablished"),
              ),
            })}
          </p>
          {leafTerminalKindRows(checkpoint.leaf_terminal_kinds).map(
            ([child, kind]) => (
              <p key={child}>{child + ": " + kind}</p>
            ),
          )}
          {failedBranches.map((branch, index) => {
            const failure = asRecord(branch);
            if (
              !failure ||
              typeof failure.failed_branch_ref !== "string" ||
              typeof failure.origin_node_ref !== "string" ||
              typeof failure.stage !== "string" ||
              typeof failure.exception_type !== "string" ||
              typeof failure.error_message !== "string"
            ) {
              return (
                <p key={index} data-testid="overview-checkpoint-refused">
                  {t("pages.runs.candidateSimulation.checkpointRefused")}
                </p>
              );
            }
            return (
              <div key={index} data-testid="overview-recursive-failure">
                <p>{failure.failed_branch_ref}</p>
                <p>{failure.origin_node_ref}</p>
                <p>{failure.stage}</p>
                <p>{failure.exception_type}</p>
                {typeof failure.error_code === "string" ? (
                  <p>{failure.error_code}</p>
                ) : null}
                <p>{failure.error_message}</p>
              </div>
            );
          })}
        </div>
      ) : checkpoint ? (
        <p data-testid="overview-checkpoint-refused">
          {t("pages.runs.candidateSimulation.checkpointRefused")}
        </p>
      ) : null}
    </Card>
  );
}

function GenericCycleSimulationPanel({
  presentation,
}: {
  presentation: ReturnType<typeof normalizeGenericCycleSimulation>;
}) {
  const { t } = useI18n();
  if (presentation.kind === "absent") {
    return null;
  }
  if (presentation.kind === "refused") {
    return (
      <Card
        className="space-y-3"
        data-testid="overview-generic-cycle-simulation"
      >
        <h4>{t("pages.runs.genericCycleSimulation.title")}</h4>
        <p>{t("pages.runs.genericCycleSimulation.authority")}</p>
        <p role="alert" data-testid="overview-generic-cycle-simulation-refused">
          {t("pages.runs.genericCycleSimulation.refused", {
            reason: presentation.reason,
          })}
        </p>
      </Card>
    );
  }

  const { projection } = presentation;
  const observations =
    projection.artifact_status === "resolved" ? projection.n5_observations : [];
  const cycleHistory = projection.n6_cycle_history ?? [];
  const profileBindings =
    projection.artifact_status === "resolved"
      ? projection.child_profile_bindings
      : [];
  const checkpoint =
    projection.artifact_status === "resolved"
      ? projection.recursive_cycle_checkpoint
      : null;
  const leafTerminalKinds = checkpoint
    ? leafTerminalKindRows(checkpoint.leaf_terminal_kinds)
    : [];

  return (
    <Card className="space-y-4" data-testid="overview-generic-cycle-simulation">
      <h4>{t("pages.runs.genericCycleSimulation.title")}</h4>
      <p className="text-muted text-sm">
        {t("pages.runs.genericCycleSimulation.authority")}
      </p>
      <div
        className="space-y-1"
        data-testid="overview-generic-cycle-simulation-status"
      >
        <p>
          {t("pages.runs.genericCycleSimulation.artifactStatus", {
            status: projection.artifact_status,
          })}
        </p>
        <p>
          {t("pages.runs.genericCycleSimulation.childProfileStatus", {
            status: projection.child_profile_status,
          })}
        </p>
        <p>
          {t("pages.runs.genericCycleSimulation.currentnessStatus", {
            status: projection.currentness_status,
          })}
        </p>
        {projection.n4_source_status ? (
          <p>
            {t("pages.runs.genericCycleSimulation.n4SourceStatus", {
              status: projection.n4_source_status,
            })}
          </p>
        ) : null}
      </div>
      {projection.n6_cycle_history_status ? (
        <div
          className="space-y-2 border-t pt-3"
          data-testid="overview-generic-cycle-history"
        >
          <h5>{t("pages.runs.genericCycleSimulation.cycleHistoryTitle")}</h5>
          <p data-testid="overview-generic-cycle-history-status">
            {t("pages.runs.genericCycleSimulation.cycleHistoryStatus", {
              status: projection.n6_cycle_history_status,
            })}
          </p>
          {projection.n6_cycle_history_limitation_code ? (
            <p data-testid="overview-generic-cycle-history-limitation">
              {t("pages.runs.genericCycleSimulation.cycleHistoryLimitation", {
                reason: projection.n6_cycle_history_limitation_code,
              })}
            </p>
          ) : null}
          {cycleHistory.map((cycle) => (
            <article
              className="space-y-1 break-all"
              data-testid="overview-generic-cycle-history-row"
              key={JSON.stringify([cycle.node_ref, cycle.cycle_index])}
            >
              <p>
                {t("pages.runs.genericCycleSimulation.cycleHistoryEntry", {
                  nodeRef: cycle.node_ref,
                  cycleIndex: cycle.cycle_index,
                  candidateRef: cycle.selected_candidate_ref,
                })}
              </p>
              <p>
                {t("pages.runs.genericCycleSimulation.cycleHistoryOutcome", {
                  generationStatus: cycle.generation_cycle_run_terminal_status,
                  terminal: cycle.terminal_kind,
                  refinement: cycle.refinement_decision,
                  search: cycle.search_iteration_status,
                })}
              </p>
              <p>
                {t("pages.runs.genericCycleSimulation.cycleHistorySignals", {
                  grounding: cycle.grounding_status,
                  groundingCurrentValid: String(cycle.grounding_current_valid),
                  value: cycle.value_status,
                  nextAction: cycle.voi_next_action,
                  blockers: cycle.value_authority_blockers.join(", "),
                })}
              </p>
            </article>
          ))}
        </div>
      ) : null}
      {projection.artifact_status !== "resolved" ? (
        <p data-testid="overview-generic-cycle-simulation-unavailable">
          {t("pages.runs.genericCycleSimulation.unavailable", {
            reason:
              projection.limitation_code ??
              projection.n4_source_limitation_code ??
              projection.n5_limitation_code ??
              "not_established",
          })}
        </p>
      ) : null}
      {projection.limitation_code ? (
        <p data-testid="overview-generic-cycle-simulation-limitation">
          {projection.limitation_code}
        </p>
      ) : null}
      {projection.child_profile_limitation_code ? (
        <p data-testid="overview-generic-cycle-simulation-profile-limitation">
          {projection.child_profile_limitation_code}
        </p>
      ) : null}
      {projection.n4_source_limitation_code ? (
        <p data-testid="overview-generic-cycle-simulation-n4-limitation">
          {projection.n4_source_limitation_code}
        </p>
      ) : null}
      {projection.n5_limitation_code ? (
        <p data-testid="overview-generic-cycle-simulation-n5-limitation">
          {projection.n5_limitation_code}
        </p>
      ) : null}

      {projection.joint_parent_status ? (
        <section
          className="space-y-2 border-t pt-3"
          data-testid="overview-generic-cycle-joint-parent"
        >
          <h5>{t("pages.runs.genericCycleSimulation.jointParentTitle")}</h5>
          <p>{t("pages.runs.genericCycleSimulation.jointParentAuthority")}</p>
          <p>
            {t("pages.runs.genericCycleSimulation.jointParentStatus", {
              status: projection.joint_parent_status,
            })}
          </p>
          {projection.joint_parent_limitation_code ? (
            <p data-testid="overview-generic-cycle-joint-parent-limitation">
              {projection.joint_parent_limitation_code}
            </p>
          ) : null}
          {(projection.joint_parent_observations ?? []).map((parent) => (
            <article
              className="space-y-1 rounded border p-3"
              key={parent.node_ref}
              data-testid="overview-generic-cycle-joint-parent-row"
            >
              <p>{parent.node_ref}</p>
              <p>{parent.status}</p>
              <p>
                {t("pages.runs.genericCycleSimulation.jointParentValue", {
                  status: parent.n8_status ?? "not_established",
                  grade:
                    parent.n8_candidate_decision_grade ?? "not_established",
                })}
              </p>
              <p>
                {t("pages.runs.genericCycleSimulation.jointParentSelection", {
                  status:
                    parent.n8_candidate_joint_selection_status ??
                    "not_established",
                  relationship:
                    parent.n8_source_candidate_relationship ??
                    "not_established",
                })}
              </p>
              {parent.simulation_result_ref ? (
                <p
                  className="text-xs break-all"
                  data-testid="overview-generic-cycle-joint-parent-ref"
                >
                  {parent.simulation_result_ref.artifact_id}
                </p>
              ) : null}
              {parent.n5_interaction_evidence ? (
                <div data-testid="overview-generic-cycle-joint-parent-evidence">
                  <p>
                    {t(
                      "pages.runs.genericCycleSimulation.jointParentInteraction",
                      {
                        classification:
                          parent.n5_interaction_evidence.numeric_interaction,
                        basis:
                          parent.n5_interaction_evidence
                            .numeric_interaction_basis,
                        sampling:
                          parent.n5_interaction_evidence
                            .interaction_sampling_status,
                      },
                    )}
                  </p>
                  <p>
                    {t("pages.runs.genericCycleSimulation.jointParentOrders", {
                      orders:
                        parent.n5_interaction_evidence.checked_interaction_orders.join(
                          ", ",
                        ),
                    })}
                  </p>
                  {Object.entries(
                    parent.n5_interaction_evidence.higher_order_residuals,
                  ).flatMap(([outcome, byStep]) =>
                    Object.entries(byStep).map(([step, value]) => (
                      <p key={`${outcome}:${step}`}>
                        {t(
                          "pages.runs.genericCycleSimulation.jointParentResidual",
                          {
                            outcome,
                            step,
                            value: formatNumber(value),
                          },
                        )}
                      </p>
                    )),
                  )}
                </div>
              ) : null}
              {parent.authority_blockers.map((blocker) => (
                <p key={`n5:${blocker}`}>{blocker}</p>
              ))}
              {parent.n8_authority_blockers.map((blocker) => (
                <p key={`n8:${blocker}`}>{blocker}</p>
              ))}
            </article>
          ))}
        </section>
      ) : null}

      {projection.artifact_status === "resolved" ? (
        <section
          className="space-y-2 border-t pt-3"
          data-testid="overview-generic-cycle-n5-observations"
        >
          <h5>{t("pages.runs.genericCycleSimulation.observationsTitle")}</h5>
          {observations.length === 0 ? (
            <p>{t("pages.runs.genericCycleSimulation.observationsEmpty")}</p>
          ) : null}
          <ul className="space-y-3">
            {observations.map((observation) => (
              <li
                className="space-y-1 rounded border p-3"
                key={`${observation.node_ref}:${observation.cycle_index}:${observation.candidate_id}`}
                data-testid="overview-generic-cycle-n5-row"
              >
                <p>{observation.candidate_id}</p>
                <p>{observation.node_ref}</p>
                <p>{observation.status}</p>
                <p>{observation.n5_request_binding_status}</p>
                {observation.n5_owner_join_status ? (
                  <p data-testid="overview-generic-cycle-n5-owner-join">
                    {t("pages.runs.genericCycleSimulation.ownerJoinStatus", {
                      status: observation.n5_owner_join_status,
                    })}
                  </p>
                ) : null}
                {observation.n5_owner_join_limitation_code ? (
                  <p>{observation.n5_owner_join_limitation_code}</p>
                ) : null}
                {observation.n5_request_content_hash ? (
                  <p>{observation.n5_request_content_hash}</p>
                ) : null}
                <p>{observation.n8_status}</p>
                <p>{observation.n8_lineage_status}</p>
                <p>
                  {t("pages.runs.genericCycleSimulation.currentnessStatus", {
                    status: observation.currentness_status,
                  })}
                </p>
                <p>{observation.profile_selection_ref}</p>
                {observation.n8_limitation_code ? (
                  <p>{observation.n8_limitation_code}</p>
                ) : null}
                {observation.authority_blockers.map((blocker) => (
                  <p key={blocker}>{blocker}</p>
                ))}
                {observation.n8_authority_blockers.map((blocker) => (
                  <p key={blocker}>{blocker}</p>
                ))}
                {observation.simulation_result_ref ? (
                  <p data-testid="overview-generic-cycle-simulation-result-ref">
                    {observation.simulation_result_ref.artifact_id}
                  </p>
                ) : null}
                {observation.simulation_result_body ? (
                  <div
                    className="mt-2 space-y-2 border-t pt-2"
                    data-testid="overview-generic-cycle-n5-result-body"
                  >
                    <h6>
                      {t("pages.runs.genericCycleSimulation.resultBodyTitle")}
                    </h6>
                    <p>
                      {t("pages.runs.genericCycleSimulation.resultCandidate")}
                    </p>
                    <p>
                      {t("pages.runs.genericCycleSimulation.horizon", {
                        start: observation.simulation_result_body.horizon.start,
                        end: observation.simulation_result_body.horizon.end,
                        step: observation.simulation_result_body.horizon.step,
                      })}
                    </p>
                    {observation.simulation_result_body.trajectories.map(
                      (trajectory, trajectoryIndex) => (
                        <section
                          key={
                            trajectory.run_level +
                            ":" +
                            trajectory.atom_ids.join(":") +
                            ":" +
                            trajectoryIndex.toString()
                          }
                          data-testid="overview-generic-cycle-n5-trajectory"
                        >
                          <p>
                            {t("pages.runs.genericCycleSimulation.trajectory", {
                              scope: trajectory.run_level,
                            })}
                          </p>
                          <p>
                            {t(
                              "pages.runs.genericCycleSimulation.trajectoryAtoms",
                              {
                                atomIds: trajectory.atom_ids.join(", "),
                              },
                            )}
                          </p>
                          {trajectory.points.map((point) => (
                            <div key={point.step}>
                              <p>
                                {t("pages.runs.genericCycleSimulation.step", {
                                  step: point.step,
                                })}
                              </p>
                              {Object.entries(point.outcomes).map(
                                ([name, value]) => (
                                  <p key={"outcome:" + name}>
                                    {t(
                                      "pages.runs.genericCycleSimulation.outcome",
                                      {
                                        name,
                                        value: formatNumber(value),
                                      },
                                    )}
                                  </p>
                                ),
                              )}
                              {Object.entries(point.effects).map(
                                ([name, value]) => (
                                  <p key={"effect:" + name}>
                                    {t(
                                      "pages.runs.genericCycleSimulation.effect",
                                      {
                                        name,
                                        value: formatNumber(value),
                                      },
                                    )}
                                  </p>
                                ),
                              )}
                            </div>
                          ))}
                        </section>
                      ),
                    )}
                  </div>
                ) : observation.simulation_result_body_status ===
                  "not_established" ? (
                  <p data-testid="overview-generic-cycle-n5-result-body-limited">
                    {t("pages.runs.genericCycleSimulation.bodyUnavailable")}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {profileBindings.length > 0 ? (
        <section
          className="space-y-2 border-t pt-3"
          data-testid="overview-generic-cycle-profile-bindings"
        >
          <h5>{t("pages.runs.genericCycleSimulation.profileBindingsTitle")}</h5>
          <ul className="space-y-3">
            {profileBindings.map((binding) => (
              <li
                className="space-y-1 rounded border p-3"
                key={`${binding.node_ref}:${binding.profile_id}`}
                data-testid="overview-generic-cycle-profile-binding"
              >
                <p>{binding.node_ref}</p>
                <p>{binding.profile_id}</p>
                <p>{binding.historical_binding_status}</p>
                <p>
                  {t("pages.runs.genericCycleSimulation.currentnessStatus", {
                    status: binding.currentness_status,
                  })}
                </p>
                <p>{binding.profile_selection_ref}</p>
                <p>{binding.profile_ref.artifact_id}</p>
                <p>{binding.context_job_ref.artifact_id}</p>
                <p>{binding.source_result_ref}</p>
                {binding.limitation_code ? (
                  <p>{binding.limitation_code}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {checkpoint ? (
        <section
          className="space-y-2 border-t pt-3"
          data-testid="overview-generic-cycle-checkpoint"
        >
          <h5>{t("pages.runs.candidateSimulation.checkpointTitle")}</h5>
          <p>{checkpoint.status}</p>
          <p>
            {t("pages.runs.candidateSimulation.rootN9", {
              status: checkpoint.root_n9_status,
            })}
          </p>
          <p>
            {t("pages.runs.candidateSimulation.frontier", {
              refs: checkpoint.pending_frontier.join(", ") || "—",
            })}
          </p>
          <p>
            {t("pages.runs.candidateSimulation.completed", {
              refs: checkpoint.completed_design_refs.join(", ") || "—",
            })}
          </p>
          {leafTerminalKinds.length > 0 ? (
            leafTerminalKinds.map(([nodeRef, kind]) => (
              <p
                key={nodeRef}
                data-testid="overview-generic-cycle-terminal-kind"
              >
                {nodeRef + ": " + kind}
              </p>
            ))
          ) : (
            <p data-testid="overview-generic-cycle-terminal-kinds-not-established">
              {t("pages.runs.candidateSimulation.notEstablished")}
            </p>
          )}
          {checkpoint.failed_branches.length > 0 ? (
            <ul
              className="space-y-2"
              data-testid="overview-generic-cycle-failed-branches"
            >
              {checkpoint.failed_branches.map((failure) => (
                <li
                  className="rounded border p-3"
                  key={`${failure.failed_branch_ref}:${failure.stage}:${failure.exception_type}`}
                >
                  <p>{failure.failed_branch_ref}</p>
                  <p>{failure.stage}</p>
                  <p>{failure.exception_type}</p>
                  {failure.error_code ? <p>{failure.error_code}</p> : null}
                  <p>{failure.error_message}</p>
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}
    </Card>
  );
}

type RunDetailsPayload = RunDetailsView;

function fullRunArtifactRefKey(ref: RunArtifactRef): string {
  return JSON.stringify([
    ref.artifact_id,
    ref.kind,
    ref.media_type,
    ref.manifest_profile_sha256 ?? null,
  ]);
}

type SelectedValueDataProfileRef = RunArtifactRef & {
  media_type: "application/json";
  manifest_profile_sha256: string;
};

function hasSelectedValueDataProfile(
  ref: RunArtifactRef,
): ref is SelectedValueDataProfileRef {
  return (
    ref.media_type === "application/json" &&
    typeof ref.manifest_profile_sha256 === "string"
  );
}

function selectedValueRef<TRef extends RunArtifactRef>(
  options: readonly TRef[],
  key: string,
): TRef | undefined {
  return options.find((ref) => fullRunArtifactRefKey(ref) === key);
}

function PredictiveCalibrationPanel({
  runId,
  run,
}: {
  runId: string;
  run: RunDetailsPayload;
}) {
  const { t } = useI18n();
  const query = useRunPredictiveCalibration(runId);
  const mutation = useCreateRunPredictiveCalibration(runId);
  const canCreate = usePermission("runs.feedback.evaluate");
  const [lastIntent, setLastIntent] =
    useState<PredictiveCalibrationRequest | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const candidateSourceRefs = (
    run.candidate_simulation?.n5_observations ?? []
  ).flatMap((observation): RunArtifactRef[] => {
    const ref = observation.n4_source_ref;
    return observation.status === "joint_simulated" &&
      observation.lineage_status === "resolved" &&
      ref?.kind === "runtime.quality.n4_candidate_scenario_source" &&
      ref.media_type === "application/json" &&
      Boolean(ref.manifest_profile_sha256)
      ? [ref]
      : [];
  });
  const rootInputs = (run.root_input_artifacts ?? []).filter((ref) =>
    Boolean(ref.manifest_profile_sha256),
  );
  const rootArtifacts = [...(run.root_artifacts ?? []), ...rootInputs].filter(
    (ref) => Boolean(ref.manifest_profile_sha256),
  );
  const observedSourceRefs = rootInputs.filter(
    (ref) => ref.kind === "fabric.data_snapshot",
  );
  const valueDataProfileRefs = rootInputs.filter(
    (ref): ref is SelectedValueDataProfileRef =>
      ref.kind === "runtime.value_data_profile" &&
      hasSelectedValueDataProfile(ref),
  );
  const modelSpecRefs = rootArtifacts.filter(
    (ref) => ref.kind === "ir.model_spec",
  );
  const policySpecRefs = rootArtifacts.filter(
    (ref) => ref.kind === "ir.policy_spec",
  );
  const calibrationRuleRefs = rootArtifacts.filter(
    (ref) => ref.kind === "ir.forecast_calibration_rule",
  );
  const queryUnresolved = query.isPending;
  const noSavedAssociation = Boolean(
    query.error && isRuntimeApiNotFound(query.error),
  );
  const queryRefused = Boolean(query.error && !noSavedAssociation);
  const canOfferForm = canCreate && !queryRefused;

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    const form = new FormData(event.currentTarget);
    const candidateSourceRef = selectedValueRef(
      candidateSourceRefs,
      String(form.get("candidate_source_ref") ?? ""),
    );
    const observedSourceRef = selectedValueRef(
      observedSourceRefs,
      String(form.get("observed_source_ref") ?? ""),
    );
    const modelSpecRef = selectedValueRef(
      modelSpecRefs,
      String(form.get("model_spec_ref") ?? ""),
    );
    const policySpecRef = selectedValueRef(
      policySpecRefs,
      String(form.get("policy_spec_ref") ?? ""),
    );
    const calibrationRuleRef = selectedValueRef(
      calibrationRuleRefs,
      String(form.get("calibration_rule_ref") ?? ""),
    );
    const valueDataProfileRef = selectedValueRef(
      valueDataProfileRefs,
      String(form.get("value_data_profile_ref") ?? ""),
    );
    const textValue = (name: string) => String(form.get(name) ?? "").trim();
    const valueDataUnitId = textValue("value_data_unit_id");
    const integerValue = (name: string): number | null => {
      const raw = textValue(name);
      if (!raw) return null;
      const value = Number(raw);
      return Number.isSafeInteger(value) && value >= 0 ? value : null;
    };
    const decimalValue = (name: string): number | null => {
      const raw = textValue(name);
      if (!raw) return null;
      const value = Number(raw);
      return Number.isFinite(value) ? value : null;
    };
    const timeValue = (name: string): string | null => {
      const value = textValue(name);
      if (!value) return null;
      const parsed = new Date(value);
      return Number.isNaN(parsed.valueOf()) ? null : parsed.toISOString();
    };
    const split = {
      train_start: integerValue("train_start"),
      train_end: integerValue("train_end"),
      holdout_start: integerValue("holdout_start"),
      holdout_end: integerValue("holdout_end"),
      horizon: integerValue("horizon"),
    };
    const methodAlpha = decimalValue("alpha");
    const methodBeta = decimalValue("beta");
    const threshold = decimalValue("calibration_threshold");
    const seed = integerValue("seed");
    const temporalRoles = {
      data_valid_time: timeValue("data_valid_time"),
      calibration_window_start: timeValue("calibration_window_start"),
      calibration_window_end: timeValue("calibration_window_end"),
      policy_effective_time: timeValue("policy_effective_time"),
      prediction_time: timeValue("prediction_time"),
      observation_time: timeValue("observation_time"),
    };
    const splitValues = Object.values(split);
    const splitIsValid =
      splitValues.every((value) => value !== null) &&
      split.train_start! < split.train_end! &&
      split.holdout_start === split.train_end &&
      split.holdout_start! < split.holdout_end! &&
      split.horizon === split.holdout_end! - split.holdout_start!;
    const roleValues = Object.values(temporalRoles);
    const rolesAreValid =
      roleValues.every((value) => value !== null) &&
      new Set(roleValues).size === roleValues.length &&
      temporalRoles.data_valid_time! <
        temporalRoles.calibration_window_start! &&
      temporalRoles.calibration_window_start! <
        temporalRoles.calibration_window_end! &&
      temporalRoles.calibration_window_end! <= temporalRoles.prediction_time! &&
      temporalRoles.prediction_time! < temporalRoles.observation_time! &&
      temporalRoles.policy_effective_time! <= temporalRoles.prediction_time!;
    if (
      !candidateSourceRef ||
      !observedSourceRef ||
      !modelSpecRef ||
      !policySpecRef ||
      !calibrationRuleRef ||
      threshold === null ||
      threshold <= 0 ||
      threshold > 1 ||
      !splitIsValid ||
      methodAlpha === null ||
      methodAlpha <= 0 ||
      methodAlpha > 1 ||
      methodBeta === null ||
      methodBeta <= 0 ||
      methodBeta > 1 ||
      seed === null ||
      !rolesAreValid ||
      Boolean(valueDataProfileRef) !== Boolean(valueDataUnitId) ||
      !textValue("target_metric")
    ) {
      setFormError(t("pages.runs.predictiveCalibration.formIncomplete"));
      return;
    }
    const intentId = globalThis.crypto.randomUUID();
    const request: PredictiveCalibrationRequest = {
      intent_id: intentId,
      candidate_source_ref: candidateSourceRef,
      observed_source_ref: observedSourceRef,
      model_spec_ref: modelSpecRef,
      policy_spec_ref: policySpecRef,
      calibration_rule_ref: calibrationRuleRef,
      calibration_threshold: threshold,
      split: {
        train_start: split.train_start!,
        train_end: split.train_end!,
        holdout_start: split.holdout_start!,
        holdout_end: split.holdout_end!,
        horizon: split.horizon!,
      },
      target_metric: textValue("target_metric"),
      method_params: {
        horizon: split.horizon!,
        alpha: methodAlpha,
        beta: methodBeta,
      },
      temporal_roles: {
        data_valid_time: temporalRoles.data_valid_time!,
        calibration_window_start: temporalRoles.calibration_window_start!,
        calibration_window_end: temporalRoles.calibration_window_end!,
        policy_effective_time: temporalRoles.policy_effective_time!,
        prediction_time: temporalRoles.prediction_time!,
        observation_time: temporalRoles.observation_time!,
      },
      seed,
    };
    if (valueDataProfileRef) {
      request.value_data_profile_ref = valueDataProfileRef;
      request.value_data_unit_id = valueDataUnitId;
    }
    setLastIntent(request);
    mutation.mutate(request);
  };

  const retrySameIntent = () => {
    if (lastIntent && mutation.isError && !mutation.isPending) {
      mutation.mutate(lastIntent);
    }
  };

  const { association } = query.data ?? {};
  return (
    <Card className="space-y-4" data-testid="overview-predictive-calibration">
      <div>
        <p className="eyebrow">
          {t("pages.runs.predictiveCalibration.eyebrow")}
        </p>
        <h4>{t("pages.runs.predictiveCalibration.title")}</h4>
        <p className="text-muted text-sm">
          {t("pages.runs.predictiveCalibration.authority")}
        </p>
      </div>
      {queryUnresolved ? (
        <p role="status">{t("pages.runs.predictiveCalibration.loading")}</p>
      ) : null}
      {queryRefused ? (
        <p role="alert" data-testid="overview-predictive-calibration-refused">
          {t("pages.runs.predictiveCalibration.unavailable")}
        </p>
      ) : null}
      {association ? (
        <>
          <div className="grid gap-3 md:grid-cols-2">
            <MetricCard
              label={t("pages.runs.predictiveCalibration.observedCoverage")}
              value={t("pages.runs.predictiveCalibration.coverageCount", {
                numerator: formatNumber(association.observed_numerator),
                denominator: formatNumber(association.observed_denominator),
              })}
            />
            <MetricCard
              label={t("pages.runs.predictiveCalibration.s10Status")}
              value={association.s10.calibration_status}
            />
          </div>
          <dl className="grid gap-2 text-sm md:grid-cols-2">
            <div>
              <dt className="text-muted">
                {t("pages.runs.predictiveCalibration.assessment")}
              </dt>
              <dd>{association.assessment}</dd>
            </div>
            <div>
              <dt className="text-muted">
                {t("pages.runs.predictiveCalibration.authorityScope")}
              </dt>
              <dd>{association.authority_scope}</dd>
            </div>
            <div>
              <dt className="text-muted">
                {t("pages.runs.predictiveCalibration.observedRate")}
              </dt>
              <dd>{formatPercent(association.observed_hit_rate)}</dd>
            </div>
            <div>
              <dt className="text-muted">
                {t("pages.runs.predictiveCalibration.forecastTier")}
              </dt>
              <dd>{association.s10.forecast_tier}</dd>
            </div>
            <div>
              <dt className="text-muted">
                {t("pages.runs.predictiveCalibration.issuerStatus")}
              </dt>
              <dd>{association.issuer_status}</dd>
            </div>
            <div>
              <dt className="text-muted">
                {t("pages.runs.predictiveCalibration.sourceTimeStatus")}
              </dt>
              <dd>{association.source_time_status}</dd>
            </div>
            <div>
              <dt className="text-muted">
                {t("pages.runs.predictiveCalibration.populationStatus")}
              </dt>
              <dd>{association.population_scope_status}</dd>
            </div>
            <div>
              <dt className="text-muted">
                {t("pages.runs.predictiveCalibration.counterfactualStatus")}
              </dt>
              <dd>{association.counterfactual_credibility_status}</dd>
            </div>
          </dl>
          <p className="text-muted text-xs break-all">
            {t("pages.runs.predictiveCalibration.evidenceRef", {
              ref: association.empirical_evidence_ref.artifact_id,
            })}
          </p>
          <p className="text-muted text-xs break-all">
            {t("pages.runs.predictiveCalibration.intent", {
              intent: association.intent_id,
            })}
          </p>
          <Link
            to={buildArtifactHref(
              association.uncertainty_bundle_ref.artifact_id,
              {
                tab: "content",
                artifactRef: association.uncertainty_bundle_ref,
              },
            )}
            data-testid="overview-predictive-uncertainty-bundle"
            className="text-accent text-sm font-semibold underline"
          >
            {t("pages.runs.predictiveCalibration.uncertaintyBundle")}
          </Link>
        </>
      ) : null}
      {!canCreate ? (
        <p
          role="status"
          data-testid="overview-predictive-calibration-permission"
        >
          {t("pages.runs.predictiveCalibration.permissionRequired")}
        </p>
      ) : null}
      {canOfferForm ? (
        <form
          className="border-subtle space-y-3 border-t pt-4"
          data-testid="overview-predictive-calibration-form"
          onSubmit={submit}
        >
          <h5>{t("pages.runs.predictiveCalibration.formTitle")}</h5>
          <p className="text-muted text-sm">
            {t("pages.runs.predictiveCalibration.formBoundary")}
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm">
              <span>
                {t("pages.runs.predictiveCalibration.candidateSource")}
              </span>
              <select
                name="candidate_source_ref"
                required
                defaultValue=""
                data-testid="predictive-candidate-source"
              >
                <option value="">
                  {t("pages.runs.predictiveCalibration.chooseRef")}
                </option>
                {candidateSourceRefs.map((ref) => (
                  <option
                    key={fullRunArtifactRefKey(ref)}
                    value={fullRunArtifactRefKey(ref)}
                  >
                    {ref.kind} · {ref.artifact_id}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span>
                {t("pages.runs.predictiveCalibration.observedSource")}
              </span>
              <select
                name="observed_source_ref"
                required
                defaultValue=""
                data-testid="predictive-observed-source"
              >
                <option value="">
                  {t("pages.runs.predictiveCalibration.chooseRef")}
                </option>
                {observedSourceRefs.map((ref) => (
                  <option
                    key={fullRunArtifactRefKey(ref)}
                    value={fullRunArtifactRefKey(ref)}
                  >
                    {ref.kind} · {ref.artifact_id}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span>
                {t("pages.runs.predictiveCalibration.valueDataProfile")}
              </span>
              <select
                name="value_data_profile_ref"
                defaultValue=""
                data-testid="predictive-value-data-profile"
              >
                <option value="">
                  {t("pages.runs.predictiveCalibration.profilelessOption")}
                </option>
                {valueDataProfileRefs.map((ref) => (
                  <option
                    key={fullRunArtifactRefKey(ref)}
                    value={fullRunArtifactRefKey(ref)}
                  >
                    {ref.kind} · {ref.artifact_id}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span>{t("pages.runs.predictiveCalibration.valueDataUnit")}</span>
              <input
                name="value_data_unit_id"
                maxLength={256}
                data-testid="predictive-value-data-unit"
              />
            </label>
            <label className="space-y-1 text-sm">
              <span>{t("pages.runs.predictiveCalibration.modelSpec")}</span>
              <select
                name="model_spec_ref"
                required
                defaultValue=""
                data-testid="predictive-model-spec"
              >
                <option value="">
                  {t("pages.runs.predictiveCalibration.chooseRef")}
                </option>
                {modelSpecRefs.map((ref) => (
                  <option
                    key={fullRunArtifactRefKey(ref)}
                    value={fullRunArtifactRefKey(ref)}
                  >
                    {ref.artifact_id}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span>{t("pages.runs.predictiveCalibration.policySpec")}</span>
              <select
                name="policy_spec_ref"
                required
                defaultValue=""
                data-testid="predictive-policy-spec"
              >
                <option value="">
                  {t("pages.runs.predictiveCalibration.chooseRef")}
                </option>
                {policySpecRefs.map((ref) => (
                  <option
                    key={fullRunArtifactRefKey(ref)}
                    value={fullRunArtifactRefKey(ref)}
                  >
                    {ref.artifact_id}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span>
                {t("pages.runs.predictiveCalibration.calibrationRule")}
              </span>
              <select
                name="calibration_rule_ref"
                required
                defaultValue=""
                data-testid="predictive-calibration-rule"
              >
                <option value="">
                  {t("pages.runs.predictiveCalibration.chooseRef")}
                </option>
                {calibrationRuleRefs.map((ref) => (
                  <option
                    key={fullRunArtifactRefKey(ref)}
                    value={fullRunArtifactRefKey(ref)}
                  >
                    {ref.artifact_id}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span>{t("pages.runs.predictiveCalibration.targetMetric")}</span>
              <input
                name="target_metric"
                required
                maxLength={200}
                data-testid="predictive-target-metric"
              />
            </label>
            <label className="space-y-1 text-sm">
              <span>{t("pages.runs.predictiveCalibration.threshold")}</span>
              <input
                name="calibration_threshold"
                type="number"
                min="0.000001"
                max="1"
                step="any"
                required
                data-testid="predictive-threshold"
              />
            </label>
            <label className="space-y-1 text-sm">
              <span>{t("pages.runs.predictiveCalibration.seed")}</span>
              <input
                name="seed"
                type="number"
                min="0"
                step="1"
                required
                data-testid="predictive-seed"
              />
            </label>
            <label className="space-y-1 text-sm">
              <span>{t("pages.runs.predictiveCalibration.trainStart")}</span>
              <input
                name="train_start"
                type="number"
                min="0"
                step="1"
                required
              />
            </label>
            <label className="space-y-1 text-sm">
              <span>{t("pages.runs.predictiveCalibration.trainEnd")}</span>
              <input name="train_end" type="number" min="0" step="1" required />
            </label>
            <label className="space-y-1 text-sm">
              <span>{t("pages.runs.predictiveCalibration.holdoutStart")}</span>
              <input
                name="holdout_start"
                type="number"
                min="0"
                step="1"
                required
              />
            </label>
            <label className="space-y-1 text-sm">
              <span>{t("pages.runs.predictiveCalibration.holdoutEnd")}</span>
              <input
                name="holdout_end"
                type="number"
                min="0"
                step="1"
                required
              />
            </label>
            <label className="space-y-1 text-sm">
              <span>{t("pages.runs.predictiveCalibration.horizon")}</span>
              <input name="horizon" type="number" min="1" step="1" required />
            </label>
            <label className="space-y-1 text-sm">
              <span>{t("pages.runs.predictiveCalibration.alpha")}</span>
              <input
                name="alpha"
                type="number"
                min="0"
                max="1"
                step="any"
                required
              />
            </label>
            <label className="space-y-1 text-sm">
              <span>{t("pages.runs.predictiveCalibration.beta")}</span>
              <input
                name="beta"
                type="number"
                min="0"
                max="1"
                step="any"
                required
              />
            </label>
          </div>
          <fieldset className="grid gap-3 md:grid-cols-2">
            <legend>
              {t("pages.runs.predictiveCalibration.temporalRoles")}
            </legend>
            {(
              [
                "data_valid_time",
                "calibration_window_start",
                "calibration_window_end",
                "policy_effective_time",
                "prediction_time",
                "observation_time",
              ] as const
            ).map((name) => (
              <label key={name} className="space-y-1 text-sm">
                <span>{t(`pages.runs.predictiveCalibration.${name}`)}</span>
                <input name={name} type="datetime-local" required />
              </label>
            ))}
          </fieldset>
          {candidateSourceRefs.length === 0 ||
          observedSourceRefs.length === 0 ||
          modelSpecRefs.length === 0 ||
          policySpecRefs.length === 0 ||
          calibrationRuleRefs.length === 0 ? (
            <p
              role="status"
              data-testid="overview-predictive-calibration-inputs-missing"
            >
              {t("pages.runs.predictiveCalibration.runInputsRequired")}
            </p>
          ) : null}
          {formError ? <p role="alert">{formError}</p> : null}
          {mutation.isError ? (
            <div
              role="alert"
              data-testid="overview-predictive-calibration-mutation-error"
            >
              <p>
                {mutation.error instanceof Error
                  ? mutation.error.message
                  : String(mutation.error)}
              </p>
              {lastIntent ? (
                <button
                  type="button"
                  onClick={retrySameIntent}
                  disabled={mutation.isPending}
                  data-testid="overview-predictive-calibration-retry"
                >
                  {t("pages.runs.predictiveCalibration.retrySameIntent")}
                </button>
              ) : null}
            </div>
          ) : null}
          <p className="text-muted text-xs">
            {t("pages.runs.predictiveCalibration.newIntentHint")}
          </p>
          <button
            type="submit"
            disabled={
              !canCreate ||
              queryUnresolved ||
              queryRefused ||
              mutation.isPending ||
              candidateSourceRefs.length === 0 ||
              observedSourceRefs.length === 0
            }
            data-testid="overview-predictive-calibration-submit"
          >
            {mutation.isPending
              ? t("pages.runs.predictiveCalibration.submitting")
              : t("pages.runs.predictiveCalibration.submit")}
          </button>
        </form>
      ) : null}
    </Card>
  );
}

export default function OverviewTab() {
  const { t } = useI18n();
  const whatIfEnabled = useFeatureFlag("enableWhatIfAnalysis");
  const canReviewCycleBoard = usePermission("runs.review");
  const { runId } = useParams();
  const summary = useRunInspector();
  const coreRunId = coreRunIdFromDetails(summary.run);
  const genericCycleSimulation = useMemo(
    () =>
      normalizeGenericCycleSimulation(
        summary.run?.run_id ?? runId ?? "unknown-run",
        summary.run?.generic_cycle_simulation,
      ),
    [runId, summary.run?.run_id, summary.run?.generic_cycle_simulation],
  );

  if (!summary.run || !coreRunId || !runId) {
    return null;
  }

  return (
    <div className="space-y-5" data-testid="run-tab-overview">
      <PredictiveCalibrationPanel runId={coreRunId} run={summary.run} />
      <CandidateSimulationPanel run={summary.run} />
      <GenericCycleSimulationPanel presentation={genericCycleSimulation} />
      <div className="grid gap-5 xl:grid-cols-2">
        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.runs.sections.decision")}</p>
              <h4>{summary.decisionHeadline}</h4>
            </div>
          </div>
          {summary.primaryDecisionArtifactRef ? (
            <FeatureAsyncBoundary
              feature="runs.overview.decision"
              title={t("pages.runs.decisionLoadError")}
              body={t("common.pageErrorBody")}
              loading={
                <PanelSkeleton
                  rows={4}
                  className="border-0 bg-transparent p-0"
                />
              }
              resetKeys={[
                evidenceArtifactRefKey(summary.primaryDecisionArtifactRef),
              ]}
            >
              <DecisionPanelContent
                artifactRef={summary.primaryDecisionArtifactRef}
              />
            </FeatureAsyncBoundary>
          ) : (
            <EmptyState
              title={t("pages.runs.decisionCandidatesEmptyTitle")}
              body={t("pages.runs.decisionCandidatesEmptyBody")}
            />
          )}
        </Card>

        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.runs.sections.governance")}</p>
              <h4>
                {t("pages.runs.blockers", {
                  count: formatNumber(summary.blockerCount),
                })}
              </h4>
            </div>
          </div>
          <FeatureAsyncBoundary
            feature="runs.overview.governance"
            title={t("pages.runs.governanceLoadError")}
            body={t("common.pageErrorBody")}
            loading={
              <PanelSkeleton rows={6} className="border-0 bg-transparent p-0" />
            }
            resetKeys={[runId]}
          >
            <GovernancePanelContent runId={coreRunId} />
          </FeatureAsyncBoundary>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.runs.sections.evidence")}</p>
              <h4>
                {t("pages.runs.evidenceSummary", {
                  plans: formatNumber(
                    summary.evidenceContext?.fetchPlans.length ?? 0,
                  ),
                  promotions: formatNumber(
                    summary.evidenceContext?.promotionCandidates.length ?? 0,
                  ),
                })}
              </h4>
            </div>
            <Link
              to={`/runs/${runId}/evidence`}
              className="text-accent text-xs font-semibold underline"
            >
              {t("pages.runs.openEvidence")}
            </Link>
          </div>
          <FeatureAsyncBoundary
            feature="runs.overview.evidence"
            title={t("pages.runs.evidenceLoadError")}
            body={t("common.pageErrorBody")}
            loading={
              <PanelSkeleton rows={5} className="border-0 bg-transparent p-0" />
            }
            resetKeys={[runId]}
          >
            <EvidencePanelContent runId={coreRunId} />
          </FeatureAsyncBoundary>
        </Card>

        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.runs.timelineEvents")}</p>
              <h4>{t("pages.runs.overviewTimelineTitle")}</h4>
            </div>
          </div>
          <FeatureAsyncBoundary
            feature="runs.overview.timeline"
            title={t("pages.runs.timelineLoadError")}
            body={t("common.pageErrorBody")}
            loading={
              <PanelSkeleton rows={4} className="border-0 bg-transparent p-0" />
            }
            resetKeys={[runId]}
          >
            <TimelinePanelContent runId={coreRunId} />
          </FeatureAsyncBoundary>
        </Card>
      </div>

      {whatIfEnabled ? (
        <Card className="space-y-4" data-testid="overview-scenario-workbench">
          <ScenarioWorkbench runId={coreRunId} />
        </Card>
      ) : null}

      <RunOverviewProfileLineage runId={coreRunId} />

      {/* Explainability & Trust (XAI) */}
      <Card className="space-y-4">
        <div className="panel-header">
          <div>
            <p className="eyebrow">{t("pages.runs.sections.explainability")}</p>
            <h4>{t("pages.runs.explainabilitySubtitle")}</h4>
          </div>
          {canReviewCycleBoard ? (
            <Link
              className="text-accent text-xs font-semibold underline"
              to="/runs/cycle-board"
            >
              {t("pages.cycleBoard.globalCohortLink")}
            </Link>
          ) : null}
        </div>
        <RunExplainabilityPanel level="summary" summary={summary} />
      </Card>
    </div>
  );
}
