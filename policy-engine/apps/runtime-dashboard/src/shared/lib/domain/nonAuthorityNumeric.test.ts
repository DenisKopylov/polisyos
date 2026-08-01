import * as nonAuthorityNumeric from "./nonAuthorityNumeric";

describe("non-authority numeric classifications", () => {
  it("preserves numeric runtime identity without exporting a value vocabulary", () => {
    expect(nonAuthorityNumeric.interactionControl(0.0025)).toBe(0.0025);
    expect(nonAuthorityNumeric.layoutGeometry(-24)).toBe(-24);
    expect(nonAuthorityNumeric.motionGeometry(0.3)).toBe(0.3);
    expect(nonAuthorityNumeric.operationalRequestControl(0)).toBe(0);
    expect(Object.keys(nonAuthorityNumeric).sort()).toEqual([
      "interactionControl",
      "layoutGeometry",
      "motionGeometry",
      "operationalRequestControl",
    ]);
  });
});
