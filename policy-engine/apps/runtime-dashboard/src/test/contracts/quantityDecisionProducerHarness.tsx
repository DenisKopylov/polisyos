import type { ReactElement } from "react";

import { ConnectorCharacterCards } from "@/features/evidence/components/ConnectorCharacterCards";
import {
  buildConnectorCharacterCards,
  type ConnectorCharacterCard,
} from "@/features/evidence/domain/productionSlice";
import { AtlasRunDeck } from "@/features/runs/components/AtlasRunDeck";
import * as explainabilityModule from "@/features/runs/components/RunExplainabilityPanel";
import { PublicSectorReadinessPanel } from "@/features/runs/components/PublicSectorReadinessPanel";
import { PublicationPacketPanel } from "@/features/runs/components/PublicationPacketPanel";
import { ATLAS_STANDALONE_DECK_TEMPLATE } from "@/features/runs/domain/deckTemplate";
import {
  buildFairnessAuditView,
  buildPublicSectorReadinessSnapshot,
  createDefaultReviewAttentionState,
} from "@/features/runs/domain/publicSectorReadiness";
import {
  buildSignedPublicDecisionPacket,
  type SignedPublicDecisionPacket,
} from "@/features/runs/domain/publicationPacket";
import * as runSummaryModule from "@/features/runs/routes/useRunDetailSummary";
import type { DecisionCardViewModel } from "@/shared/lib/domain/decision";
import type { GovernanceIssueView } from "@/shared/lib/domain/governance";

type UnknownRecord = Record<string, unknown>;

export type QuantityProducerProbe = {
  column: number;
  expectedMetricId: string;
  expectedPoint: number | null;
  line: number;
  path: string;
  read: () => unknown;
  renderConsumer?: () => ReactElement;
};

const baseDecisionView: DecisionCardViewModel = {
  confidence: "HIGH",
  diagnosticsBadges: [],
  distributional: null,
  generatedAt: "2026-04-01T12:00:00.000Z",
  interventionCount: 1,
  issues: {
    blockedPasses: [],
    blockerCount: 0,
    infoCount: 0,
    warningCount: 0,
  },
  keyMetrics: [],
  metricComparisons: [],
  metricValidationFamilyAdjustment: null,
  policySummary: "Candidate policy summary.",
  runId: "run-c06",
  sourceKind: "decision_packet",
  totalDurationMs: 10,
  verdict: "REVIEW",
};

const governanceIssue: GovernanceIssueView = {
  code: "fairness_gap",
  durationMs: 10,
  message: "Protected cohort evidence is incomplete.",
  passId: "fairness-pass",
  path: null,
  raw: {},
  severity: "blocker",
};

function offlineConnectorCards(): ConnectorCharacterCard[] {
  return buildConnectorCharacterCards({
    connectors: [
      {
        connector_id: "offline",
        known_datasets: [],
        last_health_check: null,
        loaded: false,
        namespace: "offline",
        version: "0.0.0",
      },
    ],
    profiles: [],
    runContext: null,
  });
}

function explainabilityQuantities(): UnknownRecord {
  const candidate = explainabilityModule as UnknownRecord;
  const builder = candidate.buildRunExplainabilityDecisionQuantities;
  if (typeof builder !== "function") {
    return {};
  }
  return builder({
    ...baseDecisionView,
    blockerCount: 0,
    decisionScore: null,
    decisionView: baseDecisionView,
    impactRows: [],
  }) as UnknownRecord;
}

function runDecisionScore(input: {
  confidence: DecisionCardViewModel["confidence"] | null;
  point?: number | null;
}) {
  const candidate = runSummaryModule as UnknownRecord;
  const builder = candidate.resolveRunDecisionScoreQuantity;
  if (typeof builder !== "function") {
    return undefined;
  }
  return builder({
    confidence: input.confidence,
    generatedAt: "2026-04-01T12:00:00.000Z",
    point: input.point ?? null,
    runId: "run-c06",
  });
}

