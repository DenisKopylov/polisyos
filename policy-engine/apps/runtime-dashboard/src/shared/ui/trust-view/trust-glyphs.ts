import type {
  LineageFreshness,
  TemporalRef,
  VerificationStatus,
} from "@/shared/ui/quantity";

export type DisputeStatus = "none" | "disputed" | "under_review" | "resolved";

export type VerificationMetadata = {
  hash?: string | null;
  verification_status: VerificationStatus;
  verified_by?: string | null;
  verified_at?: string | null;
  verification_method?: string | null;
  freshness: LineageFreshness;
  dispute_status: DisputeStatus;
  temporal_scope?: TemporalRef | null;
};

export type TrustGlyphTone =
  | "verified"
  | "pending"
  | "disputed"
  | "stale"
  | "untraced";

export function trustToneFromMetadata(
  metadata: VerificationMetadata | null | undefined,
): TrustGlyphTone {
  if (!metadata) {
    return "untraced";
  }
  if (
    metadata.dispute_status === "disputed" ||
    metadata.verification_status === "disputed"
  ) {
    return "disputed";
  }
  if (metadata.freshness === "stale") {
    return "stale";
  }
  return metadata.verification_status;
}

export function trustGlyph(tone: TrustGlyphTone): string {
  switch (tone) {
    case "verified":
      return "✓";
    case "pending":
      return "◌";
    case "disputed":
      return "!";
    case "stale":
      return "~";
    case "untraced":
      return "?";
  }
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

export function trustMetadataFromLineage({
  fallbackTemporalScope,
  freshness,
  hash,
  status,
  trustMetadata,
}: {
  fallbackTemporalScope?: TemporalRef | null;
  freshness: LineageFreshness;
  hash?: string | null;
  status: VerificationStatus;
  trustMetadata?: VerificationMetadata | null;
}): VerificationMetadata {
  return {
    dispute_status: status === "disputed" ? "disputed" : "none",
    freshness,
    hash: trustMetadata?.hash ?? hash ?? null,
    temporal_scope:
      trustMetadata?.temporal_scope ?? fallbackTemporalScope ?? null,
    verification_method:
      trustMetadata?.verification_method ??
      (status === "untraced" ? "lineage_id_resolution" : "lineage_hash_match"),
    verification_status: trustMetadata?.verification_status ?? status,
    verified_at: trustMetadata?.verified_at ?? null,
    verified_by: trustMetadata?.verified_by ?? null,
  };
}
