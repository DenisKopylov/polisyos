import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

import type { ReadingViewDefinition } from "./reading-view-tokens";

type DefinitionListProps = {
  items: ReadingViewDefinition[];
  className?: string;
} & Omit<HTMLAttributes<HTMLDListElement>, "children">;

export function DefinitionList({
  items,
  className,
  ...rest
}: DefinitionListProps) {
  if (items.length === 0) {
    return null;
  }

  return (
    <dl
      {...rest}
      className={cn(
        "reading-definition-list grid gap-3 sm:grid-cols-2",
        className,
      )}
    >
      {items.map((item) => (
        <div
          key={item.term}
          className="border-line bg-surface/60 rounded-2xl border p-4"
        >
          <dt className="definition-term text-muted text-[0.72rem] font-semibold uppercase">
            {item.term}
          </dt>
          <dd className="mt-2 text-sm leading-relaxed">{item.definition}</dd>
        </div>
      ))}
    </dl>
  );
}
