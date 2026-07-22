import type { QuantityUncertainty } from "@polisyos/runtime-api-client";

import type { RunEvidenceContext } from "@/shared/lib/domain/evidence";
import {
  metricIdentifiability,
  type DecisionCardViewModel,
  type DecisionDistributionalRow,
  type DecisionMetric,
} from "@/shared/lib/domain/decision";
import type { GovernanceIssueView } from "@/shared/lib/domain/governance";
import {
  createInteractionState,
  type InteractionState,
} from "@/shared/lib/domain/statusOwnership";

export type IdentifiabilityState = QuantityUncertainty["identifiability"];

export type IdentificationRemedy = {
  effort: "low" | "medium" | "high";
  kind: "dataset" | "rct" | "iv" | "covariate" | "panel" | "measurement";
  ref: string;
};

export type IdentifiabilityCell = {
  assumptionCount: number;
  bounds: {
    lower: number | null;
    method: string | null;
    upper: number | null;
  };
  decisionImpact: {
    policyRecommendations: number | null;
    quantities: number;
  };
  id: string;
  label: string;
  remedy: IdentificationRemedy;
  remedies: IdentificationRemedy[];
  state: IdentifiabilityState;
};

export type IdentifiabilitySurfaceView = {
  cells: IdentifiabilityCell[];
  summary: Array<{ count: number; state: IdentifiabilityState }>;
  totalCells: number;
  totalDecisionBearingQuantities: number;
  initialCellId: string | null;
};

export type SensitivityClaim = {
  eValue: number;
  extinguished: boolean;
  explanationKey: "below_threshold" | "survives_threshold";
  id: string;
  label: string;
  threshold: number;
};

export type SensitivityRotorView = {
  decisionBearingExtinguished: number;
  decisionBearingExtinguishedShare: number;
  decisionBearingTotal: number;
  extinguishedClaims: number;
  fairnessGateChanged: boolean;
  remainingDecisionBearingShare: number;
  remainingClaims: number;
  threshold: number;
  totalClaims: number;
  verdictChanged: boolean | null;
  claims: SensitivityClaim[];
};

export type CohortTransition = {
  baselineShare: number;
  cohortId: string;
  cohortLabel: string;
  fromState: string;
  observedShare: number;
  overlayShare: number;
  policyEffect: InteractionState;
  timeIndex: number;
  toState: string;
};

export type CohortTimeTravelerView = {
  activeIndex: number;
  filters: Array<{ id: string; label: string; value: string | null }>;
  policyOverlay: {
    ref: string;
    verdict: string | null;
  };
  timeline: Array<{ index: number; label: string; validAt: string | null }>;
  transitions: CohortTransition[];
};

export type StressSceneDiagnosticDisplay = InteractionState;

function stressSceneDiagnostic(label: string): StressSceneDiagnosticDisplay {
  return createInteractionState(label, "diagnostic_display");
}

export type StressScene = {
  act: 1 | 2 | 3;
  actual: StressSceneDiagnosticDisplay;
  diff: "same" | "degraded" | "improved";
  expected: StressSceneDiagnosticDisplay;
  id: string;
  immutableRef: string;
  issueRefs: string[];
  labelKey: string;
  policyChanged: boolean | null;
  priority: number;
  reactionKey: string;
};

export type StressTestTheatreView = {
  citedSceneRef: string | null;
  scenes: StressScene[];
  summary: {
    diagnosticFindings: number;
    evidenceWarnings: number;
  };
};

export type ScientificDepthSnapshot = {
  cohort: CohortTimeTravelerView;
  identifiability: IdentifiabilitySurfaceView;
  sensitivity: SensitivityRotorView;
  stress: StressTestTheatreView;
};

function metricId(metric: DecisionMetric, index: number) {
  return (
    metric.name
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || `metric-${index + 1}`
  );
}

function assertNeverIdentifiability(value: never): never {
  throw new TypeError(`Unhandled generated identifiability member: ${value}`);
}

