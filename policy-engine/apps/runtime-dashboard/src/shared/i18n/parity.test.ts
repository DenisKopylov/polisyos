import crypto from "node:crypto";
import { IntlMessageFormat } from "intl-messageformat";

import { formatIcuMessage, isPluralMessage } from "./messages/icu-messages";
import en from "./locales/en.json";
import ru from "./locales/ru.json";
import uk from "./locales/uk.json";
import { PRIMARY_LOCALE } from "./locale";

type Catalog = Record<string, unknown>;

function comparePaths(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

function collectPaths(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value == null || Array.isArray(value)) {
    return prefix ? [prefix] : [];
  }

  return Object.entries(value as Catalog).flatMap(([key, nested]) =>
    collectPaths(nested, prefix ? `${prefix}.${key}` : key),
  );
}

const COUNT_MESSAGE_ALLOWLIST = new Map<string, string>([
  [
    "pages.dashboard.toolbar.addWidget",
    "Parenthesized badge counter; the imperative label does not agree with the count.",
  ],
  [
    "pages.dashboard.toolbar.views",
    "Parenthesized badge counter; `Views` is a fixed toolbar label.",
  ],
  [
    "pages.composer.planSummary",
    "Numeric NL-iteration cap value; it is not a noun-bearing quantity phrase.",
  ],
  [
    "pages.cycleBoard.confidenceLedger.positiveEmpty.status",
    "The count modifies the invariant issued-status predicate; no counted noun changes form in either active locale.",
  ],
  [
    "pages.runs.activeRunAnnouncement",
    "Count is the total denominator in “row … of”; it has no agreeing noun.",
  ],
  ["pages.runs.pageCount", "Machine-readable `name=value` pagination metric."],
  [
    "pages.runs.pageCountWithTotal",
    "Machine-readable pagination metric paired with a total.",
  ],
  [
    "pages.runs.missingRefs",
    "Postfixed diagnostic tally; fixed technical label rather than a quantified phrase.",
  ],
  [
    "pages.runs.blockers",
    "Postfixed diagnostic tally; fixed technical label rather than a quantified phrase.",
  ],
  [
    "pages.platform.registeredConnectors",
    "Predicative status “registered”; no noun form is selected by count.",
  ],
  [
    "panels.reviewCollaboration.reviewers",
    "Declared, unenforced: the only tracked caller currently selects this key when `participants.length > 1`; singular uses `panels.reviewCollaboration.solo`, but no witness binds that caller guard.",
  ],
  [
    "panels.dataIntelligence.catalogMatches",
    "Colon-delimited result metric; the count is not adjacent to the fixed label.",
  ],
  [
    "panels.dataIntelligence.discoverCandidates",
    "Parenthesized action badge; the action label does not agree with count.",
  ],
  ["panels.agentPipeline.diagnostics", "Colon-delimited diagnostic metric."],
  [
    "panels.agentPipeline.iteration",
    "Iteration identifier, not a noun quantity.",
  ],
  [
    "panels.agentPipeline.overBudget",
    "Numeric budget delta with an invariant predicate, not a counted noun.",
  ],
  ["panels.errors.total", "Aggregate total metric with no agreeing noun."],
  [
    "panels.nodeDebug.timelineEvents",
    "Parenthesized badge counter; the timeline label is fixed.",
  ],
  [
    "shared.ui.quantity.miniGraph.hidden",
    "Generic `{kind}` supplies the noun; this template cannot choose its inflection.",
  ],
  [
    "collaboration.toolbar.onlineCount",
    "Online-status predicate, not a noun quantity.",
  ],
  [
    "controlJob.humanReviewUnresolved",
    "Postfixed summary tally for a fixed diagnostic-status label.",
  ],
]);

const NUMERIC_VARIABLE_REASONS = new Map<string, string>([
  ["accepted", "Accepted-item numerator in an accepted/total ratio."],
  ["accuracy", "Measured correctness proportion."],
  ["act", "Ordinal Act number."],
  ["actual", "Measured value, including elapsed seconds."],
  ["after", "Numeric endpoint of a before/after range."],
  ["alpha", "Statistical alpha scalar."],
  ["artifacts", "Artifact cardinality in count-bearing summary uses."],
  ["attempt", "Ordinal attempt number."],
  ["available", "Available-profile cardinality."],
  ["before", "Numeric endpoint of a before/after range."],
  ["bindings", "Binding cardinality."],
  ["bins", "Quantile-dot bin cardinality."],
  ["blocked", "Blocked-item tally."],
  ["blockers", "Blocker tally."],
  ["budget", "Quantitative budget denominator."],
  ["candidates", "Candidate cardinality."],
  ["completed", "Progress numerator."],
  [
    "completeness",
    "Preview completeness proportion formatted as a percentage.",
  ],
  ["confidence", "Confidence percentage or out-of-100 quantity."],
  ["cost", "Price per million."],
  ["depth", "Graph or workflow depth."],
  ["docs", "Document cardinality."],
  ["duration", "Time quantity, sometimes preformatted."],
  ["durationMs", "Duration in milliseconds."],
  ["eValue", "E-value scalar."],
  ["events", "Event cardinality."],
  [
    "fallbacks",
    "Fallback-plan cardinality derived from the caller array length.",
  ],
  ["fps", "Frames-per-second quantity."],
  ["index", "Ordinal section, note, or timeline position."],
  ["info", "Informational-issue tally."],
  ["interval", "Preformatted numeric confidence-interval range."],
  ["lag", "Time-lag quantity."],
  ["latency", "Latency in milliseconds."],
  ["level", "Confidence percentage."],
  ["losers", "Population-share quantity."],
  ["lower", "Numeric interval lower bound."],
  ["maxNodes", "Numeric node-rendering threshold."],
  ["minimum", "Minimum contrast ratio."],
  ["needs", "Need cardinality."],
  ["nodes", "Graph-node cardinality."],
  ["observed", "Observed budget quantity."],
  ["p10", "Tenth-percentile value."],
  ["p90", "Ninetieth-percentile value."],
  ["parameters", "Parameter cardinality."],
  ["percent", "Explicit percentage."],
  ["plans", "Plan cardinality."],
  ["policies", "Policy-recommendation cardinality."],
  ["position", "Row ordinal."],
  ["positivePct", "Explicit positive percentage."],
  ["promotions", "Promotion cardinality."],
  ["priority", "Numeric intervention priority from the typed Trinity domain."],
  ["quality", "Quality-floor scalar."],
  ["quantities", "Estimated-quantity cardinality."],
  ["rate", "Success-rate quantity."],
  ["ratio", "Numeric ratio."],
  ["required", "Required dwell seconds."],
  ["rows", "Row cardinality."],
  ["score", "Numeric score or floor."],
  ["seconds", "Explicit seconds."],
  ["selected", "Selected-profile cardinality."],
  ["share", "Cohort or population share."],
  ["strength", "Explicit percentage strength."],
  ["success", "Successful-outcome cardinality."],
  ["target", "Section count at one use; identifier or value elsewhere."],
  ["threshold", "E-value or fairness threshold scalar."],
  ["total", "Count or ratio denominator."],
  ["upper", "Numeric interval upper bound."],
  ["value", "Count-bearing in selected Phase 32/34 uses; generic elsewhere."],
  ["warned", "Warning tally."],
  ["warnings", "Warning tally."],
  ["winners", "Population-share quantity."],
]);

const NUMERIC_VARIABLE_KEY_SET_SHA256 =
  "c60120b6795593d5f5b84b83353e2c1d02c7ea568e8e48e146942aadbfdf3517";

const NON_NUMERIC_VARIABLE_REASONS = new Map<string, string>(
  `actor
affected
alias
artifactId
artifactKind
ast
authority
baseRunId
basis
code
connector
coverage
createdAt
dataset
date
diff
direction
effort
engine
filename
focus
from
group
hash
hints
how
kind
known
label
lane
likelihood
method
methodology
metric
mode
name
namespace
needId
next
outputDir
parity
passId
path
planId
policy
promotionId
query
reaction
reason
reasons
ref
refs
requestId
residual
runId
scenarioId
significance
skeleton
source
sourceKind
state
status
targetRunId
time
timestamp
title
to
txAt
type
unlock
updatedAt
valid
validAt
verdict
version
view
what
why`
    .split("\n")
    .map((variable) => [
      variable,
      "Institutionally supplied owner declaration: nonquantitative for this gate; caller type is not inferred.",
    ]),
);

const NON_NUMERIC_VARIABLE_KEY_SET_SHA256 =
  "b5b3aa0106b331d5b639b53c929748417e2fc9fbe1932a4384df81047327c7d3";
const INTERPOLATION_VARIABLE_KEY_SET_SHA256 =
  "c6e55dde50b11769f4babae1c8c2d835ce9b671340aa8afbd452fc70da4c1f70";
