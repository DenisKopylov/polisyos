import type { CSSProperties, HTMLAttributes } from "react";

import { cn } from "@/shared/lib/utils";

export type JanusGlyphSize = 16 | 24 | 32;
export type JanusGlyphVariant = "mark" | "line" | "serif-punctuation";
export type JanusGlyphIntent = "default" | "verified" | "blocked" | "pending";

type JanusGlyphProps = {
  size?: JanusGlyphSize;
  variant?: JanusGlyphVariant;
  intent?: JanusGlyphIntent;
  inverted?: boolean;
  title?: string;
  decorative?: boolean;
  className?: string;
} & Omit<HTMLAttributes<SVGSVGElement>, "children">;

const INTENT_COLOR: Record<JanusGlyphIntent, string> = {
  default: "currentColor",
  verified: "var(--color-status-approved, var(--teal, #1C8B82))",
  blocked: "var(--color-status-rejected, var(--ember, #B7412A))",
  pending: "var(--color-status-pending, var(--gold, #B58B2B))",
};

function Mark({ inverted }: { inverted: boolean }) {
  const frame = inverted ? "#FBF8F2" : "#17191D";
  const stroke = inverted ? "#17191D" : "#FBF8F2";
  return (
    <>
      <rect x="1" y="1" width="30" height="30" rx="8" fill={frame} />
      <path
        d="M11 8 C 6 12, 6 20, 11 24"
        stroke={stroke}
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M21 8 C 26 12, 26 20, 21 24"
        stroke={stroke}
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />
      <circle cx="16" cy="16" r="1.3" fill="#1C8B82" />
    </>
  );
}

function Line() {
  return (
    <>
      <path
        d="M10 6 C 5 11, 5 21, 10 26"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M22 6 C 27 11, 27 21, 22 26"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />
      <circle cx="16" cy="16" r="1.3" fill="currentColor" stroke="none" />
    </>
  );
}

function SerifPunctuation() {
  return (
    <>
      <path
        d="M11 5 C 6 11, 6 21, 11 27"
        strokeWidth="1.75"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M21 5 C 26 11, 26 21, 21 27"
        strokeWidth="1.75"
        strokeLinecap="round"
        fill="none"
      />
      <circle cx="16" cy="16" r="1.1" fill="currentColor" stroke="none" />
    </>
  );
}

export function JanusGlyph({
  size = 24,
  variant = "mark",
  intent = "default",
  inverted = false,
  title,
  decorative = false,
  className,
  ...rest
}: JanusGlyphProps) {
  const ariaProps = decorative
    ? { "aria-hidden": true as const, role: "presentation" as const }
    : { role: "img" as const, "aria-label": title ?? "PolicyOS Janus mark" };

  const style: CSSProperties = {
    color: INTENT_COLOR[intent],
    width: size,
    height: size,
  };

  const stroke = variant === "mark" ? undefined : "currentColor";

  return (
    <svg
      {...rest}
      {...ariaProps}
      className={cn(
        "janus-glyph",
        `janus-glyph--${variant}`,
        `janus-glyph--${size}`,
        className,
      )}
      data-variant={variant}
      data-size={size}
      data-intent={intent}
      data-inverted={inverted ? "true" : undefined}
      viewBox="0 0 32 32"
      fill="none"
      stroke={stroke}
      style={style}
    >
      {!decorative && title ? <title>{title}</title> : null}
      {variant === "mark" ? <Mark inverted={inverted} /> : null}
      {variant === "line" ? <Line /> : null}
      {variant === "serif-punctuation" ? <SerifPunctuation /> : null}
    </svg>
  );
}

export const JANUS_ASSETS = {
  mark: "/atlas/logo-janus.svg",
  favicon: "/atlas/favicon.svg",
} as const;
