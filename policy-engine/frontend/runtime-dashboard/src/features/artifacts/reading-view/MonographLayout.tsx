import { useMemo, useRef } from "react";

import { parseDecisionCardPayload } from "@/shared/lib/domain/decision";
import { useOptionalI18n } from "@/shared/i18n/LocaleProvider";
import {
  asArray,
  asBoolean,
  asNumber,
  asRecord,
  asString,
  toDisplayLabel,
} from "@/shared/lib/parsing";
import {
  formatDate,
  formatDuration,
  formatNumber,
  formatPercent,
  cn,
} from "@/shared/lib/utils";
import { JanusGlyph } from "@/shared/brand/JanusGlyph";
import { ProvenanceStrip } from "@/shared/ui";
import {
  AuthoredText,
  normalizeAuthoredNarrativeBlock,
  type AuthoredNarrativeBlock,
} from "@/shared/ui/authored-text";

import "@/styles/print.css";

import { DefinitionList } from "./DefinitionList";
import { FootnoteList, FootnoteReference } from "./Footnote";
import { MarginNotes } from "./MarginNotes";
import { PullQuote } from "./PullQuote";
import { TableOfContentsGlyphed } from "./TableOfContentsGlyphed";
import { useMarginNoteAnchors } from "./hooks/useMarginNoteAnchors";
import { useReadingProgress } from "./hooks/useReadingProgress";
import "./prose.css";
import {
  sectionGlyphForType,
  sectionLabelForType,
  type DecisionPacketSectionType,
  type ReadingViewDocument,
  type ReadingViewFootnote,
  type ReadingViewParagraph,
  type ReadingViewSection,
} from "./reading-view-tokens";

type MonographLayoutProps = {
  document: ReadingViewDocument;
  className?: string;
};

type OutlineEntry = {
  sectionId: string;
  title: string;
  sectionType: DecisionPacketSectionType;
};

