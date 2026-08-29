import { downloadAcquisitionRoutePacket } from "./acquisitionRouteExport";

describe("acquisition route MACHINE export", () => {
  it("downloads a defensive copy of the exact captured response bytes", async () => {
    const wire = new TextEncoder().encode(' {"route":"exact"}\n');
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    let capturedBlob: Blob | null = null;
    vi.spyOn(URL, "createObjectURL").mockImplementation((blob) => {
      capturedBlob = blob as Blob;
      return "blob:acquisition-route";
    });
    const revoke = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined);

    downloadAcquisitionRoutePacket("run-1", wire);
    wire.fill(0);

    expect(click).toHaveBeenCalledTimes(1);
    expect(revoke).toHaveBeenCalledWith("blob:acquisition-route");
    expect(capturedBlob).not.toBeNull();
    const bytes = await new Promise<ArrayBuffer>((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () =>
        reject(reader.error ?? new Error("blob read failed"));
      reader.onload = () => resolve(reader.result as ArrayBuffer);
      reader.readAsArrayBuffer(capturedBlob!);
    });
    expect(Array.from(new Uint8Array(bytes))).toEqual(
      Array.from(new TextEncoder().encode(' {"route":"exact"}\n')),
    );
  });
});
