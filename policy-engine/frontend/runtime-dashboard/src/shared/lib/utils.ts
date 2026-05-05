import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import { formatCurrency } from "../i18n/formatters/currency";
import {
  formatDate,
  formatRelativeTime,
  formatTime,
} from "../i18n/formatters/date";
import { formatNumber, formatPercent } from "../i18n/formatters/number";
import type { Locale } from "../i18n/locale";

export {
  formatCurrency,
  formatDate,
  formatNumber,
  formatPercent,
  formatRelativeTime,
  formatTime,
};

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
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
