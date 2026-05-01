import type { RunEvidenceContext } from "@/lib/domain/evidence";
import type {
  DecisionCardViewModel,
  DecisionDistributionalRow,
  DecisionMetric,
} from "@/lib/domain/decision";
import type { GovernanceIssueView } from "@/lib/domain/governance";

export type IdentifiabilityState =
  | "point"
  | "partial"
  | "set"
  | "not_identified";

export type IdentificationRemedy = {
  effort: "low" | "medium" | "high";
  kind: "dataset" | "rct" | "iv" | "covariate" | "panel" | "measurement";
  ref: string;
};

export type IdentifiabilityCell = {
  assumptionCount: number;
  bounds: {
    lower: number | null;
    method: "confidence_interval" | "manski" | "robins" | "point" | "unknown";
    upper: number | null;
  };
  decisionImpact: {
    policyRecommendations: number;
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
  summary: Record<IdentifiabilityState, number>;
  totalCells: number;
  totalDecisionBearingQuantities: number;
  weakestCellId: string | null;
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
  verdictChanged: boolean;
  claims: SensitivityClaim[];
};

export type CohortTransition = {
  baselineShare: number;
  cohortId: string;
  cohortLabel: string;
  fromState: string;
  observedShare: number;
  overlayShare: number;
  policyEffect: "pass" | "fail" | "review";
  timeIndex: number;
  toState: string;
};

export type CohortTimeTravelerView = {
  activeIndex: number;
  filters: Array<{ id: string; label: string; value: string }>;
  policyOverlay: {
    ref: string;
    verdict: string;
  };
  timeline: Array<{ index: number; label: string; validAt: string | null }>;
  transitions: CohortTransition[];
};

export type StressSceneStatus = "pass" | "warn" | "block";

export type StressScene = {
  act: 1 | 2 | 3;
  actual: StressSceneStatus;
  diff: "same" | "degraded" | "improved";
  expected: StressSceneStatus;
  id: string;
  immutableRef: string;
  issueRefs: string[];
  labelKey: string;
  policyChanged: boolean;
  priority: number;
  reactionKey: string;
};

export type StressTestTheatreView = {
  citedSceneRef: string | null;
  scenes: StressScene[];
  summary: {
    blocked: number;
    warned: number;
  };
};

export type ScientificDepthSnapshot = {
  cohort: CohortTimeTravelerView;
  identifiability: IdentifiabilitySurfaceView;
  sensitivity: SensitivityRotorView;
  stress: StressTestTheatreView;
};

const STATE_RANK: Record<IdentifiabilityState, number> = {
  point: 0,
  partial: 1,
  set: 2,
  not_identified: 3,
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

function identifiabilityState(metric: DecisionMetric): IdentifiabilityState {
  const hasBounds =
    typeof metric.ciLower === "number" && typeof metric.ciUpper === "number";
  const hasWarnings = Boolean(metric.assumptionWarnings?.length);

  if (hasWarnings && hasBounds) {
    return "partial";
  }
  if (hasWarnings) {
    return "set";
  }
  if (!hasBounds) {
    return "not_identified";
  }
  return "point";
}

function remedyForCell(
  state: IdentifiabilityState,
  context: RunEvidenceContext | null | undefined,
): IdentificationRemedy {
  if (state === "point") {
    return {
      effort: "low",
      kind: "measurement",
      ref: context?.promotionCandidates[0]?.promotionId ?? "audit-current-data",
    };
  }
  if (state === "partial") {
    return {
      effort: "medium",
      kind: "covariate",
      ref: context?.fetchPlans[0]?.planId ?? "add-confounder-covariate",
    };
  }
  if (state === "set") {
    return {
      effort: "high",
      kind: "iv",
      ref: context?.dataNeeds[0]?.needId ?? "find-valid-instrument",
    };
  }
  return {
    effort: "high",
    kind: context?.dataNeeds.length ? "dataset" : "rct",
    ref: context?.dataNeeds[0]?.needId ?? "create-identifying-study",
  };
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

  if (state === "point") {
    return [
      { effort: "low", kind: "measurement", ref: "audit-current-data" },
      { effort: "low", kind: "dataset", ref: promotionRef },
    ];
  }
  if (state === "partial") {
    return [
      { effort: "medium", kind: "covariate", ref: planRef },
      { effort: "medium", kind: "panel", ref: needRef },
      { effort: "high", kind: "rct", ref: "design-targeted-rct" },
    ];
  }
  if (state === "set") {
    return [
      { effort: "high", kind: "iv", ref: needRef },
      { effort: "high", kind: "rct", ref: "design-encouragement-study" },
      { effort: "medium", kind: "panel", ref: planRef },
    ];
  }
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

function boundsMethodForMetric(
  metric: DecisionMetric,
  state: IdentifiabilityState,
): IdentifiabilityCell["bounds"]["method"] {
  const hasBounds =
    typeof metric.ciLower === "number" && typeof metric.ciUpper === "number";
  if (hasBounds && state === "partial") {
    return "robins";
  }
  if (hasBounds) {
    return "confidence_interval";
  }
  if (state === "set") {
    return "manski";
  }
  if (state === "point") {
    return "point";
  }
  return "unknown";
}

export function buildIdentifiabilitySurfaceView(input: {
  decisionView: DecisionCardViewModel | null | undefined;
  evidenceContext?: RunEvidenceContext | null;
}): IdentifiabilitySurfaceView {
  const metrics = input.decisionView?.keyMetrics ?? [];
  const cells = metrics.map<IdentifiabilityCell>((metric, index) => {
    const state = identifiabilityState(metric);
    const id = metricId(metric, index);
    return {
      assumptionCount: metric.assumptionWarnings?.length ?? 0,
      bounds: {
        lower: metric.ciLower,
        method: boundsMethodForMetric(metric, state),
        upper: metric.ciUpper,
      },
      decisionImpact: {
        policyRecommendations: state === "point" ? 0 : 1,
        quantities: 1 + (metric.assumptionWarnings?.length ?? 0),
      },
      id,
      label: metric.name,
      remedy: remedyForCell(state, input.evidenceContext),
      remedies: remedyCandidatesForCell(state, input.evidenceContext),
      state,
    };
  });
  const weakestCell =
    [...cells].sort(
      (a, b) =>
        STATE_RANK[b.state] - STATE_RANK[a.state] ||
        b.decisionImpact.quantities - a.decisionImpact.quantities,
    )[0] ?? null;

  return {
    cells,
    summary: cells.reduce<Record<IdentifiabilityState, number>>(
      (acc, cell) => {
        acc[cell.state] += 1;
        return acc;
      },
      {
        point: 0,
        partial: 0,
        set: 0,
        not_identified: 0,
      },
    ),
    totalCells: cells.length,
    totalDecisionBearingQuantities: cells.reduce(
      (total, cell) => total + cell.decisionImpact.quantities,
      0,
    ),
    weakestCellId: weakestCell?.id ?? null,
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
  const verdictChanged =
    input.decisionView?.verdict === "APPROVE" &&
    claims.length > 0 &&
    decisionBearingExtinguishedShare >= 0.5;

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
    verdictChanged,
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
  const policyEffect =
    row.primaryDelta > 0 ? "pass" : row.primaryDelta < 0 ? "fail" : "review";
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
      policyEffect === "pass"
        ? "eligible-under-policy"
        : policyEffect === "fail"
          ? "at-risk-under-policy"
          : "review-under-policy",
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
        value: input.decisionView?.verdict ?? "REVIEW",
      },
    ],
    policyOverlay: {
      ref: `policy-overlay:${input.decisionView?.runId ?? "unknown-run"}:${input.decisionView?.verdict ?? "REVIEW"}`,
      verdict: input.decisionView?.verdict ?? "REVIEW",
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

function statusForIssues(issues: GovernanceIssueView[]): StressSceneStatus {
  if (issues.some((issue) => issue.severity === "blocker")) {
    return "block";
  }
  if (issues.length > 0) {
    return "warn";
  }
  return "pass";
}

function statusRank(status: StressSceneStatus) {
  if (status === "block") {
    return 2;
  }
  if (status === "warn") {
    return 1;
  }
  return 0;
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
    const actual = evidenceWarningHit ? "warn" : statusForIssues(matchedIssues);
    const expected: StressSceneStatus = scene.id === "boring" ? "pass" : "warn";
    return {
      act: scene.act,
      actual,
      diff:
        actual === expected
          ? "same"
          : actual === "block"
            ? "degraded"
            : "improved",
      expected,
      id: scene.id,
      immutableRef: `stress:${input.runId}:${scene.id}`,
      issueRefs: matchedIssues.map((issue) => issue.code),
      labelKey: scene.labelKey,
      policyChanged:
        input.decisionView?.verdict === "APPROVE" && actual === "block",
      priority: scene.priority,
      reactionKey: `phase33.stress.reaction.${scene.reactionKey}`,
    };
  });
  const citedScene =
    scenes
      .filter((scene) => scene.actual === "block" || scene.actual === "warn")
      .sort(
        (a, b) =>
          statusRank(b.actual) - statusRank(a.actual) ||
          b.priority - a.priority,
      )[0] ?? null;

  return {
    citedSceneRef: citedScene?.immutableRef ?? null,
    scenes,
    summary: {
      blocked: scenes.filter((scene) => scene.actual === "block").length,
      warned: scenes.filter((scene) => scene.actual === "warn").length,
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
