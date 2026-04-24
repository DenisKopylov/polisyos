import type { Locale } from "../locale";
import { resolveIntlLocale } from "./shared";

export function formatNumber(
  value: number | null | undefined,
  options?: Intl.NumberFormatOptions,
  locale?: Locale,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat(resolveIntlLocale(locale), options).format(
    value,
  );
}

export function formatPercent(
  value: number | null | undefined,
  options?: Intl.NumberFormatOptions,
  locale?: Locale,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat(resolveIntlLocale(locale), {
    style: "percent",
    maximumFractionDigits: 1,
    ...options,
  }).format(value);
}
