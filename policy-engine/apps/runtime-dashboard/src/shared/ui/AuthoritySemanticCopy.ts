import type { AvailableGovernedProjectionPacket } from "@polisyos/runtime-api-client";

const authoritySemanticCopyBrand: unique symbol = Symbol("polisyos.authority-semantic-copy");
const authoritySemanticReviewReceiptBrand: unique symbol = Symbol(
  "polisyos.authority-semantic-review-receipt",
);
const issuedAuthoritySemanticCopies = new WeakSet();
const admittedAuthoritySemanticReviewReceipts = new WeakSet();

const CLOSED_LIMITED_SEMANTIC_ID = "phase34.harm.risk.limited" as const;
const RIGHTS_BAR_SCOPE = "governed_projection.rights_bar" as const;
const ENGLISH_BASELINE_LOCALE = "en" as const;
const CLOSED_COPY_CONTENT_HASH =
  "sha256:28fb42a4a99f4293d47318a3cb821e26c3f83482583bbba7f12459d32db23a07";
const CLOSED_COPY_REVIEWER_IDENTITY = "external-reviewer:policy-language";
const CLOSED_COPY_REVIEWER_VERSION = "v1";
const CLOSED_COPY_REVIEWER_SCOPE = "authority-copy.en.governed_projection.rights_bar";

type MayNotUseForOwnerToken =
  AvailableGovernedProjectionPacket["may_not_use_for"][number];

export type AuthoritySemanticReviewReceipt = Readonly<{
  [authoritySemanticReviewReceiptBrand]: true;
  contentHash: string;
  reviewerIdentity: string;
  reviewerScope: string;
  reviewerVersion: string;
  semanticId: typeof CLOSED_LIMITED_SEMANTIC_ID;
}>;

export type AuthoritySemanticCopy = Readonly<{
  [authoritySemanticCopyBrand]: true;
  authorityClass: "verification_missing";
  semanticId: string;
  strength: "limited";
  text: string;
}>;

type ClosedSemanticCopyInput = Readonly<{
  locale: "en" | "uk";
  receipt?: AuthoritySemanticReviewReceipt;
  semanticId: typeof CLOSED_LIMITED_SEMANTIC_ID;
  sourceToken: "harm_risk";
  scope: typeof RIGHTS_BAR_SCOPE;
}>;

type MayNotUseForInput = Readonly<{
  ownerToken: MayNotUseForOwnerToken;
  scope: typeof RIGHTS_BAR_SCOPE;
}>;

export type ReviewReceiptInput = Readonly<{
  contentHash: string;
  reviewerIdentity: string;
  reviewerScope: string;
  reviewerVersion: string;
  semanticId: typeof CLOSED_LIMITED_SEMANTIC_ID;
}>;

function issueAuthoritySemanticCopy(
  semanticId: string,
  text: string,
): AuthoritySemanticCopy {
  const issued: AuthoritySemanticCopy = Object.freeze({
    [authoritySemanticCopyBrand]: true as const,
    authorityClass: "verification_missing" as const,
    semanticId,
    strength: "limited" as const,
    text,
  });
  issuedAuthoritySemanticCopies.add(issued);
  return issued;
}

function assertReviewReceipt(
  receipt: unknown,
  input: ReviewReceiptInput,
): AuthoritySemanticReviewReceipt {
  const candidate = receipt as Readonly<Record<PropertyKey, unknown>>;
  if (
    receipt === null ||
    typeof receipt !== "object" ||
    !admittedAuthoritySemanticReviewReceipts.has(receipt) ||
    candidate[authoritySemanticReviewReceiptBrand] !== true ||
    candidate.semanticId !== input.semanticId ||
    candidate.contentHash !== input.contentHash ||
    candidate.reviewerIdentity !== input.reviewerIdentity ||
    candidate.reviewerVersion !== input.reviewerVersion ||
    candidate.reviewerScope !== input.reviewerScope
  ) {
    throw new TypeError("semantic review receipt is not admitted for this copy");
  }
  return receipt as AuthoritySemanticReviewReceipt;
}

function assertContentBoundReviewInput(input: ReviewReceiptInput): void {
  if (
    input.semanticId !== CLOSED_LIMITED_SEMANTIC_ID ||
    input.contentHash !== CLOSED_COPY_CONTENT_HASH ||
    input.reviewerIdentity !== CLOSED_COPY_REVIEWER_IDENTITY ||
    input.reviewerVersion !== CLOSED_COPY_REVIEWER_VERSION ||
    input.reviewerScope !== CLOSED_COPY_REVIEWER_SCOPE
  ) {
    throw new TypeError("semantic review receipt is not content-bound for this copy");
  }
}

/**
 * Admits a content-bound competent-review receipt when the registry supplies one.
 * C05b-R2 has zero accepted receipts, so every current candidate fails closed.
 */
export function admitAuthoritySemanticReviewReceipt(
  input: ReviewReceiptInput,
): AuthoritySemanticReviewReceipt {
  assertContentBoundReviewInput(input);
  throw new TypeError("semantic review receipt is not accepted by the registry");
}

/** Issues only the unreviewed English baseline for the closed limited semantic. */
export function presentSemanticCopy(input: ClosedSemanticCopyInput): AuthoritySemanticCopy {
  if (
    input.semanticId !== CLOSED_LIMITED_SEMANTIC_ID ||
    input.sourceToken !== "harm_risk"
  ) {
    throw new TypeError("semantic review receipt is required for localized authority copy");
  }
  if (input.scope !== RIGHTS_BAR_SCOPE) {
    throw new TypeError("authority semantic copy scope is not admitted");
  }
  if (input.locale !== ENGLISH_BASELINE_LOCALE) {
    assertReviewReceipt(input.receipt, {
      contentHash: CLOSED_COPY_CONTENT_HASH,
      reviewerIdentity: CLOSED_COPY_REVIEWER_IDENTITY,
      reviewerScope: CLOSED_COPY_REVIEWER_SCOPE,
      reviewerVersion: CLOSED_COPY_REVIEWER_VERSION,
      semanticId: CLOSED_LIMITED_SEMANTIC_ID,
    });
  }
  return issueAuthoritySemanticCopy(input.semanticId, "Limited harm-risk authority");
}

/**
 * Presents generated owner tokens as opaque rights-bar limits without proposing
 * a vocabulary or converting a prohibition into a recommendation.
 */
export function presentMayNotUseFor(input: MayNotUseForInput): AuthoritySemanticCopy {
  if (input.scope !== RIGHTS_BAR_SCOPE) {
    throw new TypeError("authority semantic copy scope is not admitted");
  }
  return issueAuthoritySemanticCopy(
    `generated:GovernedProjectionPacket.may_not_use_for:${input.ownerToken}`,
    input.ownerToken,
  );
}

/** Rejects structurally plausible values that were not issued by this module. */
export function assertIssuedAuthoritySemanticCopy(
  presentation: unknown,
): asserts presentation is AuthoritySemanticCopy {
  const candidate = presentation as Readonly<Record<PropertyKey, unknown>>;
  if (
    presentation === null ||
    typeof presentation !== "object" ||
    candidate[authoritySemanticCopyBrand] !== true ||
    !issuedAuthoritySemanticCopies.has(presentation)
  ) {
    throw new TypeError("authority semantic copy must be issuer-derived");
  }
}