const ACTIVE_LOCALE_LEAF_COUNT = 2693;
const NON_COUNT_MESSAGE_COUNT = 245;
const NON_COUNT_VARIABLE_USE_COUNT = 361;
const NON_COUNT_VARIABLE_USE_KEY_SET_SHA256 =
  "791057b29c0cd78eebd831c2f86285316d1a204ebb893f9598df693dff84417d";

type NumericUseClassification = "pluralized" | "invariant";

type NumericUseDeclaration = {
  classification: NumericUseClassification;
  reason: string;
};

const NUMERIC_INVARIANT_USE_DECLARATIONS = new Map<
  string,
  NumericUseDeclaration
>(
  `causal.edgeDetail.confidenceInterval#{level}
causal.edgeDetail.confidenceInterval#{lower}
causal.edgeDetail.confidenceInterval#{upper}
causal.interference.patternSummary#{strength}
causal.nodeDetail.confidenceInterval#{level}
causal.nodeDetail.confidenceInterval#{lower}
causal.nodeDetail.confidenceInterval#{upper}
causal.pipeline.stageProgress#{completed}
clerk.diff.acceptedSummary#{accepted}
clerk.diff.acceptedSummary#{total}
clerk.diff.section#{index}
common.freshness.updated#{value}
common.lineageGraph.threshold#{maxNodes}
controlJob.humanReviewAgreement#{value}
controlJob.humanReviewBurden#{value}
controlJob.humanReviewOverrideRate#{value}
controlJob.observedBudget#{budget}
controlJob.observedBudget#{observed}
features.dashboard.systemHealth.latencyMs#{latency}
pages.artifacts.corruptedArtifacts#{artifacts}
pages.artifacts.decisionCard.metaIssuesSummary#{blockers}
pages.artifacts.decisionCard.metaIssuesSummary#{info}
pages.artifacts.decisionCard.metaIssuesSummary#{warnings}
pages.artifacts.metricValidation.alpha#{alpha}
pages.artifacts.metricValidation.stat#{value}
pages.artifacts.missingArtifacts#{artifacts}
pages.artifacts.readingView.noteLabel#{index}
pages.artifacts.simulation.calibrationReport.totalLoss#{value}
pages.artifacts.simulation.distributionalPanel.delta#{value}
pages.artifacts.simulation.distributionalPanel.giniRange#{after}
pages.artifacts.simulation.distributionalPanel.giniRange#{before}
pages.artifacts.simulation.distributionalPanel.populationShare#{losers}
pages.artifacts.simulation.distributionalPanel.populationShare#{winners}
pages.artifacts.simulation.metricsPanel.ciRange#{lower}
pages.artifacts.simulation.metricsPanel.ciRange#{upper}
pages.artifacts.trinity.calibrationRef#{value}
pages.artifacts.trinity.dataSnapshotRef#{value}
pages.artifacts.trinity.interventionPriority#{priority}
pages.artifacts.trinity.notes#{value}
pages.artifacts.trinity.objectiveMeta#{target}
pages.artifacts.trinity.registryBundleRef#{value}
pages.composer.inputCostPerMillion#{cost}
pages.composer.outputCostPerMillion#{cost}
pages.composer.selectedProfiles#{available}
pages.composer.selectedProfiles#{selected}
pages.dashboard.durationArtifacts#{duration}
pages.dashboard.promotionMeta#{confidence}
pages.dashboard.runCardMeta#{artifacts}
pages.dashboard.runCardMeta#{duration}
pages.dashboard.sampledRuns#{duration}
pages.dashboard.successRate#{rate}
pages.runs.activeRunAnnouncement#{position}
pages.runs.confidenceIntervalShort#{confidence}
pages.runs.missingArtifacts#{artifacts}
pages.runs.narrative.ciRange#{level}
pages.runs.narrative.ciRange#{lower}
pages.runs.narrative.ciRange#{upper}
pages.runs.pageCountWithTotal#{total}
pages.runs.promotionMeta#{confidence}
pages.runs.qualityFloor#{score}
pages.runs.score#{score}
pages.runs.timelineIndex#{index}
panels.agentPipeline.attempt#{attempt}
panels.dataIntelligence.catalogCandidateMeta#{confidence}
panels.dataIntelligence.discoverCandidateMeta#{confidence}
panels.dataIntelligence.previewMeta#{completeness}
panels.dataIntelligence.previewMeta#{rows}
panels.dataIntelligence.promotionCandidateMeta#{confidence}
panels.dataIntelligence.resolvePlanMeta#{fallbacks}
panels.dataIntelligence.resolvePlanMeta#{quality}
panels.governance.durationMs#{duration}
panels.governance.summaryValues#{blockers}
panels.governance.summaryValues#{info}
panels.governance.summaryValues#{warnings}
panels.reviewCollaboration.activeTarget#{target}
panels.workflow.depthValue#{depth}
phase32.choreography.laneMeta#{duration}
phase32.disputes.meta#{target}
phase32.disputes.openCount#{value}
phase32.freshness.governingLag#{lag}
phase32.freshness.volume#{value}
phase32.telemetry.flagCount#{value}
phase33.cohort.filter#{value}
phase33.cohort.flow#{share}
phase33.identifiability.interval#{lower}
phase33.identifiability.interval#{upper}
phase33.identifiability.weakest#{value}
phase33.sensitivity.eValue#{value}
phase33.sensitivity.explanation.below_threshold#{eValue}
phase33.sensitivity.explanation.below_threshold#{threshold}
phase33.sensitivity.explanation.survives_threshold#{eValue}
phase33.sensitivity.explanation.survives_threshold#{threshold}
phase33.stress.act#{act}
phase34.blockers.embargo#{target}
phase34.blockers.fairness#{target}
phase34.blockers.harm#{target}
phase34.blockers.objection#{target}
phase34.blockers.revocation#{target}
phase34.fairness.calibration#{value}
phase34.fairness.ci#{lower}
phase34.fairness.ci#{upper}
phase34.fairness.ratio#{value}
phase34.fairness.sentinelBody#{ratio}
phase34.fairness.sentinelBody#{threshold}
phase34.fairness.threshold#{value}
phase34.slowReview.dwell#{actual}
phase34.slowReview.dwell#{required}
phase34.slowReview.progress#{completed}
phase34.slowReview.progress#{total}
phase36.onboarding.progress#{completed}
phase36.onboarding.progress#{total}
phase36.onboarding.ttv#{seconds}
shared.a11y.contrastEnforcer.ratioNeeds#{minimum}
shared.a11y.contrastEnforcer.ratioNeeds#{ratio}
shared.charts.common.confidenceIntervalBracketed#{confidence}
shared.charts.common.confidenceIntervalBracketed#{lower}
shared.charts.common.confidenceIntervalBracketed#{upper}
shared.charts.common.confidenceIntervalShort#{confidence}
shared.charts.frequencyDots.outOf#{total}
shared.charts.hypotheticalOutcomePlot.framesPerSecond#{fps}
shared.charts.metaLearner.ate#{value}
shared.charts.quantileDotplot.tailSummary#{p10}
shared.charts.quantileDotplot.tailSummary#{p90}
shared.charts.specificationCurve.summary#{positivePct}
shared.ui.counterfactual.ci95#{interval}
shared.ui.counterfactual.deltaAria#{value}
shared.ui.evidenceCoverageRadar.overall#{percent}
shared.ui.governancePassGrid.statusWithDuration#{durationMs}
shared.ui.lineageGraph.depthValue#{depth}
shared.ui.quantity.aria.withCi95#{lower}
shared.ui.quantity.aria.withCi95#{upper}
shared.ui.quantity.aria.withCi95#{value}
shared.ui.quantity.aria.withoutCi#{value}
shared.ui.quantity.popover.interval#{lower}
shared.ui.quantity.popover.interval#{upper}
shared.ui.reasoningChain.totalDuration#{duration}
shared.ui.trustCalibrationDisplay.actual#{actual}
shared.ui.trustCalibrationDisplay.intervalLabel#{level}
shared.ui.trustCalibrationDisplay.summary#{accuracy}
shared.uncertainty.defaultFraming.confidenceOnly#{confidence}
shared.uncertainty.defaultFraming.range#{confidence}
shared.uncertainty.defaultFraming.range#{lower}
shared.uncertainty.defaultFraming.range#{upper}
whatIf.impact.confidenceInterval#{lower}
whatIf.impact.confidenceInterval#{upper}
whatIf.impact.wasValue#{value}
whatIf.parameterSlider.defaultValue#{value}`
    .split("\n")
    .map((identity) => [
      identity,
      {
        classification: "invariant" as const,
        reason:
          "Adjudicated quantitative use whose wording does not require variable-selected agreement.",
      },
    ]),
);

