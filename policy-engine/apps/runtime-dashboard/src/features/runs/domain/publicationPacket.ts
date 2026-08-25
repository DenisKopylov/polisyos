import type {
  DecisionCardViewModel,
  DecisionMetric,
} from "@/shared/lib/domain/decision";
import type { RunEvidenceContext } from "@/shared/lib/domain/evidence";
import type { GovernanceIssueView } from "@/shared/lib/domain/governance";
import {
  createInteractionState,
  type InteractionState,
} from "@/shared/lib/domain/statusOwnership";
import { untracedDecisionQuantity } from "@/shared/ui/quantity/quantity-value";
import type { QuantityValueOutput } from "@polisyos/runtime-api-client";
import {
  DEFAULT_PROJECTION_USE_LIMITS,
  type GeneratedProjectionAuthority,
} from "@/shared/lib/domain/projectionFailClosed";

export type ToulminNodeKind =
  | "backing"
  | "claim"
  | "grounds"
  | "rebuttal"
  | "warrant";

export type ArgumentMapNode = {
  detail: string;
  id: string;
  kind: ToulminNodeKind;
  label: string;
  refs: string[];
};

export type ArgumentMapEdge = {
  from: string;
  relation: "answers" | "backs" | "grounds" | "rebuts" | "warrants";
  to: string;
};

export type ArgumentMapView = {
  edges: ArgumentMapEdge[];
  nodes: ArgumentMapNode[];
  rootClaimId: string;
};

export type ComprehensionDescriptor = {
  freshness: string;
  id: string;
  intent: string;
  label: string;
  provenance: string;
};

export type DerivationStep = {
  detail: string;
  id: string;
  kind: "artifact" | "calculation" | "model" | "source" | "transform";
  label: string;
};

export type DeterministicExplanationPart = {
  contributionShare: number;
  label: string;
  value: string;
};

export type DeterministicExplanation = {
  derivationPath: DerivationStep[];
  id: string;
  label: string;
  narrative: string;
  parts: DeterministicExplanationPart[];
  quantity: QuantityValueOutput;
  subjectRef: string;
};

export type GlossaryTerm = {
  definition: string;
  fixedAt: string;
  owner: string;
  provenanceRef: string;
  term: string;
};

export type ConfidenceLadderItem = {
  id: string;
  label: string;
  reason: string;
  /** Opaque producer label when one exists; DS4 does not mint a rung vocabulary. */
  rung: string | null;
  score: QuantityValueOutput;
  targetRef: string;
};

export type CitationModelCardSection = {
  body: string;
  footnoteRefs: string[];
  id: string;
  provenanceRefs: string[];
  title: string;
};

export type CitationReference = {
  id: string;
  label: string;
  locator: string;
  type: "artifact" | "bibliography" | "dataset" | "model" | "policy";
};

export type CitationModelCard = {
  modelId: string;
  references: CitationReference[];
  sections: CitationModelCardSection[];
  title: string;
};

export type CoverageRegion = {
  caveat: string;
  density: number;
  displayState: CandidateCoverageDisplayState;
  evidenceRefs: string[];
  label: string;
};

export type CandidateCoverageDisplayState = InteractionState;
export type CandidateCoverageCaveatState = InteractionState;

export type CoverageCaveat = {
  caveatState: CandidateCoverageCaveatState;
  regions: CoverageRegion[];
  summary: string;
};

export type ThresholdMicrocontract = {
  aboveCount: null;
  belowCount: null;
  calibrationCaveat: string;
  edgeCases: [];
  epsilon: null;
  nearLineCount: null;
  policyRef: string;
  threshold: null;
};

export type BureaucraticPublicationForm = {
  astPatchContract: string;
  editSurfaceId: string;
  genre: "nakaz" | "postanova" | "rozporiadzhennia" | "vysnovok";
  label: string;
  legalOrder: string[];
  locale: "uk-UA";
  renderSurfaceId: string;
};

export type PublicDecisionSummary = {
  confidence: string | null;
  generatedAt: string | null;
  headline: string;
  policySummary: string;
  runId: string;
  verdict: string | null;
};

export type PublicDecisionPacket = {
  argumentMap: ArgumentMapView;
  bureaucraticForms: BureaucraticPublicationForm[];
  comprehension: ComprehensionDescriptor[];
  confidenceLadder: ConfidenceLadderItem[];
  coverageCaveat: CoverageCaveat;
  decision: PublicDecisionSummary;
  deterministicExplanations: DeterministicExplanation[];
  glossary: GlossaryTerm[];
  modelCard: CitationModelCard;
  packetHash: string;
  projectionSemantics: PublicProjectionSemantics;
  schema: "polisyos.public_decision_packet.v1";
  thresholdContract: ThresholdMicrocontract;
  trustFraming: PublicTrustFraming;
};

