import type { ReactElement } from "react";

import { ConnectorCharacterCards } from "@/features/evidence/components/ConnectorCharacterCards";
import {
  buildConnectorCharacterCards,
  type ConnectorCharacterCard,
} from "@/features/evidence/domain/productionSlice";
import { AtlasRunDeck } from "@/features/runs/components/AtlasRunDeck";
import { PublicSectorReadinessPanel } from "@/features/runs/components/PublicSectorReadinessPanel";
import * as explainabilityModule from "@/features/runs/components/RunExplainabilityPanel";
import { PublicationPacketPanel } from "@/features/runs/components/PublicationPacketPanel";
import { ATLAS_STANDALONE_DECK_TEMPLATE } from "@/features/runs/domain/deckTemplate";
import {
  buildSignedPublicDecisionPacket,
  type SignedPublicDecisionPacket,
} from "@/features/runs/domain/publicationPacket";
import * as runSummaryModule from "@/features/runs/routes/useRunDetailSummary";
import { ChartQuantityEvidence } from "@/shared/charts/quantityChartSemantics";
import type { DecisionCardViewModel } from "@/shared/lib/domain/decision";
import { Quantity } from "@/shared/ui/quantity";
import { epochNonreceipt } from "@/shared/ui/temporal/TimeSemanticsLabel";
import {
  OUTER_SET_GAP_TOKEN,
  OUTER_SET_NO_ADMISSIBLE_RANKING_TOKEN,
  OuterSetValue,
  OuterSetValueStateCell,
} from "@/shared/ui/quantity/OuterSetValue";
import type { QuantityValue } from "@/shared/ui/quantity/quantity.types";

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

function publicationPacket(confidence: DecisionCardViewModel["confidence"]) {
  return buildSignedPublicDecisionPacket({
    decisionView: { ...baseDecisionView, confidence },
    epochSemantics: epochNonreceipt(),
    evidenceContext: null,
    governanceIssues: [],
    runId: "run-c06",
  });
}

function publicationFallbackQuantity(packet: SignedPublicDecisionPacket) {
  return (packet.deterministicExplanations[0] as UnknownRecord | undefined)
    ?.quantity;
}

const productionPath =
  "apps/runtime-dashboard/src/features/evidence/domain/productionSlice.ts";
const explainabilityPath =
  "apps/runtime-dashboard/src/features/runs/components/RunExplainabilityPanel.tsx";
const deckPath =
  "apps/runtime-dashboard/src/features/runs/domain/deckTemplate.ts";
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
  {
    column: 26,
    line: 420,
    path: "apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts",
  },
  {
    column: 28,
    line: 428,
    path: "apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts",
  },
  { column: 21, line: 384, path: explainabilityPath },
  { column: 13, line: 188, path: summaryPath },
  { column: 15, line: 190, path: summaryPath },
  { column: 17, line: 192, path: summaryPath },
  { column: 17, line: 193, path: summaryPath },
  { column: 52, line: 788, path: publicationPath },
  { column: 58, line: 788, path: publicationPath },
] as const;

export function renderRepresentativeProducerConsumers(): ReactElement[] {
  return quantityDecisionProducerProbes.flatMap((probe) =>
    probe.renderConsumer ? [probe.renderConsumer()] : [],
  );
}

