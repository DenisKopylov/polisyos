import { describe, expect, it } from "vitest";

import {
  compareTemporalScopes,
  fromApiTemporalScope,
  normalizeTemporalScope,
  temporalScopeKey,
  toApiTemporalParams,
} from "./temporal";

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

  it("compares normalized scopes", () => {
    expect(
      compareTemporalScopes(
        { validAt: "2026-04-15T12:00:00Z" },
        {
          validAt: "2026-04-15T15:00:00+03:00",
        },
      ),
    ).toBe(true);
  });

  it("normalizes generated API payloads", () => {
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
