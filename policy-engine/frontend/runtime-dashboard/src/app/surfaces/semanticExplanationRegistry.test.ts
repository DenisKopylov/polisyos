import { SURFACE_REGISTRY } from "./surfaceRegistry";
import {
  getSemanticExplanation,
  getSurfaceSemanticExplanation,
  SEMANTIC_EXPLANATION_REGISTRY,
} from "./semanticExplanationRegistry";

describe("semantic explanation registry", () => {
  it("contains an explanation for every registered surface", () => {
    for (const surface of SURFACE_REGISTRY) {
      expect(getSurfaceSemanticExplanation(surface.id)).toMatchObject({
        id: surface.semanticExplanationId,
        kind: "surface",
        surfaceId: surface.id,
      });
    }
  });

  it("includes shared E2 primitive explanations", () => {
    expect(getSemanticExplanation("chart.confidenceInterval")?.kind).toBe(
      "chart",
    );
    expect(getSemanticExplanation("glyph.atlasRadical")?.provenance).toContain(
      "ADR-045",
    );
    expect(SEMANTIC_EXPLANATION_REGISTRY.length).toBeGreaterThan(
      SURFACE_REGISTRY.length,
    );
  });

  it("keeps explanation ids unique", () => {
    const ids = SEMANTIC_EXPLANATION_REGISTRY.map((entry) => entry.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
