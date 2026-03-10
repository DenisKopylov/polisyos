import type { EvidenceArtifactRef, EvidenceFocus } from "@/lib/domain/evidence";

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

export function dedupeEvidenceArtifactRefs(
  refs: Array<EvidenceArtifactRef | null | undefined>,
): EvidenceArtifactRef[] {
  const seen = new Set<string>();
  const result: EvidenceArtifactRef[] = [];
  for (const ref of refs) {
    if (!ref?.artifact_id || seen.has(ref.artifact_id)) {
      continue;
    }
    seen.add(ref.artifact_id);
    result.push(ref);
  }
  return result;
}
