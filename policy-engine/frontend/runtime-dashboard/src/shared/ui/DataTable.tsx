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
      tabIndex={0}
      className={cn(
        "overflow-x-auto rounded-2xl border border-line",
        className,
      )}
    >
      <table className="min-w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cn("px-3 py-2", column.className)}
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
                  className={cn("px-3 py-3 align-top", column.className)}
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
