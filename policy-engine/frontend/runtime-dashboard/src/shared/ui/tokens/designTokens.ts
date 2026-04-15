export type DesignTokenDefinition = {
  cssVar: `--${string}`;
  description: string;
};

export const foundationTokens = {
  color: {
    accent: {
      cssVar: "--accent",
      description: "Primary accent for active controls and highlights.",
    },
    canvas: {
      cssVar: "--canvas",
      description: "Global canvas background token.",
    },
    danger: {
      cssVar: "--danger",
      description: "High-risk/destructive base color.",
    },
    gold: {
      cssVar: "--gold",
      description: "Warning and pending-state foundation color.",
    },
    ink: {
      cssVar: "--ink",
      description: "Primary foreground color.",
    },
    line: {
      cssVar: "--line",
      description: "Neutral border and divider color.",
    },
    muted: {
      cssVar: "--muted",
      description: "Subdued text and secondary labels.",
    },
    paper: {
      cssVar: "--paper",
      description: "Paper-like raised surface tone.",
    },
    success: {
      cssVar: "--success",
      description: "Positive base color.",
    },
    surface: {
      cssVar: "--surface",
      description: "Default content surface tone.",
    },
    teal: {
      cssVar: "--teal",
      description: "Brand accent foundation.",
    },
    text: {
      cssVar: "--text",
      description: "Resolved text color token.",
    },
    warning: {
      cssVar: "--warning",
      description: "Warning base color.",
    },
  },
  motion: {
    fast: {
      cssVar: "--motion-fast",
      description: "Fast UI micro-transition duration.",
    },
    moderate: {
      cssVar: "--motion-moderate",
      description: "Default UI transition duration.",
    },
    slow: {
      cssVar: "--motion-slow",
      description: "Longer emphasis transition duration.",
    },
  },
  radius: {
    card: {
      cssVar: "--radius-card",
      description: "Default card radius.",
    },
    panel: {
      cssVar: "--radius-panel",
      description: "Large panel radius.",
    },
    pill: {
      cssVar: "--radius-pill",
      description: "Fully rounded badge/button radius.",
    },
  },
  elevation: {
    xs: {
      cssVar: "--shadow-xs",
      description: "Subtle hover elevation.",
    },
    sm: {
      cssVar: "--shadow-sm",
      description: "Light card elevation.",
    },
    md: {
      cssVar: "--shadow-md",
      description: "Default floating elevation.",
    },
    lg: {
      cssVar: "--shadow-lg",
      description: "Prominent dialog/dropdown elevation.",
    },
    xl: {
      cssVar: "--shadow-xl",
      description: "Maximum elevation (overlays, modals).",
    },
  },
  shadow: {
    focusRing: {
      cssVar: "--focus-ring",
      description: "Accessible focus ring color.",
    },
    panel: {
      cssVar: "--shadow-panel",
      description: "Primary raised panel shadow.",
    },
  },
  spacing: {
    lg: {
      cssVar: "--space-4",
      description: "Large space token.",
    },
    md: {
      cssVar: "--space-3",
      description: "Medium space token.",
    },
    sm: {
      cssVar: "--space-2",
      description: "Small space token.",
    },
    xl: {
      cssVar: "--space-5",
      description: "Extra-large space token.",
    },
  },
  typography: {
    mono: {
      cssVar: "--font-mono",
      description: "Monospace face for telemetry and code-like data.",
    },
    sans: {
      cssVar: "--font-sans",
      description: "Primary interface typeface.",
    },
    text2xs: {
      cssVar: "--text-2xs",
      description: "Extra-extra-small text size (10px).",
    },
    textXs: {
      cssVar: "--text-xs",
      description: "Extra-small text size (12px).",
    },
    textSm: {
      cssVar: "--text-sm",
      description: "Small text size (14px).",
    },
    textBase: {
      cssVar: "--text-base",
      description: "Base text size (16px).",
    },
    textLg: {
      cssVar: "--text-lg",
      description: "Large text size (18px).",
    },
    textXl: {
      cssVar: "--text-xl",
      description: "Extra-large text size (20px).",
    },
    text2xl: {
      cssVar: "--text-2xl",
      description: "Display text size (24px).",
    },
    text3xl: {
      cssVar: "--text-3xl",
      description: "Heading text size (30px).",
    },
    text4xl: {
      cssVar: "--text-4xl",
      description: "Hero text size (36px).",
    },
  },
  zIndex: {
    base: {
      cssVar: "--z-base",
      description: "Default stacking layer.",
    },
    dropdown: {
      cssVar: "--z-dropdown",
      description: "Dropdown menus stacking layer.",
    },
    sticky: {
      cssVar: "--z-sticky",
      description: "Sticky headers and footers.",
    },
    overlay: {
      cssVar: "--z-overlay",
      description: "Background overlays / scrims.",
    },
    modal: {
      cssVar: "--z-modal",
      description: "Modal dialogs and sheets.",
    },
    popover: {
      cssVar: "--z-popover",
      description: "Popovers and tooltips.",
    },
    toast: {
      cssVar: "--z-toast",
      description: "Toast notifications.",
    },
    command: {
      cssVar: "--z-command",
      description: "Command palette (highest layer).",
    },
  },
} as const satisfies Record<string, Record<string, DesignTokenDefinition>>;