function remedyForCell(
  state: IdentifiabilityState,
  context: RunEvidenceContext | null | undefined,
): IdentificationRemedy {
  if (state === "identified") {
    return {
      effort: "low",
      kind: "measurement",
      ref: context?.promotionCandidates[0]?.promotionId ?? "audit-current-data",
    };
  }
  if (state === "estimated") {
    return {
      effort: "medium",
      kind: "covariate",
      ref: context?.fetchPlans[0]?.planId ?? "add-confounder-covariate",
    };
  }
  if (state === "assumed") {
    return {
      effort: "high",
      kind: "iv",
      ref: context?.dataNeeds[0]?.needId ?? "find-valid-instrument",
    };
  }
  if (state === "unknown") {
    return {
      effort: "high",
      kind: context?.dataNeeds.length ? "dataset" : "rct",
      ref: context?.dataNeeds[0]?.needId ?? "create-identifying-study",
    };
  }
  return assertNeverIdentifiability(state);
}

function remedyCandidatesForCell(
  state: IdentifiabilityState,
  context: RunEvidenceContext | null | undefined,
): IdentificationRemedy[] {
  const promotionRef =
    context?.promotionCandidates[0]?.promotionId ??
    "replicate-current-estimate";
  const planRef = context?.fetchPlans[0]?.planId ?? "collect-panel-covariates";
  const needRef =
    context?.dataNeeds[0]?.needId ?? "register-identification-gap";

  if (state === "identified") {
    return [
      { effort: "low", kind: "measurement", ref: "audit-current-data" },
      { effort: "low", kind: "dataset", ref: promotionRef },
    ];
  }
  if (state === "estimated") {
    return [
      { effort: "medium", kind: "covariate", ref: planRef },
      { effort: "medium", kind: "panel", ref: needRef },
      { effort: "high", kind: "rct", ref: "design-targeted-rct" },
    ];
  }
  if (state === "assumed") {
    return [
      { effort: "high", kind: "iv", ref: needRef },
      { effort: "high", kind: "rct", ref: "design-encouragement-study" },
      { effort: "medium", kind: "panel", ref: planRef },
    ];
  }
  if (state === "unknown") {
    return [
      {
        effort: "high",
        kind: context?.dataNeeds.length ? "dataset" : "rct",
        ref: needRef,
      },
      { effort: "high", kind: "rct", ref: "create-identifying-study" },
      {
        effort: "medium",
        kind: "measurement",
        ref: "instrument-outcome-measure",
      },
    ];
  }
  return assertNeverIdentifiability(state);
}

function boundsMethodForMetric(
  metric: DecisionMetric,
): IdentifiabilityCell["bounds"]["method"] {
  return metric.uncertaintyMethod ?? null;
}

export function buildIdentifiabilitySurfaceView(input: {
  decisionView: DecisionCardViewModel | null | undefined;
  evidenceContext?: RunEvidenceContext | null;
}): IdentifiabilitySurfaceView {
  const metrics = input.decisionView?.keyMetrics ?? [];
  const cells = metrics.map<IdentifiabilityCell>((metric, index) => {
    const state = metricIdentifiability(metric);
    const id = metricId(metric, index);
    return {
      assumptionCount: metric.assumptionWarnings?.length ?? 0,
      bounds: {
        lower: metric.ciLower,
        method: boundsMethodForMetric(metric),
        upper: metric.ciUpper,
      },
      decisionImpact: {
        policyRecommendations: null,
        quantities: 1 + (metric.assumptionWarnings?.length ?? 0),
      },
      id,
      label: metric.name,
      remedy: remedyForCell(state, input.evidenceContext),
      remedies: remedyCandidatesForCell(state, input.evidenceContext),
      state,
    };
  });
  const summary = new Map<IdentifiabilityState, number>();
  for (const cell of cells) {
    summary.set(cell.state, (summary.get(cell.state) ?? 0) + 1);
  }

  return {
    cells,
    summary: Array.from(summary, ([state, count]) => ({ count, state })),
    totalCells: cells.length,
    totalDecisionBearingQuantities: cells.reduce(
      (total, cell) => total + cell.decisionImpact.quantities,
      0,
    ),
    initialCellId: cells[0]?.id ?? null,
  };
}