export function renderContainedPublicSectorConsumer(): ReactElement {
  return <PublicSectorReadinessPanel runId="run-c06" />;
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

// ---------------------------------------------------------------------------
// DS16-C01 — value-grammar negatives: deliberately violating fixtures.
//
// A negative written over an empty set passes vacuously and proves nothing.
// Every fixture below commits exactly the sin one DS16-C01 negative forbids so
// that the negative can be observed RED on demand; correcting or removing the
// fixture turns it green. A negative that cannot be made to fail is not a
// negative, it is decoration (`P29` authorial proof in test clothing).
//
// `QuantityProducerProbe` above cannot express these: it identifies a producer
// quantity by `path:line:column` against the debt manifest and asserts a
// metric id and an expected point. A value-grammar negative has no source
// identity and no expected point — it discriminates a compliant render from a
// violating one. These therefore extend the harness with a second shape rather
// than forking a second registry (`P27`).
//
// Vocabulary is REFERENCED, never coined (constitution Rule 10):
//   ObservationProvenanceClass — src/polisyos/data_forge/domains/catalog/
//     knowledge/overlay.py:84-90 (observed | proxy | derived | model_output)
//   ValueOuterSetComparison — src/polisyos/core/contracts/value_outer_set.py:36
//     (dominates | incomparable | unknown)
// ---------------------------------------------------------------------------

export type ObservationProvenanceClass =
  | "observed"
  | "proxy"
  | "derived"
  | "model_output";

/** `value_outer_set.py:36` — the comparison verdict, not a rank. */
export type ValueOuterSetComparison = "dominates" | "incomparable" | "unknown";

/**
 * The three states DS16-C01 negative 5 must keep pairwise distinct. `gap` has
 * no representation in `Quantity` today (`data-quantity-presentation` is only
 * scalar | non-scalar | unknown) — that absence is the negative's subject.
 */
export type RenderedValueState = "zero" | "unknown" | "gap";

function grammarQuantity(
  metricId: string,
  overrides: Partial<QuantityValue> = {},
): QuantityValue {
  return {
    label: metricId,
    lineage: {
      freshness: "current",
      id: `lineage:${metricId}`,
      status: "verified",
    },
    metric_id: metricId,
    point: null,
    quantity_class: "decision",
    time: null,
    uncertainty: null,
    unit: { code: "1", display: "value", system: "ucum" },
    ...overrides,
  };
}

/** A two-member outer set: no admissible scalar summarises it. */
export const outerSetMembers: readonly QuantityValue[] = [
  grammarQuantity("ds16.outer_set.lower_support", { point: -0.3 }),
  grammarQuantity("ds16.outer_set.upper_support", { point: 0.7 }),
];

export const zeroValuedQuantity = grammarQuantity("ds16.zero_reference", {
  point: 0,
});

export const unknownValuedQuantity = grammarQuantity("ds16.unknown_reference");

/**
 * Fixture copy is rendered as i18n-key-shaped TOKENS, never as prose. The
 * catalog under `shared/i18n/**` is DS6's exclusive territory, so this slice
 * may not add keys to it, and squatting on the eventual product wording here
 * would be a worse answer than not writing it: these negatives discriminate on
 * the rendered SIGNATURE, and the signature does not need English to be
 * distinct. C07/C08 resolve these tokens through DS6's catalog when the copy
 * is actually owned.
 */
// C07 moved these into the production component that renders them; the harness re-exports
// so C01's expectations bind the real tokens rather than a test-local copy of them.
export const GAP_STATE_TOKEN = OUTER_SET_GAP_TOKEN;
export const NO_ADMISSIBLE_RANKING_TOKEN =
  OUTER_SET_NO_ADMISSIBLE_RANKING_TOKEN;

// -- negative 1: a set-valued value rendered as a point estimate -------------

/** Compliant: the production seam keeps every member and declares cardinality. */
export function renderOuterSetAsSet(): ReactElement {
  // C07: the real family, which composes the existing set-vs-point seam rather than
  // reducing the members first.
  return <OuterSetValue comparison={null} members={outerSetMembers} />;
}

/**
 * VIOLATING: collapses the outer set to the midpoint of its supports and
 * renders one scalar. No cardinality is declared and the set is gone.
 */
export function renderOuterSetCollapsedToPoint(): ReactElement {
  const points = outerSetMembers.map((member) => member.point ?? 0);
  const midpoint =
    points.reduce((total, point) => total + point, 0) / points.length;
  return (
    <Quantity
      value={grammarQuantity("ds16.outer_set.collapsed", { point: midpoint })}
      provenanceMode="off"
    />
  );
}

// -- negative 2: a derived series rendered without its provenance class ------

function ProvenanceMarkedSeries({
  observationClass,
  series,
}: {
  observationClass: ObservationProvenanceClass;
  series: readonly QuantityValue[];
}) {
  return (
    <span
      data-observation-class={observationClass}
      data-testid="ds16-provenance-series"
    >
      <ChartQuantityEvidence value={series} />
    </span>
  );
}

const derivedSeries: readonly QuantityValue[] = [
  grammarQuantity("ds16.derived.q1", { point: 1.1 }),
  grammarQuantity("ds16.derived.q2", { point: 1.4 }),
];

/** Compliant: the derived series carries its class where it is rendered. */
export function renderDerivedSeriesWithProvenanceClass(): ReactElement {
  return (
    <ProvenanceMarkedSeries observationClass="derived" series={derivedSeries} />
  );
}

/** VIOLATING: same derived numbers, no provenance class anywhere on the glass. */
export function renderDerivedSeriesWithoutProvenanceClass(): ReactElement {
  return (
    <span data-testid="ds16-provenance-series">
      <ChartQuantityEvidence value={derivedSeries} />
    </span>
  );
}

// -- negative 3: a class-(iv) model output styled as observed data -----------

const modelOutputValue = grammarQuantity("ds16.model_output.projection", {
  point: 0.42,
});

/**
 * Compliant: a model output is marked `model_output`. `overlay.py` makes this
 * the fourth `ObservationProvenanceClass` member — the master plan's
 * "class-(iv)" — and `acquisition_executor.py:1719` refuses its admission as
 * an observation with `model_output_not_observation`.
 */
export function renderModelOutputAsModelOutput(): ReactElement {
  return (
    <ProvenanceMarkedSeries
      observationClass="model_output"
      series={[modelOutputValue]}
    />
  );
}

/** VIOLATING: a class-(iv) model output wearing the `observed` class. */
export function renderModelOutputStyledAsObserved(): ReactElement {
  return (
    <ProvenanceMarkedSeries
      observationClass="observed"
      series={[modelOutputValue]}
    />
  );
}

// -- negative 5: unknown, zero and gap are three states, not two -------------

/** C07: the real component now renders every value-state cell, compliant and violating
 * alike, so the negatives discriminate production code rather than fixture markup. */
function ValueStateCell({
  state,
  value,
}: {
  state: RenderedValueState;
  value: QuantityValue;
}) {
  return <OuterSetValueStateCell state={state} value={value} />;
}

/** Compliant: three states, three distinct rendered signatures. */
export function renderThreeDistinctValueStates(): ReactElement {
  return (
    <div>
      <ValueStateCell state="zero" value={zeroValuedQuantity} />
      <ValueStateCell state="unknown" value={unknownValuedQuantity} />
      <ValueStateCell state="gap" value={unknownValuedQuantity} />
    </div>
  );
}

/** VIOLATING: `unknown` is rendered as the number zero. */
export function renderUnknownAsZero(): ReactElement {
  return (
    <div>
      <ValueStateCell state="zero" value={zeroValuedQuantity} />
      <ValueStateCell state="unknown" value={zeroValuedQuantity} />
      <ValueStateCell state="gap" value={unknownValuedQuantity} />
    </div>
  );
}

/** VIOLATING: `unknown` is rendered as the gap, erasing the distinction. */
export function renderUnknownAsGap(): ReactElement {
  return (
    <div>
      <ValueStateCell state="zero" value={zeroValuedQuantity} />
      <ValueStateCell state="gap" value={unknownValuedQuantity} />
      <ValueStateCell state="gap" value={unknownValuedQuantity} />
    </div>
  );
}

/** VIOLATING: a gap is rendered as the number zero. */
export function renderGapAsZero(): ReactElement {
  return (
    <div>
      <ValueStateCell state="zero" value={zeroValuedQuantity} />
      <ValueStateCell state="unknown" value={unknownValuedQuantity} />
      <ValueStateCell state="zero" value={zeroValuedQuantity} />
    </div>
  );
}

// -- negative 6: `incomparable` rendered as a ranking ------------------------

/**
 * Compliant: an `incomparable` verdict renders the frontier with no order —
 * no list ordinals, no rank, no set-position semantics.
 */
export function renderIncomparableAsFrontier(): ReactElement {
  // C07: the real family renders this. `incomparable` is a producer verdict about the
  // VALUES; the family has no ranking path at all, because the authorization type that
  // would license one does not exist.
  return <OuterSetValue comparison="incomparable" members={outerSetMembers} />;
}

/** VIOLATING: the same incomparable members sorted and given rank positions. */
export function renderIncomparableAsRanking(): ReactElement {
  const ranked = [...outerSetMembers].sort(
    (left, right) => (right.point ?? 0) - (left.point ?? 0),
  );
  return (
    <ol data-comparison="incomparable" data-testid="ds16-comparison">
      {ranked.map((member, index) => (
        <li
          aria-posinset={index + 1}
          aria-setsize={ranked.length}
          data-rank={index + 1}
          key={member.metric_id}
        >
          <Quantity provenanceMode="off" value={member} />
        </li>
      ))}
    </ol>
  );
}
