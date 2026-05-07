import type { Locale } from "../locale";
import {
  fallbackDateValue,
  type DateValue,
  resolveDate,
  resolveIntlLocale,
} from "./shared";

export function formatDate(
  value: DateValue,
  locale?: Locale,
  options?: Intl.DateTimeFormatOptions,
): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  const date = resolveDate(value);
  if (!date) {
    return fallbackDateValue(value);
  }

  return new Intl.DateTimeFormat(resolveIntlLocale(locale), {
    dateStyle: "medium",
    timeStyle: "short",
    ...options,
  }).format(date);
}

export function formatLongDate(
  value: DateValue,
  locale?: Locale,
  options?: Intl.DateTimeFormatOptions,
): string {
  return formatDate(value, locale, {
    dateStyle: "long",
    timeStyle: undefined,
    ...options,
  });
}

export function formatIsoDate(value: DateValue): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  const date = resolveDate(value);
  if (!date) {
    return fallbackDateValue(value);
  }

  return date.toISOString().slice(0, 10);
}

export function formatIsoDateTime(value: DateValue): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  const date = resolveDate(value);
  if (!date) {
    return fallbackDateValue(value);
  }

  return date.toISOString().slice(0, 16).replace("T", " ");
}

export function formatTime(
  value: DateValue,
  locale?: Locale,
  options?: Intl.DateTimeFormatOptions,
): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  const date = resolveDate(value);
  if (!date) {
    return fallbackDateValue(value);
  }

  return new Intl.DateTimeFormat(resolveIntlLocale(locale), {
    hour: "2-digit",
    minute: "2-digit",
    ...options,
  }).format(date);
}

export function formatRelativeTime(
  value: DateValue,
  locale?: Locale,
  now: DateValue = Date.now(),
): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  const date = resolveDate(value);
  const reference = resolveDate(now);
  if (!date || !reference) {
    return fallbackDateValue(value);
  }

  const diffSeconds = Math.round((reference.getTime() - date.getTime()) / 1000);
  const formatter = new Intl.RelativeTimeFormat(resolveIntlLocale(locale), {
    numeric: "auto",
  });

  if (Math.abs(diffSeconds) < 60) {
    return formatter.format(-diffSeconds, "second");
  }

  const diffMinutes = Math.round(diffSeconds / 60);
  if (Math.abs(diffMinutes) < 60) {
    return formatter.format(-diffMinutes, "minute");
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (Math.abs(diffHours) < 24) {
    return formatter.format(-diffHours, "hour");
  }

  const diffDays = Math.round(diffHours / 24);
  return formatter.format(-diffDays, "day");
}
