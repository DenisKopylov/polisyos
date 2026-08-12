import crypto from "node:crypto";
import { IntlMessageFormat } from "intl-messageformat";

import { formatIcuMessage, isPluralMessage } from "./messages/icu-messages";
import en from "./locales/en.json";
import ru from "./locales/ru.json";
import uk from "./locales/uk.json";

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
    "pages.runs.activeRunAnnouncement",
    "Count is the total denominator in “row … of”; it has no agreeing noun.",
  ],
  [
    "pages.runs.pageCount",
    "Machine-readable `name=value` pagination metric.",
  ],
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
  [
    "panels.agentPipeline.diagnostics",
    "Colon-delimited diagnostic metric.",
  ],
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
  ["completeness", "Preview completeness proportion formatted as a percentage."],
  ["confidence", "Confidence percentage or out-of-100 quantity."],
  ["cost", "Price per million."],
  ["depth", "Graph or workflow depth."],
  ["docs", "Document cardinality."],
  ["duration", "Time quantity, sometimes preformatted."],
  ["durationMs", "Duration in milliseconds."],
  ["eValue", "E-value scalar."],
  ["events", "Event cardinality."],
  ["fallbacks", "Fallback-plan cardinality derived from the caller array length."],
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

type NumericAgreementTreatment =
  | "plural"
  | "label_form"
  | "split"
  | "exempt";

type NumericAgreementRule = {
  treatment: NumericAgreementTreatment;
  reason: string;
};

const NUMERIC_NON_AGREEMENT_USES = new Map<string, string>(
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
      "Declared numeric use whose catalog context does not select an agreeing word.",
    ]),
);

const NUMERIC_NON_AGREEMENT_KEY_SET_SHA256 =
  "2e3c9c18f5980770733df476a5d1427c42208c67f745cd50a408bfa43a6d9cae";

