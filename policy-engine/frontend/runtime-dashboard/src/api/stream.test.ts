import { buildRuntimeStreamUrl } from "@/api/stream";

describe("buildRuntimeStreamUrl", () => {
  it("keeps relative urls and appends query params", () => {
    expect(
      buildRuntimeStreamUrl("/api/v1/runs/live", {
        cursor: "cursor-1",
      }),
    ).toBe("/api/v1/runs/live?cursor=cursor-1");
  });
});
