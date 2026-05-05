import type { CSSProperties, HTMLAttributes, ReactNode } from "react";

import { cn } from "@/shared/lib/utils";

import { GLYPH_ANCHORS, type GlyphName } from "./glyph-vocabulary";

export type GlyphSize = 12 | 14 | 16 | 24;
export type GlyphIntent = "default" | "verified" | "blocked" | "pending";
export type GlyphStrokeStyle = "solid" | "dashed" | "double";
export type GlyphDiacritic = "strict" | "assumed" | "scoped";

const INTENT_COLOR: Record<GlyphIntent, string> = {
  default: "var(--ink, currentColor)",
  verified: "var(--color-status-approved, var(--teal, #1C8B82))",
  blocked: "var(--color-status-rejected, var(--ember, #B7412A))",
  pending: "var(--color-status-pending, var(--gold, #B58B2B))",
};

const SIZE_STROKE: Record<GlyphSize, number> = {
  12: 1.25,
  14: 1.25,
  16: 1.5,
  24: 1.5,
};

/**
 * Path data for each radical, authored on a 5×5 unit grid published into a
 * 24-unit viewBox. Strokes inherit `currentColor` from the host.
 */
const GLYPH_GEOMETRY: Record<GlyphName, ReactNode> = {
  intervention: (
    <>
      <circle cx="12" cy="12" r="7" />
      <circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" />
    </>
  ),
  evidence: <path d="M12 4 L20 20 L4 20 Z" />,
  provenance: (
    <>
      <path d="M3 12 C 6 7, 9 17, 12 12 S 18 7, 21 12" />
      <path d="M17.5 9.5 L21 12 L17.5 14.5" />
    </>
  ),
  transport: (
    <>
      <path d="M4 9 L19 9" />
      <path d="M16 6 L19 9 L16 12" />
      <path d="M20 15 L5 15" />
      <path d="M8 12 L5 15 L8 18" />
    </>
  ),
  counterfactual: (
    <>
      <path d="M12 4 L4 20" />
      <path d="M12 4 L20 20" />
    </>
  ),
  identifiability: (
    <>
      <path d="M3 10 L15 10" />
      <path d="M3 14 L15 14" />
      <circle cx="19" cy="10" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="19" cy="14" r="1.1" fill="currentColor" stroke="none" />
    </>
  ),
  reproducibility: (
    <>
      <path d="M19 12 A 7 7 0 1 0 15 18" />
      <path d="M15 14 L15 18 L19 18" />
    </>
  ),
  "governance-pass": (
    <>
      <rect x="4" y="4" width="16" height="16" rx="1" />
      <path d="M10 4 L10 20" />
    </>
  ),
  blocker: (
    <>
      <circle cx="12" cy="12" r="7" />
      <path d="M7 7 L17 17" />
    </>
  ),
  freshness: (
    <>
      <circle cx="12" cy="12" r="7" />
      <path d="M12 12 L12 5" />
      <path d="M12 12 L19 12" />
    </>
  ),
};

const DIACRITIC_GEOMETRY: Record<GlyphDiacritic, ReactNode> = {
  strict: <path d="M8 1.8 L16 1.8" strokeWidth={1.25} />,
  assumed: (
    <>
      <path d="M9 1 L15 1" strokeWidth={1.25} />
      <path d="M9 3.4 L15 3.4" strokeWidth={1.25} />
    </>
  ),
  scoped: (
    <>
      <path d="M2 8 C 0.5 12, 0.5 12, 2 16" strokeWidth={1.25} />
      <path d="M22 8 C 23.5 12, 23.5 12, 22 16" strokeWidth={1.25} />
    </>
  ),
};

const STROKE_DASHARRAY: Record<GlyphStrokeStyle, string | undefined> = {
  solid: undefined,
  dashed: "2 1.5",
  double: undefined,
};

export type GlyphProps = {
  name: GlyphName;
  size?: GlyphSize;
  intent?: GlyphIntent;
  strokeStyle?: GlyphStrokeStyle;
  diacritic?: GlyphDiacritic;
  title?: string;
  decorative?: boolean;
  className?: string;
} & Omit<HTMLAttributes<SVGSVGElement>, "children">;

export function Glyph({
  name,
  size = 14,
  intent = "default",
  strokeStyle = "solid",
  diacritic,
  title,
  decorative = false,
  className,
  ...rest
}: GlyphProps) {
  const strokeWidth = SIZE_STROKE[size];
  const color = INTENT_COLOR[intent];
  const dash = STROKE_DASHARRAY[strokeStyle];
  const geometry = GLYPH_GEOMETRY[name];
  const diacriticGeometry = diacritic ? DIACRITIC_GEOMETRY[diacritic] : null;
  const inner = (
    <>
      <g>{geometry}</g>
      {strokeStyle === "double" ? (
        <g
          style={{
            transform:
              "translate(12px, 12px) scale(0.72) translate(-12px, -12px)",
            transformOrigin: "center",
          }}
        >
          {geometry}
        </g>
      ) : null}
      {diacriticGeometry ? <g>{diacriticGeometry}</g> : null}
    </>
  );

  const style: CSSProperties = {
    color,
    width: size,
    height: size,
  };

  const ariaProps = decorative
    ? { "aria-hidden": true as const, role: "presentation" as const }
    : {
        role: "img" as const,
        "aria-label": title ?? name,
      };

  return (
    <svg
      {...rest}
      {...ariaProps}
      className={cn("brand-glyph", `brand-glyph--${name}`, className)}
      data-glyph-name={name}
      data-glyph-intent={intent}
      data-glyph-stroke-style={strokeStyle}
      data-glyph-size={size}
      data-glyph-diacritic={diacritic ?? undefined}
      data-glyph-anchor={GLYPH_ANCHORS[name]}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeDasharray={dash}
      style={style}
      viewBox="0 0 24 24"
    >
      {!decorative && title ? <title>{title}</title> : null}
      {inner}
    </svg>
  );
}

Glyph.displayName = "Glyph";
