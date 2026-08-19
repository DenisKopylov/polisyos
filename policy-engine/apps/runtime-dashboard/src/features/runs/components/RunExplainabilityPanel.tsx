import { useMemo } from "react";
import type {
  LegacyProvingGroundPayload,
  QuantityValueOutput,
} from "@polisyos/runtime-api-client";

import {
  ExplainabilityCard,
  type ExplainabilityFactor,
  type ExplainabilityGovernance,
  type ExplainabilityLevel,
} from "@/shared/ui/compounds/ExplainabilityCard";
import {
  GovernancePassGrid,
  type GovernancePass,
} from "@/shared/ui/compounds/GovernancePassGrid";
import {
  ProvenanceChain,
  type ProvenanceStep,
} from "@/shared/ui/compounds/ProvenanceChain";
import {
  AttributionWaterfall,
  type AttributionStep,
} from "@/shared/ui/compounds/AttributionWaterfall";
import {
  FactorImportanceChart,
  type ImportanceFactor,
} from "@/shared/ui/compounds/FactorImportanceChart";
import {
  ReasoningChainDisplay,
  type ReasoningStep,
} from "@/shared/ui/compounds/ReasoningChainDisplay";
import type { RunInspectorSummary } from "@/features/runs/context/RunInspectorContext";
import type { DepthNCycleBoardProjection } from "@/features/runs/api/useDepthNCycleBoardProjection";
import type { CacheObservation } from "@/api/cacheDiscipline";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { LocalizedJsonPreview } from "@/shared/ui/LocalizedJsonPreview";
import { BlockerCard } from "@/shared/ui/compounds/BlockerCard";
import { DataFreshnessBadge } from "@/shared/ui/compounds/DataFreshnessBadge";
import { WeakestLinkExplainer } from "@/shared/ui/compounds/WeakestLinkExplainer";
import { Quantity, untracedDecisionQuantity } from "@/shared/ui/quantity";
import { TimeSemanticsLabel } from "@/shared/ui/temporal/TimeSemanticsLabel";
import {
  AuthorityBadge,
  Badge,
  Card,
  EnvelopeChip,
  EvidenceLink,
  createGovernedAuthorityPurpose,
  createOpaqueAuthorityPresentation,
} from "@polisyos/atlas-ui";

type RunExplainabilityPanelProps = {
  cacheObservation?: CacheObservation | null;
  governedProjection?: DepthNCycleBoardProjection | null;
  summary: RunInspectorSummary;
  level?: ExplainabilityLevel;
  projectionError?: boolean;
  projectionLoading?: boolean;
};

type AttributionAdapter = {
  baseValue: QuantityValueOutput;
  contributions: AttributionStep[];
};

export function buildRunExplainabilityDecisionQuantities(
  summary: Pick<RunInspectorSummary, "decisionView">,
): {
  attributionBaseline: QuantityValueOutput;
} {
  const time = { valid_at: summary.decisionView?.generatedAt ?? null };
  return {
    attributionBaseline: untracedDecisionQuantity({
      label: "Attribution baseline",
      metricId: "run.attribution.baseline",
      point: 0,
      reasonCode: "explainability_baseline_without_runtime_quantity",
      time,
      trackingIssue: "ATLAS-DS4-C06",
    }),
  };
}

function factorDirection(value: number): ImportanceFactor["direction"] {
  if (value > 0) {
    return "positive";
  }
  if (value < 0) {
    return "negative";
  }
  return "neutral";
}

function buildRecordedExplainabilityCard(summary: RunInspectorSummary) {
  if (summary.decisionScore.lineage.status !== "verified") {
    return null;
  }
  return {
    confidence: summary.decisionScore,
    decisionGrade: summary.decisionView?.verdict ?? null,
    summary:
      summary.decisionView?.policySummary ??
      summary.primaryIssue?.message ??
      summary.decisionHeadline,
  };
}

