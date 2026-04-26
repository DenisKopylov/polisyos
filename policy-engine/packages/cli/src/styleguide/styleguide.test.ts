import { describe, expect, it } from "vitest";

import { formatProvenance } from "./format-provenance";
import { formatProgress, formatStatus } from "./format-status";
import { formatTable } from "./format-table";

describe("CLI styleguide", () => {
  it("formats trust statuses as ASCII-safe snapshot tokens", () => {
    expect(
      formatStatus("verified", { includeDescription: true }),
    ).toMatchInlineSnapshot(
      `"[VERIFIED] Lineage and hash verification completed for this temporal scope."`,
    );
    expect(formatStatus("untraced", { severity: "warning" })).toBe(
      "WRN [UNTRACED]",
    );
  });

  it("formats progress without relying on color or spinners", () => {
    expect(
      formatProgress("running", "rendering bureaucratic exports", {
        current: 3,
        total: 5,
      }),
    ).toBe("RUNNING 3/5 rendering bureaucratic exports");
  });

  it("formats stable fixed-width tables", () => {
    expect(
      formatTable(
        ["metric", "status", "delta"],
        [
          ["employment", "[VERIFIED]", "+1.4pp"],
          ["budget", "[STALE]", "-3200"],
        ],
      ),
    ).toMatchInlineSnapshot(`
      "metric     | status     | delta 
      -----------+------------+-------
      employment | [VERIFIED] | +1.4pp
      budget     | [STALE]    |  -3200"
    `);
  });

  it("formats provenance without dropping temporal scope", () => {
    expect(
      formatProvenance({
        hash: "sha256:abcdef1234567890",
        method: "lineage_hash_match",
        source: "QES 2024 Q3",
        status: "verified",
        temporalScope: {
          branch: "main",
          txAt: "2026-04-16T09:20:00Z",
          validAt: "2026-04-15T12:00:00Z",
        },
        unit: "ratio",
        valueLabel: "effect_size=0.23",
        verifiedAt: "2026-04-16T09:20:00Z",
        verifiedBy: "RiskReviewBot@2.0",
      }),
    ).toMatchInlineSnapshot(`
      "provenance [VERIFIED] sha256:abcdef1234...
      value      effect_size=0.23 (ratio)
      source     QES 2024 Q3
      method     lineage_hash_match
      verified  RiskReviewBot@2.0 at 2026-04-16T09:20:00Z
      time       valid=2026-04-15T12:00:00Z tx=2026-04-16T09:20:00Z branch=main"
    `);
  });
});