const NUMERIC_INVARIANT_USE_KEY_SET_SHA256 =
  "2e3c9c18f5980770733df476a5d1427c42208c67f745cd50a408bfa43a6d9cae";

const NUMERIC_AGREEMENT_COHORT_DECLARATIONS = new Map<
  string,
  NumericUseDeclaration
>([
  [
    "causal.pipeline.stageProgress#{total}",
    {
      classification: "invariant",
      reason:
        "Progress numerator and denominator each use a separate stage label.",
    },
  ],
  [
    "common.lineageGraph.threshold#{nodes}",
    {
      classification: "pluralized",
      reason: "Node count selects both noun and Ukrainian verb agreement.",
    },
  ],
  [
    "pages.artifacts.trinity.bindingSummary#{bindings}",
    {
      classification: "invariant",
      reason: "Independent binding and parameter axes use compact labels.",
    },
  ],
  [
    "pages.artifacts.trinity.bindingSummary#{parameters}",
    {
      classification: "invariant",
      reason: "Independent binding and parameter axes use compact labels.",
    },
  ],
  [
    "pages.dashboard.narrativeAttentionBody#{blocked}",
    {
      classification: "pluralized",
      reason:
        "Blocked count selects the packet agreement independently of the run count.",
    },
  ],
  [
    "pages.dashboard.narrativeEvidenceBody#{docs}",
    {
      classification: "invariant",
      reason: "Independent document and promotion quantities use labels.",
    },
  ],
  [
    "pages.dashboard.narrativeEvidenceBody#{promotions}",
    {
      classification: "invariant",
      reason: "Independent document and promotion quantities use labels.",
    },
  ],
  [
    "pages.dashboard.narrativeThroughputBody#{success}",
    {
      classification: "invariant",
      reason:
        "Independent success and total axes use metric labels instead of a plural cross-product.",
    },
  ],
  [
    "pages.dashboard.narrativeThroughputBody#{total}",
    {
      classification: "invariant",
      reason:
        "Independent success and total axes use metric labels instead of a plural cross-product.",
    },
  ],
  [
    "pages.evidence.runContextSummary#{needs}",
    {
      classification: "invariant",
      reason: "Four independent run-context quantities use compact labels.",
    },
  ],
  [
    "pages.evidence.runContextSummary#{plans}",
    {
      classification: "invariant",
      reason: "Four independent run-context quantities use compact labels.",
    },
  ],
  [
    "pages.evidence.runContextSummary#{promotions}",
    {
      classification: "invariant",
      reason: "Four independent run-context quantities use compact labels.",
    },
  ],
  [
    "pages.evidence.runContextSummary#{artifacts}",
    {
      classification: "invariant",
      reason: "Four independent run-context quantities use compact labels.",
    },
  ],
  [
    "pages.runs.evidenceSummary#{plans}",
    {
      classification: "invariant",
      reason: "Independent plan and promotion counts use labels.",
    },
  ],
  [
    "pages.runs.evidenceSummary#{promotions}",
    {
      classification: "invariant",
      reason: "Independent plan and promotion counts use labels.",
    },
  ],
  [
    "panels.dataIntelligence.focusSummary#{needs}",
    {
      classification: "invariant",
      reason: "Three independent focus-summary counts use labels.",
    },
  ],
  [
    "panels.dataIntelligence.focusSummary#{plans}",
    {
      classification: "invariant",
      reason: "Three independent focus-summary counts use labels.",
    },
  ],
  [
    "panels.dataIntelligence.focusSummary#{promotions}",
    {
      classification: "invariant",
      reason: "Three independent focus-summary counts use labels.",
    },
  ],
  [
    "panels.dataIntelligence.lastDiscoverSummary#{docs}",
    {
      classification: "invariant",
      reason: "Independent document and candidate counts use labels.",
    },
  ],
  [
    "panels.dataIntelligence.lastDiscoverSummary#{candidates}",
    {
      classification: "invariant",
      reason: "Independent document and candidate counts use labels.",
    },
  ],
  [
    "panels.dataIntelligence.resolvedSummary#{plans}",
    {
      classification: "invariant",
      reason: "Independent plan and candidate counts use labels.",
    },
  ],
  [
    "panels.dataIntelligence.resolvedSummary#{candidates}",
    {
      classification: "invariant",
      reason: "Independent plan and candidate counts use labels.",
    },
  ],
  [
    "phase32.choreography.artifacts#{value}",
    {
      classification: "invariant",
      reason: "Generic value is rendered after an artifact label.",
    },
  ],
  [
    "phase32.choreography.laneMeta#{events}",
    {
      classification: "invariant",
      reason: "Event count is compact metadata beside a preformatted duration.",
    },
  ],
  [
    "phase32.connectors.datasets#{value}",
    {
      classification: "invariant",
      reason: "Generic value is rendered after a dataset label.",
    },
  ],
  [
    "phase32.connectors.facts#{value}",
    {
      classification: "invariant",
      reason: "Generic value is rendered after a connector-facts label.",
    },
  ],
  [
    "phase32.connectors.profiles#{value}",
    {
      classification: "invariant",
      reason: "Generic value is rendered after a profiles label.",
    },
  ],
  [
    "phase32.freshness.derivedFacts#{value}",
    {
      classification: "invariant",
      reason: "Generic value is rendered after a derived-facts label.",
    },
  ],
  [
    "phase33.identifiability.impactMeta#{quantities}",
    {
      classification: "invariant",
      reason: "Independent quantity and policy axes use labels.",
    },
  ],
  [
    "phase33.identifiability.impactMeta#{policies}",
    {
      classification: "invariant",
      reason: "Independent quantity and policy axes use labels.",
    },
  ],
  [
    "phase33.stress.summary#{blocked}",
    {
      classification: "invariant",
      reason: "Independent block and warning tallies use labels.",
    },
  ],
  [
    "phase33.stress.summary#{warned}",
    {
      classification: "invariant",
      reason: "Independent block and warning tallies use labels.",
    },
  ],
  [
    "phase34.approval.blocked#{value}",
    {
      classification: "invariant",
      reason: "Generic value is rendered after an approval-block label.",
    },
  ],
  [
    "phase34.auditTrail#{value}",
    {
      classification: "invariant",
      reason: "Generic value is rendered after an audit-event label.",
    },
  ],
  [
    "phase34.blockers.slowReview#{target}",
    {
      classification: "pluralized",
      reason: "This target use is a section count and selects noun agreement.",
    },
  ],
  [
    "shared.charts.quantileDotplot.tailSummary#{bins}",
    {
      classification: "pluralized",
      reason: "Bin count selects the equal-probability-dot noun form.",
    },
  ],
]);

const NUMERIC_AGREEMENT_COHORT_KEY_SET_SHA256 =
  "10b722ba7f4776a504eba6b983deface1b607af76fa190f72ff177fe0fabff88";

function mergeNumericUseDeclarations(
  ...declarationSets: ReadonlyMap<string, NumericUseDeclaration>[]
): Map<string, NumericUseDeclaration> {
  const declarations = new Map<string, NumericUseDeclaration>();

  for (const declarationSet of declarationSets) {
    for (const [identity, declaration] of declarationSet) {
      if (declarations.has(identity)) {
        throw new Error(`Duplicate quantitative-use declaration: ${identity}`);
      }
      declarations.set(identity, declaration);
    }
  }

  return declarations;
}

const QUANTITATIVE_USE_DECLARATIONS = mergeNumericUseDeclarations(
  NUMERIC_AGREEMENT_COHORT_DECLARATIONS,
  NUMERIC_INVARIANT_USE_DECLARATIONS,
);

const QUANTITATIVE_USE_DECLARATION_KEY_SET_SHA256 =
  "4bc1fc6d6b2600cfbebd509630f3f5ad82276c47e88b38834ce6fa3d526ee858";

const LEGACY_CONTINUITY_RU_KEY_COUNT = 2449;
const LEGACY_CONTINUITY_RU_KEY_SET_SHA256 =
  "67b7a921f503f108a9b47e034c31be130911c1fe8b7b9321fa8a163ef8d271a8";
const LEGACY_CONTINUITY_RU_LEAF_VALUE_SHA256 =
  "0426d4ce0397027d25f5a2053bce794b12e31fbe3757d3afefb24de6ba3f45eb";

function collectCountMessages(
  value: unknown,
  prefix = "",
): Array<[path: string, message: string]> {
  if (typeof value !== "object" || value == null || Array.isArray(value)) {
    return [];
  }

  return Object.entries(value as Catalog).flatMap(([key, nested]) => {
    const path = prefix ? `${prefix}.${key}` : key;

    if (typeof nested === "string") {
      return nested.includes("{count") ? [[path, nested]] : [];
    }

    return collectCountMessages(nested, path);
  });
}

