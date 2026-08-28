export function downloadAcquisitionRoutePacket(
  runId: string,
  rawPacketBytes: Uint8Array,
) {
  const packetBuffer = new Uint8Array(rawPacketBytes).buffer;
  const blob = new Blob([packetBuffer], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.download = `policyos-run-${runId}-acquisition-route.json`;
  link.href = url;
  link.click();
  URL.revokeObjectURL(url);
}

/** Decode the independently rendered raw blocks for MACHINE/DOM parity tests. */
export function decodeAcquisitionTimelineMachineFacts(root: ParentNode) {
  return Array.from(
    root.querySelectorAll<HTMLElement>("[data-acquisition-machine-fact]"),
    (element) => ({
      phase: element.dataset.acquisitionMachineFact ?? "",
      value: JSON.parse(element.textContent ?? "null") as unknown,
    }),
  );
}