function eValue(metric: DecisionMetric) {
  const hasWarnings = Boolean(metric.assumptionWarnings?.length);
  const spansZero =
    typeof metric.ciLower === "number" &&
    typeof metric.ciUpper === "number" &&
    metric.ciLower <= 0 &&
    metric.ciUpper >= 0;
  const significanceBoost =
    typeof metric.pAdj === "number" && metric.pAdj <= 0.05
      ? 1.1
      : typeof metric.pValue === "number" && metric.pValue <= 0.05
        ? 0.8
        : 0;
  const effectMagnitude =
    typeof metric.effectSize === "number"
      ? Math.abs(metric.effectSize)
      : Math.min(2, Math.abs(metric.value) / 10);
  const warningPenalty = hasWarnings ? 0.45 : 0;
  const zeroPenalty = spansZero ? 0.35 : 0;
  return Math.max(
    1,
    Number(
      (
        1.05 +
        effectMagnitude +
        significanceBoost -
        warningPenalty -
        zeroPenalty
      ).toFixed(2),
    ),
  );
}

export function buildSensitivityRotorView(input: {
  decisionView: DecisionCardViewModel | null | undefined;
  governanceIssues?: GovernanceIssueView[];
  threshold: number;
}): SensitivityRotorView {
  const threshold = Number(input.threshold.toFixed(2));
  const claims = (input.decisionView?.keyMetrics ?? []).map<SensitivityClaim>(
    (metric, index) => {
      const value = eValue(metric);
      const extinguished = value < threshold;
      return {
        eValue: value,
        extinguished,
        explanationKey: extinguished ? "below_threshold" : "survives_threshold",
        id: metricId(metric, index),
        label: metric.name,
        threshold,
      };
    },
  );
  const extinguishedClaims = claims.filter(
    (claim) => claim.extinguished,
  ).length;
  const decisionBearingTotal = (input.decisionView?.keyMetrics ?? []).reduce(
    (total, metric) => total + 1 + (metric.assumptionWarnings?.length ?? 0),
    0,
  );
  const decisionBearingExtinguished = claims.reduce((total, claim, index) => {
    if (!claim.extinguished) {
      return total;
    }
    const metric = input.decisionView?.keyMetrics[index];
    return total + 1 + (metric?.assumptionWarnings?.length ?? 0);
  }, 0);
  const decisionBearingExtinguishedShare =
    decisionBearingTotal > 0
      ? decisionBearingExtinguished / decisionBearingTotal
      : 0;
  const fairnessGateChanged = Boolean(
    input.governanceIssues?.some((issue) =>
      /fair|bias|disparate|protected/i.test(
        `${issue.code} ${issue.message} ${issue.passId ?? ""}`,
      ),
    ) && extinguishedClaims > 0,
  );
  return {
    claims,
    decisionBearingExtinguished,
    decisionBearingExtinguishedShare,
    decisionBearingTotal,
    extinguishedClaims,
    fairnessGateChanged,
    remainingDecisionBearingShare: Math.max(
      0,
      1 - decisionBearingExtinguishedShare,
    ),
    remainingClaims: claims.length - extinguishedClaims,
    threshold,
    totalClaims: claims.length,
    verdictChanged: null,
  };
}

function addDays(anchor: string | null | undefined, days: number) {
  const base = anchor ? Date.parse(anchor) : Date.UTC(2026, 0, 1);
  const date = new Date(Number.isFinite(base) ? base : Date.UTC(2026, 0, 1));
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString();
}

