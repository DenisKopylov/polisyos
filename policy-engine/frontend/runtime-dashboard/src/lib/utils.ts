import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import { resolveLocale, toIntlLocale, type Locale } from "../i18n/locale";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

type DateValue = Date | number | string | null | undefined;

function resolveIntlLocale(locale?: Locale): string {
  return toIntlLocale(locale ?? resolveLocale());
}

function resolveDate(value: DateValue): Date | null {
  if (value === null || value === undefined) {
    return null;
  }
  const date = value instanceof Date ? new Date(value) : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date;
}

function fallbackDateValue(value: DateValue): string {
  if (typeof value === "string") {
    return value;
  }
  return "-";
}

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
    maximumFractionDigits: 2,
    ...options,
  }).format(value);
}

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

export function formatDuration(
  durationMs: number | null | undefined,
  locale?: Locale,
): string {
  if (durationMs === null || durationMs === undefined) {
    return "-";
  }
  if (durationMs < 1000) {
    return `${formatNumber(durationMs, undefined, locale)} ms`;
  }
  if (durationMs < 60_000) {
    return `${formatNumber(durationMs / 1000, { maximumFractionDigits: 2 }, locale)} s`;
  }
  if (durationMs < 3_600_000) {
    return `${formatNumber(durationMs / 60_000, { maximumFractionDigits: 1 }, locale)} min`;
  }
  return `${formatNumber(durationMs / 3_600_000, { maximumFractionDigits: 1 }, locale)} h`;
}

export function formatBytes(
  bytes: number | null | undefined,
  locale?: Locale,
): string {
  if (bytes === null || bytes === undefined) {
    return "-";
  }
  if (bytes < 1024) {
    return `${formatNumber(bytes, undefined, locale)} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${formatNumber(bytes / 1024, { maximumFractionDigits: 1 }, locale)} KB`;
  }
  if (bytes < 1024 * 1024 * 1024) {
    return `${formatNumber(bytes / (1024 * 1024), { maximumFractionDigits: 2 }, locale)} MB`;
  }
  return `${formatNumber(bytes / (1024 * 1024 * 1024), { maximumFractionDigits: 2 }, locale)} GB`;
}
