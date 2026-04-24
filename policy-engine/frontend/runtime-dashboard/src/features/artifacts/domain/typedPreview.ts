type ArtifactPreviewCarrier = {
  kind?: string | null;
  preview?: unknown;
  decision_packet_preview?: Record<string, unknown> | null;
};

function isDecisionPacketKind(kind: string | null | undefined) {
  return kind === "scientist.decision_packet" || kind === "decision_packet";
}

export function resolveArtifactPreviewPayload(
  artifact: ArtifactPreviewCarrier | null | undefined,
): unknown {
  if (!artifact) {
    return null;
  }

  if (isDecisionPacketKind(artifact.kind) && artifact.decision_packet_preview) {
    return artifact.decision_packet_preview;
  }

  return artifact.preview ?? null;
}
