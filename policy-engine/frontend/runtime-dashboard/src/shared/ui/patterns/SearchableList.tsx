import { startTransition, useDeferredValue, useMemo } from "react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { EmptyState, Input } from "@/shared/ui/primitives";

type SearchableListProps<Item> = {
  items: Item[];
  query: string;
  onQueryChange: (value: string) => void;
  getItemKey: (item: Item) => string;
  getSearchText: (item: Item) => string;
  renderItem: (item: Item) => ReactNode;
  emptyTitle: string;
  emptyBody: string;
  placeholder: string;
  className?: string;
};

export function SearchableList<Item>({
  className,
  emptyBody,
  emptyTitle,
  getItemKey,
  getSearchText,
  items,
  onQueryChange,
  placeholder,
  query,
  renderItem,
}: SearchableListProps<Item>) {
  const deferredQuery = useDeferredValue(query);
  const filteredItems = useMemo(() => {
    const normalized = deferredQuery.trim().toLowerCase();
    if (!normalized) {
      return items;
    }
    return items.filter((item) =>
      getSearchText(item).toLowerCase().includes(normalized),
    );
  }, [deferredQuery, getSearchText, items]);

  return (
    <div className={cn("space-y-4", className)}>
      <Input
        value={query}
        placeholder={placeholder}
        onChange={(event) => {
          const nextValue = event.target.value;
          startTransition(() => onQueryChange(nextValue));
        }}
      />
      {filteredItems.length === 0 ? (
        <EmptyState title={emptyTitle} body={emptyBody} />
      ) : (
        <div className="space-y-3">
          {filteredItems.map((item) => (
            <div key={getItemKey(item)}>{renderItem(item)}</div>
          ))}
        </div>
      )}
    </div>
  );
}
