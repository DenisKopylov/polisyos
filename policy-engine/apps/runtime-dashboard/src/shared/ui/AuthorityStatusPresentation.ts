import type { BadgeTone } from "@polisyos/atlas-ui";

const authorityStatusPresentationBrand = Symbol(
  "polisyos.authority-status-presentation",
);
const authorityStatusIssuances = new WeakSet();

type AuthorityPresentationRecognition =
  | "informational"
  | "recognized"
  | "unrecognized";

export type AuthorityStatusPresentation = Readonly<{
  [authorityStatusPresentationBrand]: true;
  ownerLabel: string;
  recognition: AuthorityPresentationRecognition;
  source:
    | "approval_availability"
    | "governance_count"
    | "human_decision_evidence"
    | "human_decision_gate"
    | "human_decision_review_coverage"
    | "informational_owner_value"
    | "legal_review"
    | "opaque_owner_status"
    | "override_requirement"
    | "review_disagreement"
    | "review_required_aggregate";
  tone: BadgeTone;
}>;

type LegalReviewVocabularyMember =
  | "approved"
  | "pending_external_review"
  | "rejected";

const legalReviewPresentationTones = {
  approved: "ok",
  pending_external_review: "warn",
  rejected: "fail",
} as const satisfies Record<LegalReviewVocabularyMember, BadgeTone>;

function issuePresentation(
  value: Omit<
    AuthorityStatusPresentation,
    typeof authorityStatusPresentationBrand
  >,
): AuthorityStatusPresentation {
  const presentation: AuthorityStatusPresentation = {
    [authorityStatusPresentationBrand]: true,
    ...value,
  };
  authorityStatusIssuances.add(presentation);
  return Object.freeze(presentation);
}

