/** Download the exact response bytes that supplied the run paper document. */
export function downloadRunPaperPacket(
  runId: string,
  rawPacketBytes: Uint8Array,
) {
  const packetBuffer = new Uint8Array(rawPacketBytes).buffer;
  const blob = new Blob([packetBuffer], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.download = `policyos-run-${runId}-paper.json`;
  link.href = url;
  link.click();
  URL.revokeObjectURL(url);
}