function formatEnum(value: string) {
  return value
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function joinClauses(parts: string[]) {
  if (parts.length === 0) {
    return "";
  }
  if (parts.length === 1) {
    return parts[0];
  }
  if (parts.length === 2) {
    return `${parts[0]} and ${parts[1]}`;
  }
  return `${parts.slice(0, -1).join(", ")}, and ${parts.at(-1)}`;
}

function pluralize(count: number, noun: string) {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function isDefined<T>(value: T | null | undefined): value is T {
  return value !== null && value !== undefined;
}

function confidenceIntent(confidence: string) {
  if (confidence === "HIGH") {
    return "verified" as const;
  }
  if (confidence === "LOW") {
    return "blocked" as const;
  }
  return "pending" as const;
}

function governanceItem(blockerCount: number) {
  return blockerCount > 0
    ? {
        detail: `${blockerCount} governance blocker(s) still open.`,
        glyph: "blocker" as const,
        id: "governance",
        intent: "blocked" as const,
        label: pluralize(blockerCount, "blocker"),
      }
    : {
        detail: "No governance blockers are currently recorded.",
        glyph: "governance-pass" as const,
        id: "governance",
        intent: "verified" as const,
        label: "Governance pass",
      };
}

function buildSectionProvenance(
  sectionType: DecisionPacketSectionType,
  packet: ReturnType<typeof parseDecisionCardPayload>,
) {
  if (!packet) {
    return [];
  }

  return [
    {
      glyph: sectionGlyphForType(sectionType),
      id: `${sectionType}-section`,
      label: sectionLabelForType(sectionType),
    },
    {
      detail: `Packet confidence resolves to ${formatEnum(packet.confidence)}.`,
      glyph: "evidence" as const,
      id: `${sectionType}-confidence`,
      intent: confidenceIntent(packet.confidence),
      label: `${formatEnum(packet.confidence)} confidence`,
      strokeStyle:
        packet.confidence === "MEDIUM" ? ("dashed" as const) : undefined,
    },
    governanceItem(packet.issues.blockerCount),
  ];
}

function parseOutline(payload: Record<string, unknown>) {
  const entries = new Map<string, OutlineEntry>();
  for (const value of asArray(payload.document_outline)) {
    const entry = asRecord(value);
    const sectionId = asString(entry?.section_id);
    const title = asString(entry?.title);
    const sectionType = asString(entry?.section_type);
    if (!sectionId || !title || !sectionType) {
      continue;
    }

    if (
      sectionType === "problem" ||
      sectionType === "intervention" ||
      sectionType === "evidence" ||
      sectionType === "policy" ||
      sectionType === "governance" ||
      sectionType === "reproducibility"
    ) {
      entries.set(sectionId, {
        sectionId,
        sectionType,
        title,
      });
    }
  }
  return entries;
}

function metricSentence(
  metric: NonNullable<
    ReturnType<typeof parseDecisionCardPayload>
  >["keyMetrics"][number],
) {
  const unit = metric.unit ? ` ${metric.unit}` : "";
  const interval =
    metric.ciLower !== null && metric.ciUpper !== null
      ? ` (${formatNumber((metric.ciLevel ?? 0.95) * 100, {
          maximumFractionDigits: 0,
        })}% CI ${formatNumber(metric.ciLower, {
          maximumFractionDigits: 2,
        })} to ${formatNumber(metric.ciUpper, {
          maximumFractionDigits: 2,
        })})`
      : "";
  return `${metric.name} is estimated at ${metric.formatted}${unit}${interval}`;
}

function buildDocumentSection(
  outline: Map<string, OutlineEntry>,
  section: Omit<ReadingViewSection, "sectionType" | "title"> & {
    fallbackTitle: string;
    fallbackType: DecisionPacketSectionType;
  },
): ReadingViewSection {
  const outlined = outline.get(section.id);
  return {
    ...section,
    sectionType: outlined?.sectionType ?? section.fallbackType,
    title: outlined?.title ?? section.fallbackTitle,
  };
}

function normalizeStrings(value: unknown, limit = 4) {
  return asArray(value)
    .map((item) => asString(item))
    .filter((item): item is string => Boolean(item))
    .slice(0, limit);
}

function normalizeDescriptions(
  value: unknown,
  limit = 4,
): ReadingViewFootnote[] {
  return asArray(value)
    .map((item, index) => {
      const record = asRecord(item);
      if (record) {
        const message =
          asString(record.description) ??
          asString(record.message) ??
          asString(record.reason);
        if (!message) {
          return null;
        }
        return {
          body: message,
          id: `issue-${index + 1}`,
        } satisfies ReadingViewFootnote;
      }
      const body = asString(item);
      return body
        ? ({ body, id: `issue-${index + 1}` } satisfies ReadingViewFootnote)
        : null;
    })
    .filter((item): item is ReadingViewFootnote => item !== null)
    .slice(0, limit);
}

function toReadingParagraph(
  id: string,
  content: string,
  author: ReadingViewParagraph["author"] = "human",
): ReadingViewParagraph {
  return {
    author,
    content,
    id,
  };
}

function normalizeParagraphs(
  value: unknown,
  fallbackParagraphs: string[],
  sectionId: string,
): ReadingViewParagraph[] {
  const authoredBlocks = asArray(value)
    .map((item) => asRecord(item))
    .filter((item): item is AuthoredNarrativeBlock =>
      Boolean(item && typeof item.content === "string" && item.content.trim()),
    )
    .map((block) => normalizeAuthoredNarrativeBlock(block));

  if (authoredBlocks.length > 0) {
    return authoredBlocks.map((block, index) => ({
      author: block.author,
      authorAgentVersion: block.authorAgentVersion,
      confidence: block.confidence,
      content: block.content,
      id: `${sectionId}-block-${block.id || index + 1}`,
      reviewedByHuman: block.reviewedByHuman,
      sourceRef: block.sourceRef,
      timestamp: block.timestamp,
    }));
  }

  return fallbackParagraphs.map((paragraph, index) =>
    toReadingParagraph(`${sectionId}-p${index + 1}`, paragraph),
  );
}

export function buildDecisionPacketDocument(
  payload: unknown,
): ReadingViewDocument | null {
  const record = asRecord(payload);
  const packet = parseDecisionCardPayload(payload);
  if (!record || !packet || packet.sourceKind !== "decision_packet") {
    return null;
  }

  const outline = parseOutline(record);
  const policyAnswer = asRecord(record.policy_answer);
  const legalVerification = asRecord(record.legal_verification);
  const sourceCoverage = asRecord(record.source_coverage);
  const governance = asRecord(record.governance) ?? asRecord(record.feedback);
  const replay = asRecord(record.replay);
  const analysisLimits = asRecord(record.analysis_limits);
  const distributional = packet.distributional;
  const verifiedFindings = normalizeStrings(record.verified_findings);
  const hypotheses = normalizeStrings(record.hypotheses);
  const missingEvidence = normalizeStrings(policyAnswer?.missing_evidence);
  const notes = normalizeStrings(record.notes);
  const degradedPaths = normalizeDescriptions(record.degraded_paths, 6);
  const documentSections: ReadingViewSection[] = [];

  const executiveSummary =
    asString(policyAnswer?.executive_summary) ?? packet.policySummary;
  const needsExpertReview =
    asBoolean(policyAnswer?.needs_expert_review) === true ||
    asBoolean(legalVerification?.needs_expert_review) === true;

  if (
    executiveSummary ||
    verifiedFindings.length > 0 ||
    missingEvidence.length > 0 ||
    hypotheses.length > 0
  ) {
    documentSections.push(
      buildDocumentSection(outline, {
        fallbackTitle: "Recommendation",
        fallbackType: "policy",
        footnotes: missingEvidence.map((body, index) => ({
          body,
          id: `policy-answer-missing-${index + 1}`,
        })),
        id: "policy_answer",
        lede: executiveSummary ?? undefined,
        marginNotes: [
          {
            anchorId: "policy_answer-lede",
            body: [
              `Run ${packet.runId}`,
              packet.generatedAt ? formatDate(packet.generatedAt) : null,
              formatDuration(packet.totalDurationMs),
            ]
              .filter(Boolean)
              .join(" · "),
            id: "policy-answer-packet",
            label: "Packet",
          },
          {
            anchorId: "policy_answer-p1",
            body: `${formatEnum(packet.confidence)} confidence with ${pluralize(packet.issues.blockerCount, "blocker")} and ${pluralize(packet.issues.warningCount, "warning")}.`,
            id: "policy-answer-confidence",
            label: "Confidence",
          },
        ],
        paragraphs: normalizeParagraphs(
          record.narrative_blocks ?? record.blocks,
          [
            `The packet currently resolves to ${formatEnum(packet.verdict)} across ${pluralize(packet.interventionCount, "intervention")} and a ${formatEnum(packet.confidence)} confidence posture.`,
            needsExpertReview
              ? "Expert review is still explicitly required before this packet should be treated as publication-grade guidance."
              : "No explicit expert-review gate is attached to the current recommendation bundle.",
            hypotheses.length > 0
              ? `Open hypotheses remain active: ${joinClauses(hypotheses)}.`
              : "No additional policy hypotheses are attached to the decision packet.",
          ],
          "policy_answer",
        ),
        provenanceItems: buildSectionProvenance("policy", packet),
        pullQuote: verifiedFindings[0] ?? executiveSummary ?? undefined,
      }),
    );
  }

  if (packet.policySummary !== "N/A" || packet.interventionCount > 0) {
    const legalBasisMap = asRecord(record.intervention_legal_basis_map);
    const legalBasisCount = legalBasisMap
      ? Object.keys(legalBasisMap).length
      : 0;

    documentSections.push(
      buildDocumentSection(outline, {
        definitions: [
          {
            definition: String(packet.interventionCount),
            term: "Interventions",
          },
          {
            definition: formatEnum(packet.verdict),
            term: "Verdict",
          },
          {
            definition: formatEnum(packet.confidence),
            term: "Confidence",
          },
        ],
        fallbackTitle: "Intervention scope",
        fallbackType: "intervention",
        highlights:
          legalBasisMap && Object.keys(legalBasisMap).length > 0
            ? Object.entries(legalBasisMap)
                .slice(0, 4)
                .map(
                  ([key, value]) =>
                    `${toDisplayLabel(key)} — ${normalizeStrings(value, 3).join(", ") || "no cited basis"}`,
                )
            : undefined,
        highlightsTitle: legalBasisCount > 0 ? "Legal basis map" : undefined,
        id: "policy_summary",
        lede: packet.policySummary,
        marginNotes: [
          {
            anchorId: "policy_summary-lede",
            body:
              legalBasisCount > 0
                ? `${pluralize(legalBasisCount, "intervention")} already link to verified legal basis.`
                : "No explicit intervention-to-basis map is currently embedded in the packet.",
            id: "policy-summary-basis",
            label: "Basis",
          },
        ],
        paragraphs: normalizeParagraphs(
          undefined,
          [
            `The intervention envelope is currently summarised as "${packet.policySummary}".`,
            `This packet models ${pluralize(packet.interventionCount, "intervention")} and keeps the recommendation legible enough to scan in a single sitting.`,
            legalBasisCount > 0
              ? `At least ${pluralize(legalBasisCount, "intervention")} already map to explicit legal anchors, which reduces operator ambiguity during review.`
              : "The packet does not yet expose a dense legal-basis map for every intervention, so operators may still need to inspect supporting artifacts directly.",
          ],
          "policy_summary",
        ),
        provenanceItems: buildSectionProvenance("intervention", packet),
      }),
    );
  }

  if (
    packet.keyMetrics.length > 0 ||
    packet.metricComparisons.length > 0 ||
    asRecord(record.causal) ||
    asRecord(record.uncertainty)
  ) {
    const metricWarnings = packet.keyMetrics.flatMap(
      (metric) => metric.assumptionWarnings ?? [],
    );
    const comparisonWarnings = packet.metricComparisons.flatMap(
      (comparison) => comparison.assumptionWarnings,
    );
    const evidenceFootnotes = joinClauses(
      [...metricWarnings, ...comparisonWarnings].slice(0, 3),
    );
    const causal = asRecord(record.causal);
    const causalStatus = asString(causal?.status);
    const causalEstimate = asNumber(causal?.point_estimate);

    documentSections.push(
      buildDocumentSection(outline, {
        fallbackTitle: "Evidence and uncertainty",
        fallbackType: "evidence",
        footnotes: evidenceFootnotes
          ? [{ body: evidenceFootnotes, id: "evidence-assumptions" }]
          : undefined,
        id: "evidence",
        lede: packet.keyMetrics[0]
          ? `${metricSentence(packet.keyMetrics[0])}.`
          : undefined,
        marginNotes: [
          packet.keyMetrics[0]
            ? {
                anchorId: "evidence-lede",
                body:
                  packet.keyMetrics[0].ciLower !== null &&
                  packet.keyMetrics[0].ciUpper !== null
                    ? `${formatNumber(
                        (packet.keyMetrics[0].ciLevel ?? 0.95) * 100,
                        {
                          maximumFractionDigits: 0,
                        },
                      )}% interval ${formatNumber(
                        packet.keyMetrics[0].ciLower,
                        {
                          maximumFractionDigits: 2,
                        },
                      )} to ${formatNumber(packet.keyMetrics[0].ciUpper, {
                        maximumFractionDigits: 2,
                      })}.`
                    : "No explicit interval is attached to the lead metric.",
                id: "evidence-interval",
                label: "Interval",
              }
            : null,
          {
            anchorId: "evidence-p2",
            body:
              packet.metricComparisons.length > 0
                ? `${pluralize(packet.metricComparisons.length, "comparison")} in the validation family.`
                : "No metric-validation comparisons are attached to this packet.",
            id: "evidence-validation",
            label: "Validation",
          },
        ].filter(isDefined),
        paragraphs: normalizeParagraphs(
          record.evidence_summary_blocks,
          [
            packet.keyMetrics.length > 1
              ? `${joinClauses(
                  packet.keyMetrics
                    .slice(1, 3)
                    .map((metric) => metricSentence(metric)),
                )}.`
              : "Only one primary metric is currently surfaced above the fold.",
            packet.metricComparisons.length > 0
              ? `The packet carries ${pluralize(packet.metricComparisons.length, "metric comparison")} under ${
                  packet.metricValidationFamilyAdjustment?.method
                    ? `${packet.metricValidationFamilyAdjustment.method.toUpperCase()} family adjustment`
                    : "an explicit validation family"
                }, helping the reader separate directional movement from statistically defensible movement.`
              : "No formal metric-validation family is attached, so the evidence section remains descriptive rather than adjudicative.",
            causalStatus || causalEstimate !== null
              ? `Causal evidence is currently reported as ${
                  causalStatus ? formatEnum(causalStatus) : "available"
                }${
                  causalEstimate !== null
                    ? ` with a point estimate of ${formatNumber(
                        causalEstimate,
                        {
                          maximumFractionDigits: 3,
                        },
                      )}`
                    : ""
                }.`
              : "No standalone causal summary is embedded in the current packet preview.",
          ],
          "evidence",
        ),
        provenanceItems: buildSectionProvenance("evidence", packet),
        pullQuote: packet.keyMetrics[0]
          ? metricSentence(packet.keyMetrics[0])
          : undefined,
      }),
    );
  }

  if (distributional) {
    const firstBreakdown = distributional.breakdowns[0];
    const exposedRows = firstBreakdown?.rows.slice(0, 4) ?? [];
    const hardestHit = [...exposedRows].sort(
      (left, right) => left.primaryDelta - right.primaryDelta,
    )[0];

    documentSections.push(
      buildDocumentSection(outline, {
        definitions: [
          {
            definition:
              distributional.giniBefore !== null
                ? formatNumber(distributional.giniBefore, {
                    maximumFractionDigits: 2,
                  })
                : "-",
            term: "Gini before",
          },
          {
            definition:
              distributional.giniAfter !== null
                ? formatNumber(distributional.giniAfter, {
                    maximumFractionDigits: 2,
                  })
                : "-",
            term: "Gini after",
          },
          {
            definition:
              distributional.giniDelta !== null
                ? formatNumber(distributional.giniDelta, {
                    maximumFractionDigits: 2,
                    signDisplay: "always",
                  })
                : "-",
            term: "Delta",
          },
        ],
        fallbackTitle: "Distributional effects",
        fallbackType: "evidence",
        highlights: exposedRows.map(
          (row) =>
            `${row.cohortLabel} — ${formatNumber(row.primaryDelta, {
              maximumFractionDigits: 2,
              signDisplay: "always",
            })}`,
        ),
        highlightsTitle: firstBreakdown
          ? `${firstBreakdown.dimensionLabel} cohorts`
          : undefined,
        id: "distributional",
        lede: `${formatPercent(distributional.winnersShare)} of modelled cohorts improve while ${formatPercent(distributional.losersShare)} worsen.`,
        marginNotes: [
          {
            anchorId: "distributional-lede",
            body: `${pluralize(distributional.vulnerableLosersCount, "vulnerable loser")} appear in the current preview.`,
            id: "distributional-vulnerable",
            label: "Vulnerability",
          },
          hardestHit
            ? {
                anchorId: "distributional-p1",
                body: `${hardestHit.cohortLabel} is the steepest downside cohort at ${formatNumber(
                  hardestHit.primaryDelta,
                  {
                    maximumFractionDigits: 2,
                    signDisplay: "always",
                  },
                )}.`,
                id: "distributional-hardest-hit",
                label: "Hardest hit",
              }
            : null,
        ].filter(isDefined),
        paragraphs: normalizeParagraphs(
          undefined,
          [
            `The distributional layer records ${pluralize(distributional.winnersCount, "winner")} and ${pluralize(distributional.losersCount, "loser")} in the current policy simulation.`,
            hardestHit
              ? `${hardestHit.cohortLabel} currently carries the sharpest negative delta, which is the first place an analyst should inspect for compensating policy design.`
              : "No cohort-level downside standouts are attached to the previewed distributional bundle.",
            distributional.giniDelta !== null
              ? `Overall inequality shifts by ${formatNumber(
                  distributional.giniDelta,
                  {
                    maximumFractionDigits: 3,
                    signDisplay: "always",
                  },
                )}, which keeps the packet anchored in distributional rather than average-case reasoning.`
              : "The packet does not currently surface a comparable inequality delta.",
          ],
          "distributional",
        ),
        provenanceItems: buildSectionProvenance("evidence", packet),
      }),
    );
  }

  if (
    governance ||
    legalVerification ||
    sourceCoverage ||
    verifiedFindings.length > 0
  ) {
    const verifiedClaimCount =
      asNumber(legalVerification?.verified_claim_count) ?? 0;
    const unresolvedGaps = asArray(sourceCoverage?.unresolved_critical_gaps);

    documentSections.push(
      buildDocumentSection(outline, {
        fallbackTitle: "Governance and legal basis",
        fallbackType: "governance",
        footnotes: unresolvedGaps.length
          ? normalizeDescriptions(unresolvedGaps, 4)
          : undefined,
        highlights: verifiedFindings,
        highlightsTitle:
          verifiedFindings.length > 0 ? "Verified findings" : undefined,
        id: "governance",
        lede:
          packet.issues.blockerCount > 0
            ? `Governance still reports ${pluralize(packet.issues.blockerCount, "blocker")} before this packet can be treated as clear-to-act.`
            : "Governance currently clears without blockers in the previewed packet.",
        marginNotes: [
          {
            anchorId: "governance-lede",
            body:
              verifiedClaimCount > 0
                ? `${pluralize(verifiedClaimCount, "verified claim")} grounded in the legal verification pass.`
                : "No verified-claim count is exposed in this preview.",
            id: "governance-claims",
            label: "Claims",
          },
          {
            anchorId: "governance-p2",
            body:
              unresolvedGaps.length > 0
                ? `${pluralize(unresolvedGaps.length, "critical gap")} remain in source coverage.`
                : "Source coverage shows no unresolved critical gaps.",
            id: "governance-gaps",
            label: "Coverage",
          },
        ],
        paragraphs: normalizeParagraphs(
          undefined,
          [
            verifiedClaimCount > 0
              ? `Legal verification currently grounds ${pluralize(verifiedClaimCount, "verified claim")} across ${
                  asNumber(legalVerification?.verification_cycles_completed) ??
                  0
                } review cycle(s), which gives the packet a traceable legal spine.`
              : "No dense legal-verification bundle is surfaced in the current preview, so legal certainty still depends on supporting artifacts.",
            unresolvedGaps.length > 0
              ? `Source coverage still records ${pluralize(unresolvedGaps.length, "critical gap")}, so the packet should be read as operationally useful but not fully closed.`
              : "Source coverage does not expose critical unresolved gaps in the current packet preview.",
            needsExpertReview
              ? "The packet still requests expert review, which should be treated as a gating signal rather than a cosmetic warning."
              : "No additional expert-review escalation is attached to the legal or governance layers.",
          ],
          "governance",
        ),
        provenanceItems: buildSectionProvenance("governance", packet),
      }),
    );
  }

  if (replay || asRecord(record.runtime_contracts)) {
    const readiness = asString(replay?.readiness);
    const missingRefs = normalizeStrings(replay?.missing_refs, 5);
    const suggestedNextStep = asString(replay?.suggested_next_step);

    documentSections.push(
      buildDocumentSection(outline, {
        definitions: [
          {
            definition: readiness ? formatEnum(readiness) : "-",
            term: "Replay readiness",
          },
          {
            definition: asString(replay?.determinism_tier) ?? "-",
            term: "Determinism tier",
          },
          {
            definition:
              asNumber(replay?.effective_seed) !== null
                ? String(asNumber(replay?.effective_seed))
                : "-",
            term: "Seed",
          },
        ],
        fallbackTitle: "Replay and runtime contracts",
        fallbackType: "reproducibility",
        footnotes: missingRefs.map((body, index) => ({
          body,
          id: `replay-missing-${index + 1}`,
        })),
        id: "replay",
        lede: readiness
          ? `Replay readiness is currently ${formatEnum(readiness)}.`
          : "Replay readiness is not explicitly declared in the previewed packet.",
        marginNotes: [
          {
            anchorId: "replay-lede",
            body:
              suggestedNextStep ??
              "No explicit replay next-step is attached to this packet.",
            id: "replay-next-step",
            label: "Next step",
          },
        ],
        paragraphs: normalizeParagraphs(
          undefined,
          [
            asString(replay?.strategy_hint)
              ? `The packet currently points operators toward the ${formatEnum(
                  asString(replay?.strategy_hint) ?? "none",
                )} replay path.`
              : "No replay strategy hint is exposed in the preview.",
            missingRefs.length > 0
              ? "Replay completeness is still limited by missing references, so exact re-execution would require additional artifact persistence."
              : "No missing replay references are listed, which is the strongest signal that this packet can be rerun without manual reconstruction.",
            asBoolean(replay?.fallback_from_decision_packet) === true
              ? "The runtime is currently falling back from the decision packet rather than from full replay-grade inputs."
              : "The preview does not indicate a fallback-from-packet replay path.",
          ],
          "replay",
        ),
        provenanceItems: buildSectionProvenance("reproducibility", packet),
      }),
    );
  }

  if (analysisLimits || degradedPaths.length > 0 || notes.length > 0) {
    const labels = normalizeStrings(analysisLimits?.labels, 6);

    documentSections.push(
      buildDocumentSection(outline, {
        fallbackTitle: "Limits and degraded paths",
        fallbackType: "problem",
        footnotes: degradedPaths,
        highlights: notes,
        highlightsTitle: notes.length > 0 ? "Packet notes" : undefined,
        id: "analysis_limits",
        lede:
          labels.length > 0
            ? `Current analysis limits include ${joinClauses(labels.map((label) => formatEnum(label)))}.`
            : "The packet does not enumerate named analysis-limit labels in the current preview.",
        marginNotes: [
          {
            anchorId: "analysis_limits-lede",
            body:
              degradedPaths.length > 0
                ? `${pluralize(degradedPaths.length, "degraded path")} are still recorded.`
                : "No degraded paths are listed in the current preview.",
            id: "analysis-limits-degraded",
            label: "Degraded",
          },
        ],
        paragraphs: normalizeParagraphs(
          undefined,
          [
            asBoolean(analysisLimits?.decision_packet_degraded) === true
              ? "The packet explicitly marks itself as degraded, so all downstream reading should be framed as conditional rather than final."
              : "No global degraded flag is attached to the packet-level analysis limits.",
            degradedPaths.length > 0
              ? "Degraded paths remain concentrated in supporting sections rather than in the UI shell, which is exactly why they should stay visible in the prose surface."
              : "The packet preview exposes no degraded-path envelopes, although reviewers should still scan the supporting artifacts when decisions are consequential.",
            notes.length > 0
              ? "Editorial notes remain attached to the packet and should be preserved in any exported or printed rendering."
              : "No free-form packet notes are attached to the current preview.",
          ],
          "analysis_limits",
        ),
        provenanceItems: buildSectionProvenance("problem", packet),
      }),
    );
  }

  if (documentSections.length === 0) {
    return null;
  }

  const outlineOrder = Array.from(outline.keys());
  const orderedSections =
    outlineOrder.length > 0
      ? [...documentSections].sort((left, right) => {
          const leftIndex = outlineOrder.indexOf(left.id);
          const rightIndex = outlineOrder.indexOf(right.id);
          if (leftIndex === -1 && rightIndex === -1) {
            return 0;
          }
          if (leftIndex === -1) {
            return 1;
          }
          if (rightIndex === -1) {
            return -1;
          }
          return leftIndex - rightIndex;
        })
      : documentSections;

  return {
    deck: "Decision packet · reading view",
    sections: orderedSections,
    subtitle: [
      `Run ${packet.runId}`,
      packet.generatedAt ? formatDate(packet.generatedAt) : null,
      `${formatEnum(packet.confidence)} confidence`,
    ]
      .filter(Boolean)
      .join(" · "),
    summary: executiveSummary ?? packet.policySummary,
    title:
      executiveSummary && executiveSummary !== packet.policySummary
        ? executiveSummary
        : `Decision packet for ${packet.runId}`,
  };
}

function SectionBody({
  inlineMarginNotes,
  section,
}: {
  inlineMarginNotes: boolean;
  section: ReadingViewSection;
}) {
  const { t } = useOptionalI18n();
  const footnotes = section.footnotes ?? [];
  let footnoteCursor = 0;
  const ledeAuthor = section.paragraphs[0]?.author ?? "human";

  return (
    <div className="reading-section-body">
      {section.lede ? (
        <AuthoredText
          as="p"
          author={ledeAuthor}
          className="text-[1.18rem] leading-[1.75] text-[color:color-mix(in_srgb,var(--ink)_92%,transparent)]"
        >
          <span data-margin-anchor={`${section.id}-lede`} />
          {section.lede}{" "}
          {footnotes[footnoteCursor] ? (
            <FootnoteReference
              noteId={footnotes[footnoteCursor++].id}
              label={String(footnoteCursor)}
            />
          ) : null}
        </AuthoredText>
      ) : null}

      {section.pullQuote ? <PullQuote>{section.pullQuote}</PullQuote> : null}

      {section.definitions?.length ? (
        <DefinitionList items={section.definitions} />
      ) : null}

      {section.highlights?.length ? (
        <div>
          {section.highlightsTitle ? (
            <p
              className="text-muted mb-3 text-[0.72rem] font-semibold tracking-[0.18em] uppercase"
              data-authored-exempt="true"
              data-authored-exempt-reason="Reading-view highlight title is structural chrome, not authored prose."
            >
              {section.highlightsTitle}
            </p>
          ) : null}
          <ul className="reading-inline-list">
            {section.highlights.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {section.paragraphs.map((paragraph, index) => (
        <AuthoredText
          key={paragraph.id}
          as="p"
          author={paragraph.author}
          authorAgentVersion={paragraph.authorAgentVersion}
          confidence={paragraph.confidence}
          reviewedByHuman={paragraph.reviewedByHuman}
          sourceRef={paragraph.sourceRef}
          timestamp={paragraph.timestamp}
        >
          <span data-margin-anchor={`${section.id}-p${index + 1}`} />
          {paragraph.content}{" "}
          {footnotes[footnoteCursor] ? (
            <FootnoteReference
              noteId={footnotes[footnoteCursor++].id}
              label={String(footnoteCursor)}
            />
          ) : null}
        </AuthoredText>
      ))}

      {section.provenanceItems?.length ? (
        <ProvenanceStrip
          className="mt-4"
          density="compact"
          items={section.provenanceItems}
          title={t("pages.artifacts.readingView.provenanceTitle")}
        />
      ) : null}

      {inlineMarginNotes && section.marginNotes?.length ? (
        <MarginNotes inline notes={section.marginNotes} />
      ) : null}

      {section.footnotes?.length ? (
        <FootnoteList notes={section.footnotes} />
      ) : null}
    </div>
  );
}

export function MonographLayout({ document, className }: MonographLayoutProps) {
  const { t } = useOptionalI18n();
  const articleRef = useRef<HTMLElement | null>(null);
  const { activeSectionId, progress } = useReadingProgress(articleRef);
  const { positions, isInline } = useMarginNoteAnchors(articleRef);
  const marginNotes = useMemo(
    () => document.sections.flatMap((section) => section.marginNotes ?? []),
    [document.sections],
  );

  return (
    <div className={cn("monograph-layout", className)}>
      <aside className="monograph-sidebar">
        <div className="monograph-sidebar-card">
          <span className="monograph-medallion">
            <JanusGlyph decorative size={32} variant="mark" />
          </span>
          {document.deck ? (
            <p
              className="text-muted text-[0.72rem] font-semibold tracking-[0.2em] uppercase"
              data-authored-exempt="true"
              data-authored-exempt-reason="Reading-view deck label is structural chrome, not authored prose."
            >
              {document.deck}
            </p>
          ) : null}
          <div>
            <h1 className="text-[1.45rem] leading-tight font-semibold tracking-tight">
              {document.title}
            </h1>
            {document.subtitle ? (
              <p
                className="text-muted mt-2 text-sm leading-relaxed"
                data-authored-exempt="true"
                data-authored-exempt-reason="Reading-view subtitle is structural chrome, not authored prose."
              >
                {document.subtitle}
              </p>
            ) : null}
          </div>
          <div className="monograph-progress" aria-hidden="true">
            <span style={{ transform: `scaleX(${progress})` }} />
          </div>
        </div>
        <TableOfContentsGlyphed
          activeSectionId={activeSectionId}
          sections={document.sections}
        />
      </aside>

      <main className="monograph-main">
        <div className="monograph-prose-frame">
          <article
            ref={articleRef}
            className="prose"
            aria-label={document.title}
          >
            <header className="mb-12">
              {document.summary ? (
                <AuthoredText
                  as="p"
                  author="human"
                  className="text-xl leading-[1.7] text-[color:color-mix(in_srgb,var(--ink)_94%,transparent)]"
                >
                  {document.summary}
                </AuthoredText>
              ) : null}
            </header>

            <div className="space-y-14">
              {document.sections.map((section) => (
                <section
                  key={section.id}
                  id={section.id}
                  className="monograph-section scroll-mt-24"
                  data-reading-section-id={section.id}
                >
                  <header className="reading-section-header">
                    <p
                      className="text-muted flex items-center gap-2 text-[0.72rem] font-semibold tracking-[0.18em] uppercase"
                      data-authored-exempt="true"
                      data-authored-exempt-reason="Reading-view section label is structural chrome, not authored prose."
                    >
                      <JanusGlyph decorative size={16} variant="line" />
                      {sectionLabelForType(section.sectionType)}
                    </p>
                    <h2>{section.title}</h2>
                  </header>
                  <SectionBody inlineMarginNotes={isInline} section={section} />
                </section>
              ))}
            </div>
          </article>

          {!isInline ? (
            <MarginNotes notes={marginNotes} positions={positions} />
          ) : null}
        </div>
      </main>
    </div>
  );
}