function collectLeafPairs(
  value: unknown,
  prefix = "",
): Array<[path: string, value: unknown]> {
  if (typeof value !== "object" || value == null || Array.isArray(value)) {
    return prefix ? [[prefix, value]] : [];
  }

  return Object.entries(value as Catalog).flatMap(([key, nested]) =>
    collectLeafPairs(nested, prefix ? `${prefix}.${key}` : key),
  );
}

function isValidPluralMessage(message: string): boolean {
  if (!isPluralMessage(message)) {
    return false;
  }

  try {
    new IntlMessageFormat(message, "en-US");
    return true;
  } catch {
    return false;
  }
}

function collectUnjustifiedCountMessages(
  catalog: unknown,
  exemptions: ReadonlyMap<string, string> = COUNT_MESSAGE_ALLOWLIST,
): string[] {
  return collectCountMessages(catalog)
    .filter(([path, message]) =>
      isPluralMessage(message)
        ? !isValidPluralMessage(message)
        : !exemptions.get(path)?.trim(),
    )
    .map(([path]) => path)
    .sort(comparePaths);
}

function getMessage(catalog: Catalog, path: string): string {
  const message = path.split(".").reduce<unknown>((value, key) => {
    return typeof value === "object" && value != null && !Array.isArray(value)
      ? (value as Catalog)[key]
      : undefined;
  }, catalog);

  if (typeof message !== "string") {
    throw new Error(`Expected ${path} to resolve to a message.`);
  }

  return message;
}

type MessageAstElement = ReturnType<IntlMessageFormat["getAst"]>[number];
const NUMBER_ARGUMENT_AST_TYPE: MessageAstElement["type"] = 2;
const VARIABLE_VALUE_AST_TYPES = new Set<MessageAstElement["type"]>([
  1, 2, 3, 4,
]);

type MessageVariableScan = {
  uses: Array<[path: string, variable: string]>;
  explicitNumericUseKeys: string[];
  parseFailurePaths: string[];
};

function collectAstVariables(
  elements: MessageAstElement[],
  variables = new Set<string>(),
  explicitNumericVariables = new Set<string>(),
): Set<string> {
  for (const element of elements) {
    if (VARIABLE_VALUE_AST_TYPES.has(element.type) && "value" in element) {
      variables.add(element.value);
      if (element.type === NUMBER_ARGUMENT_AST_TYPE) {
        explicitNumericVariables.add(element.value);
      }
      continue;
    }
    if ("options" in element) {
      variables.add(element.value);
      if ("pluralType" in element) {
        explicitNumericVariables.add(element.value);
      }
      for (const option of Object.values(element.options)) {
        collectAstVariables(option.value, variables, explicitNumericVariables);
      }
      continue;
    }
    if ("children" in element) {
      collectAstVariables(
        element.children,
        variables,
        explicitNumericVariables,
      );
    }
  }

  return variables;
}

function collectMessageVariables(
  catalog: unknown,
  intlLocale: string,
): MessageVariableScan {
  const uses: Array<[path: string, variable: string]> = [];
  const explicitNumericUseKeys: string[] = [];
  const parseFailurePaths: string[] = [];

  for (const [path, message] of collectLeafPairs(catalog)) {
    if (typeof message !== "string" || !message.includes("{")) {
      continue;
    }
    try {
      const ast = new IntlMessageFormat(message, intlLocale).getAst();
      const explicitNumericVariables = new Set<string>();
      for (const variable of collectAstVariables(
        ast,
        new Set<string>(),
        explicitNumericVariables,
      )) {
        if (variable !== "count") {
          uses.push([path, variable]);
          if (explicitNumericVariables.has(variable)) {
            explicitNumericUseKeys.push(`${path}#{${variable}}`);
          }
        }
      }
    } catch {
      parseFailurePaths.push(path);
    }
  }

  return {
    uses: [
      ...new Map(uses.map((use) => [`${use[0]}#{${use[1]}}`, use])).values(),
    ].sort(([leftPath, leftVariable], [rightPath, rightVariable]) =>
      comparePaths(
        `${leftPath}#{${leftVariable}}`,
        `${rightPath}#{${rightVariable}}`,
      ),
    ),
    explicitNumericUseKeys: [...new Set(explicitNumericUseKeys)].sort(
      comparePaths,
    ),
    parseFailurePaths: [...new Set(parseFailurePaths)].sort(comparePaths),
  };
}

function collectVariableKindDeclarationFailures(
  catalog: unknown,
  locale: string,
  numericDeclarations: ReadonlyMap<string, string> = NUMERIC_VARIABLE_REASONS,
  nonNumericDeclarations: ReadonlyMap<
    string,
    string
  > = NON_NUMERIC_VARIABLE_REASONS,
): string[] {
  const intlLocale = locale === "uk" ? "uk-UA" : "en-US";
  const scan = collectMessageVariables(catalog, intlLocale);
  const explicitNumericUseKeySet = new Set(scan.explicitNumericUseKeys);

  return [
    ...scan.parseFailurePaths.map(
      (path) => `${locale}:${path}:message_parse_failed`,
    ),
    ...scan.uses.flatMap(([path, variable]) => {
      const identity = `${path}#{${variable}}`;
      const numericReason = numericDeclarations.get(variable);
      const nonNumericReason = nonNumericDeclarations.get(variable);
      const declaredNumeric = numericDeclarations.has(variable);
      const declaredNonNumeric = nonNumericDeclarations.has(variable);

      if (!declaredNumeric && !declaredNonNumeric) {
        return [`${locale}:${identity}:variable-kind-undeclared`];
      }
      if (declaredNumeric && declaredNonNumeric) {
        return [`${locale}:${identity}:variable-kind-conflict`];
      }
      if (!(numericReason ?? nonNumericReason)?.trim()) {
        return [`${locale}:${identity}:variable-kind-reason-missing`];
      }
      if (declaredNonNumeric && explicitNumericUseKeySet.has(identity)) {
        return [`${locale}:${identity}:numeric-kind-conflict`];
      }
      return [];
    }),
  ].sort(comparePaths);
}

type NumericVariableAstEvidence = {
  owningCardinalPluralSelectors: number;
  owningCardinalPluralCategories: string[][];
  rawOccurrences: Array<{ underOwningCardinalPlural: boolean }>;
};

function inspectNumericVariableAst(
  elements: MessageAstElement[],
  variable: string,
  underOwningCardinalPlural = false,
  evidence: NumericVariableAstEvidence = {
    owningCardinalPluralSelectors: 0,
    owningCardinalPluralCategories: [],
    rawOccurrences: [],
  },
): NumericVariableAstEvidence {
  elements.forEach((element) => {
    if ("options" in element && "pluralType" in element) {
      const ownsVariable =
        element.value === variable && element.pluralType === "cardinal";
      if (ownsVariable) {
        evidence.owningCardinalPluralSelectors += 1;
        evidence.owningCardinalPluralCategories.push(
          Object.keys(element.options),
        );
      } else if (element.value === variable) {
        evidence.rawOccurrences.push({ underOwningCardinalPlural });
      }
      for (const option of Object.values(element.options)) {
        inspectNumericVariableAst(
          option.value,
          variable,
          underOwningCardinalPlural || ownsVariable,
          evidence,
        );
      }
      return;
    }

    if ("options" in element) {
      if (element.value === variable) {
        evidence.rawOccurrences.push({ underOwningCardinalPlural });
      }
      for (const option of Object.values(element.options)) {
        inspectNumericVariableAst(
          option.value,
          variable,
          underOwningCardinalPlural,
          evidence,
        );
      }
      return;
    }

    if ("children" in element) {
      inspectNumericVariableAst(
        element.children,
        variable,
        underOwningCardinalPlural,
        evidence,
      );
      return;
    }

    if (
      VARIABLE_VALUE_AST_TYPES.has(element.type) &&
      "value" in element &&
      element.value === variable
    ) {
      evidence.rawOccurrences.push({
        underOwningCardinalPlural,
      });
    }
  });

  return evidence;
}

function parseNumericUseIdentity(
  identity: string,
): [path: string, variable: string] | undefined {
  const markerIndex = identity.lastIndexOf("#{");
  if (markerIndex < 1 || !identity.endsWith("}")) {
    return undefined;
  }

  const path = identity.slice(0, markerIndex);
  const variable = identity.slice(markerIndex + 2, -1);
  return variable ? [path, variable] : undefined;
}

