import { useVirtualizer } from "@tanstack/react-virtual";
import type { CSSProperties, HTMLAttributes, ReactNode } from "react";
import { useEffect, useRef } from "react";

import { cn } from "../lib/cn";

export type VirtualTableColumn<Row> = {
  className?: string;
  header: ReactNode;
  key: string;
  render: (row: Row) => ReactNode;
};

export type VirtualTableProps<Row> = {
  activeIndex?: number;
  ariaLabel?: string;
  className?: string;
  columns: Array<VirtualTableColumn<Row>>;
  estimateRowHeight?: number;
  initialScrollTop?: number;
  maxHeight?: number;
  onScrollPositionChange?: (scrollTop: number) => void;
  overscan?: number;
  rowClassName?: (row: Row, index: number) => string;
  rowKey: (row: Row, index: number) => string;
  rowProps?: (row: Row, index: number) => HTMLAttributes<HTMLTableRowElement>;
  rows: Row[];
};

export function VirtualTable<Row>({
  activeIndex,
  ariaLabel,
  className,
  columns,
  estimateRowHeight = 60,
  initialScrollTop = 0,
  maxHeight = 560,
  overscan = 10,
  onScrollPositionChange,
  rowClassName,
  rowKey,
  rowProps,
  rows,
}: VirtualTableProps<Row>) {
  const parentRef = useRef<HTMLDivElement | null>(null);
  const virtualizer = useVirtualizer({
    count: rows.length,
    estimateSize: () => estimateRowHeight,
    getItemKey: (index) => rowKey(rows[index], index),
    getScrollElement: () => parentRef.current,
    overscan,
  });
  const virtualRows = virtualizer.getVirtualItems();
  const paddingTop = virtualRows[0]?.start ?? 0;
  const paddingBottom =
    virtualizer.getTotalSize() -
    (virtualRows[virtualRows.length - 1]?.end ?? 0);

  useEffect(() => {
    if (activeIndex == null || activeIndex < 0 || activeIndex >= rows.length) {
      return;
    }
    virtualizer.scrollToIndex(activeIndex, { align: "auto" });
  }, [activeIndex, rows.length, virtualizer]);

  useEffect(() => {
    if (!parentRef.current) {
      return;
    }
    parentRef.current.scrollTop = initialScrollTop;
  }, [initialScrollTop]);

  return (
    <div
      ref={parentRef}
      className={cn("border-line overflow-auto rounded-2xl border", className)}
      onScroll={(event) => {
        onScrollPositionChange?.(event.currentTarget.scrollTop);
      }}
      style={{ maxHeight }}
    >
      <table
        aria-label={ariaLabel}
        className="min-w-full border-collapse text-sm"
      >
        <thead className="bg-panel sticky top-0 z-10">
          <tr className="border-line text-muted border-b text-left text-xs tracking-wide uppercase">
            {columns.map((column) => (
              <th
                key={column.key}
                className={cn("px-3 py-2", column.className)}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {paddingTop > 0 ? (
            <tr aria-hidden="true">
              <td
                colSpan={columns.length}
                style={{ height: paddingTop } satisfies CSSProperties}
              />
            </tr>
          ) : null}

          {virtualRows.map((virtualRow) => {
            const row = rows[virtualRow.index];
            const resolvedRowProps = rowProps?.(row, virtualRow.index) ?? {};

            return (
              <tr
                key={virtualRow.key}
                data-index={virtualRow.index}
                ref={virtualizer.measureElement}
                className={cn(
                  "border-line/70 border-b last:border-b-0",
                  rowClassName?.(row, virtualRow.index),
                  resolvedRowProps.className,
                )}
                {...resolvedRowProps}
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
            );
          })}

          {paddingBottom > 0 ? (
            <tr aria-hidden="true">
              <td
                colSpan={columns.length}
                style={{ height: paddingBottom } satisfies CSSProperties}
              />
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