const NUMERIC_AGREEMENT_RULES = new Map<string, NumericAgreementRule>([
  [
    "causal.pipeline.stageProgress#{total}",
    {
      treatment: "label_form",
      reason: "Progress numerator and denominator each use a separate stage label.",
    },
  ],
  [
    "common.lineageGraph.threshold#{nodes}",
    {
      treatment: "plural",
      reason: "Node count selects both noun and Ukrainian verb agreement.",
    },
  ],
  [
    "pages.artifacts.trinity.bindingSummary#{bindings}",
    {
      treatment: "label_form",
      reason: "Independent binding and parameter axes use compact labels.",
    },
  ],
  [
    "pages.artifacts.trinity.bindingSummary#{parameters}",
    {
      treatment: "label_form",
      reason: "Independent binding and parameter axes use compact labels.",
    },
  ],
  [
    "pages.dashboard.narrativeAttentionBody#{blocked}",
    {
      treatment: "label_form",
      reason: "A blocked-packet label avoids nesting inside the existing count plural.",
    },
  ],
  [
    "pages.dashboard.narrativeEvidenceBody#{docs}",
    {
      treatment: "label_form",
      reason: "Independent document and promotion quantities use labels.",
    },
  ],
  [
    "pages.dashboard.narrativeEvidenceBody#{promotions}",
    {
      treatment: "label_form",
      reason: "Independent document and promotion quantities use labels.",
    },
  ],
  [
    "pages.dashboard.narrativeThroughputBody#{success}",
    {
      treatment: "label_form",
      reason: "Independent success and total axes use metric labels instead of a plural cross-product.",
    },
  ],
  [
    "pages.dashboard.narrativeThroughputBody#{total}",
    {
      treatment: "label_form",
      reason: "Independent success and total axes use metric labels instead of a plural cross-product.",
    },
  ],
  [
    "pages.evidence.runContextSummary#{needs}",
    {
      treatment: "label_form",
      reason: "Four independent run-context quantities use compact labels.",
    },
  ],
  [
    "pages.evidence.runContextSummary#{plans}",
    {
      treatment: "label_form",
      reason: "Four independent run-context quantities use compact labels.",
    },
  ],
  [
    "pages.evidence.runContextSummary#{promotions}",
    {
      treatment: "label_form",
      reason: "Four independent run-context quantities use compact labels.",
    },
  ],
  [
    "pages.evidence.runContextSummary#{artifacts}",
    {
      treatment: "label_form",
      reason: "Four independent run-context quantities use compact labels.",
    },
  ],
  [
    "pages.runs.evidenceSummary#{plans}",
    {
      treatment: "label_form",
      reason: "Independent plan and promotion counts use labels.",
    },
  ],
  [
    "pages.runs.evidenceSummary#{promotions}",
    {
      treatment: "label_form",
      reason: "Independent plan and promotion counts use labels.",
    },
  ],
  [
    "panels.dataIntelligence.focusSummary#{needs}",
    {
      treatment: "label_form",
      reason: "Three independent focus-summary counts use labels.",
    },
  ],
  [
    "panels.dataIntelligence.focusSummary#{plans}",
    {
      treatment: "label_form",
      reason: "Three independent focus-summary counts use labels.",
    },
  ],
  [
    "panels.dataIntelligence.focusSummary#{promotions}",
    {
      treatment: "label_form",
      reason: "Three independent focus-summary counts use labels.",
    },
  ],
  [
    "panels.dataIntelligence.lastDiscoverSummary#{docs}",
    {
      treatment: "label_form",
      reason: "Independent document and candidate counts use labels.",
    },
  ],
  [
    "panels.dataIntelligence.lastDiscoverSummary#{candidates}",
    {
      treatment: "label_form",
      reason: "Independent document and candidate counts use labels.",
    },
  ],
  [
    "panels.dataIntelligence.resolvedSummary#{plans}",
    {
      treatment: "label_form",
      reason: "Independent plan and candidate counts use labels.",
    },
  ],
  [
    "panels.dataIntelligence.resolvedSummary#{candidates}",
    {
      treatment: "label_form",
      reason: "Independent plan and candidate counts use labels.",
    },
  ],
  [
    "phase32.choreography.artifacts#{value}",
    {
      treatment: "label_form",
      reason: "Generic value is rendered after an artifact label.",
    },
  ],
  [
    "phase32.choreography.laneMeta#{events}",
    {
      treatment: "label_form",
      reason: "Event count is compact metadata beside a preformatted duration.",
    },
  ],
  [
    "phase32.connectors.datasets#{value}",
    {
      treatment: "label_form",
      reason: "Generic value is rendered after a dataset label.",
    },
  ],
  [
    "phase32.connectors.facts#{value}",
    {
      treatment: "label_form",
      reason: "Generic value is rendered after a connector-facts label.",
    },
  ],
  [
    "phase32.connectors.profiles#{value}",
    {
      treatment: "label_form",
      reason: "Generic value is rendered after a profiles label.",
    },
  ],
  [
    "phase32.freshness.derivedFacts#{value}",
    {
      treatment: "label_form",
      reason: "Generic value is rendered after a derived-facts label.",
    },
  ],
  [
    "phase33.identifiability.impactMeta#{quantities}",
    {
      treatment: "label_form",
      reason: "Independent quantity and policy axes use labels.",
    },
  ],
  [
    "phase33.identifiability.impactMeta#{policies}",
    {
      treatment: "label_form",
      reason: "Independent quantity and policy axes use labels.",
    },
  ],
  [
    "phase33.stress.summary#{blocked}",
    {
      treatment: "label_form",
      reason: "Independent block and warning tallies use labels.",
    },
  ],
  [
    "phase33.stress.summary#{warned}",
    {
      treatment: "label_form",
      reason: "Independent block and warning tallies use labels.",
    },
  ],
  [
    "phase34.approval.blocked#{value}",
    {
      treatment: "label_form",
      reason: "Generic value is rendered after an approval-block label.",
    },
  ],
  [
    "phase34.auditTrail#{value}",
    {
      treatment: "label_form",
      reason: "Generic value is rendered after an audit-event label.",
    },
  ],
  [
    "phase34.blockers.slowReview#{target}",
    {
      treatment: "plural",
      reason: "This target use is a section count and selects noun agreement.",
    },
  ],
  [
    "shared.charts.quantileDotplot.tailSummary#{bins}",
    {
      treatment: "plural",
      reason: "Bin count selects the equal-probability-dot noun form.",
    },
  ],
]);

