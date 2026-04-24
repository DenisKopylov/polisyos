import { IntlMessageFormat } from "intl-messageformat";

import type { Locale } from "./locale";
import { toIntlLocale } from "./locale";

export type MessagePrimitive =
  | boolean
  | Date
  | number
  | string
  | null
  | undefined;
export type MessageValues = Record<string, MessagePrimitive>;
export type RichMessageValues = Record<string, unknown>;

const LEGACY_PLACEHOLDER_PATTERN = /\{\{\s*([A-Za-z0-9_]+)\s*\}\}/g;
const XML_TAG_PATTERN = /<([a-z][a-z0-9-]*)>/giu;
const formatterCache = new Map<string, IntlMessageFormat>();

function normalizeMessageTemplate(message: string): string {
  return message.replace(LEGACY_PLACEHOLDER_PATTERN, "{$1}");
}

function readXmlTags(message: string): string[] {
  const tags = new Set<string>();

  for (const match of message.matchAll(XML_TAG_PATTERN)) {
    if (match[1]) {
      tags.add(match[1]);
    }
  }

  return [...tags];
}

function getMessageFormatter(
  message: string,
  locale: Locale,
): IntlMessageFormat {
  const template = normalizeMessageTemplate(message);
  const intlLocale = toIntlLocale(locale);
  const cacheKey = `${intlLocale}::${template}`;
  const cached = formatterCache.get(cacheKey);

  if (cached) {
    return cached;
  }

  const formatter = new IntlMessageFormat(template, intlLocale);
  formatterCache.set(cacheKey, formatter);
  return formatter;
}

function withDefaultXmlResolvers(
  message: string,
  values?: RichMessageValues,
): RichMessageValues | undefined {
  if (!values) {
    const tags = readXmlTags(message);
    if (tags.length === 0) {
      return undefined;
    }
    return Object.fromEntries(
      tags.map((tag) => [tag, (chunks: unknown) => chunks]),
    );
  }

  const nextValues: RichMessageValues = { ...values };
  for (const tag of readXmlTags(message)) {
    if (nextValues[tag] === undefined) {
      nextValues[tag] = (chunks: unknown) => chunks;
    }
  }

  return nextValues;
}

function stringifyFormattedValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((part) => stringifyFormattedValue(part)).join("");
  }
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}

export function formatIcuMessage(
  message: string,
  locale: Locale,
  values?: MessageValues,
): string {
  try {
    const formatter = getMessageFormatter(message, locale);
    return stringifyFormattedValue(formatter.format(values));
  } catch {
    return stringifyFormattedValue(normalizeMessageTemplate(message));
  }
}

export function formatIcuRichMessage(
  message: string,
  locale: Locale,
  values?: RichMessageValues,
): unknown {
  try {
    const formatter = getMessageFormatter(message, locale);
    return formatter.format(withDefaultXmlResolvers(message, values));
  } catch {
    return normalizeMessageTemplate(message);
  }
}

export function formatPluralMessage(
  message: string,
  locale: Locale,
  count: number,
  values?: MessageValues,
): string {
  return formatIcuMessage(message, locale, {
    ...values,
    count,
  });
}

export function isPluralMessage(message: string): boolean {
  return /,\s*plural\s*,/u.test(normalizeMessageTemplate(message));
}