export type PublicProjectionSemantics = {
  authorityRole: string | null;
  closeoutTruth: GeneratedProjectionAuthority["closeout_truth"] | null;
  displayStates: InteractionState[];
  evidenceClass: string | null;
  generatedAt: string | null;
  mayNotBeUsedFor: string[];
  primaryDisplayState: InteractionState;
  projectionPolicy: NonNullable<
    GeneratedProjectionAuthority["projection_policy"]
  > | null;
  provenanceKind: string | null;
  surface: string | null;
};

export type FrontendIntegritySignatureNotice = {
  authorityCaveat: string;
  badge: string;
  label: string;
  signatureCue: "frontend_integrity_signature_not_authoritative";
};

export type PublicTrustFraming = {
  authorityRole: "not_closeout_authority";
  closeoutAuthorityCaveat: string;
  integritySignatureNotice: FrontendIntegritySignatureNotice;
  mayNotBeUsedFor: string[];
  /** Compatibility shape only; the client no longer emits inferred scenarios. */
  scenarioCaveats: never[];
  visibleCaveat: string;
};

export type SignedPublicDecisionPacket = PublicDecisionPacket & {
  publicUrlPath: string;
  signature: string;
  signedId: string;
};

export type PublicDecisionPacketInput = {
  decisionScore?: QuantityValueOutput | null;
  decisionView?: DecisionCardViewModel | null;
  evidenceContext?: RunEvidenceContext | null;
  governanceIssues?: GovernanceIssueView[];
  now?: string;
  policyDesignCaseProjection?: GeneratedProjectionAuthority | null;
  runId: string;
};

export type SignedPacketVerification =
  | {
      packet: SignedPublicDecisionPacket;
      reason: null;
      valid: true;
    }
  | {
      packet: null;
      reason: "bad_format" | "bad_payload" | "bad_signature";
      valid: false;
    };

const PUBLIC_PACKET_SCHEMA = "polisyos.public_decision_packet.v1" as const;
const SIGNATURE_SALT = "polisyos.atlas.public-viewer.v1";
const FALLBACK_GENERATED_AT = "1970-01-01T00:00:00.000Z";
const TRUST_FRAMING_VISIBLE_CAVEAT =
  "Use runtime scorecard/readiness authority before approval or closeout.";
const TRUST_FRAMING_CLOSEOUT_CAVEAT =
  "Frontend signatures, badges, labels, and projections are not closeout authority.";
const FRONTEND_INTEGRITY_SIGNATURE_CAVEAT =
  "This frontend signature verifies packet integrity only; it is not trust, approval, publication, or closeout authority.";
const GLOSSARY_TERMS: GlossaryTerm[] = [
  {
    definition:
      "A decision-bearing record that keeps outcome, evidence, uncertainty, provenance and review status together.",
    fixedAt: "2026-04-29",
    owner: "Atlas design system",
    provenanceRef: "docs/brand/ATLAS_DESIGN_SYSTEM.md#decision-packet",
    term: "decision packet",
  },
  {
    definition:
      "A trace from source data through transformations, model output and artifact publication.",
    fixedAt: "2026-04-29",
    owner: "Evidence Fabric",
    provenanceRef: "docs/brand/ATLAS_DESIGN_SYSTEM.md#provenance",
    term: "provenance",
  },
  {
    definition:
      "A confidence, interval or identifiability marker that changes how strongly a claim can be used.",
    fixedAt: "2026-04-29",
    owner: "Scientist layer",
    provenanceRef: "docs/brand/ATLAS_DESIGN_SYSTEM.md#uncertainty",
    term: "uncertainty",
  },
  {
    definition:
      "A policy cutoff contract that exposes the threshold, edge cases and calibration caveat.",
    fixedAt: "2026-04-29",
    owner: "PolicyOS governance",
    provenanceRef: "docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md#f4",
    term: "threshold microcontract",
  },
  {
    definition:
      "A public warning attached when affected geography or cohort evidence is sparse.",
    fixedAt: "2026-04-29",
    owner: "Evidence Fabric",
    provenanceRef: "docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md#f3",
    term: "coverage caveat",
  },
];

