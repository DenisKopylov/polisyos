import {
  buildLexHref,
  parseLexSearchParams,
} from "@/features/lex/domain/searchParams";

describe("lex search params", () => {
  it("parses and builds lex route search", () => {
    expect(
      parseLexSearchParams(
        "/knowledge?pipelineId=pipe-1&outputDir=data%2Flex&q=water&resume=true",
      ),
    ).toEqual({
      outputDir: "data/lex",
      pipelineId: "pipe-1",
      q: "water",
      resume: true,
    });

    expect(
      buildLexHref({
        outputDir: "data/lex",
        pipelineId: "pipe-1",
        q: "water",
        resume: true,
      }),
    ).toBe(
      "/knowledge?outputDir=data%2Flex&pipelineId=pipe-1&q=water&resume=true",
    );
  });
});
