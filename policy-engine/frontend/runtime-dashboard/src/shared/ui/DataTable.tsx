import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import type { ExportValue } from "@/shared/ui/dataExport";

export type DataTableColumn<Row> = {
  key: string;
  header: ReactNode;
  className?: string;
  exportHeader?: string;
  exportValue?: (row: Row) => ExportValue;
  clipboardValue?: (row: Row) => ExportValue;
  render: (row: Row) => ReactNode;
};

export type DataTableProps<Row> = {
  rows: Row[];
  columns: Array<DataTableColumn<Row>>;
  rowKey: (row: Row, index: number) => string;
  className?: string;
  label?: string;
};

export function DataTable<Row>({
  className,
  columns,
  label = "Data table",
  rowKey,
  rows,
}: DataTableProps<Row>) {
  return (
    <div
      aria-label={label}
      role="region"
      className={cn(
        "border-line overflow-x-auto rounded-2xl border",
        className,
      )}
    >
      <table className="w-full min-w-[var(--table-min-width)] border-collapse text-[length:var(--control-text-md)]">
        <thead>
          <tr className="border-line text-muted border-b text-left text-xs tracking-wide uppercase">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cn(
                  "px-[var(--table-cell-px)] py-[var(--table-header-py)]",
                  column.className,
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={rowKey(row, index)}
              className="border-line/70 border-b last:border-b-0"
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cn(
                    "h-[var(--table-row-height)] px-[var(--table-cell-px)] py-[var(--table-cell-py)] align-top",
                    column.className,
                  )}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