function collectNumericUseDeclarationFailures(
  catalog: unknown,
  locale: string,
  intlLocale: string,
  declarations: ReadonlyMap<
    string,
    NumericUseDeclaration
  > = QUANTITATIVE_USE_DECLARATIONS,
): string[] {
  const failures: string[] = [];
  const scan = collectMessageVariables(catalog, intlLocale);
  const parseFailurePathSet = new Set(scan.parseFailurePaths);
  const actualUseKeys = scan.uses
    .filter(([, variable]) => NUMERIC_VARIABLE_REASONS.has(variable))
    .map(([path, variable]) => `${path}#{${variable}}`);
  const actualUseKeySet = new Set(actualUseKeys);

  for (const path of scan.parseFailurePaths) {
    failures.push(`${locale}:${path}:message_parse_failed`);
  }

  for (const identity of actualUseKeys) {
    if (!declarations.has(identity)) {
      failures.push(`${locale}:${identity}:declaration_missing`);
    }
  }

  for (const [identity, declaration] of declarations) {
    const parsedIdentity = parseNumericUseIdentity(identity);
    if (!parsedIdentity) {
      failures.push(`${locale}:${identity}:declaration_identity_invalid`);
      continue;
    }

    const [path, variable] = parsedIdentity;
    const failureIdentity = `${locale}:${identity}`;

    if (parseFailurePathSet.has(path)) {
      continue;
    }
    if (!NUMERIC_VARIABLE_REASONS.has(variable)) {
      failures.push(`${failureIdentity}:numeric_variable_undeclared`);
      continue;
    }
    if (!actualUseKeySet.has(identity)) {
      failures.push(`${failureIdentity}:declaration_stale`);
      continue;
    }
    if (typeof declaration.reason !== "string" || !declaration.reason.trim()) {
      failures.push(`${failureIdentity}:reason_missing`);
      continue;
    }
    if (declaration.classification === "invariant") {
      continue;
    }

    try {
      const message = getMessage(catalog as Catalog, path);
      const ast = new IntlMessageFormat(message, intlLocale).getAst();
      const evidence = inspectNumericVariableAst(ast, variable);
      const pluralSelectionComplete =
        evidence.owningCardinalPluralSelectors > 0 &&
        evidence.rawOccurrences.every(
          (occurrence) => occurrence.underOwningCardinalPlural,
        );
      if (!pluralSelectionComplete) {
        failures.push(`${failureIdentity}:plural_ownership_missing`);
        continue;
      }

      const requiredCategories =
        locale === "uk" ? ["one", "few", "many", "other"] : ["one", "other"];
      if (
        evidence.owningCardinalPluralCategories.some((categories) =>
          requiredCategories.some(
            (requiredCategory) => !categories.includes(requiredCategory),
          ),
        )
      ) {
        failures.push(`${failureIdentity}:plural_categories_missing`);
      }
    } catch {
      failures.push(`${failureIdentity}:plural_ownership_missing`);
    }
  }

  return [...new Set(failures)].sort(comparePaths);
}