function transitionForRow(
  row: DecisionDistributionalRow,
  index: number,
): CohortTransition {
  const deltaDirection =
    row.primaryDelta > 0
      ? "positive_delta"
      : row.primaryDelta < 0
        ? "negative_delta"
        : "no_delta";
  const policyEffect = createInteractionState(
    deltaDirection,
    "diagnostic_display",
  );
  const overlayShare = Math.max(
    0,
    Math.min(1, row.populationShare + row.primaryDelta),
  );
  return {
    baselineShare: Math.max(
      0,
      Math.min(1, row.populationShare - row.primaryDelta),
    ),
    cohortId: `cohort-${index + 1}`,
    cohortLabel: row.cohortLabel,
    fromState: row.isVulnerable ? "covered-vulnerable" : "covered",
    observedShare: row.populationShare,
    overlayShare,
    policyEffect,
    timeIndex: 1,
    toState:
      row.primaryDelta > 0
        ? "overlay-share-increased"
        : row.primaryDelta < 0
          ? "overlay-share-decreased"
          : "overlay-share-unchanged",
  };
}

export function buildCohortTimeTravelerView(input: {
  activeIndex?: number;
  decisionView: DecisionCardViewModel | null | undefined;
}): CohortTimeTravelerView {
  const breakdown = input.decisionView?.distributional?.breakdowns[0] ?? null;
  const rows = breakdown?.rows ?? [];
  const timeline = [
    {
      index: 0,
      label: "baseline",
      validAt: addDays(input.decisionView?.generatedAt, -30),
    },
    {
      index: 1,
      label: "decision",
      validAt: input.decisionView?.generatedAt ?? addDays(null, 0),
    },
    {
      index: 2,
      label: "policy-overlay",
      validAt: addDays(input.decisionView?.generatedAt, 30),
    },
  ];

  return {
    activeIndex: Math.min(
      Math.max(input.activeIndex ?? 1, 0),
      timeline.length - 1,
    ),
    filters: [
      {
        id: "dimension",
        label: "dimension",
        value: breakdown?.dimensionLabel ?? "decision-cohort",
      },
      {
        id: "policy",
        label: "policy",
        value: input.decisionView?.verdict ?? null,
      },
    ],
    policyOverlay: {
      ref: `policy-overlay:${input.decisionView?.runId ?? "unknown-run"}`,
      verdict: input.decisionView?.verdict ?? null,
    },
    timeline,
    transitions: rows.map(transitionForRow),
  };
}

const SCENE_SPECS = [
  {
    act: 1,
    id: "boring",
    labelKey: "phase33.stress.scenes.boring",
    priority: 10,
    reactionKey: "baseline",
  },
  {
    act: 2,
    id: "missing-data",
    labelKey: "phase33.stress.scenes.missingData",
    priority: 40,
    reactionKey: "dataWarning",
  },
  {
    act: 2,
    id: "adversarial-labels",
    labelKey: "phase33.stress.scenes.adversarialLabels",
    priority: 45,
    reactionKey: "review",
  },
  {
    act: 2,
    id: "ood-source",
    labelKey: "phase33.stress.scenes.oodSource",
    priority: 50,
    reactionKey: "transportWarning",
  },
  {
    act: 3,
    id: "legal-blocker",
    labelKey: "phase33.stress.scenes.legalBlocker",
    priority: 90,
    reactionKey: "block",
  },
  {
    act: 3,
    id: "fairness-blocker",
    labelKey: "phase33.stress.scenes.fairnessBlocker",
    priority: 85,
    reactionKey: "blockOrReview",
  },
  {
    act: 3,
    id: "stale-evidence",
    labelKey: "phase33.stress.scenes.staleEvidence",
    priority: 80,
    reactionKey: "freshnessWarning",
  },
] as const;

