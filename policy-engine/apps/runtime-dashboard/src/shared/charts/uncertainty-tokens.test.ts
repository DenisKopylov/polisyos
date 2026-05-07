import {
  resolveCounterfactualColor,
  resolveIdentifiabilityPattern,
  resolveUncertaintyBandOpacity,
  resolveUncertaintyIntervalColor,
  resolveUncertaintyPaletteColor,
  uncertaintyTokens,
} from "@/shared/charts/uncertainty-tokens";

describe("uncertainty tokens", () => {
  it("returns palette colors for normal and disputed states", () => {
    expect(resolveUncertaintyPaletteColor("default")).toBe(
      uncertaintyTokens.pointEstimate,
    );
    expect(resolveUncertaintyPaletteColor("disputed")).toBe(
      uncertaintyTokens.disputed,
    );
  });

  it("resolves interval and counterfactual colors", () => {
    expect(resolveUncertaintyIntervalColor("default")).toBe(
      uncertaintyTokens.confidenceInterval,
    );
    expect(resolveUncertaintyIntervalColor("disputed")).toBe(
      uncertaintyTokens.disputed,
    );
    expect(resolveCounterfactualColor("default")).toBe(
      uncertaintyTokens.counterfactualInterval,
    );
    expect(resolveCounterfactualColor("disputed")).toBe(
      uncertaintyTokens.disputed,
    );
  });

  it("maps interval levels to layered opacities", () => {
    expect(resolveUncertaintyBandOpacity(0.5)).toBe(0.26);
    expect(resolveUncertaintyBandOpacity(0.8)).toBe(0.18);
    expect(resolveUncertaintyBandOpacity(0.95)).toBe(0.1);
  });

  it("resolves identifiability patterns", () => {
    expect(resolveIdentifiabilityPattern("identified")).toBe("none");
    expect(resolveIdentifiabilityPattern("estimated")).toBe("diagonal-lines");
    expect(resolveIdentifiabilityPattern("assumed")).toBe("dots");
  });
});
