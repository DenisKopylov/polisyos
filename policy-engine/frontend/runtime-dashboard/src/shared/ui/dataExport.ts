import type { DataTableColumn } from "@/shared/ui/DataTable";

export type ExportValue =
  | boolean
  | Date
  | number
  | string
  | null
  | undefined
  | ExportValue[]
  | Record<string, unknown>;

export type DataExportColumn<Row> = Pick<
  DataTableColumn<Row>,
  "clipboardValue" | "exportHeader" | "exportValue" | "header" | "key"
>;

function serializeExportValue(value: ExportValue): string {
  if (value == null) {
    return "";
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  if (Array.isArray(value)) {
    return value.map(serializeExportValue).join(", ");
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function resolveColumnHeader<Row>(column: DataExportColumn<Row>) {
  if (column.exportHeader) {
    return column.exportHeader;
  }
  if (typeof column.header === "string" || typeof column.header === "number") {
    return String(column.header);
  }
  return column.key;
}

function escapeCsvCell(value: string) {
  const normalized = value.split('"').join('""');
  if (
    normalized.includes(",") ||
    normalized.includes('"') ||
    normalized.includes("\n")
  ) {
    return `"${normalized}"`;
  }
  return normalized;
}

function downloadTextFile(filename: string, content: string, mimeType: string) {
  if (typeof document === "undefined") {
    return;
  }

  const blob = new Blob([content], {
    type: mimeType,
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

async function copyText(text: string) {
  if (typeof navigator !== "undefined" && navigator.clipboard) {
    await navigator.clipboard.writeText(text);
    return;
  }

  if (typeof document === "undefined") {
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

export function buildRowExportRecord<Row>(
  row: Row,
  columns: Array<DataExportColumn<Row>>,
) {
  return Object.fromEntries(
    columns.map((column) => [
      resolveColumnHeader(column),
      serializeExportValue(
        column.exportValue ? column.exportValue(row) : column.clipboardValue?.(row),
      ),
    ]),
  );
}

export function buildTableExportRecords<Row>(
  rows: Row[],
  columns: Array<DataExportColumn<Row>>,
) {
  return rows.map((row) => buildRowExportRecord(row, columns));
}

export function exportCsv<Row>(
  filename: string,
  rows: Row[],
  columns: Array<DataExportColumn<Row>>,
) {
  const headers = columns.map(resolveColumnHeader);
  const csvRows = rows.map((row) =>
    columns
      .map((column) =>
        escapeCsvCell(
          serializeExportValue(
            column.exportValue
              ? column.exportValue(row)
              : column.clipboardValue?.(row),
          ),
        ),
      )
      .join(","),
  );
  const content = [headers.join(","), ...csvRows].join("\n");
  downloadTextFile(filename, content, "text/csv;charset=utf-8");
}

export function exportJson(filename: string, payload: unknown) {
  downloadTextFile(
    filename,
    JSON.stringify(payload, null, 2),
    "application/json;charset=utf-8",
  );
}

export async function copyCell(value: ExportValue) {
  await copyText(serializeExportValue(value));
}

export async function copyRow<Row>(
  row: Row,
  columns: Array<DataExportColumn<Row>>,
) {
  await copyText(JSON.stringify(buildRowExportRecord(row, columns), null, 2));
}

export async function copyShareLink(input?: string | URL) {
  const resolved =
    typeof input === "string"
      ? input
      : input instanceof URL
        ? input.toString()
        : typeof window !== "undefined"
          ? window.location.href
          : "";

  await copyText(resolved);
}
