import { describe, expect, it } from "vitest";

import {
  compareTemporalScopes,
  fromApiTemporalScope,
  normalizeTemporalScope,
  temporalScopeKey,
  toApiTemporalParams,
} from "./temporal-scope";
import {
  readTemporalScopeFromSearchParams,
  serializeTemporalUrlParams,
} from "./temporal-url";

describe("temporal-scope", () => {
  it("normalizes timestamps to UTC", () => {
    expect(
      normalizeTemporalScope({
        txAt: "2026-04-16T12:20:00+03:00",
        validAt: "2026-04-15T15:00:00+03:00",
      }),
    ).toEqual({
      branch: null,
      scenarioId: null,
      snapshotId: null,
      txAt: "2026-04-16T09:20:00.000Z",
      validAt: "2026-04-15T12:00:00.000Z",
    });
  });

  it("serializes API and query-key shapes", () => {
    const scope = {
      branch: "main",
      txAt: "2026-04-16T09:20:00Z",
      validAt: "2026-04-15T12:00:00Z",
    };

    expect(toApiTemporalParams(scope)).toEqual({
      branch: "main",
      tx_at: "2026-04-16T09:20:00.000Z",
      valid_at: "2026-04-15T12:00:00.000Z",
    });
    expect(temporalScopeKey(scope)).toMatchObject({
      branch: "main",
      txAt: "2026-04-16T09:20:00.000Z",
      validAt: "2026-04-15T12:00:00.000Z",
    });
  });

  it("parses shorthand and compares normalized scopes", () => {
    const parsed = readTemporalScopeFromSearchParams(
      new URLSearchParams("?t=2026-04-15T12:00:00Z"),
    );

    expect(parsed?.validAt).toBe("2026-04-15T12:00:00.000Z");
    expect(
      compareTemporalScopes(parsed, {
        validAt: "2026-04-15T15:00:00+03:00",
      }),
    ).toBe(true);
  });

  it("round-trips canonical URL params and API payloads", () => {
    const query = serializeTemporalUrlParams({
      branch: "main",
      validAt: "2026-04-15T12:00:00Z",
    });

    expect(query).toBe("valid_at=2026-04-15T12%3A00%3A00.000Z&branch=main");
    expect(
      fromApiTemporalScope({
        branch: "main",
        tx_at: null,
        valid_at: "2026-04-15T12:00:00Z",
      }),
    ).toEqual({
      branch: "main",
      scenarioId: null,
      snapshotId: null,
      txAt: null,
      validAt: "2026-04-15T12:00:00.000Z",
    });
  });
});