function runExplainabilityConsumer(input: {
  confidence: DecisionCardViewModel["confidence"] | null;
  point?: number | null;
}): ReactElement {
  const decisionScore = runDecisionScore(input);
  return (
    <explainabilityModule.RunExplainabilityPanel
      level="deep"
      summary={
        {
          artifactRefs: [],
          blockerCount: 0,
          decisionHeadline: "Candidate policy summary.",
          decisionScore,
          decisionView: baseDecisionView,
          evidenceContext: null,
          governanceIssues: [],
          governanceSummary: null,
          impactRows: [
            {
              display: "+0.1",
              label: "Illustrative impact",
              value: 0.1,
            },
          ],
          pipeline: null,
          primaryIssue: null,
          run: null,
          transportStatus: "ready",
        } as never
      }
    />
  );
}

function fairnessIssueView() {
  return buildFairnessAuditView({
    decisionView: null,
    governanceIssues: [governanceIssue],
  });
}

function missingFairnessView() {
  return buildFairnessAuditView({
    decisionView: null,
    governanceIssues: [],
  });
}

function publicationPacket(confidence: DecisionCardViewModel["confidence"]) {
  return buildSignedPublicDecisionPacket({
    decisionView: { ...baseDecisionView, confidence },
    evidenceContext: null,
    governanceIssues: [],
    runId: "run-c06",
  });
}

function lowConfidenceScore(packet: SignedPublicDecisionPacket) {
  return packet.confidenceLadder.find((item) => item.rung === "low_confidence")
    ?.score;
}

function publicationFallbackQuantity(packet: SignedPublicDecisionPacket) {
  return (packet.deterministicExplanations[0] as UnknownRecord | undefined)
    ?.quantity;
}

function publicSectorSnapshot() {
  return buildPublicSectorReadinessSnapshot({
    decisionView: null,
    disputes: [],
    evidenceContext: null,
    governanceIssues: [],
    lens: "operator",
    now: "2026-04-01T12:00:00.000Z",
    reviewState: createDefaultReviewAttentionState(),
    runId: "run-c06",
  });
}

const productionPath =
  "apps/runtime-dashboard/src/features/evidence/domain/productionSlice.ts";
const explainabilityPath =
  "apps/runtime-dashboard/src/features/runs/components/RunExplainabilityPanel.tsx";
const deckPath =
  "apps/runtime-dashboard/src/features/runs/domain/deckTemplate.ts";
const readinessPath =
  "apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts";
const publicationPath =
  "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts";
const summaryPath =
  "apps/runtime-dashboard/src/features/runs/routes/useRunDetailSummary.ts";

