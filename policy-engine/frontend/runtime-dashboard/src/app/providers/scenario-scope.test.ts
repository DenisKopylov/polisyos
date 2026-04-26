import { describe, expect, it } from "vitest";

import {
  compareScenarioScopes,
  readScenarioScopeFromSearchParams,
  scenarioScopeKey,
  serializeScenarioUrlParams,
  writeScenarioScopeToSearchParams,
} from "./scenario-scope";

describe("scenario-scope", () => {
  it("round-trips scenario id and mode through URL params", () => {
    const serialized = serializeScenarioUrlParams({
      scenarioId: "scn_rate_cut_25bps",
      mode: "actual_vs_scenario",
    });

    expect(serialized).toContain("scenario_id=scn_rate_cut_25bps");
    expect(serialized).toContain("cf_mode=actual_vs_scenario");
    expect(
      readScenarioScopeFromSearchParams(new URLSearchParams(serialized)),
    ).toEqual({
      scenarioId: "scn_rate_cut_25bps",
      mode: "actual_vs_scenario",
    });
  });

  it("preserves unrelated temporal params while replacing scenario params", () => {
    const params = new URLSearchParams(
      "valid_at=2026-04-15T12%3A00%3A00.000Z&scenario_id=old&cf_mode=scenario_only",
    );

    writeScenarioScopeToSearchParams(params, {
      scenarioId: "scn_new",
      mode: "actual_vs_scenario",
    });

    expect(params.get("valid_at")).toBe("2026-04-15T12:00:00.000Z");
    expect(params.get("scenario_id")).toBe("scn_new");
    expect(params.get("cf_mode")).toBe("actual_vs_scenario");
  });

  it("normalizes invalid modes to actual for stable keys", () => {
    expect(
      scenarioScopeKey({
        scenarioId: " scn_1 ",
        mode: "legacy" as never,
      }),
    ).toEqual({ scenarioId: "scn_1", mode: "actual" });
    expect(compareScenarioScopes(null, { mode: "actual" })).toBe(true);
  });
});
