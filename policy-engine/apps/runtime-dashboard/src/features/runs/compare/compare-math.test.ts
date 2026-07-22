import {
  comparabilityLabel,
  formatSignedNumber,
  saliencePercent,
  significanceLabel,
  topDeltas,
} from "./compare-math";
import * as compareMath from "./compare-math";
import { policyDiffFixture } from "./fixtures";

describe("compare-math", () => {
  it("formats labels and signed values for diff surfaces", () => {
    expect(formatSignedNumber(0.1234)).toBe("+0.123");
    expect(formatSignedNumber(-8)).toBe("-8.00");
    expect(significanceLabel("not_comparable")).toBe("not comparable");
    expect(comparabilityLabel("warning")).toBe("Comparable with warnings");
  });

  it("sorts deltas by decision salience", () => {
    const deltas = topDeltas(policyDiffFixture.deltas ?? [], 1);
    expect(deltas).toHaveLength(1);
    expect(deltas[0].metric_id).toBe("employment_rate_delta");
    expect(saliencePercent(deltas[0])).toBe(82);
  });

  it("does not reclassify producer comparability or significance into badge tones", () => {
    expect(compareMath).not.toHaveProperty("comparabilityTone");
    expect(compareMath).not.toHaveProperty("significanceTone");
  });
});
