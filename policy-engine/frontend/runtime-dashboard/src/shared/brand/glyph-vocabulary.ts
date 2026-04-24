/**
 * Source of truth for the PolicyOS glyph alphabet.
 *
 * The ten radicals listed in `GLYPH_NAMES` are the full alphabet (ADR-045).
 * `DOMAIN_VOCABULARY` maps every term in the 18-word domain vocabulary to a
 * single radical. A domain term must map to exactly one radical; a radical
 * may carry one or two terms. Expanding the alphabet or the vocabulary
 * requires an ADR.
 *
 * The `pnpm test:glyph-vocabulary` script parses
 * `docs/brand/GLYPH_SPECIFICATION.md` and this module and fails when they
 * disagree.
 */

export const GLYPH_NAMES = [
  "intervention",
  "evidence",
  "provenance",
  "transport",
  "counterfactual",
  "identifiability",
  "reproducibility",
  "governance-pass",
  "blocker",
  "freshness",
] as const;

export type GlyphName = (typeof GLYPH_NAMES)[number];

export const GLYPH_ANCHORS: Record<GlyphName, string> = {
  intervention: "\u2299",
  evidence: "\u25B2",
  provenance: "\u27FF",
  transport: "\u21C4",
  counterfactual: "\u22CC",
  identifiability: "\u2254",
  reproducibility: "\u27F3",
  "governance-pass": "\u25EB",
  blocker: "\u2298",
  freshness: "\u25F7",
};

/**
 * 18-term domain vocabulary → glyph radical. Adding a term without a mapped
 * radical is a review-blocker. The full set of terms is closed and matches
 * the domain vocabulary anchored by Phase 1.0.
 */
export const DOMAIN_VOCABULARY: Record<string, GlyphName> = {
  intervention: "intervention",
  "policy-action": "intervention",
  evidence: "evidence",
  observation: "evidence",
  claim: "evidence",
  provenance: "provenance",
  lineage: "provenance",
  "source-chain": "provenance",
  transport: "transport",
  generalisation: "transport",
  "external-validity": "transport",
  counterfactual: "counterfactual",
  hypothetical: "counterfactual",
  "what-if": "counterfactual",
  identification: "identifiability",
  estimand: "identifiability",
  "identified-set": "identifiability",
  reproducibility: "reproducibility",
  replay: "reproducibility",
  "re-run": "reproducibility",
  "governance-approved": "governance-pass",
  compliant: "governance-pass",
  ratified: "governance-pass",
  blocker: "blocker",
  denied: "blocker",
  "legal-stop": "blocker",
  freshness: "freshness",
  staleness: "freshness",
  "age-of-evidence": "freshness",
};

export type DomainTerm = keyof typeof DOMAIN_VOCABULARY;

export function resolveGlyphForTerm(term: string): GlyphName | null {
  const normalized = term.trim().toLowerCase();
  return DOMAIN_VOCABULARY[normalized] ?? null;
}

export function isGlyphName(value: unknown): value is GlyphName {
  return (
    typeof value === "string" &&
    (GLYPH_NAMES as readonly string[]).includes(value)
  );
}

export const GLYPH_ASSET_BASE = "/atlas/glyphs";

export function glyphAssetUrl(name: GlyphName): string {
  return `${GLYPH_ASSET_BASE}/${name}.svg`;
}
