import { createElement } from "react";
import { Badge } from "@polisyos/atlas-ui";

const authoritySemanticCopyBrand: unique symbol = Symbol(
  "polisyos.authority-semantic-copy",
);
const authoritySemanticCopyIssuances = new WeakSet<object>();
const semanticReviewReceiptBrand: unique symbol = Symbol(
  "polisyos.semantic-review-receipt",
);
const semanticReviewReceiptIssuances = new WeakSet<object>();

type AuthoritySemanticReviewReceipt = Readonly<{
  [semanticReviewReceiptBrand]: true;
  contentHash: string;
  reviewerIdentity: string;
  reviewerScope: string;
  reviewerVersion: string;
  semanticId: string;
}>;

export type AuthoritySemanticCopy = Readonly<{
  [authoritySemanticCopyBrand]: true;
  authorityClass: "verification_missing";
  semanticId: string;
  strength: "limited";
  text: string;
}>;

type MayNotUseForInput = {
  canonicalSemanticId?: "phase34.harm.risk.limited";
  locale?: "en" | "uk";
  ownerToken: string;
  receipt?: AuthoritySemanticReviewReceipt;
  scope: "governed_projection.rights_bar";
};

const CLOSED_LIMITED_COPY = {
  contentHash:
    "sha256:28fb42a4a99f4293d47318a3cb821e26c3f83482583bbba7f12459d32db23a07",
  locale: "en",
  reviewStatus: "verification_missing",
  scope: "governed_projection.rights_bar",
  semanticId: "phase34.harm.risk.limited",
  text: "Limited harm-risk authority",
} as const;

function issuePresentation(
  semanticId: string,
  text: string,
): AuthoritySemanticCopy {
  const issued: AuthoritySemanticCopy = {
    [authoritySemanticCopyBrand]: true,
    authorityClass: "verification_missing",
    semanticId,
    strength: "limited",
    text,
  };
  authoritySemanticCopyIssuances.add(issued);
  return Object.freeze(issued);
}

function assertReceipt(
  receipt: AuthoritySemanticReviewReceipt,
  expected: typeof CLOSED_LIMITED_COPY,
): void {
  if (
    !semanticReviewReceiptIssuances.has(receipt) ||
    receipt.semanticId !== expected.semanticId ||
    receipt.contentHash !== expected.contentHash ||
    receipt.reviewerScope !== "authority-copy.en.governed_projection.rights_bar" ||
    expected.reviewStatus !== "accepted"
  ) {
    throw new TypeError("semantic review receipt is not admitted for this copy");
  }
}

/** Creates a nominal external-review receipt; admission remains registry-owned. */
export function createAuthoritySemanticReviewReceipt(
  receipt: Omit<AuthoritySemanticReviewReceipt, typeof semanticReviewReceiptBrand>,
): AuthoritySemanticReviewReceipt {
  const issued: AuthoritySemanticReviewReceipt = {
    [semanticReviewReceiptBrand]: true,
    ...receipt,
  };
  semanticReviewReceiptIssuances.add(issued);
  return Object.freeze(issued);
}

/**
 * Presents a generated `may_not_use_for` owner token without inventing a vocabulary.
 * Closed semantic copy is admitted only with a content-bound accepted external receipt.
 */
export function presentMayNotUseFor(
  input: MayNotUseForInput,
): AuthoritySemanticCopy {
  if (
    input.canonicalSemanticId === CLOSED_LIMITED_COPY.semanticId &&
    input.locale === CLOSED_LIMITED_COPY.locale &&
    input.ownerToken === "harm_risk" &&
    input.scope === CLOSED_LIMITED_COPY.scope &&
    input.receipt !== undefined
  ) {
    assertReceipt(input.receipt, CLOSED_LIMITED_COPY);
    return issuePresentation(CLOSED_LIMITED_COPY.semanticId, CLOSED_LIMITED_COPY.text);
  }

  return issuePresentation(
    `generated:DepthNCycleBoardProjection.may_not_use_for:${input.ownerToken}`,
    input.ownerToken,
  );
}

function assertAuthoritySemanticCopy(
  presentation: AuthoritySemanticCopy,
): void {
  if (
    presentation === null ||
    typeof presentation !== "object" ||
    presentation[authoritySemanticCopyBrand] !== true ||
    !authoritySemanticCopyIssuances.has(presentation)
  ) {
    throw new TypeError("authority semantic copy must be issuer-derived");
  }
}

/** Renders only an issuer-created authority semantic presentation. */
export function AuthoritySemanticCopyBadge({
  presentation,
}: {
  presentation: AuthoritySemanticCopy;
}) {
  assertAuthoritySemanticCopy(presentation);
  return createElement(
    Badge,
    {
      "data-authority-class": presentation.authorityClass,
      "data-semantic-id": presentation.semanticId,
      "data-semantic-strength": presentation.strength,
      kind: "outline",
    },
    presentation.text,
  );
}
