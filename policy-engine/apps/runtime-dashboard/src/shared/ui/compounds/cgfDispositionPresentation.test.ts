import * as cgfDispositionPresentation from "./cgfDispositionPresentation";

describe("CGF disposition presentation", () => {
  it("renders a novel owner label as explicit unrecognized presentation", () => {
    const ownerValue = {
      disposition: "future-owner-disposition",
      owner_extension: { explanation: "opaque owner payload" },
    };

    expect(
      cgfDispositionPresentation.presentCgfDisposition(ownerValue),
    ).toEqual({
      classification: "unrecognized",
      ownerValue,
    });
  });

  it("exports no value-level vocabulary constants", () => {
    expect(Object.keys(cgfDispositionPresentation)).toEqual([
      "presentCgfDisposition",
    ]);
  });
});
