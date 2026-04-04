import {
  buildRowExportRecord,
  buildTableExportRecords,
  copyCell,
  copyRow,
  copyShareLink,
  exportCsv,
  exportJson,
} from "@/shared/ui/dataExport";

function readBlobText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () =>
      reject(reader.error ?? new Error("Failed to read blob text"));
    reader.onload = () => resolve(String(reader.result));
    reader.readAsText(blob);
  });
}

type DemoRow = {
  id: string;
  createdAt: Date;
  meta: { status: string };
  notes: string[];
  title: string;
};

const columns = [
  {
    key: "title",
    header: "Title",
    exportValue: (row: DemoRow) => row.title,
  },
  {
    key: "created",
    exportHeader: "Created",
    header: "Ignored",
    exportValue: (row: DemoRow) => row.createdAt,
  },
  {
    key: "meta",
    header: "Meta",
    exportValue: (row: DemoRow) => row.meta,
  },
  {
    key: "notes",
    header: "Notes",
    clipboardValue: (row: DemoRow) => row.notes,
  },
] as const;

describe("dataExport", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("builds row and table records with normalized export values", () => {
    const row: DemoRow = {
      id: "row-1",
      createdAt: new Date("2026-03-10T10:00:00Z"),
      meta: { status: "ok" },
      notes: ["alpha", "beta"],
      title: "Primary row",
    };

    expect(buildRowExportRecord(row, [...columns])).toEqual({
      Created: "2026-03-10T10:00:00.000Z",
      Meta: '{"status":"ok"}',
      Notes: "alpha, beta",
      Title: "Primary row",
    });
    expect(buildTableExportRecords([row], [...columns])).toEqual([
      {
        Created: "2026-03-10T10:00:00.000Z",
        Meta: '{"status":"ok"}',
        Notes: "alpha, beta",
        Title: "Primary row",
      },
    ]);
  });

  it("downloads csv and json exports with escaped content", async () => {
    const row: DemoRow = {
      id: "row-2",
      createdAt: new Date("2026-03-10T10:00:00Z"),
      meta: { status: "warn" },
      notes: ["line 1", "line,2"],
      title: 'Needs "review"\nnow',
    };
    const createObjectUrlMock = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:download");
    const revokeObjectUrlMock = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined);
    const clickMock = vi.fn();
    let lastDownload = "";
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      lastDownload = this.download;
      clickMock();
    });

    exportCsv("runs.csv", [row], [...columns]);
    expect(createObjectUrlMock).toHaveBeenCalledTimes(1);
    expect(lastDownload).toBe("runs.csv");
    expect(clickMock).toHaveBeenCalledTimes(1);
    const csvBlob = createObjectUrlMock.mock.calls[0]?.[0];
    expect(csvBlob).toBeInstanceOf(Blob);
    await expect(readBlobText(csvBlob as Blob)).resolves.toContain(
      '"Needs ""review""\nnow"',
    );
    expect(revokeObjectUrlMock).toHaveBeenCalledWith("blob:download");

    exportJson("runs.json", { rows: [row.id] });
    expect(createObjectUrlMock).toHaveBeenCalledTimes(2);
    expect(lastDownload).toBe("runs.json");
    const jsonBlob = createObjectUrlMock.mock.calls[1]?.[0];
    expect(jsonBlob).toBeInstanceOf(Blob);
    await expect(readBlobText(jsonBlob as Blob)).resolves.toContain(
      '"rows": [',
    );
  });

  it("copies cells, rows, and share links through the clipboard api", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    await copyCell(["alpha", "beta"]);
    await copyRow(
      {
        createdAt: new Date("2026-03-10T10:00:00Z"),
        id: "row-3",
        meta: { status: "ok" },
        notes: ["note"],
        title: "Copied row",
      },
      [...columns],
    );
    window.history.replaceState({}, "", "/runs?tab=overview");
    await copyShareLink();
    await copyShareLink(new URL("https://example.test/shared"));

    expect(writeText).toHaveBeenNthCalledWith(1, "alpha, beta");
    expect(writeText.mock.calls[1]?.[0]).toContain('"Title": "Copied row"');
    expect(writeText).toHaveBeenNthCalledWith(
      3,
      "http://localhost:3000/runs?tab=overview",
    );
    expect(writeText).toHaveBeenNthCalledWith(4, "https://example.test/shared");
  });

  it("falls back to execCommand when the clipboard api is unavailable", async () => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: undefined,
    });
    const execCommand = vi.fn().mockReturnValue(true);
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: execCommand,
    });

    await copyCell("legacy-copy");

    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(document.querySelector("textarea")).toBeNull();
  });
});
