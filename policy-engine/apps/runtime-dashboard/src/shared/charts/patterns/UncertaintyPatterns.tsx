export type UncertaintyPatternIds = {
  assumed: string;
  disputed: string;
  estimated: string;
  unknown: string;
};

export function buildUncertaintyPatternIds(
  prefix: string,
): UncertaintyPatternIds {
  return {
    assumed: `${prefix}-assumed`,
    disputed: `${prefix}-disputed`,
    estimated: `${prefix}-estimated`,
    unknown: `${prefix}-unknown`,
  };
}

export function resolveUncertaintyPatternFill(
  pattern: "crosshatch" | "diagonal-lines" | "dots" | "none",
  ids: UncertaintyPatternIds,
) {
  if (pattern === "diagonal-lines") {
    return `url(#${ids.estimated})`;
  }
  if (pattern === "dots") {
    return `url(#${ids.assumed})`;
  }
  if (pattern === "crosshatch") {
    return `url(#${ids.unknown})`;
  }
  return "none";
}

export function UncertaintyPatterns({ ids }: { ids: UncertaintyPatternIds }) {
  return (
    <defs>
      <pattern
        id={ids.estimated}
        data-testid={ids.estimated}
        width="4"
        height="4"
        patternUnits="userSpaceOnUse"
        patternTransform="rotate(45)"
      >
        <line
          x1="0"
          y1="0"
          x2="0"
          y2="4"
          stroke="var(--slate)"
          strokeWidth="1"
          opacity="0.4"
        />
      </pattern>
      <pattern
        id={ids.assumed}
        data-testid={ids.assumed}
        width="8"
        height="8"
        patternUnits="userSpaceOnUse"
      >
        <circle
          cx="2"
          cy="2"
          r="1.05"
          fill="var(--gold-vibrant)"
          opacity="0.5"
        />
        <circle
          cx="6"
          cy="6"
          r="1.05"
          fill="var(--gold-vibrant)"
          opacity="0.5"
        />
      </pattern>
      <pattern
        id={ids.unknown}
        data-testid={ids.unknown}
        width="6"
        height="6"
        patternUnits="userSpaceOnUse"
      >
        <path
          d="M0 0 L6 6 M6 0 L0 6"
          stroke="var(--slate)"
          strokeWidth="1"
          opacity="0.45"
        />
      </pattern>
      <pattern
        id={ids.disputed}
        data-testid={ids.disputed}
        width="8"
        height="8"
        patternUnits="userSpaceOnUse"
      >
        <path
          d="M0 0 L8 8 M8 0 L0 8"
          stroke="var(--ember)"
          strokeWidth="1"
          opacity="0.28"
        />
      </pattern>
    </defs>
  );
}
