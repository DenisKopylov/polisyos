import { afterEach, describe, expect, it, vi } from "vitest";

import {
  downloadEpochStalenessMachine,
  epochStalenessMachineBytes,
} from "./epochStalenessTwin";

async function readBlobBytes(blob: Blob): Promise<Uint8Array> {
  return new Promise<Uint8Array>((resolveBytes, reject) => {
    const reader = new FileReader();
    reader.onerror = () =>
      reject(reader.error ?? new Error("Blob read failed"));
    reader.onload = () =>
      resolveBytes(new Uint8Array(reader.result as ArrayBuffer));
    reader.readAsArrayBuffer(blob);
  });
}

describe("epoch staleness MACHINE twin", () => {
  afterEach(() => vi.restoreAllMocks());

  it("downloads a defensive copy of captured bytes, never a reserialization", async () => {
    const wire = new TextEncoder().encode(
      '{\n  "projection": {"status":"not_established"},\n  "meta": {"request_id":"r"}\n}\n',
    );
    const expected = wire.slice();
    const normalized = new TextEncoder().encode(
      JSON.stringify(JSON.parse(new TextDecoder().decode(wire))),
    );
    let downloaded: Blob | null = null;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => undefined,
    );
    vi.spyOn(URL, "createObjectURL").mockImplementation((value) => {
      downloaded = value as Blob;
      return "blob:epoch-staleness";
    });
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);

    const exposed = epochStalenessMachineBytes(wire);
    downloadEpochStalenessMachine(wire, "R_core_api_001");
    wire.fill(0);

    expect(Array.from(exposed)).toEqual(Array.from(expected));
    expect(Array.from(exposed)).not.toEqual(Array.from(normalized));
    expect(downloaded).not.toBeNull();
    expect(
      Array.from(await readBlobBytes(downloaded as unknown as Blob)),
    ).toEqual(Array.from(expected));
  });
});