const NUMERIC_AGREEMENT_RULE_KEY_SET_SHA256 =
  "10b722ba7f4776a504eba6b983deface1b607af76fa190f72ff177fe0fabff88";

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
    .filter(
      ([path, message]) =>
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

function collectMessageVariables(
  catalog: unknown,
): Array<[path: string, variable: string]> {
  const uses = collectLeafPairs(catalog).flatMap(([path, message]) => {
    if (typeof message !== "string") {
      return [];
    }

    return [...message.matchAll(/\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?=[,}])/g)]
      .map((match) => match[1])
      .filter((variable) => variable !== "count")
      .map((variable): [string, string] => [path, variable]);
  });

  return [...new Map(uses.map((use) => [`${use[0]}#{${use[1]}}`, use])).values()]
    .sort(([leftPath, leftVariable], [rightPath, rightVariable]) =>
      comparePaths(
        `${leftPath}#{${leftVariable}}`,
        `${rightPath}#{${rightVariable}}`,
      ),
    );
}

const NUMERIC_NAME_TOKENS = new Set([
  "amount",
  "budget",
  "count",
  "depth",
  "duration",
  "fps",
  "index",
  "latency",
  "length",
  "lower",
  "max",
  "maximum",
  "milliseconds",
  "min",
  "minimum",
  "ms",
  "num",
  "number",
  "pct",
  "percent",
  "position",
  "qty",
  "quantity",
  "rate",
  "ratio",
  "rows",
  "score",
  "seconds",
  "size",
  "threshold",
  "total",
  "upper",
  "value",
]);

function looksNumericVariable(variable: string): boolean {
  const tokens = variable
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .toLowerCase()
    .split(/[^a-z0-9]+/u)
    .filter(Boolean);

  return tokens.some((token) => NUMERIC_NAME_TOKENS.has(token));
}

function collectUncoveredNumericVariableUses(
  catalog: unknown,
  locale: string,
  declarations: ReadonlyMap<string, string> = NUMERIC_VARIABLE_REASONS,
): string[] {
  return collectMessageVariables(catalog)
    .filter(([, variable]) => {
      const reason = declarations.get(variable);
      return (
        (declarations.has(variable) || looksNumericVariable(variable)) &&
        !reason?.trim()
      );
    })
    .map(([path, variable]) => `${locale}:${path}#{${variable}}`)
    .sort(comparePaths);
}

function collectUnadjudicatedNumericVariableUses(
  catalog: unknown,
  locale: string,
  rules: ReadonlyMap<string, NumericAgreementRule> = NUMERIC_AGREEMENT_RULES,
  declarations: ReadonlyMap<string, string> = NUMERIC_VARIABLE_REASONS,
  nonAgreementUses: ReadonlyMap<string, string> = NUMERIC_NON_AGREEMENT_USES,
): string[] {
  return collectMessageVariables(catalog)
    .filter(([, variable]) => declarations.has(variable))
    .filter(([path, variable]) => {
      const identity = `${path}#{${variable}}`;
      return !rules.has(identity) && !nonAgreementUses.get(identity)?.trim();
    })
    .map(([path, variable]) => `${locale}:${path}#{${variable}}`)
    .sort(comparePaths);
}

type MessageAstElement = ReturnType<IntlMessageFormat["getAst"]>[number];

type NumericVariableAstEvidence = {
  owningPluralSelectors: number;
  rawOccurrences: Array<{
    followedByBoundary: boolean;
    followsColonLabel: boolean;
    underOwningPlural: boolean;
  }>;
};

function literalValue(element: MessageAstElement | undefined): string {
  return element?.type === 0 ? element.value : "";
}

function inspectNumericVariableAst(
  elements: MessageAstElement[],
  variable: string,
  underOwningPlural = false,
  evidence: NumericVariableAstEvidence = {
    owningPluralSelectors: 0,
    rawOccurrences: [],
  },
): NumericVariableAstEvidence {
  elements.forEach((element, index) => {
    if (element.type === 6) {
      const ownsVariable = element.value === variable;
      if (ownsVariable) {
        evidence.owningPluralSelectors += 1;
      }
      for (const option of Object.values(element.options)) {
        inspectNumericVariableAst(
          option.value,
          variable,
          underOwningPlural || ownsVariable,
          evidence,
        );
      }
      return;
    }

    if (element.type === 5) {
      for (const option of Object.values(element.options)) {
        inspectNumericVariableAst(
          option.value,
          variable,
          underOwningPlural,
          evidence,
        );
      }
      return;
    }

    if (element.type === 8) {
      inspectNumericVariableAst(
        element.children,
        variable,
        underOwningPlural,
        evidence,
      );
      return;
    }

    if (
      [1, 2, 3, 4].includes(element.type) &&
      "value" in element &&
      element.value === variable
    ) {
      const before = literalValue(elements[index - 1]);
      const after = literalValue(elements[index + 1]);
      evidence.rawOccurrences.push({
        followedByBoundary:
          after.length === 0 || /^(?:\s*[·/;.]|\s*$)/u.test(after),
        followsColonLabel: /:\s*$/u.test(before),
        underOwningPlural,
      });
    }
  });

  return evidence;
}

