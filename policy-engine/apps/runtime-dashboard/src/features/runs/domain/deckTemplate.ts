import type { RunDeckSnapshot } from "@/features/runs/domain/compare";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";
import type { QuantityValueOutput } from "@polisyos/runtime-api-client";

function templateQuantity(input: {
  label: string;
  metricId: string;
  point: number;
  unit?: QuantityValueOutput["unit"];
}): QuantityValueOutput {
  return untracedDecisionQuantity({
    ...input,
    reasonCode: "fixture_only_atlas_deck_template",
    trackingIssue: "ATLAS-DS4-C06",
  });
}

const templateDecisionScore = templateQuantity({
  label: "Decision score",
  metricId: "template.decision_score",
  point: 0.78,
  unit: { code: "1", display: "ratio", system: "ucum" },
});
const templateHouseholdStability = templateQuantity({
  label: "Household stability",
  metricId: "template.household_stability_delta",
  point: 1.8,
  unit: { code: "%", display: "%", system: "ucum" },
});
const templateAdministrativeLoad = templateQuantity({
  label: "Administrative load",
  metricId: "template.administrative_load_delta",
  point: -0.6,
  unit: { code: "%", display: "%", system: "ucum" },
});
const templateCoverageConfidence = templateQuantity({
  label: "Coverage confidence",
  metricId: "template.coverage_confidence_delta",
  point: 2.1,
  unit: { code: "1", display: "pts", system: "ucum" },
});

export const ATLAS_STANDALONE_DECK_TEMPLATE: RunDeckSnapshot = {
  fixture_authority: "fixture_only",
  close: {
    commentWindow:
      "Keep a 72-hour stakeholder comment window open before ratification.",
    downstreamDependencies: [
      "Audit packet for executive review",
      "Promotion lane approval notes",
      "Artifact continuity across deck and report",
    ],
    nextAction: "Ratify the packet and circulate the stakeholder deck.",
  },
  cover: {
    eyebrow: "Standalone Atlas template",
    subtitle: "Reusable executive deck frame for runtime decision packets",
    title: "Atlas policy decision template",
  },
  evidence: {
    body: "Use this slot for the strongest claim, dissent excerpt, or provenance note that should travel with the decision.",
    provenance: "Connector / artifact / note provenance",
    quote:
      "Template evidence quote: replace with the strongest runtime-backed sentence available.",
    title: "Evidence and dissent",
  },
  metrics: {
    cards: [
      {
        kind: "quantity",
        label: "Decision score",
        quantity: templateDecisionScore,
      },
      {
        kind: "text",
        label: "Blocker state",
        value: "1",
      },
      {
        kind: "quantity",
        label: "Impact delta",
        quantity: templateHouseholdStability,
      },
      {
        kind: "text",
        label: "Artifact continuity",
        value: "4 refs",
      },
    ],
    title: "Rollout impact and operating posture",
  },
  report: {
    artifactRefs: [
      { artifact_id: "template-artifact-1", kind: "decision_card" },
      { artifact_id: "template-artifact-2", kind: "report_bundle" },
    ],
    auditTrail: [],
    blockerCount: 1,
    decisionConfidence: "High",
    decisionHeadline: "Policy packet is ready for executive review.",
    decisionScore: templateDecisionScore,
    governanceIssues: [],
    impactRows: [
      {
        label: "Household stability",
        quantity: templateHouseholdStability,
      },
      {
        label: "Administrative load",
        quantity: templateAdministrativeLoad,
      },
      {
        label: "Coverage confidence",
        quantity: templateCoverageConfidence,
      },
    ],
    mainUncertainty:
      "Template uncertainty placeholder: replace with the main unresolved evidence or governance risk.",
    primaryVerdict: "Ratify with conditions",
    runId: "template-run",
    status: "in_review",
    strongestEvidence: {
      body: "Template strongest evidence summary describing the most credible supporting signal.",
      provenance: "Atlas template provenance",
      title: "Template strongest evidence",
    },
    transportStatus: "stable",
  },
  tradeoff: {
    hold: [
      "Keep this lane for blockers, uncertainty, and transport cautions.",
      "Add the main thing that would cause a decision hold.",
      "Document the explicit review owner and comment deadline.",
    ],
    ratify: [
      "Keep this lane for the strongest reasons to proceed now.",
      "Reference evidence coverage, score, and operator readiness.",
      "Call out which artifacts remain continuous across report and deck.",
    ],
    title: "Ratify now versus hold for review",
  },
  verdict: {
    blockers: "1 blocker still needs operator attention.",
    confidence: "High",
    headline: "A polished, stakeholder-ready headline belongs here.",
    status: "In review",
    verdict: "Ratify with conditions",
  },
};
