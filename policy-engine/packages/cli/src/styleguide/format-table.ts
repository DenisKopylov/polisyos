export type CliTableCell = number | string | null | undefined;

export type CliTableOptions = {
  maxWidth?: number;
};

export function formatTable(
  headers: readonly string[],
  rows: readonly (readonly CliTableCell[])[],
  options: CliTableOptions = {},
) {
  const normalizedRows = rows.map((row) =>
    headers.map((_, index) => formatCell(row[index])),
  );
  const widths = headers.map((header, index) =>
    Math.min(
      options.maxWidth ?? 32,
      Math.max(
        header.length,
        ...normalizedRows.map((row) => row[index]?.length ?? 0),
      ),
    ),
  );
  const separator = widths.map((width) => "-".repeat(width)).join("-+-");
  const lines = [
    joinRow(headers, widths),
    separator,
    ...normalizedRows.map((row) => joinRow(row, widths)),
  ];

  return lines.join("\n");
}

function joinRow(row: readonly string[], widths: readonly number[]) {
  return row
    .map((cell, index) => {
      const clipped = clip(cell, widths[index]);
      return isNumericLike(clipped)
        ? clipped.padStart(widths[index])
        : clipped.padEnd(widths[index]);
    })
    .join(" | ");
}

function formatCell(cell: CliTableCell) {
  if (cell === null || cell === undefined) {
    return "-";
  }

  return String(cell);
}

function clip(value: string, width: number) {
  if (value.length <= width) {
    return value;
  }

  if (width <= 3) {
    return value.slice(0, width);
  }

  return `${value.slice(0, width - 3)}...`;
}

function isNumericLike(value: string) {
  return /^[-+]?\d+(?:\.\d+)?(?:%|pp|x)?$/.test(value.trim());
}
