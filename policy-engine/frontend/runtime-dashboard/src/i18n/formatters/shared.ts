import type { Locale } from "../locale";
import { resolveLocale, toIntlLocale } from "../locale";

export type DateValue = Date | number | string | null | undefined;

export function resolveIntlLocale(locale?: Locale): string {
  return toIntlLocale(locale ?? resolveLocale());
}

export function resolveDate(value: DateValue): Date | null {
  if (value === null || value === undefined) {
    return null;
  }

  const date = value instanceof Date ? new Date(value) : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return date;
}

export function fallbackDateValue(value: DateValue): string {
  if (typeof value === "string") {
    return value;
  }
  return "-";
}
