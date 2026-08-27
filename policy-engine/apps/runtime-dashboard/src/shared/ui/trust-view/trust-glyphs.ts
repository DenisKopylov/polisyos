import type { VerificationMetadata as RuntimeVerificationMetadata } from "@polisyos/runtime-api-client";

export type VerificationMetadata = RuntimeVerificationMetadata;

const trustPresentationBrand: unique symbol = Symbol(
  "owner-issued-trust-presentation",
);

export type TrustPresentation = Readonly<{
  readonly [trustPresentationBrand]: true;
}>;

export type TrustPresentationData = Readonly<{
  dispute: "none" | "disputed" | "under_review" | "resolved" | "unrecognized";
  status: "verified" | "pending" | "disputed" | "stale" | "unknown" | "unrecognized";
}>;

type MetadataFields = Readonly<{
  disputeStatus: unknown;
  freshness: unknown;
  hash: unknown;
  verificationMethod: unknown;
  verificationStatus: unknown;
  verifiedBy: unknown;
}>;

const issuedTrustPresentations = new WeakSet<object>();
const issuedTrustPresentationData = new WeakMap<object, TrustPresentationData>();

const UNKNOWN_PRESENTATION: TrustPresentationData = Object.freeze({
  dispute: "unrecognized",
  status: "unknown",
});

const UNRECOGNIZED_PRESENTATION: TrustPresentationData = Object.freeze({
  dispute: "unrecognized",
  status: "unrecognized",
});

/** Issue the only presentation that Trust View clothing may render. */
export function issueTrustPresentation(metadata: unknown): TrustPresentation {
  const data = deriveTrustPresentation(metadata);
  const issued = Object.freeze({
    [trustPresentationBrand]: true as const,
  }) as TrustPresentation;
  issuedTrustPresentations.add(issued);
  issuedTrustPresentationData.set(issued, data);
  return issued;
}

/** Return whether a value was issued by this module's runtime authority boundary. */
export function isIssuedTrustPresentation(
  value: unknown,
): value is TrustPresentation {
  return (
    typeof value === "object" &&
    value !== null &&
    Object.isFrozen(value) &&
    issuedTrustPresentations.has(value)
  );
}

/** Return safe display data, never trusting a structural presentation lookalike. */
export function presentTrustPresentation(value: unknown): TrustPresentationData {
  if (!isIssuedTrustPresentation(value)) {
    return UNRECOGNIZED_PRESENTATION;
  }
  return issuedTrustPresentationData.get(value) ?? UNRECOGNIZED_PRESENTATION;
}

function deriveTrustPresentation(metadata: unknown): TrustPresentationData {
  const fields = readMetadataFields(metadata);
  if (!fields) {
    return UNKNOWN_PRESENTATION;
  }

  if (
    !isVerificationStatus(fields.verificationStatus) ||
    !isDisputeStatus(fields.disputeStatus) ||
    !isFreshness(fields.freshness)
  ) {
    if (
      typeof fields.verificationStatus === "string" &&
      typeof fields.disputeStatus === "string" &&
      typeof fields.freshness === "string"
    ) {
      return UNRECOGNIZED_PRESENTATION;
    }
    return UNKNOWN_PRESENTATION;
  }

  const dispute =
    fields.verificationStatus === "disputed"
      ? "disputed"
      : fields.disputeStatus;
  if (dispute === "disputed" || dispute === "under_review") {
    return Object.freeze({ dispute, status: "disputed" });
  }
  if (fields.freshness === "stale") {
    return Object.freeze({ dispute, status: "stale" });
  }
  if (
    fields.freshness === "unknown" ||
    fields.verificationStatus === "untraced"
  ) {
    return Object.freeze({ dispute, status: "unknown" });
  }
  if (fields.verificationStatus === "pending") {
    return Object.freeze({ dispute, status: "pending" });
  }
  if (
    hasNonBlankString(fields.hash) &&
    hasNonBlankString(fields.verificationMethod) &&
    hasNonBlankString(fields.verifiedBy)
  ) {
    return Object.freeze({ dispute, status: "verified" });
  }
  return Object.freeze({ dispute, status: "unknown" });
}

function readMetadataFields(metadata: unknown): MetadataFields | null {
  if (typeof metadata !== "object" || metadata === null) {
    return null;
  }
  try {
    return {
      disputeStatus: Reflect.get(metadata, "dispute_status"),
      freshness: Reflect.get(metadata, "freshness"),
      hash: Reflect.get(metadata, "hash"),
      verificationMethod: Reflect.get(metadata, "verification_method"),
      verificationStatus: Reflect.get(metadata, "verification_status"),
      verifiedBy: Reflect.get(metadata, "verified_by"),
    };
  } catch {
    return null;
  }
}

function isVerificationStatus(
  value: unknown,
): value is NonNullable<VerificationMetadata["verification_status"]> {
  return (
    value === "verified" ||
    value === "pending" ||
    value === "disputed" ||
    value === "untraced"
  );
}

function isDisputeStatus(
  value: unknown,
): value is NonNullable<VerificationMetadata["dispute_status"]> {
  return (
    value === "none" ||
    value === "disputed" ||
    value === "under_review" ||
    value === "resolved"
  );
}

function isFreshness(
  value: unknown,
): value is NonNullable<VerificationMetadata["freshness"]> {
  return value === "current" || value === "stale" || value === "unknown";
}

function hasNonBlankString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

export function truncateHash(hash: string | null | undefined, size = 8) {
  if (!hash) {
    return "";
  }
  const normalized = hash.replace(/^sha256:/, "");
  if (normalized.length <= size * 2) {
    return hash;
  }
  return `sha256:${normalized.slice(0, size)}…${normalized.slice(-size)}`;
}
