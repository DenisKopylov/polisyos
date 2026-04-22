import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";
import { Glyph } from "@/shared/brand/Glyph";
import type { ProvenanceItem } from "@/shared/brand/provenance-adapter";

export type ProvenanceStripDensity = "comfortable" | "compact";

type ProvenanceStripProps = {
  /** 3..8 provenance items. Lower counts are allowed but discouraged — the
   * strip carries conviction only when the eyebrow carries at least three
   * glyphs. */
  items: ProvenanceItem[];
  /** Present tense noun-phrase. Rendered as the accessible eyebrow label
   * sibling to the glyph strip. */
  title?: string;
  density?: ProvenanceStripDensity;
  className?: string;
  /** Optional trailing content such as a freshness badge. Rendered after
   * the glyphs. */
  trailing?: ReactNode;
} & Omit<HTMLAttributes<HTMLDivElement>, "children">;

const ITEM_SPACING: Record<ProvenanceStripDensity, string> = {
  comfortable: "gap-3",
  compact: "gap-2",
};

const LABEL_SIZE: Record<ProvenanceStripDensity, string> = {
  comfortable: "text-[0.68rem]",
  compact: "text-[0.62rem]",
};

export function ProvenanceStrip({
  items,
  title,
  density = "comfortable",
  className,
  trailing,
  ...rest
}: ProvenanceStripProps) {
  return (
    <div
      {...rest}
      role="group"
      aria-label={title ?? "Provenance strip"}
      data-density={density}
      data-testid="provenance-strip"
      className={cn(
        "provenance-strip inline-flex flex-wrap items-center",
        ITEM_SPACING[density],
        className,
      )}
    >
      {title ? (
        <span
          className={cn(
            "text-muted font-semibold tracking-[0.2em] uppercase",
            LABEL_SIZE[density],
          )}
        >
          {title}
        </span>
      ) : null}
      <ul
        className={cn(
          "flex flex-wrap items-center",
          density === "comfortable" ? "gap-2" : "gap-1.5",
        )}
      >
        {items.map((item) => (
          <li
            key={item.id}
            className="inline-flex items-center gap-1.5"
            data-glyph={item.glyph}
            data-intent={item.intent ?? "default"}
          >
            <Glyph
              name={item.glyph}
              size={density === "comfortable" ? 14 : 12}
              intent={item.intent}
              strokeStyle={item.strokeStyle ?? "solid"}
              title={item.label}
            />
            <span
              className={cn(
                "text-muted font-medium",
                density === "comfortable"
                  ? "text-xs"
                  : "text-[0.68rem] leading-none",
              )}
              title={item.detail}
            >
              {item.label}
            </span>
          </li>
        ))}
      </ul>
      {trailing ? <span className="ml-2">{trailing}</span> : null}
    </div>
  );
}
