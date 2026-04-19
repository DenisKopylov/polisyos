import type { RunDeckSnapshot } from "@/features/runs/domain/compare";

export const ATLAS_STANDALONE_DECK_TEMPLATE: RunDeckSnapshot = {
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
        label: "Decision score",
        tone: "ok",
        value: "0.78",
      },
      {
        label: "Blocker state",
        tone: "warn",
        value: "1",
      },
      {
        label: "Impact delta",
        tone: "neutral",
        value: "+1.8%",
      },
      {
        label: "Artifact continuity",
        tone: "neutral",
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
    decisionScore: 0.78,
    governanceIssues: [],
    impactRows: [
      {
        display: "+1.8%",
        label: "Household stability",
        value: 1.8,
      },
      {
        display: "-0.6%",
        label: "Administrative load",
        value: -0.6,
      },
      {
        display: "+2.1 pts",
        label: "Coverage confidence",
        value: 2.1,
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