describe("locale catalogs", () => {
  it("keeps the legacy-continuity Russian key set frozen", () => {
    const productCatalogs = { en, uk } as const;
    const authoredKeys = collectPaths(productCatalogs[PRIMARY_LOCALE]).sort(
      comparePaths,
    );
    const ukKeys = collectPaths(uk).sort(comparePaths);
    const ruKeys = collectPaths(ru).sort(comparePaths);
    const ruLeaves = collectLeafPairs(ru).sort(([left], [right]) =>
      comparePaths(left, right),
    );

    expect(PRIMARY_LOCALE).toBe("en");
    expect(ukKeys).toEqual(authoredKeys);
    expect(
      crypto.createHash("sha256").update(JSON.stringify(ruKeys)).digest("hex"),
    ).toBe(LEGACY_CONTINUITY_RU_KEY_SET_SHA256);
    expect(ruKeys).toHaveLength(LEGACY_CONTINUITY_RU_KEY_COUNT);
    expect(
      crypto
        .createHash("sha256")
        .update(JSON.stringify(ruLeaves))
        .digest("hex"),
    ).toBe(LEGACY_CONTINUITY_RU_LEAF_VALUE_SHA256);
  });

  it("justifies exactly every active non-ICU count-message identity", () => {
    const activeNonIcuCountPaths = [
      ...new Set(
        [en, uk]
          .flatMap((catalog) => collectCountMessages(catalog))
          .filter(([, message]) => !isPluralMessage(message))
          .map(([path]) => path),
      ),
    ].sort(comparePaths);

    expect([...COUNT_MESSAGE_ALLOWLIST.keys()].sort(comparePaths)).toEqual(
      activeNonIcuCountPaths,
    );
    for (const [path, reason] of COUNT_MESSAGE_ALLOWLIST) {
      expect(
        reason.trim(),
        `${path} needs a non-empty exemption reason`,
      ).not.toBe("");
    }
  });

  it.each([
    ["en", en],
    ["uk", uk],
  ] as const)(
    "requires every active %s count message to be ICU plural or justified",
    (_locale, catalog) => {
      expect(collectUnjustifiedCountMessages(catalog)).toEqual([]);
    },
  );

  it.each([
    [
      "pages.dashboard.narrativeAttentionBody",
      { blocked: "7" },
      [
        "1 active run needs immediate review posture; blocked packets: 7.",
        "2 active runs need immediate review posture; blocked packets: 7.",
      ],
      [
        "1 активний запуск уже вимагає review posture; 7 заблокованих packet.",
        "2 активні запуски уже вимагають review posture; 7 заблокованих packet.",
        "5 активних запусків уже вимагають review posture; 7 заблокованих packet.",
      ],
      {
        grouped:
          "Активні запуски: 1 001; уже потрібна review posture; 7 заблокованих packet.",
        unavailable:
          "Активні запуски: unavailable; уже потрібна review posture; 7 заблокованих packet.",
      },
    ],
    [
      "pages.dashboard.narrativeQueueBody",
      {},
      [
        "1 decision-bearing run is ready to open from the fleet.",
        "2 decision-bearing runs are ready to open from the fleet.",
      ],
      [
        "1 decision-bearing запуск уже готовий відкриватися з fleet.",
        "2 decision-bearing запуски вже готові відкриватися з fleet.",
        "5 decision-bearing запусків уже готові відкриватися з fleet.",
      ],
      {
        grouped:
          "Decision-bearing запуски, готові до відкриття з fleet: 1 001.",
        unavailable:
          "Decision-bearing запуски, готові до відкриття з fleet: unavailable.",
      },
    ],
    [
      "pages.runs.planMatches",
      {},
      ["1 matched need", "2 matched needs"],
      ["1 пов'язаний need", "2 пов'язані needs", "5 пов'язаних needs"],
      {
        grouped: "Пов'язані needs: 1 001",
        unavailable: "Пов'язані needs: unavailable",
      },
    ],
    [
      "controlJob.scientistEvents",
      {},
      ["1 event", "2 events"],
      ["1 подія", "2 події", "5 подій"],
      {
        grouped: "Події: 1 001",
        unavailable: "Події: unavailable",
      },
    ],
    [
      "pages.composer.curatedConstraints",
      {},
      ["1 curated constraint", "2 curated constraints"],
      [
        "1 curated constraint",
        "2 curated constraints",
        "5 curated constraints",
      ],
      undefined,
    ],
    [
      "pages.composer.capabilitiesVisible",
      {},
      ["1 runtime capability visible", "2 runtime capabilities visible"],
      [
        "1 runtime capability видно",
        "2 runtime capabilities видно",
        "5 runtime capabilities видно",
      ],
      undefined,
    ],
    [
      "pages.evidence.totalProfiles",
      {},
      ["1 total curated profile", "2 total curated profiles"],
      [
        "1 curated profile загалом",
        "2 curated profiles загалом",
        "5 curated profiles загалом",
      ],
      undefined,
    ],
    [
      "panels.agentPipeline.variants",
      {},
      ["1 variant", "2 variants"],
      ["1 variant", "2 variants", "5 variants"],
      undefined,
    ],
  ] as const)(
    "formats repaired plural message %s with locale-specific count forms",
    (
      path,
      values,
      englishExpected,
      ukrainianExpected,
      ukrainianOtherWitness,
    ) => {
      expect(
        [1, 2].map((count) =>
          formatIcuMessage(getMessage(en, path), "en", { ...values, count }),
        ),
      ).toEqual(englishExpected);
      expect(
        [1, 2, 5].map((count) =>
          formatIcuMessage(getMessage(uk, path), "uk", { ...values, count }),
        ),
      ).toEqual(ukrainianExpected);

      const ukrainianOtherActual = ukrainianOtherWitness
        ? {
            grouped: formatIcuMessage(getMessage(uk, path), "uk", {
              ...values,
              count: new Intl.NumberFormat("uk-UA").format(1001),
            }),
            unavailable: formatIcuMessage(getMessage(uk, path), "uk", {
              ...values,
              count: "unavailable",
            }),
          }
        : undefined;
      expect(ukrainianOtherActual).toEqual(ukrainianOtherWitness);
    },
  );

  it("renders the blocked axis with its own locale-specific agreement", () => {
    expect(
      [1, 2].map((blocked) =>
        formatIcuMessage(
          getMessage(en, "pages.dashboard.narrativeAttentionBody"),
          "en",
          { blocked, count: 1 },
        ),
      ),
    ).toEqual([
      "1 active run needs immediate review posture; 1 blocked packet.",
      "1 active run needs immediate review posture; blocked packets: 2.",
    ]);
    expect(
      [1, 2, 5].map((blocked) =>
        formatIcuMessage(
          getMessage(uk, "pages.dashboard.narrativeAttentionBody"),
          "uk",
          { blocked, count: 1 },
        ),
      ),
    ).toEqual([
      "1 активний запуск уже вимагає review posture; 1 заблокований packet.",
      "1 активний запуск уже вимагає review posture; 2 заблоковані packet.",
      "1 активний запуск уже вимагає review posture; 5 заблокованих packet.",
    ]);
    expect([
      formatIcuMessage(
        getMessage(en, "pages.dashboard.narrativeAttentionBody"),
        "en",
        { blocked: "unavailable", count: "unavailable" },
      ),
      formatIcuMessage(
        getMessage(uk, "pages.dashboard.narrativeAttentionBody"),
        "uk",
        { blocked: "unavailable", count: "unavailable" },
      ),
    ]).toEqual([
      "unavailable active runs need immediate review posture; blocked packets: unavailable.",
      "Активні запуски: unavailable; уже потрібна review posture; Заблоковані packet: unavailable.",
    ]);
  });

  it.each([
    [
      "en",
      "en-US",
      en,
      "{count, plural, one {{count} active run needs immediate review posture; blocked packets: {blocked}.} other {{count} active runs need immediate review posture; blocked packets: {blocked}.}}",
    ],
    [
      "uk",
      "uk-UA",
      uk,
      "{count, plural, one {{count} активний запуск уже вимагає review posture; заблоковані packet: {blocked}.} few {{count} активні запуски уже вимагають review posture; заблоковані packet: {blocked}.} many {{count} активних запусків уже вимагають review posture; заблоковані packet: {blocked}.} other {Активні запуски: {count}; заблоковані packet: {blocked}; уже потрібна review posture.}}",
    ],
  ] as const)(
    "rejects the certified wrong %s blocked output at the gate boundary",
    (locale, intlLocale, sourceCatalog, wrongMessage) => {
      const catalog = structuredClone(sourceCatalog) as Catalog;
      const pages = catalog.pages as Catalog;
      const dashboard = pages.dashboard as Catalog;
      dashboard.narrativeAttentionBody = wrongMessage;

      expect(
        collectNumericUseDeclarationFailures(catalog, locale, intlLocale),
      ).toEqual([
        `${locale}:pages.dashboard.narrativeAttentionBody#{blocked}:plural_ownership_missing`,
      ]);
    },
  );

  it("renders both throughput quantities as independent label values", () => {
    const pairs = [
      [1, 1],
      [1, 2],
      [2, 1],
      [2, 2],
    ] as const;

    expect(
      pairs.map(([success, total]) =>
        formatIcuMessage(
          getMessage(en, "pages.dashboard.narrativeThroughputBody"),
          "en",
          { success, total },
        ),
      ),
    ).toEqual([
      "Current sample · successful outcomes: 1 · total runs: 1",
      "Current sample · successful outcomes: 1 · total runs: 2",
      "Current sample · successful outcomes: 2 · total runs: 1",
      "Current sample · successful outcomes: 2 · total runs: 2",
    ]);
    expect(
      [
        [1, 5],
        [5, 1],
        ["1 001", "unavailable"],
      ].map(([success, total]) =>
        formatIcuMessage(
          getMessage(uk, "pages.dashboard.narrativeThroughputBody"),
          "uk",
          { success, total },
        ),
      ),
    ).toEqual([
      "Поточна вибірка · успішні результати: 1 · усі запуски: 5",
      "Поточна вибірка · успішні результати: 5 · усі запуски: 1",
      "Поточна вибірка · успішні результати: 1 001 · усі запуски: unavailable",
    ]);
  });

  it.each([
    [
      "common.lineageGraph.threshold",
      { maxNodes: 500 },
      [
        "Graph has 1 node, which is above render threshold (500).",
        "Graph nodes: 2; render threshold: 500.",
      ],
      [
        "У графі 1 вузол, що перевищує поріг рендерингу (500).",
        "У графі 2 вузли, що перевищують поріг рендерингу (500).",
        "У графі 5 вузлів, що перевищують поріг рендерингу (500).",
      ],
    ],
    [
      "phase34.blockers.slowReview",
      {},
      [
        "Review attention is incomplete: 1 section is done.",
        "Review attention is incomplete; sections done: 2.",
      ],
      [
        "Review attention incomplete: завершено 1 секцію.",
        "Review attention incomplete: завершено 2 секції.",
        "Review attention incomplete: завершено 5 секцій.",
      ],
    ],
    [
      "shared.charts.quantileDotplot.tailSummary",
      { p10: "0.1", p90: "0.9" },
      [
        "p10 0.1 · p90 0.9 · 1 equal-probability dot.",
        "p10 0.1 · p90 0.9 · Equal-probability dots: 2.",
      ],
      [
        "p10 0.1 · p90 0.9 · 1 точка рівної ймовірності.",
        "p10 0.1 · p90 0.9 · 2 точки рівної ймовірності.",
        "p10 0.1 · p90 0.9 · 5 точок рівної ймовірності.",
      ],
    ],
  ] as const)(
    "renders numeric agreement message %s through the live formatter",
    (path, values, englishExpected, ukrainianExpected) => {
      expect(
        [1, 2].map((numericValue) =>
          formatIcuMessage(getMessage(en, path), "en", {
            ...values,
            [path.endsWith("threshold")
              ? "nodes"
              : path.endsWith("slowReview")
                ? "target"
                : "bins"]: numericValue,
          }),
        ),
      ).toEqual(englishExpected);
      expect(
        [1, 2, 5].map((numericValue) =>
          formatIcuMessage(getMessage(uk, path), "uk", {
            ...values,
            [path.endsWith("threshold")
              ? "nodes"
              : path.endsWith("slowReview")
                ? "target"
                : "bins"]: numericValue,
          }),
        ),
      ).toEqual(ukrainianExpected);
    },
  );

  it("rejects omitted and whitespace-only count-message exemption reasons", () => {
    const message = { synthetic: { count: "{count} synthetic records" } };

    expect(collectUnjustifiedCountMessages(message)).toEqual([
      "synthetic.count",
    ]);
    expect(
      collectUnjustifiedCountMessages(
        message,
        new Map([["synthetic.count", "   "]]),
      ),
    ).toEqual(["synthetic.count"]);
  });

  it("rejects a new active count-message identity until it has a reason", () => {
    const message = { synthetic: { newCount: "{count} new records" } };

    expect(collectUnjustifiedCountMessages(message)).toEqual([
      "synthetic.newCount",
    ]);
    expect(
      collectUnjustifiedCountMessages(
        message,
        new Map([
          ["synthetic.newCount", "Synthetic metric with an invariant label."],
        ]),
      ),
    ).toEqual([]);
  });

  it("rejects malformed ICU plural syntax despite an exemption reason", () => {
    const message = { synthetic: { malformed: "{count, plural,}" } };
    const exemptions = new Map([
      ["synthetic.malformed", "Synthetic malformed-ICU admission probe."],
    ]);

    expect(collectUnjustifiedCountMessages(message, exemptions)).toEqual([
      "synthetic.malformed",
    ]);
  });

  it("fails closed for an invented interpolation variable without name inference", () => {
    for (const metric of [
      "Synthetic measure: {inventedAxis}",
      "Synthetic measure: {inventedAxis, number}",
    ]) {
      expect(
        collectVariableKindDeclarationFailures({ synthetic: { metric } }, "en"),
      ).toEqual([
        "en:synthetic.metric#{inventedAxis}:variable-kind-undeclared",
      ]);
    }

    expect(
      collectVariableKindDeclarationFailures(
        { synthetic: { metric: "Synthetic measure: {inventedAxis, number}" } },
        "en",
        new Map(),
        new Map([
          [
            "inventedAxis",
            "Synthetic variable is deliberately misdeclared nonnumeric.",
          ],
        ]),
      ),
    ).toEqual(["en:synthetic.metric#{inventedAxis}:numeric-kind-conflict"]);
  });

  it("accepts numeric variables that control no agreeing word", () => {
    const message = {
      synthetic: { progress: "Step {position} of {total}" },
    };
    const declarations = new Map<string, NumericUseDeclaration>([
      [
        "synthetic.progress#{position}",
        {
          classification: "invariant",
          reason: "Position is an ordinal value; no word agrees with it.",
        },
      ],
      [
        "synthetic.progress#{total}",
        {
          classification: "invariant",
          reason: "Total is a denominator value; no word agrees with it.",
        },
      ],
    ]);

    expect(
      collectNumericUseDeclarationFailures(
        message,
        "en",
        "en-US",
        declarations,
      ),
    ).toEqual([]);
  });

  it("does not use text shape to gate an invariant declaration", () => {
    const catalogWithInvariantCopy = structuredClone(en) as Catalog;
    const phase32 = catalogWithInvariantCopy.phase32 as Catalog;
    const choreography = phase32.choreography as Catalog;
    choreography.laneMeta = "{events} online · {duration}";

    expect(
      collectNumericUseDeclarationFailures(
        catalogWithInvariantCopy,
        "en",
        "en-US",
        QUANTITATIVE_USE_DECLARATIONS,
      ),
    ).toEqual([]);
  });

  it("rejects a real new active-catalog numeric use until it is declared", () => {
    const catalogWithNewUse = structuredClone(en) as Catalog;
    const pages = catalogWithNewUse.pages as Catalog;
    const dashboard = pages.dashboard as Catalog;
    dashboard.c15R1NewQuantitativeUse = "Events: {events}; events";

    expect(
      collectVariableKindDeclarationFailures(catalogWithNewUse, "en"),
    ).toEqual([]);
    expect(
      collectNumericUseDeclarationFailures(catalogWithNewUse, "en", "en-US"),
    ).toEqual([
      "en:pages.dashboard.c15R1NewQuantitativeUse#{events}:declaration_missing",
    ]);

    const declarationsWithNewUse = new Map(QUANTITATIVE_USE_DECLARATIONS);
    declarationsWithNewUse.set(
      "pages.dashboard.c15R1NewQuantitativeUse#{events}",
      {
        classification: "invariant",
        reason: "New event metric was reviewed and declared invariant.",
      },
    );
    expect(
      collectNumericUseDeclarationFailures(
        catalogWithNewUse,
        "en",
        "en-US",
        declarationsWithNewUse,
      ),
    ).toEqual([]);
  });

  it("rejects a stale declaration in one active locale independently", () => {
    const ukWithoutEventUse = structuredClone(uk) as Catalog;
    const phase32 = ukWithoutEventUse.phase32 as Catalog;
    const choreography = phase32.choreography as Catalog;
    choreography.laneMeta = "Тривалість: {duration}";

    expect(
      collectNumericUseDeclarationFailures(ukWithoutEventUse, "uk", "uk-UA"),
    ).toEqual(["uk:phase32.choreography.laneMeta#{events}:declaration_stale"]);
    expect(collectNumericUseDeclarationFailures(en, "en", "en-US")).toEqual([]);
  });

  it("derives point-use membership from ICU semantics, not brace markers", () => {
    const enWithQuotedMarker = structuredClone(en) as Catalog;
    const phase32 = enWithQuotedMarker.phase32 as Catalog;
    const choreography = phase32.choreography as Catalog;
    choreography.laneMeta = "Events: '{events}' · {duration}";

    expect(
      collectNumericUseDeclarationFailures(enWithQuotedMarker, "en", "en-US"),
    ).toEqual(["en:phase32.choreography.laneMeta#{events}:declaration_stale"]);
  });

  it("does not let a plural for one variable protect a different agreeing variable", () => {
    const message = {
      synthetic: {
        nested:
          "{count, plural, one {{count} batch has {events} events.} other {{count} batches have {events} events.}}",
      },
    };
    const rules = new Map([
      [
        "synthetic.nested#{events}",
        {
          classification: "pluralized" as const,
          reason:
            "`events` selects the agreeing noun independently of `count`.",
        },
      ],
    ]);

    expect(
      collectNumericUseDeclarationFailures(message, "en", "en-US", rules),
    ).toEqual(["en:synthetic.nested#{events}:plural_ownership_missing"]);
  });

  it("requires same-variable plural protection in every sibling branch", () => {
    const partial = {
      synthetic: {
        partial:
          "{count, plural, one {{events, plural, one {{events} event} other {{events} events}}} other {{events} events}}",
      },
    };
    const complete = {
      synthetic: {
        complete:
          "{count, plural, one {{events, plural, one {{events} event} other {{events} events}}} other {{events, plural, one {{events} event} other {{events} events}}}}",
      },
    };
    const partialRules = new Map([
      [
        "synthetic.partial#{events}",
        {
          classification: "pluralized" as const,
          reason: "Every occurrence must be owned by the `events` plural.",
        },
      ],
    ]);
    const completeRules = new Map([
      [
        "synthetic.complete#{events}",
        {
          classification: "pluralized" as const,
          reason: "Every occurrence is owned by the `events` plural.",
        },
      ],
    ]);

    expect(
      collectNumericUseDeclarationFailures(
        partial,
        "en",
        "en-US",
        partialRules,
      ),
    ).toEqual(["en:synthetic.partial#{events}:plural_ownership_missing"]);
    expect(
      collectNumericUseDeclarationFailures(
        complete,
        "en",
        "en-US",
        completeRules,
      ),
    ).toEqual([]);
  });

  it("does not treat selectordinal as cardinal plural ownership", () => {
    const ordinal = {
      synthetic: {
        ordinal:
          "{events, selectordinal, one {{events}st event} other {{events}th events}}",
      },
    };
    const declarations = new Map([
      [
        "synthetic.ordinal#{events}",
        {
          classification: "pluralized" as const,
          reason: "Cardinal event agreement cannot be selected by an ordinal.",
        },
      ],
    ]);

    expect(
      collectNumericUseDeclarationFailures(
        ordinal,
        "en",
        "en-US",
        declarations,
      ),
    ).toEqual(["en:synthetic.ordinal#{events}:plural_ownership_missing"]);
  });

  it("requires each locale's cardinal agreement categories independently", () => {
    const message = {
      synthetic: {
        agreement:
          "{events, plural, one {{events} event} other {{events} events}}",
      },
    };
    const declarations = new Map([
      [
        "synthetic.agreement#{events}",
        {
          classification: "pluralized" as const,
          reason: "Event count selects the agreeing noun.",
        },
      ],
    ]);

    expect(
      collectNumericUseDeclarationFailures(
        message,
        "en",
        "en-US",
        declarations,
      ),
    ).toEqual([]);
    expect(
      collectNumericUseDeclarationFailures(
        message,
        "uk",
        "uk-UA",
        declarations,
      ),
    ).toEqual(["uk:synthetic.agreement#{events}:plural_categories_missing"]);
  });

  it("does not let same-variable select or ordinal selectors launder ownership", () => {
    const declarations = new Map([
      [
        "synthetic.selector#{events}",
        {
          classification: "pluralized" as const,
          reason: "Every event selector must be beneath cardinal ownership.",
        },
      ],
    ]);

    for (const selector of ["select", "selectordinal"] as const) {
      const message = {
        synthetic: {
          selector: `{events, ${selector}, special {{events, plural, one {{events} event} other {{events} events}}} other {No event metric}}`,
        },
      };
      expect(
        collectNumericUseDeclarationFailures(
          message,
          "en",
          "en-US",
          declarations,
        ),
      ).toEqual(["en:synthetic.selector#{events}:plural_ownership_missing"]);
    }
  });

  it("rejects an invariant declaration with a missing or empty reason", () => {
    const message = { synthetic: { agreement: "{events} events" } };
    const missingReason = new Map<string, NumericUseDeclaration>([
      [
        "synthetic.agreement#{events}",
        { classification: "invariant" } as NumericUseDeclaration,
      ],
    ]);
    const absentReason = new Map([
      [
        "synthetic.agreement#{events}",
        { classification: "invariant" as const, reason: "" },
      ],
    ]);
    const whitespaceReason = new Map([
      [
        "synthetic.agreement#{events}",
        { classification: "invariant" as const, reason: "   " },
      ],
    ]);

    for (const declarations of [
      missingReason,
      absentReason,
      whitespaceReason,
    ]) {
      expect(
        collectNumericUseDeclarationFailures(
          message,
          "en",
          "en-US",
          declarations,
        ),
      ).toEqual(["en:synthetic.agreement#{events}:reason_missing"]);
    }
  });

  it("rejects malformed ICU for a pluralized declaration", () => {
    const message = {
      synthetic: { malformed: "{events, plural,}" },
    };
    const rules = new Map([
      [
        "synthetic.malformed#{events}",
        {
          classification: "pluralized" as const,
          reason: "Synthetic parser-failure witness.",
        },
      ],
    ]);

    expect(
      collectNumericUseDeclarationFailures(message, "en", "en-US", rules),
    ).toEqual(["en:synthetic.malformed:message_parse_failed"]);
  });

  it("freezes the complete quantitative-use declaration set", () => {
    const activeScans = [
      collectMessageVariables(en, "en-US"),
      collectMessageVariables(uk, "uk-UA"),
    ];
    const activeNumericUseKeys = [
      ...new Set(
        activeScans
          .flatMap((scan) => scan.uses)
          .filter(([, variable]) => NUMERIC_VARIABLE_REASONS.has(variable))
          .map(([path, variable]) => `${path}#{${variable}}`),
      ),
    ].sort(comparePaths);
    const activeVariableNames = [
      ...new Set(
        activeScans
          .flatMap((scan) => scan.uses)
          .map(([, variable]) => variable),
      ),
    ].sort(comparePaths);
    const declaredVariableNames = [
      ...NUMERIC_VARIABLE_REASONS.keys(),
      ...NON_NUMERIC_VARIABLE_REASONS.keys(),
    ].sort(comparePaths);
    const activeUseKeySets = activeScans.map((scan) =>
      scan.uses.map(([path, variable]) => `${path}#{${variable}}`),
    );
    const activeMessagePathSets = activeScans.map(
      (scan) => new Set(scan.uses.map(([path]) => path)),
    );
    const adjudicatedNumericUseKeys = [
      ...QUANTITATIVE_USE_DECLARATIONS.keys(),
    ].sort(comparePaths);
    const paths = new Set(
      [...NUMERIC_AGREEMENT_COHORT_DECLARATIONS.keys()].map((identity) =>
        identity.slice(0, identity.lastIndexOf("#{")),
      ),
    );
    const cohortClassifications = [
      ...NUMERIC_AGREEMENT_COHORT_DECLARATIONS.values(),
    ].reduce(
      (counts, declaration) => ({
        ...counts,
        [declaration.classification]: counts[declaration.classification] + 1,
      }),
      { pluralized: 0, invariant: 0 },
    );
    const allClassifications = [
      ...QUANTITATIVE_USE_DECLARATIONS.values(),
    ].reduce(
      (counts, declaration) => ({
        ...counts,
        [declaration.classification]: counts[declaration.classification] + 1,
      }),
      { pluralized: 0, invariant: 0 },
    );
    const labelGuidedPaths = new Set(
      [...NUMERIC_AGREEMENT_COHORT_DECLARATIONS]
        .filter(([, declaration]) => declaration.classification === "invariant")
        .map(([identity]) => identity.slice(0, identity.lastIndexOf("#{"))),
    );

    expect(paths.size).toBe(23);
    expect(NUMERIC_AGREEMENT_COHORT_DECLARATIONS.size).toBe(36);
    expect(NUMERIC_VARIABLE_REASONS.size).toBe(71);
    expect(NON_NUMERIC_VARIABLE_REASONS.size).toBe(78);
    expect(declaredVariableNames).toHaveLength(149);
    expect(new Set(declaredVariableNames).size).toBe(149);
    expect([collectLeafPairs(en).length, collectLeafPairs(uk).length]).toEqual([
      ACTIVE_LOCALE_LEAF_COUNT,
      ACTIVE_LOCALE_LEAF_COUNT,
    ]);
    expect(activeMessagePathSets.map((paths) => paths.size)).toEqual([
      NON_COUNT_MESSAGE_COUNT,
      NON_COUNT_MESSAGE_COUNT,
    ]);
    expect(activeUseKeySets.map((keys) => keys.length)).toEqual([
      NON_COUNT_VARIABLE_USE_COUNT,
      NON_COUNT_VARIABLE_USE_COUNT,
    ]);
    expect(activeUseKeySets[0]).toEqual(activeUseKeySets[1]);
    expect(
      crypto
        .createHash("sha256")
        .update(activeUseKeySets[0].join("\n"))
        .digest("hex"),
    ).toBe(NON_COUNT_VARIABLE_USE_KEY_SET_SHA256);
    expect(NUMERIC_INVARIANT_USE_DECLARATIONS.size).toBe(147);
    expect(QUANTITATIVE_USE_DECLARATIONS.size).toBe(183);
    expect(activeScans.flatMap((scan) => scan.parseFailurePaths)).toEqual([]);
    expect(declaredVariableNames).toEqual(activeVariableNames);
    expect(adjudicatedNumericUseKeys).toEqual(activeNumericUseKeys);
    expect(
      crypto
        .createHash("sha256")
        .update(
          [...NUMERIC_VARIABLE_REASONS.keys()].sort(comparePaths).join("\n"),
        )
        .digest("hex"),
    ).toBe(NUMERIC_VARIABLE_KEY_SET_SHA256);
    expect(
      crypto
        .createHash("sha256")
        .update(
          [...NON_NUMERIC_VARIABLE_REASONS.keys()]
            .sort(comparePaths)
            .join("\n"),
        )
        .digest("hex"),
    ).toBe(NON_NUMERIC_VARIABLE_KEY_SET_SHA256);
    expect(
      crypto
        .createHash("sha256")
        .update(declaredVariableNames.join("\n"))
        .digest("hex"),
    ).toBe(INTERPOLATION_VARIABLE_KEY_SET_SHA256);
    expect(
      crypto
        .createHash("sha256")
        .update(
          [...NUMERIC_AGREEMENT_COHORT_DECLARATIONS.keys()]
            .map((identity) => identity.replace("#{", "\t").slice(0, -1))
            .sort(comparePaths)
            .join("\n"),
        )
        .digest("hex"),
    ).toBe(NUMERIC_AGREEMENT_COHORT_KEY_SET_SHA256);
    expect(
      crypto
        .createHash("sha256")
        .update(
          [...NUMERIC_INVARIANT_USE_DECLARATIONS.keys()]
            .sort(comparePaths)
            .join("\n"),
        )
        .digest("hex"),
    ).toBe(NUMERIC_INVARIANT_USE_KEY_SET_SHA256);
    expect(
      crypto
        .createHash("sha256")
        .update(adjudicatedNumericUseKeys.join("\n"))
        .digest("hex"),
    ).toBe(QUANTITATIVE_USE_DECLARATION_KEY_SET_SHA256);
    expect(cohortClassifications).toEqual({ pluralized: 4, invariant: 32 });
    expect(allClassifications).toEqual({ pluralized: 4, invariant: 179 });
    expect(labelGuidedPaths.size).toBe(19);
    for (const identity of NUMERIC_AGREEMENT_COHORT_DECLARATIONS.keys()) {
      const parsedIdentity = parseNumericUseIdentity(identity);
      expect(
        parsedIdentity,
        `${identity} must be a valid point-of-use key`,
      ).toBeDefined();
      expect(
        NUMERIC_VARIABLE_REASONS.has(parsedIdentity![1]),
        `${identity} must use a declared numeric variable`,
      ).toBe(true);
    }
    for (const [identity, declaration] of QUANTITATIVE_USE_DECLARATIONS) {
      expect(
        declaration.reason.trim(),
        `${identity} needs a declaration reason`,
      ).not.toBe("");
    }
    for (const [variable, reason] of NUMERIC_VARIABLE_REASONS) {
      expect(
        reason.trim(),
        `${variable} needs a numeric-variable reason`,
      ).not.toBe("");
    }
    for (const [variable, reason] of NON_NUMERIC_VARIABLE_REASONS) {
      expect(
        reason.trim(),
        `${variable} needs a nonnumeric-variable reason`,
      ).not.toBe("");
    }
    for (const [identity, declaration] of NUMERIC_INVARIANT_USE_DECLARATIONS) {
      const parsedIdentity = parseNumericUseIdentity(identity);
      expect(
        parsedIdentity,
        `${identity} must be a valid point-of-use key`,
      ).toBeDefined();
      expect(
        NUMERIC_VARIABLE_REASONS.has(parsedIdentity![1]),
        `${identity} must use a declared numeric variable`,
      ).toBe(true);
      expect(
        declaration.reason.trim(),
        `${identity} needs an invariant-use reason`,
      ).not.toBe("");
      expect(declaration.classification).toBe("invariant");
    }
  });

  it.each([
    ["en", "en-US", en],
    ["uk", "uk-UA", uk],
  ] as const)(
    "requires complete active %s quantitative-use declarations",
    (locale, intlLocale, catalog) => {
      expect(collectVariableKindDeclarationFailures(catalog, locale)).toEqual(
        [],
      );
      expect(
        collectNumericUseDeclarationFailures(
          catalog,
          locale,
          intlLocale,
          QUANTITATIVE_USE_DECLARATIONS,
        ),
      ).toEqual([]);
    },
  );
});