function buildExplainabilityFactors(
  summary: RunInspectorSummary,
): ExplainabilityFactor[] {
  const impactRows = summary.impactRows ?? [];
  if (impactRows.length > 0) {
    return impactRows.map((row) => ({
      direction: factorDirection(row.value),
      label: row.label,
      value: row.display,
    }));
  }

  return (summary.decisionView?.keyMetrics ?? []).slice(0, 5).map((metric) => ({
    direction: factorDirection(metric.value),
    label: metric.name,
    value: `${metric.formatted}${metric.unit}`,
  }));
}

function buildProvenanceSteps(summary: RunInspectorSummary): ProvenanceStep[] {
  const steps: ProvenanceStep[] = [];

  if (summary.evidenceContext?.dataNeeds?.length) {
    steps.push({
      detail: `${summary.evidenceContext.dataNeeds.length} evidence needs mapped to the run.`,
      id: "evidence-needs",
      label: "Evidence needs identified",
      source: "diagnostic-summary",
      type: "dataset",
    });
  }

  if (summary.evidenceContext?.fetchPlans?.length) {
    steps.push({
      detail: `${summary.evidenceContext.fetchPlans.length} fetch plans prepared for supporting evidence.`,
      id: "fetch-plans",
      label: "Evidence collection planned",
      source: "diagnostic-summary",
      type: "method",
    });
  }

  steps.push({
    detail: summary.run?.status ?? "unknown",
    id: "analysis-executed",
    label: "Analysis executed",
    diagnosticLabel: summary.run?.status ?? null,
    source: "diagnostic-summary",
    timestamp: summary.run?.finished_at ?? summary.run?.started_at ?? undefined,
    type: "result",
  });

  if (summary.governanceSummary) {
    steps.push({
      detail: `${summary.governanceSummary.blocker} blockers, ${summary.governanceSummary.warning} warnings.`,
      id: "governance-review",
      label: "Governance review",
      source: "diagnostic-summary",
      type: "artifact",
    });
  }

  return steps;
}

function buildGovernancePasses(summary: RunInspectorSummary): GovernancePass[] {
  const passes: GovernancePass[] = [];

  if (summary.pipeline?.preflight) {
    const firstDiagnostic = summary.pipeline.preflight.diagnostics?.[0];
    passes.push({
      detail:
        firstDiagnostic?.message ??
        summary.pipeline.preflight.notes?.[0] ??
        undefined,
      id: "preflight",
      label: "Preflight",
      status: firstDiagnostic?.severity ?? null,
      vocabulary: "preflight_diagnostic",
    });
  }

  if (summary.pipeline?.evaluator) {
    passes.push({
      detail:
        summary.pipeline.evaluator.reasons?.[0] ??
        summary.pipeline.evaluator.diagnostics?.[0]?.message ??
        undefined,
      id: "evaluator",
      label: "Evaluator",
      status: summary.pipeline.evaluator.verdict ?? null,
      vocabulary: "evaluator_verdict",
    });
  }

  if (summary.pipeline?.reproducibility) {
    passes.push({
      detail:
        summary.pipeline.reproducibility.why_partial?.[0] ??
        summary.pipeline.reproducibility.suggested_next_step ??
        summary.pipeline.reproducibility.notes?.[0] ??
        undefined,
      id: "reproducibility",
      label: "Reproducibility",
      status: summary.pipeline.reproducibility.readiness ?? null,
      vocabulary: "reproducibility_readiness",
    });
  }

  return passes;
}

function buildExplainabilityGovernance(
  passes: GovernancePass[],
  summary: RunInspectorSummary,
): ExplainabilityGovernance | undefined {
  const projection = summary.run?.policy_design_case_projection;
  const blockers = projection ? projection.closeout_truth.blockers : [];
  if (
    passes.length === 0 &&
    summary.governanceIssues.length === 0 &&
    blockers.length === 0
  ) {
    return undefined;
  }

  return {
    blockers,
    failed: summary.governanceSummary?.blocker ?? 0,
    passed: 0,
    warnings: summary.governanceSummary?.warning ?? 0,
  };
}

