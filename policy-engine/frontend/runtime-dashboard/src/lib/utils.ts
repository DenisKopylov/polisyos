import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import { resolveLocale, toIntlLocale, type Locale } from "../i18n/locale";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

function resolveIntlLocale(locale?: Locale): string {
  return toIntlLocale(locale ?? resolveLocale());
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
  value: string | null | undefined,
  locale?: Locale,
): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(resolveIntlLocale(locale), {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
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
