import { useMemo } from "react";

import {
  ExplainabilityCard,
  type ExplainabilityFactor,
  type ExplainabilityGovernance,
  type ExplainabilityLevel,
  type ExplainabilityVerdict,
} from "@/shared/ui/compounds/ExplainabilityCard";
import {
  GovernancePassGrid,
  type GovernancePass,
} from "@/shared/ui/compounds/GovernancePassGrid";
import {
  NegativeCertificateCard,
  type SuggestedExperiment,
} from "@/shared/ui/compounds/NegativeCertificateCard";
import {
  ProvenanceChain,
  type ProvenanceStep,
} from "@/shared/ui/compounds/ProvenanceChain";
import {
  AttributionWaterfall,
  type AttributionStep,
} from "@/shared/ui/compounds/AttributionWaterfall";
import {
  EvidenceCoverageRadar,
  type EvidenceCoverage,
} from "@/shared/ui/compounds/EvidenceCoverageRadar";
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
import { Quantity, untracedDecisionQuantity } from "@/shared/ui/quantity";
import { Card } from "@polisyos/atlas-ui";
import type { QuantityValueOutput } from "@polisyos/runtime-api-client";

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

function clamp01(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return 0;
  }
  return Math.max(0, Math.min(1, value));
}

function decisionScorePoint(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }
  return clamp01(value);
}

function normalizeVerdictStatus(
  verdict: string | null | undefined,
): ExplainabilityVerdict["status"] {
  const normalized = (verdict ?? "").trim().toUpperCase();
  if (normalized.includes("APPROVE")) {
    return "approved";
  }
  if (normalized.includes("REJECT")) {
    return "rejected";
  }
  return "review";
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

function buildExplainabilityVerdict(
  summary: RunInspectorSummary,
): ExplainabilityVerdict | null {
  if (summary.decisionScore.lineage.status !== "verified") {
    return null;
  }
  const confidence = decisionScorePoint(summary.decisionScore.point);
  if (confidence === null) {
    return null;
  }
  return {
    confidence,
    status: normalizeVerdictStatus(
      summary.pipeline?.evaluator?.verdict ?? summary.decisionView?.verdict,
    ),
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
      status: "ok",
      statusLabel: `${summary.evidenceContext.dataNeeds.length} needs`,
      type: "data",
    });
  }

  if (summary.evidenceContext?.fetchPlans?.length) {
    steps.push({
      detail: `${summary.evidenceContext.fetchPlans.length} fetch plans prepared for supporting evidence.`,
      id: "fetch-plans",
      label: "Evidence collection planned",
      status: "ok",
      statusLabel: `${summary.evidenceContext.fetchPlans.length} plans`,
      type: "method",
    });
  }

  steps.push({
    detail: summary.run?.status ?? "unknown",
    id: "analysis-executed",
    label: "Analysis executed",
    status: summary.run?.status === "completed" ? "ok" : "warn",
    statusLabel:
      summary.run?.status === "completed" ? "Completed" : "In review",
    timestamp: summary.run?.finished_at ?? summary.run?.started_at ?? undefined,
    type: "result",
  });

  if (summary.governanceSummary) {
    steps.push({
      detail: `${summary.governanceSummary.blocker} blockers, ${summary.governanceSummary.warning} warnings.`,
      id: "governance-review",
      label: "Governance review",
      status: summary.governanceSummary.blocker > 0 ? "fail" : "ok",
      statusLabel: summary.governanceSummary.blocker > 0 ? "Blocked" : "Passed",
      type: "governance",
    });
  }

  return steps;
}

function buildGovernancePasses(summary: RunInspectorSummary): GovernancePass[] {
  const passes: GovernancePass[] = [];

  if (summary.pipeline?.preflight) {
    const firstDiagnostic = summary.pipeline.preflight.diagnostics?.[0];
    const readyToRun = summary.pipeline.preflight.ready_to_run === true;
    passes.push({
      detail:
        firstDiagnostic?.message ??
        summary.pipeline.preflight.notes?.[0] ??
        undefined,
      id: "preflight",
      label: "Preflight",
      status: readyToRun
        ? "pass"
        : firstDiagnostic?.severity?.toLowerCase() === "blocker"
          ? "fail"
          : "warning",
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
      status:
        normalizeVerdictStatus(summary.pipeline.evaluator.verdict) ===
        "approved"
          ? "pass"
          : normalizeVerdictStatus(summary.pipeline.evaluator.verdict) ===
              "rejected"
            ? "fail"
            : "warning",
    });
  }

  if (summary.pipeline?.reproducibility) {
    const readiness = (summary.pipeline.reproducibility.readiness ?? "")
      .trim()
      .toLowerCase();
    passes.push({
      detail:
        summary.pipeline.reproducibility.why_partial?.[0] ??
        summary.pipeline.reproducibility.suggested_next_step ??
        summary.pipeline.reproducibility.notes?.[0] ??
        undefined,
      id: "reproducibility",
      label: "Reproducibility",
      status:
        readiness === "ready" || readiness === "complete" ? "pass" : "warning",
    });
  }

  return passes;
}

