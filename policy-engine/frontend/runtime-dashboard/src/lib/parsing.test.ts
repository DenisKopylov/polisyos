import {
  asArray,
  asBoolean,
  asNumber,
  asRecord,
  asString,
  clamp,
  formatMaybeNumber,
  toDisplayLabel,
} from "@/lib/parsing";

describe("parsing helpers", () => {
  it("normalizes records and arrays", () => {
    expect(asRecord({ feature: "runs" })).toEqual({ feature: "runs" });
    expect(asRecord(["not", "a", "record"])).toBeNull();
    expect(asRecord(null)).toBeNull();

    expect(asArray(["a", "b"])).toEqual(["a", "b"]);
    expect(asArray("a")).toEqual([]);
  });

  it("reads strings, numbers, booleans, and display labels", () => {
    expect(asString("  atlas shell  ")).toBe("atlas shell");
    expect(asString("   ")).toBeNull();
    expect(asString(42)).toBe("42");
    expect(asString(Number.POSITIVE_INFINITY)).toBeNull();

    expect(asNumber(12.5)).toBe(12.5);
    expect(asNumber(" 1,234.5 ")).toBe(1234.5);
    expect(asNumber("")).toBeNull();
    expect(asNumber("nan")).toBeNull();

    expect(asBoolean(true)).toBe(true);
    expect(asBoolean(" FALSE ")).toBe(false);
    expect(asBoolean("pending")).toBeNull();

    expect(toDisplayLabel("legal_transport-summary")).toBe(
      "Legal Transport Summary",
    );
  });

  it("formats maybe-numbers and clamps ranges", () => {
    expect(formatMaybeNumber(1.2345)).toBe("1.23");
    expect(formatMaybeNumber(1.2345, 3)).toBe("1.234");
    expect(formatMaybeNumber(null)).toBe("-");
    expect(formatMaybeNumber(undefined)).toBe("-");
    expect(formatMaybeNumber(Number.NaN)).toBe("-");

    expect(clamp(5, 0, 10)).toBe(5);
    expect(clamp(-5, 0, 10)).toBe(0);
    expect(clamp(15, 0, 10)).toBe(10);
  });
});