function buildAttribution(summary: RunInspectorSummary): AttributionAdapter {
  const { attributionBaseline } =
    buildRunExplainabilityDecisionQuantities(summary);
  const metricContributions = (summary.decisionView?.keyMetrics ?? [])
    .slice(0, 5)
    .map<AttributionStep>((metric) => ({
      detail: `${metric.formatted}${metric.unit}`,
      label: metric.name,
      value: metric.value,
    }));

  if (metricContributions.length > 0) {
    return {
      baseValue: attributionBaseline,
      contributions: metricContributions,
    };
  }

  return {
    baseValue: attributionBaseline,
    contributions: (summary.impactRows ?? []).map((row) => ({
      detail: row.display,
      label: row.label,
      value: row.value,
    })),
  };
}

function buildImportanceFactors(
  summary: RunInspectorSummary,
): ImportanceFactor[] {
  if (summary.decisionView?.keyMetrics?.length) {
    return summary.decisionView.keyMetrics.slice(0, 6).map((metric) => ({
      detail: `${metric.formatted}${metric.unit}`,
      direction: factorDirection(metric.value),
      importance: Math.abs(metric.value),
      label: metric.name,
    }));
  }

  return (summary.impactRows ?? []).slice(0, 6).map((row) => ({
    detail: row.display,
    direction: factorDirection(row.value),
    importance: Math.abs(row.value),
    label: row.label,
  }));
}

function buildReasoningSteps(summary: RunInspectorSummary): ReasoningStep[] {
  const steps: ReasoningStep[] = [
    {
      id: "question",
      summary:
        summary.decisionView?.policySummary ??
        "Policy run requested for review.",
      title: summary.decisionHeadline,
      type: "question",
    },
  ];

  if (summary.evidenceContext) {
    steps.push({
      id: "retrieval",
      metadata: {
        artifacts: String(summary.artifactRefs.length),
        fetchPlans: String(summary.evidenceContext.fetchPlans.length),
      },
      summary:
        "Evidence needs, plans, and supporting artifacts were assembled.",
      title: "Evidence gathered",
      type: "retrieval",
    });
  }

  if (summary.pipeline?.evaluator) {
    steps.push({
      detail: summary.pipeline.evaluator.reasons?.join("\n"),
      durationMs: summary.run?.duration_ms ?? undefined,
      id: "analysis",
      summary:
        summary.pipeline.evaluator.verdict ?? "Evaluator verdict unavailable",
      title: "Evaluator synthesized the evidence",
      type: "analysis",
    });
  }

  return steps;
}

