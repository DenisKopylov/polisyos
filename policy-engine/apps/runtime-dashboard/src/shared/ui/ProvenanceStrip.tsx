import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/shared/lib/utils";
import { Glyph, type GlyphSize } from "@/shared/brand/Glyph";
import { GLYPH_ANCHORS } from "@/shared/brand/glyph-vocabulary";
import type { ProvenanceItem } from "@/shared/brand/provenance-adapter";

export type ProvenanceStripDensity = "comfortable" | "compact" | "condensed";

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
  condensed: "gap-1.5",
};

const LABEL_SIZE: Record<ProvenanceStripDensity, string> = {
  comfortable: "text-[0.68rem]",
  compact: "text-[0.62rem]",
  condensed: "text-[0.58rem]",
};

const GLYPH_SIZE: Record<ProvenanceStripDensity, GlyphSize> = {
  comfortable: 14,
  compact: 12,
  condensed: 12,
};

const ITEM_LABEL_SIZE: Record<ProvenanceStripDensity, string> = {
  comfortable: "text-xs",
  compact: "text-[0.68rem] leading-none",
  condensed: "text-[0.62rem] leading-none",
};

export function ProvenanceStrip({
  items,
  title,
  density = "comfortable",
  className,
  trailing,
  ...rest
}: ProvenanceStripProps) {
  const glyphSummary = items
    .map((item) => GLYPH_ANCHORS[item.glyph] ?? item.glyph)
    .join(" ");

  return (
    <div
      {...rest}
      role="group"
      aria-label={title ?? "Provenance strip"}
      data-density={density}
      data-glyph-summary={glyphSummary}
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
          density === "comfortable"
            ? "gap-2"
            : density === "compact"
              ? "gap-1.5"
              : "gap-1",
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
              size={GLYPH_SIZE[density]}
              intent={item.intent}
              strokeStyle={item.strokeStyle ?? "solid"}
              title={item.label}
            />
            <span
              className={cn("text-muted font-medium", ITEM_LABEL_SIZE[density])}
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
