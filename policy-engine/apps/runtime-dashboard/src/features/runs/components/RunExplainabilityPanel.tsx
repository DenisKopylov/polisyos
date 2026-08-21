import { useMemo } from "react";
import type { QuantityValueOutput } from "@polisyos/runtime-api-client";

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
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { BlockerCard } from "@/shared/ui/compounds/BlockerCard";
import { Quantity, untracedDecisionQuantity } from "@/shared/ui/quantity";
import { Card } from "@polisyos/atlas-ui";

type RunExplainabilityPanelProps = {
  summary: RunInspectorSummary;
  level?: ExplainabilityLevel;
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

export function RunExplainabilityPanel({
  summary,
  level = "summary",
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
