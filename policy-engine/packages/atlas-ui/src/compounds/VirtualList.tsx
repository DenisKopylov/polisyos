import { useVirtualizer } from "@tanstack/react-virtual";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useRef } from "react";

import { cn } from "../lib/cn";

export const VIRTUALIZATION_THRESHOLD = 30;

export type VirtualListProps<Item> = {
  className?: string;
  estimateSize?: number;
  itemKey: (item: Item, index: number) => string;
  items: Item[];
  maxHeight?: number;
  overscan?: number;
  renderItem: (item: Item, index: number) => ReactNode;
};

export function VirtualList<Item>({
  className,
  estimateSize = 72,
  itemKey,
  items,
  maxHeight = 420,
  overscan = 8,
  renderItem,
}: VirtualListProps<Item>) {
  const parentRef = useRef<HTMLDivElement | null>(null);
  const virtualizer = useVirtualizer({
    count: items.length,
    estimateSize: () => estimateSize,
    getItemKey: (index) => itemKey(items[index], index),
    getScrollElement: () => parentRef.current,
    overscan,
  });
  const virtualItems = virtualizer.getVirtualItems();

  useEffect(() => {
    virtualizer.measure();
  }, [items.length, virtualizer]);

  return (
    <div
      ref={parentRef}
      className={cn("overflow-y-auto", className)}
      style={{ maxHeight }}
    >
      <div
        style={
          {
            height: virtualizer.getTotalSize(),
            position: "relative",
            width: "100%",
          } satisfies CSSProperties
        }
      >
        {virtualItems.map((virtualItem) => (
          <div
            key={virtualItem.key}
            data-index={virtualItem.index}
            ref={virtualizer.measureElement}
            style={
              {
                left: 0,
                paddingBottom: 8,
                position: "absolute",
                top: 0,
                transform: `translateY(${virtualItem.start}px)`,
                width: "100%",
              } satisfies CSSProperties
            }
          >
            {renderItem(items[virtualItem.index], virtualItem.index)}
          </div>
        ))}
      </div>
    </div>
  );
}