function ownerLabel(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function issueUnrecognized(
  value: unknown,
  source: AuthorityStatusPresentation["source"],
): AuthorityStatusPresentation {
  return issuePresentation({
    ownerLabel: ownerLabel(value) ?? "unrecognized",
    recognition: "unrecognized",
    source,
    tone: "neutral",
  });
}

/** Preserves an open owner status without treating its spelling as authority. */
export function issueOpaqueAuthorityStatusPresentation(
  value: unknown,
): AuthorityStatusPresentation {
  return issueUnrecognized(value, "opaque_owner_status");
}

/** Issues clothing for the closed legal-review union at its typed boundary. */
export function issueLegalReviewPresentation(
  value: LegalReviewVocabularyMember,
): AuthorityStatusPresentation {
  const runtimeValue: unknown = value;
  if (
    typeof runtimeValue !== "string" ||
    !Object.hasOwn(legalReviewPresentationTones, runtimeValue)
  ) {
    return issueUnrecognized(runtimeValue, "legal_review");
  }
  const legalReview = runtimeValue as LegalReviewVocabularyMember;
  return issuePresentation({
    ownerLabel: legalReview,
    recognition: "recognized",
    source: "legal_review",
    tone: legalReviewPresentationTones[legalReview],
  });
}

type HumanDecisionGateVocabularyMember =
  | "artifact_missing"
  | "available"
  | "blocked"
  | "invalid_source"
  | "producer_missing"
  | "revalidation_required";

const humanDecisionGatePresentationTones = {
  artifact_missing: "fail",
  available: "ok",
  blocked: "fail",
  invalid_source: "fail",
  producer_missing: "fail",
  revalidation_required: "warn",
} as const satisfies Record<HumanDecisionGateVocabularyMember, BadgeTone>;

/** Issues the complete generated human-decision gate vocabulary. */
export function issueHumanDecisionGatePresentation(
  value: HumanDecisionGateVocabularyMember,
): AuthorityStatusPresentation {
  const runtimeValue: unknown = value;
  if (
    typeof runtimeValue !== "string" ||
    !Object.hasOwn(humanDecisionGatePresentationTones, runtimeValue)
  ) {
    return issueUnrecognized(runtimeValue, "human_decision_gate");
  }
  const gateValue = runtimeValue as HumanDecisionGateVocabularyMember;
  return issuePresentation({
    ownerLabel: gateValue,
    recognition: "recognized",
    source: "human_decision_gate",
    tone: humanDecisionGatePresentationTones[gateValue],
  });
}

/** Issues evidence exposure clothing from the checked exposure fact. */
export function issueHumanDecisionEvidencePresentation(
  opened: unknown,
): AuthorityStatusPresentation {
  if (typeof opened !== "boolean") {
    return issueUnrecognized(opened, "human_decision_evidence");
  }
  return issuePresentation({
    ownerLabel: opened ? "opened" : "unavailable",
    recognition: "recognized",
    source: "human_decision_evidence",
    tone: opened ? "ok" : "fail",
  });
}

type HumanDecisionCoverageVocabularyMember = "complete" | "incomplete";

const humanDecisionCoveragePresentationTones = {
  complete: "ok",
  incomplete: "warn",
} as const satisfies Record<HumanDecisionCoverageVocabularyMember, BadgeTone>;

/** Issues the complete generated review-effectiveness coverage vocabulary. */
export function issueHumanDecisionReviewCoveragePresentation(
  value: HumanDecisionCoverageVocabularyMember,
): AuthorityStatusPresentation {
  const runtimeValue: unknown = value;
  if (
    typeof runtimeValue !== "string" ||
    !Object.hasOwn(humanDecisionCoveragePresentationTones, runtimeValue)
  ) {
    return issueUnrecognized(runtimeValue, "human_decision_review_coverage");
  }
  const coverage = runtimeValue as HumanDecisionCoverageVocabularyMember;
  return issuePresentation({
    ownerLabel: coverage,
    recognition: "recognized",
    source: "human_decision_review_coverage",
    tone: humanDecisionCoveragePresentationTones[coverage],
  });
}

/**
 * Issues a closed availability result from boolean owner facts.
 * A denial wins a mixed set; malformed or incomplete facts cannot look positive.
 */
export function issueApprovalAvailabilityPresentation(
  ownerFacts: readonly unknown[],
  value: unknown,
): AuthorityStatusPresentation {
  const label = ownerLabel(value) ?? "unrecognized";
  if (ownerFacts.some((fact) => fact === false)) {
    return issuePresentation({
      ownerLabel: label,
      recognition: "recognized",
      source: "approval_availability",
      tone: "fail",
    });
  }
  if (
    ownerFacts.length === 0 ||
    ownerFacts.some((fact) => typeof fact !== "boolean")
  ) {
    return issueUnrecognized(value, "approval_availability");
  }
  return issuePresentation({
    ownerLabel: label,
    recognition: "recognized",
    source: "approval_availability",
    tone: "ok",
  });
}

/** Issues the closed override-required boolean without parsing a status label. */
export function issueOverrideRequirementPresentation(
  required: unknown,
): AuthorityStatusPresentation {
  if (typeof required !== "boolean") {
    return issueUnrecognized(required, "override_requirement");
  }
  return issuePresentation({
    ownerLabel: required ? "override_required" : "not_required",
    recognition: "recognized",
    source: "override_requirement",
    tone: required ? "warn" : "ok",
  });
}

/** Issues review-disagreement clothing from a checked, non-negative count. */
export function issueReviewDisagreementPresentation(
  count: unknown,
): AuthorityStatusPresentation {
  if (!Number.isSafeInteger(count) || Number(count) < 0) {
    return issueUnrecognized(count, "review_disagreement");
  }
  return issuePresentation({
    ownerLabel: `unresolved:${String(count)}`,
    recognition: "recognized",
    source: "review_disagreement",
    tone: Number(count) > 0 ? "warn" : "ok",
  });
}

/** Issues an aggregate only when the complete producer fact set is present. */
export function issueReviewRequiredPresentation(
  ownerFacts: readonly unknown[] | undefined,
): AuthorityStatusPresentation {
  if (
    !ownerFacts ||
    ownerFacts.length === 0 ||
    ownerFacts.some((fact) => typeof fact !== "boolean")
  ) {
    return issueUnrecognized(undefined, "review_required_aggregate");
  }
  const reviewRequired = ownerFacts.some((fact) => fact === true);
  return issuePresentation({
    ownerLabel: reviewRequired ? "review_required" : "not_required",
    recognition: "recognized",
    source: "review_required_aggregate",
    tone: reviewRequired ? "warn" : "ok",
  });
}

/** Keeps governance counts informational even when their label sounds decisive. */
export function issueAuthorityCountPresentation(
  kind: "failed" | "passed" | "warnings",
  count: number,
): AuthorityStatusPresentation {
  if (!Number.isSafeInteger(count) || count < 0) {
    throw new TypeError("authority count must be a non-negative safe integer");
  }
  return issuePresentation({
    ownerLabel: `${kind}:${count}`,
    recognition: "informational",
    source: "governance_count",
    tone: "outline",
  });
}

/** Marks a producer value as informational without deriving authority from it. */
export function issueAuthorityInformationPresentation(
  value: unknown,
): AuthorityStatusPresentation {
  return issuePresentation({
    ownerLabel: ownerLabel(value) ?? String(value ?? "unrecognized"),
    recognition: "informational",
    source: "informational_owner_value",
    tone: "neutral",
  });
}

/** Returns Badge props only for an issuance produced by this module. */
export function authorityStatusBadgeProps(
  presentation: AuthorityStatusPresentation,
): Readonly<{
  "data-authority-recognition": AuthorityPresentationRecognition;
  "data-authority-source": AuthorityStatusPresentation["source"];
  "data-owner-status": string;
  "data-presentation-tone": BadgeTone;
  kind: BadgeTone;
}> {
  if (
    typeof presentation !== "object" ||
    presentation === null ||
    !presentation[authorityStatusPresentationBrand] ||
    !authorityStatusIssuances.has(presentation)
  ) {
    throw new TypeError(
      "authority status presentation must be privately issued",
    );
  }
  return Object.freeze({
    "data-authority-recognition": presentation.recognition,
    "data-authority-source": presentation.source,
    "data-owner-status": presentation.ownerLabel,
    "data-presentation-tone": presentation.tone,
    kind: presentation.tone,
  });
}