function issueMatchesScene(issue: GovernanceIssueView, sceneId: string) {
  const haystack =
    `${issue.code} ${issue.message} ${issue.passId ?? ""}`.toLowerCase();
  if (sceneId === "legal-blocker") {
    return haystack.includes("legal") || haystack.includes("law");
  }
  if (sceneId === "fairness-blocker") {
    return (
      haystack.includes("fair") ||
      haystack.includes("bias") ||
      haystack.includes("disparate")
    );
  }
  if (sceneId === "stale-evidence") {
    return haystack.includes("stale") || haystack.includes("fresh");
  }
  if (sceneId === "missing-data") {
    return (
      (haystack.includes("missing") && haystack.includes("data")) ||
      haystack.includes("incomplete_data")
    );
  }
  if (sceneId === "adversarial-labels") {
    return haystack.includes("adversarial") || haystack.includes("label");
  }
  if (sceneId === "ood-source") {
    return haystack.includes("ood") || haystack.includes("transport");
  }
  return false;
}

function statusForIssues(
  issues: GovernanceIssueView[],
): StressSceneDiagnosticDisplay {
  return stressSceneDiagnostic(
    issues.length > 0 ? "owner_issue_recorded" : "no_owner_issue_recorded",
  );
}

export function buildStressTestTheatreView(input: {
  decisionView: DecisionCardViewModel | null | undefined;
  evidenceContext?: RunEvidenceContext | null;
  governanceIssues?: GovernanceIssueView[];
  runId: string;
}): StressTestTheatreView {
  const issues = input.governanceIssues ?? [];
  const scenes = SCENE_SPECS.map<StressScene>((scene) => {
    const matchedIssues =
      scene.id === "boring"
        ? []
        : issues.filter((issue) => issueMatchesScene(issue, scene.id));
    const evidenceWarningHit =
      scene.id === "stale-evidence" &&
      Boolean(input.evidenceContext?.warnings.length);
    const actual = evidenceWarningHit
      ? stressSceneDiagnostic("evidence_warning_recorded")
      : statusForIssues(matchedIssues);
    const expected = stressSceneDiagnostic(
      scene.id === "boring"
        ? "baseline_no_issue"
        : "scenario_attention_expected",
    );
    return {
      act: scene.act,
      actual,
      diff: actual.label === "no_owner_issue_recorded" ? "same" : "degraded",
      expected,
      id: scene.id,
      immutableRef: `stress:${input.runId}:${scene.id}`,
      issueRefs: matchedIssues.map((issue) => issue.code),
      labelKey: scene.labelKey,
      policyChanged: null,
      priority: scene.priority,
      reactionKey: `phase33.stress.reaction.${scene.reactionKey}`,
    };
  });
  const citedScene =
    scenes
      .filter((scene) => scene.actual.label !== "no_owner_issue_recorded")
      .sort((a, b) => b.priority - a.priority)[0] ?? null;

  return {
    citedSceneRef: citedScene?.immutableRef ?? null,
    scenes,
    summary: {
      diagnosticFindings: scenes.filter(
        (scene) => scene.actual.label === "owner_issue_recorded",
      ).length,
      evidenceWarnings: scenes.filter(
        (scene) => scene.actual.label === "evidence_warning_recorded",
      ).length,
    },
  };
}

export function buildScientificDepthSnapshot(input: {
  activeCohortIndex?: number;
  decisionView: DecisionCardViewModel | null | undefined;
  evidenceContext?: RunEvidenceContext | null;
  governanceIssues?: GovernanceIssueView[];
  runId: string;
  sensitivityThreshold: number;
}): ScientificDepthSnapshot {
  return {
    cohort: buildCohortTimeTravelerView({
      activeIndex: input.activeCohortIndex,
      decisionView: input.decisionView,
    }),
    identifiability: buildIdentifiabilitySurfaceView({
      decisionView: input.decisionView,
      evidenceContext: input.evidenceContext,
    }),
    sensitivity: buildSensitivityRotorView({
      decisionView: input.decisionView,
      governanceIssues: input.governanceIssues,
      threshold: input.sensitivityThreshold,
    }),
    stress: buildStressTestTheatreView({
      decisionView: input.decisionView,
      evidenceContext: input.evidenceContext,
      governanceIssues: input.governanceIssues,
      runId: input.runId,
    }),
  };
}