function GovernedDepthProjection({
  cacheObservation,
  projection,
  projectionError = false,
  projectionLoading = false,
}: {
  cacheObservation?: CacheObservation | null;
  projection?: DepthNCycleBoardProjection | null;
  projectionError?: boolean;
  projectionLoading?: boolean;
}) {
  const { t } = useI18n();
  if (projectionError) {
    return (
      <Card
        className="p-4"
        data-interaction-state="error"
        data-testid="governed-depth-projection-interaction"
      >
        <p className="text-muted-foreground text-sm">
          {t("common.unavailable")}
        </p>
      </Card>
    );
  }
  if (projectionLoading) {
    return (
      <Card
        className="p-4"
        data-interaction-state="loading"
        data-testid="governed-depth-projection-interaction"
      >
        <p className="text-muted-foreground text-sm">{t("common.loading")}</p>
      </Card>
    );
  }
  if (!projection) {
    return null;
  }

  const { packet, payload } = projection;
  if (packet.availability !== "available" || !payload) {
    const fixtureAuthority =
      "fixture_only" satisfies LegacyProvingGroundPayload["fixture_authority"];
    const artifactMissing = packet.availability === "artifact_missing";
    return (
      <Card
        className="space-y-3 p-4"
        data-authority-posture="unavailable"
        data-projection-availability={packet.availability}
        data-testid="governed-depth-projection"
      >
        <div className="flex flex-wrap items-center gap-2">
          <Badge kind="outline">{packet.availability}</Badge>
          {artifactMissing ? (
            <span
              className="text-muted-foreground text-xs font-semibold"
              data-fixture-authority={fixtureAuthority}
            >
              {fixtureAuthority} · {t("common.unavailable")}
            </span>
          ) : null}
        </div>
        <p className="text-muted-foreground text-sm">{packet.absence_reason}</p>
        <DataFreshnessBadge freshness={packet.freshness} />
        <TimeSemanticsLabel
          cacheObservation={cacheObservation ?? null}
          freshness={packet.freshness}
          payloadAsOf={packet.as_of}
        />
      </Card>
    );
  }

  const domainRuns = Object.entries(payload.domain_runs);
  return (
    <Card
      className="space-y-5 p-4"
      data-authority-posture="producer-projection"
      data-projection-availability={packet.availability}
      data-testid="governed-depth-projection"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h3 className="font-semibold">{packet.projection_id}</h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge kind="outline">{packet.availability}</Badge>
          <DataFreshnessBadge freshness={packet.freshness} />
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {packet.authoritative_for.map((purpose) => (
          <EnvelopeChip
            authorityPurpose={createGovernedAuthorityPurpose(packet, purpose)}
            key={purpose}
          />
        ))}
      </div>

      {packet.may_not_use_for.length > 0 ? (
        <div className="space-y-2">
          <p className="text-muted-foreground text-xs font-semibold">
            {t("pages.runs.sections.governance")}
          </p>
          <div className="flex flex-wrap gap-2">
            {packet.may_not_use_for.map((purpose) => (
              <Badge
                data-may-not-use-for={purpose}
                kind="outline"
                key={purpose}
              >
                {purpose}
              </Badge>
            ))}
          </div>
        </div>
      ) : null}

      <TimeSemanticsLabel
        cacheObservation={cacheObservation ?? null}
        freshness={packet.freshness}
        payloadAsOf={packet.as_of}
      />

      <div className="space-y-2">
        <p className="text-xs font-semibold">{t("common.sourceText")}</p>
        <EvidenceLink
          evidenceRef={packet.source.artifact_content_hash}
          label={packet.source.relative_path}
        />
        <Badge
          data-source-validation={packet.source.validation.status}
          kind="outline"
        >
          {packet.source.validation.status}
        </Badge>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {domainRuns.map(([domainId, domainProjection]) => (
          <section
            aria-label={domainId}
            className="border-line space-y-4 rounded-2xl border p-4"
            data-domain-run={domainId}
            key={domainId}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="font-semibold">{domainId}</h4>
              <Badge kind="neutral">{domainProjection.domain_role}</Badge>
            </div>
            <AuthorityBadge
              presentation={createOpaqueAuthorityPresentation(
                domainProjection.evidence_class,
              )}
            />
            <EvidenceLink
              evidenceRef={domainProjection.design_problem_ref}
              label="Design problem"
            />
            <div className="space-y-2" data-terminal-distribution="opaque">
              <p className="text-xs font-semibold">
                {domainProjection.generation_cycle_run_id}
              </p>
              <LocalizedJsonPreview
                data={domainProjection.terminal_distribution}
              />
            </div>
            <WeakestLinkExplainer projection={domainProjection} />
          </section>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="space-y-2">
          <h4 className="text-xs font-semibold">{t("pages.runs.evidence")}</h4>
          <LocalizedJsonPreview data={payload.depth_evidence} />
        </section>
        <section className="space-y-2" data-terminal-distribution="opaque">
          <h4 className="text-xs font-semibold">{packet.projection_id}</h4>
          <LocalizedJsonPreview data={payload.terminal_distributions} />
        </section>
      </div>
    </Card>
  );
}

export function RunExplainabilityPanel({
  cacheObservation,
  governedProjection,
  summary,
  level = "summary",
  projectionError = false,
  projectionLoading = false,
}: RunExplainabilityPanelProps) {
  const { t } = useI18n();
  const explainabilityCard = useMemo(
    () => buildRecordedExplainabilityCard(summary),
    [summary],
  );
  const explainabilityFactors = useMemo(
    () => buildExplainabilityFactors(summary),
    [summary],
  );
  const provenanceSteps = useMemo(
    () => buildProvenanceSteps(summary),
    [summary],
  );
  const governancePasses = useMemo(
    () => buildGovernancePasses(summary),
    [summary],
  );
  const governance = useMemo(
    () => buildExplainabilityGovernance(governancePasses, summary),
    [governancePasses, summary],
  );
  const attribution = useMemo(() => buildAttribution(summary), [summary]);
  const importanceFactors = useMemo(
    () => buildImportanceFactors(summary),
    [summary],
  );
  const reasoningSteps = useMemo(() => buildReasoningSteps(summary), [summary]);
  const producerBlockers =
    summary.run?.policy_design_case_projection?.closeout_truth.blockers ?? [];

  return (
    <div className="space-y-4">
      {explainabilityCard ? (
        <ExplainabilityCard
          governance={governance}
          keyFactors={explainabilityFactors}
          level={level}
          methodology={summary.pipeline?.source ?? undefined}
          verdict={explainabilityCard}
        />
      ) : null}
      <GovernedDepthProjection
        cacheObservation={cacheObservation}
        projection={governedProjection}
        projectionError={projectionError}
        projectionLoading={projectionLoading}
      />
      <div data-quantity-metric-id={summary.decisionScore.metric_id}>
        <Quantity value={summary.decisionScore} variant="dense" />
      </div>

      {!explainabilityCard && producerBlockers.length > 0 ? (
        <Card className="space-y-3 p-4">
          <p className="text-sm font-semibold">
            {t("pages.runs.report.blockers")}
          </p>
          {producerBlockers.map((blocker) => (
            <BlockerCard
              blocker={blocker}
              key={`${blocker.code}:${blocker.message}`}
            />
          ))}
        </Card>
      ) : null}

      {level !== "glance" && (
        <div className="grid gap-4 lg:grid-cols-2">
          {provenanceSteps.length > 0 && (
            <Card className="p-4">
              <p className="mb-3 text-xs font-semibold">
                {t("pages.runs.explainability.provenanceChain")}
              </p>
              <ProvenanceChain steps={provenanceSteps} />
            </Card>
          )}

          {governancePasses.length > 0 && (
            <Card className="p-4">
              <p className="mb-3 text-xs font-semibold">
                {t("shared.ui.governancePassGrid.title")}
              </p>
              <GovernancePassGrid passes={governancePasses} />
            </Card>
          )}

          {attribution.contributions.length > 0 && (
            <Card className="p-4">
              <p className="mb-3 text-xs font-semibold">
                {t("pages.runs.explainability.attribution")}
              </p>
              <AttributionWaterfall
                baseValue={attribution.baseValue}
                contributions={attribution.contributions}
              />
            </Card>
          )}
        </div>
      )}

      {level === "deep" && (
        <div className="grid gap-4 lg:grid-cols-2">
          {importanceFactors.length > 0 && (
            <Card className="p-4">
              <p className="mb-3 text-xs font-semibold">
                {t("pages.runs.explainability.factorImportance")}
              </p>
              <FactorImportanceChart factors={importanceFactors} />
            </Card>
          )}

          {reasoningSteps.length > 0 && (
            <Card className="p-4">
              <p className="mb-3 text-xs font-semibold">
                {t("pages.runs.explainability.reasoningChain")}
              </p>
              <ReasoningChainDisplay steps={reasoningSteps} />
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
