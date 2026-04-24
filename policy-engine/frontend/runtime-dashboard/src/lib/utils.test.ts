import {
  cn,
  formatBytes,
  formatCurrency,
  formatDate,
  formatDuration,
  formatNumber,
  formatPercent,
  formatRelativeTime,
  formatTime,
} from "@/lib/utils";

describe("utils formatters", () => {
  it("merges tailwind classes", () => {
    expect(
      cn("px-2", ["text-sm", "font-medium"], "px-4", {
        hidden: false,
        block: true,
      }),
    ).toBe("text-sm font-medium px-4 block");
  });

  it("formats numbers, percentages, and currency", () => {
    expect(formatNumber(1234.5, undefined, "en")).toBe("1,234.5");
    expect(formatNumber(null, undefined, "en")).toBe("-");

    expect(formatPercent(0.256, undefined, "en")).toBe("25.6%");
    expect(formatPercent(Number.NaN, undefined, "en")).toBe("-");

    expect(formatCurrency(12.3, "USD", "en")).toBe("$12.30");
    expect(formatCurrency(12.3, "USD", "uk")).toBe("12,30 $");
    expect(formatCurrency(undefined, "USD", "en")).toBe("-");
  });

  it("formats dates, durations, and bytes", () => {
    expect(formatDate(undefined, "en")).toBe("-");
    expect(formatDate("not-a-date", "en")).toBe("not-a-date");
    expect(formatDate("2026-03-09T12:00:00Z", "en")).toContain("2026");
    expect(formatTime("not-a-date", "en")).toBe("not-a-date");
    expect(formatTime("2026-03-09T12:34:00Z", "en")).toMatch(/\d/);
    expect(
      formatRelativeTime("2026-03-09T11:59:00Z", "en", "2026-03-09T12:00:00Z"),
    ).toContain("minute");

    expect(formatDuration(null, "en")).toBe("-");
    expect(formatDuration(500, "en")).toBe("500 ms");
    expect(formatDuration(1_500, "en")).toBe("1.5 s");
    expect(formatDuration(61_000, "en")).toBe("1 min");
    expect(formatDuration(3_600_000, "en")).toBe("1 h");

    expect(formatBytes(null, "en")).toBe("-");
    expect(formatBytes(512, "en")).toBe("512 B");
    expect(formatBytes(2 * 1024, "en")).toBe("2 KB");
    expect(formatBytes(3 * 1024 * 1024, "en")).toBe("3 MB");
    expect(formatBytes(2 * 1024 * 1024 * 1024, "en")).toBe("2 GB");
  });
});
