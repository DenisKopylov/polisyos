import type { VerificationMetadata as RuntimeVerificationMetadata } from "@polisyos/runtime-api-client";

export type VerificationMetadata = RuntimeVerificationMetadata;

type TrustPresentation = Readonly<{
  ownerContractPresent: boolean;
  tone: string;
}>;

export function hasVerificationOwnerContract(
  metadata: VerificationMetadata | null | undefined,
): metadata is VerificationMetadata {
  if (typeof metadata !== "object" || metadata === null) {
    return false;
  }
  return (
    typeof metadata.dispute_status === "string" &&
    typeof metadata.freshness === "string" &&
    typeof metadata.verification_status === "string"
  );
}

export function trustPresentationFromMetadata(
  metadata: VerificationMetadata | null | undefined,
): TrustPresentation {
  if (!hasVerificationOwnerContract(metadata)) {
    return { ownerContractPresent: false, tone: "unknown" };
  }
  if (
    (metadata.dispute_status !== "none" &&
      metadata.dispute_status !== "resolved") ||
    metadata.verification_status === "disputed"
  ) {
    return { ownerContractPresent: true, tone: "disputed" };
  }
  if (metadata.freshness === "stale") {
    return { ownerContractPresent: true, tone: "stale" };
  }
  return {
    ownerContractPresent: true,
    tone: metadata.verification_status,
  };
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
