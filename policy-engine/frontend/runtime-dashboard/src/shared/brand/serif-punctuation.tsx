import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

import { JanusGlyph } from "./JanusGlyph";

type PolicyPropositionMarkProps = {
  children: ReactNode;
  /** When false, render without the opening/closing Janus punctuation. */
  bracketed?: boolean;
  className?: string;
} & Omit<HTMLAttributes<HTMLSpanElement>, "children">;

/**
 * `)·(` — the typographic signature of a policy proposition. The serif
 * Janus-line frames a claim that PolicyOS has minted as a proposition, the
 * only inline glyph role permitted outside the ten-radical alphabet.
 *
 * The opening and closing marks are rendered as accessible, decorative
 * `JanusGlyph` instances so screen readers receive the wrapped prose
 * unmodified.
 */
export function PolicyPropositionMark({
  children,
  bracketed = true,
  className,
  ...rest
}: PolicyPropositionMarkProps) {
  return (
    <span
      {...rest}
      className={cn(
        "policy-proposition",
        "inline-flex items-baseline gap-1.5 font-serif italic",
        className,
      )}
      data-policy-proposition
    >
      {bracketed ? (
        <JanusGlyph
          variant="serif-punctuation"
          size={16}
          decorative
          className="relative top-[2px] -scale-x-100"
        />
      ) : null}
      <span className="policy-proposition__body">{children}</span>
      {bracketed ? (
        <JanusGlyph
          variant="serif-punctuation"
          size={16}
          decorative
          className="relative top-[2px]"
        />
      ) : null}
    </span>
  );
}

export default PolicyPropositionMark;
