import {
  densityScale,
  designTokens,
  foundationTokens,
  readDesignTokenValue,
  semanticTokens,
  toCssVar,
} from "@/shared/ui/tokens/designTokens";

describe("designTokens", () => {
  afterEach(() => {
    document.documentElement.style.removeProperty("--accent");
  });

  it("exposes grouped token registries", () => {
    expect(designTokens.density).toBe(densityScale);
    expect(designTokens.foundation).toBe(foundationTokens);
    expect(designTokens.semantic).toBe(semanticTokens);
  });

  it("converts tokens to css vars and reads computed values", () => {
    document.documentElement.style.setProperty("--accent", "#0ea5e9");

    expect(toCssVar(foundationTokens.color.accent)).toBe("var(--accent)");
    expect(readDesignTokenValue(foundationTokens.color.accent)).toBe("#0ea5e9");
  });
});
