import { downloadRunPaperPacket } from "./runPaperExport";

describe("run paper MACHINE export", () => {
  it("downloads a defensive copy of the exact captured response bytes", async () => {
    const wire = new TextEncoder().encode(' {"wire":"exact"}\n');
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    let capturedBlob: Blob | null = null;
    vi.spyOn(URL, "createObjectURL").mockImplementation((blob) => {
      capturedBlob = blob as Blob;
      return "blob:run-paper";
    });
    const revoke = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined);

    downloadRunPaperPacket("run-1", wire);
    wire.fill(0);

    expect(click).toHaveBeenCalledTimes(1);
    expect(revoke).toHaveBeenCalledWith("blob:run-paper");
    expect(capturedBlob).not.toBeNull();
    const bytes = await new Promise<ArrayBuffer>((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () =>
        reject(reader.error ?? new Error("Failed to read run paper Blob"));
      reader.onload = () => resolve(reader.result as ArrayBuffer);
      reader.readAsArrayBuffer(capturedBlob!);
    });
    expect(Array.from(new Uint8Array(bytes))).toEqual(
      Array.from(new TextEncoder().encode(' {"wire":"exact"}\n')),
    );
  });
});