/**
 * Responsive breakpoint tokens — mirrors the Tailwind CSS breakpoint scale.
 * Values are min-width thresholds in pixels.
 */
export const breakpointTokens = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  "2xl": 1536,
} as const;

export type BreakpointKey = keyof typeof breakpointTokens;

/** Build a `(min-width: …px)` media query string for a given breakpoint. */
export function mediaQuery(bp: BreakpointKey): string {
  return `(min-width: ${breakpointTokens[bp]}px)`;
}

export const semanticTokens = {
  action: {
    destructive: {
      cssVar: "--color-action-destructive",
      description: "Irreversible or destructive actions.",
    },
    primary: {
      cssVar: "--color-action-primary",
      description: "Primary actionable controls.",
    },
  },
  evidence: {
    verified: {
      cssVar: "--color-evidence-verified",
      description: "Evidence that passed validation or reuse checks.",
    },
  },
  governance: {
    blocker: {
      cssVar: "--color-governance-blocker",
      description: "Blocking governance decisions and legal stops.",
    },
    review: {
      cssVar: "--color-governance-review",
      description: "Human review required state.",
    },
  },
  severity: {
    high: {
      cssVar: "--color-severity-high",
      description: "Critical/high-severity operational events.",
    },
    low: {
      cssVar: "--color-severity-low",
      description: "Informational or low-severity events.",
    },
    medium: {
      cssVar: "--color-severity-medium",
      description: "Medium-severity operational events.",
    },
  },
  status: {
    approved: {
      cssVar: "--color-status-approved",
      description: "Approved/success status color.",
    },
    pending: {
      cssVar: "--color-status-pending",
      description: "Pending/in-progress status color.",
    },
    rejected: {
      cssVar: "--color-status-rejected",
      description: "Rejected/failure status color.",
    },
  },
  transport: {
    degraded: {
      cssVar: "--color-transport-degraded",
      description: "Polling fallback and degraded live transport state.",
    },
    live: {
      cssVar: "--color-transport-live",
      description: "Healthy live transport state.",
    },
  },
} as const satisfies Record<string, Record<string, DesignTokenDefinition>>;

export const designTokens = {
  foundation: foundationTokens,
  semantic: semanticTokens,
} as const;

export type FoundationTokens = typeof foundationTokens;
export type SemanticTokens = typeof semanticTokens;
export type DesignTokens = typeof designTokens;

export function toCssVar(token: DesignTokenDefinition) {
  return `var(${token.cssVar})`;
}

export function readDesignTokenValue(
  token: DesignTokenDefinition,
  root: HTMLElement = document.documentElement,
) {
  return getComputedStyle(root).getPropertyValue(token.cssVar).trim();
}
