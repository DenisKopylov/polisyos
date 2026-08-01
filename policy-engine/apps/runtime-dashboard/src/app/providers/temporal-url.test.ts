import { describe, expect, it } from "vitest";

import {
  readTemporalScopeFromSearchParams,
  serializeTemporalUrlParams,
} from "./temporal-url";

describe("temporal URL binding", () => {
  it("parses the valid-time shorthand without conflating time roles", () => {
    const parsed = readTemporalScopeFromSearchParams(
      new URLSearchParams("?t=2026-04-15T12:00:00Z"),
    );

    expect(parsed).toMatchObject({
      txAt: null,
      validAt: "2026-04-15T12:00:00.000Z",
    });
  });

  it("serializes canonical URL parameters", () => {
    expect(
      serializeTemporalUrlParams({
        branch: "main",
        validAt: "2026-04-15T12:00:00Z",
      }),
    ).toBe("valid_at=2026-04-15T12%3A00%3A00.000Z&branch=main");
  });
});
