import * as cacheAgePresentation from "./cacheAgePresentation";

describe("cache-age presentation", () => {
  it("renders a novel owner label as explicit unrecognized presentation", () => {
    expect(
      cacheAgePresentation.presentCacheAgeLabel("future-owner-state"),
    ).toEqual({
      classification: "unrecognized",
      ownerLabel: "future-owner-state",
    });
  });

  it("exports no value-level vocabulary constants", () => {
    expect(Object.keys(cacheAgePresentation)).toEqual(["presentCacheAgeLabel"]);
  });
});
