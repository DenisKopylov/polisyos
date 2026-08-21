/** Download the exact server response bytes that supplied the Cycle Board. */
export function downloadCycleBoardPacket(rawPacketBytes: Uint8Array) {
  const packetBuffer = new Uint8Array(rawPacketBytes).buffer;
  const blob = new Blob([packetBuffer], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.download = "policyos-cycle-board.json";
  link.href = url;
  link.click();
  URL.revokeObjectURL(url);
}
