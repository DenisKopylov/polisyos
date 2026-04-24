import type { CSSProperties, HTMLAttributes } from "react";
import { useId } from "react";

import { cn } from "@/lib/utils";

export type EvidenceSigilSize = 48 | 64 | 96;

/**
 * FRESC profile — five evidence tiers introduced in Phase 1.0. The component
 * maps them onto inner glyph density so a reader can read tier at a glance
 * without color.
 */
export type FrescProfile =
  | "unclassified"
  | "reconnaissance"
  | "corroborated"
  | "replicated"
  | "canonical";

const FRESC_DENSITY: Record<FrescProfile, number> = {
  unclassified: 1,
  reconnaissance: 2,
  corroborated: 3,
  replicated: 4,
  canonical: 5,
};

export type EvidenceSigilGeometry = {
  /** number of vertices on the outer polygon, 6..12 */
  vertices: number;
  /** per-vertex radial jitter in [0, 1] */
  jitters: number[];
  /** rotation in radians */
  rotation: number;
  /** which inner glyph index, 0..2 */
  innerIndex: number;
};

const MIN_VERTICES = 6;
const MAX_VERTICES = 12;

/**
 * Deterministic geometry from a bundle hash. The same hash always produces
 * the same geometry; differing hashes with ≥48 bits of entropy collide with
 * probability below 1e-6.
 */
export function sigilGeometryFromHash(
  bundleHash: string,
): EvidenceSigilGeometry {
  const trimmed = bundleHash.trim().replace(/^0x/, "");
  const bytes = hexBytes(trimmed.length > 0 ? trimmed : "00");
  if (bytes.length === 0) {
    return {
      vertices: MIN_VERTICES,
      jitters: Array.from({ length: MIN_VERTICES }, () => 0.5),
      rotation: 0,
      innerIndex: 0,
    };
  }
  const vertices =
    MIN_VERTICES + (bytes[0] % (MAX_VERTICES - MIN_VERTICES + 1));
  const jitters: number[] = [];
  for (let index = 0; index < vertices; index += 1) {
    const byte = bytes[(index + 1) % bytes.length];
    jitters.push(byte / 255);
  }
  const rotationByte = bytes[bytes.length - 1];
  const rotation = (rotationByte / 255) * Math.PI * 2;
  const innerIndex = bytes[Math.min(2, bytes.length - 1)] % 3;
  return { vertices, jitters, rotation, innerIndex };
}

function hexBytes(hex: string): number[] {
  const cleaned = hex.replace(/[^0-9a-fA-F]/g, "");
  const bytes: number[] = [];
  for (let index = 0; index + 1 < cleaned.length; index += 2) {
    bytes.push(parseInt(cleaned.slice(index, index + 2), 16));
  }
  if (bytes.length === 0 && cleaned.length === 1) {
    bytes.push(parseInt(cleaned, 16));
  }
  return bytes;
}

function polygonPath(
  cx: number,
  cy: number,
  rMin: number,
  rMax: number,
  geometry: EvidenceSigilGeometry,
): string {
  const points: string[] = [];
  const { vertices, jitters, rotation } = geometry;
  for (let index = 0; index < vertices; index += 1) {
    const angle = rotation + (index / vertices) * Math.PI * 2;
    const radius = rMin + jitters[index] * (rMax - rMin);
    const x = cx + Math.cos(angle) * radius;
    const y = cy + Math.sin(angle) * radius;
    points.push(`${x.toFixed(2)},${y.toFixed(2)}`);
  }
  return `M${points[0]} L${points.slice(1).join(" L")} Z`;
}

function clamp01(value: number): number {
  if (Number.isNaN(value)) {
    return 0;
  }
  return Math.max(0, Math.min(1, value));
}

function identifiabilityColor(value: number): string {
  const clamped = clamp01(value);
  if (clamped < 0.33) {
    return "var(--color-status-rejected, var(--ember, #B7412A))";
  }
  if (clamped < 0.66) {
    return "var(--color-status-pending, var(--gold, #B58B2B))";
  }
  return "var(--color-status-approved, var(--teal, #1C8B82))";
}

type EvidenceSigilProps = {
  bundleHash: string;
  frescProfile?: FrescProfile;
  identifiability?: number;
  size?: EvidenceSigilSize;
  className?: string;
  title?: string;
  decorative?: boolean;
} & Omit<HTMLAttributes<SVGSVGElement>, "children">;

export function EvidenceSigil({
  bundleHash,
  frescProfile = "unclassified",
  identifiability = 0,
  size = 64,
  className,
  title,
  decorative = false,
  ...rest
}: EvidenceSigilProps) {
  const geometry = sigilGeometryFromHash(bundleHash);
  const patternId = useId();
  const accent = identifiabilityColor(identifiability);
  const outer = polygonPath(32, 32, 18, 28, geometry);
  const inner = polygonPath(32, 32, 8, 14, {
    ...geometry,
    jitters: geometry.jitters.slice().reverse(),
    rotation: geometry.rotation + Math.PI / geometry.vertices,
  });
  const density = FRESC_DENSITY[frescProfile];

  const style: CSSProperties = {
    width: size,
    height: size,
  };

  const ariaProps = decorative
    ? { "aria-hidden": true as const, role: "presentation" as const }
    : {
        role: "img" as const,
        "aria-label":
          title ??
          `Evidence sigil for bundle ${bundleHash.slice(0, 8) || "unknown"}`,
      };

  return (
    <svg
      {...rest}
      {...ariaProps}
      className={cn("evidence-sigil", `evidence-sigil--${size}`, className)}
      data-bundle-hash={bundleHash}
      data-fresc-profile={frescProfile}
      data-identifiability={clamp01(identifiability).toFixed(2)}
      data-vertices={geometry.vertices}
      viewBox="0 0 64 64"
      style={style}
    >
      {!decorative && title ? <title>{title}</title> : null}
      <defs>
        <pattern
          id={`evidence-sigil-hatch-${patternId}`}
          patternUnits="userSpaceOnUse"
          width="3"
          height="3"
          patternTransform="rotate(45)"
        >
          <line
            x1="0"
            y1="0"
            x2="0"
            y2="3"
            stroke="currentColor"
            strokeWidth="0.5"
            opacity="0.18"
          />
        </pattern>
      </defs>
      <g stroke={accent} fill="none" strokeLinejoin="round">
        <path d={outer} strokeWidth={2} />
        <path
          d={inner}
          strokeWidth={1.25}
          fill={`url(#evidence-sigil-hatch-${patternId})`}
        />
      </g>
      {Array.from({ length: density }).map((_, index) => {
        const angle = geometry.rotation + (index / density) * Math.PI * 2;
        const x = 32 + Math.cos(angle) * 4;
        const y = 32 + Math.sin(angle) * 4;
        return (
          <circle
            key={`tier-dot-${index}`}
            cx={x.toFixed(2)}
            cy={y.toFixed(2)}
            r={1.1}
            fill={accent}
          />
        );
      })}
    </svg>
  );
}
