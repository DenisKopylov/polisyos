import { parseComposerSearchParams } from "@/features/composer/domain/searchParams";

describe("parseComposerSearchParams", () => {
  it("parses supported mode and fromRun values", () => {
    expect(
      parseComposerSearchParams("/compose?fromRun=run-42&mode=workflow"),
    ).toEqual({
      fromRun: "run-42",
      mode: "workflow",
    });
  });

  it("normalizes unsupported values to null", () => {
    expect(parseComposerSearchParams("/compose?mode=invalid")).toEqual({
      fromRun: null,
      mode: null,
    });
  });
});
