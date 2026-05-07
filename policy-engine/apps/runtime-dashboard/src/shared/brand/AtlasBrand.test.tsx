import {
  getAtlasLogoMarkBucket,
  resolveAtlasLogoMarkAsset,
} from "@/shared/brand/AtlasBrand";

describe("AtlasBrand assets", () => {
  it("keeps Atlas marks on the public/favicon-sized path", () => {
    expect(getAtlasLogoMarkBucket(12)).toBe(16);
    expect(resolveAtlasLogoMarkAsset({ size: 16 })).toBe(
      "/atlas/logo-mark.svg",
    );
  });

  it("keeps the shared logo mark asset for 32px and 48px sizes", () => {
    expect(getAtlasLogoMarkBucket(32)).toBe(32);
    expect(getAtlasLogoMarkBucket(48)).toBe(48);
    expect(resolveAtlasLogoMarkAsset({ size: 32 })).toBe(
      "/atlas/logo-mark.svg",
    );
    expect(resolveAtlasLogoMarkAsset({ inverted: true, size: 48 })).toBe(
      "/atlas/logo-mark-inverse.svg",
    );
  });
});
