import {
  createContext,
  type PropsWithChildren,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  formatIcuMessage,
  formatIcuRichMessage,
  type MessageValues,
} from "./icu-messages";
import type { Locale } from "./locale";
import { persistLocale, resolveLocale } from "./locale";
import en from "./locales/en.json";
import ru from "./locales/ru.json";
import uk from "./locales/uk.json";
import {
  applyLocaleTypography,
  applyTypographyToReactNode,
  type LocaleTypographyOptions,
} from "./typography/typography";

const catalogs = { en, uk, ru } as const;

type LabelMapName = keyof typeof en.labels;

type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (
    path: string,
    vars?: MessageValues,
    options?: LocaleTypographyOptions,
  ) => string;
  rich: (
    path: string,
    vars?: Record<string, unknown>,
    options?: LocaleTypographyOptions,
  ) => ReactNode;
  label: (
    mapName: LabelMapName,
    value: string | null | undefined,
    fallback?: string,
  ) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

function humanize(value: string): string {
  return value
    .replace(/[_.-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function readPathValue(source: unknown, path: string): string | null {
  const segments = path.split(".");
  let current: unknown = source;
  for (const segment of segments) {
    if (!current || typeof current !== "object" || !(segment in current)) {
      return null;
    }
    current = (current as Record<string, unknown>)[segment];
  }
  return typeof current === "string" ? current : null;
}

function createI18nContextValue(
  locale: Locale,
  setLocale: (locale: Locale) => void,
): I18nContextValue {
  const catalog = catalogs[locale];

  return {
    locale,
    setLocale,
    t: (path, vars, options) => {
      const translated =
        readPathValue(catalog, path) ??
        readPathValue(catalogs.en, path) ??
        path;
      return applyLocaleTypography(
        formatIcuMessage(translated, locale, vars),
        locale,
        options,
      );
    },
    rich: (path, vars, options) => {
      const translated =
        readPathValue(catalog, path) ??
        readPathValue(catalogs.en, path) ??
        path;
      return applyTypographyToReactNode(
        formatIcuRichMessage(translated, locale, vars) as ReactNode,
        locale,
        options,
      );
    },
    label: (mapName, value, fallback) => {
      if (!value) {
        return fallback ?? "-";
      }
      const direct =
        readPathValue(catalog.labels[mapName], value) ??
        readPathValue(catalogs.en.labels[mapName], value);
      if (direct) {
        return applyLocaleTypography(direct, locale);
      }
      return applyLocaleTypography(fallback ?? humanize(value), locale);
    },
  };
}

export function LocaleProvider({ children }: PropsWithChildren) {
  const [locale, setLocaleState] = useState<Locale>(() => resolveLocale());

  useEffect(() => {
    persistLocale(locale);
    document.documentElement.lang = locale;
  }, [locale]);

  const value = useMemo<I18nContextValue>(
    () => createI18nContextValue(locale, setLocaleState),
    [locale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useOptionalI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  return context ?? createI18nContextValue(resolveLocale(), () => undefined);
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within LocaleProvider");
  }
  return context;
}
