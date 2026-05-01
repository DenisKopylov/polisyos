import {
  SURFACE_REGISTRY,
  type SurfaceId,
  type SurfaceRegistryEntry,
} from "./surfaceRegistry";

export type SemanticExplanationKind = "chart" | "control" | "glyph" | "surface";

export type SemanticExplanationEntry = {
  accessibilityNote: string;
  dataFreshness: string;
  id: string;
  intent: string;
  kind: SemanticExplanationKind;
  provenance: string;
  surfaceId?: SurfaceId;
};

function surfaceExplanationIntent(surface: SurfaceRegistryEntry) {
  if (surface.kind === "workspace") {
    return "Primary workspace entry point. It orients the operator before nested work starts.";
  }
  if (surface.kind === "run-tab") {
    return "Run inspector tab. It narrows attention without adding a new top-level navigation item.";
  }
  return "Nested panel surface. It can be deep-linked, replayed, and explained without expanding the sidebar.";
}

const SURFACE_EXPLANATIONS: SemanticExplanationEntry[] = SURFACE_REGISTRY.map(
  (surface) => ({
    accessibilityNote:
      "Shown through the comprehension layer as structural navigation, not authored decision prose.",
    dataFreshness:
      surface.kind === "workspace"
        ? "Uses the workspace bootstrap contract and active route context."
        : "Uses the parent workspace or run snapshot active at the current route.",
    id: surface.semanticExplanationId,
    intent: surfaceExplanationIntent(surface),
    kind: "surface",
    provenance:
      "Defined by the Atlas surface registry and linked to route, command, replay, and fixture metadata.",
    surfaceId: surface.id,
  }),
);

const CORE_EXPLANATIONS: SemanticExplanationEntry[] = [
  {
    accessibilityNote:
      "Must expose label, estimate, interval level, and disputed state to assistive technology.",
    dataFreshness:
      "Uses the same temporal scope as the quantity or decision packet that owns the chart.",
    id: "chart.confidenceInterval",
    intent:
      "Explains uncertainty around a point estimate and whether the displayed interval is decision-bearing.",
    kind: "chart",
    provenance:
      "Derived from QuantityValue uncertainty metadata or the decision packet metric contract.",
  },
  {
    accessibilityNote:
      "Must name the radical and never rely on shape alone for status meaning.",
    dataFreshness:
      "Glyphs are semantic chrome; freshness is inherited from the object they annotate.",
    id: "glyph.atlasRadical",
    intent:
      "Maps a domain concept to the closed 10-radical Atlas glyph alphabet.",
    kind: "glyph",
    provenance: "Defined by ADR-045 and src/shared/brand/glyph-vocabulary.ts.",
  },
  {
    accessibilityNote:
      "Must expose current threshold, affected count, and keyboard-adjustable controls.",
    dataFreshness:
      "Uses the active run, packet, or workspace snapshot at the moment the control changes.",
    id: "control.thresholdDial",
    intent:
      "Lets an operator raise or lower a trust/sensitivity threshold and see which claims remain visible.",
    kind: "control",
    provenance:
      "Recorded through the replay event envelope so the adjustment can be audited later.",
  },
];

export const SEMANTIC_EXPLANATION_REGISTRY: readonly SemanticExplanationEntry[] =
  [...SURFACE_EXPLANATIONS, ...CORE_EXPLANATIONS] as const;

export function getSemanticExplanation(id: string) {
  return SEMANTIC_EXPLANATION_REGISTRY.find((entry) => entry.id === id) ?? null;
}

export function getSurfaceSemanticExplanation(surfaceId: SurfaceId) {
  return (
    SEMANTIC_EXPLANATION_REGISTRY.find(
      (entry) => entry.kind === "surface" && entry.surfaceId === surfaceId,
    ) ?? null
  );
}
