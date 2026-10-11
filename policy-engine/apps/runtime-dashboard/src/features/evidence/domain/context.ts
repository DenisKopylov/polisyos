import {
  dedupeEvidenceArtifactRefs,
  evidenceArtifactRefKey,
  type EvidenceFocus,
} from "@/shared/lib/domain/evidence";

export { dedupeEvidenceArtifactRefs, evidenceArtifactRefKey };

export const EVIDENCE_FOCUSES: EvidenceFocus[] = [
  "overview",
  "need",
  "plan",
  "promotion",
  "artifact",
];

export function parseEvidenceFocus(value: string | null): EvidenceFocus | null {
  if (!value) {
    return null;
  }
  return EVIDENCE_FOCUSES.includes(value as EvidenceFocus)
    ? (value as EvidenceFocus)
    : null;
}