function parseNumericAgreementIdentity(
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

function collectUnsafeNumericAgreementUses(
  catalog: unknown,
  locale: string,
  intlLocale: string,
  rules: ReadonlyMap<string, NumericAgreementRule> = NUMERIC_AGREEMENT_RULES,
): string[] {
  const failures: string[] = [];

  for (const [identity, rule] of rules) {
    const parsedIdentity = parseNumericAgreementIdentity(identity);
    if (!parsedIdentity) {
      failures.push(`${locale}:${identity}`);
      continue;
    }

    const [path, variable] = parsedIdentity;
    const failureIdentity = `${locale}:${path}#{${variable}}`;
    try {
      const message = getMessage(catalog as Catalog, path);
      const ast = new IntlMessageFormat(message, intlLocale).getAst();
      const evidence = inspectNumericVariableAst(ast, variable);
      const totalOccurrences =
        evidence.owningPluralSelectors + evidence.rawOccurrences.length;
      const reasonPresent = rule.reason.trim().length > 0;

      const safe =
        reasonPresent &&
        (rule.treatment === "plural"
          ? evidence.owningPluralSelectors > 0 &&
            evidence.rawOccurrences.every(
              (occurrence) => occurrence.underOwningPlural,
            )
          : rule.treatment === "label_form"
            ? evidence.owningPluralSelectors === 0 &&
              evidence.rawOccurrences.length > 0 &&
              evidence.rawOccurrences.every(
                (occurrence) =>
                  !occurrence.underOwningPlural &&
                  occurrence.followsColonLabel &&
                  occurrence.followedByBoundary,
              )
            : rule.treatment === "split"
              ? totalOccurrences === 0
              : totalOccurrences > 0);

      if (!safe) {
        failures.push(failureIdentity);
      }
    } catch {
      failures.push(failureIdentity);
    }
  }

  return [...new Set(failures)].sort(comparePaths);
}

describe("locale catalogs", () => {
  it("keeps the legacy-continuity Russian key set frozen", () => {
    const enKeys = collectPaths(en).sort(comparePaths);
    const ukKeys = collectPaths(uk).sort(comparePaths);
    const ruKeys = collectPaths(ru).sort(comparePaths);
    const ruLeaves = collectLeafPairs(ru).sort(([left], [right]) =>
      comparePaths(left, right),
    );

    expect(ukKeys).toEqual(enKeys);
    expect(
      crypto.createHash("sha256").update(JSON.stringify(ruKeys)).digest("hex"),
    ).toBe(LEGACY_CONTINUITY_RU_KEY_SET_SHA256);
    expect(ruKeys).toHaveLength(LEGACY_CONTINUITY_RU_KEY_COUNT);
    expect(
      crypto.createHash("sha256").update(JSON.stringify(ruLeaves)).digest("hex"),
    ).toBe(LEGACY_CONTINUITY_RU_LEAF_VALUE_SHA256);
  });

  it("justifies exactly every active non-ICU count-message identity", () => {
    const activeNonIcuCountPaths = [...new Set(
      [en, uk]
        .flatMap((catalog) => collectCountMessages(catalog))
        .filter(([, message]) => !isPluralMessage(message))
        .map(([path]) => path),
    )].sort(comparePaths);

    expect([...COUNT_MESSAGE_ALLOWLIST.keys()].sort(comparePaths)).toEqual(
      activeNonIcuCountPaths,
    );
    for (const [path, reason] of COUNT_MESSAGE_ALLOWLIST) {
      expect(reason.trim(), `${path} needs a non-empty exemption reason`).not.toBe("");
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
      ["1 active run needs immediate review posture; blocked packets: 7.", "2 active runs need immediate review posture; blocked packets: 7."],
      ["1 активний запуск уже вимагає review posture; заблоковані packet: 7.", "2 активні запуски уже вимагають review posture; заблоковані packet: 7.", "5 активних запусків уже вимагають review posture; заблоковані packet: 7."],
      {
        grouped: "Активні запуски: 1 001; заблоковані packet: 7; уже потрібна review posture.",
        unavailable: "Активні запуски: unavailable; заблоковані packet: 7; уже потрібна review posture.",
      },
    ],
    [
      "pages.dashboard.narrativeQueueBody",
      {},
      ["1 decision-bearing run is ready to open from the fleet.", "2 decision-bearing runs are ready to open from the fleet."],
      ["1 decision-bearing запуск уже готовий відкриватися з fleet.", "2 decision-bearing запуски вже готові відкриватися з fleet.", "5 decision-bearing запусків уже готові відкриватися з fleet."],
      {
        grouped: "Decision-bearing запуски, готові до відкриття з fleet: 1 001.",
        unavailable: "Decision-bearing запуски, готові до відкриття з fleet: unavailable.",
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
      ["1 curated constraint", "2 curated constraints", "5 curated constraints"],
      undefined,
    ],
    [
      "pages.composer.capabilitiesVisible",
      {},
      ["1 runtime capability visible", "2 runtime capabilities visible"],
      ["1 runtime capability видно", "2 runtime capabilities видно", "5 runtime capabilities видно"],
      undefined,
    ],
    [
      "pages.evidence.totalProfiles",
      {},
      ["1 total curated profile", "2 total curated profiles"],
      ["1 curated profile загалом", "2 curated profiles загалом", "5 curated profiles загалом"],
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
    (path, values, englishExpected, ukrainianExpected, ukrainianOtherWitness) => {
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

      if (ukrainianOtherWitness) {
        expect(
          formatIcuMessage(getMessage(uk, path), "uk", {
            ...values,
            count: new Intl.NumberFormat("uk-UA").format(1001),
          }),
        ).toBe(ukrainianOtherWitness.grouped);
        expect(
          formatIcuMessage(getMessage(uk, path), "uk", {
            ...values,
            count: "unavailable",
          }),
        ).toBe(ukrainianOtherWitness.unavailable);
      }
    },
  );

  it("renders the independent blocked axis without nested plural branches", () => {
    expect(
      [1, 2].map((blocked) =>
        formatIcuMessage(
          getMessage(en, "pages.dashboard.narrativeAttentionBody"),
          "en",
          { blocked, count: 1 },
        ),
      ),
    ).toEqual([
      "1 active run needs immediate review posture; blocked packets: 1.",
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
      "1 активний запуск уже вимагає review posture; заблоковані packet: 1.",
      "1 активний запуск уже вимагає review posture; заблоковані packet: 2.",
      "1 активний запуск уже вимагає review posture; заблоковані packet: 5.",
    ]);
  });

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

    expect(collectUnjustifiedCountMessages(message)).toEqual(["synthetic.count"]);
    expect(
      collectUnjustifiedCountMessages(
        message,
        new Map([["synthetic.count", "   "]]),
      ),
    ).toEqual(["synthetic.count"]);
  });

  it("rejects a new active count-message identity until it has a reason", () => {
    const message = { synthetic: { newCount: "{count} new records" } };

    expect(collectUnjustifiedCountMessages(message)).toEqual(["synthetic.newCount"]);
    expect(
      collectUnjustifiedCountMessages(
        message,
        new Map([["synthetic.newCount", "Synthetic metric with an invariant label."]]),
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

  it("reports an uncovered numeric-shaped variable at its exact point of use", () => {
    const message = {
      synthetic: { metric: "Processed records: { recordCount }" },
    };

    expect(collectUncoveredNumericVariableUses(message, "en")).toEqual([
      "en:synthetic.metric#{recordCount}",
    ]);
    expect(
      collectUncoveredNumericVariableUses(
        message,
        "en",
        new Map([["recordCount", "   "]]),
      ),
    ).toEqual(["en:synthetic.metric#{recordCount}"]);
    expect(
      collectUncoveredNumericVariableUses(
        message,
        "en",
        new Map([["recordCount", "Synthetic record cardinality."]]),
      ),
    ).toEqual([]);
  });

  it("rejects punctuation around an agreeing phrase as a fake label form", () => {
    const rules = new Map([
      [
        "synthetic.agreement#{events}",
        {
          treatment: "label_form" as const,
          reason: "Event count requires a real label/value boundary.",
        },
      ],
    ]);

    for (const agreement of [
      "Processed ({events}) events.",
      "Events: {events} events.",
      "Events: {events} (events)",
    ]) {
      expect(
        collectUnsafeNumericAgreementUses(
          { synthetic: { agreement } },
          "en",
          "en-US",
          rules,
        ),
      ).toEqual(["en:synthetic.agreement#{events}"]);
    }
  });

  it("rejects a new agreement-bearing use of a declared numeric variable", () => {
    for (const newIdentity of [
      "{events} events",
      "Processed ({events}) events.",
    ]) {
      const message = { synthetic: { newIdentity } };

      expect(collectUncoveredNumericVariableUses(message, "en")).toEqual([]);
      expect(collectUnadjudicatedNumericVariableUses(message, "en")).toEqual([
        "en:synthetic.newIdentity#{events}",
      ]);
    }
  });

  it("does not let a plural for one variable protect a different agreeing variable", () => {
    const message = {
      synthetic: {
        nested:
          "{count, plural, one {{count} batch has {records} records.} other {{count} batches have {records} records.}}",
      },
    };
    const rules = new Map([
      [
        "synthetic.nested#{records}",
        {
          treatment: "plural" as const,
          reason: "`records` selects the agreeing noun independently of `count`.",
        },
      ],
    ]);

    expect(
      collectUnsafeNumericAgreementUses(message, "en", "en-US", rules),
    ).toEqual(["en:synthetic.nested#{records}"]);
  });

  it("requires same-variable plural protection in every sibling branch", () => {
    const partial = {
      synthetic: {
        partial:
          "{count, plural, one {{records, plural, one {{records} record} other {{records} records}}} other {{records} records}}",
      },
    };
    const complete = {
      synthetic: {
        complete:
          "{count, plural, one {{records, plural, one {{records} record} other {{records} records}}} other {{records, plural, one {{records} record} other {{records} records}}}}",
      },
    };
    const partialRules = new Map([
      [
        "synthetic.partial#{records}",
        {
          treatment: "plural" as const,
          reason: "Every occurrence must be owned by the `records` plural.",
        },
      ],
    ]);
    const completeRules = new Map([
      [
        "synthetic.complete#{records}",
        {
          treatment: "plural" as const,
          reason: "Every occurrence is owned by the `records` plural.",
        },
      ],
    ]);

    expect(
      collectUnsafeNumericAgreementUses(
        partial,
        "en",
        "en-US",
        partialRules,
      ),
    ).toEqual(["en:synthetic.partial#{records}"]);
    expect(
      collectUnsafeNumericAgreementUses(
        complete,
        "en",
        "en-US",
        completeRules,
      ),
    ).toEqual([]);
  });

  it("rejects a declared agreeing variable with neither plural nor a reason", () => {
    const message = { synthetic: { agreement: "{events} events" } };
    const absentReason = new Map([
      [
        "synthetic.agreement#{events}",
        { treatment: "exempt" as const, reason: "" },
      ],
    ]);
    const whitespaceReason = new Map([
      [
        "synthetic.agreement#{events}",
        { treatment: "exempt" as const, reason: "   " },
      ],
    ]);

    expect(
      collectUnsafeNumericAgreementUses(
        message,
        "en",
        "en-US",
        absentReason,
      ),
    ).toEqual(["en:synthetic.agreement#{events}"]);
    expect(
      collectUnsafeNumericAgreementUses(
        message,
        "en",
        "en-US",
        whitespaceReason,
      ),
    ).toEqual(["en:synthetic.agreement#{events}"]);
  });

  it("rejects malformed numeric ICU even when an exemption has a reason", () => {
    const message = {
      synthetic: { malformed: "{records, plural,}" },
    };
    const rules = new Map([
      [
        "synthetic.malformed#{records}",
        {
          treatment: "exempt" as const,
          reason: "Synthetic parser-failure witness.",
        },
      ],
    ]);

    expect(
      collectUnsafeNumericAgreementUses(message, "en", "en-US", rules),
    ).toEqual(["en:synthetic.malformed#{records}"]);
  });

  it("adjudicates the complete 23-identity numeric-agreement set", () => {
    const activeNumericUseKeys = [...new Set(
      [en, uk]
        .flatMap((catalog) => collectMessageVariables(catalog))
        .filter(([, variable]) => NUMERIC_VARIABLE_REASONS.has(variable))
        .map(([path, variable]) => `${path}#{${variable}}`),
    )].sort(comparePaths);
    const adjudicatedNumericUseKeys = [
      ...NUMERIC_AGREEMENT_RULES.keys(),
      ...NUMERIC_NON_AGREEMENT_USES.keys(),
    ].sort(comparePaths);
    const paths = new Set(
      [...NUMERIC_AGREEMENT_RULES.keys()].map((identity) =>
        identity.slice(0, identity.lastIndexOf("#{")),
      ),
    );
    const treatments = [...NUMERIC_AGREEMENT_RULES.values()].reduce(
      (counts, rule) => ({
        ...counts,
        [rule.treatment]: counts[rule.treatment] + 1,
      }),
      { plural: 0, label_form: 0, split: 0, exempt: 0 },
    );

    expect(paths.size).toBe(23);
    expect(NUMERIC_AGREEMENT_RULES.size).toBe(36);
    expect(NUMERIC_VARIABLE_REASONS.size).toBe(71);
    expect(NUMERIC_NON_AGREEMENT_USES.size).toBe(147);
    expect(adjudicatedNumericUseKeys).toEqual(activeNumericUseKeys);
    expect(
      crypto
        .createHash("sha256")
        .update([...NUMERIC_VARIABLE_REASONS.keys()].sort(comparePaths).join("\n"))
        .digest("hex"),
    ).toBe(NUMERIC_VARIABLE_KEY_SET_SHA256);
    expect(
      crypto
        .createHash("sha256")
        .update(
          [...NUMERIC_AGREEMENT_RULES.keys()]
            .map((identity) => identity.replace("#{", "\t").slice(0, -1))
            .sort(comparePaths)
            .join("\n"),
        )
        .digest("hex"),
    ).toBe(NUMERIC_AGREEMENT_RULE_KEY_SET_SHA256);
    expect(
      crypto
        .createHash("sha256")
        .update(
          [...NUMERIC_NON_AGREEMENT_USES.keys()]
            .sort(comparePaths)
            .join("\n"),
        )
        .digest("hex"),
    ).toBe(NUMERIC_NON_AGREEMENT_KEY_SET_SHA256);
    expect(treatments).toEqual({
      plural: 3,
      label_form: 33,
      split: 0,
      exempt: 0,
    });
    for (const identity of NUMERIC_AGREEMENT_RULES.keys()) {
      const parsedIdentity = parseNumericAgreementIdentity(identity);
      expect(parsedIdentity, `${identity} must be a valid point-of-use key`).toBeDefined();
      expect(
        NUMERIC_VARIABLE_REASONS.has(parsedIdentity![1]),
        `${identity} must use a declared numeric variable`,
      ).toBe(true);
    }
    for (const [identity, rule] of NUMERIC_AGREEMENT_RULES) {
      expect(rule.reason.trim(), `${identity} needs a treatment reason`).not.toBe(
        "",
      );
    }
    for (const [variable, reason] of NUMERIC_VARIABLE_REASONS) {
      expect(
        reason.trim(),
        `${variable} needs a numeric-variable reason`,
      ).not.toBe("");
    }
    for (const [identity, reason] of NUMERIC_NON_AGREEMENT_USES) {
      const parsedIdentity = parseNumericAgreementIdentity(identity);
      expect(parsedIdentity, `${identity} must be a valid point-of-use key`).toBeDefined();
      expect(
        NUMERIC_VARIABLE_REASONS.has(parsedIdentity![1]),
        `${identity} must use a declared numeric variable`,
      ).toBe(true);
      expect(
        reason.trim(),
        `${identity} needs a numeric-use exemption reason`,
      ).not.toBe("");
    }
  });

  it.each([
    ["en", "en-US", en],
    ["uk", "uk-UA", uk],
  ] as const)(
    "covers and repairs every active %s numeric-variable use",
    (locale, intlLocale, catalog) => {
      expect(collectUncoveredNumericVariableUses(catalog, locale)).toEqual([]);
      expect(
        collectUnadjudicatedNumericVariableUses(catalog, locale),
      ).toEqual([]);
      expect(
        collectUnsafeNumericAgreementUses(
          catalog,
          locale,
          intlLocale,
          NUMERIC_AGREEMENT_RULES,
        ),
      ).toEqual([]);
    },
  );
});
