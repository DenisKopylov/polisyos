import { formatCurrency } from "./currency";
import {
  formatDate,
  formatIsoDate,
  formatIsoDateTime,
  formatLongDate,
  formatRelativeTime,
  formatTime,
} from "./date";
import { formatNumber, formatPercent } from "./number";

const NBSP = "\u00A0";
const TIMESTAMP = "2026-04-22T14:30:00Z";

describe("i18n formatters", () => {
  it.each([
    ["en", 0, "0"],
    ["en", 1, "1"],
    ["en", 2, "2"],
    ["en", 5, "5"],
    ["en", 11, "11"],
    ["en", 21, "21"],
    ["en", 101, "101"],
    ["uk", 0, "0"],
    ["uk", 1, "1"],
    ["uk", 2, "2"],
    ["uk", 5, "5"],
    ["uk", 11, "11"],
    ["uk", 21, "21"],
    ["uk", 101, "101"],
    ["ru", 0, "0"],
    ["ru", 1, "1"],
    ["ru", 2, "2"],
    ["ru", 5, "5"],
    ["ru", 11, "11"],
    ["ru", 21, "21"],
    ["ru", 101, "101"],
  ] as const)(
    "formats scalar numbers for %s locale (%s)",
    (locale, value, expected) => {
      expect(formatNumber(value, undefined, locale)).toBe(expected);
    },
  );

  it("formats localized separators and percentages", () => {
    expect(formatNumber(1234567.89, undefined, "en")).toBe("1,234,567.89");
    expect(formatNumber(1234567.89, undefined, "uk")).toBe(
      `1${NBSP}234${NBSP}567,89`,
    );
    expect(formatNumber(1234567.89, undefined, "ru")).toBe(
      `1${NBSP}234${NBSP}567,89`,
    );
    expect(formatPercent(0.256, undefined, "en")).toBe("25.6%");
    expect(formatPercent(0.256, undefined, "uk")).toBe("25,6%");
    expect(formatPercent(Number.NaN, undefined, "uk")).toBe("-");
  });

  it.each([
    ["en", "USD", "$12.30"],
    ["en", "EUR", "€12.30"],
    ["en", "UAH", "₴12.30"],
    ["uk", "USD", `12,30${NBSP}$`],
    ["uk", "EUR", `12,30${NBSP}€`],
    ["uk", "UAH", `12,30${NBSP}₴`],
    ["ru", "USD", `12,30${NBSP}$`],
    ["ru", "EUR", `12,30${NBSP}€`],
    ["ru", "UAH", `12,30${NBSP}₴`],
  ] as const)(
    "formats %s currency in %s locale",
    (locale, currency, expected) => {
      expect(formatCurrency(12.3, currency, locale)).toBe(expected);
    },
  );

  it("formats dates in locale-aware and ISO variants", () => {
    expect(formatDate(undefined, "en")).toBe("-");
    expect(formatDate("not-a-date", "en")).toBe("not-a-date");
    expect(formatLongDate(TIMESTAMP, "uk", { timeZone: "UTC" })).toBe(
      "22 квітня 2026 р.",
    );
    expect(formatLongDate(TIMESTAMP, "ru", { timeZone: "UTC" })).toBe(
      "22 апреля 2026 г.",
    );
    expect(formatLongDate(TIMESTAMP, "en", { timeZone: "UTC" })).toBe(
      "April 22, 2026",
    );
    expect(
      formatDate(TIMESTAMP, "uk", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "UTC",
      }),
    ).toBe(`22 квіт. 2026 р., 14:30`);
    expect(formatTime(TIMESTAMP, "en", { hour12: true, timeZone: "UTC" })).toBe(
      "02:30 PM",
    );
    expect(
      formatTime(TIMESTAMP, "uk", { hour12: false, timeZone: "UTC" }),
    ).toBe("14:30");
    expect(formatIsoDate(TIMESTAMP)).toBe("2026-04-22");
    expect(formatIsoDateTime(TIMESTAMP)).toBe("2026-04-22 14:30");
  });

  it("formats relative time boundaries", () => {
    expect(
      formatRelativeTime("2026-04-22T14:29:30Z", "en", "2026-04-22T14:30:00Z"),
    ).toContain("second");
    expect(
      formatRelativeTime("2026-04-22T14:00:00Z", "en", "2026-04-22T14:30:00Z"),
    ).toContain("minute");
    expect(
      formatRelativeTime("2026-04-22T10:30:00Z", "en", "2026-04-22T14:30:00Z"),
    ).toContain("hour");
    expect(
      formatRelativeTime("2026-04-20T14:30:00Z", "en", "2026-04-22T14:30:00Z"),
    ).toContain("day");
  });
});