export const quantityDecisionProducerProbes: QuantityProducerProbe[] = [
  {
    column: 9,
    expectedMetricId: "connector.offline.error_budget_burn",
    expectedPoint: 1,
    line: 264,
    path: productionPath,
    read: () => offlineConnectorCards()[0]?.errorBudgetBurn,
    renderConsumer: () => (
      <ConnectorCharacterCards cards={offlineConnectorCards()} />
    ),
  },
  {
    column: 18,
    expectedMetricId: "run.attribution.baseline",
    expectedPoint: 0,
    line: 323,
    path: explainabilityPath,
    read: () => explainabilityQuantities().attributionBaseline,
    renderConsumer: () =>
      runExplainabilityConsumer({ confidence: "HIGH", point: 0.84 }),
  },
  {
    column: 16,
    expectedMetricId: "run.attribution.baseline",
    expectedPoint: 0,
    line: 329,
    path: explainabilityPath,
    read: () => explainabilityQuantities().attributionBaseline,
    renderConsumer: () =>
      runExplainabilityConsumer({ confidence: "HIGH", point: 0.84 }),
  },
  {
    column: 20,
    expectedMetricId: "template.decision_score",
    expectedPoint: 0.78,
    line: 60,
    path: deckPath,
    read: () => ATLAS_STANDALONE_DECK_TEMPLATE.report.decisionScore,
    renderConsumer: () => (
      <AtlasRunDeck deck={ATLAS_STANDALONE_DECK_TEMPLATE} />
    ),
  },
  ...[
    [66, 16, "template.household_stability_delta", 1.8, 0],
    [71, 17, "template.administrative_load_delta", -0.6, 1],
    [76, 16, "template.coverage_confidence_delta", 2.1, 2],
  ].map(([line, column, expectedMetricId, expectedPoint, index]) => ({
    column: column as number,
    expectedMetricId: expectedMetricId as string,
    expectedPoint: expectedPoint as number,
    line: line as number,
    path: deckPath,
    read: () =>
      (
        ATLAS_STANDALONE_DECK_TEMPLATE.report.impactRows[index as number] as
          | UnknownRecord
          | undefined
      )?.quantity,
    renderConsumer: () => (
      <AtlasRunDeck deck={ATLAS_STANDALONE_DECK_TEMPLATE} />
    ),
  })),
  {
    column: 26,
    expectedMetricId: "fairness.primary_delta.issue_fallback",
    expectedPoint: -0.12,
    line: 420,
    path: readinessPath,
    read: () =>
      (fairnessIssueView().groups[0] as UnknownRecord | undefined)
        ?.primaryDelta,
    renderConsumer: () => (
      <PublicSectorReadinessPanel
        runId="run-c06"
        summary={
          {
            decisionView: null,
            evidenceContext: null,
            governanceIssues: [governanceIssue],
          } as never
        }
      />
    ),
  },
  {
    column: 28,
    expectedMetricId: "fairness.primary_delta.missing_evidence",
    expectedPoint: -0.5,
    line: 428,
    path: readinessPath,
    read: () =>
      (missingFairnessView().groups[0] as UnknownRecord | undefined)
        ?.primaryDelta,
    renderConsumer: () => (
      <PublicSectorReadinessPanel
        runId="run-c06"
        summary={
          {
            decisionView: null,
            evidenceContext: null,
            governanceIssues: [],
          } as never
        }
      />
    ),
  },
  {
    column: 52,
    expectedMetricId: "public.confidence_ladder.low_confidence.score",
    expectedPoint: 0.2,
    line: 788,
    path: publicationPath,
    read: () => lowConfidenceScore(publicationPacket("LOW")),
    renderConsumer: () => (
      <PublicationPacketPanel packet={publicationPacket("LOW")} />
    ),
  },
  {
    column: 58,
    expectedMetricId: "public.confidence_ladder.low_confidence.score",
    expectedPoint: 0.7,
    line: 788,
    path: publicationPath,
    read: () => lowConfidenceScore(publicationPacket("HIGH")),
    renderConsumer: () => (
      <PublicationPacketPanel packet={publicationPacket("HIGH")} />
    ),
  },
  {
    column: 18,
    expectedMetricId: "public.decision_metric.fallback",
    expectedPoint: null,
    line: 851,
    path: publicationPath,
    read: () => publicationFallbackQuantity(publicationPacket("HIGH")),
    renderConsumer: () => (
      <PublicationPacketPanel packet={publicationPacket("HIGH")} />
    ),
  },
];

export const removedAuthorityGuessIdentities = [
  { column: 21, line: 384, path: explainabilityPath },
  { column: 13, line: 188, path: summaryPath },
  { column: 15, line: 190, path: summaryPath },
  { column: 17, line: 192, path: summaryPath },
  { column: 17, line: 193, path: summaryPath },
] as const;

export function renderRepresentativeProducerConsumers(): ReactElement[] {
  return quantityDecisionProducerProbes.flatMap((probe) =>
    probe.renderConsumer ? [probe.renderConsumer()] : [],
  );
}

export function renderTypedFixtureAuthorityConsumer(): ReactElement {
  return <AtlasRunDeck deck={ATLAS_STANDALONE_DECK_TEMPLATE} />;
}

export function readKnownConfidenceWithoutScore() {
  return runDecisionScore({ confidence: "HIGH" });
}

export function readAbsentDecisionScore() {
  return runDecisionScore({ confidence: null });
}

export function renderKnownConfidenceWithoutScoreConsumer(): ReactElement {
  return runExplainabilityConsumer({ confidence: "HIGH" });
}

export function renderAbsentDecisionScoreConsumer(): ReactElement {
  return runExplainabilityConsumer({ confidence: null });
}

export function renderUntracedNumericScoreConsumer(): ReactElement {
  return runExplainabilityConsumer({ confidence: "HIGH", point: 0.84 });
}

export const typedFixtureAuthority =
  ATLAS_STANDALONE_DECK_TEMPLATE.fixture_authority;

export const quantityControlIdentities = [
  { column: 39, line: 617, path: publicationPath },
  { column: 39, line: 713, path: publicationPath },
  {
    column: 28,
    line: 255,
    path: "apps/runtime-dashboard/src/shared/lib/domain/simulation.ts",
  },
] as const;
