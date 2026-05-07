import type { QuantityValue, UnitRef } from "./quantity.types";

export type QuantityFormatOptions = {
  format?: "decimal" | "percent" | "currency" | "scientific" | "compact";
  locale?: string;
  maximumFractionDigits?: number;
  minimumFractionDigits?: number;
  showUnit?: boolean;
};

export type FormattedQuantity = {
  value: string;
  unit: string;
  text: string;
};

export function formatQuantityValue(
  quantity: QuantityValue,
  options: QuantityFormatOptions = {},
): FormattedQuantity {
  const value = formatPoint(quantity.point, options);
  const unit = options.showUnit === false ? "" : formatUnit(quantity.unit);
  return {
    value,
    unit,
    text: unit ? `${value} ${unit}` : value,
  };
}

export function formatUnit(unit: UnitRef): string {
  const display = unit.display?.trim();
  if (display && display !== "value") {
    return display;
  }
  if (unit.code === "1") {
    return "";
  }
  return unit.code;
}

function formatPoint(
  value: number | null,
  options: QuantityFormatOptions,
): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }

  const notation = options.format === "compact" ? "compact" : "standard";
  if (options.format === "percent") {
    return new Intl.NumberFormat(options.locale, {
      maximumFractionDigits: options.maximumFractionDigits ?? 2,
      minimumFractionDigits: options.minimumFractionDigits,
      style: "percent",
    }).format(value);
  }
  if (options.format === "currency") {
    return new Intl.NumberFormat(options.locale, {
      currency: "USD",
      maximumFractionDigits: options.maximumFractionDigits ?? 2,
      minimumFractionDigits: options.minimumFractionDigits,
      style: "currency",
    }).format(value);
  }
  if (options.format === "scientific") {
    return new Intl.NumberFormat(options.locale, {
      maximumFractionDigits: options.maximumFractionDigits ?? 3,
      minimumFractionDigits: options.minimumFractionDigits,
      notation: "scientific",
    }).format(value);
  }

  return new Intl.NumberFormat(options.locale, {
    maximumFractionDigits: options.maximumFractionDigits ?? 4,
    minimumFractionDigits: options.minimumFractionDigits,
    notation,
  }).format(value);
}