const PUBLICATION_FORMS: BureaucraticPublicationForm[] = [
  {
    astPatchContract: "bureaucratic_ast_patch.v1",
    editSurfaceId: "forms.ua.nakaz.edit",
    genre: "nakaz",
    label: "Наказ",
    legalOrder: ["requisites", "preamble", "order", "control", "signature"],
    locale: "uk-UA",
    renderSurfaceId: "forms.ua.nakaz.render",
  },
  {
    astPatchContract: "bureaucratic_ast_patch.v1",
    editSurfaceId: "forms.ua.rozporiadzhennia.edit",
    genre: "rozporiadzhennia",
    label: "Розпорядження",
    legalOrder: [
      "requisites",
      "legal_basis",
      "directive",
      "execution",
      "signature",
    ],
    locale: "uk-UA",
    renderSurfaceId: "forms.ua.rozporiadzhennia.render",
  },
  {
    astPatchContract: "bureaucratic_ast_patch.v1",
    editSurfaceId: "forms.ua.postanova.edit",
    genre: "postanova",
    label: "Постанова",
    legalOrder: [
      "requisites",
      "preamble",
      "operative_part",
      "annexes",
      "signature",
    ],
    locale: "uk-UA",
    renderSurfaceId: "forms.ua.postanova.render",
  },
  {
    astPatchContract: "bureaucratic_ast_patch.v1",
    editSurfaceId: "forms.ua.vysnovok.edit",
    genre: "vysnovok",
    label: "Висновок",
    legalOrder: [
      "requisites",
      "question",
      "analysis",
      "evidence",
      "conclusion",
      "signature",
    ],
    locale: "uk-UA",
    renderSurfaceId: "forms.ua.vysnovok.render",
  },
];

function stableJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(stableJson).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, nested]) => `${JSON.stringify(key)}:${stableJson(nested)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function stableHash(value: unknown) {
  const source = typeof value === "string" ? value : stableJson(value);
  let hash = 0x811c9dc5;
  for (let index = 0; index < source.length; index += 1) {
    hash ^= source.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function clamp(value: number, min = 0, max = 1) {
  return Math.max(min, Math.min(max, value));
}

function quantityPoint(value: QuantityValueOutput | null | undefined) {
  return typeof value?.point === "number" && Number.isFinite(value.point)
    ? value.point
    : null;
}

function publicationQuantity(input: {
  label: string;
  metricId: string;
  point: number | null | undefined;
  reasonCode: string;
  unit?: QuantityValueOutput["unit"];
}): QuantityValueOutput {
  return untracedDecisionQuantity({
    label: input.label,
    metricId: input.metricId,
    point: input.point,
    reasonCode: input.reasonCode,
    trackingIssue: "ATLAS-DS4-C06",
    unit: input.unit ?? { code: "1", display: "ratio", system: "ucum" },
  });
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values));
}

function publicRef(value: string | null | undefined, fallback: string) {
  const source = value?.trim() || fallback;
  const masked = source
    .replace(/\b\d{3}-\d{2}-\d{4}\b/g, "redacted_identifier")
    .replace(/\bssn[-:_]?[A-Z0-9-]*\b/gi, "redacted_identifier")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "redacted_email")
    .replace(/\bprivate_reviewer\b/gi, "restricted_reviewer")
    .replace(/\braw_restricted\b/gi, "restricted")
    .replace(/\bconfidential\b/gi, "restricted")
    .replace(/\bsecret\b/gi, "restricted")
    .replace(/\b\d{3,}\b/g, "redacted_number")
    .replace(/[^A-Za-z0-9:._/-]+/g, "_")
    .slice(0, 96);
  return masked.length > 0 ? masked : fallback;
}

function publicText(value: string | null | undefined, fallback: string) {
  const source = value?.trim() || fallback;
  const masked = source
    .replace(/\b\d{3}-\d{2}-\d{4}\b/g, "redacted identifier")
    .replace(/\bssn[-:_]?[A-Z0-9-]*\b/gi, "redacted identifier")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "redacted email")
    .replace(/\bprivate reviewer\b/gi, "restricted reviewer")
    .replace(/\braw restricted\b/gi, "restricted")
    .replace(/\bconfidential\b/gi, "restricted")
    .replace(/\bsecret\b/gi, "restricted")
    .replace(/\b\d{6,}\b/g, "redacted number")
    .slice(0, 320);
  return masked.length > 0 ? masked : fallback;
}

function issueRef(issue: GovernanceIssueView, index: number) {
  return publicRef(issue.passId ?? issue.code, `public-issue-${index + 1}`);
}

function metricRef(metric: DecisionMetric, index: number) {
  return `metric:${publicRef(metric.name, `metric-${index + 1}`)}`;
}

function metricLabel(metric: DecisionMetric, index: number) {
  return publicText(metric.name, `Metric ${index + 1}`);
}

function formatMetric(metric: DecisionMetric) {
  return `${metric.formatted}${metric.unit}`;
}

function buildDecisionSummary(
  input: PublicDecisionPacketInput,
): PublicDecisionSummary {
  const decision = input.decisionView;
  const runId = publicRef(decision?.runId ?? input.runId, input.runId);
  const verdict = decision?.verdict?.trim() || null;
  return {
    confidence: decision?.confidence ?? null,
    generatedAt: decision?.generatedAt ?? null,
    headline: verdict
      ? "Public decision: owner verdict recorded"
      : "Public decision: owner verdict unavailable",
    policySummary: publicText(
      decision?.policySummary,
      "No restricted decision text is included in this public packet.",
    ),
    runId,
    verdict,
  };
}

function buildArgumentMap(input: {
  decision: PublicDecisionSummary;
  evidenceContext?: RunEvidenceContext | null;
  governanceIssues: GovernanceIssueView[];
  metrics: DecisionMetric[];
}): ArgumentMapView {
  const issueRefs = input.governanceIssues.map(issueRef);
  const evidenceRefs = [
    input.evidenceContext?.evidenceBundleRef?.artifact_id,
    input.evidenceContext?.dataSnapshotRef?.artifact_id,
    input.evidenceContext?.inputBindingsRef?.artifact_id,
  ]
    .filter((ref): ref is string => Boolean(ref))
    .map((ref, index) => publicRef(ref, `artifact-${index + 1}`));
  const rootClaimId = `claim:${input.decision.runId}:verdict`;
  const [primaryMetric] = input.metrics;
  const nodes: ArgumentMapNode[] = [
    {
      detail: input.decision.policySummary,
      id: rootClaimId,
      kind: "claim",
      label: input.decision.headline,
      refs: [input.decision.runId],
    },
    {
      detail: primaryMetric
        ? `${metricLabel(primaryMetric, 0)} is ${formatMetric(primaryMetric)}.`
        : "No public metric was attached to this packet.",
      id: `grounds:${input.decision.runId}:metrics`,
      kind: "grounds",
      label: "Published grounds",
      refs: input.metrics.map(metricRef),
    },
    {
      detail:
        "The recommendation is warranted only when the published metrics, uncertainty, coverage and governance status remain aligned.",
      id: `warrant:${input.decision.runId}:policy-standard`,
      kind: "warrant",
      label: "Policy warrant",
      refs: ["atlas:publication:warrant"],
    },
    {
      detail:
        evidenceRefs.length > 0
          ? "The public packet cites evidence artifacts without exposing private raw context."
          : "The packet has no public evidence artifact reference.",
      id: `backing:${input.decision.runId}:evidence`,
      kind: "backing",
      label: "Evidence backing",
      refs: evidenceRefs,
    },
    {
      detail:
        issueRefs.length > 0
          ? `${issueRefs.length} public governance issue reference(s) are attached.`
          : "No public governance issue references were supplied; absence does not establish that no dispute exists.",
      id: `rebuttal:${input.decision.runId}:governance`,
      kind: "rebuttal",
      label: "Governance issue references",
      refs: issueRefs,
    },
  ];
  return {
    edges: [
      {
        from: nodes[1].id,
        relation: "grounds",
        to: rootClaimId,
      },
      {
        from: nodes[2].id,
        relation: "warrants",
        to: rootClaimId,
      },
      {
        from: nodes[3].id,
        relation: "backs",
        to: nodes[2].id,
      },
      {
        from: nodes[4].id,
        relation: "rebuts",
        to: rootClaimId,
      },
    ],
    nodes,
    rootClaimId,
  };
}

function buildConfidenceLadder(input: {
  decision: PublicDecisionSummary;
}): ConfidenceLadderItem[] {
  return [
    {
      id: `ladder:${input.decision.runId}:owner-confidence`,
      label: input.decision.confidence
        ? "Owner-recorded confidence label"
        : "Owner confidence unavailable",
      reason: input.decision.confidence
        ? "The producer label is preserved opaquely; the client does not convert it into a numeric confidence or trust posture."
        : "No owner-issued confidence quantity was supplied; absence remains unknown.",
      rung: null,
      score: publicationQuantity({
        label: "Owner confidence quantity",
        metricId: "public.confidence_ladder.owner_confidence.score",
        point: null,
        reasonCode: "owner_confidence_quantity_absent",
      }),
      targetRef: input.decision.runId,
    },
  ];
}

function buildDerivationPath(input: {
  evidenceContext?: RunEvidenceContext | null;
  metric: DecisionMetric;
  metricIndex: number;
}) {
  const sourceRef = publicRef(
    input.evidenceContext?.dataSnapshotRef?.artifact_id,
    "public-data-snapshot",
  );
  const bundleRef = publicRef(
    input.evidenceContext?.evidenceBundleRef?.artifact_id,
    "public-evidence-bundle",
  );
  return [
    {
      detail: "Published source evidence enters the public packet as a ref.",
      id: `derive:${input.metricIndex}:source`,
      kind: "source" as const,
      label: sourceRef,
    },
    {
      detail: "Evidence bundle binds source refs to decision metrics.",
      id: `derive:${input.metricIndex}:artifact`,
      kind: "artifact" as const,
      label: bundleRef,
    },
    {
      detail: "Model output reports the point estimate and interval.",
      id: `derive:${input.metricIndex}:model`,
      kind: "model" as const,
      label: metricLabel(input.metric, input.metricIndex),
    },
    {
      detail:
        "Publication adapter renders the same parts as deterministic prose.",
      id: `derive:${input.metricIndex}:publication`,
      kind: "transform" as const,
      label: "publication narrative",
    },
  ];
}

function buildDeterministicExplanations(input: {
  decision: PublicDecisionSummary;
  evidenceContext?: RunEvidenceContext | null;
  metrics: DecisionMetric[];
}): DeterministicExplanation[] {
  const fallbackQuantity = publicationQuantity({
    label: "Decision score fallback",
    metricId: "public.decision_metric.fallback",
    point: null,
    reasonCode: "public_packet_without_decision_metric",
    unit: { code: "1", display: "value", system: "ucum" },
  });
  const metrics = input.metrics.length
    ? input.metrics.map((metric, index) => {
        const label = metricLabel(metric, index);
        return {
          metric,
          quantity: publicationQuantity({
            label,
            metricId: `public.decision_metric.${index + 1}`,
            point: metric.value,
            reasonCode: "public_projection_without_runtime_quantity",
            unit: {
              code: metric.unit || "1",
              display: metric.unit || "value",
              system: "ucum",
            },
          }),
        };
      })
    : [
        {
          metric: {
            ciLevel: null,
            ciLower: null,
            ciUpper: null,
            formatted: "Unknown",
            name: "Decision score",
            unit: "",
            value: quantityPoint(fallbackQuantity) ?? Number.NaN,
          } satisfies DecisionMetric,
          quantity: fallbackQuantity,
        },
      ];
  return metrics.slice(0, 4).map(({ metric, quantity }, index) => {
    const hasInterval = metric.ciLower !== null && metric.ciUpper !== null;
    const intervalShare = hasInterval ? 0.25 : 0.1;
    const provenanceShare = input.evidenceContext?.evidenceBundleRef
      ? 0.2
      : 0.1;
    const pointShare = 1 - intervalShare - provenanceShare;
    const intervalText = hasInterval
      ? `interval ${metric.ciLower} to ${metric.ciUpper}`
      : "no public interval";
    return {
      derivationPath: buildDerivationPath({
        evidenceContext: input.evidenceContext,
        metric,
        metricIndex: index,
      }),
      id: `explanation:${input.decision.runId}:${index + 1}`,
      label: metricLabel(metric, index),
      narrative: `${metricLabel(metric, index)} is ${formatMetric(metric)} because the public point estimate carries ${Math.round(
        pointShare * 100,
      )}% of the explanation, uncertainty carries ${Math.round(
        intervalShare * 100,
      )}% (${intervalText}), and public provenance carries ${Math.round(
        provenanceShare * 100,
      )}%.`,
      parts: [
        {
          contributionShare: pointShare,
          label: "point estimate",
          value: formatMetric(metric),
        },
        {
          contributionShare: intervalShare,
          label: "uncertainty",
          value: intervalText,
        },
        {
          contributionShare: provenanceShare,
          label: "public provenance",
          value:
            input.evidenceContext?.evidenceBundleRef?.artifact_id ??
            "not published",
        },
      ],
      quantity,
      subjectRef: metricRef(metric, index),
    };
  });
}

function buildComprehensionDescriptors(input: {
  decision: PublicDecisionSummary;
  explanationCount: number;
}) {
  return [
    {
      freshness: input.decision.generatedAt ?? FALLBACK_GENERATED_AT,
      id: "phase35.argumentMap",
      intent:
        "Shows claim, grounds, warrant, backing and rebuttal as one auditable argument path.",
      label: "Argument map",
      provenance: input.decision.runId,
    },
    {
      freshness: input.decision.generatedAt ?? FALLBACK_GENERATED_AT,
      id: "phase35.deterministicExplanations",
      intent:
        "Turns decision-bearing numbers into reproducible non-LLM explanations.",
      label: "Deterministic explanations",
      provenance: `${input.explanationCount} explanation parts`,
    },
    {
      freshness: input.decision.generatedAt ?? FALLBACK_GENERATED_AT,
      id: "phase35.publicViewer",
      intent:
        "Presents only signed public packet data; no privileged API context is required.",
      label: "Public viewer",
      provenance: input.decision.runId,
    },
  ] satisfies ComprehensionDescriptor[];
}

function buildModelCard(input: {
  decision: PublicDecisionSummary;
  evidenceContext?: RunEvidenceContext | null;
  metrics: DecisionMetric[];
}): CitationModelCard {
  const refs: CitationReference[] = [
    {
      id: "ref:model",
      label: "PolicyOS decision model",
      locator: `model:${input.decision.runId}`,
      type: "model",
    },
    ...[
      input.evidenceContext?.evidenceBundleRef,
      input.evidenceContext?.dataSnapshotRef,
      input.evidenceContext?.inputBindingsRef,
    ]
      .filter((ref): ref is NonNullable<typeof ref> => Boolean(ref))
      .map<CitationReference>((ref, index) => ({
        id: `ref:artifact:${index + 1}`,
        label: ref.kind ?? "artifact",
        locator: publicRef(ref.artifact_id, `artifact-${index + 1}`),
        type: "artifact",
      })),
  ];
  return {
    modelId: `model:${input.decision.runId}`,
    references: refs,
    sections: [
      {
        body: "This card documents the public-facing model behavior used for the decision packet.",
        footnoteRefs: ["ref:model"],
        id: "intended-use",
        provenanceRefs: [input.decision.runId],
        title: "Intended use",
      },
      {
        body: input.metrics.length
          ? `Published metrics: ${input.metrics
              .map((metric, index) => metricLabel(metric, index))
              .join(", ")}.`
          : "No public metrics were attached.",
        footnoteRefs: refs.slice(1).map((ref) => ref.id),
        id: "inputs",
        provenanceRefs: refs.map((ref) => ref.locator),
        title: "Inputs and evidence",
      },
      {
        body: `The owner-recorded decision grade is ${input.decision.verdict ?? "unavailable"}; the recorded confidence label is ${input.decision.confidence ?? "unavailable"}.`,
        footnoteRefs: ["ref:model"],
        id: "validation",
        provenanceRefs: [input.decision.runId],
        title: "Validation",
      },
      {
        body: "Restricted notes, raw values and embargoed evidence are excluded from this public card.",
        footnoteRefs: [],
        id: "limitations",
        provenanceRefs: ["atlas:public-redaction"],
        title: "Limitations",
      },
    ],
    title: "Citation-grade model card",
  };
}

function coverageDisplayState(density: number): CandidateCoverageDisplayState {
  if (density >= 0.74) {
    return createInteractionState("high", "candidate_display");
  }
  if (density >= 0.5) {
    return createInteractionState("medium", "candidate_display");
  }
  return createInteractionState("low", "candidate_display");
}

function buildCoverageCaveat(
  evidenceContext: RunEvidenceContext | null | undefined,
): CoverageCaveat {
  const regions = (evidenceContext?.dataNeeds ?? []).map<CoverageRegion>(
    (need, index) => {
      const matchedPlanIds = need.matchedPlanIds ?? [];
      const qualityMin = Number.isFinite(need.qualityMin)
        ? need.qualityMin
        : 0.35;
      const matchedPlanCount = matchedPlanIds.length;
      const density = clamp(qualityMin * 0.7 + matchedPlanCount * 0.12);
      const displayState = coverageDisplayState(density);
      return {
        caveat:
          displayState.label === "low"
            ? "Calculated coverage falls in the low display band; inspect the source references."
            : displayState.label === "medium"
              ? "Calculated coverage falls in the middle display band; inspect the source references."
              : "Calculated coverage falls in the upper display band; publication readiness is not inferred.",
        density,
        displayState,
        evidenceRefs: matchedPlanIds.map((id, planIndex) =>
          publicRef(id, `plan-${index + 1}-${planIndex + 1}`),
        ),
        label: publicText(need.geography ?? need.metric, `region-${index + 1}`),
      };
    },
  );
  const fallbackRegions =
    regions.length > 0
      ? regions
      : [
          {
            caveat:
              "No geography-specific public evidence coverage is attached.",
            density: 0.32,
            displayState: createInteractionState("low", "candidate_display"),
            evidenceRefs: [],
            label: "coverage unspecified",
          },
        ];
  const hasLowDisplayBand = fallbackRegions.some(
    (region) => region.displayState.label === "low",
  );
  return {
    caveatState: createInteractionState(
      hasLowDisplayBand ? "caveat" : "clear",
      "candidate_display",
    ),
    regions: fallbackRegions,
    summary: hasLowDisplayBand
      ? "At least one calculated coverage display is in the low band; owner publication semantics are not inferred."
      : "No calculated coverage display is in the low band; owner publication semantics are not inferred.",
  };
}

function buildThresholdMicrocontract(input: {
  decisionView?: DecisionCardViewModel | null;
  runId: string;
}): ThresholdMicrocontract {
  const policyRef = `policy:${publicRef(
    input.decisionView?.runId ?? input.runId,
    input.runId,
  )}`;
  return {
    aboveCount: null,
    belowCount: null,
    calibrationCaveat:
      "Decision threshold proximity is unavailable until a producer threshold contract is supplied.",
    edgeCases: [],
    epsilon: null,
    nearLineCount: null,
    policyRef,
    threshold: null,
  };
}

function unsignedPacketHash(packet: Omit<PublicDecisionPacket, "packetHash">) {
  return `pub:${stableHash(packet)}`;
}

function buildProjectionSemantics(
  projection: GeneratedProjectionAuthority | null | undefined,
): PublicProjectionSemantics {
  const primaryLabel = projection?.primary_state ?? "projection_absent";
  const ownerStates = projection
    ? uniqueStrings(
        projection.states.map((state) => state.trim()).filter(Boolean),
      )
    : [primaryLabel];
  return {
    authorityRole: projection?.authority_role ?? null,
    closeoutTruth: projection?.closeout_truth ?? null,
    displayStates: ownerStates.map((state) =>
      createInteractionState(state, "candidate_display"),
    ),
    evidenceClass: projection?.evidence_class ?? null,
    generatedAt: projection?.generated_at ?? null,
    mayNotBeUsedFor: uniqueStrings([
      ...DEFAULT_PROJECTION_USE_LIMITS,
      ...(projection?.may_not_be_used_for ?? []),
    ]),
    primaryDisplayState: createInteractionState(
      primaryLabel,
      "candidate_display",
    ),
    projectionPolicy: projection?.projection_policy ?? null,
    provenanceKind: projection?.provenance_kind ?? null,
    surface: projection?.surface ?? null,
  };
}

function buildTrustFraming(input: {
  projectionSemantics: PublicProjectionSemantics;
}): PublicTrustFraming {
  return {
    authorityRole: "not_closeout_authority",
    closeoutAuthorityCaveat: TRUST_FRAMING_CLOSEOUT_CAVEAT,
    integritySignatureNotice: {
      authorityCaveat: FRONTEND_INTEGRITY_SIGNATURE_CAVEAT,
      badge: "Integrity only",
      label: "Frontend integrity signature",
      signatureCue: "frontend_integrity_signature_not_authoritative",
    },
    mayNotBeUsedFor: uniqueStrings([
      ...DEFAULT_PROJECTION_USE_LIMITS,
      ...input.projectionSemantics.mayNotBeUsedFor,
    ]),
    scenarioCaveats: [],
    visibleCaveat: TRUST_FRAMING_VISIBLE_CAVEAT,
  };
}

export function buildPublicDecisionPacket(
  input: PublicDecisionPacketInput,
): PublicDecisionPacket {
  const governanceIssues = input.governanceIssues ?? [];
  const decision = buildDecisionSummary(input);
  const metrics = input.decisionView?.keyMetrics ?? [];
  const deterministicExplanations = buildDeterministicExplanations({
    decision,
    evidenceContext: input.evidenceContext,
    metrics,
  });
  const projectionSemantics = buildProjectionSemantics(
    input.policyDesignCaseProjection,
  );
  const packetWithoutHash = {
    argumentMap: buildArgumentMap({
      decision,
      evidenceContext: input.evidenceContext,
      governanceIssues,
      metrics,
    }),
    bureaucraticForms: PUBLICATION_FORMS,
    comprehension: buildComprehensionDescriptors({
      decision,
      explanationCount: deterministicExplanations.length,
    }),
    confidenceLadder: buildConfidenceLadder({
      decision,
    }),
    coverageCaveat: buildCoverageCaveat(input.evidenceContext),
    decision,
    deterministicExplanations,
    glossary: GLOSSARY_TERMS,
    modelCard: buildModelCard({
      decision,
      evidenceContext: input.evidenceContext,
      metrics,
    }),
    projectionSemantics,
    schema: PUBLIC_PACKET_SCHEMA,
    thresholdContract: buildThresholdMicrocontract({
      decisionView: input.decisionView,
      runId: input.runId,
    }),
    trustFraming: buildTrustFraming({
      projectionSemantics,
    }),
  } satisfies Omit<PublicDecisionPacket, "packetHash">;

  return {
    ...packetWithoutHash,
    packetHash: unsignedPacketHash(packetWithoutHash),
  };
}

function encodeBase64Url(value: string) {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  const encoded =
    typeof globalThis.btoa === "function"
      ? globalThis.btoa(binary)
      : (globalThis as unknown as { Buffer: typeof Buffer }).Buffer.from(
          value,
          "utf8",
        ).toString("base64");
  return encoded.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/u, "");
}

function decodeBase64Url(value: string) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = `${normalized}${"=".repeat((4 - (normalized.length % 4)) % 4)}`;
  const decoded =
    typeof globalThis.atob === "function"
      ? new TextDecoder().decode(
          Uint8Array.from(globalThis.atob(padded), (char) =>
            char.charCodeAt(0),
          ),
        )
      : (globalThis as unknown as { Buffer: typeof Buffer }).Buffer.from(
          padded,
          "base64",
        ).toString("utf8");
  return decoded;
}

function signatureForPayload(payload: PublicDecisionPacket) {
  return `sig:${stableHash(`${SIGNATURE_SALT}:${stableJson(payload)}`)}`;
}

function isSignedPublicDecisionPacket(
  value: unknown,
): value is SignedPublicDecisionPacket {
  if (!value || typeof value !== "object") {
    return false;
  }
  const record = value as Partial<SignedPublicDecisionPacket>;
  return (
    record.schema === PUBLIC_PACKET_SCHEMA &&
    typeof record.packetHash === "string" &&
    typeof record.publicUrlPath === "string" &&
    typeof record.signature === "string" &&
    typeof record.signedId === "string" &&
    Boolean(record.argumentMap) &&
    Boolean(record.modelCard) &&
    Boolean(record.coverageCaveat) &&
    Boolean(record.projectionSemantics) &&
    Boolean(record.thresholdContract) &&
    Boolean(record.trustFraming)
  );
}

function reviveCandidateDisplayState(
  value: InteractionState,
): InteractionState {
  if (
    !value ||
    typeof value !== "object" ||
    typeof value.label !== "string" ||
    value.purpose !== "interaction_only" ||
    value.authorityPurpose !== "candidate_display"
  ) {
    throw new TypeError("signed packet candidate display state is invalid");
  }
  return createInteractionState(value.label, "candidate_display");
}

function revivePublicationDisplayStates(
  packet: PublicDecisionPacket,
): PublicDecisionPacket {
  return {
    ...packet,
    coverageCaveat: {
      ...packet.coverageCaveat,
      caveatState: reviveCandidateDisplayState(
        packet.coverageCaveat.caveatState,
      ),
      regions: packet.coverageCaveat.regions.map((region) => ({
        ...region,
        displayState: reviveCandidateDisplayState(region.displayState),
      })),
    },
    projectionSemantics: {
      ...packet.projectionSemantics,
      displayStates: packet.projectionSemantics.displayStates.map(
        reviveCandidateDisplayState,
      ),
      primaryDisplayState: reviveCandidateDisplayState(
        packet.projectionSemantics.primaryDisplayState,
      ),
    },
  };
}

export function signPublicDecisionPacket(
  packet: PublicDecisionPacket,
): SignedPublicDecisionPacket {
  const signature = signatureForPayload(packet);
  const payload = encodeBase64Url(stableJson({ packet, signature }));
  const signedId = `${payload}.${signature.replace("sig:", "")}`;
  return {
    ...packet,
    publicUrlPath: `/public/decisions/${signedId}`,
    signature,
    signedId,
  };
}

export function verifySignedPublicDecisionPacket(
  signedId: string,
): SignedPacketVerification {
  const [payload, signatureSuffix] = signedId.split(".");
  if (!payload || !signatureSuffix) {
    return { packet: null, reason: "bad_format", valid: false };
  }
  try {
    const parsed = JSON.parse(decodeBase64Url(payload)) as {
      packet?: unknown;
      signature?: unknown;
    };
    const packet = parsed.packet;
    if (
      !packet ||
      typeof parsed.signature !== "string" ||
      !isPublicDecisionPacket(packet)
    ) {
      return { packet: null, reason: "bad_payload", valid: false };
    }
    const expectedSignature = signatureForPayload(packet);
    if (
      parsed.signature !== expectedSignature ||
      signatureSuffix !== expectedSignature.replace("sig:", "")
    ) {
      return { packet: null, reason: "bad_signature", valid: false };
    }
    const revivedPacket = revivePublicationDisplayStates(packet);
    const signedPacket = {
      ...revivedPacket,
      publicUrlPath: `/public/decisions/${signedId}`,
      signature: expectedSignature,
      signedId,
    };
    if (!isSignedPublicDecisionPacket(signedPacket)) {
      return { packet: null, reason: "bad_payload", valid: false };
    }
    return { packet: signedPacket, reason: null, valid: true };
  } catch {
    return { packet: null, reason: "bad_payload", valid: false };
  }
}

function isPublicDecisionPacket(value: unknown): value is PublicDecisionPacket {
  if (!value || typeof value !== "object") {
    return false;
  }
  const record = value as Partial<PublicDecisionPacket>;
  return (
    record.schema === PUBLIC_PACKET_SCHEMA &&
    typeof record.packetHash === "string" &&
    Array.isArray(record.deterministicExplanations) &&
    Array.isArray(record.glossary) &&
    Boolean(record.argumentMap) &&
    Boolean(record.modelCard) &&
    Boolean(record.coverageCaveat) &&
    Boolean(record.projectionSemantics) &&
    Boolean(record.thresholdContract) &&
    Boolean(record.trustFraming)
  );
}

export function buildSignedPublicDecisionPacket(
  input: PublicDecisionPacketInput,
): SignedPublicDecisionPacket {
  return signPublicDecisionPacket(buildPublicDecisionPacket(input));
}

export function packetContainsPrivateContext(packet: PublicDecisionPacket) {
  const serialized = JSON.stringify(packet).toLowerCase();
  return [
    "ssn",
    "private reviewer",
    "raw restricted",
    "confidential value",
    "secret",
  ].some((needle) => serialized.includes(needle));
}
