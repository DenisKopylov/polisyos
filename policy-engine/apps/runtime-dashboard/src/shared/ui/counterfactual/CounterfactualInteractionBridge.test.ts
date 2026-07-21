import {
  COUNTERFACTUAL_MODES,
  normalizeCounterfactualMode,
} from "./CounterfactualInteractionBridge";

describe("CounterfactualInteractionBridge", () => {
  it.each(COUNTERFACTUAL_MODES)(
    "preserves generated interaction mode %s",
    (mode) => {
      expect(normalizeCounterfactualMode(mode)).toBe(mode);
    },
  );

  it("normalizes an unknown URL mode to the neutral actual view", () => {
    expect(normalizeCounterfactualMode("future-mode")).toBe("actual");
    expect(normalizeCounterfactualMode("toString")).toBe("actual");
  });
});
