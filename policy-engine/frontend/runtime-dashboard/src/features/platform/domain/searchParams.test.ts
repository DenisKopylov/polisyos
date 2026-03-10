import {
  buildPlatformHref,
  parsePlatformSearchParams,
} from "@/features/platform/domain/searchParams";

describe("platform search params", () => {
  it("parses and builds section filters", () => {
    expect(parsePlatformSearchParams("/platform?section=health")).toEqual({
      section: "health",
    });
    expect(buildPlatformHref({ section: "constraints" })).toBe(
      "/platform?section=constraints",
    );
  });
});