function buildExplainabilityGovernance(
  passes: GovernancePass[],
  summary: RunInspectorSummary,
): ExplainabilityGovernance | undefined {
  if (passes.length === 0 && summary.governanceIssues.length === 0) {
    return undefined;
  }

  return {
    blockers: summary.governanceIssues
      .filter((issue) => issue.severity === "blocker")
      .map((issue) => issue.message)
      .slice(0, 4),
    failed: passes.filter((pass) => pass.status === "fail").length,
    passed: passes.filter((pass) => pass.status === "pass").length,
    warnings: passes.filter((pass) => pass.status === "warning").length,
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

function buildEvidenceCoverage(summary: RunInspectorSummary): {
  benchmark: EvidenceCoverage;
  coverage: EvidenceCoverage;
} {
  const transportStatus = summary.transportStatus.toLowerCase();
  return {
    benchmark: {
      academic: 0.75,
      dataset: 0.75,
      legal: 0.75,
      transport: 0.75,
    },
    coverage: {
      academic: clamp01(
        (summary.decisionView?.diagnosticsBadges?.length ?? 0) / 4,
      ),
      dataset: clamp01((summary.evidenceContext?.fetchPlans?.length ?? 0) / 4),
      legal: clamp01(
        summary.governanceSummary
          ? 1 - summary.governanceSummary.blocker * 0.2
          : 0.6,
      ),
      transport:
        transportStatus === "passed" || transportStatus === "ready"
          ? 0.9
          : transportStatus === "not_available"
            ? 0.25
            : 0.55,
    },
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

  steps.push({
    id: "conclusion",
    metadata:
      summary.primaryIssue?.code != null
        ? { primaryIssue: summary.primaryIssue.code }
        : undefined,
    summary:
      summary.primaryIssue?.message ??
      summary.decisionView?.policySummary ??
      "Decision ready for review.",
    title: "Decision concluded",
    type: "conclusion",
  });

  return steps;
}

function buildNegativeCertificate(summary: RunInspectorSummary): {
  assumptions: string[];
  blockingType: string;
  reason: string;
  suggestedExperiments: SuggestedExperiment[];
} | null {
  if (summary.blockerCount <= 0 && summary.transportStatus === "ready") {
    return null;
  }

  const suggestedExperiments = (summary.evidenceContext?.dataNeeds ?? [])
    .slice(0, 3)
    .map<SuggestedExperiment>((need) => ({
      description: `Collect ${need.metric} data at ${need.granularity} resolution.`,
      feasibility:
        need.qualityMin >= 0.85
          ? "low"
          : need.qualityMin >= 0.65
            ? "medium"
            : "high",
      id: need.needId,
      rationale: need.purpose,
    }));

  return {
    assumptions: summary.governanceIssues
      .filter((issue) => issue.severity === "blocker")
      .map((issue) => issue.message)
      .slice(0, 4),
    blockingType:
      summary.transportStatus !== "ready" &&
      summary.transportStatus !== "passed"
        ? "transport_failure"
        : summary.evidenceContext?.fetchPlans?.length
          ? "assumption_violation"
          : "data_insufficient",
    reason:
      summary.primaryIssue?.message ??
      "This run still has unresolved blockers that limit how precise the explanation can be.",
    suggestedExperiments,
  };
}

export function RunExplainabilityPanel({
  summary,
  level = "summary",
}: RunExplainabilityPanelProps) {
  const { t } = useI18n();
  const explainabilityVerdict = useMemo(
    () => buildExplainabilityVerdict(summary),
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
  const evidenceCoverage = useMemo(
    () => buildEvidenceCoverage(summary),
    [summary],
  );
  const importanceFactors = useMemo(
    () => buildImportanceFactors(summary),
    [summary],
  );
  const reasoningSteps = useMemo(() => buildReasoningSteps(summary), [summary]);
  const negativeCertificate = useMemo(
    () => buildNegativeCertificate(summary),
    [summary],
  );

  return (
    <div className="space-y-4">
      {explainabilityVerdict ? (
        <ExplainabilityCard
          governance={governance}
          keyFactors={explainabilityFactors}
          level={level}
          methodology={summary.pipeline?.source ?? undefined}
          verdict={explainabilityVerdict}
        />
      ) : null}
      <div data-quantity-metric-id={summary.decisionScore.metric_id}>
        <Quantity value={summary.decisionScore} variant="dense" />
      </div>

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
          <Card className="p-4">
            <p className="mb-3 text-xs font-semibold">
              {t("pages.runs.explainability.evidenceCoverage")}
            </p>
            <EvidenceCoverageRadar
              benchmark={evidenceCoverage.benchmark}
              coverage={evidenceCoverage.coverage}
            />
          </Card>

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

          {negativeCertificate && (
            <Card className="p-4">
              <NegativeCertificateCard
                assumptions={negativeCertificate.assumptions}
                blockingType={negativeCertificate.blockingType}
                reason={negativeCertificate.reason}
                suggestedExperiments={negativeCertificate.suggestedExperiments}
              />
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
