import type { Locale } from "../locale";
import { resolveIntlLocale } from "./shared";

export function formatCurrency(
  value: number | null | undefined,
  currency = "USD",
  locale?: Locale,
  options?: Intl.NumberFormatOptions,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat(resolveIntlLocale(locale), {
    style: "currency",
    currency,
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    ...options,
  }).format(value);
}
