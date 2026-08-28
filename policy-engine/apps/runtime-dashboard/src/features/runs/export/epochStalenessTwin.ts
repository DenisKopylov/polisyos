/** Return a defensive copy of the exact admitted wire bytes for MACHINE consumers. */
export function epochStalenessMachineBytes(rawBytes: Uint8Array): Uint8Array {
  return rawBytes.slice();
}

/** Download captured wire bytes without parsing, normalizing, or reserializing them. */
export function downloadEpochStalenessMachine(
  rawBytes: Uint8Array,
  runId: string,
): void {
  const copied = epochStalenessMachineBytes(rawBytes);
  const ownedBuffer = new ArrayBuffer(copied.byteLength);
  new Uint8Array(ownedBuffer).set(copied);
  const blob = new Blob([ownedBuffer], { type: "application/json" });
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = `${runId}-epoch-staleness.json`;
  anchor.click();
  URL.revokeObjectURL(href);
}
